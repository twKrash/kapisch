from __future__ import annotations

from .capabilities import CapabilityClaims, CapabilityStatus
from .domain import (
    CapabilityEffect,
    EvidenceRef,
    ExecutionClass,
    Gate,
    GateDecision,
    LogicalTier,
    ProposedAction,
    ReviewDepth,
    ReviewScope,
    Risk,
    Role,
    RunState,
    Stage,
    Workflow,
)

_TIER_ORDER = {
    LogicalTier.CHEAP: 0,
    LogicalTier.STANDARD: 1,
    LogicalTier.HIGH: 2,
}


def decide(state: RunState, action: ProposedAction, capabilities: CapabilityClaims) -> GateDecision:
    """Check declared policy constraints; this does not validate persisted evidence."""
    if not _valid_inputs(state, action, capabilities):
        return GateDecision(False, ("invalid-policy-input",))

    reasons: list[str] = []
    if state.workflow is not Workflow.MILESTONE and state.graph is not None:
        reasons.append("workflow-must-be-graph-free")
    if state.workflow is Workflow.MILESTONE:
        if state.graph is None:
            reasons.append("milestone-requires-graph")
        if state.approved_plan is None:
            reasons.append("milestone-requires-approved-plan")

    if state.workflow is Workflow.ADVISORY and action.stage not in (Stage.RESEARCH, Stage.DESIGN, Stage.GATE):
        reasons.append("advisory-workflow-does-not-execute")
    if state.workflow is Workflow.ADVISORY and action.effect not in (
        CapabilityEffect.REPOSITORY_READ,
        CapabilityEffect.EXTERNAL_READ,
    ):
        reasons.append("advisory-workflow-is-read-only")
    if state.workflow is Workflow.REVIEW and (action.stage is not Stage.REVIEW or action.gate is not None):
        reasons.append("standalone-review-is-findings-only")
    if action.gate is Gate.APPROVAL and action.review_scope is ReviewScope.STANDALONE:
        reasons.append("standalone-review-cannot-approve")
    if state.workflow in (Workflow.TASK, Workflow.MILESTONE) and (
        action.gate is Gate.APPROVAL or action.stage is Stage.FINAL
    ):
        if state.review_invocation is None or state.review_result is None:
            reasons.append("approval-requires-review-evidence")
        if capabilities.mutation_free_reviewer is not CapabilityStatus.ENFORCED:
            reasons.append("reviewer-mutation-free-capability-not-enforced")

    if action.gate is not None and state.human_decision is None:
        reasons.append("gate-requires-human-decision")

    if action.stage is Stage.RESEARCH and action.role is not Role.RESEARCHER:
        reasons.append("research-requires-researcher")
    if action.stage is Stage.DESIGN and (action.role is not Role.ARCHITECT or action.tier is not LogicalTier.HIGH):
        reasons.append("design-requires-high-tier-architect")
    if action.stage is Stage.IMPLEMENT:
        floor = _implementation_floor(action.execution_class, action.risk)
        if floor is None:
            reasons.append("design-class-is-not-an-implementation-stage")
        elif action.role is not floor[0] or _TIER_ORDER[action.tier] < _TIER_ORDER[floor[1]]:
            reasons.append("implementation-below-role-tier-floor")
    if action.stage is Stage.BOUNDED_DELEGATE:
        floor = _delegated_assignment_floor(action)
        if floor is None:
            reasons.append("design-class-is-not-an-implementation-stage")
        elif action.role is not floor[0] or _TIER_ORDER[action.tier] < _TIER_ORDER[floor[1]]:
            reasons.append("delegated-assignment-below-role-tier-floor")
    if action.stage in (Stage.REVIEW, Stage.FINAL):
        if action.role is not Role.REVIEWER or action.tier is not LogicalTier.HIGH:
            reasons.append("review-requires-high-tier-reviewer")
    if (
        action.stage in (Stage.REVIEW, Stage.FINAL)
        or (state.workflow in (Workflow.TASK, Workflow.MILESTONE) and action.gate is Gate.APPROVAL)
    ) and action.risk is Risk.HIGH and action.review_depth is not ReviewDepth.DEEP:
        reasons.append("high-risk-review-requires-deep-depth")
    if action.role in (Role.ARCHITECT, Role.RESEARCHER, Role.REVIEWER) and action.effect not in (
        CapabilityEffect.REPOSITORY_READ,
        CapabilityEffect.EXTERNAL_READ,
    ):
        reasons.append("read-only-role-effect-must-be-read-only")
    if action.stage is Stage.FINAL and action.review_scope is not ReviewScope.WHOLE_BRANCH:
        reasons.append("final-requires-whole-branch-review")

    status = capabilities.status_for(action.effect)
    if status is CapabilityStatus.UNSUPPORTED:
        reasons.append("unsupported-capability-effect")
    if action.effect is CapabilityEffect.REPOSITORY_WRITE and status is not CapabilityStatus.ENFORCED:
        reasons.append("repository-write-capability-not-enforced")
    if action.effect in (CapabilityEffect.EXTERNAL_WRITE, CapabilityEffect.DESTRUCTIVE):
        reasons.append("external-write-or-destructive-effect-not-supported")
    if action.gate is Gate.SIDE_EFFECT and status is not CapabilityStatus.ENFORCED:
        reasons.append("side-effect-capability-not-enforced")

    return GateDecision(not reasons, tuple(reasons))


def _delegated_assignment_floor(action: ProposedAction) -> tuple[Role, LogicalTier] | None:
    if action.role is Role.ARCHITECT:
        return Role.ARCHITECT, LogicalTier.HIGH
    if action.role is Role.RESEARCHER:
        return Role.RESEARCHER, LogicalTier.STANDARD
    if action.role is Role.REVIEWER:
        return Role.REVIEWER, LogicalTier.HIGH
    return _implementation_floor(action.execution_class, action.risk)


def _implementation_floor(execution_class: ExecutionClass, risk: Risk) -> tuple[Role, LogicalTier] | None:
    if execution_class is ExecutionClass.MECHANICAL:
        return Role.MECHANIC, LogicalTier.CHEAP
    if execution_class is ExecutionClass.PRESCRIPTIVE and risk is Risk.HIGH:
        return Role.IMPLEMENTER, LogicalTier.STANDARD
    if execution_class is ExecutionClass.PRESCRIPTIVE:
        return Role.IMPLEMENTER_LITE, LogicalTier.CHEAP
    if execution_class is ExecutionClass.BOUNDED:
        return Role.IMPLEMENTER, LogicalTier.STANDARD
    return None


def _valid_inputs(state: RunState, action: ProposedAction, capabilities: CapabilityClaims) -> bool:
    if not isinstance(state, RunState) or not isinstance(action, ProposedAction) or not isinstance(capabilities, CapabilityClaims):
        return False
    if not isinstance(state.workflow, Workflow):
        return False
    if any(
        value is not None and not isinstance(value, EvidenceRef)
        for value in (state.graph, state.approved_plan, state.review_invocation, state.review_result, state.human_decision)
    ):
        return False
    enum_fields = (
        (action.stage, Stage),
        (action.role, Role),
        (action.risk, Risk),
        (action.execution_class, ExecutionClass),
        (action.tier, LogicalTier),
        (action.review_depth, ReviewDepth),
        (action.review_scope, ReviewScope),
        (action.effect, CapabilityEffect),
    )
    if any(not isinstance(value, enum_type) for value, enum_type in enum_fields):
        return False
    return action.gate is None or isinstance(action.gate, Gate)


__all__ = ["decide"]
