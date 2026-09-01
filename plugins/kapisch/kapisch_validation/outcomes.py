from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .artifact_io import ArtifactFailure, ArtifactFailureKind, load_toml_artifact, read_utf8_artifact
from .errors import ValidationError
from .models import Manifest, State
from .vocabulary import EXECUTOR_CLASS_VALUES

OUTCOME_FIELDS = {
    "version", "task_id", "node_id", "role", "assignment_id", "attempt_id",
    "lifecycle", "role_status", "base_revision", "head_revision",
    "working_tree_state_sha256", "report_path", "report_sha256", "invocation_path",
    "invocation_id", "invocation_sha256", "reviewer_decision", "redispatch_reason",
    "predecessor_attempt_id", "retry_budget_delta", "next_action_reason", "findings",
    "verification",
}
LIFECYCLE_VALUES = ("complete", "blocked", "failed")
ROLE_STATUS_VALUES = ("done", "done-with-concerns", "needs-context", "blocked", "failed")
SEVERITY_VALUES = ("P0", "P1", "P2", "P3")
REVIEWER_DECISION_VALUES = ("unavailable", "approve", "do-not-approve", "ready", "not-ready")
REDISPATCH_VALUES = (
    "none", "interrupted-active-stage", "reviewer-finding", "failed-attempt",
    "stale-review-state", "approved-amendment", "dispatch-no-work",
)
NEXT_ACTION_VALUES = (
    "completed", "blocked", "failed", "review-negative", "review-stale", "await-user",
    "retry-authorized", "retry-exhausted", "dispatch-failed",
)
RETRY_DELTAS = {
    "none": 0, "interrupted-active-stage": 0, "stale-review-state": 0,
    "dispatch-no-work": 0, "reviewer-finding": 1, "failed-attempt": 1,
    "approved-amendment": 1,
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _e(code: str, path: Path, reference: str, message: str) -> ValidationError:
    return ValidationError(code, str(path), reference, message)


def _contained(task_dir: Path, relative_path: object) -> Path | None:
    if not isinstance(relative_path, str) or not relative_path or "\0" in relative_path:
        return None
    try:
        root = task_dir.resolve()
        candidate = (root / relative_path).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError, RuntimeError):
        return None
    return candidate


def _digest(path: Path) -> str | None:
    artifact, failure = read_utf8_artifact(path)
    if failure is not None:
        return None
    assert artifact is not None
    return hashlib.sha256(artifact.data).hexdigest()


def _load_error(path: Path, failure: ArtifactFailure) -> ValidationError:
    codes = {
        ArtifactFailureKind.MISSING: "TWV-OUTCOME-MISSING",
        ArtifactFailureKind.NOT_REGULAR: "TWV-OUTCOME-NOT-REGULAR",
        ArtifactFailureKind.INVALID_UTF8: "TWV-OUTCOME-INVALID-UTF8",
        ArtifactFailureKind.MALFORMED_TOML: "TWV-OUTCOME-MALFORMED-TOML",
        ArtifactFailureKind.UNREADABLE: "TWV-OUTCOME-UNREADABLE",
    }
    return _e(codes[failure.kind], path, path.name, "stage outcome is not a readable UTF-8 TOML file")


def _schema_errors(raw: dict[str, object], path: Path) -> list[ValidationError]:
    errors = [
        _e("TWV-OUTCOME-UNKNOWN-FIELD", path, key, "unknown outcome field")
        for key in sorted(set(raw) - OUTCOME_FIELDS)
    ]
    for key in sorted(OUTCOME_FIELDS):
        if key not in raw:
            errors.append(_e("TWV-OUTCOME-MISSING-FIELD", path, key, "required outcome field is missing"))
    if raw.get("version") != 1:
        errors.append(_e("TWV-OUTCOME-INVALID-VERSION", path, "version", "must be integer 1"))
    string_values = {
        "task_id", "node_id", "role", "assignment_id", "attempt_id", "lifecycle",
        "role_status", "base_revision", "head_revision", "working_tree_state_sha256",
        "report_path", "report_sha256", "invocation_path", "invocation_id",
        "invocation_sha256", "reviewer_decision", "redispatch_reason",
        "predecessor_attempt_id", "next_action_reason",
    }
    for key in string_values:
        if key in raw and (not isinstance(raw[key], str) or not raw[key]):
            errors.append(_e("TWV-OUTCOME-WRONG-SHAPE", path, key, "must be a non-empty string"))
    for key, allowed in (
        ("role", EXECUTOR_CLASS_VALUES), ("lifecycle", LIFECYCLE_VALUES),
        ("role_status", ROLE_STATUS_VALUES), ("reviewer_decision", REVIEWER_DECISION_VALUES),
        ("redispatch_reason", REDISPATCH_VALUES), ("next_action_reason", NEXT_ACTION_VALUES),
    ):
        if key in raw and raw[key] not in allowed:
            errors.append(_e("TWV-OUTCOME-INVALID-VALUE", path, key, "unsupported closed-vocabulary value"))
    for key in ("report_sha256",):
        if key in raw and (not isinstance(raw[key], str) or SHA256_RE.fullmatch(raw[key]) is None):
            errors.append(_e("TWV-OUTCOME-INVALID-DIGEST", path, key, "must be 64 lowercase hexadecimal characters"))
    for key in ("working_tree_state_sha256", "invocation_sha256"):
        if key in raw and raw[key] != "unavailable" and (
            not isinstance(raw[key], str) or SHA256_RE.fullmatch(raw[key]) is None
        ):
            errors.append(_e("TWV-OUTCOME-INVALID-DIGEST", path, key, "must be unavailable or 64 lowercase hexadecimal characters"))
    if not isinstance(raw.get("retry_budget_delta"), int) or isinstance(raw.get("retry_budget_delta"), bool):
        errors.append(_e("TWV-OUTCOME-WRONG-SHAPE", path, "retry_budget_delta", "must be an integer"))
    elif raw.get("redispatch_reason") in RETRY_DELTAS and raw["retry_budget_delta"] != RETRY_DELTAS[raw["redispatch_reason"]]:
        errors.append(_e("TWV-OUTCOME-REDISPATCH-BUDGET", path, "retry_budget_delta", "does not match redispatch reason"))
    if raw.get("redispatch_reason") != "none" and raw.get("predecessor_attempt_id") == "unavailable":
        errors.append(_e("TWV-OUTCOME-REDISPATCH-PREDECESSOR", path, "predecessor_attempt_id", "re-dispatch requires predecessor attempt"))
    _collection_errors(raw.get("findings"), path, "findings", {"id", "severity", "summary", "evidence_ref"}, errors)
    findings = raw.get("findings")
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if isinstance(finding, dict):
                if finding.get("severity") not in SEVERITY_VALUES:
                    errors.append(_e("TWV-OUTCOME-INVALID-VALUE", path, f"findings[{index}].severity", "unsupported severity"))
                summary = finding.get("summary")
                if not isinstance(summary, str) or not 1 <= len(summary) <= 280:
                    errors.append(_e("TWV-OUTCOME-SUMMARY-LIMIT", path, f"findings[{index}].summary", "must be 1-280 Unicode code points"))
    _collection_errors(raw.get("verification"), path, "verification", {"check", "result", "evidence_ref", "output_sha256"}, errors)
    verification = raw.get("verification")
    if isinstance(verification, list):
        for index, record in enumerate(verification):
            if not isinstance(record, dict):
                continue
            result = record.get("result")
            if result not in {"pass", "fail", "not-run", "unavailable"}:
                errors.append(_e("TWV-OUTCOME-INVALID-VALUE", path, f"verification[{index}].result", "unsupported verification result"))
            digest = record.get("output_sha256")
            if result in {"pass", "fail"} and (not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None):
                errors.append(_e("TWV-OUTCOME-INVALID-DIGEST", path, f"verification[{index}].output_sha256", "pass/fail requires digest"))
            if result in {"not-run", "unavailable"} and digest != "unavailable":
                errors.append(_e("TWV-OUTCOME-INVALID-DIGEST", path, f"verification[{index}].output_sha256", "unavailable result requires unavailable digest"))
    return errors


def _collection_errors(value: object, path: Path, name: str, fields: set[str], errors: list[ValidationError]) -> None:
    if not isinstance(value, list):
        errors.append(_e("TWV-OUTCOME-WRONG-SHAPE", path, name, "must be an array"))
        return
    if len(value) > 20:
        errors.append(_e("TWV-OUTCOME-LIMIT", path, name, "contains more than 20 records"))
    for index, record in enumerate(value):
        if not isinstance(record, dict) or set(record) != fields:
            errors.append(_e("TWV-OUTCOME-WRONG-SHAPE", path, f"{name}[{index}]", "must have the exact required fields"))
            continue
        for field, item in record.items():
            if not isinstance(item, str) or not item:
                errors.append(_e("TWV-OUTCOME-WRONG-SHAPE", path, f"{name}[{index}].{field}", "must be a non-empty string"))


def parse_outcome(path: Path) -> tuple[dict[str, object] | None, list[ValidationError]]:
    raw, failure = load_toml_artifact(path)
    if failure is not None:
        return None, [_load_error(path, failure)]
    assert raw is not None
    errors = _schema_errors(raw, path)
    return (raw if not errors else None), errors


def _attempts(manifest: Manifest):
    for node in manifest.nodes:
        assignment = node.raw.get("assignment")
        if not isinstance(assignment, dict):
            continue
        attempts = assignment.get("attempts")
        if not isinstance(attempts, list):
            continue
        for attempt in attempts:
            if isinstance(attempt, dict):
                yield node, assignment, attempt


def _outcome_binding_errors(raw: dict[str, object], path: Path, node, assignment: dict[str, object], attempt: dict[str, object], manifest: Manifest, task_dir: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    expected = {
        "task_id": manifest.task_id, "node_id": node.id, "role": node.raw.get("executor_class"),
        "assignment_id": assignment.get("id"), "attempt_id": attempt.get("id"),
        "report_path": node.raw.get("report"),
    }
    for field, value in expected.items():
        if raw.get(field) != value:
            errors.append(_e("TWV-OUTCOME-BINDING", path, field, "does not match canonical graph binding"))
    revision = node.raw.get("revision")
    if isinstance(revision, dict):
        for field, key in (("base_revision", "base"), ("head_revision", "head")):
            if raw.get(field) != revision.get(key):
                errors.append(_e("TWV-OUTCOME-REVISION", path, field, "does not match node revision binding"))
    report = _contained(task_dir, raw.get("report_path"))
    if report is None or _digest(report) is None:
        errors.append(_e("TWV-OUTCOME-REPORT-PATH", path, "report_path", "must name a regular artifact inside task directory"))
    elif raw.get("report_sha256") != _digest(report):
        errors.append(_e("TWV-OUTCOME-REPORT-DIGEST", path, "report_sha256", "does not match detailed report bytes"))
    if raw.get("lifecycle") != attempt.get("status"):
        errors.append(_e("TWV-OUTCOME-LIFECYCLE", path, "lifecycle", "must match terminal attempt status"))
    reviewer = node.raw.get("executor_class") == "reviewer"
    invocation_fields = ("invocation_path", "invocation_id", "invocation_sha256")
    if not reviewer:
        if any(raw.get(field) != "unavailable" for field in (*invocation_fields, "reviewer_decision")):
            errors.append(_e("TWV-OUTCOME-REVIEWER-EVIDENCE", path, "invocation_path", "only reviewers may carry reviewer evidence"))
        return errors
    invocation_path = node.raw.get("reviewer_invocation")
    if raw.get("invocation_path") != invocation_path:
        errors.append(_e("TWV-OUTCOME-INVOCATION", path, "invocation_path", "does not match canonical invocation"))
        return errors
    invocation = _contained(task_dir, invocation_path)
    invocation_raw, failure = load_toml_artifact(invocation) if invocation is not None else (None, ArtifactFailure(ArtifactFailureKind.MISSING))
    if failure is not None or invocation_raw is None:
        errors.append(_e("TWV-OUTCOME-INVOCATION", path, "invocation_path", "canonical invocation is unavailable"))
        return errors
    if raw.get("invocation_sha256") != _digest(invocation):
        errors.append(_e("TWV-OUTCOME-INVOCATION-DIGEST", path, "invocation_sha256", "does not match invocation bytes"))
    if raw.get("invocation_id") != invocation_raw.get("invocation_id"):
        errors.append(_e("TWV-OUTCOME-INVOCATION", path, "invocation_id", "does not match invocation"))
    if raw.get("reviewer_decision") != invocation_raw.get("returned_decision"):
        errors.append(_e("TWV-OUTCOME-REVIEWER-DECISION", path, "reviewer_decision", "does not match canonical invocation result"))
    return errors


def _report_authorizes_finding(outcome: dict[str, object], finding: object, task_dir: Path, reviewer_node_id: str) -> bool:
    if not isinstance(finding, dict):
        return False
    report_path = outcome.get("report_path")
    report = _contained(task_dir, report_path)
    artifact, failure = read_utf8_artifact(report) if report is not None else (None, ArtifactFailure(ArtifactFailureKind.MISSING))
    if failure is not None or artifact is None:
        return False
    fields = {
        "finding_id": finding.get("id"),
        "finding_severity": finding.get("severity"),
        "finding_summary": finding.get("summary"),
        "finding_scope": reviewer_node_id,
    }
    if not all(isinstance(value, str) and value for value in fields.values()):
        return False
    keys = tuple(fields)
    lines = artifact.data.decode("utf-8").splitlines()
    return any(
        {key: lines[index + offset][len(key) + 2:] for offset, key in enumerate(keys)} == fields
        for index in range(len(lines) - len(keys) + 1)
        if all(lines[index + offset].startswith(f"{key}: ") for offset, key in enumerate(keys))
    )


def _redispatch_errors(
    raw: dict[str, object], path: Path, node, attempt: dict[str, object],
    attempts: list[tuple[object, dict[str, object], dict[str, object]]],
    valid_outcomes: dict[str, dict[str, object]], task_dir: Path
) -> list[ValidationError]:
    reason = raw.get("redispatch_reason")
    if reason == "none":
        return []
    predecessor_id = raw.get("predecessor_attempt_id")
    predecessor = next((item for item in attempts if item[2].get("id") == predecessor_id), None)
    if predecessor is None or predecessor_id == attempt.get("id"):
        return [_e("TWV-OUTCOME-REDISPATCH-PREDECESSOR", path, "predecessor_attempt_id", "must name an earlier persisted attempt")]
    predecessor_node, _, predecessor_attempt = predecessor
    current_rank = (node.sequence, next(index for index, value in enumerate(attempts) if value[2] is attempt))
    predecessor_rank = (predecessor_node.sequence, next(index for index, value in enumerate(attempts) if value[2] is predecessor_attempt))
    if predecessor_rank >= current_rank or predecessor_attempt.get("status") not in LIFECYCLE_VALUES:
        return [_e("TWV-OUTCOME-REDISPATCH-PREDECESSOR", path, "predecessor_attempt_id", "must precede this terminal attempt")]
    outcome_path = predecessor_attempt.get("outcome_path")
    if not isinstance(outcome_path, str) or outcome_path not in valid_outcomes:
        return [_e("TWV-OUTCOME-REDISPATCH-PREDECESSOR", path, "predecessor_attempt_id", "must bind a valid terminal outcome")]
    predecessor_outcome = valid_outcomes[outcome_path]
    if reason == "reviewer-finding":
        findings = predecessor_outcome.get("findings")
        if (
            predecessor_outcome.get("role") != "reviewer"
            or not isinstance(findings, list)
            or not any(_report_authorizes_finding(predecessor_outcome, finding, task_dir, predecessor_node.id) for finding in findings)
        ):
            return [_e("TWV-OUTCOME-REDISPATCH-AUTHORIZATION", path, "predecessor_attempt_id", "reviewer-finding requires a finding authorized by the canonical reviewer report")]
    if reason == "approved-amendment":
        return [_e("TWV-OUTCOME-REDISPATCH-AUTHORIZATION", path, "redispatch_reason", "approved-amendment requires a versioned amendment authority artifact")]
    same_node = {"interrupted-active-stage", "failed-attempt", "dispatch-no-work"}
    if reason in same_node and predecessor_node.id != node.id:
        return [_e("TWV-OUTCOME-REDISPATCH-PREDECESSOR", path, "predecessor_attempt_id", "reason requires a predecessor in the same node")]
    return []


def validate_outcomes(manifest: Manifest, state: State, task_dir: Path) -> list[ValidationError]:
    if manifest.version != 4:
        return []
    errors: list[ValidationError] = []
    attempts = list(_attempts(manifest))
    parsed: list[tuple[object, dict[str, object], dict[str, object], Path, dict[str, object]]] = []
    valid_outcomes: dict[str, dict[str, object]] = {}
    for node, assignment, attempt in attempts:
        if attempt.get("status") not in LIFECYCLE_VALUES:
            continue
        path = _contained(task_dir, attempt.get("outcome_path"))
        if path is None:
            errors.append(_e("TWV-OUTCOME-PATH", task_dir / "02-execution-graph.toml", f"{node.id}:{attempt.get('id')}", "terminal attempt outcome path is invalid"))
            continue
        raw, parse_errors = parse_outcome(path)
        errors.extend(parse_errors)
        if raw is not None:
            binding_errors = _outcome_binding_errors(raw, path, node, assignment, attempt, manifest, task_dir)
            errors.extend(binding_errors)
            parsed.append((node, assignment, attempt, path, raw))
            if not binding_errors and isinstance(attempt.get("outcome_path"), str):
                valid_outcomes[attempt["outcome_path"]] = raw
    for node, _, attempt, path, raw in parsed:
        errors.extend(_redispatch_errors(raw, path, node, attempt, attempts, valid_outcomes, task_dir))
    consumed = sum(
        raw["retry_budget_delta"]
        for _, _, _, _, raw in parsed
        if isinstance(raw.get("retry_budget_delta"), int) and not isinstance(raw["retry_budget_delta"], bool)
    )
    if consumed != state.raw.get("current_fix_round") or consumed > state.raw.get("max_fix_rounds", -1):
        errors.append(_e("TWV-OUTCOME-REDISPATCH-BUDGET", task_dir / "03-state.toml", "current_fix_round", "state retry budget does not match persisted outcomes"))
    return errors
