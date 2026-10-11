"""Immutable review-chain loading and validation."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._invocation import _validate_reservation
from ._review_scope import _json, _load_bound_base, _require_anchor, load_review_scope
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
    relative = locator.path[len(prefix) :]
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
        if not all(
            type(value[name]) is list for name in ("index", "worktree", "untracked")
        ):
            raise ValueError("fingerprint collections are invalid")
        index_items = []
        for item in value["index"]:
            if not isinstance(item, Mapping) or set(item) != {
                "path_hex",
                "stage",
                "object_id",
                "mode",
            }:
                raise ValueError("fingerprint index entry is invalid")
            index_items.append(
                IndexEntry(
                    path_bytes(item), item["stage"], item["object_id"], item["mode"]
                )
            )
        worktree_items = []
        for item in value["worktree"]:
            if not isinstance(item, Mapping) or set(item) not in (
                {"path_hex", "kind", "mode"},
                {"path_hex", "kind", "mode", "sha256"},
            ):
                raise ValueError("fingerprint worktree entry is invalid")
            worktree_items.append(
                WorktreeEntry(
                    path_bytes(item), item["kind"], item["mode"], item.get("sha256")
                )
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
            value["object_format"],
            value["head"],
            tuple(index_items),
            tuple(worktree_items),
            tuple(untracked_items),
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


def _first_citation_positions(
    state: Mapping[str, Any],
    stage_id: str,
    artifacts: list[tuple[str, str]],
) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for path, digest in artifacts:
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
    return positions


def _require_citation_order(
    state: Mapping[str, Any],
    stage_id: str,
    artifacts: list[tuple[str, str]],
) -> list[tuple[int, int]]:
    positions = _first_citation_positions(state, stage_id, artifacts)
    if positions != sorted(positions):
        raise ValueError("review-chain artifact citations are out of dependency order")
    return positions


def _require_chain_citation_order(
    state: Mapping[str, Any],
    run_id: str,
    operation_id: str,
    stage_id: str,
    request: ImmutableArtifactLocator,
    fingerprint: ImmutableArtifactLocator,
    report: ImmutableArtifactLocator,
    uncertainty_digest: str,
    operation_bytes: Mapping[str, bytes],
) -> None:
    prefix = f".kapisch/v3/runs/{run_id}/"
    request_path = request.path.removeprefix(prefix)
    fingerprint_path = fingerprint.path.removeprefix(prefix)
    ordered = [
        (request_path, request.sha256),
        (fingerprint_path, fingerprint.sha256),
        (
            f"invocations/{operation_id}/dispatch-uncertain.json",
            uncertainty_digest,
        ),
        (
            f"invocations/{operation_id}/review-invocation.json",
            hashlib.sha256(operation_bytes["review-invocation.json"]).hexdigest(),
        ),
        (
            report.path.removeprefix(prefix),
            report.sha256,
        ),
        *(
            (
                f"invocations/{operation_id}/{filename}",
                hashlib.sha256(operation_bytes[filename]).hexdigest(),
            )
            for filename in (
                "reviewer-return.json",
                "host-provenance-attestation.json",
                "post-result.json",
                "review-result.json",
            )
        ),
    ]
    if "planned.json" in operation_bytes:
        ordered.insert(
            2,
            (
                f"invocations/{operation_id}/planned.json",
                hashlib.sha256(operation_bytes["planned.json"]).hexdigest(),
            ),
        )
    positions = _first_citation_positions(state, stage_id, ordered)
    if positions[1][0] < positions[0][0]:
        raise ValueError("pre-dispatch fingerprint must follow request")
    if positions != sorted(positions):
        raise ValueError("review-chain artifact citations are out of dependency order")
    offset = 1 if "planned.json" in operation_bytes else 0
    uncertainty_row = positions[2 + offset][0]
    invocation_row = positions[3 + offset][0]
    report_row = positions[4 + offset][0]
    reviewer_return_row = positions[5 + offset][0]
    attestation_row = positions[6 + offset][0]
    post_result_row = positions[7 + offset][0]
    result_row = positions[8 + offset][0]
    # Evidence-array order is not durable chronology within one observation.
    if invocation_row <= uncertainty_row:
        raise ValueError("review invocation must follow durable uncertainty")
    if report_row <= invocation_row:
        raise ValueError("retained report must follow review invocation")
    if reviewer_return_row <= report_row:
        raise ValueError("reviewer return must follow retained report")
    if attestation_row <= reviewer_return_row:
        raise ValueError("host attestation must follow reviewer return")
    if post_result_row <= attestation_row:
        raise ValueError("post-result must follow host attestation")
    if result_row <= post_result_row:
        raise ValueError("review result must follow post-result")


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
                "planned.json": planned_data,
                **{name: _read_file(operation, name) for name in review_names},
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
    request_locator = ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/requests/{operation_id}.json",
        planned["request_digest"],
    )
    invocation = ReviewInvocation.from_dict(
        _json(operation_bytes["review-invocation.json"], "review invocation")
    )
    reviewer_return = ReviewerReturn.from_dict(
        _json(operation_bytes["reviewer-return.json"], "reviewer return")
    )
    _require_chain_citation_order(
        state,
        run_id,
        operation_id,
        planned["stage_id"],
        request_locator,
        invocation.pre_dispatch_fingerprint,
        reviewer_return.report,
        hashlib.sha256(uncertainty_data).hexdigest(),
        operation_bytes,
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
    report_data = _read_run_locator(
        repo, run_id, reviewer_return.report, "review report"
    )
    if hashlib.sha256(report_data).hexdigest() != reviewer_return.report_digest:
        raise ValueError("review report digest mismatch")
    _require_anchor(invocation.base, fingerprint["object_format"], "invocation base")
    _require_anchor(invocation.head, fingerprint["object_format"], "invocation head")
    fingerprint_path = f"review-inputs/{operation_id}/pre-dispatch-fingerprint.json"
    if cited.get(fingerprint_path) != invocation.pre_dispatch_fingerprint.sha256:
        raise ValueError("pre-dispatch fingerprint has no owning attempt evidence")
    candidate_ref = state.get("plan_candidate_ref")
    if (
        candidate_ref is not None
        and scope.plan_candidate_ref.to_dict() != candidate_ref
    ):
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
    if (
        result.scope != invocation.scope
        or result.fingerprint != invocation.pre_dispatch_fingerprint
    ):
        raise ValueError("review result scope or fingerprint binding mismatch")
    return ImmutableArtifactLocator(
        f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/review-result.json",
        result_digest,
    )
