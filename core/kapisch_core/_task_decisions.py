"""Canonical immutable HumanDecision reading and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._task_artifacts import (
    _DIGEST,
    ContractError,
    _load_with_digest,
    _required_id,
    _required_text,
)

_MISSING_DECISION = "missing referenced decision"
_DECISION_OUTSIDE_RUN = "decision reference is outside its Run"
_DECISION_RUN_MISMATCH = "decision run mismatch"


@dataclass(frozen=True)
class _DecisionRecord:
    ref: str
    digest: str
    decision: dict[str, Any]


_DECISION_REF = re.compile(
    r"\.kapisch/runs/[A-Za-z0-9][A-Za-z0-9._-]*/decisions/"
    r"[A-Za-z0-9][A-Za-z0-9_-]*\.json"
)


def _validate_decision_path(
    root: Path,
    run_directory: str,
    ref: Any,
    *,
    outside_run_message: str = _DECISION_OUTSIDE_RUN,
) -> None:
    if not isinstance(ref, str) or not _DECISION_REF.fullmatch(ref):
        raise ContractError("malformed decision reference")
    if not ref.startswith(run_directory + "/decisions/"):
        raise ContractError(outside_run_message)
    current = root
    for part in ref.split("/"):
        current = current / part
        try:
            linked = current.is_symlink()
        except OSError as exc:
            raise ContractError("cannot inspect decision reference") from exc
        if linked:
            raise ContractError("decision reference contains a symlink")


def _validate_unique_decision_reference(
    root: Path, run_directory: str, decision_id: str, decision_ref: str
) -> None:
    matches = []
    for candidate in sorted((root / run_directory / "decisions").glob("*.json")):
        if candidate.name != f"{decision_id}.json":
            continue
        ref = candidate.relative_to(root).as_posix()
        _validate_decision_path(root, run_directory, ref)
        matches.append(ref)
    if len(matches) != 1 or matches[0] != decision_ref:
        raise ContractError("decision identity is not unique or reference mismatches")


def _validated_historical_inputs(inputs: Any) -> None:
    """Match the producer request snapshot shape; no freshness, path or uniqueness policy."""
    if not isinstance(inputs, list):
        raise ContractError("invalid historical governing inputs")
    for item in inputs:
        if (
            not isinstance(item, dict)
            or set(item) != {"ref", "digest"}
            or not isinstance(item["ref"], str)
            or not item["ref"].strip()
            or not isinstance(item["digest"], str)
            or not _DIGEST.fullmatch(item["digest"])
        ):
            raise ContractError("malformed governing Git input")


def _validate_decision_authorization(decision: dict[str, Any]) -> None:
    source = decision.get("source_kind")
    decision_type = decision.get("decision_type")
    if (
        not isinstance(decision_type, str)
        or decision_type
        not in {
            "answer",
            "correction",
            "approval",
            "risk_acceptance",
            "external_effect_authorization",
        }
        or not isinstance(source, str)
        or source
        not in {"direct_operator", "operator_reported_external", "external_artifact"}
        or (
            source == "external_artifact"
            and (
                not isinstance(decision.get("source_ref"), str)
                or not decision["source_ref"].strip()
            )
        )
    ):
        raise ContractError("work order is not authorized")


def _read_decision_record(
    root: Path,
    run_directory: str,
    ref: str,
    digest: str | None = None,
    *,
    require_digest: bool = True,
) -> _DecisionRecord:
    _validate_decision_path(root, run_directory, ref)
    try:
        exists = (root / ref).exists()
    except OSError as exc:
        raise ContractError("cannot inspect decision reference") from exc
    if not exists:
        raise ContractError(_MISSING_DECISION)
    decision, actual_digest = _load_with_digest(
        root, ref, digest, require_digest=require_digest
    )
    decision_id = _required_id(decision, "decision_id", "decision identity")
    if Path(ref).name != f"{decision_id}.json":
        raise ContractError("decision identity is not unique or reference mismatches")
    if decision.get("run_id") != Path(run_directory).name:
        raise ContractError(_DECISION_RUN_MISMATCH)
    _required_text(decision, "question_id", "decision question identity")
    _required_text(decision, "question", "decision question")
    answer = _required_text(decision, "answer", "decision answer")
    try:
        answer.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    _required_text(decision, "subject", "decision subject")
    _required_text(decision, "scope", "decision scope")
    _validate_decision_authorization(decision)
    for field in ("source_ref", "approving_party"):
        if field in decision:
            _required_text(decision, field, "decision " + field)
    _validated_historical_inputs(decision.get("governing_inputs"))
    return _DecisionRecord(ref, actual_digest, decision)


def _load_decision(
    root: Path,
    run_directory: str,
    ref: str,
    digest: str | None = None,
    *,
    require_digest: bool = True,
    records: dict[str, _DecisionRecord] | None = None,
) -> dict[str, Any]:
    _validate_decision_path(root, run_directory, ref)
    if records is None:
        record = _read_decision_record(
            root, run_directory, ref, digest, require_digest=require_digest
        )
        _validate_unique_decision_reference(
            root, run_directory, record.decision["decision_id"], ref
        )
    else:
        if require_digest and digest is None:
            raise ContractError(f"missing artifact digest: {ref}")
        record = records.get(ref)
        if record is None:
            raise ContractError(_MISSING_DECISION)
        if digest is not None and digest != record.digest:
            raise ContractError(f"artifact digest mismatch: {ref}")
    return record.decision
