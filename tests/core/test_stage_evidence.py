"""Stage 4 consumers; external target facts are test-only producer fixtures."""

from __future__ import annotations

import unittest
from typing import Any

from kapisch_core._state import _validate_history


def creation() -> dict[str, Any]:
    return {
        "stage_id": "s-" + "1" * 32,
        "stage_kind": "review",
        "sequence": 0,
        "role": "reviewer",
        "status": "planned",
        "producer": "controller",
        "evidence": [],
        "scope_digest": "a" * 64,
    }


def locator(digest="b" * 64):
    return {
        "kind": "review-target-binding/1",
        "path": f"review-inputs/review-target-bindings/{digest}.json",
        "sha256": digest,
    }


class StageEvidenceHistoryTests(unittest.TestCase):
    def test_exact_second_planned_observation(self):
        first = creation()
        second = dict(first, sequence=1, evidence=[locator()])
        _validate_history([first, second], "task")
        _validate_history(
            [first, second, dict(second, sequence=2, status="complete")], "task"
        )

    def test_binding_structure_rejections(self):
        first = creation()
        second = dict(first, sequence=1, evidence=[locator()])
        invalid = [
            [dict(first, evidence=[locator()])],
            [first, dict(second, status="complete")],
            [first, second, dict(second, sequence=2)],
            [first, dict(second, evidence=[locator(), locator()])],
            [first, dict(second, evidence=[dict(locator(), kind="other")])],
            [first, second, dict(second, sequence=2, status="complete", evidence=[])],
            [first, dict(second, role="researcher")],
        ]
        for history in invalid:
            with self.subTest(history=history), self.assertRaises(ValueError):
                _validate_history(history, "task")


class StageEvidenceTests(unittest.TestCase):
    bundle_data: bytes

    def setUp(self):
        import hashlib
        import tempfile
        from pathlib import Path

        from kapisch_core._human_evidence import (
            ExternalArtifactInput,
            ExternalInputSource,
        )
        from kapisch_core.advisory import (
            prepare_plan_approval,
            propose_scope,
            publish_plan_approval,
        )
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import load_state, publish_state
        from kapisch_core.storage import store_bundle

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.run_root = self.repo / ".kapisch/v3/runs/run-1"
        bundle = Path(__file__).resolve().parents[2] / "core/dist/core-bundle.json"
        digest = store_bundle(
            self.repo, getattr(self, "bundle_data", bundle.read_bytes())
        )
        scope = propose_scope(
            self.repo, "run-1", "scope-1", "requirements", {"mode": "all"}
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
                "origin_run_id": scope.origin_run_id,
                "scope_id": scope.scope_id,
                "sha256": scope.sha256,
            },
        }
        publish_state(self.repo, "run-1", state, -1)
        payload = prepare_plan_approval(
            self.repo, "run-1", "plan-gate", "plan-1", b"plan"
        )
        artifact = canonical_json(
            {
                "protocol_version": 3,
                "run_id": "run-1",
                "gate_id": "plan-gate",
                "identity": payload["identity"],
                "decision": "approve",
                "target": hashlib.sha256(canonical_json(payload)).hexdigest(),
                "scope_digest": payload["scope_digest"],
            }
        )
        publish_plan_approval(
            self.repo,
            payload,
            ExternalArtifactInput(
                "test-external-human", artifact, ExternalInputSource.EXTERNALLY_SUPPLIED
            ),
        )
        self.state = load_state(self.repo, "run-1")
        self.state["revision"] += 1
        self.first = creation()
        self.first["scope_digest"] = scope.sha256
        self.state["history"] = [self.first]
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        self.root = {
            "protocol_version": 3,
            "comparison_root_contract": "comparison-root/1",
            "run_id": "run-1",
            "plan_candidate_ref": self.state["plan_candidate_ref"],
            "plan_id": "plan-1",
            "target": {"kind": "whole-branch", "ref": "refs/heads/work"},
            "object_format": "sha1",
            "anchor": "sha1:" + "a" * 40,
        }
        root_path = (
            "review-inputs/comparison-roots/"
            + self.state["plan_candidate_ref"]["sha256"]
            + ".json"
        )
        self.root_ref = self.external_fact(self.root, root_path)
        self.binding = {
            "protocol_version": 3,
            "review_target_binding_contract": "review-target-binding/1",
            "run_id": "run-1",
            "stage_id": self.first["stage_id"],
            "plan_candidate_ref": self.state["plan_candidate_ref"],
            "plan_id": "plan-1",
            "target": self.root["target"],
            "purpose": "iteration",
            "comparison_root_ref": self.root_ref,
            "comparison_root": {
                "source": "stage5-target-binding",
                "anchor": self.root["anchor"],
                "must_differ_from_head": False,
            },
            "comparison_base_ref": {
                "path": ".kapisch/v3/runs/run-1/review-inputs/comparison-bases/"
                + "c" * 64
                + ".json",
                "sha256": "c" * 64,
            },
            "object_format": "sha1",
            "base": self.root["anchor"],
            "head": "sha1:" + "b" * 40,
            "review_target_ref": {
                "path": ".kapisch/v3/runs/run-1/review-inputs/review-targets/"
                + "d" * 64
                + ".json",
                "sha256": "d" * 64,
            },
        }
        self.ref = self.external_binding(self.binding)

    def external_fact(self, value, path):
        import hashlib

        from kapisch_core.bundle import canonical_json

        data = canonical_json(value)
        dest = self.run_root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return {
            "path": ".kapisch/v3/runs/run-1/" + path,
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def external_binding(self, value):
        import hashlib

        from kapisch_core.bundle import canonical_json

        digest = hashlib.sha256(canonical_json(value)).hexdigest()
        self.external_fact(value, locator(digest)["path"])
        return locator(digest)

    def proposal(self):
        import copy

        state = copy.deepcopy(self.state)
        state["revision"] += 1
        state["history"].append(
            dict(self.first, sequence=len(state["history"]), evidence=[self.ref])
        )
        return state

    def bind(self):
        from kapisch_core.protocol import publish_state

        publish_state(self.repo, "run-1", self.proposal(), self.state["revision"])

    def test_public_bind_reload_and_read_only_validation(self):
        from kapisch_core.protocol import load_state
        from kapisch_core.validation import validate_run

        self.bind()
        before = (self.run_root / "state.json").read_bytes()
        self.assertEqual(load_state(self.repo, "run-1"), self.proposal())
        self.assertEqual(validate_run(self.repo, "run-1"), [])
        self.assertEqual((self.run_root / "state.json").read_bytes(), before)

    def test_historical_load_checks_later_evidence(self):
        from kapisch_core.protocol import load_state, publish_state

        ref = self.external_fact({"fact": "later"}, "later.json")
        self.bind()
        state = self.proposal()
        row: dict[str, Any] = dict(state["history"][-1], sequence=2, status="complete")
        row["evidence"] = row["evidence"] + [
            dict(ref, kind="local-check", path="later.json")
        ]
        state["history"].append(row)
        state["revision"] += 1
        publish_state(self.repo, "run-1", state, state["revision"] - 1)
        (self.run_root / "later.json").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            load_state(self.repo, "run-1")

    def authority_bytes(self):
        return {
            str(path.relative_to(self.repo)): path.read_bytes()
            for path in (self.repo / ".kapisch/v3").rglob("*")
            if path.is_file() and not path.name.endswith(".lock")
        }

    def assert_refusal(self, proposal=None):
        from kapisch_core.protocol import publish_state

        before = self.authority_bytes()
        directories = {
            namespace: (self.run_root / "review-inputs" / namespace).exists()
            for namespace in ("review-targets", "comparison-bases", "scopes")
        }
        with self.assertRaises((ValueError, OSError)):
            publish_state(
                self.repo, "run-1", proposal or self.proposal(), self.state["revision"]
            )
        self.assertEqual(self.authority_bytes(), before)
        for namespace in ("review-targets", "comparison-bases", "scopes"):
            self.assertEqual(
                (self.run_root / "review-inputs" / namespace).exists(),
                directories[namespace],
            )

    def test_closed_reservation_and_root_negative_matrix(self):
        import copy

        original_path = self.run_root / self.ref["path"]
        original = original_path.read_bytes()
        mutations = [
            ("purpose", "final"),
            ("run_id", "other-run"),
            ("stage_id", "s-" + "2" * 32),
            ("plan_id", "other-plan"),
            ("protocol_version", True),
            ("unknown", "field"),
            ("target", {"kind": "whole-branch", "ref": "refs/heads/../escape"}),
            ("target", {"kind": "detached", "ref": "refs/heads/work"}),
            ("base", "sha1:" + "c" * 40),
            ("head", "sha256:" + "b" * 64),
            ("comparison_root", dict(self.binding["comparison_root"], source="caller")),
            (
                "comparison_root",
                dict(self.binding["comparison_root"], must_differ_from_head=None),
            ),
            (
                "comparison_root_ref",
                dict(self.root_ref, path="review-inputs/comparison-roots/x.json"),
            ),
            ("comparison_root_ref", dict(self.root_ref, sha256="0" * 64)),
            (
                "review_target_ref",
                dict(self.binding["review_target_ref"], path="arbitrary/path"),
            ),
            (
                "plan_candidate_ref",
                {
                    "path": ".kapisch/v3/authority/plan-approval-candidates/"
                    + "e" * 64
                    + ".json",
                    "sha256": "e" * 64,
                },
            ),
        ]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                original_path.unlink()
                changed = copy.deepcopy(self.binding)
                changed[field] = value
                wrong = self.external_binding(changed)
                proposal = self.proposal()
                proposal["history"][-1]["evidence"] = [wrong]
                self.assert_refusal(proposal)
                (self.run_root / wrong["path"]).unlink()
                original_path.write_bytes(original)

    def test_canonical_bytes_filename_and_missing_fact_matrix(self):
        path = self.run_root / self.ref["path"]
        data = path.read_bytes()
        for replacement in (
            b"not json",
            data + b" ",
            data.replace(
                b'"protocol_version":3', b'"protocol_version":3,"protocol_version":3'
            ),
        ):
            with self.subTest(replacement=replacement):
                path.write_bytes(replacement)
                self.assert_refusal()
        path.write_bytes(data)
        wrong = path.with_name("0" * 64 + ".json")
        path.rename(wrong)
        self.assert_refusal()
        wrong.unlink()
        self.assert_refusal()
        path.write_bytes(data)
        root = self.run_root / self.root_ref["path"].split("/run-1/")[1]
        root_bytes = root.read_bytes()
        root.unlink()
        self.assert_refusal()
        root.write_bytes(root_bytes + b" ")
        self.assert_refusal()

    def test_duplicate_reservations_across_candidates_fail_closed(self):
        import copy

        second = copy.deepcopy(self.binding)
        second["head"] = "sha1:" + "c" * 40
        extra = self.external_binding(second)
        self.assert_refusal()
        (self.run_root / extra["path"]).unlink()
        root = copy.deepcopy(self.root)
        root["plan_candidate_ref"] = {
            "path": ".kapisch/v3/authority/plan-approval-candidates/"
            + "e" * 64
            + ".json",
            "sha256": "e" * 64,
        }
        second["plan_candidate_ref"] = root["plan_candidate_ref"]
        second["comparison_root_ref"] = self.external_fact(
            root, "review-inputs/comparison-roots/" + "e" * 64 + ".json"
        )
        self.external_binding(second)
        self.assert_refusal()

    def test_creation_plus_binding_and_batched_progression_are_rejected(self):
        from kapisch_core.bundle import canonical_json

        path = self.run_root / "state.json"
        before = path.read_bytes()
        empty = dict(self.state, history=[])
        path.write_bytes(canonical_json(empty))
        self.assert_refusal()
        path.write_bytes(before)
        proposal = self.proposal()
        proposal["history"].append(
            dict(proposal["history"][-1], sequence=2, status="complete")
        )
        self.assert_refusal(proposal)

    def test_prefix_stale_identity_and_evidence_rejections(self):
        import copy

        for field, value in (
            ("role", "researcher"),
            ("stage_kind", "implement"),
            ("scope_digest", "f" * 64),
            ("retry_of_stage_id", "s-" + "2" * 32),
            ("producer", "other"),
        ):
            proposal = self.proposal()
            proposal["history"][-1][field] = value
            self.assert_refusal(proposal)
        proposal = self.proposal()
        proposal["history"][0]["scope_digest"] = "c" * 64
        self.assert_refusal(proposal)
        proposal = self.proposal()
        proposal["revision"] += 1
        self.assert_refusal(proposal)
        proposal = self.proposal()
        proposal["history"][-1]["evidence"] += [copy.deepcopy(self.ref)]
        self.assert_refusal(proposal)
        proposal = self.proposal()
        proposal["history"][-1]["status"] = "complete"
        self.assert_refusal(proposal)

    def test_request_only_and_orphan_dispatch_facts_veto(self):
        from kapisch_core.protocol import persist_request

        operation_id = "op-" + "2" * 32
        packet = {
            "run_id": "run-1",
            "operation_id": operation_id,
            "stage_id": self.first["stage_id"],
            "role": "reviewer",
            "bundle_digest": self.state["bundle_digest"],
            "scope_digest": self.first["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "test"},
        }
        # The live checked-plan consumer remains deliberately unsupported.
        with self.assertRaisesRegex(ValueError, "unsupported-gate"):
            persist_request(self.repo, "run-1", operation_id, packet)
        self.external_fact(packet, f"requests/{operation_id}.json")
        self.assertFalse((self.run_root / "invocations").exists())
        self.assert_refusal()
        (self.run_root / f"requests/{operation_id}.json").unlink()
        for relative in (
            f"request-inputs/{operation_id}/0000.bin",
            f"invocations/{operation_id}/planned.json",
            f"invocations/{operation_id}/dispatch-uncertain.json",
            f"invocations/{operation_id}/observed.json",
            f"invocations/{operation_id}/blocked.json",
            f"invocations/{operation_id}/receipt.json",
            f"invocations/{operation_id}/review-result.json",
            f"invocations/{operation_id}/verification.json",
            f"review-inputs/{operation_id}/pre-dispatch-fingerprint.json",
        ):
            with self.subTest(relative=relative):
                self.external_fact({"stage_id": self.first["stage_id"]}, relative)
                self.assert_refusal()
                path = self.run_root / relative
                path.unlink()
                path.parent.rmdir()

    def test_unreferenced_downstream_artifacts_veto(self):
        for namespace in ("review-targets", "comparison-bases", "scopes"):
            with self.subTest(namespace=namespace):
                relative = f"review-inputs/{namespace}/" + "9" * 64 + ".json"
                self.external_fact(
                    {"run_id": "run-1", "stage_id": self.first["stage_id"]}, relative
                )
                self.assert_refusal()
                (self.run_root / relative).unlink()

    def test_symlinked_or_unreadable_census_fails_closed(self):
        from unittest.mock import patch

        path = self.run_root / self.ref["path"]
        data = path.read_bytes()
        path.unlink()
        external = self.repo / "external.json"
        external.write_bytes(data)
        path.symlink_to(external)
        self.assert_refusal()
        path.unlink()
        path.write_bytes(data)
        with patch(
            "kapisch_core._review_target_records.os.listdir",
            side_effect=PermissionError("unreadable"),
        ):
            self.assert_refusal()

    def test_no_binding_keeps_checked_plan_consumer_unsupported(self):
        from kapisch_core.validation import validate_run

        self.assertEqual(
            [error.code for error in validate_run(self.repo, "run-1")],
            ["unsupported-gate"],
        )

    def test_bound_history_is_independent_of_new_append_vetoes(self):
        from kapisch_core.protocol import load_state, publish_state
        from kapisch_core.validation import validate_run

        self.bind()
        for namespace in ("review-targets", "comparison-bases", "scopes"):
            self.external_fact(
                {"later": "external"}, f"review-inputs/{namespace}/later.json"
            )
        for status in ("complete", "interrupted", "blocked", "failed"):
            with self.subTest(status=status):
                state = self.proposal()
                state["history"].append(
                    dict(state["history"][-1], sequence=2, status=status)
                )
                state["revision"] += 1
                # Restore an exact valid bound prefix to test each existing terminal edge.
                from kapisch_core.bundle import canonical_json

                (self.run_root / "state.json").write_bytes(
                    canonical_json(self.proposal())
                )
                publish_state(self.repo, "run-1", state, state["revision"] - 1)
                before = self.authority_bytes()
                self.assertEqual(load_state(self.repo, "run-1"), state)
                self.assertEqual(validate_run(self.repo, "run-1"), [])
                self.assertEqual(self.authority_bytes(), before)
                self.assertEqual(
                    validate_run(self.repo, "run-1", "dispatch")[0].code,
                    "unsupported-gate",
                )

    def test_bound_chain_cannot_be_replaced_and_tampering_blocks_load(self):
        from kapisch_core.protocol import load_state, publish_state

        self.bind()
        state = self.proposal()
        state["revision"] += 1
        del state["approved_plan"]
        before = self.authority_bytes()
        with self.assertRaises(ValueError):
            publish_state(self.repo, "run-1", state, state["revision"] - 1)
        self.assertEqual(self.authority_bytes(), before)
        path = self.run_root / self.ref["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            load_state(self.repo, "run-1")

    def cold_process(self, source):
        import os
        import subprocess
        import sys

        return subprocess.run(
            [sys.executable, "-c", source, str(self.repo)],
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_fresh_process_missing_binding_recovery_and_noop(self):
        source = """
import copy, hashlib, json, sys
from pathlib import Path
from kapisch_core.protocol import load_state, publish_state
from kapisch_core.validation import validate_run
repo = Path(sys.argv[1])
state = load_state(repo, 'run-1')
if len(state['history']) == 1:
    path, = (repo / '.kapisch/v3/runs/run-1/review-inputs/review-target-bindings').iterdir()
    data = path.read_bytes()
    reservation = json.loads(data)
    assert reservation['stage_id'] == state['history'][0]['stage_id']
    row = copy.deepcopy(state['history'][0])
    row['sequence'] = len(state['history'])
    row['evidence'].append({'kind': 'review-target-binding/1', 'path': 'review-inputs/review-target-bindings/' + path.name, 'sha256': hashlib.sha256(data).hexdigest()})
    state['history'].append(row)
    revision = state['revision']
    state['revision'] += 1
    publish_state(repo, 'run-1', state, revision)
assert len(load_state(repo, 'run-1')['history']) == 2
assert validate_run(repo, 'run-1') == []
"""
        first = self.cold_process(source)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.authority_bytes()
        second = self.cold_process(source)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.authority_bytes(), before)

    def test_two_independent_binders_share_revision_and_serialize(self):
        import json
        import os
        import subprocess
        import sys

        from kapisch_core.protocol import load_state

        source = """
import json, sys
from pathlib import Path
from kapisch_core.protocol import ConcurrentModificationError, publish_state
proposal = json.loads(sys.stdin.readline())
print('ready', flush=True)
sys.stdin.readline()
try:
    publish_state(Path(sys.argv[1]), 'run-1', proposal, proposal['revision'] - 1)
    print('bound', flush=True)
except ConcurrentModificationError:
    print('stale', flush=True)
"""
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", source, str(self.repo)],
                env=os.environ.copy(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        try:
            for process in processes:
                assert process.stdin is not None and process.stdout is not None
                process.stdin.write(json.dumps(self.proposal()) + "\n")
                process.stdin.flush()
                self.assertEqual(process.stdout.readline().strip(), "ready")
            for process in processes:
                assert process.stdin is not None
                process.stdin.write("go\n")
                process.stdin.flush()
            outputs = [process.communicate(timeout=20) for process in processes]
            self.assertEqual(
                sorted(output[0].strip() for output in outputs),
                ["bound", "stale"],
                outputs,
            )
            self.assertEqual(len(load_state(self.repo, "run-1")["history"]), 2)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)

    def test_state_write_and_acknowledgement_faults_recover_from_bytes(self):
        from unittest.mock import patch

        from kapisch_core import _state
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import load_state

        old = canonical_json(self.state)
        binding_bytes = (self.run_root / self.ref["path"]).read_bytes()
        real_write = _state._write_atomic
        for after in (False, True):
            with self.subTest(after_replace=after):
                (self.run_root / "state.json").write_bytes(old)

                def uncertain_write(*args, **kwargs):
                    if after:
                        real_write(*args, **kwargs)
                    raise OSError("injected acknowledgement loss")

                with patch.object(_state, "_write_atomic", side_effect=uncertain_write):
                    with self.assertRaisesRegex(OSError, "acknowledgement"):
                        self.bind()
                recovered = load_state(self.repo, "run-1")
                self.assertEqual(len(recovered["history"]), 2 if after else 1)
                if not after:
                    self.bind()
                before = self.authority_bytes()
                load_state(self.repo, "run-1")
                self.assertEqual(self.authority_bytes(), before)
                self.assertEqual(
                    (self.run_root / self.ref["path"]).read_bytes(), binding_bytes
                )

    def test_file_and_directory_fsync_failure_windows(self):
        import os
        from unittest.mock import patch

        from kapisch_core import _state, storage
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import load_state

        original = _state._write_atomic
        real_fsync = os.fsync
        for failure_at in (1, 2, 3):
            with self.subTest(failure_at=failure_at):
                (self.run_root / "state.json").write_bytes(canonical_json(self.state))

                def write_with_fault(*args, **kwargs):
                    count = 0

                    def fsync(descriptor):
                        nonlocal count
                        count += 1
                        if count == failure_at:
                            raise OSError("injected fsync failure")
                        return real_fsync(descriptor)

                    with patch.object(storage.os, "fsync", side_effect=fsync):
                        original(*args, **kwargs)

                with patch.object(
                    _state, "_write_atomic", side_effect=write_with_fault
                ):
                    with self.assertRaisesRegex(OSError, "fsync"):
                        self.bind()
                recovered = load_state(self.repo, "run-1")
                self.assertEqual(len(recovered["history"]), 1 if failure_at == 1 else 2)
                if len(recovered["history"]) == 1:
                    self.bind()
                self.assertEqual(len(load_state(self.repo, "run-1")["history"]), 2)

    def follow_on(self, kind="review", predecessor_status="complete", retry=False):
        import copy

        from kapisch_core.protocol import load_state, publish_state

        state = copy.deepcopy(self.state)
        state["history"].append(dict(self.first, sequence=1, status=predecessor_status))
        state["revision"] += 1
        publish_state(self.repo, "run-1", state, state["revision"] - 1)
        first = dict(self.first, stage_id="s-" + "3" * 32, stage_kind=kind, sequence=2)
        if retry:
            first["retry_of_stage_id"] = self.first["stage_id"]
        state["history"].append(first)
        state["revision"] += 1
        publish_state(self.repo, "run-1", state, state["revision"] - 1)
        self.state = load_state(self.repo, "run-1")
        self.first = first
        self.binding["stage_id"] = first["stage_id"]
        self.binding["purpose"] = "final" if kind == "final" else "iteration"
        if kind == "final":
            self.binding["comparison_root"]["must_differ_from_head"] = True
        self.ref = self.external_binding(self.binding)

    def test_final_retry_and_corrective_follow_on_preserve_root(self):
        from kapisch_core.protocol import load_state

        self.follow_on(kind="final")
        root_bytes = (
            self.run_root / self.root_ref["path"].split("/run-1/")[1]
        ).read_bytes()
        self.bind()
        self.assertEqual(load_state(self.repo, "run-1"), self.proposal())
        self.assertEqual(
            (self.run_root / self.root_ref["path"].split("/run-1/")[1]).read_bytes(),
            root_bytes,
        )

    def test_eligible_retry_preserves_creation_and_retry_binding(self):
        from kapisch_core.protocol import load_state

        self.follow_on(predecessor_status="failed", retry=True)
        self.bind()
        self.assertEqual(
            load_state(self.repo, "run-1")["history"][-1]["retry_of_stage_id"],
            "s-" + "1" * 32,
        )

    def test_corrective_follow_on_has_no_implicit_retry(self):
        from kapisch_core.protocol import load_state

        self.follow_on()
        self.bind()
        self.assertNotIn(
            "retry_of_stage_id", load_state(self.repo, "run-1")["history"][-1]
        )

    def test_completed_predecessor_does_not_become_retry_eligible(self):
        with self.assertRaisesRegex(ValueError, "predecessor"):
            self.follow_on(predecessor_status="complete", retry=True)

    def test_final_cannot_weaken_strict_root_or_replace_previous_root(self):
        self.follow_on(kind="final")
        path = self.run_root / self.ref["path"]
        path.unlink()
        self.binding["comparison_root"]["must_differ_from_head"] = False
        self.ref = self.external_binding(self.binding)
        self.assert_refusal()
        (self.run_root / self.ref["path"]).unlink()
        self.binding["comparison_root"]["must_differ_from_head"] = True
        self.binding["head"] = self.binding["base"]
        self.ref = self.external_binding(self.binding)
        self.assert_refusal()
        (self.run_root / self.ref["path"]).unlink()
        self.binding["head"] = "sha1:" + "b" * 40
        self.root["anchor"] = "sha1:" + "e" * 40
        root_path = self.root_ref["path"].split("/run-1/")[1]
        self.binding["comparison_root_ref"] = self.external_fact(self.root, root_path)
        self.binding["comparison_root"]["anchor"] = self.root["anchor"]
        self.binding["base"] = self.root["anchor"]
        self.ref = self.external_binding(self.binding)
        # Earlier reservation still pins the old root; a new stage cannot replace it.
        self.assert_refusal()

    def test_lost_binding_cannot_be_repaired_after_progression(self):
        from kapisch_core.protocol import publish_state

        state = dict(
            self.state,
            history=self.state["history"]
            + [dict(self.first, sequence=1, status="interrupted")],
            revision=self.state["revision"] + 1,
        )
        publish_state(self.repo, "run-1", state, self.state["revision"])
        self.state = state
        self.assert_refusal()

    def test_internal_publication_cannot_introduce_binding(self):
        from kapisch_core._locking import _locked
        from kapisch_core._state import _publish_state_locked

        before = self.authority_bytes()
        with (
            _locked(self.repo, "run-1"),
            self.assertRaisesRegex(ValueError, "checked Stage 4"),
        ):
            _publish_state_locked(
                self.repo, "run-1", self.proposal(), self.state["revision"]
            )
        self.assertEqual(self.authority_bytes(), before)

    def test_current_scope_does_not_reauthorize_historical_binding(self):
        from kapisch_core.advisory import propose_scope
        from kapisch_core.protocol import load_state, publish_state
        from kapisch_core.validation import validate_run

        self.bind()
        scope = propose_scope(
            self.repo,
            "run-1",
            "scope-2",
            "changed current requirements",
            {"mode": "all"},
        )
        state = self.proposal()
        state["scope_ref"] = {
            "origin_run_id": scope.origin_run_id,
            "scope_id": scope.scope_id,
            "sha256": scope.sha256,
        }
        state["revision"] += 1
        publish_state(self.repo, "run-1", state, state["revision"] - 1)
        self.assertEqual(load_state(self.repo, "run-1"), state)
        self.assertEqual(validate_run(self.repo, "run-1"), [])

    def test_historical_dispatch_consumer_remains_an_external_activation_gate(self):
        from kapisch_core.bundle import canonical_json
        from kapisch_core.validation import validate_run

        self.bind()
        state = self.proposal()
        state["history"].append(
            dict(state["history"][-1], sequence=2, status="dispatch-uncertain")
        )
        state["revision"] += 1
        # No operation producer may be fabricated by the binding consumer.
        (self.run_root / "state.json").write_bytes(canonical_json(state))
        errors = validate_run(self.repo, "run-1")
        self.assertTrue(errors)
        self.assertIn("invocation", errors[0].message)

    def test_malformed_unreferenced_root_cannot_establish_complete_census(self):
        self.external_fact(
            {"malformed": "root"},
            "review-inputs/comparison-roots/" + "f" * 64 + ".json",
        )
        self.assert_refusal()

    def test_retained_capability_combinations_are_exact(self):
        import json
        from pathlib import Path

        from kapisch_core.bundle import canonical_json

        original = json.loads(
            (
                Path(__file__).resolve().parents[2] / "core/dist/core-bundle.json"
            ).read_bytes()
        )
        for review, stage in (
            (False, False),
            (False, True),
            (True, False),
            (True, True),
        ):
            with self.subTest(review=review, stage=stage):
                payload = dict(original)
                if not review:
                    payload.pop("review_contract")
                    payload.pop("review_schema_variant")
                if not stage:
                    payload.pop("stage_evidence_contract")
                fixture = StageEvidenceTests()
                fixture.bundle_data = canonical_json(payload)
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                if review and stage:
                    fixture.bind()
                else:
                    fixture.assert_refusal()

    def test_checked_plan_candidate_approval_and_workflow_mismatches(self):
        import copy

        from kapisch_core.bundle import canonical_json

        original = canonical_json(self.state)
        path = self.run_root / "state.json"
        mutations = [
            ("workflow", "review"),
            ("workflow", "advisory"),
            ("workflow", "milestone"),
            ("approved_plan", None),
            ("plan_candidate_ref", None),
            ("approved_plan", dict(self.state["approved_plan"], plan_id="other-plan")),
            ("approved_plan", dict(self.state["approved_plan"], plan_sha256="0" * 64)),
        ]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                previous = copy.deepcopy(self.state)
                proposal = self.proposal()
                if value is None:
                    del previous[field]
                    del proposal[field]
                else:
                    previous[field] = value
                    proposal[field] = value
                path.write_bytes(canonical_json(previous))
                self.assert_refusal(proposal)
                path.write_bytes(original)

    def test_valid_unrelated_request_does_not_veto_other_stage(self):
        from kapisch_core.protocol import load_state, persist_request, publish_state

        plan = self.state.pop("approved_plan")
        self.state["revision"] += 1
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        operation_id = "op-" + "4" * 32
        packet = {
            "run_id": "run-1",
            "operation_id": operation_id,
            "stage_id": self.first["stage_id"],
            "role": "reviewer",
            "bundle_digest": self.state["bundle_digest"],
            "scope_digest": self.first["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "test"},
        }
        persist_request(self.repo, "run-1", operation_id, packet)
        self.state["approved_plan"] = plan
        self.state["revision"] += 1
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        self.follow_on(predecessor_status="interrupted")
        self.bind()
        self.assertEqual(load_state(self.repo, "run-1"), self.proposal())

    def test_operation_review_inputs_veto_known_unrelated_requests(self):
        from kapisch_core.protocol import persist_request, publish_state

        for filename, contents in (
            ("pre-dispatch-fingerprint.json", b"not json"),
            ("unknown-input.json", b"{}"),
        ):
            with self.subTest(filename=filename):
                fixture = StageEvidenceTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                plan = fixture.state.pop("approved_plan")
                fixture.state["revision"] += 1
                publish_state(
                    fixture.repo,
                    "run-1",
                    fixture.state,
                    fixture.state["revision"] - 1,
                )
                operation_id = "op-" + "4" * 32
                packet = {
                    "run_id": "run-1",
                    "operation_id": operation_id,
                    "stage_id": fixture.first["stage_id"],
                    "role": "reviewer",
                    "bundle_digest": fixture.state["bundle_digest"],
                    "scope_digest": fixture.first["scope_digest"],
                    "adapter_binding": {
                        "adapter_id": "fake",
                        "lookup_context": "test",
                    },
                }
                persist_request(fixture.repo, "run-1", operation_id, packet)
                fixture.state["approved_plan"] = plan
                fixture.state["revision"] += 1
                publish_state(
                    fixture.repo,
                    "run-1",
                    fixture.state,
                    fixture.state["revision"] - 1,
                )
                fixture.follow_on(predecessor_status="interrupted")
                operation_input = (
                    fixture.run_root / "review-inputs" / operation_id / filename
                )
                operation_input.parent.mkdir(parents=True)
                operation_input.write_bytes(contents)
                before = (fixture.run_root / "state.json").read_bytes()

                with self.assertRaisesRegex(ValueError, "operation review input"):
                    fixture.bind()
                self.assertEqual((fixture.run_root / "state.json").read_bytes(), before)

    def test_malformed_unrelated_request_ownership_vetoes_binding(self):
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import persist_request, publish_state

        mutations = (
            ("node_id", "n-" + "a" * 32),
            ("request_digest", "b" * 64),
            ("graph", None),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                fixture = StageEvidenceTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                plan = fixture.state.pop("approved_plan")
                fixture.state["revision"] += 1
                publish_state(
                    fixture.repo,
                    "run-1",
                    fixture.state,
                    fixture.state["revision"] - 1,
                )
                operation_id = "op-" + "4" * 32
                packet = {
                    "run_id": "run-1",
                    "operation_id": operation_id,
                    "stage_id": fixture.first["stage_id"],
                    "role": "reviewer",
                    "bundle_digest": fixture.state["bundle_digest"],
                    "scope_digest": fixture.first["scope_digest"],
                    "adapter_binding": {
                        "adapter_id": "fake",
                        "lookup_context": "test",
                    },
                }
                persist_request(fixture.repo, "run-1", operation_id, packet)
                if field == "graph":
                    graph_ref = fixture.external_fact(
                        {"graph": "existing"}, "graph.json"
                    )
                    packet["graph"] = {
                        "path": "graph.json",
                        "sha256": graph_ref["sha256"],
                    }
                else:
                    packet[field] = value
                request_path = fixture.run_root / "requests" / f"{operation_id}.json"
                request_path.write_bytes(canonical_json(packet))
                fixture.state["approved_plan"] = plan
                fixture.state["revision"] += 1
                publish_state(
                    fixture.repo,
                    "run-1",
                    fixture.state,
                    fixture.state["revision"] - 1,
                )
                fixture.follow_on(predecessor_status="interrupted")
                before = fixture.authority_bytes()
                message = (
                    "graph references are forbidden in graph-free request"
                    if field == "graph"
                    else "request node binding or digest shape is invalid"
                )
                with self.assertRaisesRegex(ValueError, message):
                    fixture.bind()
                self.assertEqual(fixture.authority_bytes(), before)

    def _persist_unrelated_operation(
        self, operation_id, planned_template=None, observed=False
    ):
        import hashlib

        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import persist_request, reserve_operation

        packet = {
            "run_id": "run-1",
            "operation_id": operation_id,
            "stage_id": self.first["stage_id"],
            "role": "reviewer",
            "bundle_digest": self.state["bundle_digest"],
            "scope_digest": self.first["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "test"},
        }
        request_path, request_digest = persist_request(
            self.repo, "run-1", operation_id, packet
        )
        if planned_template is None:
            planned = reserve_operation(
                self.repo,
                "run-1",
                operation_id,
                self.first["stage_id"],
                "reviewer",
                {"path": request_path, "sha256": request_digest},
                packet["adapter_binding"],
            )
        else:
            planned = dict(
                planned_template,
                operation_id=operation_id,
                request_digest=request_digest,
                request={"path": request_path, "sha256": request_digest},
            )
            operation_root = self.run_root / "invocations" / operation_id
            operation_root.mkdir(parents=True)
            (operation_root / "planned.json").write_bytes(canonical_json(planned))
        planned_bytes = canonical_json(planned)
        refs = [
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {
                "kind": "protocol",
                "path": f"invocations/{operation_id}/planned.json",
                "sha256": hashlib.sha256(planned_bytes).hexdigest(),
            },
        ]
        if observed:
            observed_bytes = canonical_json({**planned, "status": "observed"})
            observed_path = (
                self.run_root / "invocations" / operation_id / "observed.json"
            )
            observed_path.write_bytes(observed_bytes)
            refs.append(
                {
                    "kind": "protocol",
                    "path": f"invocations/{operation_id}/observed.json",
                    "sha256": hashlib.sha256(observed_bytes).hexdigest(),
                }
            )
        return refs, planned

    def _prepare_unrelated_operations(self, operation_ids, observed_first=False):
        from kapisch_core.protocol import load_state, publish_state

        plan = self.state.pop("approved_plan")
        self.state["revision"] += 1
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        evidence = []
        planned_template = None
        for index, operation_id in enumerate(operation_ids):
            refs, planned = self._persist_unrelated_operation(
                operation_id, planned_template, observed_first and index == 0
            )
            evidence.extend(refs)
            if planned_template is None:
                planned_template = planned
        self.state["approved_plan"] = plan
        self.state["revision"] += 1
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        completed = dict(self.first, sequence=1, status="complete", evidence=evidence)
        self.state["history"].append(completed)
        self.state["revision"] += 1
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        self.state = load_state(self.repo, "run-1")
        next_stage = dict(
            creation(),
            stage_id="s-" + "3" * 32,
            sequence=len(self.state["history"]),
            scope_digest=self.first["scope_digest"],
        )
        self.state["history"].append(next_stage)
        self.state["revision"] += 1
        publish_state(self.repo, "run-1", self.state, self.state["revision"] - 1)
        self.state = load_state(self.repo, "run-1")
        self.first = self.state["history"][-1]
        self.binding["stage_id"] = self.first["stage_id"]
        self.ref = self.external_binding(self.binding)

    def test_bound_history_loads_with_unrelated_historical_operation(self):
        from kapisch_core.protocol import load_state
        from kapisch_core.validation import validate_run

        self._prepare_unrelated_operations(("op-" + "4" * 32,))
        self.bind()
        before = self.authority_bytes()
        self.assertEqual(load_state(self.repo, "run-1"), self.proposal())
        self.assertEqual(validate_run(self.repo, "run-1"), [])
        self.assertEqual(self.authority_bytes(), before)
        result = self.cold_process("""
import sys
from pathlib import Path
from kapisch_core.protocol import load_state
from kapisch_core.validation import validate_run
repo = Path(sys.argv[1])
assert len(load_state(repo, 'run-1')['history']) == 4
assert validate_run(repo, 'run-1') == []
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.authority_bytes(), before)

    def test_unrelated_attempt_cannot_own_multiple_operations(self):
        self._prepare_unrelated_operations(("op-" + "4" * 32, "op-" + "5" * 32))
        before = self.authority_bytes()
        with self.assertRaisesRegex(
            ValueError, "attempt owns multiple operation reservations"
        ):
            self.bind()
        self.assertEqual(self.authority_bytes(), before)

    def test_unrelated_observation_requires_uncertainty_producer(self):
        self._prepare_unrelated_operations(("op-" + "4" * 32,), observed_first=True)
        before = self.authority_bytes()
        with self.assertRaisesRegex(
            ValueError, "observed fact precedes its owning uncertainty producer"
        ):
            self.bind()
        self.assertEqual(self.authority_bytes(), before)

    def test_repository_and_run_locks_are_held_through_commit(self):
        import fcntl
        import json
        import subprocess
        import sys

        source = """
import json, sys
from pathlib import Path
from unittest.mock import patch
from kapisch_core import _stage_evidence
proposal = json.loads(sys.stdin.readline())
commit = _stage_evidence._commit_state_locked
def paused(*args):
    print('checked', flush=True)
    sys.stdin.readline()
    return commit(*args)
with patch.object(_stage_evidence, '_commit_state_locked', side_effect=paused):
    _stage_evidence.publish_state(Path(sys.argv[1]), 'run-1', proposal, proposal['revision'] - 1)
"""
        process = subprocess.Popen(
            [sys.executable, "-c", source, str(self.repo)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(json.dumps(self.proposal()) + "\n")
            process.stdin.flush()
            self.assertEqual(process.stdout.readline().strip(), "checked")
            for name in ("repository.lock", "run-run-1.lock"):
                with (self.repo / ".kapisch/v3/locks" / name).open("rb") as lock:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            process.stdin.write("commit\n")
            process.stdin.flush()
            _, errors = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, errors)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)

    def test_initial_state_cannot_publish_creation_and_binding_together(self):
        from kapisch_core.protocol import publish_state

        proposal = self.proposal()
        proposal["revision"] = 0
        (self.run_root / "state.json").unlink()
        before = self.authority_bytes()
        with self.assertRaisesRegex(ValueError, "separately durable"):
            publish_state(self.repo, "run-1", proposal, -1)
        self.assertEqual(self.authority_bytes(), before)

    def test_binding_retains_exact_nonempty_creation_evidence_prefix(self):
        from kapisch_core.bundle import canonical_json
        from kapisch_core.protocol import load_state

        ref = self.external_fact({"assignment": "before creation"}, "assignment.json")
        evidence = dict(ref, path="assignment.json", kind="assignment")
        self.first["evidence"] = [evidence]
        (self.run_root / "state.json").write_bytes(canonical_json(self.state))
        proposed = self.proposal()
        # Exactly prefix+locator succeeds, while reordered/duplicated old evidence does not.
        proposed["history"][-1]["evidence"] = [self.ref, evidence]
        self.assert_refusal(proposed)
        proposed["history"][-1]["evidence"] = [evidence, evidence, self.ref]
        self.assert_refusal(proposed)
        proposed["history"][-1]["evidence"] = [dict(evidence, kind="changed"), self.ref]
        self.assert_refusal(proposed)
        from kapisch_core.protocol import publish_state

        proposed["history"][-1]["evidence"] = [evidence, self.ref]
        publish_state(self.repo, "run-1", proposed, self.state["revision"])
        self.assertEqual(load_state(self.repo, "run-1"), proposed)

    def test_sha256_object_format_and_explicit_empty_iteration(self):
        from kapisch_core.protocol import load_state

        (self.run_root / self.ref["path"]).unlink()
        self.root["object_format"] = "sha256"
        self.root["anchor"] = "sha256:" + "a" * 64
        self.binding["comparison_root_ref"] = self.external_fact(
            self.root, self.root_ref["path"].split("/run-1/")[1]
        )
        self.binding["object_format"] = "sha256"
        self.binding["comparison_root"]["anchor"] = self.root["anchor"]
        self.binding["base"] = self.root["anchor"]
        self.binding["head"] = self.root["anchor"]
        self.ref = self.external_binding(self.binding)
        self.bind()
        self.assertEqual(load_state(self.repo, "run-1"), self.proposal())

    def test_missing_approval_evidence_is_not_repaired_during_load(self):
        from kapisch_core._gate_approval import load_gate_approval
        from kapisch_core.protocol import load_state

        self.bind()
        record = load_gate_approval(
            self.repo, self.state["approved_plan"]["gate_approval_ref"]
        )
        authority = record["human_authority"]
        evidence = self.repo / authority["path"]
        evidence.unlink()
        before = self.authority_bytes()
        with self.assertRaises(ValueError):
            load_state(self.repo, "run-1")
        self.assertEqual(self.authority_bytes(), before)

    def test_legacy_history_unchanged_but_cannot_consume_binding(self):
        import hashlib
        from pathlib import Path

        from kapisch_core.protocol import load_state, publish_state
        from kapisch_core.storage import store_bundle
        from kapisch_core.validation import validate_run

        bundle = (
            Path(__file__).resolve().parents[2]
            / "tests/conformance/fixtures/v3/legacy-bundle.json"
        )
        data = bundle.read_bytes()
        digest = store_bundle(self.repo, data)
        state = {
            "protocol_version": 3,
            "run_id": "legacy-run",
            "bundle_digest": digest,
            "workflow": "task",
            "revision": 0,
            "identity_contract": "stage-attempt/1",
            "history": [creation()],
        }
        publish_state(self.repo, "legacy-run", state, -1)
        self.assertEqual(load_state(self.repo, "legacy-run"), state)
        self.assertEqual(validate_run(self.repo, "legacy-run"), [])
        run = self.repo / ".kapisch/v3/runs/legacy-run"
        reservation = (self.run_root / self.ref["path"]).read_bytes()
        ref = locator(hashlib.sha256(reservation).hexdigest())
        dest = run / ref["path"]
        dest.parent.mkdir(parents=True)
        dest.write_bytes(reservation)
        before = self.authority_bytes()
        state["revision"] += 1
        state["history"].append(dict(state["history"][0], sequence=1, evidence=[ref]))
        with self.assertRaisesRegex(ValueError, "retained bundle"):
            publish_state(self.repo, "legacy-run", state, 0)
        self.assertEqual(self.authority_bytes(), before)
        self.assertEqual(hashlib.sha256(data).hexdigest(), digest)

    def test_external_locked_fixture_reservation_crash_and_uniqueness(self):
        from kapisch_core.protocol import load_state

        (self.run_root / self.ref["path"]).unlink()
        source = """
import hashlib, json, os, sys
from pathlib import Path
from kapisch_core._locking import _locked
from kapisch_core.storage import _atomic_write_at, _close, _open_dir, _read_file, _run_dir
from kapisch_core.bundle import canonical_json
repo = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
data = canonical_json(payload)
with _locked(repo, 'run-1'):
    run, fds = _run_dir(repo, 'run-1', create=False)
    try:
        review = _open_dir(run, 'review-inputs')
        fds.append(review)
        bindings = _open_dir(review, 'review-target-bindings')
        fds.append(bindings)
        for name in os.listdir(bindings):
            fact = json.loads(_read_file(bindings, name))
            if fact['stage_id'] == payload['stage_id']:
                print('occupied', flush=True)
                sys.exit(0)
        _atomic_write_at(bindings, hashlib.sha256(data).hexdigest() + '.json', data, replace=False)
        print('durable-reservation', flush=True)
        # Test-only external producer dies before a Stage 4 publication.
        os._exit(0)
    finally:
        _close(fds)
"""
        import json
        import subprocess
        import sys

        first = subprocess.run(
            [sys.executable, "-c", source, str(self.repo), json.dumps(self.binding)],
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.strip(), "durable-reservation")
        self.assertEqual(len(load_state(self.repo, "run-1")["history"]), 1)
        different = dict(self.binding, head="sha1:" + "e" * 40)
        second = subprocess.run(
            [sys.executable, "-c", source, str(self.repo), json.dumps(different)],
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout.strip(), "occupied")
        self.bind()
        self.assertEqual(load_state(self.repo, "run-1"), self.proposal())
