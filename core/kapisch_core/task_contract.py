"""Validation for the bounded, portable single-task acceptance contract."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from ._task_artifacts import (
    ContractError,
    _create_exclusive,
    _load,
    _read_bytes,
    _required_id,
    _required_text,
)
from ._task_authority import _validate_workorder


def _run_directory(run: dict[str, Any], run_ref: str) -> str:
    run_id = _required_id(run, "run_id", "Run identity")
    parts = PurePosixPath(run_ref).parts
    if parts != (".kapisch", "runs", run_id, "run.json"):
        raise ContractError("Run identity and portable reference mismatch")
    return "/".join(parts[:3])


def validate_run(
    root: str | Path, run_ref: str, run_digest: str | None = None
) -> dict[str, Any]:
    """Load persisted Run, WorkOrder, and authority evidence from disk."""
    base = Path(root).resolve()
    run = _load(base, run_ref, run_digest, require_digest=False)
    run_directory = _run_directory(run, run_ref)
    workorder_ref = _required_text(run, "workorder_ref", "WorkOrder reference")
    if workorder_ref != run_directory + "/workorder.json":
        raise ContractError("WorkOrder reference is outside its canonical Run path")
    work = _load(base, workorder_ref, run.get("workorder_digest"))
    decision, applicability = _validate_workorder(base, run_directory, work)
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
    return claim


def validate_dispatch(
    root: str | Path,
    run_ref: str,
    *,
    capabilities: dict[str, dict[str, str]],
    canonical_implementer_available: bool,
) -> dict[str, Any]:
    """Validate durable authorization and actual adapter capabilities before start."""
    records = validate_run(root, run_ref)
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
    claim_ref = _dispatch_claim_ref(run_ref)
    claim_path = (Path(root).resolve() / claim_ref).resolve()
    if not claim_path.is_relative_to(Path(root).resolve()):
        raise ContractError("dispatch claim escapes project root")
    candidate_claim = Path(root).resolve() / claim_ref
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
    allocation = run.get("attempt_allocation")
    if not isinstance(allocation, dict):
        raise ContractError("attempt allocation is missing before dispatch")
    attempt_id = _required_id(allocation, "attempt_id", "allocated attempt identity")
    output_ref = _required_text(allocation, "output_ref", "allocated output reference")
    run_directory = "/".join(PurePosixPath(run_ref).parts[:3])
    if output_ref != run_directory + "/attempts/" + attempt_id + "-output.json":
        raise ContractError("allocated output reference mismatch")
    output_path = (Path(root).resolve() / output_ref).resolve()
    if not output_path.is_relative_to(Path(root).resolve()):
        raise ContractError("allocated output escapes project root")
    attempt_path = (
        Path(root).resolve() / run_directory / "attempts" / (attempt_id + ".json")
    ).resolve()
    if not attempt_path.is_relative_to(Path(root).resolve()):
        raise ContractError("allocated attempt escapes project root")
    if output_path.exists() or attempt_path.exists():
        raise ContractError("attempt allocation already exists")
    if (
        work["worker_route"] == "host_native_fallback"
        and canonical_implementer_available
    ):
        raise ContractError(
            "host-native fallback forbidden while canonical implementer is available"
        )
    return {**records, "attempt_allocation": allocation}


def claim_dispatch(
    root: str | Path,
    run_ref: str,
    *,
    capabilities: dict[str, dict[str, str]],
    canonical_implementer_available: bool,
) -> dict[str, Any]:
    """Durably claim the sole attempt before invoking the host adapter."""
    records = validate_dispatch(
        root,
        run_ref,
        capabilities=capabilities,
        canonical_implementer_available=canonical_implementer_available,
    )
    claim = _dispatch_claim_record(run_ref, records)
    _create_exclusive(Path(root).resolve(), _dispatch_claim_ref(run_ref), claim)
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


def _make_outcome(
    run_ref: str,
    records: dict[str, Any],
    attempt: dict[str, Any],
    report: dict[str, Any],
    attempt_id: str,
    output_ref: str,
) -> dict[str, Any]:
    run, work, decision = records["run"], records["workorder"], records["decision"]
    return {
        "status": "complete",
        "run_ref": run_ref,
        "workorder_id": work["workorder_id"],
        "workorder_digest": run["workorder_digest"],
        "decision_id": decision["decision_id"],
        "decision_digest": work["decision_digest"],
        "authority": {
            "decision_type": decision["decision_type"],
            "decision_id": decision["decision_id"],
            "subject": work["subject"],
            "scope": work["scope"],
        },
        "decision": {
            "ref": work["decision_ref"],
            "decision_id": decision["decision_id"],
            "source_kind": decision["source_kind"],
            "subject": decision["subject"],
            "scope": decision["scope"],
            "applicability": {
                "status": "applicable",
                "ref": work["applicability_ref"],
                "digest": work["applicability_digest"],
                "reason": records["applicability"]["reason"],
            },
        },
        "workorder_ref": run["workorder_ref"],
        "attempt": {
            "ref": run["attempt_ref"],
            "id": attempt_id,
            "status": attempt["status"],
        },
        "evidence_refs": [
            {
                "kind": "attempt_output",
                "ref": output_ref,
                "digest": attempt["output_digest"],
            }
        ],
        "aggregation_report": {
            "ref": run["aggregation_ref"],
            "digest": run["aggregation_digest"],
            "result": report["result"],
            "coverage": report["coverage"],
            "acceptance_criteria": report["acceptance_criteria"],
        },
    }


def validate_acceptance(
    root: str | Path,
    run_ref: str,
    *,
    capabilities: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Validate one attempt and report before returning coordinator Outcome data."""
    records = validate_run(root, run_ref)
    _validate_capabilities(records["workorder"], capabilities)
    base = Path(root).resolve()
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
    root: str | Path,
    run_ref: str,
    *,
    capabilities: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Reconstruct and compare the coordinator-persisted Outcome from artifacts."""
    expected = validate_acceptance(root, run_ref, capabilities=capabilities)
    base = Path(root).resolve()
    run = validate_run(base, run_ref)["run"]
    run_directory = "/".join(PurePosixPath(run_ref).parts[:3])
    outcome_ref = _required_text(run, "outcome_ref", "Outcome reference")
    if outcome_ref != run_directory + "/outcome.json":
        raise ContractError("Outcome reference is outside its Run")
    persisted = _load(base, outcome_ref, run.get("outcome_digest"))
    if persisted != expected:
        raise ContractError("persisted Outcome does not match validated artifacts")
    return persisted
