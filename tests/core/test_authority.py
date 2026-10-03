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
        fixture_receipt = ObservedHumanAction(HumanActionOrigin(fixture["origin"]), fixture["action_id"], fixture["session_id"], fixture["run_id"], fixture["gate_id"], fixture["decision_id"], fixture["target"], fixture["scope_digest"], fixture["text_digest"], fixture["observed_at"])
        bind_human_receipt(fixture_receipt, GateTarget(fixture["run_id"], fixture["gate_id"], fixture["decision_id"], fixture["target"], fixture["scope_digest"]))


if __name__ == "__main__":
    unittest.main()
