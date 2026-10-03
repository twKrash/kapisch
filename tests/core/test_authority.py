import json
import unittest
from dataclasses import replace
from pathlib import Path

from kapisch_core.authority import GateTarget, HumanActionOrigin, ObservedHumanAction, bind_human_receipt


class HumanReceiptTests(unittest.TestCase):
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
