from __future__ import annotations

import hashlib
import shutil
import sys
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
        source_dependencies: list[dict] | None = None,
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
        subject["source_dependencies"] = source_dependencies or []
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

    def test_authority_binding_is_not_publicly_exported(self) -> None:
        import kapisch_core.authority as authority

        self.assertIn("active_authority", authority.__all__)
        self.assertNotIn("AuthorityBinding", authority.__all__)
        self.assertFalse(hasattr(authority, "AuthorityBinding"))

    def test_active_authority_returns_deeply_immutable_values(self) -> None:
        import json

        source_dependencies = [
            {"path": "source-a.md", "sha256": "a" * 64},
            {"path": "source-b.md", "sha256": "b" * 64},
        ]
        applicability = {"mode": "keys", "keys": ["alpha", "beta"]}
        acceptance_digest = self._commit_acceptance(
            "snapshot-immutable",
            applicability,
            source_dependencies=source_dependencies,
        )
        other_digest = self._commit_acceptance("snapshot-order", {"mode": "all"})
        expected_scope_ref = propose_scope(
            self.fixture.repo,
            "run-1",
            "scope-snapshot-immutable",
            "requirements",
            applicability,
        )
        consumer_ref = propose_scope(
            self.fixture.repo,
            "run-1",
            "consumer-scope",
            "requirements",
            {"mode": "all"},
        )

        bindings = active_authority(self.fixture.repo, consumer_ref)

        # Canonical JSON compares the acceptance digest first in each binding.
        expected_order = sorted(
            (
                ("snapshot-immutable", acceptance_digest),
                ("snapshot-order", other_digest),
            ),
            key=lambda binding: binding[1],
        )
        self.assertEqual(
            tuple(
                (binding.snapshot_id, binding.acceptance_record_sha256)
                for binding in bindings
            ),
            tuple(expected_order),
        )
        binding = next(
            item for item in bindings if item.snapshot_id == "snapshot-immutable"
        )
        self.assertEqual(
            (
                binding.origin_run_id,
                binding.snapshot_id,
                binding.decision_id,
                binding.acceptance_record_sha256,
            ),
            ("run-1", "snapshot-immutable", "snapshot-immutable", acceptance_digest),
        )
        self.assertEqual(binding.scope_ref, expected_scope_ref)
        self.assertEqual(binding.applicability["keys"], ("alpha", "beta"))
        self.assertEqual(
            tuple(dependency["path"] for dependency in binding.source_dependencies),
            ("source-a.md", "source-b.md"),
        )

        with self.assertRaises(AttributeError):
            binding.scope_ref.sha256 = "f" * 64
        with self.assertRaises(TypeError):
            binding.applicability["mode"] = "all"
        with self.assertRaises(TypeError):
            binding.applicability["keys"][0] = "changed"
        with self.assertRaises(TypeError):
            binding.source_dependencies[0]["path"] = "changed.md"
        with self.assertRaises(AttributeError):
            binding.source_dependencies.append({})
        with self.assertRaises(AttributeError):
            binding.origin_run_id = "changed"

        payload = {
            "origin_run_id": binding.origin_run_id,
            "snapshot_id": binding.snapshot_id,
            "decision_id": binding.decision_id,
            "acceptance_record_sha256": binding.acceptance_record_sha256,
            "scope_ref": {
                "origin_run_id": binding.scope_ref.origin_run_id,
                "scope_id": binding.scope_ref.scope_id,
                "sha256": binding.scope_ref.sha256,
            },
            "applicability": {
                "mode": binding.applicability["mode"],
                "keys": list(binding.applicability["keys"]),
            },
            "source_dependencies": [
                {"path": item["path"], "sha256": item["sha256"]}
                for item in binding.source_dependencies
            ],
        }
        self.assertEqual(
            json.loads(canonical_json(payload)),
            {
                "origin_run_id": "run-1",
                "snapshot_id": "snapshot-immutable",
                "decision_id": "snapshot-immutable",
                "acceptance_record_sha256": acceptance_digest,
                "scope_ref": {
                    "origin_run_id": "run-1",
                    "scope_id": "scope-snapshot-immutable",
                    "sha256": expected_scope_ref.sha256,
                },
                "applicability": {"mode": "keys", "keys": ["alpha", "beta"]},
                "source_dependencies": source_dependencies,
            },
        )

    def _assert_invalid_authority_basis(self, change: dict, message: str) -> None:
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
        binding = {
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
        binding.update(change)
        self._commit_acceptance(
            "invalid-basis",
            {"mode": "keys", "keys": ["acceptance-does-not-match"]},
            authority_basis=[binding],
        )
        disjoint = propose_scope(
            self.fixture.repo,
            "consumer",
            "disjoint-work",
            "work",
            {"mode": "keys", "keys": ["does-not-match"]},
        )
        with self.assertRaisesRegex(ValueError, message):
            active_authority(self.fixture.repo, disjoint)

    def test_authority_basis_rejects_missing_qualified_snapshot(self):
        self._assert_invalid_authority_basis(
            {"snapshot_id": "absent"}, "authority basis target is missing"
        )

    def test_authority_basis_rejects_wrong_origin_run(self):
        self._assert_invalid_authority_basis(
            {"origin_run_id": "other-run"}, "authority basis target is missing"
        )

    def test_authority_basis_rejects_wrong_decision_id(self):
        self._assert_invalid_authority_basis(
            {"decision_id": "other-decision"}, "authority basis target is missing"
        )

    def test_authority_basis_rejects_changed_acceptance_digest(self):
        self._assert_invalid_authority_basis(
            {"acceptance_record_sha256": "f" * 64},
            "authority basis binding differs from committed target",
        )

    def test_authority_basis_rejects_changed_scope_ref(self):
        self._assert_invalid_authority_basis(
            {
                "scope_ref": {
                    "origin_run_id": "run-1",
                    "scope_id": "scope-basis-target",
                    "sha256": "f" * 64,
                }
            },
            "authority basis binding differs from committed target",
        )

    def test_authority_basis_rejects_changed_applicability(self):
        self._assert_invalid_authority_basis(
            {"applicability": {"mode": "all"}},
            "authority basis binding differs from committed target",
        )

    def test_authority_basis_rejects_changed_source_dependencies(self):
        self._assert_invalid_authority_basis(
            {"source_dependencies": [{"path": "source.md", "sha256": "a" * 64}]},
            "authority basis binding differs from committed target",
        )

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
            "basis-owner",
            {"mode": "keys", "keys": ["beta"]},
            authority_basis=[historical_basis],
        )
        self._commit_acceptance(
            "successor",
            {"mode": "keys", "keys": ["alpha"]},
            supersedes=[
                {
                    "origin_run_id": "run-1",
                    "snapshot_id": "historical-target",
                    "decision_id": "historical-target",
                    "sha256": target_digest,
                }
            ],
        )
        consuming = propose_scope(
            self.fixture.repo,
            "consumer",
            "alpha",
            "work",
            {"mode": "keys", "keys": ["alpha"]},
        )
        self.assertEqual(
            [
                binding.decision_id
                for binding in active_authority(self.fixture.repo, consuming)
            ],
            ["successor"],
        )

    def test_deep_supersession_chain_is_validated_iteratively(self):
        depth = sys.getrecursionlimit() + 10
        identifiers = [f"chain-{index}" for index in range(depth)]
        filename = lambda value: hashlib.sha256(
            canonical_json({"origin_run_id": "run-1", "snapshot_id": value})
        ).hexdigest()
        previous_names = [filename(value) for value in identifiers]
        terminal = "terminal-0"
        suffix = 1
        while filename(terminal) >= min(previous_names):
            terminal = f"terminal-{suffix}"
            suffix += 1
        identifiers[-1] = terminal

        digest = None
        for index, snapshot_id in enumerate(identifiers):
            supersedes = []
            if digest is not None:
                predecessor = identifiers[index - 1]
                supersedes = [
                    {
                        "origin_run_id": "run-1",
                        "snapshot_id": predecessor,
                        "decision_id": predecessor,
                        "sha256": digest,
                    }
                ]
            digest = self._commit_acceptance(
                snapshot_id, {"mode": "keys", "keys": ["alpha"]}, supersedes
            )

        consumer = propose_scope(
            self.fixture.repo,
            "consumer",
            "deep-chain",
            "work",
            {"mode": "keys", "keys": ["alpha"]},
        )
        self.assertEqual(
            [
                binding.decision_id
                for binding in active_authority(self.fixture.repo, consumer)
            ],
            [terminal],
        )

    def test_validate_graph_rejects_self_link(self):
        from kapisch_core._authority_records import _Acceptance, _validate_graph

        acceptance = _Acceptance(
            "run-1",
            "self",
            "digest",
            {},
            {
                "subject": {
                    "decision_id": "self",
                    "authority_basis": [],
                    "amends": [],
                    "supersedes": [
                        {
                            "origin_run_id": "run-1",
                            "snapshot_id": "self",
                            "decision_id": "self",
                            "sha256": "digest",
                        }
                    ],
                    "applicability": {"mode": "all"},
                }
            },
        )
        with self.assertRaisesRegex(ValueError, "acceptance cannot relate to itself"):
            _validate_graph((acceptance,))

    def test_validate_graph_rejects_nontrivial_cycle(self):
        from kapisch_core._authority_records import _Acceptance, _validate_graph

        def record(name, target):
            return _Acceptance(
                "run-1",
                name,
                f"digest-{name}",
                {},
                {
                    "subject": {
                        "decision_id": name,
                        "authority_basis": [],
                        "amends": [],
                        "supersedes": [
                            {
                                "origin_run_id": "run-1",
                                "snapshot_id": target,
                                "decision_id": target,
                                "sha256": f"digest-{target}",
                            }
                        ],
                        "applicability": {"mode": "all"},
                    }
                },
            )

        with self.assertRaisesRegex(
            ValueError, "acceptance relationship cycle detected"
        ):
            _validate_graph((record("first", "second"), record("second", "first")))

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

        with patch(
            "kapisch_core.storage._read_file", side_effect=disappear
        ) as read_file:
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
