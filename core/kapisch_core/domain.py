from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    ARCHITECT = "architect"
    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    IMPLEMENTER_LITE = "implementer-lite"
    MECHANIC = "mechanic"
    REVIEWER = "reviewer"


class Workflow(str, Enum):
    ADVISORY = "advisory"
    REVIEW = "review"
    TASK = "task"
    MILESTONE = "milestone"


class Stage(str, Enum):
    RESEARCH = "research"
    DESIGN = "design"
    IMPLEMENT = "implement"
    REVIEW = "review"
    FINAL = "final"
    GATE = "gate"
    BOUNDED_DELEGATE = "bounded-delegate"


class Gate(str, Enum):
    HUMAN_DECISION = "human-decision"
    APPROVAL = "approval"
    SIDE_EFFECT = "side-effect"


class Risk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExecutionClass(str, Enum):
    MECHANICAL = "mechanical"
    PRESCRIPTIVE = "prescriptive"
    BOUNDED = "bounded"
    DESIGN = "design"


class LogicalTier(str, Enum):
    CHEAP = "cheap"
    STANDARD = "standard"
    HIGH = "high"


class ReviewDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ReviewScope(str, Enum):
    STANDALONE = "standalone"
    ITERATION = "iteration"
    WHOLE_BRANCH = "whole-branch"


class CapabilityEffect(str, Enum):
    REPOSITORY_READ = "repository-read"
    REPOSITORY_WRITE = "repository-write"
    EXTERNAL_READ = "external-read"
    EXTERNAL_WRITE = "external-write"
    DESTRUCTIVE = "destructive"


class TransitionKind(str, Enum):
    COMPLETE = "complete"
    BLOCK = "block"
    FAIL = "fail"
    INTERRUPT = "interrupt"
    DISPATCH_UNCERTAIN = "dispatch-uncertain"


@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    identifier: str


@dataclass(frozen=True)
class Transition:
    """Semantic transition intent; Stage 7 defines allowed lifecycle edges."""

    kind: TransitionKind
    stage: Stage
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, TransitionKind) or not isinstance(self.stage, Stage):
            raise TypeError("transition kind and stage must use core vocabularies")
        if not isinstance(self.evidence, tuple) or any(not isinstance(ref, EvidenceRef) for ref in self.evidence):
            raise TypeError("transition evidence must be a tuple of EvidenceRef")


@dataclass(frozen=True)
class AuthorityGrant:
    actor: str
    source: str
    target: str
    scope: str
    effect: CapabilityEffect
    revision: str
    digest: str
    timestamp: str
    evidence: EvidenceRef


@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: str
    stage: Stage
    transition: Transition


@dataclass(frozen=True)
class RunState:
    workflow: Workflow
    graph: EvidenceRef | None = None
    approved_plan: EvidenceRef | None = None
    review_invocation: EvidenceRef | None = None
    review_result: EvidenceRef | None = None
    human_decision: EvidenceRef | None = None


@dataclass(frozen=True)
class ProposedAction:
    stage: Stage
    role: Role
    risk: Risk = Risk.LOW
    execution_class: ExecutionClass = ExecutionClass.PRESCRIPTIVE
    tier: LogicalTier = LogicalTier.STANDARD
    review_depth: ReviewDepth = ReviewDepth.STANDARD
    review_scope: ReviewScope = ReviewScope.ITERATION
    effect: CapabilityEffect = CapabilityEffect.REPOSITORY_READ
    gate: Gate | None = None


@dataclass(frozen=True)
class PolicyEvaluation:
    admissible: bool
    violations: tuple[str, ...] = ()


__all__ = [
    "AttemptRecord",
    "AuthorityGrant",
    "CapabilityEffect",
    "EvidenceRef",
    "ExecutionClass",
    "Gate",
    "LogicalTier",
    "ProposedAction",
    "ReviewDepth",
    "ReviewScope",
    "Risk",
    "Role",
    "RunState",
    "Stage",
    "Transition",
    "TransitionKind",
    "Workflow",
]
