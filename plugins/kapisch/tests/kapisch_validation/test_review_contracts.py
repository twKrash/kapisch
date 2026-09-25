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
            self.assertIn(relationship, profile)

        self.assertIn("Every blocking finding must state", review)
        self.assertIn("Unchanged repository material may prove a finding", review)
        self.assertIn("An unrelated pre-existing defect is an observation", review)
        self.assertIn("is not automatically `material-scope-expansion`", review)
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
        self.assertIn("question-driven", profile)
        self.assertIn("authorization migration", scenarios)
        self.assertIn("without a material review question", scenarios)

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


if __name__ == "__main__":
    unittest.main()

    unittest.main()
