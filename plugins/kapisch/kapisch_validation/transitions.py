from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .artifact_io import load_toml_artifact
from .delegations import ROUTE_FILE, parse_route
from .errors import ValidationError
from .models import Manifest, State
from .vocabulary import (
    TERMINAL_NEXT_ACTIONS,
    TERMINAL_WORKFLOW_STATUSES,
    WORKFLOW_STATUS_TRANSITIONS,
)

ALLOWED = {
    "pending": {"ready", "cancelled"},
    "ready": {"running", "cancelled"},
    "running": {"implemented", "blocked", "failed"},
    "implemented": {"reviewing"},
    "reviewing": {"complete", "blocked", "failed"},
    "complete": set(),
    "blocked": set(),
    "failed": set(),
    "cancelled": set(),
}
BLOCK_ACTIONS = {
    "block:active-node-conflict",
    "block:missing-review-final",
    "block:no-ready-node",
}
IMMUTABLE_NODE_FIELDS = (
    "sequence",
    "title",
    "kind",
    "risk",
    "depends_on",
    "brief",
    "context",
    "report",
    "reviewer_invocation",
    "reads",
    "writes",
    "shared_resources",
    "verification",
    "context_refs",
    "executor_class",
    "model_tier",
    "batching",
    "review_scope",
    "delegation_ids",
    "extensions",
)
LIST_NODE_FIELDS = frozenset(
    {
        "reads",
        "writes",
        "shared_resources",
        "verification",
        "context_refs",
        "delegation_ids",
    }
)
NODE_PATH_INDEX = {
    "brief": 0,
    "context": 1,
    "report": 2,
    "reviewer_invocation": 3,
}
TERMINAL_NODE_STATUSES = frozenset(
    status for status, allowed in ALLOWED.items() if not allowed
)
TERMINAL_NODE_BINDING_FIELDS = (
    "revision",
    "assignment",
    "batch",
    "verification_evidence",
    "blocker",
)
TERMINAL_STATE_BINDING_FIELDS = (
    "current_revision",
    "latest_approving_review_path",
    "latest_approving_invocation_id",
    "current_fix_round",
    "max_fix_rounds",
)
RUNTIME_BINDING_FIELDS = (
    "revision",
    "assignment",
    "batch",
    "verification_evidence",
    "blocker",
)
RUNTIME_STATUS_TRANSITIONS = {
    "pending": frozenset({"pending", "running", "complete", "blocked", "failed"}),
    "running": frozenset({"running", "complete", "blocked", "failed"}),
    "complete": frozenset({"complete"}),
    "blocked": frozenset({"blocked"}),
    "failed": frozenset({"failed"}),
    "cancelled": frozenset({"cancelled"}),
}


def determine_next_action(manifest: Manifest, state: State) -> str:
    if manifest.version == 1 and not manifest.nodes:
        return "complete"
    nodes_by_id = {node.id: node for node in manifest.nodes}
    active = [
        n.id
        for n in manifest.nodes
        if n.status in {"running", "implemented", "reviewing"}
    ]
    if len(active) > 1:
        return "block:active-node-conflict"
    if active:
        return "resolve:" + active[0]
    ready = [
        n
        for n in manifest.nodes
        if n.status == "ready"
        and all(
            dependency in nodes_by_id and nodes_by_id[dependency].status == "complete"
            for dependency in n.depends_on
        )
    ]
    if ready:
        return "select:" + min(ready, key=lambda n: (n.sequence, n.id)).id
    reviews = [node for node in manifest.nodes if node.kind == "review"]
    finals = [node for node in manifest.nodes if node.kind == "final"]
    completed_gate = any(
        review.status == "complete"
        and final.status == "complete"
        and review.id in final.depends_on
        and review.sequence < final.sequence
        for review in reviews
        for final in finals
    )
    if not completed_gate:
        return "block:missing-review-final"
    if all(
        node.status in {"complete", "cancelled"}
        or (node.kind in {"review", "final"} and node.status in {"blocked", "failed"})
        for node in manifest.nodes
    ):
        return "complete"
    return "block:no-ready-node"


def validate_lifecycle(
    manifest: Manifest,
    state: State,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    node_ids = {node.id for node in manifest.nodes}
    action = state.next_action
    if action not in BLOCK_ACTIONS and action != "complete":
        prefix, separator, node_id = action.partition(":")
        if (
            prefix not in {"select", "resolve", "resume"}
            or not separator
            or node_id not in node_ids
        ):
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INVALID-NEXT-ACTION",
                    state.path or manifest.path,
                    "next_action",
                    "next_action must use a documented action token and known node ID",
                )
            )
    status_is_terminal = state.workflow_status in TERMINAL_WORKFLOW_STATUSES
    action_is_terminal = state.next_action in TERMINAL_NEXT_ACTIONS
    if status_is_terminal != action_is_terminal:
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-WORKFLOW-STATUS",
                state.path or manifest.path,
                "workflow_status",
                f"workflow_status={state.workflow_status!r} and "
                f"next_action={state.next_action!r} disagree; 'complete' is "
                "required on both or neither",
            )
        )
    for node in manifest.nodes:
        if node.status not in ALLOWED:
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INVALID-STATUS",
                    manifest.path,
                    node.id,
                    "unknown lifecycle status",
                )
            )
    nodes_by_id = {node.id: node for node in manifest.nodes}
    for node in manifest.nodes:
        if node.status not in {
            "ready",
            "running",
            "implemented",
            "reviewing",
            "complete",
        }:
            continue
        for dependency_id in node.depends_on:
            dependency = nodes_by_id.get(dependency_id)
            if dependency is not None and dependency.status != "complete":
                errors.append(
                    ValidationError(
                        "TWV-LIFECYCLE-INCOMPLETE-DEPENDENCY",
                        manifest.path,
                        f"{node.id}->{dependency_id}",
                        "active or completed nodes require completed dependencies",
                    )
                )
    expected = determine_next_action(manifest, state)
    if state.next_action != expected:
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-NEXT-ACTION",
                manifest.path,
                "next_action",
                f"expected {expected}",
            )
        )
    return errors


def validate_snapshot_compatibility(
    manifest: Manifest,
    state: State,
    previous: Manifest,
    previous_state: State,
    task_dir: Path | None = None,
    previous_task_dir: Path | None = None,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    identities = (
        ("version", manifest.version, previous.version),
        ("task_id", manifest.task_id, previous.task_id),
        ("base_revision", manifest.base_revision, previous.base_revision),
        ("source_plan", manifest.source_plan, previous.source_plan),
        ("roadmap_item", manifest.roadmap_item, previous.roadmap_item),
        ("policies", manifest.policies, previous.policies),
    )
    for reference, current, prior in identities:
        if not _semantic_equal(current, prior):
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                    manifest.path,
                    reference,
                    f"current {reference}={current!r} does not match "
                    f"previous {reference}={prior!r}",
                )
            )
    if errors:
        return errors

    current_nodes = {node.id: node for node in manifest.nodes}
    for previous_node in previous.nodes:
        current_node = current_nodes.get(previous_node.id)
        if current_node is None:
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                    manifest.path,
                    f"nodes[{previous_node.id}]",
                    "previously persisted node is missing from current snapshot",
                )
            )
            continue
        for field in IMMUTABLE_NODE_FIELDS:
            current_value = _normalized_node_field(current_node, field)
            previous_value = _normalized_node_field(previous_node, field)
            if _semantic_equal(current_value, previous_value):
                continue
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                    manifest.path,
                    f"nodes[{previous_node.id}].{field}",
                    f"current value {current_value!r} does not match "
                    f"previous value {previous_value!r}",
                )
            )
        if previous_node.status in TERMINAL_NODE_STATUSES:
            for field in TERMINAL_NODE_BINDING_FIELDS:
                current_value = current_node.raw.get(field)
                previous_value = previous_node.raw.get(field)
                if _semantic_equal(current_value, previous_value):
                    continue
                errors.append(
                    ValidationError(
                        "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                        manifest.path,
                        f"nodes[{previous_node.id}].{field}",
                        f"terminal node binding changed from {previous_value!r} "
                        f"to {current_value!r}",
                    )
                )
        else:
            errors.extend(
                _validate_nonterminal_runtime_bindings(
                    manifest, previous_node.id, current_node.raw, previous_node.raw
                )
            )

    previous_ids = {node.id for node in previous.nodes}
    for node in manifest.nodes:
        if node.id in previous_ids:
            continue
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                manifest.path,
                f"nodes[{node.id}]",
                "new nodes require a versioned graph-amendment protocol",
            )
        )

    if state.raw.get("current_fix_round", 0) < previous_state.raw.get(
        "current_fix_round", 0
    ):
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                state.path or manifest.path,
                "current_fix_round",
                "current fix round cannot decrease across persisted snapshots",
            )
        )

    if previous_state.workflow_status == "complete":
        for field in TERMINAL_STATE_BINDING_FIELDS:
            current_value = state.raw.get(field)
            previous_value = previous_state.raw.get(field)
            if _semantic_equal(current_value, previous_value):
                continue
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                    state.path or manifest.path,
                    field,
                    f"completed workflow binding changed from {previous_value!r} "
                    f"to {current_value!r}",
                )
            )
    if task_dir is not None and previous_task_dir is not None:
        errors.extend(
            _validate_artifact_compatibility(
                manifest, previous, task_dir, previous_task_dir
            )
        )
        if manifest.version == 3 or previous.version == 3:
            errors.extend(_validate_route_compatibility(task_dir, previous_task_dir))
    return errors


def _semantic_value(value: object) -> object:
    if value is None or isinstance(value, (str, bytes, bool, int)):
        return (type(value).__name__, value)
    if isinstance(value, float):
        if math.isnan(value):
            return ("float", "nan")
        if math.isinf(value):
            return ("float", "infinity" if value > 0 else "-infinity")
        return ("float", value)
    if isinstance(value, list):
        return ("list", tuple(_semantic_value(item) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_semantic_value(item) for item in value))
    if isinstance(value, dict):
        return (
            "dict",
            tuple(
                (str(key), _semantic_value(item))
                for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            ),
        )
    return (type(value).__name__, repr(value))


def _semantic_equal(current: object, previous: object) -> bool:
    return _semantic_value(current) == _semantic_value(previous)


def _runtime_error(manifest: Manifest, node_id: str, field: str, message: str) -> ValidationError:
    return ValidationError(
        "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
        manifest.path,
        f"nodes[{node_id}].{field}",
        message,
    )


def _records_by_id(value: object) -> dict[str, dict[str, object]] | None:
    if not isinstance(value, list):
        return None
    records: dict[str, dict[str, object]] = {}
    for record in value:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            return None
        if record["id"] in records:
            return None
        records[record["id"]] = record
    return records


def _validate_append_only_records(
    manifest: Manifest,
    node_id: str,
    field: str,
    current: object,
    previous: object,
    *,
    mutable_fields: frozenset[str] = frozenset(),
) -> list[ValidationError]:
    if previous is None:
        return []
    current_records = _records_by_id(current)
    previous_records = _records_by_id(previous)
    if current_records is None or previous_records is None:
        return [_runtime_error(manifest, node_id, field, "runtime record shape changed")]
    errors: list[ValidationError] = []
    if not _is_record_prefix(current, previous):
        errors.append(
            _runtime_error(manifest, node_id, field, "persisted runtime record chronology changed")
        )
    for record_id, previous_record in previous_records.items():
        current_record = current_records.get(record_id)
        if current_record is None:
            errors.append(
                _runtime_error(
                    manifest, node_id, field, "persisted runtime record is missing"
                )
            )
            continue
        for key, previous_value in previous_record.items():
            if key in mutable_fields:
                continue
            if _semantic_equal(current_record.get(key), previous_value):
                continue
            errors.append(
                _runtime_error(
                    manifest,
                    node_id,
                    field,
                    "persisted runtime record was replaced or rebound",
                )
            )
            break
        if set(current_record) != set(previous_record):
            errors.append(
                _runtime_error(manifest, node_id, field, "persisted runtime record shape changed")
            )
    return errors


def _is_prefix(current: object, previous: object) -> bool:
    return (
        isinstance(current, list)
        and isinstance(previous, list)
        and len(current) >= len(previous)
        and all(_semantic_equal(new, old) for new, old in zip(current, previous))
    )


def _is_record_prefix(current: object, previous: object) -> bool:
    return (
        isinstance(current, list)
        and isinstance(previous, list)
        and len(current) >= len(previous)
        and all(
            isinstance(new, dict)
            and isinstance(old, dict)
            and new.get("id") == old.get("id")
            for new, old in zip(current, previous)
        )
    )


def _monotonic_status(current: object, previous: object) -> bool:
    return isinstance(current, str) and current in RUNTIME_STATUS_TRANSITIONS.get(
        previous, frozenset()
    )


def _validate_attempt_advancement(
    manifest: Manifest,
    node_id: str,
    current: dict[str, object],
    previous: dict[str, object],
) -> list[ValidationError]:
    if not _monotonic_status(current.get("status"), previous.get("status")):
        return [
            _runtime_error(
                manifest,
                node_id,
                "assignment.attempts",
                "persisted attempt status cannot regress",
            )
        ]
    if not _is_prefix(current.get("verification"), previous.get("verification")):
        return [
            _runtime_error(
                manifest,
                node_id,
                "assignment.attempts",
                "persisted attempt verification cannot be removed or rewritten",
            )
        ]
    if (
        previous.get("status") in {"complete", "blocked", "failed"}
        and not _semantic_equal(current.get("outcome_path"), previous.get("outcome_path"))
    ):
        return [
            _runtime_error(
                manifest,
                node_id,
                "assignment.attempts",
                "terminal attempt outcome path is immutable",
            )
        ]
    return []


def _validate_batch_advancement(
    manifest: Manifest,
    node_id: str,
    current: object,
    previous: object,
) -> list[ValidationError]:
    if previous is None:
        return []
    if not isinstance(current, dict) or not isinstance(previous, dict):
        return [_runtime_error(manifest, node_id, "batch", "persisted batch is missing")]
    if current.get("id") != previous.get("id"):
        return [_runtime_error(manifest, node_id, "batch", "batch identity changed")]
    errors: list[ValidationError] = []
    for field in ("member_node_ids", "member_assignment_ids"):
        if _semantic_equal(current.get(field), previous.get(field)):
            continue
        errors.append(
            _runtime_error(manifest, node_id, "batch", "batch membership changed")
        )
    previous_outcomes = previous.get("member_outcomes")
    current_outcomes = current.get("member_outcomes")
    if not isinstance(previous_outcomes, list) or not isinstance(current_outcomes, list):
        errors.append(_runtime_error(manifest, node_id, "batch", "batch outcomes changed shape"))
    elif len(current_outcomes) != len(previous_outcomes) or any(
        not _monotonic_status(new, old)
        for new, old in zip(current_outcomes, previous_outcomes)
    ):
        errors.append(_runtime_error(manifest, node_id, "batch", "batch member outcome cannot regress"))
    if not _monotonic_status(current.get("outcome"), previous.get("outcome")):
        errors.append(_runtime_error(manifest, node_id, "batch", "batch composite outcome cannot regress"))
    return errors


def _validate_nonterminal_runtime_bindings(
    manifest: Manifest,
    node_id: str,
    current: dict[str, object],
    previous: dict[str, object],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    previous_assignment = previous.get("assignment")
    current_assignment = current.get("assignment")
    if previous_assignment is not None:
        if not isinstance(previous_assignment, dict) or not isinstance(current_assignment, dict):
            errors.append(
                _runtime_error(manifest, node_id, "assignment", "persisted assignment is missing")
            )
        elif current_assignment.get("id") != previous_assignment.get("id"):
            errors.append(
                _runtime_error(manifest, node_id, "assignment", "assignment identity changed")
            )
        else:
            if set(current_assignment) != set(previous_assignment):
                errors.append(
                    _runtime_error(
                        manifest,
                        node_id,
                        "assignment",
                        "persisted assignment shape changed",
                    )
                )
            for key, previous_value in previous_assignment.items():
                if key in {"attempts", "escalations"}:
                    continue
                if _semantic_equal(current_assignment.get(key), previous_value):
                    continue
                errors.append(
                    _runtime_error(
                        manifest, node_id, "assignment", "persisted assignment was replaced or rebound"
                    )
                )
                break
            errors.extend(
                _validate_append_only_records(
                    manifest,
                    node_id,
                    "assignment.attempts",
                    current_assignment.get("attempts", []),
                    previous_assignment.get("attempts", []),
                    mutable_fields=frozenset({"status", "verification", "outcome_path"}),
                )
            )
            current_attempts = _records_by_id(current_assignment.get("attempts", []))
            previous_attempts = _records_by_id(previous_assignment.get("attempts", []))
            if current_attempts is not None and previous_attempts is not None:
                for attempt_id, previous_attempt in previous_attempts.items():
                    current_attempt = current_attempts.get(attempt_id)
                    if current_attempt is not None:
                        errors.extend(
                            _validate_attempt_advancement(
                                manifest, node_id, current_attempt, previous_attempt
                            )
                        )
            errors.extend(
                _validate_append_only_records(
                    manifest,
                    node_id,
                    "assignment.escalations",
                    current_assignment.get("escalations", []),
                    previous_assignment.get("escalations", []),
                )
            )
    for field in ("verification_evidence",):
        errors.extend(
            _validate_append_only_records(
                manifest, node_id, field, current.get(field, []), previous.get(field, [])
            )
        )
    errors.extend(
        _validate_batch_advancement(
            manifest, node_id, current.get("batch"), previous.get("batch")
        )
    )
    for field in ("revision", "blocker"):
        previous_value = previous.get(field)
        if previous_value is None or _semantic_equal(current.get(field), previous_value):
            continue
        errors.append(
            _runtime_error(
                manifest, node_id, field, "persisted runtime binding was replaced or removed"
            )
        )
    return errors


def _artifact_digest(task_dir: Path, relative_path: str) -> str | None:
    if not relative_path:
        return None
    try:
        return hashlib.sha256((task_dir / relative_path).read_bytes()).hexdigest()
    except OSError:
        return None


def _artifact_error(manifest: Manifest, reference: str, message: str) -> ValidationError:
    return ValidationError(
        "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT", manifest.path, reference, message
    )


def _validate_artifact_compatibility(
    manifest: Manifest,
    previous: Manifest,
    task_dir: Path,
    previous_task_dir: Path,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    current_nodes = {node.id: node for node in manifest.nodes}
    for previous_node in previous.nodes:
        current_node = current_nodes.get(previous_node.id)
        if current_node is None:
            continue
        if previous_node.status in TERMINAL_NODE_STATUSES:
            for field, index in (("report", 2), ("reviewer_invocation", 3)):
                previous_path = previous_node.paths[index]
                current_path = current_node.paths[index]
                if not previous_path:
                    continue
                if field == "reviewer_invocation":
                    unchanged = _semantic_equal(
                        _toml_value(task_dir / current_path),
                        _toml_value(previous_task_dir / previous_path),
                    )
                else:
                    unchanged = _artifact_digest(task_dir, current_path) == _artifact_digest(
                        previous_task_dir, previous_path
                    )
                if not unchanged:
                    errors.append(
                        _artifact_error(
                            manifest,
                            f"nodes[{previous_node.id}].{field}",
                            "terminal artifact content does not match the persisted snapshot",
                        )
                    )
        previous_assignment = previous_node.raw.get("assignment")
        current_assignment = current_node.raw.get("assignment")
        if not isinstance(previous_assignment, dict) or not isinstance(current_assignment, dict):
            continue
        previous_attempts = _records_by_id(previous_assignment.get("attempts", []))
        current_attempts = _records_by_id(current_assignment.get("attempts", []))
        if previous_attempts is None or current_attempts is None:
            continue
        for attempt_id, previous_attempt in previous_attempts.items():
            if previous_attempt.get("status") not in {"complete", "blocked", "failed"}:
                continue
            current_attempt = current_attempts.get(attempt_id)
            previous_path = previous_attempt.get("outcome_path")
            current_path = current_attempt.get("outcome_path") if current_attempt else None
            if (
                not isinstance(previous_path, str)
                or previous_path != current_path
                or task_dir is None
                or previous_task_dir is None
                or _artifact_digest(task_dir, current_path) != _artifact_digest(previous_task_dir, previous_path)
            ):
                errors.append(
                    _artifact_error(
                        manifest,
                        f"nodes[{previous_node.id}].attempts[{attempt_id}].outcome_path",
                        "terminal outcome content does not match the persisted snapshot",
                    )
                )
    return errors


def _toml_value(path: Path) -> dict[str, object] | None:
    value, failure = load_toml_artifact(path)
    return value if failure is None else None


def _validate_route_compatibility(
    task_dir: Path, previous_task_dir: Path
) -> list[ValidationError]:
    current_path = task_dir / ROUTE_FILE
    previous_path = previous_task_dir / ROUTE_FILE
    if not current_path.is_file() and not previous_path.is_file():
        return []
    current, _ = parse_route(task_dir)
    previous, _ = parse_route(previous_task_dir)
    if current is None or previous is None:
        return [
            ValidationError(
                "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                str(current_path),
                "delegations",
                "delegation route presence does not match the persisted snapshot",
            )
        ]
    errors: list[ValidationError] = []
    for field in ("version", "task_id", "route_id", "source_revision", "extensions"):
        if _semantic_equal(current.get(field), previous.get(field)):
            continue
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                str(current_path),
                f"delegations.{field}",
                "delegation route value does not match the persisted snapshot",
            )
        )
    current_steps = {
        step.get("id"): step
        for step in current.get("steps", [])
        if isinstance(step, dict) and isinstance(step.get("id"), str)
    }
    for previous_step in previous.get("steps", []):
        if not isinstance(previous_step, dict):
            continue
        step_id = previous_step.get("id")
        if not isinstance(step_id, str):
            continue
        current_step = current_steps.get(step_id)
        if current_step is None:
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                    str(current_path),
                    f"delegations.steps[{step_id}]",
                    "persisted delegation step is missing",
                )
            )
            continue
        if _semantic_equal(current_step, previous_step):
            continue
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                str(current_path),
                f"delegations.steps[{step_id}]",
                "delegation step does not match the persisted snapshot",
            )
        )
    if len(current_steps) != len(previous.get("steps", [])):
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT",
                str(current_path),
                "delegations.steps",
                "new delegation steps require a versioned graph-amendment protocol",
            )
        )
    return errors


def _normalized_node_field(node, field: str) -> object:
    if field == "depends_on":
        return tuple(sorted(node.depends_on))
    if field in NODE_PATH_INDEX:
        return node.paths[NODE_PATH_INDEX[field]]
    if field == "review_scope":
        return node.review_scope or {}
    if field in LIST_NODE_FIELDS:
        value = node.raw.get(field, ())
        return tuple(value) if isinstance(value, list) else value
    return node.raw.get(field)


def validate_transition(
    manifest: Manifest,
    state: State,
    previous: Manifest,
    previous_state: State,
    task_dir: Path | None = None,
    previous_task_dir: Path | None = None,
) -> list[ValidationError]:
    errors = validate_snapshot_compatibility(
        manifest, state, previous, previous_state, task_dir, previous_task_dir
    )
    if errors:
        return errors
    allowed_statuses = WORKFLOW_STATUS_TRANSITIONS.get(
        previous_state.workflow_status, frozenset()
    )
    if state.workflow_status not in allowed_statuses:
        errors.append(
            ValidationError(
                "TWV-LIFECYCLE-ILLEGAL-WORKFLOW-TRANSITION",
                state.path or manifest.path,
                "workflow_status",
                f"{previous_state.workflow_status!r} cannot transition to "
                f"{state.workflow_status!r}",
            )
        )
    old = {node.id: node for node in previous.nodes}
    for node in manifest.nodes:
        if (
            node.id in old
            and node.status != old[node.id].status
            and node.status not in ALLOWED.get(old[node.id].status, set())
        ):
            errors.append(
                ValidationError(
                    "TWV-LIFECYCLE-ILLEGAL-TRANSITION",
                    manifest.path,
                    node.id,
                    f"{old[node.id].status} cannot transition to {node.status}",
                )
            )
    return errors
