from __future__ import annotations

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
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    identities = (
        ("version", manifest.version, previous.version),
        ("task_id", manifest.task_id, previous.task_id),
        ("base_revision", manifest.base_revision, previous.base_revision),
        ("source_plan", manifest.source_plan, previous.source_plan),
        ("policies", manifest.policies, previous.policies),
    )
    for reference, current, prior in identities:
        if current != prior:
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
            if current_value == previous_value:
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
) -> list[ValidationError]:
    errors = validate_snapshot_compatibility(
        manifest, state, previous, previous_state
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
