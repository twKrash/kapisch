from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kapisch_core._human_evidence import (
    ExternalArtifactInput,
    ExternalInputSource,
    GateApprovalTarget,
    GateIdentity,
    HumanActionOrigin,
    ObservedGateAction,
    validate_external_human_approval_artifact,
)
from kapisch_core.bundle import canonical_json


class ExternalHumanApprovalEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "protocol_version": 3,
            "gate_contract": "human-gate/1",
            "run_id": "run-1",
            "gate_id": "gate-1",
            "identity": {"kind": "decision", "id": "decision-1"},
            "scope_digest": "b" * 64,
            "gate_kind": "repository-decision",
            "subject": {
                "acceptance_contract": "global-authority/1",
                "origin_run_id": "run-1",
                "snapshot_id": "snapshot-1",
                "decision_id": "decision-1",
                "decision": "approve repository decision",
                "scope_ref": {
                    "origin_run_id": "run-1",
                    "scope_id": "scope-1",
                    "sha256": "b" * 64,
                },
                "applicability": {"mode": "all"},
                "bundle_digest": "c" * 64,
                "source_dependencies": [],
                "authority_basis": [],
                "amends": [],
                "supersedes": [],
            },
        }
        self.target = GateApprovalTarget(
            "run-1",
            "gate-1",
            GateIdentity("decision", "decision-1"),
            hashlib.sha256(canonical_json(self.payload)).hexdigest(),
            "b" * 64,
        )
        self.artifact = {
            "protocol_version": 3,
            "run_id": "run-1",
            "gate_id": "gate-1",
            "identity": {"kind": "decision", "id": "decision-1"},
            "decision": "approve",
            "target": self.target.target,
            "scope_digest": self.target.scope_digest,
        }

    def _input(self, data: bytes) -> ExternalArtifactInput:
        return ExternalArtifactInput(
            "external-source", data, ExternalInputSource.EXTERNALLY_SUPPLIED
        )

    def test_exact_canonical_artifact_binds_complete_gate_target(self) -> None:
        validate_external_human_approval_artifact(
            self._input(canonical_json(self.artifact)), self.target
        )

    def test_artifact_rejects_every_retargeted_or_unsupported_field(self) -> None:
        for field, value in (
            ("protocol_version", True),
            ("protocol_version", 3.0),
            ("run_id", "other-run"),
            ("gate_id", "other-gate"),
            ("identity", {"kind": "decision", "id": "plan-1"}),
            ("decision", "reject"),
            ("target", "e" * 64),
            ("scope_digest", "f" * 64),
            ("unexpected", "field"),
        ):
            with self.subTest(field=field, value=value):
                artifact = copy.deepcopy(self.artifact)
                artifact[field] = value
                with self.assertRaises(ValueError):
                    validate_external_human_approval_artifact(
                        self._input(canonical_json(artifact)), self.target
                    )

    def test_artifact_rejects_noncanonical_duplicate_and_malformed_json(self) -> None:
        noncanonical = b'{ "decision":"approve" }\n'
        duplicate = (
            b'{"protocol_version":3,"protocol_version":3,"run_id":"run-1",'
            b'"gate_id":"gate-1","identity":{"kind":"plan","id":"plan-1"},'
            b'"decision":"approve","target":"'
            + self.target.target.encode()
            + b'","scope_digest":"'
            + self.target.scope_digest.encode()
            + b'"}\n'
        )
        for data in (noncanonical, duplicate, b"not-json"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_external_human_approval_artifact(
                    self._input(data), self.target
                )

    def test_controller_generated_source_marker_is_rejected(self) -> None:
        evidence = ExternalArtifactInput(
            "source",
            canonical_json(self.artifact),
            "controller-generated",  # type: ignore[arg-type]
        )
        with self.assertRaisesRegex(ValueError, "source is not externally supplied"):
            validate_external_human_approval_artifact(evidence, self.target)

    def test_invalid_identity_kinds_fail_before_artifact_parse(self) -> None:
        for kind in (["plan"], {"kind": "plan"}, None, 7, "", "unsupported"):
            with self.subTest(kind=kind):
                invalid_target = GateApprovalTarget(
                    self.target.run_id,
                    self.target.gate_id,
                    GateIdentity(kind, self.target.identity.id),
                    self.target.target,
                    self.target.scope_digest,
                )
                with self.assertRaises(ValueError):
                    validate_external_human_approval_artifact(
                        self._input(b"not-json"), invalid_target
                    )

    def test_invalid_expected_target_rejected_before_artifact_parse(self) -> None:
        invalid_target = GateApprovalTarget(
            "run-1",
            "gate-1",
            {"kind": "plan", "id": "plan-1"},
            self.target.target,
            "b" * 64,
        )
        with self.assertRaises(TypeError):
            validate_external_human_approval_artifact(
                self._input(b"not-json"), invalid_target
            )


class GateApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        from kapisch_core.advisory import propose_scope
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        bundle_bytes = (
            Path(__file__).resolve().parents[2] / "core/dist/core-bundle.json"
        ).read_bytes()
        self.bundle_digest = store_bundle(self.repo, bundle_bytes)
        scope_ref = propose_scope(
            self.repo, "run-1", "scope-1", "requirements", {"mode": "all"}
        )
        self.scope_ref = {
            "origin_run_id": scope_ref.origin_run_id,
            "scope_id": scope_ref.scope_id,
            "sha256": scope_ref.sha256,
        }
        state = {
            "protocol_version": 3,
            "run_id": "run-1",
            "bundle_digest": self.bundle_digest,
            "workflow": "task",
            "revision": 0,
            "history": [],
            "identity_contract": "stage-attempt/1",
            "scope_ref": self.scope_ref,
        }
        publish_state(self.repo, "run-1", state, expected_revision=-1)
        self.payload = self._repository_payload()
        self.canonical_json = canonical_json
        self.target: GateApprovalTarget = self._target(self.payload)
        self.artifact_bytes = self._artifact(self.target)

    def _target(self, payload: dict) -> GateApprovalTarget:
        return GateApprovalTarget(
            payload["run_id"],
            payload["gate_id"],
            GateIdentity(**payload["identity"]),
            hashlib.sha256(self.canonical_json(payload)).hexdigest(),
            payload["scope_digest"],
        )

    def _artifact(self, target: GateApprovalTarget) -> bytes:
        return self.canonical_json(
            {
                "protocol_version": 3,
                "run_id": target.run_id,
                "gate_id": target.gate_id,
                "identity": {"kind": target.identity.kind, "id": target.identity.id},
                "decision": "approve",
                "target": target.target,
                "scope_digest": target.scope_digest,
            }
        )

    def _external_input(self, data: bytes) -> ExternalArtifactInput:
        return ExternalArtifactInput(
            "human-submission", data, ExternalInputSource.EXTERNALLY_SUPPLIED
        )

    def _receipt(self, target: GateApprovalTarget | None = None) -> ObservedGateAction:
        if target is None:
            target = self._target(self.payload)
        return ObservedGateAction(
            HumanActionOrigin.INBOUND_HUMAN,
            "host",
            "session",
            "action-1",
            target.run_id,
            target.gate_id,
            target.identity,
            target.target,
            target.scope_digest,
            "c" * 64,
            "2026-10-03T12:00:00Z",
        )

    def _weaken_approval_schema(self) -> dict:
        from kapisch_core.storage import store_bundle

        bundle_path = self.repo / ".kapisch/v3/bundles" / f"{self.bundle_digest}.json"
        bundle = json.loads(bundle_path.read_bytes())
        bundle["schemas"]["approval"]["$defs"]["gate_approval_payload"][
            "additionalProperties"
        ] = True
        weakened_digest = store_bundle(self.repo, self.canonical_json(bundle))
        state_path = self.repo / ".kapisch/v3/runs/run-1/state.json"
        state = json.loads(state_path.read_bytes())
        state["bundle_digest"] = weakened_digest
        state_path.write_bytes(self.canonical_json(state))
        return {
            **self.payload,
            "subject": {
                **self.payload["subject"],
                "bundle_digest": weakened_digest,
            },
            "unapproved_contract_extension": True,
        }

    def test_gate_publisher_rejects_weakened_retained_approval_schema(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        payload = self._weaken_approval_schema()
        target = self._target(payload)
        evidence = self._external_input(self._artifact(target))
        with self.assertRaisesRegex(ValueError, "retained bundle"):
            publish_gate_approval(self.repo, payload, evidence)
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_gate_loader_rejects_weakened_retained_approval_schema(self) -> None:
        from kapisch_core._gate_approval import _approval_id, load_gate_approval
        from kapisch_core.storage import (
            retain_human_approval_artifact,
            store_authority_record,
        )

        payload = self._weaken_approval_schema()
        target = self._target(payload)
        payload_digest = hashlib.sha256(self.canonical_json(payload)).hexdigest()
        approval_id = _approval_id(payload, payload_digest)
        artifact_ref = retain_human_approval_artifact(self.repo, self._artifact(target))
        record = {
            "protocol_version": 3,
            "approval_contract": "human-gate-approval/1",
            "approval_id": approval_id,
            "payload": payload,
            "approved_target_sha256": payload_digest,
            "human_authority": {"kind": "external-artifact", **artifact_ref},
        }
        record_bytes = self.canonical_json(record)
        store_authority_record(self.repo, "gate-approvals", approval_id, record_bytes)
        reference = {
            "approval_id": approval_id,
            "sha256": hashlib.sha256(record_bytes).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "retained bundle"):
            load_gate_approval(self.repo, reference)

    def test_global_gate_schema_contract_rejects_semantic_drift(self) -> None:
        from kapisch_core._validation_schema import _validate_identity_contract
        from kapisch_core.bundle import verify_bundle

        bundle_path = self.repo / ".kapisch/v3/bundles" / f"{self.bundle_digest}.json"
        original = json.loads(bundle_path.read_bytes())
        mutations = (
            "open-payload",
            "missing-gate-id",
            "gate-kind",
            "identity-kind",
            "redirect-payload-ref",
            "open-human-action",
            "open-scope",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bundle = copy.deepcopy(original)
                approval = bundle["schemas"]["approval"]
                payload = approval["$defs"]["gate_approval_payload"]
                if mutation == "open-payload":
                    payload["additionalProperties"] = True
                elif mutation == "missing-gate-id":
                    payload["required"].remove("gate_id")
                elif mutation == "gate-kind":
                    payload["properties"]["gate_kind"]["enum"] = [
                        "repository-decision",
                        "plan-approval",
                    ]
                elif mutation == "identity-kind":
                    payload["properties"]["identity"]["properties"]["kind"]["enum"] = [
                        "decision",
                        "plan",
                    ]
                elif mutation == "redirect-payload-ref":
                    approval["properties"]["payload"]["$ref"] = "#/$defs/subject"
                elif mutation == "open-human-action":
                    bundle["schemas"]["human-action"]["additionalProperties"] = True
                else:
                    bundle["schemas"]["scope"]["additionalProperties"] = True

                data = self.canonical_json(bundle)
                candidate = verify_bundle(data, hashlib.sha256(data).hexdigest())
                with self.assertRaisesRegex(
                    ValueError, "global-authority/1 gate schemas"
                ):
                    _validate_identity_contract(candidate)

        annotated = copy.deepcopy(original)
        annotated["schemas"]["approval"]["description"] = "nonsemantic annotation"
        data = self.canonical_json(annotated)
        _validate_identity_contract(
            verify_bundle(data, hashlib.sha256(data).hexdigest())
        )

    def test_cold_recovery_uses_retained_bundle_without_run_state(
        self,
    ) -> None:
        from unittest.mock import patch

        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core.storage import load_bundle

        reference = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        shutil.rmtree(self.repo / ".kapisch/v3/runs/run-1")

        with patch(
            "kapisch_core._gate_approval.load_bundle",
            wraps=load_bundle,
        ) as retained_bundle_loader:
            record = load_gate_approval(self.repo, reference)
            retained_bundle_loader.assert_called_once_with(
                self.repo, self.bundle_digest
            )
        self.assertEqual(record["approval_id"], reference["approval_id"])
        self.assertEqual(record["payload"]["gate_kind"], "repository-decision")

    def test_invalid_receipt_identity_kinds_fail_before_claim_persistence(self) -> None:
        from dataclasses import replace

        from kapisch_core._human_action_ownership import publish_human_action_claim

        receipt = self._receipt()
        for kind in (["plan"], {"kind": "plan"}, None, 7, "", "unsupported"):
            with self.subTest(kind=kind):
                malformed = replace(
                    receipt, identity=GateIdentity(kind, receipt.identity.id)
                )
                with self.assertRaises(ValueError):
                    publish_human_action_claim(self.repo, malformed, self.target)
                self.assertFalse(
                    (self.repo / ".kapisch/v3/authority/human-actions").exists()
                )

    def _prepare_plan_approval(self) -> dict:
        from kapisch_core.advisory import prepare_plan_approval

        return prepare_plan_approval(
            self.repo,
            "run-1",
            "plan-gate",
            "plan-1",
            b"exact retained plan bytes",
        )

    def test_plan_candidate_is_persisted_and_anchored_before_gate_payload(self) -> None:
        from kapisch_core.protocol import load_state
        from kapisch_core.storage import load_authority_record

        payload = self._prepare_plan_approval()
        reference = payload["subject"]["plan_candidate_ref"]
        state = load_state(self.repo, "run-1")
        self.assertEqual(state["plan_candidate_ref"], reference)
        self.assertEqual(
            reference["path"],
            f".kapisch/v3/authority/plan-approval-candidates/{reference['sha256']}.json",
        )
        candidate_bytes = load_authority_record(
            self.repo, "plan-approval-candidates", reference["sha256"]
        )
        self.assertEqual(hashlib.sha256(candidate_bytes).hexdigest(), reference["sha256"])
        candidate = json.loads(candidate_bytes)
        self.assertEqual(candidate["candidate_contract"], "plan-approval-candidate/1")
        self.assertEqual(candidate["run_id"], "run-1")
        self.assertEqual(candidate["gate_id"], "plan-gate")
        self.assertEqual(candidate["plan_ref"]["plan_id"], "plan-1")
        self.assertEqual(
            candidate["plan_sha256"],
            hashlib.sha256(b"exact retained plan bytes").hexdigest(),
        )
        self.assertEqual(candidate["scope_ref"], self.scope_ref)
        self.assertEqual(candidate["bundle_digest"], self.bundle_digest)
        self.assertEqual(candidate["execution_binding"], {"mode": "graph-free"})
        self.assertEqual(payload["subject"], {"plan_candidate_ref": reference})

    def test_candidate_reference_is_durable_before_payload_construction(self) -> None:
        from unittest.mock import patch

        from kapisch_core.advisory import prepare_plan_approval
        from kapisch_core.protocol import load_state
        from kapisch_core.storage import load_authority_record, load_authority_records

        with patch(
            "kapisch_core._promotion._payload_for_candidate",
            side_effect=RuntimeError("injected payload construction failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "payload construction failure"):
                prepare_plan_approval(
                    self.repo, "run-1", "plan-gate", "plan-1", b"exact retained plan bytes"
                )
        reference = load_state(self.repo, "run-1")["plan_candidate_ref"]
        candidate = load_authority_record(
            self.repo, "plan-approval-candidates", reference["sha256"]
        )
        self.assertEqual(hashlib.sha256(candidate).hexdigest(), reference["sha256"])
        self.assertEqual(load_authority_records(self.repo, "gate-approvals"), [])

    def test_plan_approval_history_uses_exact_candidate_chain_after_run_loss(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import propose_scope, publish_plan_approval
        from kapisch_core.storage import store_bundle

        payload = self._prepare_plan_approval()
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),
        )["gate_approval_ref"]
        pinned_path = self.repo / ".kapisch/v3/bundles" / f"{self.bundle_digest}.json"
        alternate = json.loads(pinned_path.read_bytes())
        alternate["schemas"]["approval"]["description"] = "another compatible retained bundle"
        store_bundle(self.repo, self.canonical_json(alternate))

        unrelated_ref = propose_scope(
            self.repo, "unrelated-run", "unrelated-scope", "requirements", {"mode": "all"}
        )
        unrelated_identity = {
            "origin_run_id": unrelated_ref.origin_run_id,
            "scope_id": unrelated_ref.scope_id,
        }
        scope_dir = self.repo / ".kapisch/v3/authority/scopes"
        unrelated_key = hashlib.sha256(
            self.canonical_json(unrelated_identity)
        ).hexdigest()
        unrelated_path = scope_dir / f"{unrelated_key}.json"
        unrelated_path.unlink()
        unrelated_path.mkdir()

        shutil.rmtree(self.repo / ".kapisch/v3/runs/run-1")
        self.assertEqual(
            load_gate_approval(self.repo, reference)["approval_id"],
            reference["approval_id"],
        )

        unrelated_path.rmdir()
        propose_scope(
            self.repo, "unrelated-run", "unrelated-scope", "requirements", {"mode": "all"}
        )
        candidate_identity = {
            "origin_run_id": self.scope_ref["origin_run_id"],
            "scope_id": self.scope_ref["scope_id"],
        }
        candidate_key = hashlib.sha256(
            self.canonical_json(candidate_identity)
        ).hexdigest()
        candidate_path = scope_dir / f"{candidate_key}.json"
        candidate_path.unlink()
        with self.assertRaisesRegex(ValueError, "proposed scope record is missing"):
            load_gate_approval(self.repo, reference)
        propose_scope(self.repo, "run-1", "scope-1", "requirements", {"mode": "all"})

        pinned_path.unlink()
        with self.assertRaisesRegex(ValueError, "exact retained bundle is missing"):
            load_gate_approval(self.repo, reference)

    def test_delayed_old_candidate_retry_cannot_replace_current_plan_ref(self) -> None:
        from kapisch_core.advisory import (
            prepare_plan_approval,
            publish_plan_approval,
        )
        from kapisch_core.protocol import load_state

        first = self._prepare_plan_approval()
        first_evidence = self._external_input(self._artifact(self._target(first)))
        publish_plan_approval(self.repo, first, first_evidence)
        second = prepare_plan_approval(
            self.repo, "run-1", "plan-gate", "plan-1", b"replacement plan bytes"
        )
        second_evidence = self._external_input(self._artifact(self._target(second)))
        second_ref = publish_plan_approval(self.repo, second, second_evidence)

        with self.assertRaisesRegex(ValueError, "candidate is not current run anchor"):
            publish_plan_approval(self.repo, first, first_evidence)

        state = load_state(self.repo, "run-1")
        self.assertEqual(
            state["plan_candidate_ref"], second["subject"]["plan_candidate_ref"]
        )
        self.assertEqual(state["approved_plan"], second_ref)

    def test_retry_uses_detached_payload_when_caller_mutates_candidate_reference(
        self,
    ) -> None:
        from contextlib import contextmanager
        from unittest.mock import patch

        import kapisch_core._locking as locking
        from kapisch_core.advisory import (
            prepare_plan_approval,
            promote_plan,
            publish_plan_approval,
        )
        from kapisch_core.protocol import load_state
        from kapisch_core.storage import load_authority_records

        first = self._prepare_plan_approval()
        first_reference = first["subject"]["plan_candidate_ref"]
        first_evidence = self._external_input(self._artifact(self._target(first)))
        publish_plan_approval(self.repo, first, first_evidence)

        second = prepare_plan_approval(
            self.repo, "run-1", "plan-gate", "plan-1", b"replacement plan bytes"
        )
        second_reference = copy.deepcopy(second["subject"]["plan_candidate_ref"])
        second_plan_ref = publish_plan_approval(
            self.repo,
            second,
            self._external_input(self._artifact(self._target(second))),
        )
        approvals_before = load_authority_records(self.repo, "gate-approvals")
        original_locked = locking._locked
        mutated = False

        @contextmanager
        def mutate_before_lock(repo: Path, run_id: str | None = None):
            nonlocal mutated
            if run_id == "run-1" and not mutated:
                mutated = True
                first_reference.clear()
                first_reference.update(second_reference)
            with original_locked(repo, run_id):
                yield

        with patch("kapisch_core._locking._locked", side_effect=mutate_before_lock):
            with self.assertRaisesRegex(ValueError, "candidate is not current run anchor"):
                publish_plan_approval(self.repo, first, first_evidence)

        self.assertTrue(mutated)
        state = load_state(self.repo, "run-1")
        self.assertEqual(state["plan_candidate_ref"], second_reference)
        self.assertEqual(state["approved_plan"], second_plan_ref)
        self.assertEqual(
            load_authority_records(self.repo, "gate-approvals"), approvals_before
        )
        self.assertEqual(promote_plan(self.repo, "run-1", "plan-1"), second_plan_ref)

    def test_candidate_replacement_before_backlink_repair_preserves_new_plan_ref(
        self,
    ) -> None:
        from unittest.mock import patch

        from kapisch_core._gate_approval import _approval_id, load_gate_approval
        from kapisch_core.advisory import (
            prepare_plan_approval,
            publish_plan_approval,
        )
        from kapisch_core.protocol import load_state

        first = self._prepare_plan_approval()
        first_evidence = self._external_input(self._artifact(self._target(first)))
        first_id = _approval_id(
            first, hashlib.sha256(self.canonical_json(first)).hexdigest()
        )
        original_load = load_gate_approval
        replacement_ref = None
        replaced = False

        def load_and_replace(repo: Path, reference: dict[str, str]):
            nonlocal replacement_ref, replaced
            record = original_load(repo, reference)
            if reference["approval_id"] == first_id and not replaced:
                replaced = True
                replacement = prepare_plan_approval(
                    repo,
                    "run-1",
                    "plan-gate",
                    "plan-1",
                    b"interleaved replacement plan bytes",
                )
                replacement_evidence = self._external_input(
                    self._artifact(self._target(replacement))
                )
                replacement_ref = publish_plan_approval(
                    repo, replacement, replacement_evidence
                )
            return record

        with patch(
            "kapisch_core._gate_approval.load_gate_approval",
            side_effect=load_and_replace,
        ):
            with self.assertRaisesRegex(
                ValueError, "candidate is not current run anchor"
            ):
                publish_plan_approval(self.repo, first, first_evidence)

        self.assertTrue(replaced)
        state = load_state(self.repo, "run-1")
        self.assertEqual(state["approved_plan"], replacement_ref)
        self.assertNotEqual(
            state["plan_candidate_ref"], first["subject"]["plan_candidate_ref"]
        )

    def test_plan_recovery_never_selects_same_run_and_plan_with_other_candidate(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval
        from kapisch_core.advisory import prepare_plan_approval, recover_plan_approval
        from kapisch_core.protocol import load_state
        from kapisch_core.storage import load_authority_record

        first = self._prepare_plan_approval()
        first_ref = first["subject"]["plan_candidate_ref"]
        publish_gate_approval(
            self.repo, first, self._external_input(self._artifact(self._target(first)))
        )
        second = prepare_plan_approval(
            self.repo, "run-1", "plan-gate", "plan-1", b"replacement plan bytes"
        )
        second_ref = second["subject"]["plan_candidate_ref"]
        self.assertNotEqual(first_ref, second_ref)
        self.assertEqual(load_state(self.repo, "run-1")["plan_candidate_ref"], second_ref)
        with self.assertRaisesRegex(ValueError, "no GateApproval exists for exact plan candidate"):
            recover_plan_approval(self.repo, "run-1", "plan-1")
        first_record_bytes = load_authority_record(
            self.repo,
            "gate-approvals",
            __import__("kapisch_core._gate_approval", fromlist=["_approval_id"])._approval_id(
                first, hashlib.sha256(self.canonical_json(first)).hexdigest()
            ),
        )
        self.assertTrue(first_record_bytes)

    def test_historical_candidate_load_ignores_unrelated_later_acceptance(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core._plan_candidate import (
            load_plan_approval_candidate,
            validate_plan_approval_candidate,
        )
        from kapisch_core.advisory import (
            accept_repository_decision,
            promote_plan,
            publish_plan_approval,
        )

        plan_payload = self._prepare_plan_approval()
        plan_reference = publish_plan_approval(
            self.repo,
            plan_payload,
            self._external_input(self._artifact(self._target(plan_payload))),
        )["gate_approval_ref"]
        plan_record = load_gate_approval(self.repo, plan_reference)
        candidate_ref = plan_record["payload"]["subject"]["plan_candidate_ref"]
        candidate, _ = load_plan_approval_candidate(self.repo, candidate_ref)
        self.assertEqual(candidate["authority_basis"], [])

        decision_payload = self._repository_payload()
        decision_ref = publish_gate_approval(
            self.repo,
            decision_payload,
            self._external_input(self._artifact(self._target(decision_payload))),
        )
        accept_repository_decision(self.repo, decision_ref)
        decision_record = load_gate_approval(self.repo, decision_ref)
        (self.repo / decision_record["human_authority"]["path"]).unlink()

        reloaded, _ = validate_plan_approval_candidate(self.repo, candidate_ref)
        self.assertEqual(reloaded, candidate)
        with self.assertRaisesRegex(
            ValueError, "referenced external human approval artifact is missing"
        ):
            promote_plan(self.repo, "run-1", "plan-1")

    def test_historical_candidate_load_requires_referenced_acceptance(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core._plan_candidate import validate_plan_approval_candidate
        from kapisch_core.advisory import (
            accept_repository_decision,
            prepare_plan_approval,
        )

        decision_payload = self._repository_payload()
        decision_ref = publish_gate_approval(
            self.repo,
            decision_payload,
            self._external_input(self._artifact(self._target(decision_payload))),
        )
        accept_repository_decision(self.repo, decision_ref)
        approval = load_gate_approval(self.repo, decision_ref)
        artifact_path = self.repo / approval["human_authority"]["path"]

        candidate_payload = prepare_plan_approval(
            self.repo,
            "run-1",
            "plan-gate",
            "plan-1",
            b"plan bound to historical authority",
        )
        candidate_ref = candidate_payload["subject"]["plan_candidate_ref"]
        candidate, _ = validate_plan_approval_candidate(self.repo, candidate_ref)
        self.assertEqual(len(candidate["authority_basis"]), 1)

        artifact_path.unlink()
        with self.assertRaisesRegex(ValueError, "human approval artifact is missing"):
            validate_plan_approval_candidate(self.repo, candidate_ref)

    def test_historical_candidate_load_requires_transitive_acceptance_history(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core._plan_candidate import validate_plan_approval_candidate
        from kapisch_core.advisory import (
            accept_repository_decision,
            prepare_plan_approval,
        )

        first_payload = self._repository_payload()
        first_gate_ref = publish_gate_approval(
            self.repo,
            first_payload,
            self._external_input(self._artifact(self._target(first_payload))),
        )
        first_acceptance_ref = accept_repository_decision(self.repo, first_gate_ref)
        first_approval = load_gate_approval(self.repo, first_gate_ref)
        first_subject = first_payload["subject"]
        first_binding = {
            "origin_run_id": first_acceptance_ref["origin_run_id"],
            "snapshot_id": first_acceptance_ref["snapshot_id"],
            "decision_id": first_subject["decision_id"],
            "acceptance_record_sha256": first_acceptance_ref["sha256"],
            "scope_ref": first_subject["scope_ref"],
            "applicability": first_subject["applicability"],
            "source_dependencies": first_subject["source_dependencies"],
        }

        second_payload = self._repository_payload()
        second_payload["gate_id"] = "decision-gate-2"
        second_payload["identity"]["id"] = "decision-2"
        second_subject = second_payload["subject"]
        second_subject.update(
            {
                "snapshot_id": "snapshot-2",
                "decision_id": "decision-2",
                "authority_basis": [first_binding],
                "supersedes": [
                    {
                        "origin_run_id": first_acceptance_ref["origin_run_id"],
                        "snapshot_id": first_acceptance_ref["snapshot_id"],
                        "decision_id": first_subject["decision_id"],
                        "sha256": first_acceptance_ref["sha256"],
                    }
                ],
            }
        )
        second_gate_ref = publish_gate_approval(
            self.repo,
            second_payload,
            self._external_input(self._artifact(self._target(second_payload))),
        )
        accept_repository_decision(self.repo, second_gate_ref)

        candidate_payload = prepare_plan_approval(
            self.repo,
            "run-1",
            "plan-gate",
            "plan-1",
            b"plan bound to transitive authority history",
        )
        candidate_ref = candidate_payload["subject"]["plan_candidate_ref"]
        candidate, _ = validate_plan_approval_candidate(self.repo, candidate_ref)
        self.assertEqual(
            [binding["snapshot_id"] for binding in candidate["authority_basis"]],
            ["snapshot-2"],
        )

        artifact_path = self.repo / first_approval["human_authority"]["path"]
        artifact_path.unlink()
        with self.assertRaisesRegex(ValueError, "human approval artifact is missing"):
            validate_plan_approval_candidate(self.repo, candidate_ref)

    def test_historical_plan_approval_ignores_mutated_current_scope(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import (
            promote_plan,
            propose_scope,
            publish_plan_approval,
        )
        from kapisch_core.protocol import load_state, publish_state

        payload = self._prepare_plan_approval()
        plan_ref = publish_plan_approval(
            self.repo, payload, self._external_input(self._artifact(self._target(payload)))
        )
        approval_ref = plan_ref["gate_approval_ref"]
        proposed = propose_scope(
            self.repo, "run-1", "scope-2", "changed current scope", {"mode": "all"}
        )
        state = load_state(self.repo, "run-1")
        changed = dict(state)
        changed["revision"] += 1
        changed["scope_ref"] = {
            "origin_run_id": proposed.origin_run_id,
            "scope_id": proposed.scope_id,
            "sha256": proposed.sha256,
        }
        publish_state(self.repo, "run-1", changed, expected_revision=state["revision"])

        self.assertEqual(load_gate_approval(self.repo, approval_ref)["approval_id"], approval_ref["approval_id"])
        with self.assertRaisesRegex(ValueError, "scope differs from current run scope"):
            promote_plan(self.repo, "run-1", "plan-1")

    def test_milestone_candidate_retains_graph_scopes_and_dependency_binding(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core._plan_candidate import (
            load_plan_approval_artifact,
            load_plan_approval_candidate,
        )
        from kapisch_core.advisory import (
            prepare_plan_approval,
            promote_plan,
            propose_scope,
            publish_plan_approval,
        )
        from kapisch_core.protocol import publish_state

        run_id = "run-milestone"
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        (run_root / "scopes").mkdir(parents=True)
        (run_root / "graphs").mkdir()
        scope_ref = propose_scope(
            self.repo, run_id, "scope-1", "milestone scope", {"mode": "all"}
        )
        nodes = []
        scope_bytes_by_node = {}
        for index in (1, 2):
            node_id = f"n-{index:032x}"
            scope = {
                "protocol_version": 3,
                "run_id": run_id,
                "node_id": node_id,
                "requirements": f"Requirement {index}.",
            }
            scope_bytes = self.canonical_json(scope)
            path = f"scopes/{node_id}.json"
            (run_root / path).write_bytes(scope_bytes)
            scope_ref_for_node = {
                "path": path,
                "sha256": hashlib.sha256(scope_bytes).hexdigest(),
            }
            nodes.append({
                "node_id": node_id,
                "scope": scope_ref_for_node,
                "depends_on": [] if index == 1 else ["n-" + f"{1:032x}"],
            })
            scope_bytes_by_node[node_id] = scope_bytes
        graph = {"protocol_version": 3, "run_id": run_id, "plan_id": "plan-1", "nodes": nodes}
        graph_bytes = self.canonical_json(graph)
        graph_ref = {
            "path": "graphs/plan-1.json",
            "sha256": hashlib.sha256(graph_bytes).hexdigest(),
        }
        (run_root / graph_ref["path"]).write_bytes(graph_bytes)
        state = {
            "protocol_version": 3,
            "run_id": run_id,
            "bundle_digest": self.bundle_digest,
            "workflow": "milestone",
            "revision": 0,
            "history": [],
            "identity_contract": "stage-attempt/1",
            "scope_ref": {
                "origin_run_id": scope_ref.origin_run_id,
                "scope_id": scope_ref.scope_id,
                "sha256": scope_ref.sha256,
            },
            "graph": graph_ref,
        }
        publish_state(self.repo, run_id, state, expected_revision=-1)
        plan_bytes = self.canonical_json({"plan_id": "plan-1", "graph": graph_ref})
        payload = prepare_plan_approval(
            self.repo, run_id, "plan-gate", "plan-1", plan_bytes
        )
        candidate_ref = payload["subject"]["plan_candidate_ref"]
        candidate, _ = load_plan_approval_candidate(self.repo, candidate_ref)
        execution = candidate["execution_binding"]
        self.assertEqual(execution["mode"], "milestone")
        self.assertEqual(execution["graph_ref"], graph_ref)
        self.assertEqual(
            load_plan_approval_artifact(self.repo, execution["retained_graph_ref"]),
            graph_bytes,
        )
        self.assertEqual(len(execution["node_scope_refs"]), 2)
        self.assertNotIn("dependencies", execution)
        for item in execution["node_scope_refs"]:
            self.assertEqual(item["scope_ref"], next(
                node["scope"] for node in nodes if node["node_id"] == item["node_id"]
            ))
            self.assertEqual(
                load_plan_approval_artifact(self.repo, item["retained_ref"]),
                scope_bytes_by_node[item["node_id"]],
            )

        plan_ref = publish_plan_approval(
            self.repo, payload, self._external_input(self._artifact(self._target(payload)))
        )
        approval_ref = plan_ref["gate_approval_ref"]
        changed_graph = {**graph, "nodes": [{**nodes[0]}, {**nodes[1], "depends_on": []}]}
        (run_root / graph_ref["path"]).write_bytes(self.canonical_json(changed_graph))
        with self.assertRaises(ValueError):
            promote_plan(self.repo, run_id, "plan-1")
        self.assertEqual(
            load_gate_approval(self.repo, approval_ref)["approval_id"],
            approval_ref["approval_id"],
        )
        shutil.rmtree(run_root)
        self.assertEqual(
            load_gate_approval(self.repo, approval_ref)["approval_id"],
            approval_ref["approval_id"],
        )

    def test_plan_approval_loader_recovers_exact_retained_plan_bytes(self) -> None:
        import kapisch_core.advisory as advisory

        self.assertTrue(hasattr(advisory, "prepare_plan_approval"))
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import publish_plan_approval
        from kapisch_core.storage import load_authority_record

        payload = self._prepare_plan_approval()
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),
        )["gate_approval_ref"]
        record = load_gate_approval(self.repo, reference)
        candidate_ref = record["payload"]["subject"]["plan_candidate_ref"]
        from kapisch_core._plan_candidate import load_plan_approval_candidate

        candidate, _ = load_plan_approval_candidate(self.repo, candidate_ref)
        plan_bytes = load_authority_record(
            self.repo, "plans", candidate["plan_sha256"]
        )
        self.assertEqual(plan_bytes, b"exact retained plan bytes")
        self.assertEqual(candidate["plan_ref"]["plan_id"], "plan-1")
        self.assertEqual(record["payload"]["gate_kind"], "plan-approval")

    def test_cold_recovery_needs_retained_bundle_not_producer_run(self) -> None:
        import kapisch_core.advisory as advisory

        self.assertTrue(hasattr(advisory, "prepare_plan_approval"))
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import publish_plan_approval

        payload = self._prepare_plan_approval()
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),
        )["gate_approval_ref"]
        shutil.rmtree(self.repo / ".kapisch/v3/runs/run-1")
        self.assertEqual(
            load_gate_approval(self.repo, reference)["approval_id"],
            reference["approval_id"],
        )
        (self.repo / ".kapisch/v3/bundles" / f"{self.bundle_digest}.json").unlink()
        with self.assertRaisesRegex(ValueError, "retained bundle"):
            load_gate_approval(self.repo, reference)

    def test_plan_approval_record_precedes_plan_ref_and_recovers_without_gate(
        self,
    ) -> None:
        import kapisch_core.advisory as advisory

        self.assertTrue(hasattr(advisory, "prepare_plan_approval"))
        from unittest.mock import patch

        from kapisch_core._gate_approval import _approval_id, load_gate_approval
        from kapisch_core.advisory import publish_plan_approval, recover_plan_approval
        from kapisch_core.bundle import canonical_json
        from kapisch_core.storage import load_authority_record

        payload = self._prepare_plan_approval()
        evidence = self._external_input(self._artifact(self._target(payload)))
        state_path = self.repo / ".kapisch/v3/runs/run-1/state.json"
        state_before = state_path.read_bytes()
        approval_id = _approval_id(
            payload, hashlib.sha256(canonical_json(payload)).hexdigest()
        )
        with patch(
            "kapisch_core._promotion._publish_state_locked",
            side_effect=OSError("injected PlanRef publication failure"),
        ):
            with self.assertRaisesRegex(OSError, "PlanRef publication failure"):
                publish_plan_approval(self.repo, payload, evidence)

        self.assertEqual(state_path.read_bytes(), state_before)
        record_bytes = load_authority_record(self.repo, "gate-approvals", approval_id)
        reference = {
            "approval_id": approval_id,
            "sha256": hashlib.sha256(record_bytes).hexdigest(),
        }
        self.assertEqual(
            load_gate_approval(self.repo, reference)["approval_id"], approval_id
        )
        with patch("kapisch_core._gate_approval.publish_gate_approval") as gate:
            repaired = recover_plan_approval(self.repo, "run-1", "plan-1")
        gate.assert_not_called()
        from kapisch_core.protocol import load_state

        state = load_state(self.repo, "run-1")
        self.assertEqual(state["approved_plan"], repaired)
        self.assertEqual(repaired["gate_approval_ref"], reference)

    def test_plan_approval_claim_is_durable_before_plan_ref(self) -> None:
        from unittest.mock import patch

        from kapisch_core.advisory import publish_plan_approval
        from kapisch_core.storage import load_authority_records

        payload = self._prepare_plan_approval()
        evidence = self._receipt(self._target(payload))
        state_path = self.repo / ".kapisch/v3/runs/run-1/state.json"
        state_before = state_path.read_bytes()
        with patch(
            "kapisch_core._promotion._publish_state_locked",
            side_effect=OSError("injected PlanRef publication failure"),
        ):
            with self.assertRaisesRegex(OSError, "PlanRef publication failure"):
                publish_plan_approval(self.repo, payload, evidence)
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(len(load_authority_records(self.repo, "human-actions")), 1)
        self.assertEqual(len(load_authority_records(self.repo, "gate-approvals")), 1)

    def test_plan_approval_loader_rejects_changed_retained_plan_bytes(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import publish_plan_approval

        payload = self._prepare_plan_approval()
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),
        )["gate_approval_ref"]
        from kapisch_core._plan_candidate import load_plan_approval_candidate

        candidate, _ = load_plan_approval_candidate(
            self.repo, payload["subject"]["plan_candidate_ref"]
        )
        digest = candidate["plan_sha256"]
        plan_path = self.repo / ".kapisch/v3/authority/plans" / f"{digest}.json"
        plan_path.write_bytes(b"different plan bytes")
        with self.assertRaisesRegex(ValueError, "retained plan digest mismatch"):
            load_gate_approval(self.repo, reference)

    def test_plan_approval_loader_fails_closed_on_missing_or_changed_evidence(
        self,
    ) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import publish_plan_approval

        payload = self._prepare_plan_approval()
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),
        )["gate_approval_ref"]
        record = load_gate_approval(self.repo, reference)
        evidence = record["human_authority"]
        artifact = self.repo / evidence["path"]
        original = artifact.read_bytes()
        artifact.write_bytes(original + b"tampered")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            load_gate_approval(self.repo, reference)
        artifact.write_bytes(original)
        artifact.unlink()
        with self.assertRaisesRegex(ValueError, "artifact is missing"):
            load_gate_approval(self.repo, reference)

    def test_plan_approval_blocks_when_plan_bytes_are_missing(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        payload = self._prepare_plan_approval()
        from kapisch_core._plan_candidate import load_plan_approval_candidate

        candidate, _ = load_plan_approval_candidate(
            self.repo, payload["subject"]["plan_candidate_ref"]
        )
        digest = candidate["plan_sha256"]
        (self.repo / ".kapisch/v3/authority/plans" / f"{digest}.json").unlink()
        with self.assertRaisesRegex(ValueError, "exact plan bytes are not retained"):
            publish_gate_approval(
                self.repo,
                payload,
                self._external_input(self._artifact(self._target(payload))),
            )
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_plan_approval_blocks_when_scope_descriptor_is_missing(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        payload = self._prepare_plan_approval()
        next((self.repo / ".kapisch/v3/authority/scopes").glob("*.json")).unlink()
        with self.assertRaisesRegex(ValueError, "proposed scope record is missing"):
            publish_gate_approval(self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),)
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())

    def test_plan_approval_rejects_retargeted_evidence_and_record_digest(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import publish_plan_approval

        payload = self._prepare_plan_approval()
        target = self._target(payload)
        wrong_target = self._target({**payload, "gate_id": "other-gate"})
        with self.assertRaisesRegex(ValueError, "does not bind exact GateTarget"):
            publish_plan_approval(
                self.repo,
                payload,
                self._external_input(self._artifact(wrong_target)),
            )
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(target)),
        )["gate_approval_ref"]
        with self.assertRaisesRegex(ValueError, "reference digest mismatch"):
            load_gate_approval(self.repo, {**reference, "sha256": "0" * 64})

    def test_plan_approval_loader_fails_closed_when_plan_bytes_are_missing(
        self,
    ) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.advisory import publish_plan_approval

        payload = self._prepare_plan_approval()
        reference = publish_plan_approval(
            self.repo,
            payload,
            self._external_input(self._artifact(self._target(payload))),
        )["gate_approval_ref"]
        from kapisch_core._plan_candidate import load_plan_approval_candidate

        candidate, _ = load_plan_approval_candidate(
            self.repo, payload["subject"]["plan_candidate_ref"]
        )
        digest = candidate["plan_sha256"]
        (self.repo / ".kapisch/v3/authority/plans" / f"{digest}.json").unlink()
        with self.assertRaisesRegex(ValueError, "exact plan bytes are not retained"):
            load_gate_approval(self.repo, reference)

    def test_external_approval_retains_exact_artifact_bytes_and_recovers_cold(
        self,
    ) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core.storage import (
            load_authority_record,
            load_human_approval_artifact,
        )

        state_path = self.repo / ".kapisch/v3/runs/run-1/state.json"
        state_before = state_path.read_bytes()
        ref = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(
            self.target.target,
            "66a924de383a9e934cc67e5a09c0189c9b57af0945f988c13482b72b9c65e7fa",
        )
        self.assertEqual(
            ref["approval_id"],
            "ga-7e82bd6c4550bed939e38bda40a76f9f795d0a6831a892c331084e1a64965352",
        )
        self.assertEqual(
            ref["sha256"],
            "09d2b1d2d858eae712fb0d48cec4b65f02ff63bd1947967f5eade3e5008373f0",
        )
        record = load_gate_approval(self.repo, ref)
        artifact_ref = record["human_authority"]
        self.assertEqual(artifact_ref["kind"], "external-artifact")
        self.assertEqual(
            artifact_ref["path"],
            f".kapisch/v3/authority/human-artifacts/{artifact_ref['sha256']}.json",
        )
        self.assertEqual(
            load_human_approval_artifact(
                self.repo, artifact_ref["path"], artifact_ref["sha256"]
            ),
            self.artifact_bytes,
        )
        record_bytes = load_authority_record(
            self.repo, "gate-approvals", ref["approval_id"]
        )
        self.assertEqual(hashlib.sha256(record_bytes).hexdigest(), ref["sha256"])
        self.assertEqual(record["approved_target_sha256"], self.target.target)
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-actions").exists())
        self.assertEqual(
            publish_gate_approval(
                self.repo, self.payload, self._external_input(self.artifact_bytes)
            ),
            ref,
        )

        shutil.rmtree(self.repo / ".kapisch/v3/runs/run-1")
        self.assertTrue(
            (self.repo / ".kapisch/v3/bundles" / f"{self.bundle_digest}.json").is_file()
        )
        script = (
            "import json,sys; from pathlib import Path; "
            "from kapisch_core._gate_approval import load_gate_approval; "
            "r=load_gate_approval(Path(sys.argv[1]),json.loads(sys.argv[2])); "
            "assert r['human_authority']['kind']=='external-artifact'; "
            "assert r['payload']['gate_contract']=='human-gate/1'"
        )
        run = subprocess.run(
            [sys.executable, "-c", script, str(self.repo), json.dumps(ref)],
            cwd=Path(__file__).resolve().parents[2],
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "core"),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_recovery_finds_scope_by_digest_without_mutable_run_backlink(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )

        ref = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        state_path = self.repo / ".kapisch/v3/runs/run-1/state.json"
        state = json.loads(state_path.read_bytes())
        state.pop("scope_ref")
        state_path.write_bytes(self.canonical_json(state))
        record = load_gate_approval(self.repo, ref)
        self.assertEqual(record["payload"]["scope_digest"], self.scope_ref["sha256"])

    def test_repository_decision_scope_reference_identity_must_match_descriptor(
        self,
    ) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        cases = ("origin_run_id", "scope_id")
        for field in cases:
            with self.subTest(field=field):
                payload = copy.deepcopy(self.payload)
                payload["subject"]["scope_ref"][field] = f"missing-{field}"
                evidence = self._external_input(self._artifact(self._target(payload)))
                with self.assertRaisesRegex(ValueError, "scope"):
                    publish_gate_approval(self.repo, payload, evidence)
                authority_dir = self.repo / ".kapisch/v3/authority"
                self.assertFalse((authority_dir / "human-artifacts").exists())
                self.assertFalse((authority_dir / "gate-approvals").exists())

    def test_repository_decision_recovers_when_run_state_is_missing(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )

        reference = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        (self.repo / ".kapisch/v3/runs/run-1/state.json").unlink()
        record = load_gate_approval(self.repo, reference)
        self.assertEqual(record["approval_id"], reference["approval_id"])
        self.assertEqual(record["payload"]["gate_kind"], "repository-decision")

    def test_cold_recovery_rejects_missing_scope_descriptor_and_bundle(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )

        reference = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        shutil.rmtree(self.repo / ".kapisch/v3/runs/run-1")
        scope_identity = {
            "origin_run_id": self.scope_ref["origin_run_id"],
            "scope_id": self.scope_ref["scope_id"],
        }
        scope_id = hashlib.sha256(self.canonical_json(scope_identity)).hexdigest()
        scope_path = self.repo / ".kapisch/v3/authority/scopes" / f"{scope_id}.json"
        scope_bytes = scope_path.read_bytes()
        bundle_path = self.repo / ".kapisch/v3/bundles" / f"{self.bundle_digest}.json"

        scope_path.unlink()
        with self.assertRaisesRegex(ValueError, "scope"):
            load_gate_approval(self.repo, reference)
        scope_path.write_bytes(scope_bytes)

        bundle_path.unlink()
        with self.assertRaises(FileNotFoundError):
            load_gate_approval(self.repo, reference)

    def test_raw_bytes_without_external_source_marker_are_rejected(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        with self.assertRaises(TypeError):
            publish_gate_approval(self.repo, self.payload, self.artifact_bytes)
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())

    def test_plan_approval_facade_rejects_malformed_payload_shape(self) -> None:
        from kapisch_core.advisory import publish_plan_approval
        from kapisch_core.protocol import load_state
        from kapisch_core.storage import load_authority_records

        evidence = self._external_input(b"invalid")
        cases = (
            (None, TypeError, "payload must be an object"),
            ({}, ValueError, "subject must be an object"),
            ({"subject": None}, ValueError, "subject must be an object"),
            ({"subject": {}}, ValueError, "subject must contain candidate reference"),
            (
                {"subject": {"plan_candidate_ref": None}},
                ValueError,
                "candidate reference must be an object",
            ),
            (
                {"subject": {"plan_candidate_ref": {"path": "invalid"}}},
                ValueError,
                "candidate reference",
            ),
        )
        for payload, error_type, message in cases:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(error_type, message):
                    publish_plan_approval(self.repo, payload, evidence)

        state = load_state(self.repo, "run-1")
        self.assertNotIn("plan_candidate_ref", state)
        self.assertNotIn("approved_plan", state)
        self.assertEqual(load_authority_records(self.repo, "human-artifacts"), [])
        self.assertEqual(load_authority_records(self.repo, "gate-approvals"), [])

    def _run_state_directory_sync_fault(self, failures: int | None):
        from unittest.mock import patch

        run_directory = self.repo / ".kapisch/v3/runs/run-1"
        expected = run_directory.stat()
        original_fsync = os.fsync
        calls = 0

        def fsync(descriptor: int) -> None:
            nonlocal calls
            actual = os.fstat(descriptor)
            if (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino):
                calls += 1
                if failures is None or calls <= failures:
                    raise OSError("run state directory sync failed")
            original_fsync(descriptor)

        return patch("kapisch_core.storage.os.fsync", side_effect=fsync), lambda: calls

    def test_plan_candidate_retry_retries_visible_anchor_directory_sync(self) -> None:
        from kapisch_core.advisory import prepare_plan_approval
        from kapisch_core.protocol import load_state
        from kapisch_core.storage import load_authority_records

        fault, syncs = self._run_state_directory_sync_fault(failures=None)
        with fault:
            with self.assertRaisesRegex(OSError, "run state directory sync failed"):
                prepare_plan_approval(
                    self.repo, "run-1", "plan-gate", "plan-1", b"exact retained plan bytes"
                )
            reference = load_state(self.repo, "run-1")["plan_candidate_ref"]
            first_syncs = syncs()
            with self.assertRaisesRegex(OSError, "run state directory sync failed"):
                prepare_plan_approval(
                    self.repo, "run-1", "plan-gate", "plan-1", b"exact retained plan bytes"
                )
            self.assertGreater(syncs(), first_syncs)

        self.assertEqual(load_state(self.repo, "run-1")["plan_candidate_ref"], reference)
        self.assertEqual(load_authority_records(self.repo, "gate-approvals"), [])

    def test_plan_approval_syncs_anchor_before_retaining_gate_evidence(self) -> None:
        from kapisch_core.advisory import publish_plan_approval
        from kapisch_core.storage import load_authority_records

        payload = self._prepare_plan_approval()
        evidence = self._external_input(self._artifact(self._target(payload)))
        fault, syncs = self._run_state_directory_sync_fault(failures=1)
        with fault:
            with self.assertRaisesRegex(OSError, "run state directory sync failed"):
                publish_plan_approval(self.repo, payload, evidence)
            self.assertEqual(load_authority_records(self.repo, "gate-approvals"), [])
            self.assertEqual(load_authority_records(self.repo, "human-artifacts"), [])
            first_syncs = syncs()
            plan_ref = publish_plan_approval(self.repo, payload, evidence)

        self.assertGreater(syncs(), first_syncs)
        self.assertEqual(len(load_authority_records(self.repo, "gate-approvals")), 1)
        self.assertEqual(plan_ref["plan_id"], "plan-1")

    def _gate_approval_sync_fault(self, failures: int | None):
        from unittest.mock import patch

        import kapisch_core.storage as storage

        original_sync = storage._sync_hierarchy
        approval_directory = self.repo / ".kapisch/v3/authority/gate-approvals"
        calls = 0

        def sync(descriptors: list[int]) -> None:
            nonlocal calls
            try:
                expected = approval_directory.stat()
            except FileNotFoundError:
                return original_sync(descriptors)
            actual = os.fstat(descriptors[-1])
            if (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino):
                calls += 1
                if failures is None or calls <= failures:
                    raise OSError("gate approval directory sync failed")
            original_sync(descriptors)

        return patch("kapisch_core.storage._sync_hierarchy", side_effect=sync), lambda: calls

    def test_plan_approval_retry_resyncs_visible_gate_approval(self) -> None:
        from kapisch_core.advisory import publish_plan_approval
        from kapisch_core.protocol import load_state

        payload = self._prepare_plan_approval()
        evidence = self._external_input(self._artifact(self._target(payload)))
        fault, syncs = self._gate_approval_sync_fault(failures=None)
        with fault:
            with self.assertRaisesRegex(OSError, "gate approval directory sync failed"):
                publish_plan_approval(self.repo, payload, evidence)
            with self.assertRaisesRegex(OSError, "gate approval directory sync failed"):
                publish_plan_approval(self.repo, payload, evidence)
        self.assertEqual(syncs(), 2)
        self.assertNotIn("approved_plan", load_state(self.repo, "run-1"))

    def test_plan_approval_successful_retry_syncs_before_plan_ref(self) -> None:
        from kapisch_core.advisory import publish_plan_approval
        from kapisch_core.protocol import load_state

        payload = self._prepare_plan_approval()
        evidence = self._external_input(self._artifact(self._target(payload)))
        fault, syncs = self._gate_approval_sync_fault(failures=1)
        with fault:
            with self.assertRaisesRegex(OSError, "gate approval directory sync failed"):
                publish_plan_approval(self.repo, payload, evidence)
            plan_ref = publish_plan_approval(self.repo, payload, evidence)
        self.assertEqual(syncs(), 2)
        self.assertEqual(load_state(self.repo, "run-1")["approved_plan"], plan_ref)

    def test_plan_approval_recovery_resyncs_visible_gate_approval(self) -> None:
        from kapisch_core.advisory import publish_plan_approval, recover_plan_approval
        from kapisch_core.protocol import load_state

        payload = self._prepare_plan_approval()
        evidence = self._external_input(self._artifact(self._target(payload)))
        fault, syncs = self._gate_approval_sync_fault(failures=1)
        with fault:
            with self.assertRaisesRegex(OSError, "gate approval directory sync failed"):
                publish_plan_approval(self.repo, payload, evidence)
            plan_ref = recover_plan_approval(self.repo, "run-1", "plan-1")
        self.assertEqual(syncs(), 2)
        self.assertEqual(load_state(self.repo, "run-1")["approved_plan"], plan_ref)

    def test_gate_approval_sync_failure_is_not_reported_as_success(self) -> None:
        from unittest.mock import patch

        from kapisch_core._gate_approval import _commit_record
        from kapisch_core.storage import load_authority_record

        approval_id = "ga-" + "d" * 64
        data = b"exact approval record bytes"
        with patch(
            "kapisch_core.storage._sync_hierarchy", side_effect=OSError("sync failed")
        ):
            with self.assertRaisesRegex(OSError, "sync failed"):
                _commit_record(self.repo, approval_id, data)
        reference = _commit_record(self.repo, approval_id, data)
        self.assertEqual(reference["approval_id"], approval_id)
        self.assertEqual(reference["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(
            load_authority_record(self.repo, "gate-approvals", approval_id), data
        )

    def test_publisher_rejects_missing_run_id_with_validation_error(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        with self.assertRaisesRegex(ValueError, "run_id"):
            publish_gate_approval(self.repo, {}, self._external_input(b"invalid"))
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_malformed_plan_candidate_reference_returns_validation_error(self) -> None:
        from kapisch_core._gate_approval import _record_bundle

        with self.assertRaisesRegex(ValueError, "candidate reference"):
            _record_bundle(
                self.repo,
                {
                    "gate_kind": "plan-approval",
                    "run_id": "run-1",
                    "subject": {"plan_candidate_ref": None},
                },
            )

    def test_loader_rejects_malformed_payload_routing_with_validation_error(
        self,
    ) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.storage import store_authority_record

        approval_id = "ga-" + "a" * 64
        data = self.canonical_json(
            {
                "protocol_version": 3,
                "approval_contract": "human-gate-approval/1",
                "approval_id": approval_id,
                "payload": {},
                "approved_target_sha256": "b" * 64,
                "human_authority": {
                    "kind": "external-artifact",
                    "path": "x",
                    "sha256": "c" * 64,
                },
            }
        )
        store_authority_record(self.repo, "gate-approvals", approval_id, data)
        reference = {
            "approval_id": approval_id,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "payload"):
            load_gate_approval(self.repo, reference)

    def test_payload_schema_is_enforced_before_evidence_retention(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        invalid_payload = {**self.payload, "unexpected": "field"}
        with self.assertRaises(ValueError):
            publish_gate_approval(self.repo, invalid_payload, b"not-json")
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_invalid_external_artifact_is_rejected_before_retention(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        invalid = self._artifact(self.target).replace(
            b'"decision":"approve"', b'"decision":"reject"'
        )
        with self.assertRaises(ValueError):
            publish_gate_approval(
                self.repo, self.payload, self._external_input(invalid)
            )
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_loader_rejects_embedded_approval_id_mismatch(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core.storage import load_authority_record

        ref = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        data = load_authority_record(self.repo, "gate-approvals", ref["approval_id"])
        record = json.loads(data)
        record["approval_id"] = "ga-" + "f" * 64
        mismatched = self.canonical_json(record)
        record_path = (
            self.repo
            / ".kapisch/v3/authority/gate-approvals"
            / f"{ref['approval_id']}.json"
        )
        record_path.write_bytes(mismatched)
        wrong_digest_ref = {
            "approval_id": ref["approval_id"],
            "sha256": hashlib.sha256(mismatched).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "approval ID"):
            load_gate_approval(self.repo, wrong_digest_ref)

    def test_orphan_artifact_does_not_load_as_gate_approval(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.storage import retain_human_approval_artifact

        retain_human_approval_artifact(self.repo, self.artifact_bytes)
        approval_id = "ga-" + self.target.target
        with self.assertRaises(ValueError):
            load_gate_approval(
                self.repo, {"approval_id": approval_id, "sha256": "0" * 64}
            )
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_orphan_human_action_claim_does_not_load_as_gate_approval(self) -> None:
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core._human_action_ownership import (
            load_human_action_claim,
            publish_human_action_claim,
        )

        claim_ref = publish_human_action_claim(self.repo, self._receipt(), self.target)
        load_human_action_claim(self.repo, claim_ref, self.target)
        approval_id = "ga-" + self.target.target
        with self.assertRaises(ValueError):
            load_gate_approval(
                self.repo, {"approval_id": approval_id, "sha256": "0" * 64}
            )
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_referenced_artifact_tamper_and_deletion_fail_recovery_closed(self) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )

        ref = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        record = load_gate_approval(self.repo, ref)
        artifact_path = self.repo / record["human_authority"]["path"]
        artifact_path.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            load_gate_approval(self.repo, ref)

        second = Path(self.temp.name) / "second"
        second.mkdir()
        from kapisch_core.advisory import propose_scope
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle

        digest = store_bundle(
            second,
            (
                Path(__file__).resolve().parents[2] / "core/dist/core-bundle.json"
            ).read_bytes(),
        )
        scope_ref = propose_scope(
            second, "run-1", "scope-1", "requirements", {"mode": "all"}
        )
        state = {
            "protocol_version": 3,
            "run_id": "run-1",
            "bundle_digest": digest,
            "workflow": "task",
            "revision": 0,
            "history": [],
            "identity_contract": "stage-attempt/1",
            "scope_ref": {
                "origin_run_id": scope_ref.origin_run_id,
                "scope_id": scope_ref.scope_id,
                "sha256": scope_ref.sha256,
            },
        }
        publish_state(second, "run-1", state, expected_revision=-1)
        second_payload = {**self.payload, "scope_digest": scope_ref.sha256}
        second_target = self._target(second_payload)
        second_ref = publish_gate_approval(
            second, second_payload, self._external_input(self._artifact(second_target))
        )
        second_record = load_gate_approval(second, second_ref)
        (second / second_record["human_authority"]["path"]).unlink()
        with self.assertRaises(ValueError):
            load_gate_approval(second, second_ref)

    def test_host_action_approval_references_claim_and_never_retains_external_bytes(
        self,
    ) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )
        from kapisch_core._human_action_ownership import load_human_action_claim

        ref = publish_gate_approval(self.repo, self.payload, self._receipt())
        record = load_gate_approval(self.repo, ref)
        self.assertEqual(record["human_authority"]["kind"], "host-action")
        claim = load_human_action_claim(
            self.repo, record["human_authority"]["claim_ref"], self.target
        )
        self.assertEqual(claim["claim_contract"], "human-action-claim/1")
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())

    def test_changed_evidence_cannot_replace_approval_with_same_payload_identity(
        self,
    ) -> None:
        from kapisch_core._gate_approval import (
            load_gate_approval,
            publish_gate_approval,
        )

        external_ref = publish_gate_approval(
            self.repo, self.payload, self._external_input(self.artifact_bytes)
        )
        original = load_gate_approval(self.repo, external_ref)
        with self.assertRaises(ValueError):
            publish_gate_approval(self.repo, self.payload, self._receipt())
        self.assertEqual(load_gate_approval(self.repo, external_ref), original)

    def _repository_payload(self) -> dict:
        return {
            "protocol_version": 3,
            "gate_contract": "human-gate/1",
            "run_id": "run-1",
            "gate_id": "decision-gate",
            "identity": {"kind": "decision", "id": "decision-1"},
            "scope_digest": self.scope_ref["sha256"],
            "gate_kind": "repository-decision",
            "subject": {
                "acceptance_contract": "global-authority/1",
                "origin_run_id": "run-1",
                "snapshot_id": "snapshot-1",
                "decision_id": "decision-1",
                "decision": "approve repository decision",
                "scope_ref": self.scope_ref,
                "applicability": {"mode": "all"},
                "bundle_digest": self.bundle_digest,
                "source_dependencies": [],
                "authority_basis": [],
                "amends": [],
                "supersedes": [],
            },
        }

    def test_payload_reference_arrays_must_be_sorted_and_unique(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        def binding(
            origin: str,
            *,
            dependencies: list | None = None,
            applicability: dict | None = None,
        ) -> dict:
            return {
                "origin_run_id": origin,
                "snapshot_id": f"snapshot-{origin}",
                "decision_id": f"decision-{origin}",
                "acceptance_record_sha256": origin * 64,
                "scope_ref": {
                    "origin_run_id": origin,
                    "scope_id": f"scope-{origin}",
                    "sha256": "c" * 64,
                },
                "applicability": applicability or {"mode": "all"},
                "source_dependencies": dependencies or [],
            }

        binding_a = binding("a")
        binding_b = binding("b")
        unsorted_dependencies = [
            {"path": "z.txt", "sha256": "d" * 64},
            {"path": "a.txt", "sha256": "e" * 64},
        ]
        cases = []
        unsorted_basis = copy.deepcopy(self.payload)
        unsorted_basis["subject"]["authority_basis"] = [binding_b, binding_a]
        cases.append(("authority basis order", unsorted_basis))
        duplicate_basis = copy.deepcopy(self.payload)
        duplicate_basis["subject"]["authority_basis"] = [binding_a, binding_a]
        cases.append(("authority basis duplicate", duplicate_basis))
        nested_dependencies = copy.deepcopy(self.payload)
        nested_dependencies["subject"]["authority_basis"] = [
            binding("a", dependencies=unsorted_dependencies)
        ]
        cases.append(("nested dependency order", nested_dependencies))
        nested_applicability = copy.deepcopy(self.payload)
        nested_applicability["subject"]["authority_basis"] = [
            binding("a", applicability={"mode": "keys", "keys": ["z", "a"]})
        ]
        cases.append(("nested applicability key order", nested_applicability))
        repository_dependencies = self._repository_payload()
        repository_dependencies["subject"]["source_dependencies"] = (
            unsorted_dependencies
        )
        cases.append(("repository dependency order", repository_dependencies))
        first = {
            "origin_run_id": "a",
            "snapshot_id": "s1",
            "decision_id": "d1",
            "sha256": "a" * 64,
        }
        second = {
            "origin_run_id": "b",
            "snapshot_id": "s2",
            "decision_id": "d2",
            "sha256": "b" * 64,
        }
        for field in ("amends", "supersedes"):
            repository_relationships = self._repository_payload()
            repository_relationships["subject"][field] = [second, first]
            cases.append((f"{field} order", repository_relationships))

        for name, payload in cases:
            with self.subTest(name=name):
                target = self._target(payload)
                with self.assertRaisesRegex(ValueError, "sorted|unique"):
                    publish_gate_approval(
                        self.repo,
                        payload,
                        self._external_input(self._artifact(target)),
                    )
                self.assertFalse(
                    (self.repo / ".kapisch/v3/authority/human-artifacts").exists()
                )
                self.assertFalse(
                    (self.repo / ".kapisch/v3/authority/gate-approvals").exists()
                )

    def test_loader_rejects_noncanonical_authority_basis(self) -> None:
        from kapisch_core._gate_approval import _approval_id, load_gate_approval
        from kapisch_core.storage import (
            retain_human_approval_artifact,
            store_authority_record,
        )

        def binding(origin: str) -> dict:
            return {
                "origin_run_id": origin,
                "snapshot_id": f"snapshot-{origin}",
                "decision_id": f"decision-{origin}",
                "acceptance_record_sha256": origin * 64,
                "scope_ref": {
                    "origin_run_id": origin,
                    "scope_id": f"scope-{origin}",
                    "sha256": "c" * 64,
                },
                "applicability": {"mode": "all"},
                "source_dependencies": [],
            }

        payload = copy.deepcopy(self.payload)
        payload["subject"]["authority_basis"] = [binding("b"), binding("a")]
        target = self._target(payload)
        payload_digest = hashlib.sha256(self.canonical_json(payload)).hexdigest()
        artifact_ref = retain_human_approval_artifact(self.repo, self._artifact(target))
        approval_id = _approval_id(payload, payload_digest)
        record = {
            "protocol_version": 3,
            "approval_contract": "human-gate-approval/1",
            "approval_id": approval_id,
            "payload": payload,
            "approved_target_sha256": payload_digest,
            "human_authority": {"kind": "external-artifact", **artifact_ref},
        }
        record_bytes = self.canonical_json(record)
        store_authority_record(self.repo, "gate-approvals", approval_id, record_bytes)
        reference = {
            "approval_id": approval_id,
            "sha256": hashlib.sha256(record_bytes).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "sorted and unique"):
            load_gate_approval(self.repo, reference)

    def test_repository_decision_requires_descriptor_applicability(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        payload = self._repository_payload()
        payload["subject"]["applicability"] = {"mode": "keys", "keys": ["scope-key"]}
        target = self._target(payload)
        with self.assertRaisesRegex(ValueError, "applicability"):
            publish_gate_approval(
                self.repo, payload, self._external_input(self._artifact(target))
            )
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_repository_decision_gate_approval_does_not_commit_acceptance(self) -> None:
        from kapisch_core.authority import load_gate_approval, publish_gate_approval

        payload = self._repository_payload()
        target = self._target(payload)
        state_path = self.repo / ".kapisch/v3/runs/run-1/state.json"
        state_before = state_path.read_bytes()
        ref = publish_gate_approval(
            self.repo, payload, self._external_input(self._artifact(target))
        )
        self.assertEqual(state_path.read_bytes(), state_before)
        shutil.rmtree(self.repo / ".kapisch/v3/runs/run-1")
        record = load_gate_approval(self.repo, ref)
        self.assertEqual(record["payload"], payload)
        self.assertEqual(record["approval_contract"], "human-gate-approval/1")
        self.assertFalse(state_path.exists())
        self.assertNotIn("acceptance_ref", json.loads(state_before))
        authority_entries = {
            path.name for path in (self.repo / ".kapisch/v3/authority").iterdir()
        }
        self.assertEqual(
            authority_entries, {"gate-approvals", "human-artifacts", "scopes"}
        )

    def test_gate_approval_publication_refuses_legacy_bundle(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle

        legacy = (
            Path(__file__).resolve().parents[1]
            / "conformance/fixtures/v3/legacy-bundle.json"
        ).read_bytes()
        bundle_digest = store_bundle(self.repo, legacy)
        state = {
            "protocol_version": 3,
            "run_id": "legacy-run",
            "bundle_digest": bundle_digest,
            "workflow": "task",
            "revision": 0,
            "history": [],
            "identity_contract": "stage-attempt/1",
        }
        publish_state(self.repo, "legacy-run", state, expected_revision=-1)
        with self.assertRaisesRegex(ValueError, "unsupported-gate"):
            publish_gate_approval(self.repo, {"run_id": "legacy-run"}, None)
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())

    def test_side_effect_permission_record_is_not_published_in_stage_53a(self) -> None:
        from kapisch_core._gate_approval import publish_gate_approval

        payload = {
            **self.payload,
            "identity": {"kind": "effect", "id": "effect-1"},
            "gate_kind": "side-effect-permission",
            "subject": {
                "effect_identity": "effect-1",
                "effect_classification": "external-write",
                "effect_request_sha256": "e" * 64,
            },
        }
        target = self._target(payload)
        with self.assertRaisesRegex(ValueError, "unsupported-gate"):
            publish_gate_approval(
                self.repo, payload, self._external_input(self._artifact(target))
            )
        self.assertFalse((self.repo / ".kapisch/v3/authority/human-artifacts").exists())
        self.assertFalse((self.repo / ".kapisch/v3/authority/gate-approvals").exists())


if __name__ == "__main__":
    unittest.main()
