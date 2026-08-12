from __future__ import annotations

from .errors import ValidationError

EXECUTOR_CLASS_VALUES = (
    "mechanic",
    "implementer-lite",
    "implementer",
    "architect",
    "researcher",
    "reviewer",
)
MODEL_TIER_VALUES = ("cheap", "standard", "high")
BATCHING_VALUES = ("auto", "off")
EXECUTION_CLASS_VALUES = ("mechanical", "prescriptive", "bounded", "design")

POLICY_VALUES: dict[str, tuple[str, ...]] = {
    "execution": ("sequential",),
    "executor": ("implementer",),
    "dispatch": ("auto", "single"),
    "model_tier": MODEL_TIER_VALUES,
    "batching": BATCHING_VALUES,
    "parallelism": ("off",),
    "commit": ("manual",),
    "push": ("manual",),
    "fix_policy": ("manual", "blocking"),
    "ecosystem_routing": ("auto", "off"),
}

NODE_ROUTING_VALUES: dict[str, tuple[str, ...]] = {
    "executor_class": EXECUTOR_CLASS_VALUES,
    "model_tier": MODEL_TIER_VALUES,
    "batching": BATCHING_VALUES,
}
ASSIGNMENT_VALUES: dict[str, tuple[str, ...]] = {
    "execution_class": EXECUTION_CLASS_VALUES,
}

WORKFLOW_STATUS_VALUES = ("running", "complete")
RUNTIME_RECORD_STATUS_VALUES = ("pending", "running", "complete", "blocked", "failed")
WORKFLOW_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "running": frozenset({"running", "complete"}),
    "complete": frozenset({"complete"}),
}
TERMINAL_WORKFLOW_STATUSES = frozenset({"complete"})
TERMINAL_NEXT_ACTIONS = frozenset({"complete"})


def closed_string_error(
    value: object,
    supported: tuple[str, ...],
    *,
    path: str,
    reference: str,
) -> ValidationError | None:
    alternatives = ", ".join(repr(item) for item in supported)
    if not isinstance(value, str):
        code = "TWV-SCHEMA-WRONG-SHAPE"
        detail = "must be a string"
    elif value not in supported:
        code = "TWV-SCHEMA-INVALID-VALUE"
        detail = "unsupported value"
    else:
        return None
    return ValidationError(
        code,
        path,
        reference,
        f"{detail}; got {value!r}; supported values: {alternatives}",
    )
