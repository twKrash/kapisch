from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from .artifact_io import read_utf8_artifact
from .canonical_toml import render_toml
from .errors import ValidationError
from .outcomes import parse_outcome
from .transitions import determine_next_action

VIEW_PATH = "04-controller-view.toml"


def state_semantic_sha256(state_raw: dict[str, object]) -> str:
    raw = dict(state_raw)
    raw.pop("controller_view_path", None)
    raw.pop("controller_view_sha256", None)
    return hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _outcome_records(manifest, task_dir: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for node in manifest.nodes:
        assignment = node.raw.get("assignment")
        if not isinstance(assignment, dict):
            continue
        attempts = assignment.get("attempts")
        if not isinstance(attempts, list):
            continue
        for attempt in attempts:
            if not isinstance(attempt, dict) or attempt.get("status") not in {"complete", "blocked", "failed"}:
                continue
            outcome_path = attempt.get("outcome_path")
            if not isinstance(outcome_path, str):
                continue
            outcome, errors = parse_outcome(task_dir / outcome_path)
            if outcome is not None and not errors:
                records[outcome_path] = outcome
    return records


def build_controller_view(manifest, state, outcomes: object, manifest_bytes: bytes) -> dict[str, object]:
    next_action = determine_next_action(manifest, state)
    selected_id = next_action.split(":", 1)[1] if ":" in next_action and not next_action.startswith("block:") else "unavailable"
    nodes = {node.id: node for node in manifest.nodes}
    active = nodes.get(selected_id)
    dependency_ids = active.depends_on if active is not None else ()
    outcome_map = outcomes if isinstance(outcomes, dict) else {}
    predecessors: list[dict[str, object]] = []
    for node in sorted((nodes[ident] for ident in dependency_ids if ident in nodes), key=lambda item: item.sequence):
        assignment = node.raw.get("assignment")
        attempts = assignment.get("attempts", []) if isinstance(assignment, dict) else []
        for attempt in sorted((value for value in attempts if isinstance(value, dict)), key=lambda value: str(value.get("id", ""))):
            path = attempt.get("outcome_path")
            outcome = outcome_map.get(path) if isinstance(path, str) else None
            if not isinstance(outcome, dict):
                continue
            predecessors.append({key: outcome.get(key) for key in ("node_id", "attempt_id", "lifecycle", "role_status", "reviewer_decision", "redispatch_reason", "next_action_reason") } | {"outcome_path": path})
    assignment = active.raw.get("assignment") if active is not None else None
    return {
        "version": 1,
        "task_id": manifest.task_id,
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_state_sha256": state_semantic_sha256(state.raw),
        "workflow_status": state.workflow_status,
        "current_revision": state.current_revision,
        "next_action": next_action,
        "validator_status": "pass",
        "validator_error_count": 0,
        "active_node_id": selected_id,
        "next_node_id": selected_id,
        "current_fix_round": state.raw["current_fix_round"],
        "max_fix_rounds": state.raw["max_fix_rounds"],
        "request": {
            "source_plan": manifest.source_plan,
            "roadmap_item": manifest.roadmap_item or "unavailable",
            "scope": manifest.policies.get("scope", "unavailable"),
        },
        "gates": {
            "workflow": manifest.policies.get("execution", "unavailable"),
            "risk": active.raw.get("risk", "unavailable") if active else "unavailable",
            "fix_policy": manifest.policies.get("fix_policy", "unavailable"),
            "review_required": any(node.kind == "review" for node in manifest.nodes),
            "final_readiness_required": any(node.kind == "final" for node in manifest.nodes),
            "authority": {
                key: manifest.policies.get(key, "unavailable")
                for key in ("commit", "push", "dispatch", "executor", "model_tier")
            },
        },
        "blocking_reason": next_action if next_action.startswith("block:") else "unavailable",
        "active_assignment": {
            "node_id": selected_id,
            "role": active.raw.get("executor_class", "unavailable") if active else "unavailable",
            "logical_role": active.raw.get("executor_class", "unavailable") if active else "unavailable",
            "model_tier": active.raw.get("model_tier", "unavailable") if active else "unavailable",
            "assignment_id": assignment.get("id", "unavailable") if isinstance(assignment, dict) else "unavailable",
            "brief": active.raw.get("brief", "unavailable") if active else "unavailable",
            "context": active.raw.get("context", "unavailable") if active else "unavailable",
            "report": active.raw.get("report", "unavailable") if active else "unavailable",
        },
        "predecessor_outcomes": predecessors,
    }


def _quote(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render_controller_view(view: dict[str, object]) -> bytes:
    return render_toml(
        view,
        key_order=(
            "version", "task_id", "source_manifest_sha256", "source_state_sha256",
            "workflow_status", "current_revision", "next_action", "validator_status",
            "validator_error_count", "active_node_id", "next_node_id",
            "current_fix_round", "max_fix_rounds",
        ),
    )


def validate_controller_view(manifest, state, task_dir: Path) -> list[ValidationError]:
    if manifest.version != 4:
        return []
    path = task_dir / VIEW_PATH
    artifact, failure = read_utf8_artifact(path)
    if failure is not None:
        return [ValidationError("TWV-VIEW-MISSING", str(path), VIEW_PATH, "controller view is missing or unreadable")]
    assert artifact is not None
    try:
        raw = tomllib.loads(artifact.text)
    except tomllib.TOMLDecodeError:
        return [ValidationError("TWV-VIEW-MALFORMED-TOML", str(path), VIEW_PATH, "controller view is malformed")]
    errors: list[ValidationError] = []
    manifest_bytes = Path(manifest.path).read_bytes()
    if raw.get("source_manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest():
        errors.append(ValidationError("TWV-VIEW-MANIFEST-DIGEST", str(path), "source_manifest_sha256", "source manifest digest mismatch"))
    if raw.get("source_state_sha256") != state_semantic_sha256(state.raw):
        errors.append(ValidationError("TWV-VIEW-STATE-DIGEST", str(path), "source_state_sha256", "source state digest mismatch"))
    if state.controller_view_sha256 != hashlib.sha256(artifact.data).hexdigest():
        errors.append(ValidationError("TWV-VIEW-STATE-BINDING", str(path), "controller_view_sha256", "state binding digest mismatch"))
    expected_bytes = render_controller_view(
        build_controller_view(manifest, state, _outcome_records(manifest, task_dir), manifest_bytes)
    )
    if artifact.data != expected_bytes:
        errors.append(ValidationError("TWV-VIEW-PROJECTION", str(path), VIEW_PATH, "view is not the canonical deterministic projection"))
    return errors
