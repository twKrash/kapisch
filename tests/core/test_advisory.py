from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kapisch_core.advisory import ProposedScopeRef, load_proposed_scope, propose_scope


class ProposedScopeTests(unittest.TestCase):
    def test_vectors_ordering_idempotence_and_cold_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            ref = propose_scope(
                repo,
                "run",
                "scope",
                "requirements",
                {"mode": "keys", "keys": ["a", "é"]},
            )
            identity = (
                "b61ebccd955f591b6391c2a7e467bee6be5db577d40d4b1c128e73da609d6fd3"
            )
            data = b'{"applicability":{"keys":["a","\xc3\xa9"],"mode":"keys"},"origin_run_id":"run","protocol_version":3,"requirements":"requirements","scope_contract":"applicability-scope/1","scope_id":"scope"}\n'
            self.assertEqual(
                ref,
                ProposedScopeRef(
                    "run",
                    "scope",
                    "30060f54ad1cfbc7b1f1cdd465a43a9c14ab7cd8a7335e9f225a724d316a8ff7",
                ),
            )
            self.assertEqual(
                (
                    repo / ".kapisch/v3/authority/scopes" / f"{identity}.json"
                ).read_bytes(),
                data,
            )
            self.assertEqual(
                propose_scope(
                    repo,
                    "run",
                    "scope",
                    "requirements",
                    {"mode": "keys", "keys": ["a", "é"]},
                ),
                ref,
            )
            script = (
                "from pathlib import Path; from kapisch_core.advisory import load_proposed_scope; import json; print(json.dumps(load_proposed_scope(Path(r'%s'), %s)))"
                % (repo, json.dumps(ref.__dict__))
            )
            self.assertEqual(
                json.loads(
                    subprocess.check_output(
                        [sys.executable, "-c", script], env={"PYTHONPATH": "core"}
                    )
                )["scope_id"],
                "scope",
            )
            (repo / ".kapisch/v3/runs/run").mkdir(parents=True)
            import shutil

            shutil.rmtree(repo / ".kapisch/v3/runs/run")
            self.assertEqual(load_proposed_scope(repo, ref)["origin_run_id"], "run")

    def test_validation_collision_and_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            ref = propose_scope(repo, "run", "s", "r", {"mode": "all"})
            for applicability in (
                {"mode": "all", "keys": []},
                {"mode": "keys", "keys": []},
                {"mode": "keys", "keys": ["é", "a"]},
                {"mode": "keys", "keys": ["a", "a"]},
                {"mode": "other"},
            ):
                with (
                    self.subTest(applicability=applicability),
                    self.assertRaises(ValueError),
                ):
                    propose_scope(repo, "x", "s", "r", applicability)
            with self.assertRaises(ValueError):
                propose_scope(repo, "run", "s", "changed", {"mode": "all"})
            with self.assertRaises(ValueError):
                load_proposed_scope(
                    repo,
                    {"origin_run_id": "wrong", "scope_id": "s", "sha256": ref.sha256},
                )
            path = next((repo / ".kapisch/v3/authority/scopes").glob("*.json"))
            path.write_bytes(
                path.read_bytes().replace(b'"requirements":"r"', b'"requirements":"x"')
            )
            with self.assertRaises(ValueError):
                load_proposed_scope(repo, ref)


if __name__ == "__main__":
    unittest.main()


class PlanApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        from test_gate_approval import GateApprovalTests

        self.fixture = GateApprovalTests(
            "test_repository_decision_gate_approval_does_not_commit_acceptance"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def _accept_governing_decision(self) -> None:
        import hashlib

        from kapisch_core._accepted_snapshot import publish_acceptance
        from kapisch_core._gate_approval import publish_gate_approval

        source = b"governing decision v1"
        (self.fixture.repo / "governing.md").write_bytes(source)
        payload = self.fixture._repository_payload()
        payload["subject"]["source_dependencies"] = [
            {"path": "governing.md", "sha256": hashlib.sha256(source).hexdigest()}
        ]
        approval = publish_gate_approval(
            self.fixture.repo,
            payload,
            self.fixture._external_input(
                self.fixture._artifact(self.fixture._target(payload))
            ),
        )
        publish_acceptance(self.fixture.repo, approval)

    def _accept_additional_decision(self) -> None:
        from kapisch_core._accepted_snapshot import publish_acceptance
        from kapisch_core._authority_records import _active_bindings
        from kapisch_core._gate_approval import publish_gate_approval

        payload = self.fixture._repository_payload()
        payload["gate_id"] = "decision-gate-2"
        payload["identity"]["id"] = "decision-2"
        subject = payload["subject"]
        subject["snapshot_id"] = "snapshot-2"
        subject["decision_id"] = "decision-2"
        subject["decision"] = "approve second repository decision"
        subject["authority_basis"] = list(
            _active_bindings(self.fixture.repo, self.fixture.scope_ref)
        )
        approval = publish_gate_approval(
            self.fixture.repo,
            payload,
            self.fixture._external_input(
                self.fixture._artifact(self.fixture._target(payload))
            ),
        )
        publish_acceptance(self.fixture.repo, approval)

    def test_plan_approval_rejects_changed_governing_bytes(self) -> None:
        import kapisch_core.advisory as advisory

        self.assertTrue(
            hasattr(advisory, "prepare_plan_approval"),
            "Stage 5.5 plan approval preparation is not implemented",
        )
        self._accept_governing_decision()
        payload = advisory.prepare_plan_approval(
            self.fixture.repo,
            "run-1",
            "plan-gate",
            "plan-1",
            b"exact approved plan bytes",
        )
        (self.fixture.repo / "governing.md").write_bytes(b"changed governing bytes")
        target = self.fixture._target(payload)
        evidence = self.fixture._external_input(self.fixture._artifact(target))
        with self.assertRaisesRegex(ValueError, "source dependency changed"):
            advisory.publish_plan_approval(self.fixture.repo, payload, evidence)

    def test_plan_approval_rejects_changed_authority_bindings(self) -> None:
        import kapisch_core.advisory as advisory

        self._accept_governing_decision()
        payload = advisory.prepare_plan_approval(
            self.fixture.repo,
            "run-1",
            "plan-gate",
            "plan-1",
            b"exact approved plan bytes",
        )
        self._accept_additional_decision()
        target = self.fixture._target(payload)
        with self.assertRaisesRegex(ValueError, "authority bindings are stale"):
            advisory.publish_plan_approval(
                self.fixture.repo,
                payload,
                self.fixture._external_input(self.fixture._artifact(target)),
            )

    def test_plan_promotion_rejects_stale_governing_bytes(self) -> None:
        import kapisch_core.advisory as advisory

        self._accept_governing_decision()
        payload = advisory.prepare_plan_approval(
            self.fixture.repo,
            "run-1",
            "plan-gate",
            "plan-1",
            b"exact approved plan bytes",
        )
        target = self.fixture._target(payload)
        advisory.publish_plan_approval(
            self.fixture.repo,
            payload,
            self.fixture._external_input(self.fixture._artifact(target)),
        )
        self.assertEqual(
            advisory.promote_plan(self.fixture.repo, "run-1", "plan-1")["plan_id"],
            "plan-1",
        )
        (self.fixture.repo / "governing.md").write_bytes(b"changed governing bytes")
        with self.assertRaisesRegex(ValueError, "source dependency changed"):
            advisory.promote_plan(self.fixture.repo, "run-1", "plan-1")
