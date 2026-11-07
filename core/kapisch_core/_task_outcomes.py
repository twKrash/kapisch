"""Pure construction helpers for coordinator Outcome records."""

from __future__ import annotations

from typing import Any

from ._task_artifacts import ContractError


def _advisory_review_outcome(run: dict[str, Any], attempt_id: str) -> dict[str, str]:
    review = run.get("advisory_review", {"status": "not_run"})
    if not isinstance(review, dict):
        raise ContractError("invalid advisory review metadata")
    if review == {"status": "not_run"}:
        return {"status": "not_run"}
    if review.get("status") != "performed":
        raise ContractError("invalid advisory review metadata")
    expected = {
        "status": "performed",
        "workorder_ref": run["workorder_ref"],
        "workorder_digest": run["workorder_digest"],
        "attempt_ref": run["attempt_ref"],
        "attempt_id": attempt_id,
        "attempt_digest": run["attempt_digest"],
    }
    if review != expected:
        raise ContractError(
            "advisory review is not bound to this WorkOrder and Attempt"
        )
    return expected


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
        "advisory_review": _advisory_review_outcome(run, attempt_id),
    }
