"""Graph-free M1.2 review-scope persistence.

Structural justification: scope loading, producer binding, and publication
remain together because they enforce one candidate-addressed root/base
invariant across cold restart. Splitting those checks would duplicate the
closed artifact and Git-fact validation boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._authority import _validate_state_snapshot
from ._locking import _locked
from ._plan_candidate import validate_plan_approval_candidate
from ._repository_git import _git
from ._state import _load_run_context
from ._validation_schema import _validate_schema
from .bundle import canonical_json, supports_review_evidence
from .repository import RepositoryCaptureError
from .review import ImmutableArtifactLocator, ReviewScopeArtifact
from .storage import (
    _atomic_write_at,
    _close,
    _open_dir,
    _read_contained,
    _read_file,
    _run_dir,
)

_SCOPE_PATH = re.compile(
    r"^\.kapisch/v3/runs/([^/]+)/review-inputs/scopes/([0-9a-f]{64})\.json$"
)
_BINDING_PATH = re.compile(
    r"^review-inputs/review-target-bindings/([0-9a-f]{64})\.json$"
)
_ROOT_PATH = re.compile(
    r"^\.kapisch/v3/runs/([^/]+)/review-inputs/comparison-roots/([0-9a-f]{64})\.json$"
)
_TARGET_PATH = re.compile(
    r"^\.kapisch/v3/runs/([^/]+)/review-inputs/review-targets/([0-9a-f]{64})\.json$"
)
_BASE_PATH = re.compile(
    r"^\.kapisch/v3/runs/([^/]+)/review-inputs/comparison-bases/([0-9a-f]{64})\.json$"
)
_PRE_DISPATCH_PATH = re.compile(
    r"^\.kapisch/v3/runs/([^/]+)/review-inputs/(op-[0-9a-f]{32})/pre-dispatch-fingerprint\.json$"
)
_CANDIDATE_PATH = re.compile(
    r"^\.kapisch/v3/authority/plan-approval-candidates/([0-9a-f]{64})\.json$"
)
_ANCHOR = re.compile(r"^(sha1|sha256):([0-9a-f]+)$")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("review artifact contains duplicate object key")
        result[key] = value
    return result


def _json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError(f"{label} is malformed JSON") from error
    if not isinstance(value, dict) or canonical_json(value) != data:
        raise ValueError(f"{label} is not canonical JSON")
    return value


def _scope_relative(locator: ImmutableArtifactLocator) -> tuple[str, str]:
    match = _SCOPE_PATH.fullmatch(locator.path)
    if match is None or locator.sha256 != match.group(2):
        raise ValueError("review-scope locator is not canonical")
    return match.group(1), f"review-inputs/scopes/{match.group(2)}.json"


def _read_locator(
    repo: Path,
    run_id: str,
    value: Mapping[str, Any],
    pattern,
    label: str,
    *,
    path_digest: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        raise ValueError(f"{label} reference has invalid shape")
    path = value["path"]
    digest = value["sha256"]
    match = pattern.fullmatch(path) if isinstance(path, str) else None
    if (
        match is None
        or match.group(1) != run_id
        or match.group(2) != (digest if path_digest is None else path_digest)
    ):
        raise ValueError(f"{label} reference is not canonical")
    relative = path.removeprefix(f".kapisch/v3/runs/{run_id}/")
    data = _read_contained(repo, run_id, relative)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"{label} artifact digest mismatch")
    return _json(data, label), data


def _require_anchor(value: Any, object_format: str, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} anchor is invalid")
    match = _ANCHOR.fullmatch(value)
    if match is None or match.group(1) != object_format:
        raise ValueError(f"{label} anchor is invalid")
    width = 40 if object_format == "sha1" else 64
    if len(match.group(2)) != width:
        raise ValueError(f"{label} anchor is invalid")


def _load_root(
    repo: Path,
    run_id: str,
    reference: Mapping[str, Any],
    candidate_ref: Mapping[str, Any],
    plan_id: str,
    target: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        not isinstance(reference, Mapping)
        or not isinstance(reference.get("path"), str)
        or not reference["path"].endswith(
            f"/{candidate_ref.get('sha256')}.json"
        )
    ):
        raise ValueError("comparison-root reference is not candidate-bound")
    root, _ = _read_locator(
        repo,
        run_id,
        reference,
        _ROOT_PATH,
        "comparison-root",
        path_digest=candidate_ref["sha256"],
    )
    if set(root) != {
        "protocol_version",
        "comparison_root_contract",
        "run_id",
        "plan_candidate_ref",
        "plan_id",
        "target",
        "object_format",
        "anchor",
    }:
        raise ValueError("comparison-root artifact has missing or unknown fields")
    if (
        type(root["protocol_version"]) is not int
        or root["protocol_version"] != 3
        or root["comparison_root_contract"] != "comparison-root/1"
        or root["run_id"] != run_id
        or root["plan_candidate_ref"] != candidate_ref
        or root["plan_id"] != plan_id
        or root["target"] != target
        or type(root["object_format"]) is not str
        or root["object_format"] not in {"sha1", "sha256"}
    ):
        raise ValueError("comparison-root binding mismatch")
    _require_anchor(root["anchor"], root["object_format"], "comparison-root")
    return root


def _validate_producer_git(
    repo: Path,
    reservation: Mapping[str, Any],
    *,
    verify_named_ref: bool,
) -> None:
    try:
        base_oid = reservation["base"].split(":", 1)[1]
        head_oid = reservation["head"].split(":", 1)[1]
        root_oid = reservation["comparison_root"]["anchor"].split(":", 1)[1]
        format_bytes = _git(
            repo, "rev-parse", "--show-object-format=storage", no_replace=True
        )
        if format_bytes != f"{reservation['object_format']}\n".encode("ascii"):
            raise ValueError("producer object format differs from repository")
        for oid in (base_oid, head_oid, root_oid):
            if _git(repo, "cat-file", "-t", oid, no_replace=True) != b"commit\n":
                raise ValueError("producer anchor is not an exact commit object")
        _git(repo, "check-ref-format", reservation["target"]["ref"], no_replace=True)
        if reservation["comparison_root"]["must_differ_from_head"] and base_oid == head_oid:
            raise ValueError("strict comparison base cannot equal producer head")
        _git(repo, "merge-base", "--is-ancestor", base_oid, head_oid, no_replace=True)
        if verify_named_ref:
            raw = _git(
                repo,
                "rev-parse",
                "--verify",
                f"{reservation['target']['ref']}^{{commit}}",
                no_replace=True,
            )
            if raw != f"{head_oid}\n".encode("ascii"):
                raise ValueError("producer target ref moved after capture")
    except (RepositoryCaptureError, UnicodeEncodeError) as error:
        raise ValueError("producer Git facts are unavailable or invalid") from error


def _validate_prior_roots(
    repo: Path,
    run_id: str,
    state: Mapping[str, Any],
    current: Mapping[str, Any],
) -> None:
    stage_bindings: dict[str, tuple[str, str]] = {}
    for row in state["history"]:
        bindings = [
            item
            for item in row["evidence"]
            if item.get("kind") == "review-target-binding/1"
        ]
        if len(bindings) > 1:
            raise ValueError("earlier review-target binding is ambiguous")
        if not bindings:
            continue
        item = bindings[0]
        path = item.get("path")
        match = _BINDING_PATH.fullmatch(path or "")
        if match is None or item.get("sha256") != match.group(1):
            raise ValueError("earlier review-target binding locator is invalid")
        data = _read_contained(repo, run_id, path)
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("earlier review-target binding digest mismatch")
        prior = _json(data, "earlier review-target reservation")
        if prior.get("run_id") != run_id or prior.get("stage_id") != row["stage_id"]:
            raise ValueError("earlier review-target binding owner mismatch")
        key = (path, item["sha256"])
        previous = stage_bindings.setdefault(row["stage_id"], key)
        if previous != key:
            raise ValueError("earlier review-target binding is ambiguous")
        prior_reservation, _, _ = _load_bound_base(
            repo,
            run_id,
            state,
            {"stage_id": row["stage_id"], "evidence": bindings},
            verify_git=True,
            _check_prior_roots=False,
        )
        if (
            prior_reservation["plan_candidate_ref"] != current["plan_candidate_ref"]
            or prior_reservation["target"] != current["target"]
        ):
            continue
        if (
            prior_reservation["plan_id"] != current["plan_id"]
            or prior_reservation["comparison_root_ref"]
            != current["comparison_root_ref"]
            or prior_reservation["comparison_root"]["anchor"]
            != current["comparison_root"]["anchor"]
        ):
            raise ValueError("review-target comparison root conflicts with an earlier binding")


def _require_binding_after_creation(
    state: Mapping[str, Any], attempt: Mapping[str, Any], binding: Mapping[str, Any]
) -> None:
    stage_id = attempt["stage_id"]
    rows = [
        (index, row)
        for index, row in enumerate(state["history"])
        if row["stage_id"] == stage_id
    ]
    if not rows:
        raise ValueError("review-target binding has no owning attempt")
    binding_path = binding.get("path")
    binding_digest = binding.get("sha256")
    owning_rows = [
        index
        for index, row in rows
        if any(
            evidence.get("path") == binding_path
            and evidence.get("sha256") == binding_digest
            for evidence in row["evidence"]
        )
    ]
    if not owning_rows or owning_rows[0] <= rows[0][0]:
        raise ValueError("review-target binding must follow attempt creation")


def _reject_conflicting_bindings(
    repo: Path,
    run_id: str,
    binding: Mapping[str, Any],
    reservation: Mapping[str, Any],
) -> None:
    current_name = binding["path"].rsplit("/", 1)[-1]
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        review_inputs = _open_dir(run, "review-inputs")
        try:
            bindings_dir = _open_dir(review_inputs, "review-target-bindings")
        finally:
            _close([review_inputs])
        try:
            for name in os.listdir(bindings_dir):
                match = re.fullmatch(r"([0-9a-f]{64})\.json", name)
                if match is None or name == current_name:
                    continue
                data = _read_file(bindings_dir, name)
                if hashlib.sha256(data).hexdigest() != match.group(1):
                    raise ValueError("review-target binding digest mismatch")
                prior = _json(data, "review-target reservation")
                if (
                    prior.get("run_id") == reservation["run_id"]
                    and prior.get("stage_id") == reservation["stage_id"]
                    and prior.get("plan_candidate_ref")
                    == reservation["plan_candidate_ref"]
                ):
                    raise ValueError("conflicting review-target reservations exist")
        finally:
            _close([bindings_dir])
    except FileNotFoundError:
        return
    finally:
        _close(fds)


def _load_bound_base(
    repo: Path,
    run_id: str,
    state: Mapping[str, Any],
    attempt: Mapping[str, Any],
    *,
    verify_git: bool = False,
    verify_named_ref: bool = False,
    _check_prior_roots: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    evidence = [
        item
        for item in attempt["evidence"]
        if item.get("kind") == "review-target-binding/1"
    ]
    if len(evidence) != 1:
        raise ValueError("exactly one durable review-target binding is required")
    binding = evidence[0]
    match = _BINDING_PATH.fullmatch(binding.get("path", ""))
    if match is None or binding.get("sha256") != match.group(1):
        raise ValueError("review-target binding locator is not canonical")
    reservation_data = _read_contained(repo, run_id, binding["path"])
    if hashlib.sha256(reservation_data).hexdigest() != binding["sha256"]:
        raise ValueError("review-target reservation digest mismatch")
    reservation = _json(reservation_data, "review-target reservation")
    expected_fields = {
        "protocol_version",
        "review_target_binding_contract",
        "run_id",
        "stage_id",
        "plan_candidate_ref",
        "plan_id",
        "target",
        "purpose",
        "comparison_root_ref",
        "comparison_root",
        "comparison_base_ref",
        "object_format",
        "base",
        "head",
        "review_target_ref",
    }
    if (
        type(reservation.get("protocol_version")) is not int
        or reservation.get("protocol_version") != 3
        or reservation.get("review_target_binding_contract")
        != "review-target-binding/1"
    ):
        raise ValueError("review-target reservation protocol or contract is invalid")
    if set(reservation) != expected_fields:
        raise ValueError("review-target reservation has missing or unknown fields")
    def valid_ref(value: Any) -> bool:
        return (
            isinstance(value, Mapping)
            and set(value) == {"path", "sha256"}
            and isinstance(value["path"], str)
            and type(value["sha256"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None
        )

    candidate_ref = state.get("plan_candidate_ref")
    if not isinstance(candidate_ref, Mapping) or reservation["plan_candidate_ref"] != candidate_ref:
        raise ValueError("review-target candidate binding differs from run state")
    if (
        not valid_ref(reservation["plan_candidate_ref"])
        or not valid_ref(reservation["comparison_root_ref"])
        or not valid_ref(reservation["comparison_base_ref"])
        or not valid_ref(reservation["review_target_ref"])
        or not isinstance(reservation["plan_id"], str)
        or not reservation["plan_id"]
        or reservation["run_id"] != run_id
        or reservation["stage_id"] != attempt["stage_id"]
        or type(reservation["purpose"]) is not str
        or reservation["purpose"] not in {"iteration", "final"}
    ):
        raise ValueError("review-target reservation identity is invalid")
    if (
        not isinstance(reservation["comparison_root"], Mapping)
        or set(reservation["comparison_root"])
        != {"source", "anchor", "must_differ_from_head"}
    ):
        raise ValueError("review-target comparison root is invalid")
    if (
        reservation["comparison_root"]["source"] != "stage5-target-binding"
        or type(reservation["comparison_root"]["must_differ_from_head"]) is not bool
    ):
        raise ValueError("review-target comparison root is invalid")
    target = reservation["target"]
    if (
        not isinstance(target, Mapping)
        or set(target) != {"kind", "ref"}
        or target["kind"] != "whole-branch"
        or not isinstance(target["ref"], str)
        or re.fullmatch(r"refs/heads/[^/]+(?:/[^/]+)*", target["ref"]) is None
    ):
        raise ValueError("review-target whole-branch target is invalid")
    if reservation["purpose"] == "final" and not reservation["comparison_root"][
        "must_differ_from_head"
    ]:
        raise ValueError("final review target requires a strict comparison base")
    if (
        type(reservation["object_format"]) is not str
        or reservation["object_format"] not in {"sha1", "sha256"}
    ):
        raise ValueError("review-target object format is invalid")
    _require_anchor(reservation["base"], reservation["object_format"], "base")
    _require_anchor(reservation["head"], reservation["object_format"], "head")
    if reservation["base"] != reservation["comparison_root"]["anchor"]:
        raise ValueError("review-target base differs from comparison root")
    _require_binding_after_creation(state, attempt, binding)
    _reject_conflicting_bindings(repo, run_id, binding, reservation)
    root = _load_root(
        repo,
        run_id,
        reservation["comparison_root_ref"],
        candidate_ref,
        reservation["plan_id"],
        target,
    )
    if reservation["comparison_root"]["anchor"] != root["anchor"]:
        raise ValueError("review-target root differs from established root")
    if _check_prior_roots:
        _validate_prior_roots(repo, run_id, state, reservation)
    target_artifact, _ = _read_locator(
        repo, run_id, reservation["review_target_ref"], _TARGET_PATH, "review-target"
    )
    base_artifact, _ = _read_locator(
        repo, run_id, reservation["comparison_base_ref"], _BASE_PATH, "comparison-base"
    )
    target_fields = {
        "protocol_version", "review_target_contract", "run_id", "stage_id",
        "plan_candidate_ref", "plan_id", "target", "purpose",
        "comparison_root_ref", "comparison_root", "comparison_base_ref",
        "object_format", "base", "head",
    }
    base_fields = {
        "protocol_version", "comparison_base_contract", "run_id", "stage_id",
        "plan_candidate_ref", "plan_id", "target", "purpose",
        "comparison_root_ref", "comparison_root", "object_format", "base", "head",
    }
    if set(target_artifact) != target_fields or set(base_artifact) != base_fields:
        raise ValueError("producer artifact has missing or unknown fields")
    for artifact, contract in (
        (target_artifact, "review-target/1"),
        (base_artifact, "comparison-base/1"),
    ):
        if (
            type(artifact.get("protocol_version")) is not int
            or artifact.get("protocol_version") != 3
        ):
            raise ValueError("producer artifact protocol is invalid")
        if artifact.get("run_id") != run_id or artifact.get("stage_id") != attempt["stage_id"]:
            raise ValueError("producer artifact attempt identity mismatch")
        if artifact.get("plan_candidate_ref") != candidate_ref:
            raise ValueError("producer artifact candidate binding mismatch")
        if artifact.get("plan_id") != reservation["plan_id"] or artifact.get("target") != target:
            raise ValueError("producer artifact target binding mismatch")
        if artifact.get("purpose") != reservation["purpose"]:
            raise ValueError("producer artifact purpose mismatch")
        if artifact.get("comparison_root_ref") != reservation["comparison_root_ref"]:
            raise ValueError("producer artifact root reference mismatch")
        artifact_root = artifact.get("comparison_root")
        if (
            not isinstance(artifact_root, Mapping)
            or set(artifact_root) != {"source", "anchor", "must_differ_from_head"}
            or artifact_root["source"] != "stage5-target-binding"
            or type(artifact_root["must_differ_from_head"]) is not bool
        ):
            raise ValueError("producer artifact root is invalid")
        if artifact_root != reservation["comparison_root"]:
            raise ValueError("producer artifact root mismatch")
        if artifact.get("object_format") != reservation["object_format"]:
            raise ValueError("producer artifact object format mismatch")
        if artifact.get("base") != reservation["base"] or artifact.get("head") != reservation["head"]:
            raise ValueError("producer artifact commit binding mismatch")
        if contract == "review-target/1" and artifact.get("comparison_base_ref") != reservation["comparison_base_ref"]:
            raise ValueError("producer artifact base reference mismatch")
        expected_contract_key = "review_target_contract" if contract == "review-target/1" else "comparison_base_contract"
        if artifact.get(expected_contract_key) != contract:
            raise ValueError("producer artifact contract is invalid")
    candidate, _ = validate_plan_approval_candidate(repo, candidate_ref)
    if (
        candidate.get("run_id") != run_id
        or candidate.get("bundle_digest") != state["bundle_digest"]
        or candidate.get("plan_ref", {}).get("plan_id") != reservation["plan_id"]
    ):
        raise ValueError("review-target plan identity mismatch")
    if candidate.get("execution_binding", {}).get("mode") != "graph-free":
        raise ValueError("unsupported-gate: graph-free candidate is required")
    if verify_git:
        _validate_producer_git(
            repo, reservation, verify_named_ref=verify_named_ref
        )
    return reservation, target_artifact, base_artifact


def load_review_scope(
    repo: Path, locator: ImmutableArtifactLocator
) -> ReviewScopeArtifact:
    """Load one canonical, digest-addressed graph-free review scope."""
    if type(locator) is not ImmutableArtifactLocator:
        raise ValueError("review-scope locator must be an immutable artifact locator")
    run_id, relative = _scope_relative(locator)
    data = _read_contained(Path(repo), run_id, relative)
    if hashlib.sha256(data).hexdigest() != locator.sha256:
        raise ValueError("review-scope artifact digest mismatch")
    value = _json(data, "review-scope artifact")
    scope = ReviewScopeArtifact.from_dict(value)
    if scope.run_id != run_id:
        raise ValueError("review-scope run identity mismatch")
    if hashlib.sha256(scope.canonical_bytes()).hexdigest() != locator.sha256:
        raise ValueError("review-scope canonical bytes differ from locator")
    return scope


def publish_review_scope(
    repo: Path, run_id: str, stage_id: str
) -> ImmutableArtifactLocator:
    """Publish the producer-bound graph-free review scope."""
    repo = Path(repo)
    with _locked(repo, run_id):
        state, bundle = _load_run_context(repo, run_id)
        if not supports_review_evidence(bundle):
            raise ValueError("unsupported-gate: retained bundle lacks review evidence")
        _validate_state_snapshot(repo, run_id, state, bundle)
        _validate_schema(state, "run", bundle)
        candidate_ref = state.get("plan_candidate_ref")
        if not isinstance(candidate_ref, Mapping):
            raise ValueError("review scope requires a retained plan candidate")
        attempts = [row for row in state["history"] if row["stage_id"] == stage_id]
        if not attempts or attempts[0]["status"] != "planned":
            raise ValueError("review scope requires a planned stage attempt")
        latest_attempt = attempts[-1]
        if latest_attempt["status"] != "planned":
            raise ValueError("review scope requires the pre-dispatch planned observation")
        reservation, _, base = _load_bound_base(
            repo,
            run_id,
            state,
            latest_attempt,
            verify_git=True,
            verify_named_ref=True,
        )
        scope = ReviewScopeArtifact(
            run_id=run_id,
            stage_id=stage_id,
            purpose=reservation["purpose"],
            plan_candidate_ref=ImmutableArtifactLocator(
                candidate_ref["path"], candidate_ref["sha256"]
            ),
            comparison_base=base["base"],
        )
        data = scope.canonical_bytes()
        digest = hashlib.sha256(data).hexdigest()
        locator = ImmutableArtifactLocator(
            f".kapisch/v3/runs/{run_id}/review-inputs/scopes/{digest}.json",
            digest,
        )
        run, fds = _run_dir(repo, run_id, create=True)
        try:
            review_inputs = _open_dir(run, "review-inputs", create=True)
            try:
                scopes = _open_dir(review_inputs, "scopes", create=True)
            finally:
                _close([review_inputs])
            try:
                try:
                    _atomic_write_at(scopes, f"{digest}.json", data, replace=False)
                except FileExistsError:
                    if _read_file(scopes, f"{digest}.json") != data:
                        raise ValueError("review-scope publication conflict")
            finally:
                _close([scopes])
        finally:
            _close(fds)
        return locator




__all__ = ["load_review_scope", "publish_review_scope"]
