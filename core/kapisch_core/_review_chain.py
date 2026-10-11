"""Graph-free M1.2 review-result chain persistence.

Chain validation lives in a lower-level module and hands validated immutable
locators one way to this module's guarded backlink transaction.
"""

from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._authority import _validate_state_snapshot
from ._invocation import _validate_reservation
from ._locking import _locked
from ._review_chain_validation import (
    _fingerprint_data,
    _require_citation_order,
    _require_dispatch_uncertainty,
)
from ._review_scope import (
    _json,
    _load_bound_base,
    _require_anchor,
    load_review_scope,
)
from ._state import _load_run_context, _publish_state_locked
from ._validation_schema import _validate_schema
from .bundle import supports_review_evidence
from .review import ImmutableArtifactLocator
from .storage import (
    _atomic_write_at,
    _close,
    _id,
    _open_dir,
    _read_contained,
    _read_file,
    _run_dir,
)


def publish_review_invocation(repo: Path, invocation: Any) -> ImmutableArtifactLocator:
    """Publish one invocation only after its retained immutable inputs exist."""
    from .review import ReviewInvocation

    if type(invocation) is not ReviewInvocation:
        raise TypeError("invocation must be a ReviewInvocation")
    run_id = _id(invocation.operation["run_id"], "run_id")
    operation_id = _id(invocation.operation["operation_id"], "operation_id")
    if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
        raise ValueError("invalid operation_id")
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
                        item.get("path") == f"invocations/{operation_id}/planned.json"
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
                if (
                    packet.get("purpose") != invocation.purpose
                    or packet.get("role") != "reviewer"
                ):
                    raise ValueError("request does not bind a reviewer purpose")
                expected_bundle = ImmutableArtifactLocator(
                    f".kapisch/v3/bundles/{state['bundle_digest']}.json",
                    state["bundle_digest"],
                )
                if invocation.retained_bundle != expected_bundle:
                    raise ValueError("invocation retained bundle binding mismatch")
                uncertainty_data = _require_dispatch_uncertainty(
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
                        and scope.plan_candidate_ref.to_dict()
                        != state["plan_candidate_ref"]
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
                    item["path"]: item["sha256"] for item in latest_attempt["evidence"]
                }
                if (
                    cited.get(fingerprint_path)
                    != invocation.pre_dispatch_fingerprint.sha256
                ):
                    raise ValueError(
                        "pre-dispatch fingerprint has no owning attempt evidence"
                    )
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
                if (
                    tuple(invocation.included_untracked)
                    != fingerprint["included_untracked"]
                ):
                    raise ValueError("pre-dispatch included-untracked binding mismatch")
                _require_citation_order(
                    state,
                    stage_id,
                    [
                        (
                            request_ref.path.removeprefix(
                                f".kapisch/v3/runs/{run_id}/"
                            ),
                            request_ref.sha256,
                        ),
                        (fingerprint_path, invocation.pre_dispatch_fingerprint.sha256),
                        (
                            f"invocations/{operation_id}/planned.json",
                            planned_digest,
                        ),
                        (
                            f"invocations/{operation_id}/dispatch-uncertain.json",
                            hashlib.sha256(uncertainty_data).hexdigest(),
                        ),
                    ],
                )
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
    run_id = _id(run_id, "run_id")
    repo = Path(repo)
    with _locked(repo, run_id):
        state, bundle = _load_run_context(repo, run_id)
        if not supports_review_evidence(bundle):
            raise ValueError("unsupported-gate: retained bundle lacks review evidence")
        _validate_state_snapshot(repo, run_id, state, bundle)
        _validate_schema(state, "run", bundle)
        from ._validation_inventory import _inventory

        chains = dict(_inventory(repo, run_id, state, bundle))
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
