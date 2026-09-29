from __future__ import annotations

import dataclasses
import inspect
import tomllib
import unittest
from pathlib import Path

import kapisch_core.capabilities as capabilities
import kapisch_core.domain as domain
import kapisch_core.policy as policy

ROOT = Path(__file__).resolve().parents[2]


class Stage1DomainTests(unittest.TestCase):
    def test_closed_vocabularies_and_transition_type_are_core_owned(self) -> None:
        self.assertEqual(
            {item.value for item in domain.Role},
            {"architect", "researcher", "implementer", "implementer-lite", "mechanic", "reviewer"},
        )
        self.assertEqual({item.value for item in domain.Workflow}, {"advisory", "review", "task", "milestone"})
        self.assertEqual({item.value for item in domain.Risk}, {"low", "medium", "high"})
        self.assertEqual({item.value for item in domain.LogicalTier}, {"cheap", "standard", "high"})
        self.assertEqual(
            {item.value for item in domain.ExecutionClass},
            {"mechanical", "prescriptive", "bounded", "design"},
        )
        self.assertEqual(
            {item.value for item in domain.Gate},
            {"human-decision", "approval", "side-effect"},
        )
        self.assertEqual(
            {item.value for item in domain.ReviewDepth},
            {"quick", "standard", "deep"},
        )
        self.assertEqual(
            {item.value for item in domain.ReviewScope},
            {"standalone", "iteration", "whole-branch"},
        )
        self.assertEqual(
            {item.value for item in domain.CapabilityEffect},
            {"repository-read", "repository-write", "external-read", "external-write", "destructive"},
        )
        self.assertEqual(
            {item.value for item in capabilities.CapabilityStatus},
            {"enforced", "advisory", "unsupported", "unknown"},
        )
        self.assertEqual(
            {item.value for item in domain.Stage},
            {"research", "design", "implement", "review", "final", "gate", "bounded-delegate"},
        )
        self.assertEqual(
            {item.value for item in domain.TransitionKind},
            {"complete", "block", "fail", "interrupt", "dispatch-uncertain"},
        )
        self.assertTrue(dataclasses.is_dataclass(domain.Transition))
        immutable_records = (
            domain.EvidenceRef,
            domain.Transition,
            domain.AuthorityGrant,
            domain.AttemptRecord,
            domain.RunState,
            domain.ProposedAction,
            domain.GateDecision,
        )
        self.assertTrue(all(record.__dataclass_params__.frozen for record in immutable_records))
        with self.assertRaises(TypeError):
            domain.Transition(domain.TransitionKind.COMPLETE, domain.Stage.GATE, [])
        field_names = {field.name for field in dataclasses.fields(domain.Transition)}
        self.assertNotIn("from_state", field_names)
        self.assertNotIn("to_state", field_names)

    def test_high_risk_prescriptive_cannot_use_lite_or_cheap_reviewer(self) -> None:
        state = domain.RunState(workflow=domain.Workflow.TASK)
        action = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT,
            role=domain.Role.IMPLEMENTER_LITE,
            risk=domain.Risk.HIGH,
            execution_class=domain.ExecutionClass.PRESCRIPTIVE,
            tier=domain.LogicalTier.CHEAP,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)

        allowed_executor = dataclasses.replace(
            action,
            role=domain.Role.IMPLEMENTER,
            tier=domain.LogicalTier.STANDARD,
        )
        self.assertTrue(policy.decide(state, allowed_executor, capabilities.CapabilityClaims()).allowed)
        high_tier_executor = dataclasses.replace(allowed_executor, tier=domain.LogicalTier.HIGH)
        self.assertTrue(policy.decide(state, high_tier_executor, capabilities.CapabilityClaims()).allowed)

        reviewer = domain.ProposedAction(
            stage=domain.Stage.REVIEW,
            role=domain.Role.REVIEWER,
            risk=domain.Risk.HIGH,
            execution_class=domain.ExecutionClass.PRESCRIPTIVE,
            tier=domain.LogicalTier.CHEAP,
            review_depth=domain.ReviewDepth.DEEP,
        )
        self.assertFalse(policy.decide(state, reviewer, capabilities.CapabilityClaims()).allowed)
        allowed_reviewer = dataclasses.replace(reviewer, tier=domain.LogicalTier.HIGH)
        self.assertTrue(policy.decide(state, allowed_reviewer, capabilities.CapabilityClaims()).allowed)

    def test_bounded_delegate_cannot_downgrade_high_risk_assignment(self) -> None:
        state = domain.RunState(workflow=domain.Workflow.TASK)
        action = domain.ProposedAction(
            stage=domain.Stage.BOUNDED_DELEGATE,
            role=domain.Role.IMPLEMENTER_LITE,
            risk=domain.Risk.HIGH,
            execution_class=domain.ExecutionClass.PRESCRIPTIVE,
            tier=domain.LogicalTier.CHEAP,
        )
        decision = policy.decide(state, action, capabilities.CapabilityClaims())
        self.assertFalse(decision.allowed)
        self.assertIn("delegated-assignment-below-role-tier-floor", decision.reasons)

        allowed = dataclasses.replace(action, role=domain.Role.IMPLEMENTER, tier=domain.LogicalTier.STANDARD)
        self.assertTrue(policy.decide(state, allowed, capabilities.CapabilityClaims()).allowed)

    def test_unsupported_effect_blocks(self) -> None:
        effect = domain.CapabilityEffect.EXTERNAL_WRITE
        claims = capabilities.CapabilityClaims(
            claims=(capabilities.CapabilityClaim(effect, capabilities.CapabilityStatus.UNSUPPORTED),)
        )
        action = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT,
            role=domain.Role.IMPLEMENTER,
            effect=effect,
        )
        decision = policy.decide(domain.RunState(domain.Workflow.TASK), action, claims)
        self.assertFalse(decision.allowed)
        self.assertIn("unsupported-capability-effect", decision.reasons)

    def test_repository_write_requires_enforced_capability(self) -> None:
        effect = domain.CapabilityEffect.REPOSITORY_WRITE
        state = domain.RunState(workflow=domain.Workflow.TASK)
        action = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT,
            role=domain.Role.IMPLEMENTER,
            execution_class=domain.ExecutionClass.BOUNDED,
            tier=domain.LogicalTier.STANDARD,
            effect=effect,
        )
        cases = (
            ("missing", None, False),
            ("unknown", capabilities.CapabilityStatus.UNKNOWN, False),
            ("advisory", capabilities.CapabilityStatus.ADVISORY, False),
            ("unsupported", capabilities.CapabilityStatus.UNSUPPORTED, False),
            ("enforced", capabilities.CapabilityStatus.ENFORCED, True),
        )
        for label, status, allowed in cases:
            claims = (
                capabilities.CapabilityClaims()
                if status is None
                else capabilities.CapabilityClaims(
                    claims=(capabilities.CapabilityClaim(effect, status),)
                )
            )
            with self.subTest(label=label):
                decision = policy.decide(state, action, claims)
                self.assertEqual(decision.allowed, allowed)
                if not allowed:
                    self.assertIn("repository-write-capability-not-enforced", decision.reasons)

        read_action = dataclasses.replace(action, effect=domain.CapabilityEffect.REPOSITORY_READ)
        self.assertTrue(policy.decide(state, read_action, capabilities.CapabilityClaims()).allowed)

    def test_read_only_roles_cannot_request_write_effects(self) -> None:
        accepted = domain.RunState(
            workflow=domain.Workflow.ADVISORY,
            human_decision=domain.EvidenceRef("human-decision", "h4"),
        )
        actions = (
            domain.ProposedAction(
                stage=domain.Stage.RESEARCH,
                role=domain.Role.RESEARCHER,
                effect=domain.CapabilityEffect.REPOSITORY_WRITE,
            ),
            domain.ProposedAction(
                stage=domain.Stage.DESIGN,
                role=domain.Role.ARCHITECT,
                tier=domain.LogicalTier.HIGH,
                effect=domain.CapabilityEffect.REPOSITORY_WRITE,
            ),
            domain.ProposedAction(
                stage=domain.Stage.GATE,
                role=domain.Role.ARCHITECT,
                gate=domain.Gate.HUMAN_DECISION,
                effect=domain.CapabilityEffect.REPOSITORY_WRITE,
            ),
        )
        for action in actions:
            with self.subTest(stage=action.stage):
                self.assertFalse(policy.decide(accepted, action, capabilities.CapabilityClaims()).allowed)

    def test_advisory_gate_is_read_only_regardless_of_role(self) -> None:
        state = domain.RunState(
            workflow=domain.Workflow.ADVISORY,
            human_decision=domain.EvidenceRef("human-decision", "h5"),
        )
        action = domain.ProposedAction(
            stage=domain.Stage.GATE,
            role=domain.Role.IMPLEMENTER,
            gate=domain.Gate.HUMAN_DECISION,
            effect=domain.CapabilityEffect.REPOSITORY_WRITE,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)

    def test_standalone_review_scope_cannot_approve(self) -> None:
        state = domain.RunState(
            workflow=domain.Workflow.TASK,
            review_invocation=domain.EvidenceRef("review-invocation", "i4"),
            review_result=domain.EvidenceRef("review-result", "r4"),
            human_decision=domain.EvidenceRef("human-decision", "h4"),
        )
        action = domain.ProposedAction(
            stage=domain.Stage.REVIEW,
            role=domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            review_scope=domain.ReviewScope.STANDALONE,
            gate=domain.Gate.APPROVAL,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)

    def test_workflows_keep_distinct_graph_and_evidence_rules(self) -> None:
        caps = capabilities.CapabilityClaims()
        for workflow in (domain.Workflow.ADVISORY, domain.Workflow.REVIEW, domain.Workflow.TASK):
            state = domain.RunState(workflow=workflow, graph=domain.EvidenceRef("graph", "g1"))
            action = domain.ProposedAction(stage=domain.Stage.RESEARCH, role=domain.Role.RESEARCHER)
            self.assertFalse(policy.decide(state, action, caps).allowed, workflow.value)

        milestone = domain.RunState(workflow=domain.Workflow.MILESTONE)
        implementation = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT,
            role=domain.Role.IMPLEMENTER,
            execution_class=domain.ExecutionClass.BOUNDED,
        )
        self.assertFalse(policy.decide(milestone, implementation, caps).allowed)
        milestone = domain.RunState(
            workflow=domain.Workflow.MILESTONE,
            graph=domain.EvidenceRef("graph", "g1"),
            approved_plan=domain.EvidenceRef("plan", "p1"),
        )
        self.assertTrue(policy.decide(milestone, implementation, caps).allowed)

        review_only = domain.RunState(workflow=domain.Workflow.REVIEW)
        approval = domain.ProposedAction(
            stage=domain.Stage.REVIEW,
            role=domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            gate=domain.Gate.APPROVAL,
        )
        self.assertFalse(policy.decide(review_only, approval, caps).allowed)

        advisory = domain.RunState(workflow=domain.Workflow.ADVISORY)
        advisory_approval = dataclasses.replace(approval, stage=domain.Stage.GATE)
        advisory_human_gate = domain.ProposedAction(
            stage=domain.Stage.GATE,
            role=domain.Role.ARCHITECT,
            gate=domain.Gate.HUMAN_DECISION,
        )
        self.assertFalse(policy.decide(advisory, advisory_human_gate, caps).allowed)
        self.assertFalse(policy.decide(advisory, advisory_approval, caps).allowed)
        advisory = dataclasses.replace(advisory, human_decision=domain.EvidenceRef("human-decision", "h1"))
        self.assertTrue(policy.decide(advisory, advisory_human_gate, caps).allowed)
        self.assertTrue(policy.decide(advisory, advisory_approval, caps).allowed)

        task = domain.RunState(workflow=domain.Workflow.TASK)
        self.assertFalse(policy.decide(task, approval, caps).allowed)
        task = dataclasses.replace(
            task,
            review_invocation=domain.EvidenceRef("review-invocation", "i1"),
            review_result=domain.EvidenceRef("review-result", "r1"),
            human_decision=domain.EvidenceRef("human-decision", "h1"),
        )
        self.assertTrue(
            policy.decide(
                task,
                approval,
                capabilities.CapabilityClaims(
                    mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
                ),
            ).allowed
        )

    def test_model_and_profile_values_are_not_policy_inputs(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(policy.decide).parameters),
            ("state", "action", "capabilities"),
        )
        for record in (domain.RunState, domain.ProposedAction):
            names = {field.name for field in dataclasses.fields(record)}
            self.assertTrue(names.isdisjoint({"model", "model_id", "provider", "profile", "profile_id"}))

    def test_design_class_cannot_be_dispatched_as_implementation(self) -> None:
        state = domain.RunState(workflow=domain.Workflow.TASK)
        action = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT,
            role=domain.Role.ARCHITECT,
            execution_class=domain.ExecutionClass.DESIGN,
            tier=domain.LogicalTier.HIGH,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)

    def test_authoritative_approval_requires_enforced_mutation_free_reviewer(self) -> None:
        state = domain.RunState(
            workflow=domain.Workflow.TASK,
            review_invocation=domain.EvidenceRef("review-invocation", "i0"),
            review_result=domain.EvidenceRef("review-result", "r0"),
            human_decision=domain.EvidenceRef("human-decision", "h0"),
        )
        actions = (
            domain.ProposedAction(
                stage=domain.Stage.GATE,
                role=domain.Role.IMPLEMENTER,
                gate=domain.Gate.APPROVAL,
            ),
            domain.ProposedAction(
                stage=domain.Stage.FINAL,
                role=domain.Role.REVIEWER,
                tier=domain.LogicalTier.HIGH,
                risk=domain.Risk.HIGH,
                review_depth=domain.ReviewDepth.DEEP,
                review_scope=domain.ReviewScope.WHOLE_BRANCH,
            ),
        )
        cases = (
            ("missing", None, False),
            ("unknown", capabilities.CapabilityStatus.UNKNOWN, False),
            ("advisory", capabilities.CapabilityStatus.ADVISORY, False),
            ("unsupported", capabilities.CapabilityStatus.UNSUPPORTED, False),
            ("enforced", capabilities.CapabilityStatus.ENFORCED, True),
        )
        for action in actions:
            for label, status, allowed in cases:
                claims = (
                    capabilities.CapabilityClaims()
                    if status is None
                    else capabilities.CapabilityClaims(mutation_free_reviewer=status)
                )
                with self.subTest(stage=action.stage, claim=label):
                    decision = policy.decide(state, action, claims)
                    self.assertEqual(decision.allowed, allowed)
                    if not allowed:
                        self.assertIn("reviewer-mutation-free-capability-not-enforced", decision.reasons)

    def test_high_risk_approval_requires_deep_review(self) -> None:
        state = domain.RunState(
            workflow=domain.Workflow.TASK,
            review_invocation=domain.EvidenceRef("review-invocation", "i1"),
            review_result=domain.EvidenceRef("review-result", "r1"),
            human_decision=domain.EvidenceRef("human-decision", "h1"),
        )
        quick = domain.ProposedAction(
            stage=domain.Stage.GATE,
            role=domain.Role.IMPLEMENTER,
            risk=domain.Risk.HIGH,
            review_depth=domain.ReviewDepth.QUICK,
            gate=domain.Gate.APPROVAL,
        )
        claims = capabilities.CapabilityClaims(
            mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
        )
        decision = policy.decide(state, quick, claims)
        self.assertFalse(decision.allowed)
        self.assertIn("high-risk-review-requires-deep-depth", decision.reasons)

        deep = dataclasses.replace(quick, review_depth=domain.ReviewDepth.DEEP)
        self.assertTrue(policy.decide(state, deep, claims).allowed)

    def test_approval_requires_review_evidence(self) -> None:
        state = domain.RunState(
            workflow=domain.Workflow.TASK,
            human_decision=domain.EvidenceRef("human-decision", "h2"),
        )
        action = domain.ProposedAction(
            stage=domain.Stage.GATE,
            role=domain.Role.IMPLEMENTER,
            gate=domain.Gate.APPROVAL,
        )
        caps = capabilities.CapabilityClaims(
            mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
        )
        self.assertFalse(policy.decide(state, action, caps).allowed)
        state = dataclasses.replace(
            state,
            review_invocation=domain.EvidenceRef("review-invocation", "i2"),
            review_result=domain.EvidenceRef("review-result", "r2"),
        )
        self.assertTrue(policy.decide(state, action, caps).allowed)

    def test_final_requires_review_evidence(self) -> None:
        state = domain.RunState(workflow=domain.Workflow.TASK)
        action = domain.ProposedAction(
            stage=domain.Stage.FINAL,
            role=domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            review_scope=domain.ReviewScope.WHOLE_BRANCH,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)
        state = dataclasses.replace(
            state,
            review_invocation=domain.EvidenceRef("review-invocation", "i3"),
            review_result=domain.EvidenceRef("review-result", "r3"),
        )
        self.assertTrue(
            policy.decide(
                state,
                action,
                capabilities.CapabilityClaims(
                    mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
                ),
            ).allowed
        )

    def test_standalone_review_rejects_mutating_effects(self) -> None:
        state = domain.RunState(workflow=domain.Workflow.REVIEW)
        action = domain.ProposedAction(
            stage=domain.Stage.REVIEW,
            role=domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            effect=domain.CapabilityEffect.REPOSITORY_WRITE,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)
        read_only = dataclasses.replace(action, effect=domain.CapabilityEffect.REPOSITORY_READ)
        self.assertTrue(policy.decide(state, read_only, capabilities.CapabilityClaims()).allowed)

    def test_advisory_workflow_blocks_implementation(self) -> None:
        state = domain.RunState(workflow=domain.Workflow.ADVISORY)
        action = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT,
            role=domain.Role.IMPLEMENTER,
            execution_class=domain.ExecutionClass.BOUNDED,
        )
        self.assertFalse(policy.decide(state, action, capabilities.CapabilityClaims()).allowed)

    def test_stage1_package_has_no_validator_entrypoint(self) -> None:
        config = tomllib.loads((ROOT / "core" / "pyproject.toml").read_text())
        self.assertNotIn("scripts", config.get("project", {}))


if __name__ == "__main__":
    unittest.main()
