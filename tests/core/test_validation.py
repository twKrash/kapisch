from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from kapisch_core.bundle import canonical_json
        from kapisch_core.storage import store_bundle

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
        self.digest = store_bundle(self.repo, self.bundle)
        self.state = {
            "protocol_version": 3,
            "run_id": "run-validator-test",
            "bundle_digest": self.digest,
            "workflow": "task",
            "revision": 0,
            "history": [],
            "identity_contract": "stage-attempt/1",
        }
        self.canonical_json = canonical_json

    def _use_legacy_bundle(self) -> None:
        from kapisch_core.storage import store_bundle

        self.bundle = (
            ROOT / "tests/conformance/fixtures/v3/legacy-bundle.json"
        ).read_bytes()
        self.digest = store_bundle(self.repo, self.bundle)
        self.state = {**self.state, "bundle_digest": self.digest}

    def _write_state(self, state: dict | None = None) -> None:
        state = state or self.state
        path = self.repo / ".kapisch/v3/runs" / state["run_id"] / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.canonical_json(state))

    def _publish_uncertain_attempt(
        self,
        run_id: str,
        number: int,
        workflow: str = "task",
        approved_plan: dict | None = None,
    ) -> tuple[dict, dict, list[dict]]:
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            publish_uncertainty,
            reserve_operation,
        )

        operation_id = f"op-{number:032x}"
        stage_id = f"s-{number:032x}"
        stage_kind, role = (
            ("research", "researcher")
            if workflow == "milestone"
            else ("implement", "implementer")
        )
        stage = {
            "stage_id": stage_id,
            "stage_kind": stage_kind,
            "sequence": 0,
            "role": role,
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": f"{number:064x}",
        }
        initial = {
            **self.state,
            "run_id": run_id,
            "workflow": workflow,
            "history": [stage],
        }
        if approved_plan is not None:
            initial["approved_plan"] = approved_plan
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage_id,
            "role": role,
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {
                "adapter_id": "fake",
                "lookup_context": f"ctx-{number}",
            },
        }
        if approved_plan is not None:
            packet["approved_plan"] = approved_plan
        request_path, request_digest = persist_request(
            self.repo, run_id, operation_id, packet
        )
        planned = reserve_operation(
            self.repo,
            run_id,
            operation_id,
            stage_id,
            role,
            {"path": request_path, "sha256": request_digest},
            packet["adapter_binding"],
        )
        planned_bytes = self.canonical_json(planned)
        uncertain_bytes = self.canonical_json(
            {**planned, "status": "dispatch-uncertain"}
        )
        evidence = [
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/planned.json",
                "sha256": hashlib.sha256(planned_bytes).hexdigest(),
            },
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/dispatch-uncertain.json",
                "sha256": hashlib.sha256(uncertain_bytes).hexdigest(),
            },
        ]
        if approved_plan is not None:
            evidence.append(
                {
                    "kind": "plan",
                    "path": approved_plan["path"],
                    "sha256": approved_plan["sha256"],
                }
            )
        uncertain = {
            **stage,
            "sequence": 1,
            "status": "dispatch-uncertain",
            "evidence": evidence,
        }
        state = {**initial, "revision": 1, "history": [stage, uncertain]}
        publish_uncertainty(self.repo, run_id, state, 0, operation_id)
        return state, stage, evidence

    def test_empty_run_validates_for_new_and_legacy_identity_contracts(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        for name, bundle_bytes in (
            ("new", self.bundle),
            (
                "legacy",
                (
                    ROOT / "tests/conformance/fixtures/v3/legacy-bundle.json"
                ).read_bytes(),
            ),
        ):
            digest = store_bundle(self.repo, bundle_bytes)
            run_id = f"run-identity-{name}"
            state = {**self.state, "run_id": run_id, "bundle_digest": digest}
            publish_state(self.repo, run_id, state, expected_revision=-1)
            self.assertEqual(validate_run(self.repo, run_id), [])

    def test_rejects_weakened_retained_identity_schemas(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle

        mutations = (
            "missing-marker",
            "wrong-marker",
            "weakened-stage-id",
            "missing-invocation-request",
            "missing-scope-requirements",
            "open-scope",
            "weakened-node-id",
            "weakened-dependencies",
            "added-graph-ref-property",
            "added-graph-document-property",
            "added-graph-node-property",
            "added-scope-ref-property",
            "added-scope-property",
            "weakened-invocation-role",
            "weakened-invocation-status",
            "removed-run-conditionals",
            "added-plan-ref-property",
            "weakened-bundle-digest",
            "missing-operation-id-type",
            "missing-run-id-types",
            "missing-stage-node-id-type",
            "semantic-description-property",
            "semantic-title-property",
            "semantic-title-definition",
        )
        for mutation in mutations:
            bundle = json.loads(self.bundle)
            schemas = bundle["schemas"]
            if mutation == "missing-marker":
                schemas["run"]["required"].remove("identity_contract")
                schemas["run"]["properties"].pop("identity_contract")
                schemas["run"]["additionalProperties"] = True
            elif mutation == "wrong-marker":
                schemas["run"]["properties"]["identity_contract"]["const"] = (
                    "stage-attempt/2"
                )
            elif mutation == "weakened-stage-id":
                schemas["stage"]["properties"]["stage_id"]["pattern"] = ".*"
            elif mutation == "missing-invocation-request":
                schemas["invocation"]["required"].remove("request")
                schemas["invocation"]["required"].remove("adapter_binding")
            elif mutation == "missing-scope-requirements":
                schemas["run"]["$defs"]["scope_document"]["required"].remove(
                    "requirements"
                )
            elif mutation == "open-scope":
                schemas["run"]["$defs"]["scope_document"]["additionalProperties"] = True
            elif mutation == "weakened-node-id":
                schemas["run"]["$defs"]["graph_node"]["properties"]["node_id"][
                    "pattern"
                ] = ".*"
            elif mutation == "weakened-dependencies":
                dependencies = schemas["run"]["$defs"]["graph_node"]["properties"][
                    "depends_on"
                ]
                dependencies["uniqueItems"] = False
                dependencies["items"]["pattern"] = ".*"
            elif mutation == "weakened-invocation-role":
                schemas["invocation"]["properties"]["role"]["enum"] = ["reviewer"]
            elif mutation == "weakened-invocation-status":
                schemas["invocation"]["properties"]["status"]["enum"] = ["observed"]
            elif mutation == "removed-run-conditionals":
                schemas["run"].pop("allOf")
            elif mutation == "added-plan-ref-property":
                schemas["run"]["$defs"]["plan_ref"]["properties"][
                    "unowned_authority"
                ] = {}
            elif mutation == "weakened-bundle-digest":
                schemas["bundle"]["$defs"]["digest"]["pattern"] = ".*"
            elif mutation == "missing-operation-id-type":
                schemas["invocation"]["properties"]["operation_id"].pop("type")
            elif mutation == "missing-run-id-types":
                schemas["run"]["properties"]["run_id"].pop("type")
                schemas["invocation"]["properties"]["run_id"].pop("type")
            elif mutation == "missing-stage-node-id-type":
                schemas["stage"]["properties"]["node_id"].pop("type")
            elif mutation == "semantic-description-property":
                schemas["run"]["$defs"]["plan_ref"]["properties"]["description"] = {
                    "type": "string"
                }
            elif mutation == "semantic-title-property":
                schemas["bundle"]["$defs"]["contract"]["properties"]["title"] = {
                    "type": "string"
                }
            elif mutation == "semantic-title-definition":
                schemas["run"]["$defs"]["title"] = {"type": "integer"}
            elif mutation.startswith("added-"):
                definition_name = {
                    "added-graph-ref-property": "graph_ref",
                    "added-graph-document-property": "graph_document",
                    "added-graph-node-property": "graph_node",
                    "added-scope-ref-property": "scope_ref",
                    "added-scope-property": "scope_document",
                }[mutation]
                schemas["run"]["$defs"][definition_name]["properties"][
                    "unowned_authority"
                ] = {}
            bundle_digest = store_bundle(self.repo, self.canonical_json(bundle))
            run_id = f"run-identity-schema-{mutation}"
            state = {**self.state, "run_id": run_id, "bundle_digest": bundle_digest}
            with self.assertRaisesRegex(ValueError, "alters supported stage-attempt/1"):
                publish_state(self.repo, run_id, state, expected_revision=-1)

    def test_changed_during_validation_rereads_persisted_state(self) -> None:
        from unittest.mock import patch

        import kapisch_core.validation as validation
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        run_id = "run-validation-replacement"
        state = {**self.state, "run_id": run_id}
        publish_state(self.repo, run_id, state, -1)
        original = validation._load_run_context
        calls = 0

        def replace_before_verification(repo, requested_run_id, data=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                changed = {**state, "revision": 1}
                (self.repo / ".kapisch/v3/runs" / run_id / "state.json").write_bytes(
                    self.canonical_json(changed)
                )
            return original(repo, requested_run_id, data)

        with patch.object(
            validation, "_load_run_context", side_effect=replace_before_verification
        ):
            errors = validate_run(self.repo, run_id)
        self.assertTrue(
            any("changed during validation" in error.message for error in errors),
            errors,
        )

    def test_new_checked_plan_is_not_read_by_legacy_plan_consumer(self) -> None:
        from unittest.mock import patch

        import kapisch_core.validation as validation
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        run_id = "run-checked-plan-unconsumed"
        state = {
            **self.state,
            "run_id": run_id,
            "approved_plan": {
                "plan_id": "plan-new",
                "path": "plans/must-not-open.json",
                "plan_sha256": "a" * 64,
                "gate_approval_ref": {"approval_id": "approval-1", "sha256": "b" * 64},
            },
        }
        publish_state(self.repo, run_id, state, -1)
        with patch.object(validation, "_validate_plan") as plan_reader:
            errors = validate_run(self.repo, run_id)
        plan_reader.assert_not_called()
        self.assertTrue(
            any(error.code == "unsupported-gate" for error in errors), errors
        )

    def test_validate_run_checks_legacy_snapshot_artifact(self) -> None:
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        bundle_bytes = (
            ROOT / "tests/conformance/fixtures/v3/legacy-bundle.json"
        ).read_bytes()
        digest = store_bundle(self.repo, bundle_bytes)
        run_id = "run-legacy-snapshot-missing"
        state = {
            **self.state,
            "run_id": run_id,
            "bundle_digest": digest,
            "accepted_snapshot": {
                "snapshot_id": "snap-missing",
                "path": "snapshots/missing.json",
                "sha256": "0" * 64,
            },
            "amends": [],
            "supersedes": [],
        }
        self._write_state(state)
        errors = validate_run(self.repo, run_id)
        self.assertTrue(
            any(
                "accepted snapshot artifact is unavailable" in error.message
                for error in errors
            ),
            errors,
        )

    def test_validate_run_checks_legacy_root_and_recursive_snapshot_corruption(
        self,
    ) -> None:
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        bundle = (
            ROOT / "tests/conformance/fixtures/v3/legacy-bundle.json"
        ).read_bytes()
        digest = store_bundle(self.repo, bundle)
        scenarios = (
            "root-digest",
            "dependency-missing",
            "dependency-digest",
            "dependency-identity",
        )
        for index, scenario in enumerate(scenarios):
            run_id = f"run-legacy-snapshot-corruption-{index}"
            root = self.repo / ".kapisch/v3/runs" / run_id / "snapshots"
            root.mkdir(parents=True)
            child_path = root / "child.json"
            child_id = "snap-child"
            child = {
                "protocol_version": 3,
                "snapshot_id": child_id,
                "decision": "accepted",
                "scope": "task",
                "dependencies": [],
                "amends": [],
                "supersedes": [],
            }
            child_bytes = self.canonical_json(child)
            if scenario == "dependency-identity":
                child["snapshot_id"] = "wrong-child"
                child_bytes = self.canonical_json(child)
            child_digest = hashlib.sha256(child_bytes).hexdigest()
            if scenario != "dependency-missing":
                child_path.write_bytes(child_bytes)
            expected_child_digest = (
                "0" * 64 if scenario == "dependency-digest" else child_digest
            )
            dependency = {
                "kind": "snapshot",
                "snapshot_id": child_id,
                "path": "snapshots/child.json",
                "sha256": expected_child_digest,
            }
            root_doc = {
                "protocol_version": 3,
                "snapshot_id": "snap-root",
                "decision": "accepted",
                "scope": "task",
                "dependencies": [] if scenario == "root-digest" else [dependency],
                "amends": [],
                "supersedes": [],
            }
            root_bytes = self.canonical_json(root_doc)
            root_path = root / "root.json"
            root_path.write_bytes(root_bytes)
            ref = {
                "snapshot_id": "snap-root",
                "path": "snapshots/root.json",
                "sha256": hashlib.sha256(root_bytes).hexdigest(),
            }
            if scenario == "root-digest":
                root_path.write_bytes(
                    self.canonical_json({**root_doc, "decision": "rejected"})
                )
            state = {
                **self.state,
                "run_id": run_id,
                "bundle_digest": digest,
                "accepted_snapshot": ref,
                "amends": [],
                "supersedes": [],
            }
            self._write_state(state)
            errors = validate_run(self.repo, run_id)
            expected_message = {
                "root-digest": "accepted snapshot artifact digest changed",
                "dependency-missing": "snapshot dependency artifact is unavailable",
                "dependency-digest": "snapshot dependency artifact digest changed",
                "dependency-identity": "snapshot dependency identity does not match artifact",
            }[scenario]
            self.assertTrue(
                any(expected_message in error.message for error in errors),
                (scenario, errors),
            )

    def test_operation_input_snapshot_cannot_precede_owner_creation(self) -> None:
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            publish_uncertainty,
            reserve_operation,
        )
        from kapisch_core.validation import validate_run

        run_id = "run-input-before-attempt"
        operation_id = "op-00000000000000000000000000000034"
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        source_path = "sources/input.bin"
        source_bytes = b"operation input"
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        source_file = run_root / source_path
        source_file.parent.mkdir(parents=True)
        source_file.write_bytes(source_bytes)
        source_ref = {"kind": "source", "path": source_path, "sha256": source_digest}
        unrelated = {
            "stage_id": "s-00000000000000000000000000000035",
            "stage_kind": "research",
            "sequence": 0,
            "role": "researcher",
            "status": "planned",
            "producer": "controller",
            "evidence": [source_ref],
            "scope_digest": "5" * 64,
        }
        stage = {
            "stage_id": "s-00000000000000000000000000000034",
            "stage_kind": "implement",
            "sequence": 1,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "4" * 64,
        }
        initial = {**self.state, "run_id": run_id, "history": [unrelated, stage]}
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage["stage_id"],
            "role": stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {
                "adapter_id": "fake",
                "lookup_context": "input-context",
            },
            "inputs": [{"path": source_path, "sha256": source_digest}],
        }
        request_path, request_digest = persist_request(
            self.repo, run_id, operation_id, packet
        )
        planned = reserve_operation(
            self.repo,
            run_id,
            operation_id,
            stage["stage_id"],
            stage["role"],
            {"path": request_path, "sha256": request_digest},
            packet["adapter_binding"],
        )
        planned_bytes = self.canonical_json(planned)
        uncertain_bytes = self.canonical_json(
            {**planned, "status": "dispatch-uncertain"}
        )
        input_ref = {
            "kind": "input",
            "path": f"request-inputs/{operation_id}/0000.bin",
            "sha256": source_digest,
        }
        evidence = [
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/planned.json",
                "sha256": hashlib.sha256(planned_bytes).hexdigest(),
            },
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/dispatch-uncertain.json",
                "sha256": hashlib.sha256(uncertain_bytes).hexdigest(),
            },
            input_ref,
        ]
        uncertain = {
            **stage,
            "sequence": 2,
            "status": "dispatch-uncertain",
            "evidence": evidence,
        }
        valid = {**initial, "revision": 1, "history": [unrelated, stage, uncertain]}
        publish_uncertainty(
            self.repo, run_id, valid, expected_revision=0, operation_id=operation_id
        )
        self.assertEqual(validate_run(self.repo, run_id), [])

        early_consumer = {**unrelated, "evidence": [source_ref, input_ref]}
        impossible = {**valid, "history": [early_consumer, stage, uncertain]}
        self._write_state(impossible)
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_planned_only_reservation_is_bound_by_retained_invocation_contract(
        self,
    ) -> None:
        from kapisch_core.storage import store_bundle

        original_digest = self.digest
        original_state = self.state
        for number, field, values in (
            (30, "role", ["reviewer"]),
            (31, "status", ["observed"]),
        ):
            bundle = json.loads(self.bundle)
            bundle["schemas"]["invocation"]["properties"][field]["enum"] = values
            self.digest = store_bundle(self.repo, self.canonical_json(bundle))
            self.state = {**original_state, "bundle_digest": self.digest}
            run_id = f"run-planned-schema-{number}"
            with self.assertRaisesRegex(ValueError, "alters supported stage-attempt/1"):
                self._publish_uncertain_attempt(run_id, number)
        self.digest = original_digest
        self.state = original_state

    def test_retained_identity_contract_survives_policy_only_bundle_upgrade(
        self,
    ) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        upgraded = json.loads(self.bundle)
        upgraded["policies"]["dispatch"]["contract"] += "\nDistribution upgrade marker."
        upgraded["policies"]["dispatch"]["sha256"] = hashlib.sha256(
            upgraded["policies"]["dispatch"]["contract"].encode("utf-8")
        ).hexdigest()
        upgraded["schemas"]["run"]["description"] = "Updated explanatory text."
        upgraded["schemas"]["run"]["properties"]["run_id"]["description"] = (
            "Run identifier documentation."
        )
        upgraded["schemas"]["run"]["properties"]["history"]["items"]["description"] = (
            "History entries."
        )
        upgraded["schemas"]["run"]["$defs"]["graph_node"]["properties"]["depends_on"][
            "items"
        ]["description"] = "Dependency IDs."
        upgraded_digest = store_bundle(self.repo, self.canonical_json(upgraded))
        run_id = "run-retained-identity-bundle"
        state = {**self.state, "run_id": run_id, "bundle_digest": upgraded_digest}
        publish_state(self.repo, run_id, state, expected_revision=-1)

        self.assertEqual(validate_run(self.repo, run_id), [])

    def test_filesystem_inspection_errors_return_typed_validation_errors(self) -> None:
        from unittest.mock import patch

        from kapisch_core.validation import validate_run

        self._write_state()
        legacy = self.repo / ".kapisch/runs" / self.state["run_id"]
        original_is_symlink = Path.is_symlink
        original_lstat = Path.lstat

        def deny_legacy(path: Path, original):
            if path == legacy:
                raise PermissionError("legacy path inspection denied")
            return original(path)

        with (
            patch.object(
                Path, "is_symlink", lambda path: deny_legacy(path, original_is_symlink)
            ),
            patch.object(Path, "lstat", lambda path: deny_legacy(path, original_lstat)),
        ):
            errors = validate_run(self.repo, self.state["run_id"])
        self.assertTrue(
            any(error.code == "authority-invalid" for error in errors), errors
        )

        missing_run = "run-inspection-denied"
        state_dir = self.repo / ".kapisch/v3/runs" / missing_run
        original_exists = Path.exists

        def deny_missing_state(path: Path, original):
            if path == state_dir:
                raise PermissionError("state path inspection denied")
            return original(path)

        with (
            patch.object(
                Path, "exists", lambda path: deny_missing_state(path, original_exists)
            ),
            patch.object(
                Path, "lstat", lambda path: deny_missing_state(path, original_lstat)
            ),
        ):
            errors = validate_run(self.repo, missing_run)
        self.assertTrue(
            any(error.code == "state-unavailable" for error in errors), errors
        )

    def test_conformance_run_fixtures(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        fixture_root = ROOT / "tests/conformance/fixtures/v3"
        minimal = json.loads(
            (fixture_root / "minimal-run.json").read_text(encoding="utf-8")
        )
        minimal["bundle_digest"] = self.digest
        publish_state(self.repo, minimal["run_id"], minimal, expected_revision=-1)
        self.assertEqual(validate_run(self.repo, minimal["run_id"]), [])

        invalid = json.loads(
            (fixture_root / "invalid-run.json").read_text(encoding="utf-8")
        )
        invalid["bundle_digest"] = self.digest
        invalid_path = self.repo / ".kapisch/v3/runs" / invalid["run_id"] / "state.json"
        invalid_path.parent.mkdir(parents=True)
        invalid_path.write_bytes(self.canonical_json(invalid))
        errors = validate_run(self.repo, invalid["run_id"])
        self.assertTrue(any(error.code == "schema-invalid" for error in errors), errors)

    def test_cold_restart_reads_only_persisted_state(self) -> None:
        import os

        from kapisch_core.protocol import publish_state

        publish_state(self.repo, self.state["run_id"], self.state, expected_revision=-1)
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "core")}
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; from kapisch_core.validation import validate_run; "
                "errors=validate_run(Path(__import__('sys').argv[1]), 'run-validator-test'); "
                "print('ok' if not errors else errors)",
                str(self.repo),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.stdout.strip(), "ok")

    def test_valid_empty_run_and_future_gate_are_explicit(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        publish_state(self.repo, self.state["run_id"], self.state, expected_revision=-1)
        self.assertEqual(validate_run(self.repo, self.state["run_id"]), [])
        errors = validate_run(self.repo, self.state["run_id"], gate="approval")
        self.assertEqual([error.code for error in errors], ["unsupported-gate"])

    def test_orphaned_reservation_vetoes_authority(self) -> None:
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            reserve_operation,
        )
        from kapisch_core.validation import validate_run

        run_id = "run-orphan-reservation"
        operation_id = "op-00000000000000000000000000000001"
        stage = {
            "stage_id": "s-00000000000000000000000000000001",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "0" * 64,
        }
        state = {**self.state, "run_id": run_id, "history": [stage]}
        publish_state(self.repo, run_id, state, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage["stage_id"],
            "role": stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "test-context"},
        }
        path, digest = persist_request(self.repo, run_id, operation_id, packet)
        reserve_operation(
            self.repo,
            run_id,
            operation_id,
            stage["stage_id"],
            stage["role"],
            {"path": path, "sha256": digest},
            packet["adapter_binding"],
        )
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_incomplete_reservation_directory_vetoes_authority(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        run_id = "run-incomplete-reservation"
        publish_state(
            self.repo, run_id, {**self.state, "run_id": run_id}, expected_revision=-1
        )
        incomplete = (
            self.repo
            / ".kapisch/v3/runs"
            / run_id
            / "invocations"
            / "op-00000000000000000000000000000003"
        )
        incomplete.mkdir(parents=True)
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_graphless_milestone_allows_run_wide_planning_history(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        run_id = "run-graphless-planning"
        history = []
        for suffix, kind, role, scope_digest in (
            ("10", "research", "researcher", "a" * 64),
            ("11", "design", "architect", "b" * 64),
        ):
            planned = {
                "stage_id": f"s-{'0' * 30}{suffix}",
                "stage_kind": kind,
                "sequence": len(history),
                "role": role,
                "status": "planned",
                "producer": "controller",
                "evidence": [],
                "scope_digest": scope_digest,
            }
            history.extend(
                (
                    planned,
                    {**planned, "sequence": len(history) + 1, "status": "complete"},
                )
            )
        state = {
            **self.state,
            "run_id": run_id,
            "workflow": "milestone",
            "history": history,
        }
        publish_state(self.repo, run_id, state, expected_revision=-1)

        self.assertEqual(validate_run(self.repo, run_id), [])

    def test_graphless_milestone_blocks_node_scope_and_run_wide_implementation(
        self,
    ) -> None:
        from kapisch_core.validation import validate_run

        for suffix, stage in (
            (
                "12",
                {
                    "stage_id": "s-00000000000000000000000000000012",
                    "stage_kind": "research",
                    "sequence": 0,
                    "role": "researcher",
                    "status": "planned",
                    "producer": "controller",
                    "evidence": [],
                    "scope_digest": "c" * 64,
                    "node_id": "n-00000000000000000000000000000012",
                },
            ),
            (
                "13",
                {
                    "stage_id": "s-00000000000000000000000000000013",
                    "stage_kind": "implement",
                    "sequence": 0,
                    "role": "implementer",
                    "status": "planned",
                    "producer": "controller",
                    "evidence": [],
                    "scope_digest": "d" * 64,
                },
            ),
        ):
            run_id = f"run-graphless-block-{suffix}"
            state = {
                **self.state,
                "run_id": run_id,
                "workflow": "milestone",
                "history": [stage],
            }
            self._write_state(state)
            errors = validate_run(self.repo, run_id)
            self.assertTrue(
                any(
                    "graph" in error.message.lower() or "node" in error.message.lower()
                    for error in errors
                ),
                errors,
            )

    def test_validates_milestone_scope_graph_and_plan_binding(self) -> None:
        self._use_legacy_bundle()
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        run_id = "run-graph-scope"
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        (run_root / "scopes").mkdir(parents=True)
        (run_root / "graphs").mkdir()
        (run_root / "plans").mkdir()
        node_id = "n-00000000000000000000000000000001"
        other_node_id = "n-00000000000000000000000000000002"
        scopes = []
        for index, current_node in enumerate((node_id, other_node_id), 1):
            scope = {
                "protocol_version": 3,
                "run_id": run_id,
                "node_id": current_node,
                "requirements": f"Implement requirement {index}.",
            }
            body = self.canonical_json(scope)
            path = f"scopes/node-{index}.json"
            (run_root / path).write_bytes(body)
            scopes.append(
                {
                    "node_id": current_node,
                    "scope": {"path": path, "sha256": hashlib.sha256(body).hexdigest()},
                    "depends_on": [],
                }
            )
        graph = {
            "protocol_version": 3,
            "run_id": run_id,
            "plan_id": "plan-1",
            "nodes": scopes,
        }
        graph_bytes = self.canonical_json(graph)
        graph_ref = {
            "path": "graphs/plan-1.json",
            "sha256": hashlib.sha256(graph_bytes).hexdigest(),
        }
        (run_root / graph_ref["path"]).write_bytes(graph_bytes)
        plan = {"plan_id": "plan-1", "approved": True, "graph": graph_ref}
        plan_bytes = self.canonical_json(plan)
        plan_ref = {
            "plan_id": "plan-1",
            "path": "plans/plan-1.json",
            "sha256": hashlib.sha256(plan_bytes).hexdigest(),
        }
        (run_root / plan_ref["path"]).write_bytes(plan_bytes)
        stage = {
            "stage_id": "s-00000000000000000000000000000001",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [
                {"kind": "graph", **graph_ref},
                {
                    "kind": "plan",
                    "path": plan_ref["path"],
                    "sha256": plan_ref["sha256"],
                },
            ],
            "scope_digest": scopes[0]["scope"]["sha256"],
            "node_id": node_id,
        }
        initial = {
            **self.state,
            "run_id": run_id,
            "workflow": "milestone",
            "revision": 0,
            "history": [],
            "graph": graph_ref,
            "approved_plan": plan_ref,
        }
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        state = {**initial, "revision": 1, "history": [stage]}
        publish_state(self.repo, run_id, state, expected_revision=0)
        self.assertEqual(validate_run(self.repo, run_id), [])
        expanded_bundle = json.loads(self.bundle)
        expanded_bundle["schemas"]["run"]["$defs"]["scope_document"]["properties"][
            "unowned_authority"
        ] = {"type": "boolean"}
        expanded_digest = store_bundle(self.repo, self.canonical_json(expanded_bundle))
        malformed_scope = {
            "protocol_version": 3,
            "run_id": run_id,
            "node_id": node_id,
            "requirements": "Implement requirement.",
            "unowned_authority": True,
        }
        malformed_bytes = self.canonical_json(malformed_scope)
        malformed_ref = {
            "path": "scopes/malformed.json",
            "sha256": hashlib.sha256(malformed_bytes).hexdigest(),
        }
        (run_root / malformed_ref["path"]).write_bytes(malformed_bytes)
        malformed_graph = {
            **graph,
            "nodes": [
                {**scopes[0], "scope": malformed_ref},
                scopes[1],
            ],
        }
        malformed_graph_bytes = self.canonical_json(malformed_graph)
        malformed_graph_ref = {
            "path": "graphs/plan-malformed.json",
            "sha256": hashlib.sha256(malformed_graph_bytes).hexdigest(),
        }
        (run_root / malformed_graph_ref["path"]).write_bytes(malformed_graph_bytes)
        malformed_plan = {"plan_id": "plan-1", "graph": malformed_graph_ref}
        malformed_plan_bytes = self.canonical_json(malformed_plan)
        malformed_plan_ref = {
            "plan_id": "plan-1",
            "path": "plans/plan-malformed.json",
            "sha256": hashlib.sha256(malformed_plan_bytes).hexdigest(),
        }
        (run_root / malformed_plan_ref["path"]).write_bytes(malformed_plan_bytes)
        malformed_stage = {
            **stage,
            "scope_digest": malformed_ref["sha256"],
            "evidence": [
                {"kind": "graph", **malformed_graph_ref},
                {
                    "kind": "plan",
                    "path": malformed_plan_ref["path"],
                    "sha256": malformed_plan_ref["sha256"],
                },
            ],
        }
        malformed_state = {
            **state,
            "revision": 2,
            "bundle_digest": expanded_digest,
            "graph": malformed_graph_ref,
            "approved_plan": malformed_plan_ref,
            "history": [malformed_stage],
        }
        self._write_state(malformed_state)
        errors = validate_run(self.repo, run_id)
        self.assertTrue(
            any(error.code == "identity-contract-unsupported" for error in errors),
            errors,
        )
        self._write_state(state)
        without_witness = {
            **state,
            "revision": 2,
            "history": [{**stage, "evidence": []}],
        }
        self._write_state(without_witness)
        self.assertTrue(validate_run(self.repo, run_id))
        self._write_state(state)

        changed_graph = {
            **graph,
            "plan_id": "plan-2",
            "nodes": [
                scopes[0],
                {**scopes[1], "depends_on": [node_id]},
            ],
        }
        changed_graph_bytes = self.canonical_json(changed_graph)
        changed_graph_ref = {
            "path": "graphs/plan-2.json",
            "sha256": hashlib.sha256(changed_graph_bytes).hexdigest(),
        }
        (run_root / changed_graph_ref["path"]).write_bytes(changed_graph_bytes)
        changed_plan = {"plan_id": "plan-2", "graph": changed_graph_ref}
        changed_plan_bytes = self.canonical_json(changed_plan)
        changed_plan_ref = {
            "plan_id": "plan-2",
            "path": "plans/plan-2.json",
            "sha256": hashlib.sha256(changed_plan_bytes).hexdigest(),
        }
        (run_root / changed_plan_ref["path"]).write_bytes(changed_plan_bytes)
        rebound = {
            **state,
            "revision": 3,
            "graph": changed_graph_ref,
            "approved_plan": changed_plan_ref,
        }
        self._write_state(rebound)
        errors = validate_run(self.repo, run_id)
        self.assertTrue(
            any(
                "binding" in error.message.lower() or "graph" in error.message.lower()
                for error in errors
            ),
            errors,
        )

    def test_uncertainty_observation_owns_operation_and_required_evidence(self) -> None:
        from kapisch_core.validation import validate_run

        valid, stage, evidence = self._publish_uncertain_attempt(
            "run-uncertainty-owner", 20
        )
        self.assertEqual(validate_run(self.repo, valid["run_id"]), [])

        missing_request = {
            **valid,
            "revision": 2,
            "history": [
                stage,
                {
                    **valid["history"][1],
                    "sequence": 1,
                    "evidence": [
                        ref
                        for ref in evidence
                        if not ref["path"].startswith("requests/")
                    ],
                },
            ],
        }
        self._write_state(missing_request)
        self.assertTrue(validate_run(self.repo, valid["run_id"]))

        other_stage = {
            **stage,
            "stage_id": "s-00000000000000000000000000000021",
            "sequence": 2,
            "stage_kind": "research",
            "role": "researcher",
            "status": "planned",
            "evidence": [],
            "scope_digest": "1" * 64,
        }
        borrowed = {
            **other_stage,
            "sequence": 3,
            "status": "dispatch-uncertain",
            "evidence": evidence,
        }
        borrowed_state = {
            **valid,
            "revision": 2,
            "history": [*valid["history"], other_stage, borrowed],
        }
        self._write_state(borrowed_state)
        self.assertTrue(validate_run(self.repo, valid["run_id"]))

        planned_with_future_fact = {**stage, "evidence": evidence}
        completed = {**planned_with_future_fact, "sequence": 1, "status": "complete"}
        premature = {
            **valid,
            "revision": 2,
            "history": [planned_with_future_fact, completed],
        }
        self._write_state(premature)
        self.assertTrue(validate_run(self.repo, valid["run_id"]))

    def test_operation_request_must_match_current_plan_for_graph_free_and_run_wide_milestone(
        self,
    ) -> None:
        self._use_legacy_bundle()
        from kapisch_core.validation import validate_run

        for number, workflow in ((22, "task"), (23, "milestone")):
            run_id = f"run-plan-binding-{number}"
            plans = self.repo / ".kapisch/v3/runs" / run_id / "plans"
            plans.mkdir(parents=True)
            refs = []
            for name in ("plan-a", "plan-b"):
                body = self.canonical_json({"plan_id": name})
                (plans / f"{name}.json").write_bytes(body)
                refs.append(
                    {
                        "plan_id": name,
                        "path": f"plans/{name}.json",
                        "sha256": hashlib.sha256(body).hexdigest(),
                    }
                )
            valid, _, _ = self._publish_uncertain_attempt(
                run_id, number, workflow, refs[0]
            )
            self.assertEqual(validate_run(self.repo, run_id), [])
            tampered = {**valid, "revision": 2, "approved_plan": refs[1]}
            self._write_state(tampered)
            self.assertTrue(validate_run(self.repo, run_id))

    def test_approved_plan_artifact_is_resolved_without_graph(self) -> None:
        self._use_legacy_bundle()
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        for number, workflow in ((24, "task"), (25, "milestone")):
            run_id = f"run-plan-artifact-{number}"
            run_root = self.repo / ".kapisch/v3/runs" / run_id
            plans = run_root / "plans"
            plans.mkdir(parents=True)
            body = self.canonical_json({"plan_id": "plan-valid"})
            (plans / "valid.json").write_bytes(body)
            valid_ref = {
                "plan_id": "plan-valid",
                "path": "plans/valid.json",
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            state = {
                **self.state,
                "run_id": run_id,
                "workflow": workflow,
                "history": [],
                "approved_plan": valid_ref,
            }
            publish_state(self.repo, run_id, state, expected_revision=-1)
            self.assertEqual(validate_run(self.repo, run_id), [])
            for ref in (
                {**valid_ref, "path": "plans/missing.json"},
                {**valid_ref, "sha256": "0" * 64},
                {**valid_ref, "plan_id": "plan-other"},
            ):
                self._write_state({**state, "approved_plan": ref})
                self.assertTrue(validate_run(self.repo, run_id))

    def test_new_bundle_rejects_legacy_approved_plan_reference_shape(self) -> None:
        from kapisch_core.protocol import publish_state

        run_id = "run-new-bundle-legacy-plan-ref"
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        plan_body = self.canonical_json({"plan_id": "plan-matching"})
        plan_path = "plans/plan-matching.json"
        (run_root / plan_path).parent.mkdir(parents=True)
        (run_root / plan_path).write_bytes(plan_body)
        state = {
            **self.state,
            "run_id": run_id,
            "approved_plan": {
                "plan_id": "plan-matching",
                "path": plan_path,
                "sha256": hashlib.sha256(plan_body).hexdigest(),
            },
        }
        with self.assertRaisesRegex(
            ValueError, "missing gate_approval_ref.*unknown field sha256"
        ):
            publish_state(self.repo, run_id, state, expected_revision=-1)

        self.assertFalse(
            (self.repo / ".kapisch/v3/runs" / run_id / "state.json").exists()
        )

    def test_invocation_fact_must_be_cited_by_owning_attempt(self) -> None:
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            publish_uncertainty,
            reserve_operation,
        )
        from kapisch_core.validation import validate_run

        run_id = "run-invocation-owner"
        operation_id = "op-00000000000000000000000000000006"
        first = {
            "stage_id": "s-00000000000000000000000000000006",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "6" * 64,
        }
        initial = {**self.state, "run_id": run_id, "history": [first]}
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": first["stage_id"],
            "role": first["role"],
            "bundle_digest": self.digest,
            "scope_digest": first["scope_digest"],
            "adapter_binding": {
                "adapter_id": "fake",
                "lookup_context": "owner-context",
            },
        }
        request_path, request_digest = persist_request(
            self.repo, run_id, operation_id, packet
        )
        planned = reserve_operation(
            self.repo,
            run_id,
            operation_id,
            first["stage_id"],
            first["role"],
            {"path": request_path, "sha256": request_digest},
            packet["adapter_binding"],
        )
        planned_bytes = canonical_json(planned)
        uncertain_bytes = canonical_json({**planned, "status": "dispatch-uncertain"})
        planned_ref = {
            "kind": "protocol",
            "path": f"invocations/{operation_id}/planned.json",
            "sha256": hashlib.sha256(planned_bytes).hexdigest(),
        }
        uncertainty_ref = {
            "kind": "protocol",
            "path": f"invocations/{operation_id}/dispatch-uncertain.json",
            "sha256": hashlib.sha256(uncertain_bytes).hexdigest(),
        }
        request_ref = {
            "kind": "request",
            "path": request_path,
            "sha256": request_digest,
        }
        uncertain_row = {
            **first,
            "sequence": 1,
            "status": "dispatch-uncertain",
            "evidence": [request_ref, planned_ref, uncertainty_ref],
        }
        publish_uncertainty(
            self.repo,
            run_id,
            {**initial, "revision": 1, "history": [first, uncertain_row]},
            0,
            operation_id,
        )

        second = {
            "stage_id": "s-00000000000000000000000000000007",
            "stage_kind": "research",
            "sequence": 2,
            "role": "researcher",
            "status": "planned",
            "producer": "controller",
            "evidence": [uncertainty_ref],
            "scope_digest": "7" * 64,
        }
        tampered = {
            **initial,
            "revision": 2,
            "history": [
                first,
                {**uncertain_row, "evidence": [request_ref, planned_ref]},
                second,
            ],
        }
        state_path = self.repo / ".kapisch/v3/runs" / run_id / "state.json"
        state_path.write_bytes(canonical_json(tampered))
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_blocked_before_dispatch_requires_reservation_without_uncertainty(
        self,
    ) -> None:
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            reserve_operation,
        )
        from kapisch_core.validation import validate_run

        run_id = "run-blocked-before-dispatch"
        operation_id = "op-00000000000000000000000000000024"
        stage = {
            "stage_id": "s-00000000000000000000000000000024",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "4" * 64,
        }
        initial = {**self.state, "run_id": run_id, "history": [stage]}
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage["stage_id"],
            "role": stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {
                "adapter_id": "fake",
                "lookup_context": "blocked-context",
            },
        }
        request_path, request_digest = persist_request(
            self.repo, run_id, operation_id, packet
        )
        planned = reserve_operation(
            self.repo,
            run_id,
            operation_id,
            stage["stage_id"],
            stage["role"],
            {"path": request_path, "sha256": request_digest},
            packet["adapter_binding"],
        )
        operation_root = (
            self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id
        )
        blocked_bytes = self.canonical_json({**planned, "status": "blocked"})
        (operation_root / "blocked.json").write_bytes(blocked_bytes)
        evidence = [
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/planned.json",
                "sha256": hashlib.sha256(self.canonical_json(planned)).hexdigest(),
            },
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/blocked.json",
                "sha256": hashlib.sha256(blocked_bytes).hexdigest(),
            },
        ]
        blocked = {**stage, "sequence": 1, "status": "blocked", "evidence": evidence}
        publish_state(
            self.repo,
            run_id,
            {**initial, "revision": 1, "history": [stage, blocked]},
            0,
        )
        self.assertEqual(validate_run(self.repo, run_id), [])

    def test_observed_invocation_fact_requires_prior_uncertainty(self) -> None:
        from kapisch_core.validation import validate_run

        valid, stage, evidence = self._publish_uncertain_attempt(
            "run-observed-order", 24
        )
        self.assertEqual(validate_run(self.repo, valid["run_id"]), [])
        operation_id = next(
            ref["path"].split("/")[1]
            for ref in evidence
            if ref["path"].endswith("/planned.json")
        )
        run_root = self.repo / ".kapisch/v3/runs" / valid["run_id"]
        planned = json.loads(
            (run_root / "invocations" / operation_id / "planned.json").read_bytes()
        )
        observed_bytes = self.canonical_json({**planned, "status": "observed"})
        observed_path = f"invocations/{operation_id}/observed.json"
        (run_root / observed_path).write_bytes(observed_bytes)
        observed_ref = {
            "kind": "protocol",
            "path": observed_path,
            "sha256": hashlib.sha256(observed_bytes).hexdigest(),
        }
        uncertain = valid["history"][1]
        completed = {
            **uncertain,
            "sequence": 2,
            "status": "complete",
            "evidence": [*evidence, observed_ref],
        }
        valid_observation = {
            **valid,
            "revision": 2,
            "history": [stage, uncertain, completed],
        }
        self._write_state(valid_observation)
        self.assertEqual(validate_run(self.repo, valid["run_id"]), [])

        premature_stage = {**stage, "evidence": [observed_ref]}
        premature_uncertain = {**uncertain, "evidence": [observed_ref, *evidence]}
        premature = {
            **valid,
            "revision": 1,
            "history": [premature_stage, premature_uncertain],
        }
        self._write_state(premature)
        self.assertTrue(validate_run(self.repo, valid["run_id"]))

    def test_request_cannot_be_consumed_before_owning_attempt_creation(self) -> None:
        from kapisch_core.validation import validate_run

        valid, stage, evidence = self._publish_uncertain_attempt(
            "run-request-before-attempt", 32
        )
        request_ref = next(ref for ref in evidence if ref["kind"] == "request")
        unrelated = {
            "stage_id": "s-00000000000000000000000000000033",
            "stage_kind": "research",
            "sequence": 0,
            "role": "researcher",
            "status": "planned",
            "producer": "controller",
            "evidence": [request_ref],
            "scope_digest": "3" * 64,
        }
        creation = {**stage, "sequence": 1}
        uncertain = {**valid["history"][1], "sequence": 2}
        impossible = {
            **valid,
            "revision": 2,
            "history": [unrelated, creation, uncertain],
        }
        self._write_state(impossible)
        errors = validate_run(self.repo, valid["run_id"])
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_nonplanned_fact_cannot_be_borrowed_from_another_attempt(self) -> None:
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            reserve_operation,
        )
        from kapisch_core.validation import validate_run

        run_id = "run-borrowed-observation"
        operation_id = "op-00000000000000000000000000000008"
        first = {
            "stage_id": "s-00000000000000000000000000000008",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "8" * 64,
        }
        initial = {**self.state, "run_id": run_id, "history": [first]}
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": first["stage_id"],
            "role": first["role"],
            "bundle_digest": self.digest,
            "scope_digest": first["scope_digest"],
            "adapter_binding": {
                "adapter_id": "fake",
                "lookup_context": "owner-context",
            },
        }
        request_path, request_digest = persist_request(
            self.repo, run_id, operation_id, packet
        )
        planned = reserve_operation(
            self.repo,
            run_id,
            operation_id,
            first["stage_id"],
            first["role"],
            {"path": request_path, "sha256": request_digest},
            packet["adapter_binding"],
        )
        planned_bytes = self.canonical_json(planned)
        planned_ref = {
            "kind": "protocol",
            "path": f"invocations/{operation_id}/planned.json",
            "sha256": hashlib.sha256(planned_bytes).hexdigest(),
        }
        request_ref = {
            "kind": "request",
            "path": request_path,
            "sha256": request_digest,
        }
        complete = {
            **first,
            "sequence": 1,
            "status": "complete",
            "evidence": [request_ref, planned_ref],
        }
        complete_state = {**initial, "revision": 1, "history": [first, complete]}
        publish_state(self.repo, run_id, complete_state, expected_revision=0)

        observed = {**planned, "status": "observed"}
        observed_bytes = self.canonical_json(observed)
        (
            self.repo
            / ".kapisch/v3/runs"
            / run_id
            / "invocations"
            / operation_id
            / "observed.json"
        ).write_bytes(observed_bytes)
        observed_ref = {
            "kind": "protocol",
            "path": f"invocations/{operation_id}/observed.json",
            "sha256": hashlib.sha256(observed_bytes).hexdigest(),
        }
        unrelated = {
            "stage_id": "s-00000000000000000000000000000009",
            "stage_kind": "research",
            "sequence": 2,
            "role": "researcher",
            "status": "planned",
            "producer": "controller",
            "evidence": [observed_ref],
            "scope_digest": "9" * 64,
        }
        publish_state(
            self.repo,
            run_id,
            {**complete_state, "revision": 2, "history": [first, complete, unrelated]},
            expected_revision=1,
        )
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_restored_planned_prefix_is_vetoed_by_uncertain_fact(self) -> None:
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import (
            persist_request,
            publish_state,
            publish_uncertainty,
            reserve_operation,
        )
        from kapisch_core.validation import validate_run

        run_id = "run-uncertain-veto"
        operation_id = "op-00000000000000000000000000000002"
        stage = {
            "stage_id": "s-00000000000000000000000000000002",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "1" * 64,
        }
        initial = {**self.state, "run_id": run_id, "history": [stage]}
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage["stage_id"],
            "role": stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "test-context"},
        }
        path, request_digest = persist_request(self.repo, run_id, operation_id, packet)
        planned = reserve_operation(
            self.repo,
            run_id,
            operation_id,
            stage["stage_id"],
            stage["role"],
            {"path": path, "sha256": request_digest},
            packet["adapter_binding"],
        )
        planned_bytes = canonical_json(planned)
        uncertain_bytes = canonical_json({**planned, "status": "dispatch-uncertain"})
        evidence = [
            {"kind": "request", "path": path, "sha256": request_digest},
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/planned.json",
                "sha256": hashlib.sha256(planned_bytes).hexdigest(),
            },
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/dispatch-uncertain.json",
                "sha256": hashlib.sha256(uncertain_bytes).hexdigest(),
            },
        ]
        uncertain = {
            **stage,
            "sequence": 1,
            "status": "dispatch-uncertain",
            "evidence": evidence,
        }
        publish_uncertainty(
            self.repo,
            run_id,
            {**initial, "revision": 1, "history": [stage, uncertain]},
            0,
            operation_id,
        )
        state_path = self.repo / ".kapisch/v3/runs" / run_id / "state.json"
        state_path.write_bytes(canonical_json(initial))
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any(error.code == "inventory-veto" for error in errors), errors)

    def test_graph_cycle_is_blocked(self) -> None:
        self._use_legacy_bundle()
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        run_id = "run-graph-cycle"
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        (run_root / "graphs").mkdir(parents=True)
        (run_root / "plans").mkdir()
        nodes = []
        for index in (1, 2):
            node_id = f"n-{index:032x}"
            scope = {
                "protocol_version": 3,
                "run_id": run_id,
                "node_id": node_id,
                "requirements": f"Requirement {index}.",
            }
            scope_path = f"scopes/node-{index}.json"
            scope_file = run_root / scope_path
            scope_file.parent.mkdir(exist_ok=True)
            scope_bytes = self.canonical_json(scope)
            scope_file.write_bytes(scope_bytes)
            nodes.append(
                {
                    "node_id": node_id,
                    "scope": {
                        "path": scope_path,
                        "sha256": hashlib.sha256(scope_bytes).hexdigest(),
                    },
                    "depends_on": [f"n-{(3 - index):032x}"],
                }
            )
        graph_bytes = self.canonical_json(
            {
                "protocol_version": 3,
                "run_id": run_id,
                "plan_id": "plan-cycle",
                "nodes": nodes,
            }
        )
        graph_ref = {
            "path": "graphs/plan-cycle.json",
            "sha256": hashlib.sha256(graph_bytes).hexdigest(),
        }
        (run_root / graph_ref["path"]).write_bytes(graph_bytes)
        plan_bytes = self.canonical_json({"plan_id": "plan-cycle", "graph": graph_ref})
        (run_root / "plans/plan-cycle.json").write_bytes(plan_bytes)
        initial = {**self.state, "run_id": run_id, "workflow": "milestone"}
        state = {
            **initial,
            "revision": 1,
            "approved_plan": {
                "plan_id": "plan-cycle",
                "path": "plans/plan-cycle.json",
                "sha256": hashlib.sha256(plan_bytes).hexdigest(),
            },
            "graph": graph_ref,
        }
        publish_state(self.repo, run_id, initial, expected_revision=-1)
        publish_state(self.repo, run_id, state, expected_revision=0)
        errors = validate_run(self.repo, run_id)
        self.assertTrue(any("cycle" in error.message for error in errors), errors)

    def test_graph_node_ids_must_use_exact_syntax(self) -> None:
        self._use_legacy_bundle()
        from kapisch_core.protocol import publish_state
        from kapisch_core.validation import validate_run

        cases = (
            ("node", "n-00000000000000000000000000000041\n", [], "graph node_id"),
            (
                "dependency",
                "n-00000000000000000000000000000042",
                ["n-00000000000000000000000000000043\n"],
                "graph dependency node_id",
            ),
        )
        for suffix, node_id, dependencies, expected_error in cases:
            run_id = f"run-graph-id-{suffix}"
            run_root = self.repo / ".kapisch/v3/runs" / run_id
            (run_root / "scopes").mkdir(parents=True)
            (run_root / "graphs").mkdir()
            (run_root / "plans").mkdir()
            scope = {
                "protocol_version": 3,
                "run_id": run_id,
                "node_id": node_id,
                "requirements": "Exact node identity required.",
            }
            scope_bytes = self.canonical_json(scope)
            (run_root / "scopes/node.json").write_bytes(scope_bytes)
            node = {
                "node_id": node_id,
                "scope": {
                    "path": "scopes/node.json",
                    "sha256": hashlib.sha256(scope_bytes).hexdigest(),
                },
                "depends_on": dependencies,
            }
            graph_bytes = self.canonical_json(
                {
                    "protocol_version": 3,
                    "run_id": run_id,
                    "plan_id": "plan-id",
                    "nodes": [node],
                }
            )
            graph_ref = {
                "path": "graphs/plan-id.json",
                "sha256": hashlib.sha256(graph_bytes).hexdigest(),
            }
            (run_root / graph_ref["path"]).write_bytes(graph_bytes)
            plan_bytes = self.canonical_json({"plan_id": "plan-id", "graph": graph_ref})
            plan_ref = {
                "plan_id": "plan-id",
                "path": "plans/plan-id.json",
                "sha256": hashlib.sha256(plan_bytes).hexdigest(),
            }
            (run_root / plan_ref["path"]).write_bytes(plan_bytes)
            state = {
                **self.state,
                "run_id": run_id,
                "workflow": "milestone",
                "revision": 0,
                "history": [],
                "graph": graph_ref,
                "approved_plan": plan_ref,
            }
            publish_state(self.repo, run_id, state, expected_revision=-1)
            errors = validate_run(self.repo, run_id)
            self.assertTrue(
                any(expected_error in error.message for error in errors),
                (suffix, errors),
            )

    def test_rejects_multiple_reservations_for_one_attempt(self) -> None:
        from kapisch_core.protocol import persist_request, publish_state
        from kapisch_core.validation import validate_run

        run_id = "run-duplicate-attempt-operations"
        stage = {
            "stage_id": "s-00000000000000000000000000000004",
            "stage_kind": "implement",
            "sequence": 0,
            "role": "implementer",
            "status": "planned",
            "producer": "controller",
            "evidence": [],
            "scope_digest": "2" * 64,
        }
        state = {**self.state, "run_id": run_id, "history": [stage]}
        publish_state(self.repo, run_id, state, expected_revision=-1)
        evidence = []
        for suffix in ("04", "05"):
            operation_id = f"op-{int(suffix):032x}"
            packet = {
                "run_id": run_id,
                "operation_id": operation_id,
                "stage_id": stage["stage_id"],
                "role": stage["role"],
                "bundle_digest": self.digest,
                "scope_digest": stage["scope_digest"],
                "adapter_binding": {
                    "adapter_id": "fake",
                    "lookup_context": "ctx-duplicate",
                },
            }
            request_path, request_digest = persist_request(
                self.repo, run_id, operation_id, packet
            )
            planned = {
                "protocol_version": 3,
                "operation_id": operation_id,
                "run_id": run_id,
                "stage_id": stage["stage_id"],
                "role": stage["role"],
                "request_digest": request_digest,
                "status": "planned",
                "request": {"path": request_path, "sha256": request_digest},
                "adapter_binding": packet["adapter_binding"],
            }
            planned_bytes = self.canonical_json(planned)
            path = (
                self.repo
                / ".kapisch/v3/runs"
                / run_id
                / "invocations"
                / operation_id
                / "planned.json"
            )
            path.parent.mkdir(parents=True)
            path.write_bytes(planned_bytes)
            evidence.extend(
                [
                    {"kind": "request", "path": request_path, "sha256": request_digest},
                    {
                        "kind": "protocol",
                        "path": f"invocations/{operation_id}/planned.json",
                        "sha256": hashlib.sha256(planned_bytes).hexdigest(),
                    },
                ]
            )
        state["history"] = [
            stage,
            {**stage, "sequence": 1, "status": "blocked", "evidence": evidence},
        ]
        state_path = self.repo / ".kapisch/v3/runs" / run_id / "state.json"
        state_path.write_bytes(self.canonical_json(state))
        errors = validate_run(self.repo, run_id)
        self.assertTrue(
            any(
                error.code == "inventory-veto"
                and "multiple operation reservations" in error.message
                for error in errors
            ),
            errors,
        )

    def test_refuses_v2_and_missing_retained_bundle(self) -> None:
        from kapisch_core.validation import validate_run

        self._write_state()
        v2 = self.repo / ".kapisch/runs/run-v2"
        v2.mkdir(parents=True)
        (v2 / "state.toml").write_text("protocol_version = 2\n", encoding="utf-8")
        errors = validate_run(self.repo, "run-v2")
        self.assertTrue(errors)
        self.assertTrue(any(error.code == "v2-refused" for error in errors))

        missing = {
            **self.state,
            "run_id": "run-missing-bundle",
            "bundle_digest": "f" * 64,
        }
        self._write_state(missing)
        errors = validate_run(self.repo, "run-missing-bundle")
        self.assertTrue(errors)
        self.assertTrue(
            any(error.code == "bundle-unavailable" for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
