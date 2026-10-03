import json
import unittest
from dataclasses import replace
from pathlib import Path

from kapisch_core.authority import GateTarget, HumanActionOrigin, ObservedHumanAction, bind_human_receipt


class HumanReceiptTests(unittest.TestCase):
    def test_controller_gate_blocks_without_external_artifact_input(self):
        from kapisch_core.authority import ExternalArtifactInput, ExternalInputSource, bind_external_human_artifact
        target = GateTarget("run-1", "gate-2", "decision-1", "plan-3", "a" * 64)
        artifact = ExternalArtifactInput("approval.json", b'{"decision":"approve"}', ExternalInputSource.EXTERNALLY_SUPPLIED)
        evidence = bind_external_human_artifact(artifact, target)
        self.assertEqual(evidence.kind, "external-human-artifact")
        retained = json.loads(evidence.identifier)
        self.assertEqual(retained["reference"], artifact.reference)
        self.assertEqual(retained["run_id"], target.run_id)
        self.assertEqual(retained["gate_id"], target.gate_id)
        self.assertEqual(retained["decision_id"], target.decision_id)
        self.assertEqual(retained["target"], target.target)
        self.assertEqual(retained["scope_digest"], target.scope_digest)
        import hashlib
        self.assertEqual(retained["sha256"], hashlib.sha256(artifact.exact_bytes).hexdigest())
        envelope = {"protocol_version": 3, "approval_id": "a", "run_id": "run-1", "gate": "human-decision", "decision_id": "decision-1", "decision": "approve", "target": "plan-3", "scope_digest": "a" * 64, "source": {}}
        with self.assertRaises(ValueError):
            bind_external_human_artifact(replace(artifact, exact_bytes=json.dumps(envelope).encode()), target)
        with self.assertRaises(ValueError):
            bind_external_human_artifact(replace(artifact, source="controller"), target)
        with self.assertRaises(TypeError):
            bind_external_human_artifact(object(), target)

    def test_external_artifact_rejects_invalid_scope_digests(self):
        from kapisch_core.authority import ExternalArtifactInput, ExternalInputSource, bind_external_human_artifact
        artifact = ExternalArtifactInput("approval.json", b"bytes", ExternalInputSource.EXTERNALLY_SUPPLIED)
        for digest in ("", "a" * 63, "A" * 64, "g" * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                bind_external_human_artifact(artifact, GateTarget("run", "gate", "decision", "target", digest))

    def test_external_artifact_binds_bytes_with_oversized_json_integer(self):
        import hashlib
        from kapisch_core.authority import ExternalArtifactInput, ExternalInputSource, bind_external_human_artifact
        exact_bytes = b'{"value":' + b"9" * 5000 + b"}"
        artifact = ExternalArtifactInput("approval.json", exact_bytes, ExternalInputSource.EXTERNALLY_SUPPLIED)
        target = GateTarget("run", "gate", "decision", "target", "a" * 64)
        evidence = bind_external_human_artifact(artifact, target)
        self.assertEqual(json.loads(evidence.identifier)["sha256"], hashlib.sha256(exact_bytes).hexdigest())

    def test_external_artifact_integer_parsing_ignores_runtime_digit_limit(self):
        import hashlib
        import sys
        from kapisch_core.authority import ExternalArtifactInput, ExternalInputSource, bind_external_human_artifact
        previous_limit = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(640)
            exact_bytes = b'{"value":' + b"9" * 1000 + b"}"
            artifact = ExternalArtifactInput("approval.json", exact_bytes, ExternalInputSource.EXTERNALLY_SUPPLIED)
            target = GateTarget("run", "gate", "decision", "target", "a" * 64)
            bound = bind_external_human_artifact(artifact, target)
            self.assertEqual(json.loads(bound.identifier)["sha256"], hashlib.sha256(exact_bytes).hexdigest())
            envelope = b'{"protocol_version":3,"approval_id":"a","run_id":"run","gate":"human-decision","decision_id":"decision","decision":"approve","target":"target","scope_digest":"' + b"a" * 64 + b'","source":{},"irrelevant":' + b"9" * 1000 + b"}"
            with self.assertRaisesRegex(ValueError, "controller-produced approval"):
                bind_external_human_artifact(replace(artifact, exact_bytes=envelope), target)
        finally:
            sys.set_int_max_str_digits(previous_limit)

    def test_host_receipt_binds_session_local_id_and_target(self):
        receipt = ObservedHumanAction(HumanActionOrigin.INBOUND_HUMAN, "session-message-7", "session-1", "run-1", "gate-2", "decision-1", "plan-3", "a" * 64, "b" * 64, "2026-09-29T12:00:00Z")
        target = GateTarget("run-1", "gate-2", "decision-1", "plan-3", "a" * 64)
        evidence = bind_human_receipt(receipt, target)
        self.assertEqual(evidence.kind, "host-observed-human-action")
        self.assertNotEqual(bind_human_receipt(replace(receipt, text_digest="c" * 64), target), evidence)
        self.assertNotEqual(bind_human_receipt(replace(receipt, session_id="session-2"), target), evidence)
        for field in ("run_id", "gate_id", "decision_id", "target", "scope_digest"):
            value = ("c" * 64) if field == "scope_digest" else "changed"
            changed = replace(receipt, **{field: value})
            changed_target = replace(target, **{field: value})
            with self.subTest(field=field):
                self.assertNotEqual(bind_human_receipt(changed, changed_target), evidence)
        self.assertNotEqual(bind_human_receipt(replace(receipt, observed_at="2026-09-29T12:00:01Z"), target), evidence)
        with self.assertRaises(ValueError):
            bind_human_receipt(replace(receipt, observed_at="2026-09-29"), target)
        fixture = json.loads((Path(__file__).resolve().parents[1] / "conformance/fixtures/v3/receipt.json").read_text())
        from tooling.conformance.adapter import HumanActionReceipt as Stage3Receipt, HumanActionTarget as Stage3Target, human_receipt_matches
        producer_receipt = Stage3Receipt(**fixture)
        producer_target = Stage3Target(fixture["run_id"], fixture["gate"], fixture["decision_id"], fixture["target"], fixture["scope_digest"])
        self.assertTrue(human_receipt_matches(producer_receipt, producer_target))
        fixture_receipt = ObservedHumanAction(HumanActionOrigin(producer_receipt.origin), producer_receipt.action_id, producer_receipt.session_id, producer_receipt.run_id, producer_receipt.gate, producer_receipt.decision_id, producer_receipt.target, producer_receipt.scope_digest, producer_receipt.text_digest, producer_receipt.observed_at)
        fixture_target = GateTarget(fixture["run_id"], fixture["gate"], fixture["decision_id"], fixture["target"], fixture["scope_digest"])
        evidence = bind_human_receipt(fixture_receipt, fixture_target)
        retained = json.loads(evidence.identifier)
        self.assertEqual(retained["gate_id"], fixture["gate"])
        self.assertEqual(retained["session_id"], fixture["session_id"])
        self.assertEqual(retained["text_digest"], fixture["text_digest"])
        with self.assertRaises(ValueError):
            bind_human_receipt(replace(fixture_receipt, target="other"), fixture_target)
        for origin in ("controller", "outbound-human"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                bind_human_receipt(replace(fixture_receipt, origin=origin), fixture_target)
        with self.assertRaises(ValueError):
            bind_human_receipt(replace(fixture_receipt, observed_at="2026-09-29T12:00:00+24:00"), fixture_target)


if __name__ == "__main__":
    unittest.main()
