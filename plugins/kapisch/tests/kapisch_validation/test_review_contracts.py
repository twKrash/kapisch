from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def contract(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class ReviewContractTests(unittest.TestCase):
    def test_blocking_findings_are_causal_to_the_bound_diff(self) -> None:
        review = contract("skills/kapisch/references/review.md")
        profile = contract("agents/kapisch-reviewer.toml")
        scenarios = contract("skills/kapisch/references/pressure-scenarios.md")

        for relationship in (
            "introduced",
            "exposed",
            "newly reachable",
            "made unsafe",
        ):
            self.assertIn(f"`{relationship}`", review)
        self.assertIn("review.md", profile)

        self.assertIn("Every blocking finding must state", review)
        self.assertIn("Unchanged repository material may prove a finding", review)
        self.assertIn("An unrelated pre-existing defect is an observation", review)
        self.assertIn("is not automatically `material-scope-expansion`", review)

        iteration_start = review.index("An **iteration review** is bound")
        whole_branch_start = review.index("A **whole-branch review**")
        iteration_scope = " ".join(review[iteration_start:whole_branch_start].split())
        self.assertIn(
            "A pre-existing defect is in scope when the bound diff invokes it",
            iteration_scope,
        )
        self.assertIn("not automatically `material-scope-expansion`", iteration_scope)
        self.assertNotIn(
            "If one is blocking for the iteration's safety", iteration_scope
        )

        self.assertIn("New code reaches a pre-existing defective path", scenarios)
        self.assertIn("Unrelated pre-existing defect", scenarios)

    def test_discovery_precedes_question_driven_retrieval_and_depth_is_incremental(
        self,
    ) -> None:
        review = contract("skills/kapisch/references/review.md")
        risk = contract("skills/kapisch/references/risk.md")
        context_packages = contract("skills/kapisch/references/context-packages.md")
        profile = contract("agents/kapisch-reviewer.toml")
        scenarios = contract("skills/kapisch/references/pressure-scenarios.md")
        risk_normalized = " ".join(risk.split())

        self.assertLess(
            review.index("### Mandatory discovery"),
            review.index("### Question-driven retrieval"),
        )
        for required in (
            "every changed hunk",
            "initial caller/consumer",
            "material review question",
            "Do not apply hard file, reference, tool-call, or token caps",
        ):
            self.assertIn(required, review)

        for depth in ("### Quick", "### Standard", "### Deep"):
            self.assertIn(depth, risk)
        self.assertIn("Standard adds to quick", risk)
        self.assertIn("Deep adds to standard", risk)
        self.assertIn("The controller resolves risk, depth, and active lenses", risk)
        self.assertIn("cannot replace mandatory discovery", context_packages)
        for required in (
            "Quick is valid only when there is no production behavior",
            "Standard adds to quick: trace directly affected callers and consumers",
            "Deep adds to standard: apply every active lens",
            "produce required Behavioral branch and Invariant evidence matrices",
            "a quick review still blocks discovered P0/P1 defects",
        ):
            self.assertIn(required, risk_normalized)

        self.assertIn("reviewer-baseline.md", profile)
        self.assertIn("review.md", profile)
        self.assertIn("risk.md", profile)
        self.assertIn("authorization migration", scenarios)
        self.assertIn("without a material review question", scenarios)

    def test_raised_risk_recomputes_derived_lenses(self) -> None:
        risk = " ".join(contract("skills/kapisch/references/risk.md").split())
        profile = " ".join(contract("agents/kapisch-reviewer.toml").split())
        scenarios = " ".join(
            contract("skills/kapisch/references/pressure-scenarios.md").split()
        )

        for required in (
            "When mandatory discovery reveals a trigger, recompute derived lenses from all discovered triggers whenever `focus=auto` is enabled, even when risk and depth remain unchanged",
            "union them with controller-supplied active lenses and any explicit additions",
            "With explicit-only focus, preserve exactly named optional lenses",
            "mandatory method triggers still apply regardless of focus",
        ):
            self.assertIn(required, risk)

        self.assertIn("reviewer-baseline.md", profile)

        self.assertIn(
            "`focus=auto` is enabled and discovery reveals a same-level trigger",
            scenarios,
        )
        self.assertIn(
            "Explicit-only `focus=security,permissions` is active and discovery reveals a migration trigger",
            scenarios,
        )

    def test_semantic_bundles_remain_internal_to_one_review(self) -> None:
        review = contract("skills/kapisch/references/review.md")
        profile = contract("agents/kapisch-reviewer.toml")
        scenarios = contract("skills/kapisch/references/pressure-scenarios.md")

        for invariant in (
            "optional reviewer-internal organization",
            "Each changed file belongs to exactly one primary bundle",
            "one global cross-bundle pass",
            "one reviewer invocation",
            "stales the complete review",
            "No separate artifact or schema is created",
        ):
            self.assertIn(invariant, review)

        self.assertIn("producer/consumer or import/dependency edges", review)
        self.assertIn("lexical repository path", review)
        self.assertIn("Never dispatch one reviewer per bundle", profile)
        self.assertIn("one root-cause finding", scenarios)
        self.assertIn("stales the complete review", scenarios)

    def test_role_contracts_separate_review_findings_from_human_authority(self) -> None:
        plugin_role = contract("roles/reviewer.md")
        core_role_path = ROOT.parents[1] / "core/contracts/roles/reviewer.md"
        roles = [plugin_role]
        if core_role_path.is_file():
            roles.append(core_role_path.read_text(encoding="utf-8"))
        for role in roles:
            self.assertNotIn("only this role can provide independent approval", role)
            self.assertIn("findings are not human approval", role.lower())
            self.assertIn("references/reviewer-baseline.md", role)

    def test_external_methodology_is_required_only_for_standalone_review(self) -> None:
        profile = contract("agents/kapisch-reviewer.toml").lower()
        role = contract("roles/reviewer.md").lower()
        for source_name, text in (("profile", profile), ("role", role)):
            standalone_index = text.index("review_mode=standalone")
            baseline_index = text.index("reviewer-baseline.md")
            durable_index = text.index("durable workflow mode")
            with self.subTest(source=source_name):
                self.assertLess(standalone_index, baseline_index)
                self.assertLess(baseline_index, durable_index)
                durable_instructions = text[durable_index:]
                self.assertIn("do not require", durable_instructions)
                self.assertIn("external", durable_instructions)
                self.assertIn("durable", durable_instructions)

    def test_general_document_review_and_decision_challenge_are_baseline(self) -> None:
        review = contract("skills/kapisch/references/reviewer-baseline.md")
        profile = contract("agents/kapisch-reviewer.toml")
        for required in (
            "documentation-only",
            "cross-document",
            "without requiring a Git diff",
            "Decision Challenge",
            "implicit implementation decisions",
            "code, configuration, tests, or observed behavior",
            "does not authorize implementation",
        ):
            self.assertIn(required, review)
        self.assertIn("reviewer-baseline.md", profile)

    def test_method_selection_retrieves_new_triggers_without_loading_everything(
        self,
    ) -> None:
        review = contract("skills/kapisch/references/reviewer-baseline.md")
        for required in (
            "iterative method selection",
            "newly discovered material decisions",
            "load only the methods whose triggers apply",
            "ordinary file-reading and search tools",
            "User-requested focus supplements",
            "must not suppress mandatory review",
            "retrieve `severity.md`",
            "Do not silently omit",
        ):
            self.assertIn(required, review)

    def test_conditional_method_files_cover_their_triggered_analyses(self) -> None:
        method_root = "skills/kapisch/references/reviewer-methodologies/"
        required = {
            "semantic-consistency.md": (
                "contradictions",
                "terminology drift",
                "hidden assumptions",
            ),
            "dependencies-and-traceability.md": (
                "producers and consumers",
                "requirement-to-design",
                "verification obligations",
            ),
            "authority-and-ownership.md": (
                "sources of truth",
                "human authority",
                "data owner",
            ),
            "temporal-and-lifecycle-consistency.md": (
                "stale assumptions",
                "superseded decisions",
                "recovery",
            ),
            "proof-obligations-and-evidence-quality.md": (
                "unsupported claims",
                "negative",
                "what cannot be verified",
            ),
            "executability-feasibility-and-simplicity.md": (
                "circular dependencies",
                "unsupported capabilities",
                "same governing constraints",
            ),
        }
        for filename, checks in required.items():
            method = contract(method_root + filename).lower()
            for check in checks:
                self.assertIn(check.lower(), method, filename)

    def test_evaluation_oracles_are_separate_from_reviewer_target_inputs(self) -> None:
        fixture_root = ROOT / "tests/kapisch_validation/fixtures"
        targets = fixture_root / "reviewer-methodology/targets"
        oracles = fixture_root / "reviewer-methodology-oracles"
        target_cases = sorted(path for path in targets.iterdir() if path.is_dir())
        oracle_files = sorted(oracles.glob("*.md"))
        self.assertGreaterEqual(len(target_cases), 7)
        self.assertEqual(
            {case.name for case in target_cases},
            {path.stem for path in oracle_files},
        )
        for target in (path for case in target_cases for path in case.rglob("*")):
            if not target.is_file():
                continue
            content = target.read_text(encoding="utf-8").lower()
            self.assertNotIn("expected findings", content)
            self.assertNotIn("no-finding rationale", content)
            self.assertNotIn("oracle", content)
        self.assertTrue(all(path.parent == oracles for path in oracle_files))

    def test_mutation_method_is_conditional_and_covers_ownership_and_negatives(
        self,
    ) -> None:
        mutation = contract(
            "skills/kapisch/references/reviewer-methodologies/"
            "mutation-and-side-effect-justification.md"
        )
        for required in (
            "writes, updates, deletions",
            "state transitions",
            "external effects",
            "data and resource ownership",
            "cross-tenant",
            "unauthorized",
            "unrelated data",
            "negative",
        ):
            self.assertIn(required, mutation)

    def test_document_review_does_not_load_diff_specific_methods_by_default(
        self,
    ) -> None:
        review = contract("skills/kapisch/references/reviewer-baseline.md")
        for required in (
            "universal baseline",
            "documentation-only review",
            "target-specific methods",
            "diff-specific matrices only for code/change targets",
        ):
            self.assertIn(required, review)
        self.assertNotIn("load the full methodology collection", review)

    def test_reference_cases_separate_target_from_evaluation_oracle(self) -> None:
        case = contract(
            "tests/kapisch_validation/fixtures/reviewer-methodology/targets/"
            "correct-empty-findings/target.md"
        )
        oracle = contract(
            "tests/kapisch_validation/fixtures/reviewer-methodology-oracles/"
            "correct-empty-findings.md"
        )
        self.assertIn("never this oracle", oracle)
        self.assertIn("Expected: empty findings", oracle)
        for triggered in (
            "semantic consistency",
            "dependencies and traceability",
            "proof obligations and evidence quality",
            "executability, feasibility, and simplicity",
        ):
            self.assertIn(triggered, oracle.lower())
        self.assertIn("mutation and side-effect justification", oracle.lower())
        self.assertIn("not triggered", oracle.lower())
        self.assertNotIn("expected findings", case)
        self.assertNotIn("no-finding rationale", case)
        self.assertNotIn("oracle", case.lower())


    def test_reference_oracles_define_severity_calibration_outside_targets(self) -> None:
        cases = {
            "document-only": {
                "DOC-F1 — P1",
                "DOC-F2 — P1",
                "DOC-F3 — P2",
                "DOC-F4 — P2",
            },
            "code-regression": {"CODE-F1 — P1"},
        }
        for case_name, expected in cases.items():
            oracle = contract(
                "tests/kapisch_validation/fixtures/reviewer-methodology-oracles/"
                f"{case_name}.md"
            )
            target_root = (
                "tests/kapisch_validation/fixtures/reviewer-methodology/targets/"
                f"{case_name}"
            )
            target = "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted((ROOT / target_root).rglob("*"))
                if path.is_file()
            )
            for expectation in expected:
                self.assertIn(expectation, oracle)
                self.assertNotIn(expectation.split(" — ")[0], target)
            self.assertIn("severity.md", oracle)
            self.assertNotIn("evaluator oracle", target.lower())


if __name__ == "__main__":
    unittest.main()
