"""Pure renderers for optional, non-authoritative KAPISCH presentations."""

from __future__ import annotations

from copy import deepcopy

from .canonical_bytes import canonical_json_bytes


_STATE_MEMBERSHIP_FIELDS = (
    "completed_node_ids",
    "running_node_ids",
    "ready_node_ids",
    "blocked_node_ids",
    "failed_node_ids",
)


def _state_projection(raw: dict[str, object]) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("state must be a mapping")

    # Keep the projection independent from the TOML renderer and do not mutate
    # the caller's parsed state.  These fields are sets semantically, even
    # though the durable TOML representation is an array.
    projection = deepcopy(raw)
    for field in _STATE_MEMBERSHIP_FIELDS:
        if field not in projection:
            continue
        values = projection[field]
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            raise ValueError(f"state field {field} must be a list of non-empty strings")
        if len(values) != len(set(values)):
            raise ValueError(f"state field {field} contains duplicate IDs")
        projection[field] = sorted(values)
    return projection


def render_state_markdown(raw: dict[str, object]) -> bytes:
    """Render the optional semantic state view as canonical JSON-in-Markdown."""
    payload = canonical_json_bytes(_state_projection(raw))
    return b"# KAPISCH State\n\n```json\n" + payload + b"\n```\n"


def render_metrics(
    records: list[dict[str, object]], summary: dict[str, object]
) -> bytes:
    """Render final workflow metrics without inventing or rewriting observations."""
    if not isinstance(records, list):
        raise ValueError("metric records must be a list")
    if not isinstance(summary, dict):
        raise ValueError("metric summary must be a mapping")

    copied_records = deepcopy(records)
    terminal_ids: set[str] = set()
    for record in copied_records:
        if not isinstance(record, dict):
            raise ValueError("each metric record must be a mapping")
        terminal_id = record.get("terminal_id")
        if not isinstance(terminal_id, str) or not terminal_id:
            raise ValueError("each metric record requires a non-empty terminal_id")
        if terminal_id in terminal_ids:
            raise ValueError(f"duplicate metric terminal_id: {terminal_id!r}")
        terminal_ids.add(terminal_id)

    copied_records.sort(key=lambda record: record["terminal_id"])
    payload = canonical_json_bytes({"records": copied_records, "summary": deepcopy(summary)})
    return b"# KAPISCH Workflow Metrics\n\n```json\n" + payload + b"\n```\n"
