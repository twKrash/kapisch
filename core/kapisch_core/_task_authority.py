"""Validate persisted task authority and WorkOrder applicability."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ._task_artifacts import (
    ContractError,
    _load,
    _required_id,
    _required_text,
)
from ._task_decisions import (
    _DecisionRecord,
    _load_decision,
    _validated_historical_inputs,
)
from ._task_governing_inputs import (
    _validate_governing_inputs,
    _validated_governing_inputs,
)

_ORIGINAL_GOVERNING_INPUTS = "original_governing_inputs"
_APPLICABILITY_CONTROL_FIELDS = ("result", "reason")
_APPLICABILITY_RESULTS = frozenset(
    {
        "applicable",
        "not_applicable",
        "ambiguous",
        "reassessment_required",
    }
)
_APPLICABILITY_BINDING_FIELDS = (
    "decision_id",
    "decision_ref",
    "decision_digest",
    "answer_digest",
    "subject",
    "scope",
    "governing_inputs",
)
_APPLICABILITY_DIAGNOSTICS = {
    "invalid_result": "invalid decision applicability result",
    **{
        result: f"decision applicability result is {result}"
        for result in _APPLICABILITY_RESULTS
        if result != "applicable"
    },
}


def _validate_applicability(
    applicability: dict[str, Any],
    work: dict[str, Any],
    decision: dict[str, Any],
    decision_digest: str,
) -> None:
    result_field, reason_field = _APPLICABILITY_CONTROL_FIELDS
    result = applicability.get(result_field)
    if not isinstance(result, str) or result not in _APPLICABILITY_RESULTS:
        raise ContractError(_APPLICABILITY_DIAGNOSTICS["invalid_result"])
    if result != "applicable":
        raise ContractError(_APPLICABILITY_DIAGNOSTICS[result])
    try:
        answer_bytes = decision["answer"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    answer_digest = hashlib.sha256(answer_bytes).hexdigest()
    expected_values = (
        ("decision_id", decision["decision_id"]),
        ("decision_ref", work["decision_ref"]),
        ("decision_digest", decision_digest),
        ("answer_digest", answer_digest),
        ("subject", work["subject"]),
        ("scope", work["scope"]),
        ("governing_inputs", work["governing_inputs"]),
    )
    expected = dict(expected_values)
    if any(
        applicability.get(key) != expected[key] for key in _APPLICABILITY_BINDING_FIELDS
    ):
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )
    reason = applicability.get(reason_field)
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )


def _validate_governing_binding(
    base: Path,
    work: dict[str, Any],
    decision: dict[str, Any],
    applicability: dict[str, Any],
) -> None:
    historical = decision["governing_inputs"]
    if _ORIGINAL_GOVERNING_INPUTS in applicability:
        original = applicability[_ORIGINAL_GOVERNING_INPUTS]
        _validated_historical_inputs(original)
        if original != historical:
            raise ContractError("original governing inputs mismatch")
    elif work.get("governing_inputs") != historical:
        raise ContractError("governing inputs require reassessment")


def _validate_workorder(
    base: Path,
    run_directory: str,
    work: dict[str, Any],
    decision_records: dict[str, _DecisionRecord] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_ref = _required_text(work, "decision_ref", "decision reference")
    decision_digest = _required_text(work, "decision_digest", "decision digest")
    decision = _load_decision(
        base, decision_ref, decision_digest, records=decision_records
    )
    _validated_governing_inputs(decision["governing_inputs"])
    decision_id = decision["decision_id"]
    if work.get("decision_id") != decision_id:
        raise ContractError("decision reference mismatch")
    if (
        decision["decision_type"] != "approval"
        or decision["subject"] != work.get("subject")
        or decision["scope"] != work.get("scope")
    ):
        raise ContractError("work order is not authorized")
    if "tasks" in work:
        raise ContractError("work order must contain exactly one task")
    task = work.get("task")
    if not isinstance(task, dict):
        raise ContractError("work order must contain one task")
    _required_id(task, "task_id", "task identity")
    _required_id(work, "workorder_id", "work order identity")
    _validate_governing_inputs(base, work.get("governing_inputs"))
    acceptance = work.get("acceptance_criteria")
    if (
        not isinstance(acceptance, list)
        or not acceptance
        or not all(isinstance(item, str) and item.strip() for item in acceptance)
    ):
        raise ContractError("invalid WorkOrder acceptance criteria")
    if not isinstance(work.get("required_capabilities"), list) or not all(
        isinstance(item, str) and item for item in work["required_capabilities"]
    ):
        raise ContractError("invalid required capabilities")
    applicability_ref = _required_text(
        work, "applicability_ref", "applicability reference"
    )
    applicability_digest = _required_text(
        work, "applicability_digest", "applicability digest"
    )
    if applicability_ref != run_directory + "/applicability.json":
        raise ContractError("Applicability reference is outside its Run")
    applicability = _load(base, applicability_ref, applicability_digest)
    _validate_governing_binding(base, work, decision, applicability)
    _validate_applicability(applicability, work, decision, decision_digest)
    route = _required_text(work, "worker_route", "worker route")
    role = _required_text(work, "worker_role", "worker role")
    if route == "host_native_fallback":
        fallback_reason = applicability.get("fallback_authorization_reason")
        if (
            role != "worker"
            or work.get("canonical_implementer_available") is not False
            or applicability.get("host_native_fallback_authorized") is not True
            or not isinstance(fallback_reason, str)
            or not fallback_reason.strip()
        ):
            raise ContractError(
                "host-native fallback is not authorized or canonical implementer is available"
            )
    elif route == "canonical_implementer":
        if (
            role != "implementer"
            or work.get("canonical_implementer_available") is not True
        ):
            raise ContractError("canonical implementer route is not available")
    else:
        raise ContractError("unsupported worker route")
    return decision, applicability
