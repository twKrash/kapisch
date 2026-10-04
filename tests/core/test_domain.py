from __future__ import annotations

import dataclasses
import inspect
import unittest

import kapisch_core.capabilities as capabilities
import kapisch_core.domain as domain
import kapisch_core.policy as policy


def evaluate(
    workflow: domain.Workflow,
    stage: domain.Stage,
    role: domain.Role,
    *,
    claims: capabilities.CapabilityClaims | None = None,
    **action_fields: object,
) -> domain.PolicyEvaluation:
    action = domain.ProposedAction(stage=stage, role=role, **action_fields)
    return policy.evaluate_action_policy(
        workflow,
        action,
        claims if claims is not None else capabilities.CapabilityClaims(),
    )


class Stage1DomainTests(unittest.TestCase):
    def assert_violation(self, result: domain.PolicyEvaluation, reason: str) -> None:
        self.assertFalse(result.admissible)
        self.assertIn(reason, result.violations)

    def test_closed_vocabularies_and_transition_type_are_core_owned(self) -> None:
        self.assertEqual(
            {item.value for item in domain.Role},
            {
                "architect",
                "researcher",
                "implementer",
                "implementer-lite",
                "mechanic",
                "reviewer",
            },
        )
        self.assertEqual(
            {item.value for item in domain.Workflow},
            {"advisory", "review", "task", "milestone"},
        )
        self.assertEqual(
            {item.value for item in domain.Risk}, {"low", "medium", "high"}
        )
        self.assertEqual(
            {item.value for item in domain.LogicalTier}, {"cheap", "standard", "high"}
        )
        self.assertEqual(
            {item.value for item in domain.ExecutionClass},
            {"mechanical", "prescriptive", "bounded", "design"},
        )
        self.assertEqual(
            {item.value for item in domain.Gate},
            {"human-decision", "approval", "side-effect"},
        )
        self.assertEqual(
            {item.value for item in domain.ReviewDepth}, {"quick", "standard", "deep"}
        )
        self.assertEqual(
            {item.value for item in domain.ReviewScope},
            {"standalone", "iteration", "whole-branch"},
        )
        self.assertEqual(
            {item.value for item in domain.TransitionKind},
            {"complete", "block", "fail", "interrupt", "dispatch-uncertain"},
        )
        self.assertTrue(dataclasses.is_dataclass(domain.RunState))
        self.assertTrue(dataclasses.is_dataclass(domain.Transition))
        self.assertTrue(domain.Transition.__dataclass_params__.frozen)
        with self.assertRaises(TypeError):
            domain.Transition(domain.TransitionKind.COMPLETE, domain.Stage.GATE, [])
        transition_fields = {
            field.name for field in dataclasses.fields(domain.Transition)
        }
        self.assertFalse({"from_state", "to_state"} & transition_fields)

    def test_implementation_assignment_floors(self) -> None:
        cases = (
            (
                domain.ExecutionClass.MECHANICAL,
                domain.Risk.LOW,
                domain.Role.MECHANIC,
                domain.LogicalTier.CHEAP,
            ),
            (
                domain.ExecutionClass.MECHANICAL,
                domain.Risk.HIGH,
                domain.Role.MECHANIC,
                domain.LogicalTier.CHEAP,
            ),
            (
                domain.ExecutionClass.PRESCRIPTIVE,
                domain.Risk.LOW,
                domain.Role.IMPLEMENTER_LITE,
                domain.LogicalTier.CHEAP,
            ),
            (
                domain.ExecutionClass.PRESCRIPTIVE,
                domain.Risk.MEDIUM,
                domain.Role.IMPLEMENTER_LITE,
                domain.LogicalTier.CHEAP,
            ),
            (
                domain.ExecutionClass.PRESCRIPTIVE,
                domain.Risk.HIGH,
                domain.Role.IMPLEMENTER,
                domain.LogicalTier.STANDARD,
            ),
            (
                domain.ExecutionClass.BOUNDED,
                domain.Risk.LOW,
                domain.Role.IMPLEMENTER,
                domain.LogicalTier.STANDARD,
            ),
            (
                domain.ExecutionClass.BOUNDED,
                domain.Risk.HIGH,
                domain.Role.IMPLEMENTER,
                domain.LogicalTier.STANDARD,
            ),
        )
        for execution_class, risk, role, tier in cases:
            with self.subTest(execution_class=execution_class, risk=risk):
                result = evaluate(
                    domain.Workflow.TASK,
                    domain.Stage.IMPLEMENT,
                    role,
                    execution_class=execution_class,
                    risk=risk,
                    tier=tier,
                    review_depth=(
                        domain.ReviewDepth.DEEP
                        if risk is domain.Risk.HIGH
                        else domain.ReviewDepth.STANDARD
                    ),
                )
                self.assertTrue(result.admissible, result.violations)
                below_floor = evaluate(
                    domain.Workflow.TASK,
                    domain.Stage.IMPLEMENT,
                    domain.Role.RESEARCHER,
                    execution_class=execution_class,
                    risk=risk,
                    tier=tier,
                    review_depth=(
                        domain.ReviewDepth.DEEP
                        if risk is domain.Risk.HIGH
                        else domain.ReviewDepth.STANDARD
                    ),
                )
                self.assert_violation(
                    below_floor, "implementation-below-role-tier-floor"
                )

    def test_implementation_assignments_accept_only_safe_role_upgrades(self) -> None:
        upgrades = (
            (domain.Stage.IMPLEMENT, domain.ExecutionClass.MECHANICAL, domain.Risk.LOW),
            (
                domain.Stage.IMPLEMENT,
                domain.ExecutionClass.PRESCRIPTIVE,
                domain.Risk.MEDIUM,
            ),
            (
                domain.Stage.BOUNDED_DELEGATE,
                domain.ExecutionClass.MECHANICAL,
                domain.Risk.LOW,
            ),
            (
                domain.Stage.BOUNDED_DELEGATE,
                domain.ExecutionClass.PRESCRIPTIVE,
                domain.Risk.MEDIUM,
            ),
        )
        for stage, execution_class, risk in upgrades:
            with self.subTest(stage=stage, execution_class=execution_class, risk=risk):
                result = evaluate(
                    domain.Workflow.TASK,
                    stage,
                    domain.Role.IMPLEMENTER,
                    execution_class=execution_class,
                    risk=risk,
                    tier=domain.LogicalTier.STANDARD,
                )
                self.assertTrue(result.admissible, result.violations)

        downgrades = (
            (
                domain.Stage.IMPLEMENT,
                domain.ExecutionClass.PRESCRIPTIVE,
                domain.Risk.HIGH,
            ),
            (
                domain.Stage.BOUNDED_DELEGATE,
                domain.ExecutionClass.BOUNDED,
                domain.Risk.HIGH,
            ),
        )
        for stage, execution_class, risk in downgrades:
            reason = (
                "implementation-below-role-tier-floor"
                if stage is domain.Stage.IMPLEMENT
                else "delegated-assignment-below-role-tier-floor"
            )
            with self.subTest(stage=stage, execution_class=execution_class, risk=risk):
                result = evaluate(
                    domain.Workflow.TASK,
                    stage,
                    domain.Role.IMPLEMENTER_LITE,
                    execution_class=execution_class,
                    risk=risk,
                    tier=domain.LogicalTier.CHEAP,
                )
                self.assert_violation(result, reason)

    def test_design_class_is_not_an_implementation_assignment(self) -> None:
        result = evaluate(
            domain.Workflow.TASK,
            domain.Stage.IMPLEMENT,
            domain.Role.IMPLEMENTER,
            execution_class=domain.ExecutionClass.DESIGN,
        )
        self.assert_violation(result, "design-class-is-not-an-implementation-stage")

    def test_design_research_and_review_roles_have_static_floors(self) -> None:
        self.assertTrue(
            evaluate(
                domain.Workflow.ADVISORY, domain.Stage.RESEARCH, domain.Role.RESEARCHER
            ).admissible
        )
        self.assert_violation(
            evaluate(
                domain.Workflow.ADVISORY, domain.Stage.RESEARCH, domain.Role.ARCHITECT
            ),
            "research-requires-researcher",
        )
        self.assertTrue(
            evaluate(
                domain.Workflow.ADVISORY,
                domain.Stage.DESIGN,
                domain.Role.ARCHITECT,
                tier=domain.LogicalTier.HIGH,
            ).admissible
        )
        self.assert_violation(
            evaluate(
                domain.Workflow.ADVISORY,
                domain.Stage.DESIGN,
                domain.Role.ARCHITECT,
                tier=domain.LogicalTier.STANDARD,
            ),
            "design-requires-high-tier-architect",
        )
        self.assertTrue(
            evaluate(
                domain.Workflow.TASK,
                domain.Stage.REVIEW,
                domain.Role.REVIEWER,
                tier=domain.LogicalTier.HIGH,
            ).admissible
        )
        self.assert_violation(
            evaluate(
                domain.Workflow.TASK,
                domain.Stage.REVIEW,
                domain.Role.REVIEWER,
                tier=domain.LogicalTier.STANDARD,
            ),
            "review-requires-high-tier-reviewer",
        )

    def test_research_assignments_require_standard_tier(self) -> None:
        for workflow in (
            domain.Workflow.ADVISORY,
            domain.Workflow.TASK,
            domain.Workflow.MILESTONE,
        ):
            with self.subTest(workflow=workflow):
                standard = evaluate(
                    workflow,
                    domain.Stage.RESEARCH,
                    domain.Role.RESEARCHER,
                    tier=domain.LogicalTier.STANDARD,
                )
                self.assertTrue(standard.admissible, standard.violations)
                cheap = evaluate(
                    workflow,
                    domain.Stage.RESEARCH,
                    domain.Role.RESEARCHER,
                    tier=domain.LogicalTier.CHEAP,
                )
                self.assert_violation(cheap, "research-requires-standard-tier")

    def test_bounded_delegate_keeps_role_and_tier_floor(self) -> None:
        good = evaluate(
            domain.Workflow.TASK,
            domain.Stage.BOUNDED_DELEGATE,
            domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
        )
        self.assertTrue(good.admissible, good.violations)
        low = evaluate(
            domain.Workflow.TASK,
            domain.Stage.BOUNDED_DELEGATE,
            domain.Role.REVIEWER,
            tier=domain.LogicalTier.STANDARD,
        )
        self.assert_violation(low, "delegated-assignment-below-role-tier-floor")

    def test_design_class_delegate_requires_high_tier_architect(self) -> None:
        architect = evaluate(
            domain.Workflow.TASK,
            domain.Stage.BOUNDED_DELEGATE,
            domain.Role.ARCHITECT,
            execution_class=domain.ExecutionClass.DESIGN,
            tier=domain.LogicalTier.HIGH,
        )
        self.assertTrue(architect.admissible, architect.violations)

        for role, tier in (
            (domain.Role.RESEARCHER, domain.LogicalTier.STANDARD),
            (domain.Role.REVIEWER, domain.LogicalTier.HIGH),
        ):
            with self.subTest(role=role):
                result = evaluate(
                    domain.Workflow.TASK,
                    domain.Stage.BOUNDED_DELEGATE,
                    role,
                    execution_class=domain.ExecutionClass.DESIGN,
                    tier=tier,
                )
                self.assert_violation(
                    result, "delegated-assignment-below-role-tier-floor"
                )

    def test_high_risk_implementation_assignments_require_deep_review(self) -> None:
        for stage, execution_class in (
            (domain.Stage.IMPLEMENT, domain.ExecutionClass.PRESCRIPTIVE),
            (domain.Stage.BOUNDED_DELEGATE, domain.ExecutionClass.BOUNDED),
        ):
            with self.subTest(stage=stage):
                quick = evaluate(
                    domain.Workflow.TASK,
                    stage,
                    domain.Role.IMPLEMENTER,
                    execution_class=execution_class,
                    risk=domain.Risk.HIGH,
                    tier=domain.LogicalTier.STANDARD,
                    review_depth=domain.ReviewDepth.QUICK,
                )
                self.assert_violation(quick, "high-risk-review-requires-deep-depth")
                deep = evaluate(
                    domain.Workflow.TASK,
                    stage,
                    domain.Role.IMPLEMENTER,
                    execution_class=execution_class,
                    risk=domain.Risk.HIGH,
                    tier=domain.LogicalTier.STANDARD,
                    review_depth=domain.ReviewDepth.DEEP,
                )
                self.assertTrue(deep.admissible, deep.violations)

    def test_high_risk_review_and_approval_require_deep_depth(self) -> None:
        quick_review = evaluate(
            domain.Workflow.TASK,
            domain.Stage.REVIEW,
            domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            risk=domain.Risk.HIGH,
            review_depth=domain.ReviewDepth.QUICK,
        )
        self.assert_violation(quick_review, "high-risk-review-requires-deep-depth")
        deep_review = evaluate(
            domain.Workflow.TASK,
            domain.Stage.REVIEW,
            domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            risk=domain.Risk.HIGH,
            review_depth=domain.ReviewDepth.DEEP,
        )
        self.assertTrue(deep_review.admissible, deep_review.violations)

        claims = capabilities.CapabilityClaims(
            mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
        )
        quick_approval = evaluate(
            domain.Workflow.TASK,
            domain.Stage.GATE,
            domain.Role.IMPLEMENTER,
            claims=claims,
            risk=domain.Risk.HIGH,
            review_depth=domain.ReviewDepth.QUICK,
            gate=domain.Gate.APPROVAL,
        )
        self.assert_violation(quick_approval, "high-risk-review-requires-deep-depth")
        deep_approval = evaluate(
            domain.Workflow.TASK,
            domain.Stage.GATE,
            domain.Role.IMPLEMENTER,
            claims=claims,
            risk=domain.Risk.HIGH,
            review_depth=domain.ReviewDepth.DEEP,
            gate=domain.Gate.APPROVAL,
        )
        self.assertTrue(deep_approval.admissible, deep_approval.violations)

    def test_final_policy_requires_whole_branch_reviewer_scope(self) -> None:
        claims = capabilities.CapabilityClaims(
            mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
        )
        common = {
            "tier": domain.LogicalTier.HIGH,
            "review_depth": domain.ReviewDepth.DEEP,
            "claims": claims,
        }
        iteration = evaluate(
            domain.Workflow.TASK,
            domain.Stage.FINAL,
            domain.Role.REVIEWER,
            review_scope=domain.ReviewScope.ITERATION,
            **common,
        )
        self.assert_violation(iteration, "final-requires-whole-branch-review")
        whole_branch = evaluate(
            domain.Workflow.TASK,
            domain.Stage.FINAL,
            domain.Role.REVIEWER,
            review_scope=domain.ReviewScope.WHOLE_BRANCH,
            **common,
        )
        self.assertTrue(whole_branch.admissible, whole_branch.violations)

    def test_advisory_is_non_executing_and_read_only(self) -> None:
        self.assertTrue(
            evaluate(
                domain.Workflow.ADVISORY, domain.Stage.RESEARCH, domain.Role.RESEARCHER
            ).admissible
        )
        self.assert_violation(
            evaluate(
                domain.Workflow.ADVISORY,
                domain.Stage.IMPLEMENT,
                domain.Role.IMPLEMENTER,
            ),
            "advisory-workflow-does-not-execute",
        )
        write = evaluate(
            domain.Workflow.ADVISORY,
            domain.Stage.GATE,
            domain.Role.ARCHITECT,
            effect=domain.CapabilityEffect.REPOSITORY_WRITE,
        )
        self.assert_violation(write, "advisory-workflow-is-read-only")

    def test_standalone_review_is_findings_only(self) -> None:
        claims = capabilities.CapabilityClaims(
            mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
        )
        findings = evaluate(
            domain.Workflow.REVIEW,
            domain.Stage.REVIEW,
            domain.Role.REVIEWER,
            tier=domain.LogicalTier.HIGH,
            review_scope=domain.ReviewScope.STANDALONE,
        )
        self.assertTrue(findings.admissible, findings.violations)
        approval = evaluate(
            domain.Workflow.REVIEW,
            domain.Stage.REVIEW,
            domain.Role.REVIEWER,
            claims=claims,
            tier=domain.LogicalTier.HIGH,
            review_scope=domain.ReviewScope.STANDALONE,
            gate=domain.Gate.APPROVAL,
        )
        self.assert_violation(approval, "standalone-review-is-findings-only")
        self.assertIn("approval-not-admissible-for-workflow", approval.violations)

    def test_review_scope_matches_workflow(self) -> None:
        for scope in (domain.ReviewScope.ITERATION, domain.ReviewScope.WHOLE_BRANCH):
            result = evaluate(
                domain.Workflow.REVIEW,
                domain.Stage.REVIEW,
                domain.Role.REVIEWER,
                tier=domain.LogicalTier.HIGH,
                review_scope=scope,
            )
            self.assert_violation(result, "standalone-review-requires-standalone-scope")

        for workflow in (domain.Workflow.TASK, domain.Workflow.MILESTONE):
            standalone = evaluate(
                workflow,
                domain.Stage.REVIEW,
                domain.Role.REVIEWER,
                tier=domain.LogicalTier.HIGH,
                review_scope=domain.ReviewScope.STANDALONE,
            )
            self.assert_violation(
                standalone, "task-or-milestone-review-requires-scoped-review"
            )
            for scope in (
                domain.ReviewScope.ITERATION,
                domain.ReviewScope.WHOLE_BRANCH,
            ):
                scoped = evaluate(
                    workflow,
                    domain.Stage.REVIEW,
                    domain.Role.REVIEWER,
                    tier=domain.LogicalTier.HIGH,
                    review_scope=scope,
                )
                self.assertTrue(scoped.admissible, scoped.violations)

    def test_repository_write_requires_enforced_capability(self) -> None:
        effect = domain.CapabilityEffect.REPOSITORY_WRITE
        action_fields = {
            "execution_class": domain.ExecutionClass.BOUNDED,
            "tier": domain.LogicalTier.STANDARD,
            "effect": effect,
        }
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
            with self.subTest(claim=label):
                result = evaluate(
                    domain.Workflow.TASK,
                    domain.Stage.IMPLEMENT,
                    domain.Role.IMPLEMENTER,
                    claims=claims,
                    **action_fields,
                )
                self.assertEqual(result.admissible, allowed)
                if not allowed:
                    self.assertIn(
                        "repository-write-capability-not-enforced", result.violations
                    )

    def test_external_write_and_destructive_effects_remain_unsupported(self) -> None:
        for effect in (
            domain.CapabilityEffect.EXTERNAL_WRITE,
            domain.CapabilityEffect.DESTRUCTIVE,
        ):
            claims = capabilities.CapabilityClaims(
                claims=(
                    capabilities.CapabilityClaim(
                        effect, capabilities.CapabilityStatus.ENFORCED
                    ),
                )
            )
            result = evaluate(
                domain.Workflow.TASK,
                domain.Stage.IMPLEMENT,
                domain.Role.IMPLEMENTER,
                claims=claims,
                effect=effect,
            )
            with self.subTest(effect=effect):
                self.assert_violation(
                    result, "external-write-or-destructive-effect-not-supported"
                )

    def test_read_only_roles_cannot_request_write_effects(self) -> None:
        effect = domain.CapabilityEffect.REPOSITORY_WRITE
        claims = capabilities.CapabilityClaims(
            claims=(
                capabilities.CapabilityClaim(
                    effect, capabilities.CapabilityStatus.ENFORCED
                ),
            )
        )
        cases = (
            (
                domain.Stage.RESEARCH,
                domain.Role.RESEARCHER,
                domain.LogicalTier.STANDARD,
            ),
            (domain.Stage.DESIGN, domain.Role.ARCHITECT, domain.LogicalTier.HIGH),
            (domain.Stage.REVIEW, domain.Role.REVIEWER, domain.LogicalTier.HIGH),
        )
        for stage, role, tier in cases:
            with self.subTest(role=role):
                result = evaluate(
                    domain.Workflow.TASK,
                    stage,
                    role,
                    claims=claims,
                    tier=tier,
                    effect=effect,
                )
                self.assert_violation(result, "read-only-role-effect-must-be-read-only")

    def test_approval_and_final_require_enforced_mutation_free_reviewer(self) -> None:
        cases = (
            ("missing", None, False),
            ("unknown", capabilities.CapabilityStatus.UNKNOWN, False),
            ("advisory", capabilities.CapabilityStatus.ADVISORY, False),
            ("unsupported", capabilities.CapabilityStatus.UNSUPPORTED, False),
            ("enforced", capabilities.CapabilityStatus.ENFORCED, True),
        )
        actions = (
            (
                domain.Stage.GATE,
                domain.Role.IMPLEMENTER,
                {"gate": domain.Gate.APPROVAL},
            ),
            (
                domain.Stage.FINAL,
                domain.Role.REVIEWER,
                {
                    "tier": domain.LogicalTier.HIGH,
                    "review_depth": domain.ReviewDepth.DEEP,
                    "review_scope": domain.ReviewScope.WHOLE_BRANCH,
                },
            ),
        )
        for workflow in (domain.Workflow.TASK, domain.Workflow.MILESTONE):
            for stage, role, fields in actions:
                for label, status, allowed in cases:
                    claims = (
                        capabilities.CapabilityClaims()
                        if status is None
                        else capabilities.CapabilityClaims(
                            mutation_free_reviewer=status
                        )
                    )
                    with self.subTest(workflow=workflow, stage=stage, claim=label):
                        result = evaluate(
                            workflow, stage, role, claims=claims, **fields
                        )
                        self.assertEqual(result.admissible, allowed)
                        if not allowed:
                            self.assertIn(
                                "reviewer-mutation-free-capability-not-enforced",
                                result.violations,
                            )

    def test_human_approval_and_side_effect_gates_are_distinct(self) -> None:
        human_gate = evaluate(
            domain.Workflow.TASK,
            domain.Stage.GATE,
            domain.Role.IMPLEMENTER,
            gate=domain.Gate.HUMAN_DECISION,
        )
        self.assertTrue(human_gate.admissible, human_gate.violations)

        reviewer_claim = capabilities.CapabilityClaims(
            mutation_free_reviewer=capabilities.CapabilityStatus.ENFORCED
        )
        reviewer_approval = evaluate(
            domain.Workflow.TASK,
            domain.Stage.GATE,
            domain.Role.IMPLEMENTER,
            claims=reviewer_claim,
            gate=domain.Gate.APPROVAL,
        )
        self.assertTrue(reviewer_approval.admissible, reviewer_approval.violations)

        effect = domain.CapabilityEffect.REPOSITORY_WRITE
        effect_claim = capabilities.CapabilityClaims(
            claims=(
                capabilities.CapabilityClaim(
                    effect, capabilities.CapabilityStatus.ENFORCED
                ),
            )
        )
        side_effect = evaluate(
            domain.Workflow.TASK,
            domain.Stage.GATE,
            domain.Role.IMPLEMENTER,
            claims=effect_claim,
            effect=effect,
            gate=domain.Gate.SIDE_EFFECT,
        )
        self.assertTrue(side_effect.admissible, side_effect.violations)
        self.assert_violation(
            evaluate(
                domain.Workflow.TASK,
                domain.Stage.GATE,
                domain.Role.IMPLEMENTER,
                effect=effect,
                gate=domain.Gate.SIDE_EFFECT,
            ),
            "side-effect-capability-not-enforced",
        )

    def test_policy_evaluation_derives_admissibility(self) -> None:
        admissible = domain.PolicyEvaluation()
        blocked = domain.PolicyEvaluation(("blocked",))

        self.assertTrue(admissible.admissible)
        self.assertFalse(blocked.admissible)
        self.assertEqual(
            {field.name for field in dataclasses.fields(domain.PolicyEvaluation)},
            {"violations"},
        )
        self.assertIn("PolicyEvaluation", domain.__all__)

    def test_invalid_policy_inputs_fail_closed(self) -> None:
        action = domain.ProposedAction(
            stage=domain.Stage.IMPLEMENT, role=domain.Role.IMPLEMENTER
        )
        result = policy.evaluate_action_policy(
            "task", action, capabilities.CapabilityClaims()
        )
        self.assert_violation(result, "invalid-policy-input")

    def test_policy_api_has_no_run_state_or_runtime_profile_inputs(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(policy.evaluate_action_policy).parameters),
            ("workflow", "action", "capabilities"),
        )
        runtime_fields = {"model", "model_id", "provider", "profile", "profile_id"}
        for record in (domain.RunState, domain.ProposedAction):
            fields = {field.name for field in dataclasses.fields(record)}
            self.assertTrue(fields.isdisjoint(runtime_fields))
        self.assertTrue(dataclasses.is_dataclass(domain.PolicyEvaluation))


if __name__ == "__main__":
    unittest.main()
