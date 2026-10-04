from __future__ import annotations

import hashlib
import shutil
import unittest

from kapisch_core._gate_approval import publish_gate_approval
from kapisch_core.advisory import propose_scope
from kapisch_core.authority import active_authority
from kapisch_core.bundle import canonical_json
from kapisch_core.storage import store_authority_record


class AuthorityCensusTests(unittest.TestCase):
    def setUp(self):
        from test_gate_approval import GateApprovalTests

        self.fixture = GateApprovalTests(
            "test_repository_decision_gate_approval_does_not_commit_acceptance"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def _commit_acceptance(
        self,
        snapshot_id: str,
        applicability: dict,
        supersedes: list[dict] | None = None,
        authority_basis: list[dict] | None = None,
    ) -> str:
        fixture = self.fixture
        payload = fixture._repository_payload()
        scope_ref = propose_scope(
            fixture.repo, "run-1", f"scope-{snapshot_id}", "requirements", applicability
        )
        payload["scope_digest"] = scope_ref.sha256
        subject = payload["subject"]
        subject["scope_ref"] = {
            "origin_run_id": scope_ref.origin_run_id,
            "scope_id": scope_ref.scope_id,
            "sha256": scope_ref.sha256,
        }
        subject["applicability"] = applicability
        subject["snapshot_id"] = snapshot_id
        subject["decision_id"] = snapshot_id
        subject["supersedes"] = supersedes or []
        subject["authority_basis"] = authority_basis or []
        payload["identity"]["id"] = snapshot_id
        reference = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        record = {
            "acceptance_contract": "global-authority/1",
            "origin_run_id": "run-1",
            "snapshot_id": snapshot_id,
            "gate_approval_ref": reference,
        }
        data = canonical_json(record)
        identity = hashlib.sha256(
            canonical_json({"origin_run_id": "run-1", "snapshot_id": snapshot_id})
        ).hexdigest()
        store_authority_record(fixture.repo, "acceptances", identity, data)
        return hashlib.sha256(data).hexdigest()

    def test_invalid_historical_authority_basis_blocks_even_when_nonmatching(self):
        prior_digest = self._commit_acceptance(
            "basis-target", {"mode": "keys", "keys": ["applies-elsewhere"]}
        )
        prior_scope = propose_scope(
            self.fixture.repo,
            "run-1",
            "scope-basis-target",
            "requirements",
            {"mode": "keys", "keys": ["applies-elsewhere"]},
        )
        valid = {
            "origin_run_id": "run-1",
            "snapshot_id": "basis-target",
            "decision_id": "basis-target",
            "acceptance_record_sha256": prior_digest,
            "scope_ref": {
                "origin_run_id": "run-1",
                "scope_id": "scope-basis-target",
                "sha256": prior_scope.sha256,
            },
            "applicability": {"mode": "keys", "keys": ["applies-elsewhere"]},
            "source_dependencies": [],
        }
        malformed = (
            {**valid, "snapshot_id": "absent"},
            {**valid, "acceptance_record_sha256": "f" * 64},
            {**valid, "origin_run_id": "other-run"},
            {**valid, "applicability": {"mode": "all"}},
        )
        disjoint = propose_scope(
            self.fixture.repo,
            "consumer",
            "disjoint-work",
            "work",
            {"mode": "keys", "keys": ["does-not-match"]},
        )
        for index, binding in enumerate(malformed):
            with self.subTest(index=index):
                self._commit_acceptance(
                    f"invalid-basis-{index}",
                    {"mode": "keys", "keys": ["elsewhere-too"]},
                    authority_basis=[binding],
                )
                with self.assertRaises(ValueError):
                    active_authority(self.fixture.repo, disjoint)

    def test_valid_historical_basis_survives_target_supersession(self):
        target_digest = self._commit_acceptance(
            "historical-target", {"mode": "keys", "keys": ["alpha"]}
        )
        target_scope = propose_scope(
            self.fixture.repo,
            "run-1",
            "scope-historical-target",
            "requirements",
            {"mode": "keys", "keys": ["alpha"]},
        )
        historical_basis = {
            "origin_run_id": "run-1",
            "snapshot_id": "historical-target",
            "decision_id": "historical-target",
            "acceptance_record_sha256": target_digest,
            "scope_ref": {
                "origin_run_id": "run-1",
                "scope_id": "scope-historical-target",
                "sha256": target_scope.sha256,
            },
            "applicability": {"mode": "keys", "keys": ["alpha"]},
            "source_dependencies": [],
        }
        self._commit_acceptance(
            "basis-owner", {"mode": "keys", "keys": ["beta"]},
            authority_basis=[historical_basis],
        )
        self._commit_acceptance(
            "successor", {"mode": "keys", "keys": ["alpha"]},
            supersedes=[{
                "origin_run_id": "run-1",
                "snapshot_id": "historical-target",
                "decision_id": "historical-target",
                "sha256": target_digest,
            }],
        )
        consuming = propose_scope(
            self.fixture.repo, "consumer", "alpha", "work", {"mode": "keys", "keys": ["alpha"]}
        )
        self.assertEqual(
            [binding.decision_id for binding in active_authority(self.fixture.repo, consuming)],
            ["successor"],
        )

    def test_authority_census_uses_persisted_structural_scope_and_rejects_invalid_graph(
        self,
    ):
        self._commit_acceptance("decision-a", {"mode": "keys", "keys": ["alpha"]})
        consumer = propose_scope(
            self.fixture.repo,
            "consumer",
            "work",
            "work",
            {"mode": "keys", "keys": ["alpha"]},
        )
        self.assertEqual(
            [
                binding.decision_id
                for binding in active_authority(self.fixture.repo, consumer)
            ],
            ["decision-a"],
        )
        disjoint = propose_scope(
            self.fixture.repo,
            "consumer",
            "other",
            "other",
            {"mode": "keys", "keys": ["beta"]},
        )
        self.assertEqual(active_authority(self.fixture.repo, disjoint), ())
        universal_work = propose_scope(
            self.fixture.repo, "consumer", "universal", "all work", {"mode": "all"}
        )
        self.assertEqual(
            [
                binding.decision_id
                for binding in active_authority(self.fixture.repo, universal_work)
            ],
            ["decision-a"],
        )
        shutil.rmtree(self.fixture.repo / ".kapisch/v3/runs/run-1")
        self.assertEqual(
            [
                binding.decision_id
                for binding in active_authority(self.fixture.repo, consumer)
            ],
            ["decision-a"],
        )

    def test_full_coverage_supersession_retires_predecessor(self):
        previous_digest = self._commit_acceptance(
            "decision-a", {"mode": "keys", "keys": ["alpha"]}
        )
        self._commit_acceptance(
            "decision-b",
            {"mode": "keys", "keys": ["alpha", "beta"]},
            [
                {
                    "origin_run_id": "run-1",
                    "snapshot_id": "decision-a",
                    "decision_id": "decision-a",
                    "sha256": previous_digest,
                }
            ],
        )
        consumer = propose_scope(
            self.fixture.repo,
            "consumer",
            "work",
            "work",
            {"mode": "keys", "keys": ["alpha"]},
        )
        self.assertEqual(
            [
                binding.decision_id
                for binding in active_authority(self.fixture.repo, consumer)
            ],
            ["decision-b"],
        )

    def test_supersession_must_cover_all_predecessor_scope(self):
        previous_digest = self._commit_acceptance("decision-a", {"mode": "all"})
        self._commit_acceptance(
            "decision-b",
            {"mode": "keys", "keys": ["alpha"]},
            [
                {
                    "origin_run_id": "run-1",
                    "snapshot_id": "decision-a",
                    "decision_id": "decision-a",
                    "sha256": previous_digest,
                }
            ],
        )
        consumer = propose_scope(
            self.fixture.repo, "consumer", "work", "work", {"mode": "all"}
        )
        with self.assertRaisesRegex(
            ValueError, "does not cover predecessor applicability"
        ):
            active_authority(self.fixture.repo, consumer)

    def test_acceptance_disappearing_after_listing_blocks_census(self):
        self._commit_acceptance("disappearing", {"mode": "all"})
        scope = propose_scope(
            self.fixture.repo, "consumer", "work", "work", {"mode": "all"}
        )
        from unittest.mock import patch
        from kapisch_core.storage import _read_file

        record_dir = self.fixture.repo / ".kapisch/v3/authority/acceptances"
        record_path = next(record_dir.glob("*.json"))

        def disappear(directory: int, name: str) -> bytes:
            if name == record_path.name:
                record_path.unlink()
            return _read_file(directory, name)

        with patch("kapisch_core.storage._read_file", side_effect=disappear) as read_file:
            with self.assertRaisesRegex(ValueError, "disappeared during census"):
                active_authority(self.fixture.repo, scope)
            self.assertEqual(read_file.call_count, 2)

    def test_missing_acceptance_namespace_is_empty_census(self):
        scope = propose_scope(
            self.fixture.repo, "consumer", "work", "work", {"mode": "all"}
        )
        self.assertEqual(active_authority(self.fixture.repo, scope), ())

    def test_invalid_unmatched_acceptance_blocks_filtering(self):
        scope = propose_scope(
            self.fixture.repo,
            "consumer",
            "work",
            "work",
            {"mode": "keys", "keys": ["none"]},
        )
        store_authority_record(self.fixture.repo, "acceptances", "a" * 64, b"not-json")
        with self.assertRaisesRegex(ValueError, "acceptance record is malformed"):
            active_authority(self.fixture.repo, scope)


if __name__ == "__main__":
    unittest.main()
