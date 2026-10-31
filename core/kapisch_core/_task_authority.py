"""Validate persisted task authority and WorkOrder applicability."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ._task_artifacts import ContractError, _load, _required_id, _required_text
from ._task_governing_inputs import _validate_governing_inputs


def _validate_unique_decision_reference(
    root: Path, decision_id: str, decision_ref: str
) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", decision_id):
        raise ContractError("invalid decision identity")
    matches = []
    for candidate in root.glob(".kapisch/runs/*/decisions/*.json"):
        if candidate.name != f"{decision_id}.json":
            continue
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise ContractError("decision reference escapes project root")
        matches.append(candidate)
    if len(matches) != 1 or matches[0].relative_to(root).as_posix() != decision_ref:
        raise ContractError("decision identity is not unique or reference mismatches")


def _validate_applicability(
    applicability: dict[str, Any],
    work: dict[str, Any],
    decision: dict[str, Any],
    decision_digest: str,
) -> None:
    answer_digest = hashlib.sha256(decision["answer"].encode()).hexdigest()
    if (
        applicability.get("result") != "applicable"
        or applicability.get("decision_id") != decision["decision_id"]
        or applicability.get("decision_ref") != work["decision_ref"]
        or applicability.get("decision_digest") != decision_digest
        or applicability.get("answer_digest") != answer_digest
        or applicability.get("subject") != work["subject"]
        or applicability.get("scope") != work["scope"]
        or applicability.get("governing_inputs") != work["governing_inputs"]
        or not isinstance(applicability.get("reason"), str)
        or not applicability["reason"].strip()
    ):
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )


def _validate_workorder(
    base: Path, run_directory: str, work: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_ref = _required_text(work, "decision_ref", "decision reference")
    decision_digest = _required_text(work, "decision_digest", "decision digest")
    if not decision_ref.startswith(run_directory + "/decisions/"):
        raise ContractError("decision reference is outside its Run")
    decision = _load(base, decision_ref, decision_digest)
    decision_id = _required_id(decision, "decision_id", "decision identity")
    _validate_unique_decision_reference(base, decision_id, decision_ref)
    if work.get("decision_id") != decision_id:
        raise ContractError("decision reference mismatch")
    _required_text(decision, "question_id", "decision question identity")
    _required_text(decision, "answer", "decision answer")
    _required_text(decision, "question", "decision question")
    source_kind = decision.get("source_kind")
    external_source_missing = source_kind == "external_artifact" and (
        not isinstance(decision.get("source_ref"), str)
        or not decision["source_ref"].strip()
    )
    if (
        decision.get("decision_type") != "approval"
        or not isinstance(source_kind, str)
        or source_kind
        not in {"direct_operator", "operator_reported_external", "external_artifact"}
        or external_source_missing
        or _required_text(decision, "subject", "decision subject")
        != work.get("subject")
        or _required_text(decision, "scope", "decision scope") != work.get("scope")
    ):
        raise ContractError("work order is not authorized")
    if "tasks" in work:
        raise ContractError("work order must contain exactly one task")
    task = work.get("task")
    if not isinstance(task, dict):
        raise ContractError("work order must contain one task")
    _required_id(task, "task_id", "task identity")
    _required_id(work, "workorder_id", "work order identity")
    governing = work.get("governing_inputs")
    if decision.get("governing_inputs") != governing:
        raise ContractError("governing inputs require reassessment")
    _validate_governing_inputs(base, governing)
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
