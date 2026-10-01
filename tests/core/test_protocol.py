from __future__ import annotations

import hashlib
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))


def _stage(status: str, sequence: int = 0) -> dict:
    return {
        "stage_id": "s-00000000000000000000000000000001",
        "stage_kind": "implement",
        "sequence": sequence,
        "role": "implementer",
        "status": status,
        "producer": "controller",
        "evidence": [],
        "scope_digest": "0" * 64,
    }


def _publish(repo: str, state: dict, barrier, results) -> None:
    try:
        from kapisch_core.protocol import publish_state
        barrier.wait()
        publish_state(Path(repo), state["run_id"], state, expected_revision=0)
    except Exception as error:
        results.put(type(error).__name__)
    else:
        results.put("published")


def _reserve(repo: str, run_id: str, operation_id: str, request, barrier, results) -> None:
    try:
        from kapisch_core.protocol import reserve_operation
        barrier.wait()
        reserve_operation(
            Path(repo), run_id, operation_id, "s-00000000000000000000000000000001", "implementer",
            request, {"adapter_id": "fake", "lookup_context": "ctx"},
        )
    except Exception as error:
        results.put(type(error).__name__)
    else:
        results.put("reserved")


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        from kapisch_core.storage import store_bundle

        self.bundle = (ROOT / "core/dist/core-bundle.json").read_bytes()
        self.digest = hashlib.sha256(self.bundle).hexdigest()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        store_bundle(self.repo, self.bundle)

    def _state(self, run_id: str, revision: int = 0, history=None) -> dict:
        return {
            "protocol_version": 3,
            "run_id": run_id,
            "bundle_digest": self.digest,
            "workflow": "task",
            "revision": revision,
            "history": [] if history is None else history,
            "identity_contract": "stage-attempt/1",
        }

    def _begin(self, run_id: str, operation_id: str):
        from kapisch_core import protocol

        stage = _stage("planned")
        state = self._state(run_id, history=[stage])
        protocol.publish_state(self.repo, run_id, state, expected_revision=-1)
        packet = {
            "run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
            "role": "implementer", "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
        }
        path, digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        return protocol, state, stage, packet, path, digest

    def _milestone_operation(self, run_id: str, operation_id: str):
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        initial = self._state(run_id)
        initial["workflow"] = "milestone"
        protocol.publish_state(self.repo, run_id, initial, -1)
        graph_bytes = canonical_json({"plan_id": "plan-1", "nodes": []})
        plan_bytes = canonical_json({"plan_id": "plan-1", "approved": True})
        graph_path = self.repo / ".kapisch/v3/runs" / run_id / "graphs/plan-1.json"
        plan_path = self.repo / ".kapisch/v3/runs" / run_id / "plans/plan-1.json"
        graph_path.parent.mkdir()
        plan_path.parent.mkdir()
        graph_path.write_bytes(graph_bytes)
        plan_path.write_bytes(plan_bytes)
        graph = {"path": "graphs/plan-1.json", "sha256": hashlib.sha256(graph_bytes).hexdigest()}
        approved_plan = {"plan_id": "plan-1", "path": "plans/plan-1.json",
                         "sha256": hashlib.sha256(plan_bytes).hexdigest()}
        stage = {**_stage("planned"), "node_id": "n-00000000000000000000000000000001"}
        state = {**initial, "revision": 1, "history": [stage], "graph": graph, "approved_plan": approved_plan}
        protocol.publish_state(self.repo, run_id, state, 0)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "node_id": stage["node_id"], "role": stage["role"], "bundle_digest": self.digest,
                  "scope_digest": stage["scope_digest"], "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}}
        return protocol, state, stage, packet

    def test_milestone_request_binds_exact_graph_and_approved_plan(self) -> None:
        operation_id = "op-00000000000000000000000000000015"
        run_id = "run-missing-graph-binding"
        protocol, state, stage, packet = self._milestone_operation(run_id, operation_id)
        with self.assertRaisesRegex(ValueError, "approved graph and plan binding"):
            protocol.persist_request(self.repo, run_id, operation_id, packet)
        request_path = self.repo / ".kapisch/v3/runs" / run_id / "requests" / f"{operation_id}.json"
        self.assertFalse(request_path.exists())

        packet["graph"] = {"path": "graphs/other.json", "sha256": state["graph"]["sha256"]}
        packet["approved_plan"] = state["approved_plan"]
        with self.assertRaisesRegex(ValueError, "approved graph and plan binding"):
            protocol.persist_request(self.repo, run_id, operation_id, packet)

        packet["graph"] = state["graph"]
        packet["approved_plan"] = {**state["approved_plan"], "plan_id": "plan-2"}
        with self.assertRaisesRegex(ValueError, "approved graph and plan binding"):
            protocol.persist_request(self.repo, run_id, operation_id, packet)

        packet["approved_plan"] = state["approved_plan"]
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        graph_path = self.repo / ".kapisch/v3/runs" / run_id / state["graph"]["path"]
        graph_path.write_bytes(b"changed graph")
        with self.assertRaisesRegex(ValueError, "request input evidence changed"):
            protocol.reserve_operation(
                self.repo, run_id, operation_id, stage["stage_id"], "implementer",
                {"path": request_path, "sha256": request_digest}, packet["adapter_binding"],
            )
        self.assertFalse((self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json").exists())

    def test_request_publication_serializes_with_run_state_writer(self) -> None:
        import threading
        from unittest.mock import patch
        from kapisch_core import protocol

        run_id = "run-step-one-lock"
        operation_id = "op-00000000000000000000000000000010"
        initial = self._state(run_id, history=[_stage("planned")])
        protocol.publish_state(self.repo, run_id, initial, -1)
        packet = {"run_id": run_id, "operation_id": operation_id,
                  "stage_id": "s-00000000000000000000000000000001", "role": "implementer",
                  "bundle_digest": self.digest, "scope_digest": initial["history"][0]["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}}
        entered, release, state_written = threading.Event(), threading.Event(), threading.Event()
        original = protocol._publish_immutable
        errors: list[BaseException] = []

        def pause_request(directory, name, data):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test did not release request publisher")
            original(directory, name, data)

        def persist():
            try:
                protocol.persist_request(self.repo, run_id, operation_id, packet)
            except BaseException as error:
                errors.append(error)

        changed = dict(initial)
        changed["revision"] = 1
        changed["history"] = [*initial["history"], {**initial["history"][0], "sequence": 1, "status": "failed"}]

        def publish_state():
            try:
                protocol.publish_state(self.repo, run_id, changed, 0)
            except BaseException as error:
                errors.append(error)
            finally:
                state_written.set()

        with patch.object(protocol, "_publish_immutable", side_effect=pause_request):
            request_thread = threading.Thread(target=persist)
            request_thread.start()
            self.assertTrue(entered.wait(5))
            state_thread = threading.Thread(target=publish_state)
            state_thread.start()
            try:
                self.assertFalse(state_written.wait(0.1), "state writer passed request publication")
            finally:
                release.set()
                request_thread.join(5)
                state_thread.join(5)
        self.assertFalse(request_thread.is_alive())
        self.assertFalse(state_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(protocol.load_state(self.repo, run_id)["revision"], 1)

    def test_step_one_failure_before_publication_leaves_no_request(self) -> None:
        from unittest.mock import patch
        from kapisch_core import protocol

        run_id = "run-request-before"
        operation_id = "op-00000000000000000000000000000007"
        protocol.publish_state(self.repo, run_id, self._state(run_id, history=[_stage("planned")]), -1)
        request_path = self.repo / ".kapisch/v3/runs" / run_id / "requests" / f"{operation_id}.json"
        with patch.object(protocol, "_publish_immutable", side_effect=OSError("request write failed")):
            with self.assertRaisesRegex(OSError, "request write failed"):
                protocol.persist_request(
                    self.repo, run_id, operation_id,
                    {"run_id": run_id, "operation_id": operation_id,
                     "stage_id": "s-00000000000000000000000000000001", "role": "implementer",
                     "bundle_digest": self.digest, "scope_digest": "0" * 64,
                     "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}},
                )
        self.assertFalse(request_path.exists())
        self.assertFalse((self.repo / ".kapisch/v3/runs" / run_id / "invocations").exists())

    def test_step_two_failure_before_publication_creates_no_reservation(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000008"
        protocol, _, stage, packet, path, digest = self._begin("run-reservation-before", operation_id)
        args = (self.repo, "run-reservation-before", operation_id, stage["stage_id"], "implementer",
                {"path": path, "sha256": digest}, packet["adapter_binding"])
        with patch.object(protocol, "_publish_immutable", side_effect=OSError("reservation write failed")):
            with self.assertRaisesRegex(OSError, "reservation write failed"):
                protocol.reserve_operation(*args)
        planned = self.repo / ".kapisch/v3/runs/run-reservation-before/invocations" / operation_id / "planned.json"
        self.assertFalse(planned.exists())
        self.assertEqual(protocol.load_state(self.repo, "run-reservation-before")["revision"], 0)

    def test_step_three_failure_before_uncertainty_publication_leaves_state_planned(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000009"
        protocol, _, proposed = self._dispatch_state("run-uncertainty-before", operation_id)
        with patch.object(protocol, "_publish_immutable", side_effect=OSError("uncertainty write failed")):
            with self.assertRaisesRegex(OSError, "uncertainty write failed"):
                protocol.publish_uncertainty(self.repo, "run-uncertainty-before", proposed, 0, operation_id)
        invocation = self.repo / ".kapisch/v3/runs/run-uncertainty-before/invocations" / operation_id
        self.assertTrue((invocation / "planned.json").is_file())
        self.assertFalse((invocation / "dispatch-uncertain.json").exists())
        self.assertEqual(protocol.load_state(self.repo, "run-uncertainty-before")["revision"], 0)

    def test_step_one_ack_loss_leaves_request_but_never_reserves(self) -> None:
        from unittest.mock import patch

        from kapisch_core import protocol

        operation_id = "op-00000000000000000000000000000003"
        run_id = "run-request-orphan"
        protocol.publish_state(self.repo, run_id, self._state(run_id, history=[_stage("planned")]), -1)
        request = self.repo / ".kapisch/v3/runs" / run_id / "requests" / f"{operation_id}.json"
        packet = {"run_id": run_id, "operation_id": operation_id,
                  "stage_id": "s-00000000000000000000000000000001", "role": "implementer",
                  "bundle_digest": self.digest, "scope_digest": "0" * 64,
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}}
        original = protocol._publish_immutable

        def publish_then_lose_ack(directory, name, data):
            original(directory, name, data)
            if name == f"{operation_id}.json":
                raise OSError("request publication acknowledgment lost")

        with patch.object(protocol, "_publish_immutable", side_effect=publish_then_lose_ack):
            with self.assertRaisesRegex(OSError, "acknowledgment lost"):
                protocol.persist_request(
                    self.repo, "run-request-orphan", operation_id,
                    {"run_id": "run-request-orphan", "operation_id": operation_id,
                     "stage_id": "s-00000000000000000000000000000001", "role": "implementer",
                     "bundle_digest": self.digest, "scope_digest": "0" * 64,
                     "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}},
                )
        self.assertTrue(request.is_file())
        self.assertFalse((self.repo / ".kapisch/v3/runs/run-request-orphan/invocations").exists())

    def test_published_invocation_facts_match_closed_schema(self) -> None:
        import json
        from kapisch_core.bundle import canonical_json

        operation_id = "op-00000000000000000000000000000011"
        protocol, _, proposed = self._dispatch_state("run-schema-facts", operation_id)
        invocation_schema = json.loads((ROOT / "core/schemas/v3/invocation.json").read_text())
        operation_dir = self.repo / ".kapisch/v3/runs/run-schema-facts/invocations" / operation_id
        planned = json.loads((operation_dir / "planned.json").read_bytes())
        self.assertEqual(set(planned), set(invocation_schema["properties"]))
        self.assertEqual(planned["protocol_version"], 3)
        self.assertEqual(planned["status"], "planned")
        protocol.publish_uncertainty(self.repo, "run-schema-facts", proposed, 0, operation_id)
        uncertain_bytes = (operation_dir / "dispatch-uncertain.json").read_bytes()
        uncertain = json.loads(uncertain_bytes)
        self.assertEqual(set(uncertain), set(invocation_schema["properties"]))
        self.assertEqual(uncertain["protocol_version"], 3)
        self.assertEqual(uncertain["status"], "dispatch-uncertain")
        self.assertEqual(uncertain_bytes, canonical_json(uncertain))

    def test_reservation_rechecks_input_bytes_after_step_one(self) -> None:
        from kapisch_core import protocol

        operation_id = "op-00000000000000000000000000000014"
        run_id = "run-input-race"
        stage = _stage("planned")
        state = self._state(run_id, history=[stage])
        protocol.publish_state(self.repo, run_id, state, -1)
        input_path = self.repo / ".kapisch/v3/runs" / run_id / "evidence" / "input.json"
        input_path.parent.mkdir()
        input_path.write_bytes(b"approved input")
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": "implementer", "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "inputs": [{"path": "evidence/input.json", "sha256": hashlib.sha256(b"approved input").hexdigest()}]}
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        input_path.write_bytes(b"changed input")
        with self.assertRaisesRegex(ValueError, "request input evidence changed"):
            protocol.reserve_operation(
                self.repo, run_id, operation_id, stage["stage_id"], "implementer",
                {"path": request_path, "sha256": request_digest}, packet["adapter_binding"],
            )
        self.assertFalse((self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json").exists())

    def test_reservation_requires_request_from_step_one_path(self) -> None:
        from kapisch_core.bundle import canonical_json

        operation_id = "op-00000000000000000000000000000012"
        protocol, _, stage, packet, path, digest = self._begin("run-alternate-request", operation_id)
        alternate = self.repo / ".kapisch/v3/runs/run-alternate-request/requests/manual.json"
        alternate.parent.mkdir(exist_ok=True)
        alternate.write_bytes(canonical_json(packet))
        args = (self.repo, "run-alternate-request", operation_id, stage["stage_id"], "implementer",
                {"path": "requests/manual.json", "sha256": digest}, packet["adapter_binding"])
        with self.assertRaisesRegex(ValueError, "operation-specific request path"):
            protocol.reserve_operation(*args)

    def test_reservation_ack_loss_keeps_complete_binding_and_blocks_reuse(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000004"
        protocol, _, stage, packet, path, digest = self._begin("run-reservation-orphan", operation_id)
        original = protocol._publish_immutable

        def publish_then_lose_ack(directory, name, data):
            original(directory, name, data)
            if name == "planned.json":
                raise OSError("reservation acknowledgment lost")

        args = (self.repo, "run-reservation-orphan", operation_id, stage["stage_id"], "implementer",
                {"path": path, "sha256": digest}, packet["adapter_binding"])
        with patch.object(protocol, "_publish_immutable", side_effect=publish_then_lose_ack):
            with self.assertRaisesRegex(OSError, "acknowledgment lost"):
                protocol.reserve_operation(*args)
        planned = self.repo / ".kapisch/v3/runs/run-reservation-orphan/invocations" / operation_id / "planned.json"
        self.assertTrue(planned.is_file())
        self.assertFalse(planned.with_name("dispatch-uncertain.json").exists())
        with self.assertRaisesRegex(ValueError, "already reserved"):
            protocol.reserve_operation(*args)

    def test_atomic_publication_rejects_parallel_writer(self) -> None:
        from kapisch_core.protocol import publish_state

        initial = self._state("run-parallel")
        publish_state(self.repo, initial["run_id"], initial, expected_revision=-1)
        updated = {**initial, "revision": 1}
        barrier = multiprocessing.Barrier(2)
        results = multiprocessing.Queue()
        workers = [
            multiprocessing.Process(target=_publish, args=(str(self.repo), updated, barrier, results))
            for _ in range(2)
        ]
        for worker in workers:
            worker.start()
        outcomes = [results.get(timeout=10) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
            self.assertEqual(worker.exitcode, 0)
        self.assertCountEqual(outcomes, ["published", "ConcurrentModificationError"])

    def test_publication_rejects_separate_wire_attempt_id(self) -> None:
        from kapisch_core.protocol import publish_state

        invalid = _stage("planned")
        invalid["attempt_id"] = invalid["stage_id"]
        state = self._state("run-extra-attempt-id", history=[invalid])
        with self.assertRaisesRegex(ValueError, "missing or unknown fields"):
            publish_state(self.repo, state["run_id"], state, expected_revision=-1)

    def test_generic_state_publish_cannot_bypass_uncertainty_protocol(self) -> None:
        from kapisch_core.protocol import publish_state

        run_id = "run-generic-uncertainty"
        planned = _stage("planned")
        initial = self._state(run_id, history=[planned])
        publish_state(self.repo, run_id, initial, -1)
        uncertain = {**planned, "sequence": 1, "status": "dispatch-uncertain"}
        proposed = {**initial, "revision": 1, "history": [planned, uncertain]}
        with self.assertRaisesRegex(ValueError, "publish_uncertainty"):
            publish_state(self.repo, run_id, proposed, 0)

    def test_publication_rejects_nonconsecutive_duplicate_observation(self) -> None:
        from kapisch_core.protocol import publish_state

        first = _stage("planned")
        uncertain = {**first, "sequence": 1, "status": "dispatch-uncertain"}
        other = {**_stage("planned"), "stage_id": "s-00000000000000000000000000000002", "sequence": 2}
        duplicate = {**uncertain, "sequence": 3}
        state = self._state("run-nonconsecutive-duplicate", history=[first, uncertain, other, duplicate])
        with self.assertRaisesRegex(ValueError, "duplicate creation, changed binding, or duplicate observation"):
            publish_state(self.repo, state["run_id"], state, expected_revision=-1)

    def test_publication_rejects_evidence_after_terminal_attempt(self) -> None:
        from kapisch_core.protocol import publish_state

        planned = _stage("planned")
        completed = {**planned, "sequence": 1, "status": "complete"}
        initial = self._state("run-terminal-attempt", history=[planned])
        publish_state(self.repo, initial["run_id"], initial, expected_revision=-1)
        evidence_path = self.repo / ".kapisch/v3/runs" / initial["run_id"] / "evidence" / "later.json"
        evidence_path.parent.mkdir()
        evidence_path.write_bytes(b"later evidence")
        reference = {"kind": "verification", "path": "evidence/later.json",
                     "sha256": hashlib.sha256(b"later evidence").hexdigest()}
        terminal_prefix = {**initial, "revision": 1, "history": [planned, completed]}
        publish_state(self.repo, initial["run_id"], terminal_prefix, 0)
        changed = {**terminal_prefix, "revision": 2,
                   "history": [planned, completed, {**completed, "sequence": 2, "evidence": [reference]}]}
        with self.assertRaisesRegex(ValueError, "terminal attempt is immutable"):
            publish_state(self.repo, initial["run_id"], changed, 1)

    def test_node_execution_cannot_rebind_graph_or_approved_plan(self) -> None:
        from kapisch_core.protocol import publish_state

        for field in ("graph", "approved_plan"):
            with self.subTest(field=field):
                run_id = f"run-rebind-{field}"
                stage = {**_stage("planned"), "node_id": "n-00000000000000000000000000000001"}
                state = self._state(run_id, history=[stage])
                state["workflow"] = "milestone"
                state["graph"] = {"path": "graphs/approved.json", "sha256": "1" * 64}
                state["approved_plan"] = {"plan_id": "plan-1", "path": "plans/approved.json", "sha256": "2" * 64}
                publish_state(self.repo, run_id, state, -1)
                changed = {**state, "revision": 1,
                           field: {**state[field], "sha256": "3" * 64}}
                with self.assertRaisesRegex(ValueError, "execution authority references are immutable"):
                    publish_state(self.repo, run_id, changed, 0)

    def test_publication_rejects_rewritten_history_prefix(self) -> None:
        from kapisch_core.protocol import publish_state

        planned = _stage("planned")
        state = self._state("run-prefix", history=[planned])
        publish_state(self.repo, "run-prefix", state, expected_revision=-1)
        rewritten = {**planned, "status": "failed"}
        with self.assertRaises(ValueError):
            publish_state(self.repo, "run-prefix", {**state, "revision": 1, "history": [rewritten]}, 0)

    def test_repository_reservation_lock_rejects_cross_run_operation_collision(self) -> None:
        from kapisch_core.protocol import persist_request, publish_state

        operation_id = "op-00000000000000000000000000000002"
        requests = []
        for run_id in ("run-a", "run-b"):
            publish_state(self.repo, run_id, self._state(run_id, history=[_stage("planned")]), -1)
            request_path, request_digest = persist_request(
                self.repo, run_id, operation_id,
                {
                    "run_id": run_id,
                    "operation_id": operation_id,
                    "stage_id": "s-00000000000000000000000000000001",
                    "role": "implementer",
                    "bundle_digest": self.digest,
                    "scope_digest": "0" * 64,
                    "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
                },
            )
            requests.append({"path": request_path, "sha256": request_digest})
        barrier = multiprocessing.Barrier(2)
        results = multiprocessing.Queue()
        workers = [
            multiprocessing.Process(target=_reserve, args=(str(self.repo), run_id, operation_id, request, barrier, results))
            for run_id, request in zip(("run-a", "run-b"), requests)
        ]
        for worker in workers:
            worker.start()
        outcomes = [results.get(timeout=10) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
            self.assertEqual(worker.exitcode, 0)
        self.assertCountEqual(outcomes, ["reserved", "ValueError"])
        owners = list((self.repo / ".kapisch/v3/runs").glob(f"*/invocations/{operation_id}/planned.json"))
        self.assertEqual(len(owners), 1)

    def _dispatch_state(self, run_id: str, operation_id: str):
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        stage_id = "s-00000000000000000000000000000001"
        stage = _stage("planned")
        state = self._state(run_id, history=[stage])
        protocol.publish_state(self.repo, run_id, state, expected_revision=-1)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage_id,
                  "role": "implementer", "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}}
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        reservation = protocol.reserve_operation(
            self.repo, run_id, operation_id, stage_id, "implementer",
            {"path": request_path, "sha256": request_digest}, packet["adapter_binding"],
        )
        planned_path = self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json"
        planned_bytes = planned_path.read_bytes()
        uncertain_bytes = canonical_json({**reservation, "status": "dispatch-uncertain"})
        evidence = [
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {"kind": "invocation", "path": f"invocations/{operation_id}/planned.json",
             "sha256": hashlib.sha256(planned_bytes).hexdigest()},
            {"kind": "invocation", "path": f"invocations/{operation_id}/dispatch-uncertain.json",
             "sha256": hashlib.sha256(uncertain_bytes).hexdigest()},
        ]
        next_stage = {**stage, "sequence": 1, "status": "dispatch-uncertain", "evidence": evidence}
        return protocol, state, {**state, "revision": 1, "history": [stage, next_stage]}

    def test_uncertainty_publication_rejects_additional_unreserved_attempt(self) -> None:
        operation_id = "op-00000000000000000000000000000013"
        protocol, _, proposed = self._dispatch_state("run-extra-uncertain", operation_id)
        other = {**_stage("planned"), "stage_id": "s-00000000000000000000000000000002", "sequence": 2}
        other_uncertain = {**other, "sequence": 3, "status": "dispatch-uncertain"}
        proposed["history"].extend((other, other_uncertain))
        with self.assertRaisesRegex(ValueError, "exactly one reserved attempt observation"):
            protocol.publish_uncertainty(self.repo, "run-extra-uncertain", proposed, 0, operation_id)
        invocation = self.repo / ".kapisch/v3/runs/run-extra-uncertain/invocations" / operation_id
        self.assertFalse((invocation / "dispatch-uncertain.json").exists())
        self.assertEqual(protocol.load_state(self.repo, "run-extra-uncertain")["revision"], 0)

    def test_uncertainty_publication_ack_loss_preserves_veto(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000005"
        protocol, state, proposed = self._dispatch_state("run-uncertain-orphan", operation_id)
        original = protocol._publish_immutable

        def publish_then_lose_ack(directory, name, data):
            original(directory, name, data)
            if name == "dispatch-uncertain.json":
                raise OSError("uncertainty acknowledgment lost")

        with patch.object(protocol, "_publish_immutable", side_effect=publish_then_lose_ack):
            with self.assertRaisesRegex(OSError, "acknowledgment lost"):
                protocol.publish_uncertainty(self.repo, "run-uncertain-orphan", proposed, 0, operation_id)
        self.assertEqual(protocol.load_state(self.repo, "run-uncertain-orphan")["revision"], 0)
        self.assertTrue((self.repo / ".kapisch/v3/runs/run-uncertain-orphan/invocations" / operation_id / "dispatch-uncertain.json").is_file())

    def test_state_replace_ack_loss_keeps_published_uncertain_state(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000006"
        protocol, _, proposed = self._dispatch_state("run-state-ack-loss", operation_id)
        original = protocol._write_atomic

        def publish_then_lose_ack(directory, name, data, *, replace):
            original(directory, name, data, replace=replace)
            if name == "state.json":
                raise OSError("state acknowledgment lost")

        with patch.object(protocol, "_write_atomic", side_effect=publish_then_lose_ack):
            with self.assertRaisesRegex(OSError, "acknowledgment lost"):
                protocol.publish_uncertainty(self.repo, "run-state-ack-loss", proposed, 0, operation_id)
        self.assertEqual(protocol.load_state(self.repo, "run-state-ack-loss")["revision"], 1)
        self.assertEqual(protocol.load_state(self.repo, "run-state-ack-loss")["history"][-1]["status"], "dispatch-uncertain")

    def test_state_publish_failure_retains_reserved_operation_and_uncertainty(self) -> None:
        from unittest.mock import patch
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id = "run-orphan"
        stage_id = "s-00000000000000000000000000000001"
        operation_id = "op-00000000000000000000000000000001"
        stage = _stage("planned")
        state = self._state(run_id, history=[stage])
        protocol.publish_state(self.repo, run_id, state, expected_revision=-1)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage_id,
            "role": "implementer",
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
        }
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        reservation = protocol.reserve_operation(
            self.repo, run_id, operation_id, stage_id, "implementer",
            {"path": request_path, "sha256": request_digest}, packet["adapter_binding"],
        )
        planned_path = self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json"
        planned_bytes = planned_path.read_bytes()
        uncertain_bytes = canonical_json({**reservation, "status": "dispatch-uncertain"})
        evidence = [
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {"kind": "invocation", "path": f"invocations/{operation_id}/planned.json",
             "sha256": hashlib.sha256(planned_bytes).hexdigest()},
            {"kind": "invocation", "path": f"invocations/{operation_id}/dispatch-uncertain.json",
             "sha256": hashlib.sha256(uncertain_bytes).hexdigest()},
        ]
        uncertain = {**stage, "sequence": 1, "status": "dispatch-uncertain", "evidence": evidence}
        proposed = {**state, "revision": 1, "history": [stage, uncertain]}
        with patch.object(protocol, "_write_atomic", side_effect=OSError("injected state fsync failure")):
            with self.assertRaisesRegex(OSError, "injected state fsync failure"):
                protocol.publish_uncertainty(self.repo, run_id, proposed, 0, operation_id)
        invocation = self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id
        self.assertTrue((invocation / "planned.json").is_file())
        self.assertTrue((invocation / "dispatch-uncertain.json").is_file())
        self.assertEqual(protocol.load_state(self.repo, run_id)["revision"], 0)


if __name__ == "__main__":
    unittest.main()
