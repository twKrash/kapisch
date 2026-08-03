from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from kapisch_validation.manifest import NODE, POLICIES, ROOT as MANIFEST_ROOT
from kapisch_validation.references import STATE
from kapisch_validation.review_evidence import ENVELOPE, LIFECYCLE_STATUSES
from kapisch_validation.transitions import ALLOWED


ROOT = Path(__file__).resolve().parents[2]
THEME_DIR = ROOT / "skills/kapisch/themes"

EXPECTED_KEYS = {
    "roles": {
        "architect",
        "researcher",
        "implementer",
        "implementer-lite",
        "mechanic",
        "reviewer",
    },
    "procedures": {
        "plan",
        "research",
        "implement",
        "mechanic",
        "review",
        "final",
        "resume",
    },
    "gates": {
        "material_scope",
        "architecture_choice",
        "review_fixes",
        "publication",
        "side_effect",
    },
    "statuses": set(ALLOWED) | LIFECYCLE_STATUSES,
}


def load_theme(name: str) -> dict[str, object]:
    with (THEME_DIR / f"{name}.toml").open("rb") as source:
        return tomllib.load(source)


class ThemeContractTests(unittest.TestCase):
    def test_bundled_themes_use_one_closed_vocabulary_shape(self) -> None:
        for name in ("default", "foundry"):
            with self.subTest(theme=name):
                theme = load_theme(name)
                self.assertEqual(
                    set(theme),
                    {"version", "id", "display_name", "description", "vocabulary"},
                )
                self.assertEqual(theme["version"], 1)
                self.assertEqual(theme["id"], name)
                self.assertIsInstance(theme["display_name"], str)
                self.assertTrue(theme["display_name"])
                self.assertIsInstance(theme["description"], str)
                self.assertTrue(theme["description"])
                vocabulary = theme["vocabulary"]
                self.assertIsInstance(vocabulary, dict)
                self.assertEqual(set(vocabulary), set(EXPECTED_KEYS))
                for section, expected in EXPECTED_KEYS.items():
                    labels = vocabulary[section]
                    self.assertIsInstance(labels, dict)
                    self.assertEqual(set(labels), expected)
                    self.assertTrue(
                        all(isinstance(label, str) and label for label in labels.values())
                    )

    def test_foundry_is_a_distinct_label_layer(self) -> None:
        default = load_theme("default")["vocabulary"]
        foundry = load_theme("foundry")["vocabulary"]
        for section in EXPECTED_KEYS:
            with self.subTest(section=section):
                self.assertEqual(set(default[section]), set(foundry[section]))
                self.assertTrue(
                    all(
                        default[section][key] != foundry[section][key]
                        for key in EXPECTED_KEYS[section]
                    )
                )

    def test_theme_is_not_a_normative_artifact_field(self) -> None:
        for schema in (MANIFEST_ROOT, POLICIES, NODE, STATE, ENVELOPE):
            self.assertNotIn("theme", schema)
        contract = (
            ROOT / "skills/kapisch/references/themes.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(contract.split())
        for invariant in (
            "logical role IDs",
            "workflow shape, routing, risk, review depth",
            "permissions, approval gates",
            "paths, artifact schemas, field names, field values",
            "validator behavior, errors, or exit status",
            "Localization is a separate rendering step",
        ):
            self.assertIn(invariant, normalized)

    def test_request_normalization_removes_theme_before_semantic_routing(self) -> None:
        normalization = " ".join(
            (ROOT / "skills/kapisch/references/request-normalization.md")
            .read_text(encoding="utf-8")
            .split()
        )
        self.assertIn("`theme` is the sole presentation-only control", normalization)
        self.assertIn("removed from semantic normalization", normalization)
        self.assertIn("same workflow semantics", normalization)


if __name__ == "__main__":
    unittest.main()
