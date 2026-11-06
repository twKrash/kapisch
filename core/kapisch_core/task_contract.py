"""Validation for the bounded, portable single-task acceptance contract."""

from __future__ import annotations

import stat
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from ._task_artifacts import (
    _RUN_ID,
    ContractError,
    _create_exclusive,
    _load,
    _read_bytes,
    _replace_json_atomically,
    _required_id,
    _required_text,
    _resolve,
)
from ._task_authority import _validate_workorder
from ._task_decisions import _DecisionRecord
from ._task_outcomes import _make_outcome
from ._task_roots import _validated_roots
from ._task_supersession import _scan_decisions, _validate_decision_eligibility

_INVALID_RUN_IDENTITY = "invalid Run identity"


def _reject_symlink_components(base: Path, ref: str) -> None:
    current = base
    for part in PurePosixPath(ref).parts:
        current = current / part
        try:
            is_symlink = current.is_symlink()
        except OSError as exc:
            raise ContractError("cannot inspect dispatch allocation path") from exc
        if is_symlink:
            raise ContractError("dispatch allocation path contains a symlink")


def _run_directory(run: dict[str, Any], run_ref: str) -> str:
    run_id = run.get("run_id")
    parts = PurePosixPath(run_ref).parts
    if (
        len(parts) >= 3
        and parts[:2] == (".kapisch", "runs")
        and not _RUN_ID.fullmatch(parts[2])
    ):
        raise ContractError(_INVALID_RUN_IDENTITY)
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ContractError(_INVALID_RUN_IDENTITY)
    if parts != (".kapisch", "runs", run_id, "run.json"):
        raise ContractError("Run identity and portable reference mismatch")
    return "/".join(parts[:3])


def create_run(state_root: str | Path) -> str:
    """Mint a canonical Run id by exclusively creating its directory in state_root."""
    state, _ = _validated_roots(state_root, state_root)
    runs = state / ".kapisch" / "runs"
    try:
        for directory in (runs.parent, runs):
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink() or directory.resolve(strict=True) != directory:
                raise ContractError("Run directory escapes project root")
        run_id = str(uuid.uuid4())
        (runs / run_id).mkdir(mode=0o700)
    except OSError as exc:
        raise ContractError("cannot create Run directory") from exc
    return run_id


def validate_run(
    state_root: str | Path,
    run_ref: str,
    run_digest: str | None = None,
    *,
    source_root: str | Path,
) -> dict[str, Any]:
    """Validate Run authority stored in state_root against source_root Git inputs."""
    state, source = _validated_roots(state_root, source_root)
    return _validate_run(state, source, run_ref, run_digest)


def _validate_run(
    state_root: Path,
    source_root: Path,
    run_ref: str,
    run_digest: str | None = None,
    *,
    decision_records: dict[str, _DecisionRecord] | None = None,
) -> dict[str, Any]:
    """Load persisted Run, WorkOrder, and authority evidence from disk."""
    base = state_root
    run = _load(base, run_ref, run_digest, require_digest=False)
    dispatch_state = run.get("dispatch_state")
    if not isinstance(dispatch_state, str) or dispatch_state not in (
        "ready",
        "claimed",
    ):
        raise ContractError("invalid persisted dispatch state")
    run_directory = _run_directory(run, run_ref)
    workorder_ref = _required_text(run, "workorder_ref", "WorkOrder reference")
    if workorder_ref != run_directory + "/workorder.json":
        raise ContractError("WorkOrder reference is outside its canonical Run path")
    work = _load(base, workorder_ref, run.get("workorder_digest"))
    decision, applicability = _validate_workorder(
        base, source_root, run_directory, work, decision_records
    )
    return {
        "run": run,
        "workorder": work,
        "decision": decision,
        "applicability": applicability,
    }


def _dispatch_claim_ref(run_ref: str) -> str:
    run_directory = "/".join(PurePosixPath(run_ref).parts[:3])
    return run_directory + "/dispatch-claim.json"


def _validate_attempt_allocation(run: dict[str, Any], run_ref: str) -> dict[str, Any]:
    allocation = run.get("attempt_allocation")
    if not isinstance(allocation, dict):
        raise ContractError("attempt allocation is missing before dispatch")
    attempt_id = _required_id(allocation, "attempt_id", "allocated attempt identity")
    output_ref = _required_text(allocation, "output_ref", "allocated output reference")
    run_directory = _run_directory(run, run_ref)
    if output_ref != run_directory + "/attempts/" + attempt_id + "-output.json":
        raise ContractError("allocated output reference mismatch")
    return allocation


def _dispatch_claim_record(run_ref: str, records: dict[str, Any]) -> dict[str, Any]:
    run, work = records["run"], records["workorder"]
    allocation = _validate_attempt_allocation(run, run_ref)
    return {
        "status": "claimed",
        "run_id": run["run_id"],
        "run_ref": run_ref,
        "workorder_ref": run["workorder_ref"],
        "workorder_digest": run["workorder_digest"],
        "decision_id": records["decision"]["decision_id"],
        "decision_digest": work["decision_digest"],
        "attempt_id": allocation["attempt_id"],
        "output_ref": allocation["output_ref"],
    }


def _validate_dispatch_claim(
    base: Path, run_ref: str, records: dict[str, Any]
) -> dict[str, Any]:
    claim_ref = _dispatch_claim_ref(run_ref)
    try:
        claim = _load(base, claim_ref, require_digest=False)
    except ContractError as exc:
        raise ContractError("dispatch claim is missing or invalid") from exc
    if claim != _dispatch_claim_record(run_ref, records):
        raise ContractError("dispatch claim does not match this WorkOrder allocation")
    if records["run"].get("dispatch_state") != "claimed":
        raise ContractError("persisted dispatch boundary is missing")
    return claim


def _validate_dispatch_readiness(
    root: str | Path, run_ref: str, run: dict[str, Any]
) -> Path:
    if run["dispatch_state"] != "ready":
        raise ContractError(
            "dispatch claim already exists or allocation was consumed; automatic redispatch is forbidden"
        )
    base = _resolve(Path(root), "project root")
    claim_ref = _dispatch_claim_ref(run_ref)
    claim_path = _resolve(base / claim_ref, "dispatch claim")
    if not claim_path.is_relative_to(base):
        raise ContractError("dispatch claim escapes project root")
    candidate_claim = base / claim_ref
    if candidate_claim.exists() or candidate_claim.is_symlink():
        raise ContractError(
            "dispatch claim already exists; automatic redispatch is forbidden"
        )
    if any(
        key in run
        for key in (
            "attempt_ref",
            "attempt_digest",
            "aggregation_ref",
            "aggregation_digest",
            "outcome_ref",
            "outcome_digest",
        )
    ):
        raise ContractError("Run is not dispatchable after execution has started")
    return base


def _allocation_path_exists(path: Path, label: str) -> bool:
    try:
        path.stat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ContractError(f"cannot inspect {label}") from exc
    return True


def _validate_allocation_directory(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ContractError("cannot inspect allocation directory") from exc
    if not stat.S_ISDIR(mode):
        raise ContractError("allocation parent is not a directory")


def _validate_dispatch_allocation_paths(
    base: Path, run_ref: str, run: dict[str, Any]
) -> dict[str, Any]:
    allocation = _validate_attempt_allocation(run, run_ref)
    attempt_id = allocation["attempt_id"]
    output_ref = allocation["output_ref"]
    run_directory = _run_directory(run, run_ref)
    _reject_symlink_components(base, output_ref)
    attempt_ref = run_directory + "/attempts/" + attempt_id + ".json"
    _reject_symlink_components(base, attempt_ref)
    _validate_allocation_directory(base / run_directory / "attempts")
    output_path = _resolve(base / output_ref, "allocated output")
    if not output_path.is_relative_to(base):
        raise ContractError("allocated output escapes project root")
    attempt_path = _resolve(base / attempt_ref, "allocated attempt")
    if not attempt_path.is_relative_to(base):
        raise ContractError("allocated attempt escapes project root")
    if _allocation_path_exists(
        output_path, "allocated output"
    ) or _allocation_path_exists(attempt_path, "allocated attempt"):
        raise ContractError("attempt allocation already exists")
    return allocation


def validate_dispatch(
    state_root: str | Path,
    run_ref: str,
    *,
    source_root: str | Path,
    capabilities: dict[str, dict[str, str]],
    canonical_implementer_available: bool,
) -> dict[str, Any]:
    """Validate durable authorization and actual adapter capabilities before start."""
    base, source = _validated_roots(state_root, source_root)
    run = _load(base, run_ref, require_digest=False)
    run_directory = _run_directory(run, run_ref)
    decision_records = _scan_decisions(base, run_directory)
    records = _validate_run(base, source, run_ref, decision_records=decision_records)
    work = records["workorder"]
    _validate_capabilities(work, capabilities)
    if (
        type(canonical_implementer_available) is not bool
        or canonical_implementer_available
        is not work["canonical_implementer_available"]
    ):
        raise ContractError(
            "canonical implementer availability changed; reauthorize dispatch"
        )
    run = records["run"]
    base = _validate_dispatch_readiness(base, run_ref, run)
    allocation = _validate_dispatch_allocation_paths(base, run_ref, run)
    _validate_decision_eligibility(
        base,
        _run_directory(run, run_ref),
        records["decision"]["decision_id"],
        decision_records,
    )
    return {**records, "attempt_allocation": allocation}


def claim_dispatch(
    state_root: str | Path,
    run_ref: str,
    *,
    source_root: str | Path,
    capabilities: dict[str, dict[str, str]],
    canonical_implementer_available: bool,
) -> dict[str, Any]:
    """Exclusively claim the sole attempt before invoking the host adapter."""
    records = validate_dispatch(
        state_root,
        run_ref,
        source_root=source_root,
        capabilities=capabilities,
        canonical_implementer_available=canonical_implementer_available,
    )
    base = _resolve(Path(state_root), "project root")
    claim = _dispatch_claim_record(run_ref, records)
    _create_exclusive(base, _dispatch_claim_ref(run_ref), claim)
    records["run"]["dispatch_state"] = "claimed"
    _replace_json_atomically(base, run_ref, records["run"])
    # A superseder published before the claim existed must still stop the host start.
    run_directory = _run_directory(records["run"], run_ref)
    _validate_decision_eligibility(
        base,
        run_directory,
        records["decision"]["decision_id"],
        _scan_decisions(base, run_directory),
    )
    return {**records, "dispatch_claim": claim}


def _validate_capabilities(
    work: dict[str, Any], capabilities: dict[str, dict[str, str]]
) -> None:
    if not isinstance(capabilities, dict):
        raise ContractError("invalid adapter capabilities")
    for name in work["required_capabilities"]:
        capability = capabilities.get(name)
        if (
            not isinstance(capability, dict)
            or capability.get("status") != "supported"
            or not isinstance(capability.get("reason"), str)
            or not capability["reason"].strip()
        ):
            raise ContractError(f"required capability not supported: {name}")


def _load_attempt_and_report(
    base: Path, run: dict[str, Any], run_directory: str
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    attempt_ref = _required_text(run, "attempt_ref", "attempt reference")
    aggregation_ref = _required_text(run, "aggregation_ref", "aggregation reference")
    if not attempt_ref.startswith(run_directory + "/attempts/"):
        raise ContractError("attempt reference is outside its Run")
    if aggregation_ref != run_directory + "/aggregation.json":
        raise ContractError("aggregation reference is outside its canonical Run path")
    attempt = _load(base, attempt_ref, run.get("attempt_digest"))
    report = _load(base, aggregation_ref, run.get("aggregation_digest"))
    return attempt, report, attempt_ref, aggregation_ref


def _validate_attempt_report(
    base: Path,
    records: dict[str, Any],
    attempt: dict[str, Any],
    report: dict[str, Any],
    attempt_ref: str,
    run_directory: str,
) -> tuple[str, str]:
    run, work = records["run"], records["workorder"]
    task_id = work["task"]["task_id"]
    attempt_id = _required_id(attempt, "attempt_id", "attempt identity")
    allocation = run.get("attempt_allocation")
    if not isinstance(allocation, dict) or allocation.get("attempt_id") != attempt_id:
        raise ContractError("attempt differs from pre-dispatch allocation")
    if attempt_ref != run_directory + "/attempts/" + attempt_id + ".json":
        raise ContractError("attempt identity and reference mismatch")
    workorder_id = work["workorder_id"]
    workorder_digest = run["workorder_digest"]
    decision = records["decision"]
    decision_id, decision_digest = decision["decision_id"], work["decision_digest"]
    if (
        attempt.get("task_id") != task_id
        or attempt.get("workorder_id") != workorder_id
        or attempt.get("workorder_ref") != run.get("workorder_ref")
        or attempt.get("workorder_digest") != workorder_digest
        or attempt.get("decision_id") != decision_id
        or attempt.get("decision_digest") != decision_digest
        or report.get("attempt_ref") != attempt_ref
        or report.get("attempt_digest") != run.get("attempt_digest")
        or report.get("attempt_id") != attempt_id
        or report.get("task_id") != task_id
        or report.get("workorder_id") != workorder_id
        or report.get("workorder_ref") != run.get("workorder_ref")
        or report.get("workorder_digest") != workorder_digest
        or report.get("decision_id") != decision_id
        or report.get("decision_digest") != decision_digest
    ):
        raise ContractError("report is not bound to the exact attempt and WorkOrder")
    if report.get("coverage") != [task_id]:
        raise ContractError("aggregation coverage mismatch")
    if report.get("acceptance_criteria") != work["acceptance_criteria"]:
        raise ContractError("aggregation acceptance criteria mismatch")
    output_ref = _required_text(attempt, "output_ref", "attempt output reference")
    expected_output_ref = run_directory + "/attempts/" + attempt_id + "-output.json"
    if allocation.get("output_ref") != expected_output_ref:
        raise ContractError("allocated output reference mismatch")
    if output_ref != expected_output_ref or report.get("output_ref") != output_ref:
        raise ContractError(
            "attempt output reference differs from its allocation or report"
        )
    if report.get("output_digest") != attempt.get("output_digest"):
        raise ContractError("aggregation report is not bound to the attempt output")
    _read_bytes(base, output_ref, attempt.get("output_digest"))
    return attempt_id, output_ref


def validate_acceptance(
    state_root: str | Path,
    run_ref: str,
    *,
    source_root: str | Path,
    capabilities: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Validate one attempt and report before returning coordinator Outcome data."""
    state, source = _validated_roots(state_root, source_root)
    return _validate_acceptance(state, source, run_ref, capabilities)


def _validate_acceptance(
    state_root: Path,
    source_root: Path,
    run_ref: str,
    capabilities: dict[str, dict[str, str]],
) -> dict[str, Any]:
    records = _validate_run(state_root, source_root, run_ref)
    _validate_capabilities(records["workorder"], capabilities)
    base = state_root
    _validate_dispatch_claim(base, run_ref, records)
    run_directory = "/".join(PurePosixPath(run_ref).parts[:3])
    attempt, report, attempt_ref, _ = _load_attempt_and_report(
        base, records["run"], run_directory
    )
    attempt_id, output_ref = _validate_attempt_report(
        base, records, attempt, report, attempt_ref, run_directory
    )
    if attempt.get("status") != "succeeded":
        raise ContractError("missing or failed task result")
    if (
        report.get("result") != "complete"
        or report.get("failures") != []
        or report.get("conflicts") != []
        or report.get("missing_references") != []
        or report.get("unresolved_issues") != []
    ):
        raise ContractError("aggregation report does not validate result")
    return _make_outcome(run_ref, records, attempt, report, attempt_id, output_ref)


def validate_outcome(
    state_root: str | Path,
    run_ref: str,
    *,
    source_root: str | Path,
    capabilities: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Reconstruct and compare the coordinator-persisted Outcome from artifacts."""
    state, source = _validated_roots(state_root, source_root)
    expected = _validate_acceptance(state, source, run_ref, capabilities)
    run = _validate_run(state, source, run_ref)["run"]
    run_directory = "/".join(PurePosixPath(run_ref).parts[:3])
    outcome_ref = _required_text(run, "outcome_ref", "Outcome reference")
    if outcome_ref != run_directory + "/outcome.json":
        raise ContractError("Outcome reference is outside its Run")
    persisted = _load(state, outcome_ref, run.get("outcome_digest"))
    if persisted != expected:
        raise ContractError("persisted Outcome does not match validated artifacts")
    return persisted
