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


if __name__ == "__main__":
    unittest.main()
