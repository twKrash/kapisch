import unittest

from kapisch_core.authority import (
    GateTarget,
    HumanActionOrigin,
    ObservedHumanAction,
    bind_human_receipt,
)


class HumanReceiptTests(unittest.TestCase):
    def test_host_receipt_binds_session_local_id_and_target(self):
        receipt = ObservedHumanAction(
            origin=HumanActionOrigin.INBOUND_HUMAN,
            action_id="session-message-7",
            action="approve",
            text="Approve this exact gate",
            run_id="run-1",
            gate_id="gate-2",
            target="plan-3",
            scope="implementation",
            observed_at="2026-09-29T12:00:00Z",
        )
        target = GateTarget("run-1", "gate-2", "plan-3", "implementation")
        evidence = bind_human_receipt(receipt, target)
        self.assertEqual(evidence.kind, "host-observed-human-action")
        self.assertTrue(evidence.identifier.startswith("session-message-7:"))
        with self.assertRaises(ValueError):
            bind_human_receipt(receipt, GateTarget("run-1", "gate-2", "other", "implementation"))
        with self.assertRaises(ValueError):
            bind_human_receipt(ObservedHumanAction(**{**receipt.__dict__, "origin": "controller"}), target)


if __name__ == "__main__":
    unittest.main()
