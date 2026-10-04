import dataclasses
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kapisch_core._human_action_ownership import (
    _identity_key,
    load_human_action_claim,
    publish_human_action_claim,
)
from kapisch_core._human_evidence import (
    GateApprovalTarget,
    GateIdentity,
    GateTarget,
    HumanActionOrigin,
    ObservedGateAction,
    ObservedHumanAction,
    bind_gate_action,
    bind_human_receipt,
)
from kapisch_core.storage import load_authority_record


class HumanActionOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.target = GateApprovalTarget(
            "run", "gate", GateIdentity("decision", "d1"), "a" * 64, "b" * 64
        )
        self.receipt = ObservedGateAction(
            HumanActionOrigin.INBOUND_HUMAN,
            "host",
            "session",
            "act",
            "run",
            "gate",
            self.target.identity,
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "2026-10-03T12:00:00Z",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self):
        return publish_human_action_claim(self.repo, self.receipt, self.target)

    def test_publication_recovery_and_exact_reference(self):
        ref = self.publish()
        claim = load_authority_record(
            self.repo,
            "human-actions",
            "d1277ad27804efbfacfcefffc8b4b0d8e33adb4bc12948b6dae5f18d2fc611d8",
        )
        self.assertEqual(
            ref,
            {
                "identity": {
                    "session_namespace": "host",
                    "session_id": "session",
                    "action_id": "act",
                },
                "sha256": hashlib.sha256(claim).hexdigest(),
            },
        )
        self.assertEqual(
            load_human_action_claim(self.repo, ref, self.target)["claim_contract"],
            "human-action-claim/1",
        )
        self.assertEqual(self.publish(), ref)
        for change in (
            {"run_id": "other"},
            {"gate_id": "other"},
            {"identity": GateIdentity("plan", "x")},
            {"target": "d" * 64},
            {"scope_digest": "d" * 64},
            {"text_digest": "d" * 64},
            {"observed_at": "2026-10-03T12:00:01Z"},
        ):
            target_change = {
                k: v
                for k, v in change.items()
                if k in {"run_id", "gate_id", "identity", "target", "scope_digest"}
            }
            with self.subTest(change=change), self.assertRaises(ValueError):
                publish_human_action_claim(
                    self.repo,
                    dataclasses.replace(self.receipt, **change),
                    dataclasses.replace(self.target, **target_change),
                )
        self.assertEqual(self.publish(), ref)

    def test_literal_full_claim_bytes_and_digest(self):
        a, b, c = b"a" * 64, b"b" * 64, b"c" * 64
        expected = (
            b'{"approved_target_sha256":"'
            + a
            + b'","claim_contract":"human-action-claim/1","gate_target":{"gate_id":"gate",'
            b'"identity":{"id":"d1","kind":"decision"},"run_id":"run","scope_digest":"'
            + b
            + b'","target":"'
            + a
            + b'"},"identity":{"action_id":"act","session_id":"session","session_namespace":"host"},'
            b'"protocol_version":3,"receipt":{"action_id":"act","gate_id":"gate",'
            b'"identity":{"id":"d1","kind":"decision"},"observed_at":"2026-10-03T12:00:00Z",'
            b'"origin":"inbound-human","run_id":"run","scope_digest":"'
            + b
            + b'","session_id":"session","session_namespace":"host","target":"'
            + a
            + b'","text_digest":"'
            + c
            + b'"}}\n'
        )
        digest = "844c81624269a04adc0d8e4ac9811ab7bedce6b037e3d283e485012dd19681b7"
        ref = self.publish()
        actual = load_authority_record(
            self.repo,
            "human-actions",
            "d1277ad27804efbfacfcefffc8b4b0d8e33adb4bc12948b6dae5f18d2fc611d8",
        )
        self.assertEqual(actual, expected)
        self.assertTrue(actual.endswith(b"\n"))
        self.assertEqual(hashlib.sha256(actual).hexdigest(), digest)
        self.assertEqual(ref["sha256"], digest)

    def test_plan_and_effect_publication_and_reload(self):
        for kind in ("plan", "effect"):
            identity = GateIdentity(kind, "x")
            target = dataclasses.replace(self.target, identity=identity)
            receipt = dataclasses.replace(
                self.receipt, action_id=kind, identity=identity
            )
            with self.subTest(kind=kind):
                ref = publish_human_action_claim(self.repo, receipt, target)
                claim = load_human_action_claim(self.repo, ref, target)
                self.assertEqual(
                    claim["receipt"]["identity"], {"kind": kind, "id": "x"}
                )
                self.assertEqual(
                    claim["gate_target"]["identity"], {"kind": kind, "id": "x"}
                )
                self.assertEqual(
                    publish_human_action_claim(self.repo, receipt, target), ref
                )

    def test_claim_survives_run_deletion_and_cold_reload(self):
        run = self.repo / ".kapisch/v3/runs/run"
        run.mkdir(parents=True)
        (run / "state.json").write_text("{}\n")
        ref = self.publish()
        shutil.rmtree(run)
        self.assertFalse(run.exists())
        subprocess.run(
            [
                sys.executable,
                "-c",
                """
import dataclasses
import json
import sys
from pathlib import Path
from kapisch_core._human_action_ownership import load_human_action_claim, publish_human_action_claim
from kapisch_core._human_evidence import GateApprovalTarget, GateIdentity, HumanActionOrigin, ObservedGateAction
repo = Path(sys.argv[1])
ref = json.loads(sys.argv[2])
target = GateApprovalTarget('run', 'gate', GateIdentity('decision', 'd1'), 'a' * 64, 'b' * 64)
claim = load_human_action_claim(repo, ref, target)
assert claim['claim_contract'] == 'human-action-claim/1'
assert not (repo / '.kapisch/v3/runs/run').exists()
receipt = ObservedGateAction(HumanActionOrigin.INBOUND_HUMAN, 'host', 'session', 'act', 'run', 'gate', target.identity, 'a' * 64, 'b' * 64, 'c' * 64, '2026-10-03T12:00:00Z')
assert publish_human_action_claim(repo, receipt, target) == ref
try:
    publish_human_action_claim(repo, dataclasses.replace(receipt, run_id='other'), dataclasses.replace(target, run_id='other'))
except ValueError:
    pass
else:
    raise AssertionError('run deletion released the action identity')
""",
                str(self.repo),
                json.dumps(ref),
            ],
            check=True,
        )

    def test_reference_digest_identity_and_target_mismatches(self):
        ref = self.publish()
        cases = [
            ({**ref, "sha256": "0" * 64}, self.target),
            (
                {**ref, "identity": {**ref["identity"], "session_id": "other"}},
                self.target,
            ),
        ]
        cases.extend(
            (ref, dataclasses.replace(self.target, **change))
            for change in (
                {"run_id": "other"},
                {"gate_id": "other"},
                {"identity": GateIdentity("plan", "x")},
                {"target": "d" * 64},
                {"scope_digest": "d" * 64},
            )
        )
        for badref, target in cases:
            with (
                self.subTest(badref=badref, target=target),
                self.assertRaises(ValueError),
            ):
                load_human_action_claim(self.repo, badref, target)

    def test_bad_receipt_fields_and_namespaces(self):
        for change in (
            {"origin": "controller"},
            {"text_digest": "bad"},
            {"observed_at": "not-time"},
            {"identity": GateIdentity("other", "x")},
            {"session_namespace": ""},
            {"run_id": "other"},
            {"gate_id": "other"},
            {"identity": GateIdentity("plan", "x")},
            {"target": "d" * 64},
            {"scope_digest": "d" * 64},
        ):
            with (
                self.subTest(change=change),
                self.assertRaises((ValueError, TypeError)),
            ):
                publish_human_action_claim(
                    self.repo, dataclasses.replace(self.receipt, **change), self.target
                )
        ref = self.publish()
        self.assertNotEqual(
            ref,
            publish_human_action_claim(
                self.repo,
                dataclasses.replace(self.receipt, session_namespace="other"),
                self.target,
            ),
        )
        self.assertNotEqual(
            ref,
            publish_human_action_claim(
                self.repo,
                dataclasses.replace(self.receipt, session_id="other"),
                self.target,
            ),
        )

    def test_legacy_is_not_new_evidence(self):
        old = ObservedHumanAction(
            HumanActionOrigin.INBOUND_HUMAN,
            "act",
            "session",
            "run",
            "gate",
            "d1",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "2026-10-03T12:00:00Z",
        )
        with self.assertRaises(TypeError):
            bind_gate_action(old, self.target)
        evidence = bind_human_receipt(
            old, GateTarget("run", "gate", "d1", "a" * 64, "b" * 64)
        )
        expected = (
            '{"action_id":"act","decision_id":"d1","gate_id":"gate",'
            '"observed_at":"2026-10-03T12:00:00Z","origin":"inbound-human","run_id":"run",'
            '"scope_digest":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",'
            '"session_id":"session","target":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
            '"text_digest":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}'
        )
        self.assertEqual(evidence.kind, "host-observed-human-action")
        self.assertEqual(evidence.identifier, expected)

    def test_publisher_rejects_matching_unsupported_identity_kind(self):
        identity = GateIdentity("other", "x")
        receipt = dataclasses.replace(self.receipt, identity=identity)
        target = dataclasses.replace(self.target, identity=identity)
        with self.assertRaises(ValueError):
            publish_human_action_claim(self.repo, receipt, target)
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-actions").exists())

    def test_literal_identity_key_vector(self):
        self.assertEqual(
            _identity_key("host", "session", "act"),
            "d1277ad27804efbfacfcefffc8b4b0d8e33adb4bc12948b6dae5f18d2fc611d8",
        )

    def test_invalid_expected_target_rejected_before_claim_read(self):
        ref = self.publish()
        invalid_targets = (
            dataclasses.replace(self.target, identity={"kind": "decision", "id": "d1"}),
            dataclasses.replace(
                self.target, identity=GateIdentity("unsupported", "d1")
            ),
            dataclasses.replace(self.target, identity=GateIdentity("decision", "")),
            dataclasses.replace(self.target, run_id=""),
            dataclasses.replace(self.target, gate_id=""),
            dataclasses.replace(self.target, target="not-a-digest"),
            dataclasses.replace(self.target, scope_digest="not-a-digest"),
        )
        for target in invalid_targets:
            with (
                self.subTest(target=target),
                patch(
                    "kapisch_core._human_action_ownership.load_authority_record"
                ) as read_claim,
            ):
                with self.assertRaises((TypeError, ValueError)):
                    load_human_action_claim(self.repo, ref, target)
                read_claim.assert_not_called()


if __name__ == "__main__":
    unittest.main()
