from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))

from kapisch_core.review import (  # noqa: E402
    HostProvenanceAttestation,
    ImmutableArtifactLocator,
    ReviewerReturn,
    ReviewInvocation,
    ReviewResult,
    ReviewScopeArtifact,
)
from kapisch_core.review_persistence import load_review_scope  # noqa: E402


class ReviewScopePersistenceTests(unittest.TestCase):
    def _state(self, run_id: str, bundle_digest: str) -> dict:
        return {
            "protocol_version": 3,
            "run_id": run_id,
            "bundle_digest": bundle_digest,
            "workflow": "task",
            "revision": 0,
            "history": [{
                "stage_id": "s-00000000000000000000000000000001",
                "stage_kind": "review",
                "sequence": 0,
                "role": "reviewer",
                "status": "planned",
                "producer": "controller",
                "evidence": [],
                "scope_digest": "b" * 64,
            }],
            "identity_contract": "stage-attempt/1",
        }

    def test_scope_publisher_refuses_without_durable_stage_evidence_binding(self) -> None:
        from kapisch_core.protocol import publish_review_scope, publish_state
        from kapisch_core.storage import store_bundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
            digest = store_bundle(root, bundle)
            state = self._state("run-scope-gate", digest)
            publish_state(root, state["run_id"], state, expected_revision=-1)

            with self.assertRaises(ValueError):
                publish_review_scope(
                    root,
                    state["run_id"],
                    state["history"][0]["stage_id"],
                )

    def test_backlink_repair_persists_one_entry_for_complete_chain(self) -> None:
        import shutil
        from unittest.mock import patch

        scope_validation = patch("kapisch_core._invocation._validate_review_scope_request")
        scope_validation.start()
        self.addCleanup(scope_validation.stop)

        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import (
            load_state,
            persist_request,
            publish_review_invocation,
            publish_state,
            publish_uncertainty,
            repair_review_backlinks,
            reserve_operation,
        )
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        run_id = "run-backlink-complete"
        operation_id = "op-" + "a" * 32
        stage_id = "s-00000000000000000000000000000001"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
            digest = store_bundle(root, bundle)
            state = self._state(run_id, digest)
            state["history"][0]["stage_id"] = stage_id
            publish_state(root, run_id, state, expected_revision=-1)

            candidate_ref = ImmutableArtifactLocator(
                ".kapisch/v3/authority/plan-approval-candidates/" + "a" * 64 + ".json",
                "a" * 64,
            )
            scope = ReviewScopeArtifact(
                run_id=run_id,
                stage_id=stage_id,
                purpose="iteration",
                plan_candidate_ref=candidate_ref,
                comparison_base="sha1:" + "b" * 40,
            )
            scope_data = scope.canonical_bytes()
            scope_digest = hashlib.sha256(scope_data).hexdigest()
            scope_locator = ImmutableArtifactLocator(
                f".kapisch/v3/runs/{run_id}/review-inputs/scopes/{scope_digest}.json",
                scope_digest,
            )
            scope_path = root / scope_locator.path
            scope_path.parent.mkdir(parents=True)
            scope_path.write_bytes(scope_data)

            packet = {
                "run_id": run_id,
                "operation_id": operation_id,
                "stage_id": stage_id,
                "role": "reviewer",
                "purpose": "iteration",
                "bundle_digest": digest,
                "scope_digest": state["history"][0]["scope_digest"],
                "review_scope": scope_locator.to_dict(),
                "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
            }
            with patch("kapisch_core._invocation._validate_review_scope_request"):
                request_path, request_digest = persist_request(
                    root, run_id, operation_id, packet
                )
            fingerprint = {
                "object_format": "sha1",
                "head": "d" * 40,
                "index": [],
                "worktree": [],
                "untracked": [],
            }
            fingerprint_data = canonical_json(fingerprint)
            fingerprint_digest = hashlib.sha256(fingerprint_data).hexdigest()
            fingerprint_locator = ImmutableArtifactLocator(
                f".kapisch/v3/runs/{run_id}/review-inputs/{operation_id}/pre-dispatch-fingerprint.json",
                fingerprint_digest,
            )
            fingerprint_path = root / fingerprint_locator.path
            fingerprint_path.parent.mkdir(parents=True)
            fingerprint_path.write_bytes(fingerprint_data)
            with patch("kapisch_core._invocation._validate_review_scope_request"):
                reserve_operation(
                    root,
                    run_id,
                    operation_id,
                    stage_id,
                    "reviewer",
                    {"path": request_path, "sha256": request_digest},
                    packet["adapter_binding"],
                )
            operation_dir = root / ".kapisch/v3/runs" / run_id / "invocations" / operation_id
            planned_data = (operation_dir / "planned.json").read_bytes()
            uncertain_data = canonical_json(
                {**json.loads(planned_data), "status": "dispatch-uncertain"}
            )
            uncertain_path = f"invocations/{operation_id}/dispatch-uncertain.json"
            uncertain = {
                **state["history"][0],
                "sequence": 1,
                "status": "dispatch-uncertain",
                "evidence": [
                    {"kind": "request", "path": request_path, "sha256": request_digest},
                    {"kind": "protocol", "path": f"review-inputs/{operation_id}/pre-dispatch-fingerprint.json", "sha256": fingerprint_digest},
                    {"kind": "protocol", "path": f"invocations/{operation_id}/planned.json", "sha256": hashlib.sha256(planned_data).hexdigest()},
                    {"kind": "protocol", "path": uncertain_path, "sha256": hashlib.sha256(uncertain_data).hexdigest()},
                ],
            }
            publish_uncertainty(
                root,
                run_id,
                {**state, "revision": 1, "history": [state["history"][0], uncertain]},
                expected_revision=0,
                operation_id=operation_id,
            )
            state_after_uncertainty = {**state, "revision": 1, "history": [state["history"][0], uncertain]}
            invocation = ReviewInvocation(
                ImmutableArtifactLocator(
                    f".kapisch/v3/bundles/{digest}.json", digest
                ),
                ImmutableArtifactLocator(
                    f".kapisch/v3/runs/{run_id}/{request_path}", request_digest
                ),
                {"run_id": run_id, "stage_id": stage_id},
                {"run_id": run_id, "operation_id": operation_id},
                scope_locator,
                "sha1:" + "b" * 40,
                "sha1:" + "d" * 40,
                "iteration",
                (),
                fingerprint_locator,
            )
            producer = (
                {"purpose": "iteration", "head": invocation.head},
                {},
                {"base": invocation.base},
            )
            with patch("kapisch_core._review_chain._load_bound_base", return_value=producer):
                invocation_locator = publish_review_invocation(root, invocation)
            report = b"review report\n"
            report_digest = hashlib.sha256(report).hexdigest()
            report_locator = ImmutableArtifactLocator(
                f".kapisch/v3/runs/{run_id}/reports/{operation_id}.json", report_digest
            )
            report_path = root / report_locator.path
            report_path.parent.mkdir(parents=True)
            report_path.write_bytes(report)
            target = {
                "run_id": run_id,
                "stage_id": stage_id,
                "operation_id": operation_id,
                "base": invocation.base,
                "head": invocation.head,
            }
            reviewer_return = ReviewerReturn(
                invocation_locator,
                {"run_id": run_id, "operation_id": operation_id},
                invocation.request,
                target,
                invocation.pre_dispatch_fingerprint,
                report_locator,
                report_digest,
                "clear",
            )
            reviewer_locator = ImmutableArtifactLocator(
                f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/reviewer-return.json",
                hashlib.sha256(reviewer_return.canonical_bytes()).hexdigest(),
            )
            provenance = HostProvenanceAttestation(
                reviewer_locator,
                reviewer_locator.sha256,
                {"host": "test"},
                {"context": "test"},
                {"dispatch": "not-run"},
            )
            provenance_locator = ImmutableArtifactLocator(
                f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/host-provenance-attestation.json",
                hashlib.sha256(provenance.canonical_bytes()).hexdigest(),
            )
            post_result_locator = ImmutableArtifactLocator(
                f".kapisch/v3/runs/{run_id}/invocations/{operation_id}/post-result.json",
                fingerprint_digest,
            )
            result = ReviewResult(
                invocation_locator,
                invocation.request,
                target,
                scope_locator,
                fingerprint_locator,
                reviewer_locator,
                post_result_locator,
                provenance_locator,
            )
            (operation_dir / "reviewer-return.json").write_bytes(reviewer_return.canonical_bytes())
            (operation_dir / "host-provenance-attestation.json").write_bytes(provenance.canonical_bytes())
            (operation_dir / "post-result.json").write_bytes(fingerprint_data)
            result_data = result.canonical_bytes()
            (operation_dir / "review-result.json").write_bytes(result_data)
            complete = {
                **uncertain,
                "sequence": 2,
                "status": "complete",
                "evidence": [
                    *uncertain["evidence"],
                    {"kind": "protocol", "path": f"invocations/{operation_id}/review-invocation.json", "sha256": hashlib.sha256((operation_dir / "review-invocation.json").read_bytes()).hexdigest()},
                    {"kind": "protocol", "path": f"invocations/{operation_id}/reviewer-return.json", "sha256": reviewer_locator.sha256},
                    {"kind": "protocol", "path": f"invocations/{operation_id}/host-provenance-attestation.json", "sha256": provenance_locator.sha256},
                    {"kind": "protocol", "path": f"invocations/{operation_id}/post-result.json", "sha256": fingerprint_digest},
                    {"kind": "protocol", "path": f"invocations/{operation_id}/review-result.json", "sha256": hashlib.sha256(result_data).hexdigest()},
                ],
            }
            publish_state(
                root,
                run_id,
                {**state_after_uncertainty, "revision": 2, "history": [state["history"][0], uncertain, complete]},
                expected_revision=1,
            )

            with patch("kapisch_core._review_chain._load_bound_base", return_value=producer):
                repaired = repair_review_backlinks(root, run_id)

            self.assertEqual(len(repaired), 1)
            loaded = load_state(root, run_id)
            self.assertEqual(
                loaded["review_result_ref"][operation_id],
                {"path": repaired[0].path, "sha256": repaired[0].sha256},
            )
            self.assertEqual(loaded["revision"], 3)
            with patch("kapisch_core._review_chain._load_bound_base", return_value=producer):
                self.assertEqual(validate_run(root, run_id), [])
                self.assertEqual(repair_review_backlinks(root, run_id), repaired)
            self.assertEqual(load_state(root, run_id)["revision"], 3)
            dropped = dict(loaded)
            dropped.pop("review_result_ref")
            dropped["revision"] = 4
            with self.assertRaisesRegex(ValueError, "guarded repair"):
                publish_state(root, run_id, dropped, expected_revision=3)
            replaced = dict(loaded)
            replaced["review_result_ref"] = {
                operation_id: {
                    "path": repaired[0].path,
                    "sha256": "d" * 64,
                }
            }
            replaced["revision"] = 4
            with self.assertRaisesRegex(ValueError, "guarded repair"):
                publish_state(root, run_id, replaced, expected_revision=3)
            shutil.rmtree(root / ".kapisch/v3/runs" / run_id / "invocations")
            self.assertTrue(validate_run(root, run_id))

    def test_backlink_repair_rejects_partial_review_chain(self) -> None:
        from kapisch_core.protocol import publish_state, repair_review_backlinks
        from kapisch_core.storage import store_bundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
            digest = store_bundle(root, bundle)
            state = self._state("run-backlink-partial", digest)
            publish_state(root, state["run_id"], state, expected_revision=-1)
            operation = (
                root
                / ".kapisch/v3/runs"
                / state["run_id"]
                / "invocations"
                / ("op-" + "a" * 32)
            )
            operation.mkdir(parents=True)
            (operation / "review-invocation.json").write_bytes(b"{}\n")

            with self.assertRaisesRegex(ValueError, "original reservation|partial"):
                repair_review_backlinks(root, state["run_id"])

    def test_generic_state_publication_rejects_fabricated_backlinks(self) -> None:
        from kapisch_core.protocol import publish_state
        from kapisch_core.storage import store_bundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
            digest = store_bundle(root, bundle)
            state = self._state("run-backlink-state", digest)
            operation_id = "op-" + "a" * 32
            state["review_result_ref"] = {
                operation_id: {
                    "path": f".kapisch/v3/runs/{state['run_id']}/invocations/{operation_id}/review-result.json",
                    "sha256": "c" * 64,
                }
            }
            with self.assertRaisesRegex(ValueError, "guarded repair"):
                publish_state(root, state["run_id"], state, expected_revision=-1)

    def test_backlink_repair_is_noop_without_complete_result_chains(self) -> None:
        from kapisch_core.protocol import publish_state, repair_review_backlinks
        from kapisch_core.storage import store_bundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
            digest = store_bundle(root, bundle)
            state = self._state("run-backlink-noop", digest)
            publish_state(root, state["run_id"], state, expected_revision=-1)

            self.assertEqual(repair_review_backlinks(root, state["run_id"]), ())

            from kapisch_core.protocol import load_state

            loaded = load_state(root, state["run_id"])
            self.assertNotIn("review_result_ref", loaded)

    def test_invocation_publisher_refuses_without_owned_reservation(self) -> None:
        from kapisch_core.protocol import publish_review_invocation, publish_state
        from kapisch_core.storage import store_bundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
            digest = store_bundle(root, bundle)
            state = self._state("run-invocation-gate", digest)
            publish_state(root, state["run_id"], state, expected_revision=-1)
            locator = ImmutableArtifactLocator
            invocation = ReviewInvocation(
                locator(".kapisch/v3/bundles/" + digest + ".json", digest),
                locator(".kapisch/v3/runs/run-invocation-gate/requests/op-" + "a" * 32 + ".json", "a" * 64),
                {"run_id": state["run_id"], "stage_id": state["history"][0]["stage_id"]},
                {"run_id": state["run_id"], "operation_id": "op-" + "a" * 32},
                locator(".kapisch/v3/runs/run-invocation-gate/review-inputs/scopes/" + "b" * 64 + ".json", "b" * 64),
                "sha1:" + "c" * 40,
                "sha1:" + "d" * 40,
                "iteration",
                (),
                locator(".kapisch/v3/runs/run-invocation-gate/review-inputs/op-" + "a" * 32 + "/pre-dispatch-fingerprint.json", "e" * 64),
            )

            with self.assertRaises(ValueError):
                publish_review_invocation(root, invocation)

    def test_prior_root_loader_rejects_ambiguous_stage_bindings(self) -> None:
        from kapisch_core._review_scope import _validate_prior_roots

        state = {
            "history": [{
                "stage_id": "s-" + "a" * 32,
                "evidence": [
                    {"kind": "review-target-binding/1", "path": "first", "sha256": "a" * 64},
                    {"kind": "review-target-binding/1", "path": "second", "sha256": "b" * 64},
                ],
            }],
        }
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            _validate_prior_roots(Path("/tmp"), "run-ambiguous", state, {})

    def test_bound_loader_rejects_numeric_artifact_strictness(self) -> None:
        from unittest.mock import patch

        from kapisch_core._review_scope import _load_bound_base
        from kapisch_core.bundle import canonical_json

        run_id = "run-artifact"
        stage_id = "s-" + "b" * 32
        candidate_ref = {
            "path": ".kapisch/v3/authority/plan-approval-candidates/" + "a" * 64 + ".json",
            "sha256": "a" * 64,
        }
        target = {"kind": "whole-branch", "ref": "refs/heads/main"}
        root = {
            "protocol_version": 3,
            "comparison_root_contract": "comparison-root/1",
            "run_id": run_id,
            "plan_candidate_ref": candidate_ref,
            "plan_id": "plan",
            "target": target,
            "object_format": "sha1",
            "anchor": "sha1:" + "c" * 40,
        }
        reservation_root = {
            "source": "stage5-target-binding",
            "anchor": root["anchor"],
            "must_differ_from_head": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            root_ref = {
                "path": f".kapisch/v3/runs/{run_id}/review-inputs/comparison-roots/{candidate_ref['sha256']}.json",
                "sha256": "f" * 64,
            }
            base = "sha1:" + "c" * 40
            head = "sha1:" + "d" * 40
            base_ref = {
                "path": f".kapisch/v3/runs/{run_id}/review-inputs/comparison-bases/{'b' * 64}.json",
                "sha256": "b" * 64,
            }
            target_ref = {
                "path": f".kapisch/v3/runs/{run_id}/review-inputs/review-targets/{'d' * 64}.json",
                "sha256": "d" * 64,
            }
            reservation = {
                "protocol_version": 3,
                "review_target_binding_contract": "review-target-binding/1",
                "run_id": run_id,
                "stage_id": stage_id,
                "plan_candidate_ref": candidate_ref,
                "plan_id": "plan",
                "target": target,
                "purpose": "iteration",
                "comparison_root_ref": root_ref,
                "comparison_root": reservation_root,
                "comparison_base_ref": base_ref,
                "object_format": "sha1",
                "base": base,
                "head": head,
                "review_target_ref": target_ref,
            }
            target_artifact = {**reservation, "review_target_contract": "review-target/1"}
            target_artifact.pop("review_target_binding_contract")
            target_artifact["comparison_root"] = {**reservation_root, "must_differ_from_head": 1}
            target_artifact.pop("review_target_ref")
            base_artifact = {
                key: reservation[key]
                for key in (
                    "protocol_version", "run_id", "stage_id", "plan_candidate_ref",
                    "plan_id", "target", "purpose", "comparison_root_ref",
                    "comparison_root", "object_format", "base", "head",
                )
            }
            base_artifact["comparison_base_contract"] = "comparison-base/1"
            binding_path = f"review-inputs/review-target-bindings/{'e' * 64}.json"
            binding_data = canonical_json(reservation)
            binding_file = repo / f".kapisch/v3/runs/{run_id}/{binding_path}"
            binding_file.parent.mkdir(parents=True)
            binding_file.write_bytes(binding_data)
            binding_digest = hashlib.sha256(binding_data).hexdigest()
            binding_path = f"review-inputs/review-target-bindings/{binding_digest}.json"
            binding_file.rename(binding_file.with_name(f"{binding_digest}.json"))
            state = {"plan_candidate_ref": candidate_ref, "bundle_digest": "bundle", "history": []}
            attempt = {"stage_id": stage_id, "evidence": [{"kind": "review-target-binding/1", "path": binding_path, "sha256": binding_digest}]}
            candidate = {
                "run_id": run_id,
                "bundle_digest": "bundle",
                "plan_ref": {"plan_id": "plan"},
                "execution_binding": {"mode": "graph-free"},
            }
            def read_artifact(repo_path, run, value, pattern, label, **kwargs):
                return {"comparison-root": root, "review-target": target_artifact, "comparison-base": base_artifact}[label], b""

            with patch("kapisch_core._review_scope.validate_plan_approval_candidate", return_value=(candidate, None)), patch("kapisch_core._review_scope._read_locator", side_effect=read_artifact):
                with self.assertRaisesRegex(ValueError, "artifact root is invalid"):
                    _load_bound_base(repo, run_id, state, attempt)

    def test_reservation_rejects_non_scalar_role(self) -> None:
        from kapisch_core._invocation import _validate_reservation

        operation_id = "op-" + "a" * 32
        fact = {
            "protocol_version": 3,
            "operation_id": operation_id,
            "run_id": "run-role",
            "stage_id": "s-" + "b" * 32,
            "role": [],
            "request_digest": "c" * 64,
            "status": "planned",
            "request": {"path": f"requests/{operation_id}.json", "sha256": "c" * 64},
            "adapter_binding": {"adapter_id": "adapter", "lookup_context": "context"},
        }
        with self.assertRaises(ValueError):
            _validate_reservation(Path("/tmp"), "run-role", operation_id, fact)

    def test_fingerprint_rejects_noncanonical_optional_digest_fields(self) -> None:
        from kapisch_core._review_chain import _fingerprint_data
        from kapisch_core.bundle import canonical_json

        run_id = "run-fingerprint"
        operation_id = "op-" + "a" * 32
        value = {
            "object_format": "sha1",
            "head": "b" * 40,
            "index": [],
            "worktree": [],
            "untracked": [{"path_hex": "61", "included": False, "sha256": None}],
        }
        data = canonical_json(value)
        digest = hashlib.sha256(data).hexdigest()
        locator = ImmutableArtifactLocator(
            f".kapisch/v3/runs/{run_id}/review-inputs/{operation_id}/pre-dispatch-fingerprint.json",
            digest,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / locator.path
            path.parent.mkdir(parents=True)
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "facts are invalid"):
                _fingerprint_data(Path(temporary), run_id, operation_id, locator)

    def test_comparison_root_uses_candidate_addressed_path_and_content_digest(self) -> None:
        from kapisch_core._review_scope import _load_root
        from kapisch_core.bundle import canonical_json

        run_id = "run-root"
        candidate_ref = {
            "path": ".kapisch/v3/authority/plan-approval-candidates/" + "a" * 64 + ".json",
            "sha256": "a" * 64,
        }
        target = {"kind": "whole-branch", "ref": "refs/heads/main"}
        root = {
            "protocol_version": 3,
            "comparison_root_contract": "comparison-root/1",
            "run_id": run_id,
            "plan_candidate_ref": candidate_ref,
            "plan_id": "plan-1",
            "target": target,
            "object_format": "sha1",
            "anchor": "sha1:" + "b" * 40,
        }
        data = canonical_json(root)
        digest = hashlib.sha256(data).hexdigest()
        locator = {
            "path": f".kapisch/v3/runs/{run_id}/review-inputs/comparison-roots/{candidate_ref['sha256']}.json",
            "sha256": digest,
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / locator["path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(data)
            loaded = _load_root(
                Path(temporary), run_id, locator, candidate_ref, "plan-1", target
            )
            invalid = {**root, "protocol_version": 3.0}
            invalid_data = canonical_json(invalid)
            path.write_bytes(invalid_data)
            invalid_locator = {
                "path": locator["path"],
                "sha256": hashlib.sha256(invalid_data).hexdigest(),
            }
            with self.assertRaises(ValueError):
                _load_root(
                    Path(temporary),
                    run_id,
                    invalid_locator,
                    candidate_ref,
                    "plan-1",
                    target,
                )
        self.assertEqual(loaded, root)

    def test_load_review_scope_requires_exact_digest_addressed_bytes(self) -> None:
        scope = ReviewScopeArtifact(
            run_id="run",
            stage_id="s-00000000000000000000000000000001",
            purpose="iteration",
            plan_candidate_ref=ImmutableArtifactLocator(
                ".kapisch/v3/authority/plan-approval-candidates/" + "a" * 64 + ".json",
                "a" * 64,
            ),
            comparison_base="sha1:" + "b" * 40,
        )
        data = scope.canonical_bytes()
        digest = hashlib.sha256(data).hexdigest()
        locator = ImmutableArtifactLocator(
            f".kapisch/v3/runs/run/review-inputs/scopes/{digest}.json", digest
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / locator.path
            path.parent.mkdir(parents=True)
            path.write_bytes(data)

            loaded = load_review_scope(root, locator)

        self.assertEqual(loaded.canonical_bytes(), data)

    def test_load_review_scope_rejects_substituted_bytes(self) -> None:
        scope = ReviewScopeArtifact(
            run_id="run",
            stage_id="s-00000000000000000000000000000001",
            purpose="iteration",
            plan_candidate_ref=ImmutableArtifactLocator(
                ".kapisch/v3/authority/plan-approval-candidates/" + "a" * 64 + ".json",
                "a" * 64,
            ),
            comparison_base="sha1:" + "b" * 40,
        )
        data = scope.canonical_bytes()
        digest = hashlib.sha256(data).hexdigest()
        locator = ImmutableArtifactLocator(
            f".kapisch/v3/runs/run/review-inputs/scopes/{digest}.json", digest
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / locator.path
            path.parent.mkdir(parents=True)
            path.write_bytes(data + b"tampered")

            with self.assertRaises(ValueError):
                load_review_scope(root, locator)


if __name__ == "__main__":
    unittest.main()
