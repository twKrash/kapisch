from __future__ import annotations

from .errors import ValidationError
from .models import Manifest, State

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
    manifest: Manifest, state: State, previous: Manifest | None = None
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
                    manifest.path,
                    "next_action",
                    "next_action must use a documented action token and known node ID",
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
    if previous:
        old = {n.id: n for n in previous.nodes}
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
