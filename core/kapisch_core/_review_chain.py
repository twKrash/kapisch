"""Graph-free M1.2 review-result chain persistence.

Structural justification: this module keeps the immutable chain loader and its
single guarded backlink transaction together because they share the same
artifact ownership, citation-order, and cold-restart invariants. Splitting
those checks would duplicate the fail-closed protocol boundary.
"""

from __future__ import annotations

import copy
import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._authority import _validate_state_snapshot
from ._invocation import _validate_reservation
from ._locking import _locked
from ._review_scope import (
    _json,
    _load_bound_base,
    _require_anchor,
    load_review_scope,
)
from ._state import _load_run_context, _publish_state_locked
from ._validation_schema import _validate_schema
from .bundle import canonical_json, supports_review_evidence
from .repository import (
    HeadIdentity,
    IndexEntry,
    RepositoryStateFingerprint,
    UntrackedEntry,
    WorktreeEntry,
)
from .review import (
    HostProvenanceAttestation,
    ImmutableArtifactLocator,
    ReviewerReturn,
    ReviewInvocation,
    ReviewResult,
)
from .storage import (
    _atomic_write_at,
    _close,
    _open_dir,
    _read_contained,
    _read_file,
    _run_dir,
    load_bundle,
)


def _read_run_locator(
    repo: Path, run_id: str, locator: ImmutableArtifactLocator, label: str
) -> bytes:
    prefix = f".kapisch/v3/runs/{run_id}/"
    if not locator.path.startswith(prefix):
        raise ValueError(f"{label} path is outside the run")
    relative = locator.path[len(prefix):]
    data = _read_contained(repo, run_id, relative)
    if hashlib.sha256(data).hexdigest() != locator.sha256:
        raise ValueError(f"{label} digest mismatch")
    return data


def _fingerprint_data(
    repo: Path, run_id: str, operation_id: str, locator: ImmutableArtifactLocator
) -> dict[str, Any]:
    expected = (
        f".kapisch/v3/runs/{run_id}/review-inputs/{operation_id}"
        "/pre-dispatch-fingerprint.json"
    )
    if locator.path != expected:
        raise ValueError("pre-dispatch fingerprint path is not operation-bound")
    data = _read_run_locator(repo, run_id, locator, "pre-dispatch fingerprint")
    value = _json(data, "pre-dispatch fingerprint")
    if set(value) != {"object_format", "head", "index", "worktree", "untracked"}:
        raise ValueError("pre-dispatch fingerprint has missing or unknown fields")

    def path_bytes(item: Mapping[str, Any]) -> bytes:
        path_hex = item.get("path_hex")
        if type(path_hex) is not str or not re.fullmatch(r"[0-9a-f]+", path_hex):
            raise ValueError("pre-dispatch fingerprint path is invalid")
        try:
            path = bytes.fromhex(path_hex)
        except ValueError as error:
            raise ValueError("pre-dispatch fingerprint path is invalid") from error
        if path.hex() != path_hex:
            raise ValueError("pre-dispatch fingerprint path is not canonical")
        return path

    try:
        HeadIdentity(value["object_format"], value["head"])
        if not all(type(value[name]) is list for name in ("index", "worktree", "untracked")):
            raise ValueError("fingerprint collections are invalid")
        index_items = []
        for item in value["index"]:
            if not isinstance(item, Mapping) or set(item) != {"path_hex", "stage", "object_id", "mode"}:
                raise ValueError("fingerprint index entry is invalid")
            index_items.append(
                IndexEntry(path_bytes(item), item["stage"], item["object_id"], item["mode"])
            )
        worktree_items = []
        for item in value["worktree"]:
            if not isinstance(item, Mapping) or set(item) not in (
                {"path_hex", "kind", "mode"},
                {"path_hex", "kind", "mode", "sha256"},
            ):
                raise ValueError("fingerprint worktree entry is invalid")
            worktree_items.append(
                WorktreeEntry(path_bytes(item), item["kind"], item["mode"], item.get("sha256"))
            )
        untracked_items = []
        for item in value["untracked"]:
            if not isinstance(item, Mapping) or set(item) not in (
                {"path_hex", "included"},
                {"path_hex", "included", "sha256"},
            ):
                raise ValueError("fingerprint untracked entry is invalid")
            untracked_items.append(
                UntrackedEntry(path_bytes(item), item["included"], item.get("sha256"))
            )
        fingerprint = RepositoryStateFingerprint(
            value["object_format"], value["head"], tuple(index_items),
            tuple(worktree_items), tuple(untracked_items)
        )
        if fingerprint.canonical_bytes() != data:
            raise ValueError("pre-dispatch fingerprint is not canonical")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("pre-dispatch fingerprint facts are invalid") from error
    value["included_untracked"] = tuple(
        item.path.hex() for item in fingerprint.untracked if item.included
    )
    return value


def _require_dispatch_uncertainty(
    repo: Path,
    run_id: str,
    operation_id: str,
    planned: Mapping[str, Any],
    attempt: Mapping[str, Any],
) -> bytes:
    path = f"invocations/{operation_id}/dispatch-uncertain.json"
    cited = {item["path"]: item["sha256"] for item in attempt["evidence"]}
    data = _read_contained(repo, run_id, path)
    expected = canonical_json({**planned, "status": "dispatch-uncertain"})
    if data != expected or cited.get(path) != hashlib.sha256(data).hexdigest():
        raise ValueError("dispatch uncertainty is missing or not attempt-owned")
    return data


def _require_chain_citation_order(
    state: Mapping[str, Any],
    run_id: str,
    operation_id: str,
    stage_id: str,
    fingerprint: ImmutableArtifactLocator,
    uncertainty_digest: str,
    operation_bytes: Mapping[str, bytes],
) -> None:
    prefix = f".kapisch/v3/runs/{run_id}/"
    fingerprint_path = fingerprint.path.removeprefix(prefix)
    ordered = [
        (fingerprint_path, fingerprint.sha256),
        (
            f"invocations/{operation_id}/dispatch-uncertain.json",
            uncertainty_digest,
        ),
        *(
            (
                f"invocations/{operation_id}/{filename}",
                hashlib.sha256(operation_bytes[filename]).hexdigest(),
            )
            for filename in (
                "review-invocation.json",
                "reviewer-return.json",
                "host-provenance-attestation.json",
                "post-result.json",
                "review-result.json",
            )
        ),
    ]
    positions: list[tuple[int, int]] = []
    for path, digest in ordered:
        matches = [
            (row_index, evidence_index, row)
            for row_index, row in enumerate(state["history"])
            for evidence_index, evidence in enumerate(row["evidence"])
            if evidence.get("path") == path and evidence.get("sha256") == digest
        ]
        if not matches:
            raise ValueError("review-chain artifact has no owning citation")
        row_index, evidence_index, row = matches[0]
        if row["stage_id"] != stage_id:
            raise ValueError("review-chain artifact has wrong owning stage")
        positions.append((row_index, evidence_index))
    if positions != sorted(positions):
        raise ValueError("review-chain artifact citations are out of dependency order")
    uncertainty_row = positions[1][0]
    invocation_row = positions[2][0]
    if invocation_row <= uncertainty_row:
        raise ValueError("review invocation must follow durable uncertainty")


def _load_result_chain(
    repo: Path, run_id: str, operation_id: str, state: Mapping[str, Any]
) -> ImmutableArtifactLocator | None:
    """Load one complete chain as one ownership and recovery transaction.

    Keeping the bounded validation sequence together prevents a caller from
    consuming partially validated artifacts between dependency checks.
    """
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        invocations = _open_dir(run, "invocations")
        try:
            operation = _open_dir(invocations, operation_id)
        except OSError as error:
            raise ValueError("operation reservation is unavailable") from error
        finally:
            _close([invocations])
        try:
            names = set(os.listdir(operation))
            review_names = {
                "review-invocation.json",
                "reviewer-return.json",
                "host-provenance-attestation.json",
                "post-result.json",
                "review-result.json",
            }
            if not names & review_names:
                return None
            allowed_names = {
                "planned.json",
                "dispatch-uncertain.json",
                "observed.json",
                "blocked.json",
                *review_names,
            }
            if names - allowed_names or "planned.json" not in names:
                raise ValueError("review result chain is partial")
            if not review_names <= names:
                raise ValueError("review result chain is partial")
            planned_data = _read_file(operation, "planned.json")
            planned = _json(planned_data, "operation reservation")
            packet = _validate_reservation(repo, run_id, operation_id, planned)
            planned_path = f"invocations/{operation_id}/planned.json"
            planned_digest = hashlib.sha256(planned_data).hexdigest()
            operation_attempts = [
                row
                for row in state["history"]
                if row["stage_id"] == planned["stage_id"]
                and any(
                    item.get("path") == planned_path
                    and item.get("sha256") == planned_digest
                    for item in row["evidence"]
                )
            ]
            if not operation_attempts:
                raise ValueError("reservation has no owning attempt evidence")
            operation_bytes = {
                name: _read_file(operation, name)
                for name in review_names
            }
        finally:
            _close([operation])
    finally:
        _close(fds)

    attempt = operation_attempts[-1]
    if attempt["status"] == "dispatch-uncertain":
        raise ValueError("unresolved dispatch-uncertain blocks review completion")
    if attempt["status"] != "complete":
        raise ValueError("review result chain is owned by an ineligible attempt")
    uncertainty = next(
        (
            row
            for row in reversed(operation_attempts)
            if row["status"] == "dispatch-uncertain"
        ),
        None,
    )
    if uncertainty is None:
        raise ValueError("review result chain has no durable dispatch uncertainty")
    uncertainty_data = _require_dispatch_uncertainty(
        repo, run_id, operation_id, planned, uncertainty
    )
    cited = {item["path"]: item["sha256"] for item in attempt["evidence"]}
    result_path = f"invocations/{operation_id}/review-result.json"
    result_digest = hashlib.sha256(operation_bytes["review-result.json"]).hexdigest()
    if cited.get(result_path) != result_digest:
        raise ValueError("review result has no owning attempt evidence")
    for filename, data in operation_bytes.items():
        path = f"invocations/{operation_id}/{filename}"
        if cited.get(path) != hashlib.sha256(data).hexdigest():
            raise ValueError(f"{filename} has no owning attempt evidence")
    invocation = ReviewInvocation.from_dict(
        _json(operation_bytes["review-invocation.json"], "review invocation")
    )
    _require_chain_citation_order(
        state,
        run_id,
        operation_id,
        planned["stage_id"],
        invocation.pre_dispatch_fingerprint,
        hashlib.sha256(uncertainty_data).hexdigest(),
        operation_bytes,
    )
    reviewer_return = ReviewerReturn.from_dict(
        _json(operation_bytes["reviewer-return.json"], "reviewer return")
    )
    attestation = HostProvenanceAttestation.from_dict(
        _json(
            operation_bytes["host-provenance-attestation.json"],
            "host provenance attestation",
        )
    )
    result = ReviewResult.from_dict(
        _json(operation_bytes["review-result.json"], "review result")
    )
    invocation_locator = ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/review-invocation.json",
        hashlib.sha256(operation_bytes["review-invocation.json"]).hexdigest(),
    )
    reviewer_locator = ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/reviewer-return.json",
        hashlib.sha256(operation_bytes["reviewer-return.json"]).hexdigest(),
    )
    provenance_locator = ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/host-provenance-attestation.json",
        hashlib.sha256(operation_bytes["host-provenance-attestation.json"]).hexdigest(),
    )
    post_result_locator = ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/post-result.json",
        hashlib.sha256(operation_bytes["post-result.json"]).hexdigest(),
    )
    request_locator = ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/requests/{operation_id}.json",
        planned["request_digest"],
    )
    if (
        invocation.operation != {"run_id": run_id, "operation_id": operation_id}
        or invocation.attempt != {"run_id": run_id, "stage_id": planned["stage_id"]}
        or invocation.retained_bundle.path
        != f".kapisch/v3/bundles/{state['bundle_digest']}.json"
        or invocation.retained_bundle.sha256 != state["bundle_digest"]
        or invocation.request != request_locator
        or packet.get("review_scope") != invocation.scope.to_dict()
        or packet.get("purpose") != invocation.purpose
        or packet.get("role") != "reviewer"
        or reviewer_return.invocation != invocation_locator
        or reviewer_return.request != request_locator
        or reviewer_return.fingerprint != invocation.pre_dispatch_fingerprint
        or attestation.reviewer_return != reviewer_locator
        or attestation.reviewer_return_digest != reviewer_locator.sha256
        or result.invocation != invocation_locator
        or result.request != request_locator
        or result.reviewer_return != reviewer_locator
        or result.post_result != post_result_locator
        or result.provenance != provenance_locator
        or result.fingerprint != invocation.pre_dispatch_fingerprint
        or reviewer_return.target != result.target
    ):
        raise ValueError("review result chain identity binding mismatch")
    producer_reservation, _, producer_base = _load_bound_base(
        repo, run_id, state, attempt, verify_git=True
    )
    scope = load_review_scope(repo, invocation.scope)
    fingerprint = _fingerprint_data(
        repo, run_id, operation_id, invocation.pre_dispatch_fingerprint
    )
    retained_bundle = load_bundle(repo, invocation.retained_bundle.sha256)
    if not supports_review_evidence(retained_bundle):
        raise ValueError("unsupported-gate: invocation bundle lacks review evidence")
    report_data = _read_run_locator(repo, run_id, reviewer_return.report, "review report")
    if hashlib.sha256(report_data).hexdigest() != reviewer_return.report_digest:
        raise ValueError("review report digest mismatch")
    _require_anchor(invocation.base, fingerprint["object_format"], "invocation base")
    _require_anchor(invocation.head, fingerprint["object_format"], "invocation head")
    fingerprint_path = (
        f"review-inputs/{operation_id}/pre-dispatch-fingerprint.json"
    )
    if cited.get(fingerprint_path) != invocation.pre_dispatch_fingerprint.sha256:
        raise ValueError("pre-dispatch fingerprint has no owning attempt evidence")
    candidate_ref = state.get("plan_candidate_ref")
    if candidate_ref is not None and scope.plan_candidate_ref.to_dict() != candidate_ref:
        raise ValueError("review scope candidate binding mismatch")
    if (
        scope.run_id != run_id
        or scope.stage_id != planned["stage_id"]
        or scope.purpose != invocation.purpose
        or (
            "plan_candidate_ref" in state
            and scope.plan_candidate_ref.to_dict() != state["plan_candidate_ref"]
        )
        or scope.comparison_base != producer_base["base"]
        or scope.comparison_base != invocation.base
        or producer_reservation["purpose"] != scope.purpose
        or producer_reservation["head"] != invocation.head
        or reviewer_return.target["run_id"] != run_id
        or reviewer_return.target["stage_id"] != planned["stage_id"]
        or reviewer_return.target["operation_id"] != operation_id
        or reviewer_return.target["base"] != invocation.base
        or reviewer_return.target["head"] != invocation.head
        or fingerprint["head"] != invocation.head.split(":", 1)[1]
        or tuple(invocation.included_untracked) != fingerprint["included_untracked"]
    ):
        raise ValueError("review result chain factual binding mismatch")
    if result.scope != invocation.scope or result.fingerprint != invocation.pre_dispatch_fingerprint:
        raise ValueError("review result scope or fingerprint binding mismatch")
    return ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/review-result.json",
        result_digest,
    )


def publish_review_invocation(
    repo: Path, invocation: Any
) -> ImmutableArtifactLocator:
    """Publish one invocation only after its retained immutable inputs exist."""
    from .review import ReviewInvocation

    if type(invocation) is not ReviewInvocation:
        raise TypeError("invocation must be a ReviewInvocation")
    run_id = invocation.operation["run_id"]
    operation_id = invocation.operation["operation_id"]
    repo = Path(repo)
    with _locked(repo, run_id):
        state, bundle = _load_run_context(repo, run_id)
        if not supports_review_evidence(bundle):
            raise ValueError("unsupported-gate: retained bundle lacks review evidence")
        _validate_state_snapshot(repo, run_id, state, bundle)
        _validate_schema(state, "run", bundle)
        if invocation.attempt["run_id"] != run_id:
            raise ValueError("invocation attempt run identity mismatch")
        stage_id = invocation.attempt["stage_id"]
        run, fds = _run_dir(repo, run_id, create=False)
        try:
            try:
                invocations = _open_dir(run, "invocations")
                try:
                    operation = _open_dir(invocations, operation_id)
                finally:
                    _close([invocations])
            except OSError as error:
                raise ValueError("operation reservation is unavailable") from error
            try:
                planned_data = _read_file(operation, "planned.json")
                planned = _json(planned_data, "operation reservation")
                packet = _validate_reservation(repo, run_id, operation_id, planned)
                if planned["stage_id"] != stage_id:
                    raise ValueError("reservation stage identity mismatch")
                planned_digest = hashlib.sha256(planned_data).hexdigest()
                operation_attempts = [
                    row
                    for row in state["history"]
                    if row["stage_id"] == stage_id
                    and any(
                        item.get("path")
                        == f"invocations/{operation_id}/planned.json"
                        and item.get("sha256") == planned_digest
                        for item in row["evidence"]
                    )
                ]
                stage_attempts = [
                    row for row in state["history"] if row["stage_id"] == stage_id
                ]
                if (
                    not stage_attempts
                    or stage_attempts[0]["status"] != "planned"
                    or not operation_attempts
                    or operation_attempts[-1]["status"] != "dispatch-uncertain"
                ):
                    raise ValueError("invocation requires durable dispatch uncertainty")
                latest_attempt = operation_attempts[-1]
                request_ref = invocation.request
                expected_request = (
                    f".kapisch/v3/runs/{run_id}/requests/{operation_id}.json"
                )
                if request_ref.path != expected_request:
                    raise ValueError("invocation request path is not operation-bound")
                request_data = _read_contained(
                    repo, run_id, f"requests/{operation_id}.json"
                )
                if hashlib.sha256(request_data).hexdigest() != request_ref.sha256:
                    raise ValueError("invocation request digest mismatch")
                if packet.get("review_scope") != invocation.scope.to_dict():
                    raise ValueError("request does not bind invocation review scope")
                if packet.get("purpose") != invocation.purpose or packet.get("role") != "reviewer":
                    raise ValueError("request does not bind a reviewer purpose")
                expected_bundle = ImmutableArtifactLocator(
                    f".kapisch/v3/bundles/{state['bundle_digest']}.json",
                    state["bundle_digest"],
                )
                if invocation.retained_bundle != expected_bundle:
                    raise ValueError("invocation retained bundle binding mismatch")
                _require_dispatch_uncertainty(
                    repo, run_id, operation_id, planned, latest_attempt
                )
                producer_reservation, _, producer_base = _load_bound_base(
                    repo,
                    run_id,
                    state,
                    latest_attempt,
                    verify_git=True,
                    verify_named_ref=True,
                )
                scope = load_review_scope(repo, invocation.scope)
                if (
                    scope.run_id != run_id
                    or scope.stage_id != stage_id
                    or scope.purpose != invocation.purpose
                    or (
                        "plan_candidate_ref" in state
                        and scope.plan_candidate_ref.to_dict() != state["plan_candidate_ref"]
                    )
                    or producer_reservation["purpose"] != scope.purpose
                    or producer_reservation["head"] != invocation.head
                    or scope.comparison_base != producer_base["base"]
                    or scope.comparison_base != invocation.base
                ):
                    raise ValueError("invocation scope binding mismatch")
                fingerprint_path = (
                    f"review-inputs/{operation_id}/pre-dispatch-fingerprint.json"
                )
                cited = {
                    item["path"]: item["sha256"]
                    for item in latest_attempt["evidence"]
                }
                if cited.get(fingerprint_path) != invocation.pre_dispatch_fingerprint.sha256:
                    raise ValueError("pre-dispatch fingerprint has no owning attempt evidence")
                fingerprint = _fingerprint_data(
                    repo, run_id, operation_id, invocation.pre_dispatch_fingerprint
                )
                _require_anchor(
                    invocation.base, fingerprint["object_format"], "invocation base"
                )
                _require_anchor(
                    invocation.head, fingerprint["object_format"], "invocation head"
                )
                if fingerprint["head"] != invocation.head.split(":", 1)[1]:
                    raise ValueError("pre-dispatch fingerprint binding mismatch")
                if tuple(invocation.included_untracked) != fingerprint["included_untracked"]:
                    raise ValueError("pre-dispatch included-untracked binding mismatch")
                data = invocation.canonical_bytes()
                try:
                    _atomic_write_at(
                        operation, "review-invocation.json", data, replace=False
                    )
                except FileExistsError:
                    if _read_file(operation, "review-invocation.json") != data:
                        raise ValueError("review-invocation publication conflict")
            finally:
                _close([operation])
        finally:
            _close(fds)
    return ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/review-invocation.json",
        hashlib.sha256(data).hexdigest(),
    )


def repair_review_backlinks(
    repo: Path, run_id: str
) -> tuple[ImmutableArtifactLocator, ...]:
    """Validate complete result chains and repair missing exact backlinks."""
    repo = Path(repo)
    with _locked(repo, run_id):
        state, bundle = _load_run_context(repo, run_id)
        if not supports_review_evidence(bundle):
            raise ValueError("unsupported-gate: retained bundle lacks review evidence")
        _validate_state_snapshot(repo, run_id, state, bundle)
        _validate_schema(state, "run", bundle)
        from ._validation_inventory import _inventory

        _inventory(repo, run_id, state, bundle)
        run, fds = _run_dir(repo, run_id, create=False)
        try:
            try:
                invocations = _open_dir(run, "invocations")
            except FileNotFoundError:
                if "review_result_ref" in state:
                    raise ValueError("review backlink exists without invocation inventory")
                return ()
            try:
                operation_ids = sorted(os.listdir(invocations))
                if any(
                    re.fullmatch(r"op-[0-9a-f]{32}", name) is None
                    for name in operation_ids
                ):
                    raise ValueError("invocation inventory contains invalid operation name")
            finally:
                _close([invocations])
        finally:
            _close(fds)
        chains: dict[str, ImmutableArtifactLocator] = {}
        for operation_id in operation_ids:
            locator = _load_result_chain(repo, run_id, operation_id, state)
            if locator is not None:
                chains[operation_id] = locator
        existing = state.get("review_result_ref", {})
        if not isinstance(existing, Mapping):
            raise ValueError("review_result_ref has invalid shape")
        for operation_id, reference in existing.items():
            if operation_id not in chains:
                raise ValueError("review backlink has no complete result chain")
            expected = chains[operation_id].to_dict()
            if reference != expected:
                raise ValueError("review backlink conflicts with complete result chain")
        missing = {
            operation_id: locator.to_dict()
            for operation_id, locator in chains.items()
            if operation_id not in existing
        }
        if not missing:
            return tuple(chains.values())
        proposed = copy.deepcopy(dict(state))
        proposed["review_result_ref"] = {**dict(existing), **missing}
        proposed["revision"] = state["revision"] + 1
        _publish_state_locked(
            repo,
            run_id,
            proposed,
            state["revision"],
            allow_review_backlink_repair=True,
        )
        return tuple(chains.values())


__all__ = ["publish_review_invocation", "repair_review_backlinks"]
