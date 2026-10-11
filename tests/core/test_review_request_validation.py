from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

import hashlib  # noqa: E402

from kapisch_core import _invocation  # noqa: E402
from kapisch_core.protocol import persist_request, publish_state  # noqa: E402
from kapisch_core.review import (  # noqa: E402
    ImmutableArtifactLocator,
    ReviewScopeArtifact,
)
from kapisch_core.storage import store_bundle  # noqa: E402


class ReviewRequestValidationTests(unittest.TestCase):
    def _validator_fixture(self, repo: Path):
        bundle_bytes = (ROOT / "core/dist/core-bundle.json").read_bytes()
        bundle_digest = store_bundle(repo, bundle_bytes)
        run_id = "run-review-scope"
        stage_id = "s-" + "5" * 32
        operation_id = "op-" + "6" * 32
        state = {
            "protocol_version": 3, "run_id": run_id,
            "bundle_digest": bundle_digest, "workflow": "task",
            "revision": 0, "history": [{
                "stage_id": stage_id, "stage_kind": "implement", "sequence": 0,
                "role": "reviewer", "status": "planned", "producer": "controller",
                "evidence": [], "scope_digest": "a" * 64,
            }], "identity_contract": "stage-attempt/1",
        }
        publish_state(repo, run_id, state, expected_revision=-1)
        packet = {
            "run_id": run_id, "operation_id": operation_id, "stage_id": stage_id,
            "role": "reviewer", "purpose": "iteration", "bundle_digest": bundle_digest,
            "scope_digest": "a" * 64, "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
        }
        return run_id, stage_id, packet, bundle_bytes

    def test_scope_validator_rejects_missing_and_bad_digest_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_id, _, packet, bundle_bytes = self._validator_fixture(repo)
            from kapisch_core.bundle import verify_bundle
            bundle = verify_bundle(bundle_bytes, hashlib.sha256(bundle_bytes).hexdigest())
            digest = "d" * 64
            path = f".kapisch/v3/runs/{run_id}/review-inputs/scopes/{digest}.json"
            packet["review_scope"] = {"path": path, "sha256": digest}
            with self.assertRaises(FileNotFoundError):
                _invocation._validate_review_scope_request(repo, run_id, packet, bundle)
            target = repo / path
            target.parent.mkdir(parents=True)
            target.write_bytes(b"bad bytes")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                _invocation._validate_review_scope_request(repo, run_id, packet, bundle)

    def test_scope_validator_checks_packet_binding_before_bound_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_id, stage_id, packet, bundle_bytes = self._validator_fixture(repo)
            from kapisch_core.bundle import verify_bundle
            bundle = verify_bundle(bundle_bytes, hashlib.sha256(bundle_bytes).hexdigest())
            artifact = ReviewScopeArtifact(
                run_id, "s-" + "7" * 32, "final",
                ImmutableArtifactLocator(
                    ".kapisch/v3/authority/plan-approval-candidates/" + "8" * 64 + ".json", "8" * 64
                ), "sha1:" + "9" * 40,
            )
            data = artifact.canonical_bytes()
            digest = hashlib.sha256(data).hexdigest()
            path = f".kapisch/v3/runs/{run_id}/review-inputs/scopes/{digest}.json"
            target = repo / path
            target.parent.mkdir(parents=True)
            target.write_bytes(data)
            packet["review_scope"] = {"path": path, "sha256": digest}
            with patch.object(_invocation, "_load_run_context", return_value=({"plan_candidate_ref": None, "history": []}, bundle)), patch(
                "kapisch_core._review_scope._load_bound_base"
            ) as bound_base:
                with self.assertRaisesRegex(ValueError, "binding is invalid"):
                    _invocation._validate_review_scope_request(repo, run_id, packet, bundle)
                bound_base.assert_not_called()
    def test_packet_input_validation_preserves_scope_error_precedence(self) -> None:
        bundle = type("Bundle", (), {"payload": {}})()
        packet = {"inputs": [{"bad": True}], "review_scope": {}}
        with self.assertRaisesRegex(ValueError, "immutable published bytes"):
            _invocation._validate_packet_inputs(Path("."), "run", "op", packet, bundle)

        packet = {"inputs": [], "review_scope": {}}
        with patch.object(
            _invocation,
            "_validate_review_scope_request",
            side_effect=ValueError("scope failure"),
        ) as scope:
            with self.assertRaisesRegex(ValueError, "scope failure"):
                _invocation._validate_packet_inputs(
                    Path("."), "run", "op", packet, bundle
                )
            scope.assert_called_once()

    def test_packet_input_validation_orders_shape_scope_and_evidence(self) -> None:
        bundle = type("Bundle", (), {"payload": {}})()
        packet = {"inputs": [], "review_scope": {}}
        calls = []
        with (
            patch.object(
                _invocation, "_packet_input_refs", side_effect=lambda *args: calls.append("shape") or []
            ),
            patch.object(
                _invocation,
                "_validate_review_scope_request",
                side_effect=lambda *args: calls.append("scope"),
            ),
            patch.object(
                _invocation,
                "_validate_packet_input_evidence",
                side_effect=lambda *args: calls.append("evidence"),
            ),
        ):
            _invocation._validate_packet_inputs(Path("."), "run", "op", packet, bundle)
        self.assertEqual(calls, ["shape", "scope", "evidence"])

        calls.clear()
        packet = {"inputs": []}
        with (
            patch.object(
                _invocation, "_packet_input_refs", side_effect=lambda *args: calls.append("shape") or []
            ),
            patch.object(_invocation, "_validate_review_scope_request") as scope,
            patch.object(
                _invocation,
                "_validate_packet_input_evidence",
                side_effect=lambda *args: calls.append("evidence"),
            ),
        ):
            _invocation._validate_packet_inputs(Path("."), "run", "op", packet, bundle)
        self.assertEqual(calls, ["shape", "evidence"])
        scope.assert_not_called()

    def test_review_scope_request_rejects_malformed_locator_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            packet = {
                "role": "reviewer",
                "purpose": "iteration",
                "review_scope": {"path": "../scope.json", "sha256": "a" * 64},
            }
            bundle_bytes = (ROOT / "core/dist/core-bundle.json").read_bytes()
            from kapisch_core.bundle import verify_bundle

            bundle = verify_bundle(
                bundle_bytes, __import__("hashlib").sha256(bundle_bytes).hexdigest()
            )
            with self.assertRaisesRegex(ValueError, "reference is invalid"):
                _invocation._validate_review_scope_request(
                    Path(temporary), "run", packet, bundle
                )

    def test_persist_request_validates_scope_once_before_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            bundle_bytes = (ROOT / "core/dist/core-bundle.json").read_bytes()
            bundle_digest = store_bundle(repo, bundle_bytes)
            run_id = "run-review-order"
            stage_id = "s-" + "1" * 32
            operation_id = "op-" + "2" * 32
            state = {
                "protocol_version": 3,
                "run_id": run_id,
                "bundle_digest": bundle_digest,
                "workflow": "task",
                "revision": 0,
                "history": [
                    {
                        "stage_id": stage_id,
                        "stage_kind": "implement",
                        "sequence": 0,
                        "role": "reviewer",
                        "status": "planned",
                        "producer": "controller",
                        "evidence": [],
                        "scope_digest": "a" * 64,
                    }
                ],
                "identity_contract": "stage-attempt/1",
            }
            publish_state(repo, run_id, state, expected_revision=-1)
            packet = {
                "run_id": run_id,
                "operation_id": operation_id,
                "stage_id": stage_id,
                "role": "reviewer",
                "purpose": "iteration",
                "bundle_digest": bundle_digest,
                "scope_digest": "a" * 64,
                "review_scope": {"path": "unused", "sha256": "b" * 64},
                "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
            }
            calls = []
            publish_input = _invocation._publish_request_inputs
            publish_immutable = _invocation._publish_immutable

            def inputs(*args):
                calls.append("inputs")
                publish_input(*args)

            def immutable(directory, name, body):
                if name == f"{operation_id}.json":
                    calls.append("request")
                return publish_immutable(directory, name, body)

            with (
                patch.object(
                    _invocation,
                    "_validate_review_scope_request",
                    side_effect=lambda *args: calls.append("scope"),
                ),
                patch.object(
                    _invocation, "_publish_request_inputs", side_effect=inputs
                ),
                patch.object(_invocation, "_publish_immutable", side_effect=immutable),
            ):
                persist_request(repo, run_id, operation_id, packet)
            self.assertEqual(calls, ["scope", "inputs", "request"])
            self.assertEqual(calls.count("scope"), 1)

    def test_reserve_operation_validates_review_scope_before_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_id, stage_id, packet, _ = self._validator_fixture(repo)
            operation_id = packet["operation_id"]
            packet["review_scope"] = {
                "path": "unused",
                "sha256": "b" * 64,
            }
            with patch.object(_invocation, "_validate_review_scope_request"):
                persist_request(repo, run_id, operation_id, packet)

            run = repo / ".kapisch/v3/runs" / run_id
            request_bytes = (run / "requests" / f"{operation_id}.json").read_bytes()
            request = {
                "path": f"requests/{operation_id}.json",
                "sha256": hashlib.sha256(request_bytes).hexdigest(),
            }
            state_before = (run / "state.json").read_bytes()
            with patch.object(
                _invocation,
                "_validate_review_scope_request",
                side_effect=ValueError("reservation scope refusal"),
            ) as scope_validator:
                with self.assertRaisesRegex(ValueError, "reservation scope refusal"):
                    _invocation.reserve_operation(
                        repo,
                        run_id,
                        operation_id,
                        stage_id,
                        "reviewer",
                        request,
                        packet["adapter_binding"],
                    )
            scope_validator.assert_called_once()
            self.assertFalse(
                (run / "invocations" / operation_id / "planned.json").exists()
            )
            self.assertEqual((run / "state.json").read_bytes(), state_before)

    def test_real_invalid_scopes_prevent_input_and_request_publication(self) -> None:
        cases = (
            ("malformed locator", "unused", "b" * 64, ValueError),
            (
                "missing scope file",
                ".kapisch/v3/runs/{run_id}/review-inputs/scopes/" + "b" * 64 + ".json",
                "b" * 64,
                FileNotFoundError,
            ),
            (
                "digest mismatch",
                ".kapisch/v3/runs/{run_id}/review-inputs/scopes/" + "b" * 64 + ".json",
                "b" * 64,
                ValueError,
            ),
        )
        for name, scope_path, digest, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                repo = Path(temporary)
                run_id, _, packet, _ = self._validator_fixture(repo)
                operation_id = packet["operation_id"]
                packet["review_scope"] = {
                    "path": scope_path.format(run_id=run_id),
                    "sha256": digest,
                }
                run = repo / ".kapisch/v3/runs" / run_id
                state_before = (run / "state.json").read_bytes()
                if name == "digest mismatch":
                    target = repo / packet["review_scope"]["path"]
                    target.parent.mkdir(parents=True)
                    target.write_bytes(b"{}")

                with (
                    patch.object(_invocation, "_publish_request_inputs") as inputs,
                    patch.object(_invocation, "_publish_immutable") as immutable,
                    self.assertRaises(error),
                ):
                    persist_request(repo, run_id, operation_id, packet)

                inputs.assert_not_called()
                immutable.assert_not_called()
                self.assertEqual((run / "state.json").read_bytes(), state_before)
                self.assertFalse((run / "request-inputs" / operation_id).exists())
                self.assertFalse((run / "requests" / f"{operation_id}.json").exists())

    def test_invalid_scope_prevents_input_and_request_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            bundle_bytes = (ROOT / "core/dist/core-bundle.json").read_bytes()
            bundle_digest = store_bundle(repo, bundle_bytes)
            run_id = "run-review-invalid"
            stage_id = "s-" + "3" * 32
            operation_id = "op-" + "4" * 32
            state = {
                "protocol_version": 3,
                "run_id": run_id,
                "bundle_digest": bundle_digest,
                "workflow": "task",
                "revision": 0,
                "history": [
                    {
                        "stage_id": stage_id,
                        "stage_kind": "implement",
                        "sequence": 0,
                        "role": "reviewer",
                        "status": "planned",
                        "producer": "controller",
                        "evidence": [],
                        "scope_digest": "a" * 64,
                    }
                ],
                "identity_contract": "stage-attempt/1",
            }
            publish_state(repo, run_id, state, expected_revision=-1)
            before = (repo / ".kapisch/v3/runs" / run_id / "state.json").read_bytes()
            packet = {
                "run_id": run_id,
                "operation_id": operation_id,
                "stage_id": stage_id,
                "role": "reviewer",
                "purpose": "iteration",
                "bundle_digest": bundle_digest,
                "scope_digest": "a" * 64,
                "review_scope": {"path": "unused", "sha256": "b" * 64},
                "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
            }
            with (
                patch.object(
                    _invocation,
                    "_validate_review_scope_request",
                    side_effect=ValueError("invalid scope"),
                ),
                patch.object(_invocation, "_publish_request_inputs") as inputs,
                patch.object(_invocation, "_publish_immutable") as request_writer,
            ):
                with self.assertRaisesRegex(ValueError, "invalid scope"):
                    persist_request(repo, run_id, operation_id, packet)
            inputs.assert_not_called()
            request_writer.assert_not_called()
            run = repo / ".kapisch/v3/runs" / run_id
            self.assertFalse((run / "request-inputs" / operation_id).exists())
            self.assertFalse((run / "requests" / f"{operation_id}.json").exists())
            self.assertEqual((run / "state.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
