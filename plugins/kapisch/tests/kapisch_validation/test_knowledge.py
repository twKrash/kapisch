from __future__ import annotations

import tomllib
import unittest

from kapisch_validation.knowledge import render_knowledge_records


class KnowledgeTests(unittest.TestCase):
    def test_ledger_v1_preserves_history_and_sorts_only_applicability(self) -> None:
        records = [
            {
                "id": "D-001", "kind": "decision", "scope": "task:vector",
                "authority": "binding", "status": "verified",
                "statement": "Bytes stay exact.", "source": "01-plan.md",
                "verified_at_revision": "abc1234", "applies_when": ["zeta", "alpha", "zeta"],
            },
            {
                "id": "P-002", "kind": "pitfall", "scope": "repository",
                "authority": "advisory", "status": "candidate",
                "statement": "Do not normalize evidence.", "source": "03-review.md",
                "applies_when": [],
            },
        ]
        parsed = tomllib.loads(render_knowledge_records({"version": 1, "records": records}).decode("utf-8"))
        self.assertEqual([record["id"] for record in parsed["records"]], ["D-001", "P-002"])
        self.assertEqual(parsed["records"][0]["applies_when"], ["alpha", "zeta"])
        self.assertNotEqual(
            render_knowledge_records({"version": 1, "records": records}),
            render_knowledge_records({"version": 1, "records": list(reversed(records))}),
        )

    def test_ledger_v1_rejects_unknown_incomplete_or_contradictory_records(self) -> None:
        base = {
            "id": "D-001", "kind": "decision", "scope": "repository",
            "authority": "binding", "status": "verified", "statement": "x",
            "source": "01-plan.md", "applies_when": [],
        }
        for invalid in (
            dict(base, unknown="x"),
            {key: value for key, value in base.items() if key != "source"},
            dict(base, status="superseded"),
            dict(base, kind="shortcut"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                render_knowledge_records({"version": 1, "records": [invalid]})

    def test_optional_fields_extensions_and_conditional_fields(self) -> None:
        raw = {
            "version": 1,
            "records": [{
                "id": "S-001", "kind": "shortcut", "scope": "workflow:kapisch",
                "authority": "advisory", "status": "expired", "statement": "Use it.",
                "source": "x.md", "applies_when": [], "expires_at_revision": "deadbeef",
                "preconditions": ["one"], "forbidden_cases": ["two"],
                "required_verification": ["three"], "fallback_behavior": "normal flow",
                "extensions": {"com.example": {"z": 1, "a": "x"}},
            }],
            "extensions": {"org.example": {"enabled": True}},
        }
        parsed = tomllib.loads(render_knowledge_records(raw).decode())
        self.assertEqual(parsed["records"][0]["required_verification"], ["three"])
        self.assertEqual(parsed["extensions"]["org.example"]["enabled"], True)

    def test_explicit_null_extensions_are_rejected(self) -> None:
        record = {
            "id": "D-001", "kind": "decision", "scope": "repository",
            "authority": "binding", "status": "verified", "statement": "x",
            "source": "01-plan.md", "applies_when": [],
        }
        with self.assertRaises(ValueError):
            render_knowledge_records({"version": 1, "records": [], "extensions": None})
        with self.assertRaises(ValueError):
            render_knowledge_records(
                {"version": 1, "records": [dict(record, extensions=None)]}
            )
        self.assertEqual(
            render_knowledge_records({"version": 1, "records": []}),
            render_knowledge_records(
                {"version": 1, "records": [], "extensions": {}}
            ),
        )


if __name__ == "__main__":
    unittest.main()
