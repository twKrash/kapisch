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

    def test_census_waits_for_repository_lock_before_reading_scope(self):
        import threading
        from unittest.mock import patch

        from kapisch_core import _locking
        from kapisch_core._authority_records import load_proposed_scope

        scope = propose_scope(
            self.fixture.repo, "consumer", "work", "work", {"mode": "all"}
        )
        attempted = threading.Event()
        read_started = threading.Event()
        results = []
        errors = []
        original_acquire = _locking._acquire_lock

        def acquire(fd):
            attempted.set()
            original_acquire(fd)

        def read(*args):
            read_started.set()
            return load_proposed_scope(*args)

        def census():
            try:
                results.append(active_authority(self.fixture.repo, scope))
            except BaseException as error:
                errors.append(error)

        with (
            patch.object(_locking, "_acquire_lock", side_effect=acquire),
            patch(
                "kapisch_core._authority_records.load_proposed_scope", side_effect=read
            ),
        ):
            try:
                with _locking._locked(self.fixture.repo):
                    attempted.clear()
                    thread = threading.Thread(target=census, daemon=True)
                    thread.start()
                    self.assertTrue(attempted.wait(2), "census did not acquire lock")
                    self.assertFalse(read_started.wait(0.1))
            finally:
                thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(read_started.is_set())
        self.assertEqual(errors, [])
        self.assertEqual(results, [()])

    def test_already_locked_census_core_does_not_reacquire_lock(self):
        from unittest.mock import patch

        from kapisch_core._authority_census import _active_authority_locked
        from kapisch_core._locking import _locked

        scope = propose_scope(
            self.fixture.repo, "consumer", "work", "work", {"mode": "all"}
        )
        with (
            _locked(self.fixture.repo),
            patch(
                "kapisch_core._authority_census._locked",
                side_effect=AssertionError("nested repository lock"),
            ),
        ):
            self.assertEqual(_active_authority_locked(self.fixture.repo, scope), ())

    def test_missing_acceptance_namespace_is_empty_census(self):
        scope = propose_scope(
            self.fixture.repo, "consumer", "work", "work", {"mode": "all"}
        )
        self.assertEqual(active_authority(self.fixture.repo, scope), ())

    def test_deeply_nested_acceptance_is_malformed(self):
        from kapisch_core._authority_records import _load_acceptances

        depth = sys.getrecursionlimit() + 100
        data = (
            b'{"acceptance_contract":"global-authority/1","origin_run_id":"run-1",'
            b'"snapshot_id":"nested","gate_approval_ref":'
            + b"[" * depth
            + b"0"
            + b"]" * depth
            + b"}"
        )
        store_authority_record(self.fixture.repo, "acceptances", "a" * 64, data)
        with self.assertRaisesRegex(
            ValueError, "acceptance record (is malformed|has invalid canonical shape)"
        ):
            _load_acceptances(self.fixture.repo)

    def test_acceptance_decoder_recursion_is_malformed(self):
        from unittest.mock import patch

        from kapisch_core._authority_records import _load_acceptances

        store_authority_record(self.fixture.repo, "acceptances", "a" * 64, b"{}")
        with patch(
            "kapisch_core._authority_records.json.loads",
            side_effect=RecursionError("decoder nesting"),
        ):
            with self.assertRaisesRegex(ValueError, "acceptance record is malformed"):
                _load_acceptances(self.fixture.repo)

    def test_acceptance_recovery_canonical_recursion_is_malformed(self):
        from unittest.mock import patch

        from kapisch_core import _accepted_snapshot
        from kapisch_core._accepted_snapshot import load_acceptance

        nested_reference = []
        for _ in range(200):
            nested_reference = [nested_reference]
        record = {
            "acceptance_contract": "global-authority/1",
            "origin_run_id": "run-1",
            "snapshot_id": "nested",
            "gate_approval_ref": nested_reference,
        }
        data = canonical_json(record)
        identity = hashlib.sha256(
            canonical_json({"origin_run_id": "run-1", "snapshot_id": "nested"})
        ).hexdigest()
        store_authority_record(self.fixture.repo, "acceptances", identity, data)
        original_canonical_json = _accepted_snapshot.canonical_json

        def raise_for_acceptance_envelope(value):
            if isinstance(value, dict) and value.get("acceptance_contract"):
                raise RecursionError("canonical nesting")
            return original_canonical_json(value)

        reference = {
            "origin_run_id": "run-1",
            "snapshot_id": "nested",
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        with patch(
            "kapisch_core._accepted_snapshot.canonical_json",
            side_effect=raise_for_acceptance_envelope,
        ):
            with self.assertRaisesRegex(ValueError, "acceptance record is malformed"):
                load_acceptance(self.fixture.repo, reference)

    def test_acceptance_canonical_recursion_is_malformed(self):
        from unittest.mock import patch

        from kapisch_core._authority_records import _load_acceptances

        record = {
            "acceptance_contract": "global-authority/1",
            "origin_run_id": "run-1",
            "snapshot_id": "nested",
            "gate_approval_ref": {},
        }
        store_authority_record(
            self.fixture.repo, "acceptances", "a" * 64, canonical_json(record)
        )
        # Force the operation's failure independently of runtime nesting limits.
        with patch(
            "kapisch_core._authority_records.canonical_json",
            side_effect=RecursionError("canonical nesting"),
        ):
            with self.assertRaisesRegex(ValueError, "acceptance record is malformed"):
                _load_acceptances(self.fixture.repo)

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

    def test_stage54_authority_chain_recovers_after_producer_run_loss(self) -> None:
        import subprocess
        from pathlib import Path

        from kapisch_core.advisory import accept_repository_decision
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle

        fixture = self.fixture
        raw_bundle = subprocess.check_output(
            [
                "git",
                "show",
                "e9374fb6463e5c8eafdfe28fe1023ffc51fa4774:core/dist/core-bundle.json",
            ],
            cwd=Path(__file__).resolve().parents[2],
        )
        bundle_digest = store_bundle(fixture.repo, raw_bundle)
        run_id = "run-stage54-authority"
        scope = propose_scope(
            fixture.repo, run_id, "scope-stage54", "requirements", {"mode":"all"}
        )
        scope_ref = {
            "origin_run_id": scope.origin_run_id,
            "scope_id": scope.scope_id,
            "sha256": scope.sha256,
        }
        state = {
            "protocol_version": 3,
            "run_id": run_id,
            "bundle_digest": bundle_digest,
            "workflow": "task",
            "revision": 0,
            "history": [],
            "identity_contract": "stage-attempt/1",
            "scope_ref": scope_ref,
        }
        publish_state(fixture.repo, run_id, state, expected_revision=-1)

        payload = fixture._repository_payload()
        payload["run_id"] = run_id
        payload["gate_id"] = "gate-stage54"
        payload["identity"]["id"] = "decision-stage54"
        payload["scope_digest"] = scope.sha256
        payload["subject"].update(
            {
                "origin_run_id": run_id,
                "snapshot_id": "snapshot-stage54",
                "decision_id": "decision-stage54",
                "scope_ref": scope_ref,
                "bundle_digest": bundle_digest,
            }
        )
        approval_ref = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(
                fixture._artifact(fixture._target(payload))
            ),
        )
        shutil.rmtree(fixture.repo / ".kapisch/v3/runs" / run_id)

        acceptance_ref = accept_repository_decision(fixture.repo, approval_ref)
        self.assertEqual(len(active_authority(fixture.repo, scope)), 1)
        self.assertIsNotNone(acceptance_ref["sha256"])

    def test_acceptance_publication_and_recovery_are_distinct(self) -> None:
        from kapisch_core._accepted_snapshot import load_acceptance
        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        source_path = fixture.repo / "requirements.md"
        source_bytes = b"approved requirements\n"
        source_path.write_bytes(source_bytes)
        payload = fixture._repository_payload()
        payload["subject"]["source_dependencies"] = [
            {
                "path": "requirements.md",
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
            }
        ]
        approval_ref = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        self.assertEqual(active_authority(fixture.repo, fixture.scope_ref), ())

        changed_payload = fixture._repository_payload()
        changed_payload["subject"]["decision"] = "changed decision"
        changed_approval = publish_gate_approval(
            fixture.repo,
            changed_payload,
            fixture._external_input(
                fixture._artifact(fixture._target(changed_payload))
            ),
        )

        # Approval survives producer-run loss; acceptance is a separate commit.
        shutil.rmtree(fixture.repo / ".kapisch/v3/runs/run-1")
        acceptance_ref = accept_repository_decision(fixture.repo, approval_ref)
        self.assertEqual(len(active_authority(fixture.repo, fixture.scope_ref)), 1)
        expected_record = {
            "acceptance_contract": "global-authority/1",
            "origin_run_id": payload["subject"]["origin_run_id"],
            "snapshot_id": payload["subject"]["snapshot_id"],
            "gate_approval_ref": {
                "approval_id": approval_ref["approval_id"],
                "sha256": approval_ref["sha256"],
            },
        }
        expected_bytes = canonical_json(expected_record)
        acceptance_identity = hashlib.sha256(
            canonical_json(
                {
                    "origin_run_id": expected_record["origin_run_id"],
                    "snapshot_id": expected_record["snapshot_id"],
                }
            )
        ).hexdigest()
        self.assertEqual(
            acceptance_ref["sha256"], hashlib.sha256(expected_bytes).hexdigest()
        )
        self.assertEqual(
            (
                fixture.repo
                / ".kapisch/v3/authority/acceptances"
                / f"{acceptance_identity}.json"
            ).read_bytes(),
            expected_bytes,
        )
        self.assertEqual(
            accept_repository_decision(fixture.repo, approval_ref), acceptance_ref
        )

        source_path.write_bytes(b"changed after acceptance\n")
        record = load_acceptance(fixture.repo, acceptance_ref)
        self.assertEqual(
            accept_repository_decision(fixture.repo, approval_ref), acceptance_ref
        )
        self.assertEqual(load_acceptance(fixture.repo, acceptance_ref), record)
        with self.assertRaisesRegex(ValueError, "occupied|different"):
            accept_repository_decision(fixture.repo, changed_approval)

    def test_acceptance_checks_current_sources_of_governing_authority(self) -> None:
        from unittest.mock import patch

        from kapisch_core import _accepted_snapshot
        from kapisch_core._accepted_snapshot import load_acceptance
        from kapisch_core._authority_records import _active_bindings
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import ProposedScopeRef, accept_repository_decision

        fixture = self.fixture
        source_path = fixture.repo / "governing-requirements.md"
        original = b"governing source v1\n"
        source_path.write_bytes(original)

        first_payload = fixture._repository_payload()
        first_payload["subject"]["source_dependencies"] = [
            {
                "path": "governing-requirements.md",
                "sha256": hashlib.sha256(original).hexdigest(),
            }
        ]
        first_approval = publish_gate_approval(
            fixture.repo,
            first_payload,
            fixture._external_input(fixture._artifact(fixture._target(first_payload))),
        )
        first_ref = accept_repository_decision(fixture.repo, first_approval)

        second_payload = fixture._repository_payload()
        second_payload["subject"]["snapshot_id"] = "snapshot-next"
        second_payload["subject"]["decision_id"] = "decision-next"
        second_payload["identity"]["id"] = "decision-next"
        second_payload["subject"]["authority_basis"] = _active_bindings(
            fixture.repo, ProposedScopeRef(**fixture.scope_ref)
        )
        second_approval = publish_gate_approval(
            fixture.repo,
            second_payload,
            fixture._external_input(fixture._artifact(fixture._target(second_payload))),
        )

        source_path.write_bytes(b"governing source v2\n")
        with self.assertRaisesRegex(ValueError, "source dependency changed"):
            accept_repository_decision(fixture.repo, second_approval)

        read_source = _accepted_snapshot._read_repository_file

        def unreadable_source(repo, path):
            if path == "governing-requirements.md":
                raise PermissionError("source is unreadable")
            return read_source(repo, path)

        with patch(
            "kapisch_core._accepted_snapshot._read_repository_file",
            side_effect=unreadable_source,
        ):
            with self.assertRaisesRegex(PermissionError, "source is unreadable"):
                accept_repository_decision(fixture.repo, second_approval)

        source_path.unlink()
        with self.assertRaises(FileNotFoundError):
            accept_repository_decision(fixture.repo, second_approval)
        self.assertEqual(
            load_gate_approval(fixture.repo, second_approval)["approval_id"],
            second_approval["approval_id"],
        )
        self.assertEqual(
            load_acceptance(fixture.repo, first_ref)["snapshot_id"], "snapshot-1"
        )
        self.assertEqual(len(active_authority(fixture.repo, fixture.scope_ref)), 1)

    def test_acceptance_sync_failure_requires_durable_retry(self) -> None:
        from unittest.mock import patch

        import kapisch_core.storage as storage
        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        payload = fixture._repository_payload()
        approval_ref = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        original_sync = storage._sync_hierarchy
        calls = 0

        def fail_once(descriptors):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("acceptance sync failed")
            return original_sync(descriptors)

        with patch("kapisch_core.storage._sync_hierarchy", side_effect=fail_once):
            acceptance_ref = accept_repository_decision(fixture.repo, approval_ref)
        self.assertGreaterEqual(calls, 2)
        self.assertEqual(
            active_authority(fixture.repo, fixture.scope_ref)[0].snapshot_id,
            acceptance_ref["snapshot_id"],
        )

    def test_acceptance_recovery_rejects_missing_approval_after_uncertain_write(
        self,
    ) -> None:
        from contextlib import suppress
        from unittest.mock import patch

        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        payload = fixture._repository_payload()
        approval_ref = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        approval_path = (
            fixture.repo
            / ".kapisch/v3/authority/gate-approvals"
            / f"{approval_ref['approval_id']}.json"
        )

        def remove_approval_and_fail(_descriptors):
            with suppress(FileNotFoundError):
                approval_path.unlink()
            raise OSError("acceptance sync failed")

        with patch(
            "kapisch_core.storage._sync_hierarchy",
            side_effect=remove_approval_and_fail,
        ):
            with self.assertRaisesRegex(OSError, "acceptance sync failed"):
                accept_repository_decision(fixture.repo, approval_ref)
        with self.assertRaisesRegex(ValueError, "approval reference is not retained"):
            accept_repository_decision(fixture.repo, approval_ref)

    def test_acceptance_successful_sync_retry_still_validates_approval(self) -> None:
        from contextlib import suppress
        from unittest.mock import patch

        import kapisch_core.storage as storage
        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        payload = fixture._repository_payload()
        approval_ref = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        approval_path = (
            fixture.repo
            / ".kapisch/v3/authority/gate-approvals"
            / f"{approval_ref['approval_id']}.json"
        )
        original_sync = storage._sync_hierarchy
        calls = 0

        def remove_approval_then_fail_once(descriptors):
            nonlocal calls
            calls += 1
            if calls == 1:
                with suppress(FileNotFoundError):
                    approval_path.unlink()
                raise OSError("acceptance sync failed")
            return original_sync(descriptors)

        with patch(
            "kapisch_core.storage._sync_hierarchy",
            side_effect=remove_approval_then_fail_once,
        ):
            with self.assertRaisesRegex(
                ValueError, "approval reference is not retained"
            ):
                accept_repository_decision(fixture.repo, approval_ref)
        self.assertGreaterEqual(calls, 2)

    def test_persistent_acceptance_sync_failure_never_returns_success(self) -> None:
        from unittest.mock import patch

        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        payload = fixture._repository_payload()
        approval_ref = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        with patch(
            "kapisch_core.storage._sync_hierarchy",
            side_effect=OSError("acceptance sync failed"),
        ):
            with self.assertRaisesRegex(OSError, "acceptance sync failed"):
                accept_repository_decision(fixture.repo, approval_ref)
            with self.assertRaisesRegex(OSError, "acceptance sync failed"):
                accept_repository_decision(fixture.repo, approval_ref)
        recovered = accept_repository_decision(fixture.repo, approval_ref)
        self.assertEqual(recovered["snapshot_id"], "snapshot-1")

    def test_acceptance_rejects_escaping_source_dependencies(self) -> None:
        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        outside = fixture.repo.parent / "outside-requirements.md"
        outside.write_bytes(b"outside\n")
        self.addCleanup(outside.unlink)
        payload = fixture._repository_payload()
        payload["subject"]["source_dependencies"] = [
            {
                "path": "../outside-requirements.md",
                "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
            }
        ]
        approval = publish_gate_approval(
            fixture.repo,
            payload,
            fixture._external_input(fixture._artifact(fixture._target(payload))),
        )
        with self.assertRaisesRegex(ValueError, "not canonical"):
            accept_repository_decision(fixture.repo, approval)
        self.assertFalse((fixture.repo / ".kapisch/v3/authority/acceptances").exists())

    def test_acceptance_requires_active_fully_covered_predecessors(self) -> None:
        from kapisch_core._authority_records import _active_bindings
        from kapisch_core.advisory import ProposedScopeRef, accept_repository_decision

        fixture = self.fixture
        base_digest = self._commit_acceptance("base-decision", {"mode": "all"})
        scope_ref = ProposedScopeRef(**fixture.scope_ref)

        def make_approval(snapshot_id: str) -> dict[str, str]:
            payload = fixture._repository_payload()
            payload["subject"]["snapshot_id"] = snapshot_id
            payload["subject"]["decision_id"] = snapshot_id
            payload["identity"]["id"] = snapshot_id
            payload["subject"]["authority_basis"] = _active_bindings(
                fixture.repo, scope_ref
            )
            payload["subject"]["supersedes"] = [
                {
                    "origin_run_id": "run-1",
                    "snapshot_id": "base-decision",
                    "decision_id": "base-decision",
                    "sha256": base_digest,
                }
            ]
            return publish_gate_approval(
                fixture.repo,
                payload,
                fixture._external_input(fixture._artifact(fixture._target(payload))),
            )

        first = make_approval("successor-one")
        accept_repository_decision(fixture.repo, first)
        second = make_approval("successor-two")
        with self.assertRaisesRegex(ValueError, "no longer active"):
            accept_repository_decision(fixture.repo, second)

    def test_new_acceptance_rechecks_current_source_and_authority(self) -> None:
        from kapisch_core.advisory import accept_repository_decision

        fixture = self.fixture
        source_path = fixture.repo / "requirements.md"
        original = b"requirements v1\n"
        source_path.write_bytes(original)
        stale_payload = fixture._repository_payload()
        stale_payload["subject"]["source_dependencies"] = [
            {"path": "requirements.md", "sha256": hashlib.sha256(original).hexdigest()}
        ]
        stale_approval = publish_gate_approval(
            fixture.repo,
            stale_payload,
            fixture._external_input(fixture._artifact(fixture._target(stale_payload))),
        )
        source_path.write_bytes(b"requirements changed\n")
        with self.assertRaisesRegex(ValueError, "source dependency changed"):
            accept_repository_decision(fixture.repo, stale_approval)
        self.assertFalse((fixture.repo / ".kapisch/v3/authority/acceptances").exists())

        source_path.write_bytes(original)
        first_payload = fixture._repository_payload()
        first_approval = publish_gate_approval(
            fixture.repo,
            first_payload,
            fixture._external_input(fixture._artifact(fixture._target(first_payload))),
        )
        accept_repository_decision(fixture.repo, first_approval)

        stale_basis = fixture._repository_payload()
        stale_basis["subject"]["snapshot_id"] = "snapshot-stale-basis"
        stale_basis["subject"]["decision_id"] = "decision-stale-basis"
        stale_basis["identity"]["id"] = "decision-stale-basis"
        basis_approval = publish_gate_approval(
            fixture.repo,
            stale_basis,
            fixture._external_input(fixture._artifact(fixture._target(stale_basis))),
        )
        with self.assertRaisesRegex(ValueError, "authority basis is stale"):
            accept_repository_decision(fixture.repo, basis_approval)


if __name__ == "__main__":
    unittest.main()
