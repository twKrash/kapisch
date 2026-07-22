from __future__ import annotations

import hashlib
import re
import tomllib
from collections import Counter
from pathlib import Path

from .errors import ValidationError
from .helpers import non_empty_string
from .models import Manifest, Node, State

ENVELOPE = {
    "invocation_id",
    "mode",
    "dispatch_mode",
    "requested_role",
    "requested_profile",
    "task_name",
    "dispatching_controller",
    "target",
    "base_revision",
    "reviewed_revision",
    "working_tree_state",
    "post_review_working_tree_state",
    "pre_dispatch_state_digest",
    "post_review_state_digest",
    "lifecycle_status",
    "expected_result_path",
    "produced_result_path",
    "result_encoding",
    "result_sha256",
    "returned_role",
    "returned_profile",
    "returned_target",
    "returned_revision",
    "returned_working_tree_state",
    "returned_decision",
    "external_task_id",
    "external_task_url",
    "external_task_ref",
    "external_task_request",
    "identity_assurance",
    "reviewer_selection_attested",
    "spawn_agent_type",
    "spawn_fork_turns",
    "spawn_result_task_name",
    "extensions",
}

LIFECYCLE_STATUSES = {"planned", "dispatched", "completed", "blocked", "failed"}
CANONICAL_REVIEWER_PROFILE = ".codex/agents/kapisch-reviewer.toml"
LEGACY_REVIEWER_PROFILE = ".codex/agents/reviewer.toml"
IDENTITY_ASSURANCES = {
    "observable-named-dispatch",
    "external-named-task",
    "user-attested-external-reference",
}
RESULT_FIELDS = {
    "produced_result_path",
    "result_sha256",
    "returned_role",
    "returned_profile",
    "returned_target",
    "returned_revision",
    "returned_working_tree_state",
    "returned_decision",
    "post_review_working_tree_state",
    "post_review_state_digest",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
EXTERNAL_TASK_REF_RE = re.compile(r"ext-[a-z0-9][a-z0-9-]{2,79}")
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
STATE_RE = re.compile(
    r"head=(?P<head>[^;\r\n]+);"
    r"index_sha256=(?P<index>[0-9a-f]{64});"
    r"staged_diff_sha256=(?P<staged>[0-9a-f]{64});"
    r"unstaged_diff_sha256=(?P<unstaged>[0-9a-f]{64});"
    r"status_sha256=(?P<status>[0-9a-f]{64});"
    r"relevant_untracked_count=0;"
    rf"relevant_untracked_sha256={EMPTY_SHA256}"
)


def _e(c: str, p: Path, r: str, m: str) -> ValidationError:
    return ValidationError(c, str(p), r, m)


def _load(path: Path) -> tuple[dict[str, object] | None, list[ValidationError]]:
    if not path.is_file():
        return None, [
            _e(
                "TWV-REVIEW-MISSING-INVOCATION",
                path,
                path.name,
                "canonical invocation is missing",
            )
        ]
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return None, [_e("TWV-PARSE-MALFORMED-TOML", path, "toml", str(exc))]
    errors = [
        _e("TWV-SCHEMA-UNKNOWN-FIELD", path, key, "unknown normative field")
        for key in sorted(set(raw) - ENVELOPE)
    ]
    extensions = raw.get("extensions")
    if extensions is not None and not isinstance(extensions, dict):
        errors.append(
            _e("TWV-SCHEMA-WRONG-SHAPE", path, "extensions", "must be a table")
        )
    elif isinstance(extensions, dict):
        for namespace in sorted(extensions):
            if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", namespace):
                errors.append(
                    _e(
                        "TWV-SCHEMA-INVALID-EXTENSION",
                        path,
                        f"extensions.{namespace}",
                        "extension keys must be reverse-DNS namespaces",
                    )
                )
    for key in ENVELOPE - {"extensions"}:
        if key not in raw:
            errors.append(
                _e("TWV-SCHEMA-MISSING-FIELD", path, key, "required field is missing")
            )
    string_fields = ENVELOPE - {"extensions", "reviewer_selection_attested"}
    for key in string_fields:
        if key in raw:
            non_empty_string(
                raw[key],
                errors,
                _e("TWV-SCHEMA-WRONG-SHAPE", path, key, "must be a non-empty string"),
            )
    if "reviewer_selection_attested" in raw and not isinstance(
        raw["reviewer_selection_attested"], bool
    ):
        errors.append(
            _e(
                "TWV-SCHEMA-WRONG-SHAPE",
                path,
                "reviewer_selection_attested",
                "must be a boolean",
            )
        )
    return raw, errors


def _contained(task_dir: Path, relative_path: str) -> Path | None:
    """Resolve a referenced evidence path only when it stays inside task_dir."""
    candidate = (task_dir / relative_path).resolve()
    try:
        candidate.relative_to(task_dir.resolve())
    except ValueError:
        return None
    return candidate


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _valid_reviewer_profiles(raw: dict[str, object], lifecycle: object) -> bool:
    requested = raw["requested_profile"]
    if lifecycle != "completed":
        return requested == CANONICAL_REVIEWER_PROFILE
    return requested in {CANONICAL_REVIEWER_PROFILE, LEGACY_REVIEWER_PROFILE} and (
        raw["returned_profile"] == requested
    )


def _has_exact_line(value: object, field: str, expected_value: str) -> bool:
    if not isinstance(value, str):
        return False
    expected = f"{field}={expected_value}"
    return sum(line == expected for line in re.split(r"\r?\n", value)) == 1


def _reservable_identity(raw: dict[str, object], field: str) -> str | None:
    value = raw.get(field)
    if isinstance(value, str) and value and value != "unavailable":
        return value
    return None


def _duplicate_identity_errors(
    evidence: list[tuple[Node, Path, dict[str, object], list[ValidationError]]],
) -> list[ValidationError]:
    invocation_counts = Counter(
        value
        for _, _, raw, _ in evidence
        if (value := _reservable_identity(raw, "invocation_id")) is not None
    )
    external_counts = Counter(
        value
        for _, _, raw, _ in evidence
        for field in ("external_task_id", "external_task_url", "external_task_ref")
        if (value := _reservable_identity(raw, field)) is not None
    )
    errors: list[ValidationError] = []
    for _, invocation_path, raw, _ in sorted(
        evidence, key=lambda record: (str(record[1]), record[0].id)
    ):
        invocation_id = _reservable_identity(raw, "invocation_id")
        if invocation_id is not None and invocation_counts[invocation_id] > 1:
            errors.append(
                _e(
                    "TWV-REVIEW-REUSED-INVOCATION",
                    invocation_path,
                    invocation_id,
                    "invocation ID is reused",
                )
            )
        for field in ("external_task_id", "external_task_url", "external_task_ref"):
            external_identity = _reservable_identity(raw, field)
            if external_identity is not None and external_counts[external_identity] > 1:
                errors.append(
                    _e(
                        "TWV-REVIEW-REUSED-INVOCATION",
                        invocation_path,
                        external_identity,
                        "external task identity is reused",
                    )
                )
    return errors


def _validate_node_result_paths(
    nodes: list[Node], task_dir: Path, manifest_path: Path
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    resolved_paths: dict[Path, list[Node]] = {}
    for node in nodes:
        report_ref = node.paths[2] if len(node.paths) > 2 else ""
        report_path = _contained(task_dir, report_ref) if report_ref else None
        if report_path is None:
            errors.append(
                _e(
                    "TWV-REVIEW-RESULT-PATH-MISMATCH",
                    manifest_path,
                    node.id,
                    "review and final nodes require an in-task report path",
                )
            )
            continue
        resolved_paths.setdefault(report_path, []).append(node)
    for report_path, owners in sorted(
        resolved_paths.items(), key=lambda item: str(item[0])
    ):
        if len(owners) < 2:
            continue
        for node in sorted(owners, key=lambda owner: owner.id):
            errors.append(
                _e(
                    "TWV-REVIEW-RESULT-PATH-MISMATCH",
                    manifest_path,
                    node.id,
                    f"review/final report path is reused: {report_path}",
                )
            )
    return errors


def _has_reservable_invocation_id(
    raw: dict[str, object],
) -> bool:
    return _reservable_identity(raw, "invocation_id") is not None


def _validate_state_payload(
    payload: object,
    revision: object,
    invocation_path: Path,
    invocation_id: str,
    field: str,
) -> list[ValidationError]:
    if not isinstance(payload, str):
        return []
    match = STATE_RE.fullmatch(payload)
    if match is None or match.group("head") != revision:
        return [
            _e(
                "TWV-REVIEW-INVALID-GIT-STATE",
                invocation_path,
                invocation_id,
                f"{field} is not the canonical staged Git-state payload",
            )
        ]
    return []


def _validate_dispatch(
    raw: dict[str, object],
    invocation_path: Path,
    invocation_id: str,
    lifecycle: object,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    controller = raw["dispatching_controller"]
    if controller == "unavailable":
        errors.append(
            _e(
                "TWV-REVIEW-MALFORMED-ENVELOPE",
                invocation_path,
                invocation_id,
                "dispatching_controller may not be unavailable",
            )
        )
    assurance = raw["identity_assurance"]
    if assurance not in IDENTITY_ASSURANCES:
        errors.append(
            _e(
                "TWV-REVIEW-MALFORMED-ENVELOPE",
                invocation_path,
                invocation_id,
                "identity_assurance has an invalid value",
            )
        )
    if raw["dispatch_mode"] == "runtime-named-spawn":
        spawn_result_task_name = raw["spawn_result_task_name"]
        valid_spawn_result = (
            spawn_result_task_name == "unavailable"
            if lifecycle == "planned"
            else spawn_result_task_name in {raw["task_name"], "unavailable"}
        )
        if (
            assurance != "observable-named-dispatch"
            or raw["spawn_agent_type"] != "reviewer"
            or raw["spawn_fork_turns"] != "none"
            or not valid_spawn_result
            or raw["task_name"] == controller
            or (
                spawn_result_task_name != "unavailable"
                and spawn_result_task_name == controller
            )
            or raw["external_task_id"] != "unavailable"
            or raw["external_task_url"] != "unavailable"
            or raw["external_task_ref"] != "unavailable"
            or raw["external_task_request"] != "unavailable"
            or raw["reviewer_selection_attested"] is not False
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-MALFORMED-ENVELOPE",
                    invocation_path,
                    invocation_id,
                    "runtime reviewer identity or assurance is invalid",
                )
            )
    elif raw["dispatch_mode"] == "external-named-task":
        external_values = (
            raw["external_task_id"],
            raw["external_task_url"],
            raw["external_task_ref"],
        )
        runtime_identity = any(value != "unavailable" for value in external_values[:2])
        if (
            raw["spawn_agent_type"] != "unavailable"
            or raw["spawn_fork_turns"] != "unavailable"
            or raw["spawn_result_task_name"] != "unavailable"
            or raw["reviewer_selection_attested"] is not True
            or raw["task_name"] == controller
            or raw["external_task_request"] == "unavailable"
            or any(
                value != "unavailable" and value == controller
                for value in external_values
            )
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-MALFORMED-ENVELOPE",
                    invocation_path,
                    invocation_id,
                    "external reviewer identity or assurance is invalid",
                )
            )
        ref = str(raw["external_task_ref"])
        if runtime_identity:
            if assurance != "external-named-task" or ref != "unavailable":
                errors.append(
                    _e(
                        "TWV-REVIEW-MALFORMED-ENVELOPE",
                        invocation_path,
                        invocation_id,
                        "runtime external identity may not use a fallback reference",
                    )
                )
        elif (
            assurance != "user-attested-external-reference"
            or ref == "unavailable"
            or EXTERNAL_TASK_REF_RE.fullmatch(ref) is None
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-MALFORMED-ENVELOPE",
                    invocation_path,
                    invocation_id,
                    "fallback external identity or reference grammar is invalid",
                )
            )
        elif not _has_exact_line(
            raw["external_task_request"], "external_task_ref", ref
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-REFERENCE-MISMATCH",
                    invocation_path,
                    invocation_id,
                    "external task request must contain the exact reference line once",
                )
            )
    else:
        errors.append(
            _e(
                "TWV-REVIEW-MALFORMED-ENVELOPE",
                invocation_path,
                invocation_id,
                "dispatch mode is unsupported",
            )
        )
    return errors


def _validate_result(
    raw: dict[str, object],
    task_dir: Path,
    invocation_path: Path,
    invocation_id: str,
    external_task_ref: str | None,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    result_path = _contained(task_dir, str(raw["produced_result_path"]))
    if result_path is None:
        return errors + [
            _e(
                "TWV-REF-ARTIFACT",
                invocation_path,
                invocation_id,
                "result path escapes the task directory",
            )
        ]
    if not result_path.is_file():
        return errors + [
            _e(
                "TWV-REVIEW-MISSING-RESULT",
                invocation_path,
                invocation_id,
                "referenced result is missing",
            )
        ]
    result_bytes = result_path.read_bytes()
    try:
        text = result_bytes.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(
            _e(
                "TWV-REVIEW-RESULT-ENCODING",
                result_path,
                invocation_id,
                "result must be UTF-8",
            )
        )
        return errors
    result_sha256 = raw["result_sha256"]
    if not isinstance(result_sha256, str) or SHA256_RE.fullmatch(result_sha256) is None:
        errors.append(
            _e(
                "TWV-REVIEW-INVALID-DIGEST",
                invocation_path,
                invocation_id,
                "result_sha256 must be 64 lowercase hexadecimal characters",
            )
        )
    elif hashlib.sha256(result_bytes).hexdigest() != result_sha256:
        errors.append(
            _e(
                "TWV-REVIEW-STALE-EVIDENCE",
                invocation_path,
                invocation_id,
                "result digest does not match exact referenced bytes",
            )
        )
    if not _has_exact_line(text, "invocation_id", invocation_id):
        errors.append(
            _e(
                "TWV-REVIEW-MALFORMED-ENVELOPE",
                result_path,
                invocation_id,
                "result must contain the exact invocation ID line once",
            )
        )
    if external_task_ref is not None and not _has_exact_line(
        text, "external_task_ref", external_task_ref
    ):
        errors.append(
            _e(
                "TWV-REVIEW-REFERENCE-MISMATCH",
                result_path,
                invocation_id,
                "result must contain the exact external task reference line once",
            )
        )
    return errors


def _validate_invocation(
    raw: dict[str, object],
    node: Node,
    manifest: Manifest,
    state: State,
    task_dir: Path,
    invocation_path: Path,
) -> tuple[list[ValidationError], bool]:
    errors: list[ValidationError] = []
    invocation_id = str(raw["invocation_id"])
    lifecycle = raw["lifecycle_status"]
    node_result_path = node.paths[2] if len(node.paths) > 2 else ""
    if lifecycle not in LIFECYCLE_STATUSES:
        errors.append(
            _e(
                "TWV-REVIEW-MALFORMED-ENVELOPE",
                invocation_path,
                invocation_id,
                "lifecycle_status has an invalid value",
            )
        )
    if (
        raw["mode"] != node.kind
        or raw["requested_role"] != "reviewer"
        or not _valid_reviewer_profiles(raw, lifecycle)
        or raw["base_revision"] != manifest.base_revision
        or raw["result_encoding"] != "utf-8"
    ):
        errors.append(
            _e(
                "TWV-REVIEW-MALFORMED-ENVELOPE",
                invocation_path,
                invocation_id,
                "mode, reviewer request, base revision, or encoding is invalid",
            )
        )
    expected_result_path = _contained(task_dir, str(raw["expected_result_path"]))
    if expected_result_path is None:
        errors.append(
            _e(
                "TWV-REF-ARTIFACT",
                invocation_path,
                invocation_id,
                "expected result path escapes the task directory",
            )
        )
    if raw["expected_result_path"] != node_result_path or (
        lifecycle == "completed" and raw["produced_result_path"] != node_result_path
    ):
        errors.append(
            _e(
                "TWV-REVIEW-RESULT-PATH-MISMATCH",
                invocation_path,
                invocation_id,
                "invocation result paths must bind to the graph node report path",
            )
        )
    errors.extend(_validate_dispatch(raw, invocation_path, invocation_id, lifecycle))
    errors.extend(
        _validate_state_payload(
            raw["working_tree_state"],
            raw["reviewed_revision"],
            invocation_path,
            invocation_id,
            "working_tree_state",
        )
    )
    if raw["pre_dispatch_state_digest"] != _digest(str(raw["working_tree_state"])):
        errors.append(
            _e(
                "TWV-REVIEW-INVALID-DIGEST",
                invocation_path,
                invocation_id,
                "pre_dispatch_state_digest does not hash working_tree_state",
            )
        )

    mode_decisions = {
        "review": {"approve", "do-not-approve"},
        "final": {"ready", "not-ready"},
    }
    if lifecycle == "completed":
        decision = raw["returned_decision"]
        if decision not in mode_decisions.get(str(raw["mode"]), set()):
            errors.append(
                _e(
                    "TWV-REVIEW-MALFORMED-ENVELOPE",
                    invocation_path,
                    invocation_id,
                    "returned_decision is invalid for the invocation mode",
                )
            )
        if (
            raw["returned_role"] != "reviewer"
            or raw["returned_target"] != raw["target"]
            or raw["returned_revision"] != raw["reviewed_revision"]
            or raw["returned_working_tree_state"] != raw["working_tree_state"]
            or any(raw[field] == "unavailable" for field in RESULT_FIELDS)
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-MALFORMED-ENVELOPE",
                    invocation_path,
                    invocation_id,
                    "completed invocation has invalid or unavailable returned fields",
                )
            )
        errors.extend(
            _validate_state_payload(
                raw["post_review_working_tree_state"],
                raw["reviewed_revision"],
                invocation_path,
                invocation_id,
                "post_review_working_tree_state",
            )
        )
        if raw["post_review_state_digest"] != _digest(
            str(raw["post_review_working_tree_state"])
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-INVALID-DIGEST",
                    invocation_path,
                    invocation_id,
                    "post_review_state_digest does not hash post-review state",
                )
            )
        if raw["post_review_working_tree_state"] != raw["working_tree_state"]:
            errors.append(
                _e(
                    "TWV-REVIEW-STALE-EVIDENCE",
                    invocation_path,
                    invocation_id,
                    "pre-dispatch and post-review Git states differ",
                )
            )
        external_task_ref = (
            str(raw["external_task_ref"])
            if raw["identity_assurance"] == "user-attested-external-reference"
            else None
        )
        errors.extend(
            _validate_result(
                raw,
                task_dir,
                invocation_path,
                invocation_id,
                external_task_ref,
            )
        )
    elif lifecycle in LIFECYCLE_STATUSES:
        if any(raw[field] != "unavailable" for field in RESULT_FIELDS):
            errors.append(
                _e(
                    "TWV-REVIEW-MALFORMED-ENVELOPE",
                    invocation_path,
                    invocation_id,
                    "non-completed invocation result fields must be unavailable",
                )
            )

    positive = {"review": "approve", "final": "ready"}
    negative = {"review": "do-not-approve", "final": "not-ready"}
    expected_node_status = None
    if lifecycle == "completed":
        if raw["returned_decision"] == positive.get(node.kind):
            expected_node_status = "complete"
        elif raw["returned_decision"] == negative.get(node.kind):
            expected_node_status = "failed"
    elif lifecycle in {"blocked", "failed"}:
        expected_node_status = lifecycle
    elif lifecycle in {"planned", "dispatched"}:
        expected_node_status = "reviewing"
    if expected_node_status is not None and node.status != expected_node_status:
        errors.append(
            _e(
                "TWV-REVIEW-LIFECYCLE-MISMATCH",
                invocation_path,
                invocation_id,
                "invocation lifecycle/decision does not map to graph node status",
            )
        )
    if lifecycle == "dispatched":
        errors.append(
            _e(
                "TWV-REVIEW-UNRESOLVED-DISPATCH",
                invocation_path,
                invocation_id,
                "dispatched reviewer evidence cannot satisfy validation",
            )
        )

    returned_positive = lifecycle == "completed" and raw[
        "returned_decision"
    ] == positive.get(node.kind)
    is_positive = node.status == "complete" and returned_positive
    if returned_positive and (
        raw["reviewed_revision"] != state.current_revision
        or raw["returned_revision"] != state.current_revision
    ):
        errors.append(
            _e(
                "TWV-REVIEW-STALE-EVIDENCE",
                invocation_path,
                invocation_id,
                "approving evidence is stale for current revision",
            )
        )
    return errors, is_positive


def validate_review_evidence(
    manifest: Manifest, state: State, task_dir: Path
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if manifest.version == 1 and not manifest.nodes:
        return errors
    reviews: list[Node] = []
    finals: list[Node] = []
    evidence: list[tuple[Node, Path, dict[str, object], list[ValidationError]]] = []
    completed_approvals: dict[str, tuple[Node, Path, dict[str, object]]] = {}
    for node in manifest.nodes:
        if node.kind == "review":
            if not node.review_scope or not node.review_scope.get("terminal_node_ids"):
                errors.append(
                    _e(
                        "TWV-REVIEW-MISSING-SCOPE",
                        Path(manifest.path),
                        node.id,
                        "review node requires a non-empty review_scope",
                    )
                )
            elif tuple(node.review_scope["terminal_node_ids"]) != tuple(
                sorted(set(node.review_scope["terminal_node_ids"]))
            ):
                errors.append(
                    _e(
                        "TWV-REVIEW-INVALID-SCOPE",
                        Path(manifest.path),
                        node.id,
                        "terminal node IDs must be sorted and unique",
                    )
                )
            elif tuple(node.review_scope["terminal_node_ids"]) != tuple(
                node.depends_on
            ):
                errors.append(
                    _e(
                        "TWV-REVIEW-INVALID-SCOPE",
                        Path(manifest.path),
                        node.id,
                        "depends_on must exactly match review scope terminals",
                    )
                )
            reviews.append(node)
        if node.kind == "final":
            finals.append(node)
        if node.kind not in {"review", "final"} or node.status in {
            "pending",
            "ready",
            "cancelled",
        }:
            continue
        if (
            node.raw.get("executor_class") != "reviewer"
            or node.raw.get("model_tier") != "high"
            or node.raw.get("batching") != "off"
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-INVALID-REVIEWER-NODE",
                    Path(manifest.path),
                    node.id,
                    "review and final nodes require reviewer/high/off",
                )
            )
        invocation_ref = next((p for p in node.paths if p.endswith(".toml")), "")
        invocation_path = _contained(task_dir, invocation_ref)
        if invocation_path is None:
            errors.append(
                _e(
                    "TWV-REF-ARTIFACT",
                    task_dir / invocation_ref,
                    node.id,
                    "invocation path escapes the task directory",
                )
            )
            continue
        raw, found = _load(invocation_path)
        if raw is None:
            errors.extend(found)
            continue
        evidence.append((node, invocation_path, raw, found))

    review_and_final_nodes = reviews + finals
    errors.extend(
        _validate_node_result_paths(
            review_and_final_nodes, task_dir, Path(manifest.path)
        )
    )
    errors.extend(_duplicate_identity_errors(evidence))

    for node, invocation_path, raw, found in evidence:
        legacy_schema_codes = {
            "TWV-SCHEMA-MISSING-FIELD",
            "TWV-SCHEMA-UNKNOWN-FIELD",
        }
        if (
            node.status == "failed"
            and found
            and _has_reservable_invocation_id(raw)
            and all(error.code in legacy_schema_codes for error in found)
        ):
            # Historical non-approving evidence remains preserved but cannot
            # enter completed_approvals or satisfy a current review/final gate.
            continue
        if found:
            errors.extend(found)
            continue
        invocation_id = str(raw["invocation_id"])
        found, is_positive = _validate_invocation(
            raw, node, manifest, state, task_dir, invocation_path
        )
        errors.extend(found)
        if node.kind == "review" and is_positive:
            completed_approvals[invocation_id] = (node, invocation_path, raw)

    if not reviews:
        errors.append(
            _e(
                "TWV-REVIEW-MISSING-REVIEW",
                Path(manifest.path),
                "review",
                "a durable graph requires a review node",
            )
        )
    if not finals:
        errors.append(
            _e(
                "TWV-REVIEW-MISSING-FINAL",
                Path(manifest.path),
                "final",
                "a later final node is required",
            )
        )
    state_review = completed_approvals.get(
        state.raw.get("latest_approving_invocation_id")
    )
    current_approval_chain = (
        state_review is not None
        and state_review[2].get("produced_result_path")
        == state.raw.get("latest_approving_review_path")
        and any(
            final.status == "complete"
            and state_review[0].id in final.depends_on
            and state_review[0].sequence < final.sequence
            for final in finals
        )
    )
    if state.workflow_status == "complete" and not current_approval_chain:
        errors.append(
            _e(
                "TWV-REVIEW-COMPLETED-WITHOUT-GATES",
                task_dir / "03-state.toml",
                "workflow_status",
                "completed workflows require completed review and final gates",
            )
        )
    for final in finals:
        if not any(
            review.id in final.depends_on and review.sequence < final.sequence
            for review in reviews
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-ORDERING",
                    Path(manifest.path),
                    final.id,
                    "final must depend on a review node",
                )
            )
        if final.status == "complete" and not any(
            review.id in final.depends_on
            and any(record[0] == review for record in completed_approvals.values())
            for review in reviews
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-ORDERING",
                    Path(manifest.path),
                    final.id,
                    "completed final requires a completed approving review",
                )
            )
        if final.status == "complete" and (
            state_review is None
            or state_review[0].id not in final.depends_on
            or state_review[2].get("produced_result_path")
            != state.raw.get("latest_approving_review_path")
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-FINAL-APPROVAL-MISMATCH",
                    Path(manifest.path),
                    final.id,
                    "completed final must depend on the state-bound approving review",
                )
            )
    approval_path = state.raw.get("latest_approving_review_path")
    approval_id = state.raw.get("latest_approving_invocation_id")
    if approval_path != "unavailable" or approval_id != "unavailable":
        record = completed_approvals.get(approval_id)
        if (
            record is None
            or record[2].get("produced_result_path") != approval_path
            or not _contained(task_dir, str(approval_path))
        ):
            errors.append(
                _e(
                    "TWV-REVIEW-INVALID-LATEST-APPROVAL",
                    task_dir / "03-state.toml",
                    "latest_approving_review",
                    "state approval pointers must bind a current completed approving review",
                )
            )
    return errors
