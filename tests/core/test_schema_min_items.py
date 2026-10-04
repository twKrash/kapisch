from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from kapisch_core._validation_schema import _validate_schema
from kapisch_core.bundle import verify_bundle

ROOT = Path(__file__).resolve().parents[2]


class MinimumArrayLengthValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data = (ROOT / "core/dist/core-bundle.json").read_bytes()
        cls.bundle = verify_bundle(data, hashlib.sha256(data).hexdigest())

    def test_scope_keys_require_at_least_one_unique_key(self) -> None:
        descriptor = {
            "protocol_version": 3,
            "scope_contract": "applicability-scope/1",
            "origin_run_id": "run",
            "scope_id": "scope",
            "requirements": "review this scope",
            "applicability": {"mode": "keys", "keys": ["alpha"]},
        }
        self.assertIsNone(_validate_schema(descriptor, "scope", self.bundle))

        descriptor["applicability"]["keys"] = []
        with self.assertRaises(ValueError):
            _validate_schema(descriptor, "scope", self.bundle)

        descriptor["applicability"]["keys"] = ["alpha", "alpha"]
        with self.assertRaises(ValueError):
            _validate_schema(descriptor, "scope", self.bundle)

    def test_approval_subject_and_authority_bindings_enforce_minimum_items(
        self,
    ) -> None:
        digest = "a" * 64
        scope_ref = {"origin_run_id": "origin", "scope_id": "scope", "sha256": digest}
        applicability = {"mode": "keys", "keys": ["alpha"]}
        authority_binding = {
            "origin_run_id": "origin",
            "snapshot_id": "snapshot",
            "decision_id": "decision",
            "acceptance_record_sha256": "b" * 64,
            "scope_ref": scope_ref,
            "applicability": applicability,
            "source_dependencies": [],
        }
        payload = {
            "protocol_version": 3,
            "gate_contract": "human-gate/1",
            "run_id": "run",
            "gate_id": "gate",
            "identity": {"kind": "decision", "id": "decision"},
            "scope_digest": digest,
            "gate_kind": "repository-decision",
            "subject": {
                "acceptance_contract": "global-authority/1",
                "origin_run_id": "origin",
                "snapshot_id": "snapshot",
                "decision_id": "decision",
                "decision": "approve",
                "scope_ref": scope_ref,
                "applicability": applicability,
                "bundle_digest": "c" * 64,
                "source_dependencies": [],
                "authority_basis": [authority_binding],
                "amends": [],
                "supersedes": [],
            },
        }
        record = {
            "protocol_version": 3,
            "approval_contract": "human-gate-approval/1",
            "approval_id": "ga-" + "d" * 64,
            "payload": payload,
            "approved_target_sha256": "e" * 64,
            "human_authority": {
                "kind": "external-artifact",
                "path": ".kapisch/v3/authority/human-artifacts/approval.json",
                "sha256": "f" * 64,
            },
        }
        self.assertIsNone(_validate_schema(record, "approval", self.bundle))

        payload["subject"]["applicability"]["keys"] = []
        with self.assertRaises(ValueError):
            _validate_schema(record, "approval", self.bundle)

        payload["subject"]["applicability"]["keys"] = ["alpha"]
        payload["subject"]["authority_basis"][0]["applicability"]["keys"] = []
        with self.assertRaises(ValueError):
            _validate_schema(record, "approval", self.bundle)

        payload["subject"]["authority_basis"][0]["applicability"]["keys"] = [
            "alpha",
            "alpha",
        ]
        with self.assertRaises(ValueError):
            _validate_schema(record, "approval", self.bundle)


if __name__ == "__main__":
    unittest.main()
