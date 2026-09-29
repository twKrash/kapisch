from __future__ import annotations

from types import MappingProxyType

from .capabilities import CapabilityClaims, CapabilityStatus
from .domain import (
    CapabilityEffect,
    ExecutionClass,
    Gate,
    LogicalTier,
    PolicyEvaluation,
    ProposedAction,
    ReviewDepth,
    ReviewScope,
    Risk,
    Role,
    Stage,
    Workflow,
)

_TIER_ORDER = MappingProxyType(
    {
        LogicalTier.CHEAP: 0,
        LogicalTier.STANDARD: 1,
        LogicalTier.HIGH: 2,
    }
)
_IMPLEMENTATION_FLOORS = MappingProxyType(
    {
        (ExecutionClass.MECHANICAL, Risk.LOW): (Role.MECHANIC, LogicalTier.CHEAP),
        (ExecutionClass.MECHANICAL, Risk.MEDIUM): (Role.MECHANIC, LogicalTier.CHEAP),
        (ExecutionClass.MECHANICAL, Risk.HIGH): (Role.MECHANIC, LogicalTier.CHEAP),
        (ExecutionClass.PRESCRIPTIVE, Risk.LOW): (Role.IMPLEMENTER_LITE, LogicalTier.CHEAP),
        (ExecutionClass.PRESCRIPTIVE, Risk.MEDIUM): (Role.IMPLEMENTER_LITE, LogicalTier.CHEAP),
        (ExecutionClass.PRESCRIPTIVE, Risk.HIGH): (Role.IMPLEMENTER, LogicalTier.STANDARD),
        (ExecutionClass.BOUNDED, Risk.LOW): (Role.IMPLEMENTER, LogicalTier.STANDARD),
        (ExecutionClass.BOUNDED, Risk.MEDIUM): (Role.IMPLEMENTER, LogicalTier.STANDARD),
        (ExecutionClass.BOUNDED, Risk.HIGH): (Role.IMPLEMENTER, LogicalTier.STANDARD),
    }
)
_IMPLEMENTATION_ROLE_ORDER = MappingProxyType(
    {
        Role.MECHANIC: 0,
        Role.IMPLEMENTER_LITE: 1,
        Role.IMPLEMENTER: 2,
    }
)
_STAGE_REQUIREMENTS = MappingProxyType(
    {
        Stage.RESEARCH: (Role.RESEARCHER, LogicalTier.STANDARD),
        Stage.DESIGN: (Role.ARCHITECT, LogicalTier.HIGH),
        Stage.REVIEW: (Role.REVIEWER, LogicalTier.HIGH),
        Stage.FINAL: (Role.REVIEWER, LogicalTier.HIGH),
    }
)
_DELEGATE_ROLE_FLOORS = MappingProxyType(
    {
        Role.ARCHITECT: (Role.ARCHITECT, LogicalTier.HIGH),
        Role.RESEARCHER: (Role.RESEARCHER, LogicalTier.STANDARD),
        Role.REVIEWER: (Role.REVIEWER, LogicalTier.HIGH),
    }
)
_WORKFLOW_STAGES = MappingProxyType(
    {
        Workflow.ADVISORY: frozenset({Stage.RESEARCH, Stage.DESIGN, Stage.GATE}),
        Workflow.REVIEW: frozenset({Stage.REVIEW}),
        Workflow.TASK: frozenset(Stage),
        Workflow.MILESTONE: frozenset(Stage),
    }
)
_APPROVAL_WORKFLOWS = frozenset({Workflow.TASK, Workflow.MILESTONE})
_READ_ONLY_ROLES = frozenset({Role.ARCHITECT, Role.RESEARCHER, Role.REVIEWER})
_READ_ONLY_EFFECTS = frozenset({CapabilityEffect.REPOSITORY_READ, CapabilityEffect.EXTERNAL_READ})


def evaluate_action_policy(
    workflow: Workflow,
    action: ProposedAction,
    capabilities: CapabilityClaims,
) -> PolicyEvaluation:
    """Evaluate static semantic admissibility; persisted authority is checked elsewhere."""
    if not _valid_policy_inputs(workflow, action, capabilities):
        return PolicyEvaluation(("invalid-policy-input",))

    violations = (
        *workflow_violations(workflow, action),
        *assignment_violations(action),
        *review_violations(workflow, action, capabilities),
        *effect_violations(action, capabilities),
    )
    return PolicyEvaluation(violations)


def workflow_violations(workflow: Workflow, action: ProposedAction) -> tuple[str, ...]:
    violations: list[str] = []
    if action.stage not in _WORKFLOW_STAGES[workflow]:
        violations.append(
            "advisory-workflow-does-not-execute"
            if workflow is Workflow.ADVISORY
            else "standalone-review-is-findings-only"
        )
    if workflow is Workflow.REVIEW and action.gate is not None:
        violations.append("standalone-review-is-findings-only")
    if workflow is Workflow.ADVISORY and action.effect not in _READ_ONLY_EFFECTS:
        violations.append("advisory-workflow-is-read-only")
    if action.gate is Gate.APPROVAL and workflow not in _APPROVAL_WORKFLOWS:
        violations.append("approval-not-admissible-for-workflow")
    if action.gate is Gate.APPROVAL and action.review_scope is ReviewScope.STANDALONE:
        violations.append("standalone-review-cannot-approve")
    return tuple(violations)


def assignment_violations(action: ProposedAction) -> tuple[str, ...]:
    floor = _STAGE_REQUIREMENTS.get(action.stage)
    if action.stage is Stage.IMPLEMENT:
        floor = _IMPLEMENTATION_FLOORS.get((action.execution_class, action.risk))
        if floor is None:
            return ("design-class-is-not-an-implementation-stage",)
        if not _meets_implementation_floor(action.role, action.tier, floor):
            return ("implementation-below-role-tier-floor",)
        return ()

    if action.stage is Stage.BOUNDED_DELEGATE:
        if action.execution_class is ExecutionClass.DESIGN and action.role is not Role.ARCHITECT:
            return ("delegated-assignment-below-role-tier-floor",)
        role_floor = _DELEGATE_ROLE_FLOORS.get(action.role)
        if role_floor is not None:
            if _TIER_ORDER[action.tier] < _TIER_ORDER[role_floor[1]]:
                return ("delegated-assignment-below-role-tier-floor",)
            return ()
        floor = _IMPLEMENTATION_FLOORS.get((action.execution_class, action.risk))
        if floor is None or not _meets_implementation_floor(action.role, action.tier, floor):
            return ("delegated-assignment-below-role-tier-floor",)
        return ()

    if floor is not None:
        required_role, minimum_tier = floor
        if action.role is not required_role:
            return (
                {
                    Stage.RESEARCH: "research-requires-researcher",
                    Stage.DESIGN: "design-requires-high-tier-architect",
                    Stage.REVIEW: "review-requires-high-tier-reviewer",
                    Stage.FINAL: "review-requires-high-tier-reviewer",
                }[action.stage],
            )
        if minimum_tier is not None and _TIER_ORDER[action.tier] < _TIER_ORDER[minimum_tier]:
            reason = (
                "research-requires-standard-tier"
                if action.stage is Stage.RESEARCH
                else "design-requires-high-tier-architect"
                if action.stage is Stage.DESIGN
                else "review-requires-high-tier-reviewer"
            )
            return (reason,)
    return ()


def _meets_implementation_floor(
    role: Role,
    tier: LogicalTier,
    floor: tuple[Role, LogicalTier],
) -> bool:
    role_strength = _IMPLEMENTATION_ROLE_ORDER.get(role)
    return (
        role_strength is not None
        and role_strength >= _IMPLEMENTATION_ROLE_ORDER[floor[0]]
        and _TIER_ORDER[tier] >= _TIER_ORDER[floor[1]]
    )


def review_violations(
    workflow: Workflow,
    action: ProposedAction,
    capabilities: CapabilityClaims,
) -> tuple[str, ...]:
    violations: list[str] = []
    if action.stage is Stage.REVIEW:
        if workflow is Workflow.REVIEW and action.review_scope is not ReviewScope.STANDALONE:
            violations.append("standalone-review-requires-standalone-scope")
        if workflow in _APPROVAL_WORKFLOWS and action.review_scope is ReviewScope.STANDALONE:
            violations.append("task-or-milestone-review-requires-scoped-review")
    if action.stage is Stage.FINAL and action.review_scope is not ReviewScope.WHOLE_BRANCH:
        violations.append("final-requires-whole-branch-review")
    if (
        action.risk is Risk.HIGH
        and (
            action.stage in (Stage.IMPLEMENT, Stage.BOUNDED_DELEGATE, Stage.REVIEW, Stage.FINAL)
            or action.gate is Gate.APPROVAL
        )
        and action.review_depth is not ReviewDepth.DEEP
    ):
        violations.append("high-risk-review-requires-deep-depth")
    if workflow in _APPROVAL_WORKFLOWS and (
        action.gate is Gate.APPROVAL or action.stage is Stage.FINAL
    ) and capabilities.mutation_free_reviewer is not CapabilityStatus.ENFORCED:
        violations.append("reviewer-mutation-free-capability-not-enforced")
    return tuple(violations)


def effect_violations(action: ProposedAction, capabilities: CapabilityClaims) -> tuple[str, ...]:
    violations: list[str] = []
    status = capabilities.status_for(action.effect)
    if status is CapabilityStatus.UNSUPPORTED:
        violations.append("unsupported-capability-effect")
    if action.effect is CapabilityEffect.REPOSITORY_WRITE and status is not CapabilityStatus.ENFORCED:
        violations.append("repository-write-capability-not-enforced")
    if action.effect in (CapabilityEffect.EXTERNAL_WRITE, CapabilityEffect.DESTRUCTIVE):
        violations.append("external-write-or-destructive-effect-not-supported")
    if action.gate is Gate.SIDE_EFFECT and status is not CapabilityStatus.ENFORCED:
        violations.append("side-effect-capability-not-enforced")
    if action.role in _READ_ONLY_ROLES and action.effect not in _READ_ONLY_EFFECTS:
        violations.append("read-only-role-effect-must-be-read-only")
    return tuple(violations)


def _valid_policy_inputs(
    workflow: Workflow,
    action: ProposedAction,
    capabilities: CapabilityClaims,
) -> bool:
    if not isinstance(workflow, Workflow) or not isinstance(action, ProposedAction):
        return False
    if not isinstance(capabilities, CapabilityClaims):
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


__all__ = ["evaluate_action_policy"]
