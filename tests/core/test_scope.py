from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "core/schemas/v3"


def schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.json").read_text())


class GlobalAuthoritySchemaTests(unittest.TestCase):
    def test_scope_descriptor_and_applicability_are_closed(self) -> None:
        s = schema("scope")
        self.assertEqual(
            set(s["required"]),
            {
                "protocol_version",
                "scope_contract",
                "origin_run_id",
                "scope_id",
                "requirements",
                "applicability",
            },
        )
        self.assertIs(s["additionalProperties"], False)
        self.assertEqual(
            s["properties"]["scope_contract"]["const"], "applicability-scope/1"
        )
        applicability = s["properties"]["applicability"]["oneOf"]
        self.assertEqual(set(applicability[0]["properties"]), {"mode"})
        self.assertEqual(applicability[1]["properties"]["keys"]["minItems"], 1)
        self.assertTrue(applicability[1]["properties"]["keys"]["uniqueItems"])

    def test_human_action_claim_projects_exact_identity_receipt_and_target(
        self,
    ) -> None:
        s = schema("human-action")
        self.assertIs(s["additionalProperties"], False)
        self.assertEqual(
            set(s["properties"]["identity"]["properties"]),
            {"session_namespace", "session_id", "action_id"},
        )
        self.assertIs(s["properties"]["identity"]["additionalProperties"], False)
        self.assertEqual(
            set(s["properties"]["gate_target"]["properties"]),
            {"run_id", "gate_id", "identity", "target", "scope_digest"},
        )
        self.assertEqual(
            s["properties"]["approved_target_sha256"],
            {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
        )
        receipt = s["properties"]["receipt"]
        self.assertEqual(
            set(receipt["required"]),
            {
                "origin",
                "session_namespace",
                "session_id",
                "action_id",
                "run_id",
                "gate_id",
                "identity",
                "target",
                "scope_digest",
                "text_digest",
                "observed_at",
            },
        )
        identity = receipt["properties"]["identity"]
        self.assertEqual(set(identity["required"]), {"kind", "id"})
        self.assertEqual(
            identity["properties"]["kind"]["enum"], ["decision", "plan", "effect"]
        )
        self.assertEqual(
            identity["properties"]["id"], {"type": "string", "minLength": 1}
        )
        self.assertIs(identity["additionalProperties"], False)
        self.assertIs(receipt["additionalProperties"], False)
        self.assertNotIn("decision_id", receipt["properties"])

    def test_approval_owns_payload_record_and_closed_subjects(self) -> None:
        s = schema("approval")
        self.assertEqual(
            set(s["required"]),
            {
                "protocol_version",
                "approval_contract",
                "approval_id",
                "payload",
                "approved_target_sha256",
                "human_authority",
            },
        )
        self.assertFalse(s["additionalProperties"])
        self.assertEqual(
            s["properties"]["payload"], {"$ref": "#/$defs/gate_approval_payload"}
        )
        payload = s["$defs"]["gate_approval_payload"]
        self.assertEqual(
            set(payload["required"]),
            {
                "protocol_version",
                "gate_contract",
                "run_id",
                "gate_id",
                "identity",
                "scope_digest",
                "gate_kind",
                "subject",
            },
        )
        self.assertFalse(payload["additionalProperties"])
        self.assertEqual(payload["properties"]["subject"], {"$ref": "#/$defs/subject"})
        self.assertNotIn("$defs", payload)
        variants = s["$defs"]["subject"]["oneOf"]
        self.assertEqual(
            set(variants[0]["properties"]),
            {
                "acceptance_contract",
                "origin_run_id",
                "snapshot_id",
                "decision_id",
                "decision",
                "scope_ref",
                "applicability",
                "bundle_digest",
                "source_dependencies",
                "authority_basis",
                "amends",
                "supersedes",
            },
        )
        self.assertEqual(
            set(variants[1]["properties"]),
            {"plan_ref", "plan_sha256", "authority_basis"},
        )
        self.assertEqual(
            set(variants[2]["properties"]),
            {"effect_identity", "effect_classification", "effect_request_sha256"},
        )

    def test_snapshot_owns_acceptance_envelope(self) -> None:
        s = schema("snapshot")
        self.assertEqual(
            set(s["required"]),
            {
                "acceptance_contract",
                "origin_run_id",
                "snapshot_id",
                "gate_approval_ref",
            },
        )
        self.assertFalse(s["additionalProperties"])

    def test_run_backlinks_are_closed_and_non_authoritative(self) -> None:
        s = schema("run")
        plan = s["$defs"]["plan_ref"]
        self.assertEqual(
            set(plan["required"]),
            {"plan_id", "path", "plan_sha256", "gate_approval_ref"},
        )
        self.assertEqual(
            set(s["$defs"]["scope_descriptor_ref"]["properties"]),
            {"origin_run_id", "scope_id", "sha256"},
        )

    def test_gate_kind_binds_identity_and_subject_variant(self) -> None:
        approval = schema("approval")
        payload = approval["$defs"]["gate_approval_payload"]
        conditions = {
            clause["if"]["properties"]["gate_kind"]["const"]: clause["then"]
            for clause in payload["allOf"]
        }
        self.assertEqual(
            set(conditions),
            {"repository-decision", "plan-approval", "side-effect-permission"},
        )
        for gate_kind, identity_kind, subject_index in (
            ("repository-decision", "decision", 0),
            ("plan-approval", "plan", 1),
            ("side-effect-permission", "effect", 2),
        ):
            with self.subTest(gate_kind=gate_kind):
                then = conditions[gate_kind]
                self.assertEqual(
                    then["properties"]["identity"]["properties"]["kind"]["const"],
                    identity_kind,
                )
                subject_key = ("acceptance_contract", "plan_ref", "effect_identity")[
                    subject_index
                ]
                self.assertEqual(
                    then["properties"]["subject"]["required"], [subject_key]
                )
        self.assertEqual(
            approval["properties"]["payload"], {"$ref": "#/$defs/gate_approval_payload"}
        )


#
