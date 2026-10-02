from __future__ import annotations

import hashlib
import json
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))
from kapisch_core import _invocation, _state


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
                  "role": stage["role"], "bundle_digest": self.digest,
                  "scope_digest": stage["scope_digest"], "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}}
        packet["node_id"] = stage["node_id"]
        return protocol, state, stage, packet

    def test_graphfree_request_binds_existing_approved_plan_through_uncertainty(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id = "run-graphfree-approved-plan"
        operation_id = "op-0000000000000000000000000000002c"
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        plan_bytes = canonical_json({"plan_id": "plan-task", "approved": True})
        plan_path = run_root / "plans/plan-task.json"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_bytes(plan_bytes)
        approved_plan = {
            "plan_id": "plan-task",
            "path": "plans/plan-task.json",
            "sha256": hashlib.sha256(plan_bytes).hexdigest(),
        }
        initial = self._state(run_id)
        initial["approved_plan"] = approved_plan
        protocol.publish_state(self.repo, run_id, initial, -1)
        stage = _stage("planned")
        state = {**initial, "revision": 1, "history": [stage]}
        protocol.publish_state(self.repo, run_id, state, 0)
        packet = {
            "run_id": run_id,
            "operation_id": operation_id,
            "stage_id": stage["stage_id"],
            "role": stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
        }
        request_path = run_root / "requests" / f"{operation_id}.json"
        with self.assertRaisesRegex(ValueError, "approved plan authority"):
            protocol.persist_request(self.repo, run_id, operation_id, packet)
        packet["approved_plan"] = {**approved_plan, "plan_id": "plan-substituted"}
        with self.assertRaisesRegex(ValueError, "approved plan authority"):
            protocol.persist_request(self.repo, run_id, operation_id, packet)
        self.assertFalse(request_path.exists())

        packet["approved_plan"] = approved_plan
        request_relative, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        request = {"path": request_relative, "sha256": request_digest}
        plan_path.write_bytes(b"changed plan bytes")
        with self.assertRaisesRegex(ValueError, "request input evidence changed"):
            protocol.reserve_operation(self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                                       request, packet["adapter_binding"])
        plan_path.write_bytes(plan_bytes)
        planned = protocol.reserve_operation(self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                                             request, packet["adapter_binding"])
        planned_bytes = canonical_json(planned)
        uncertain_bytes = canonical_json({**planned, "status": "dispatch-uncertain"})
        evidence = [
            {"kind": "protocol", "path": f"invocations/{operation_id}/planned.json",
             "sha256": hashlib.sha256(planned_bytes).hexdigest()},
            {"kind": "request", "path": request_relative, "sha256": request_digest},
            {"kind": "approved-plan", "path": approved_plan["path"], "sha256": approved_plan["sha256"]},
            {"kind": "protocol", "path": f"invocations/{operation_id}/dispatch-uncertain.json",
             "sha256": hashlib.sha256(uncertain_bytes).hexdigest()},
        ]
        observation = {**stage, "sequence": 1, "status": "dispatch-uncertain", "evidence": evidence}
        proposed = {**state, "revision": 2, "history": [stage, observation]}
        plan_path.write_bytes(b"changed plan bytes")
        with self.assertRaisesRegex(ValueError, "request input evidence changed"):
            protocol.publish_uncertainty(self.repo, run_id, proposed, 1, operation_id)
        self.assertFalse((run_root / "invocations" / operation_id / "dispatch-uncertain.json").exists())
        plan_path.write_bytes(plan_bytes)
        protocol.publish_uncertainty(self.repo, run_id, proposed, 1, operation_id)
        self.assertEqual(protocol.load_state(self.repo, run_id)["history"][-1]["status"], "dispatch-uncertain")

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

    def test_runwide_milestone_request_rejects_substituted_authority(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        for index, field in enumerate(("graph", "approved_plan")):
            run_id = f"run-runwide-binding-{index}"
            operation_id = f"op-{index + 16:032x}"
            initial = self._state(run_id)
            initial["workflow"] = "milestone"
            protocol.publish_state(self.repo, run_id, initial, -1)
            graph_bytes = canonical_json({"plan_id": "plan-1", "nodes": []})
            plan_bytes = canonical_json({"plan_id": "plan-1", "approved": True})
            run_root = self.repo / ".kapisch/v3/runs" / run_id
            graph_path, plan_path = run_root / "graphs/plan-1.json", run_root / "plans/plan-1.json"
            graph_path.parent.mkdir()
            plan_path.parent.mkdir()
            graph_path.write_bytes(graph_bytes)
            plan_path.write_bytes(plan_bytes)
            stage = {**_stage("planned"), "stage_kind": "final", "role": "reviewer"}
            state = {**initial, "revision": 1, "history": [stage],
                     "graph": {"path": "graphs/plan-1.json", "sha256": hashlib.sha256(graph_bytes).hexdigest()},
                     "approved_plan": {"plan_id": "plan-1", "path": "plans/plan-1.json",
                                       "sha256": hashlib.sha256(plan_bytes).hexdigest()}}
            protocol.publish_state(self.repo, run_id, state, 0)
            packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                      "role": stage["role"], "bundle_digest": self.digest,
                      "scope_digest": stage["scope_digest"], "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                      "graph": state["graph"], "approved_plan": state["approved_plan"]}
            if field == "graph":
                (graph_path.parent / "other.json").write_bytes(graph_bytes)
                packet["graph"] = {**state["graph"], "path": "graphs/other.json"}
            else:
                packet["approved_plan"] = {**state["approved_plan"], "plan_id": "plan-2"}
            with self.assertRaisesRegex(ValueError, "current approved authority"):
                protocol.persist_request(self.repo, run_id, operation_id, packet)

    def test_uncertainty_publication_preserves_runwide_authority(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id, operation_id = "run-runwide-authority-swap", "op-00000000000000000000000000000018"
        initial = self._state(run_id)
        initial["workflow"] = "milestone"
        protocol.publish_state(self.repo, run_id, initial, -1)
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        graph_bytes = canonical_json({"plan_id": "plan-1", "nodes": []})
        plan_bytes = canonical_json({"plan_id": "plan-1", "approved": True})
        graph_path, plan_path = run_root / "graphs/plan-1.json", run_root / "plans/plan-1.json"
        graph_path.parent.mkdir()
        plan_path.parent.mkdir()
        graph_path.write_bytes(graph_bytes)
        plan_path.write_bytes(plan_bytes)
        snapshot_bytes = canonical_json({"protocol_version": 3, "snapshot_id": "snap-1", "decision": "accepted",
                                         "scope": "milestone", "dependencies": [], "amends": [], "supersedes": []})
        snapshot_path = run_root / "snapshots/snap-1.json"
        snapshot_path.parent.mkdir()
        snapshot_path.write_bytes(snapshot_bytes)
        stage = {**_stage("planned"), "stage_kind": "final", "role": "reviewer"}
        state = {**initial, "revision": 1, "history": [stage],
                 "graph": {"path": "graphs/plan-1.json", "sha256": hashlib.sha256(graph_bytes).hexdigest()},
                 "approved_plan": {"plan_id": "plan-1", "path": "plans/plan-1.json",
                                   "sha256": hashlib.sha256(plan_bytes).hexdigest()},
                 "accepted_snapshot": {"snapshot_id": "snap-1", "path": "snapshots/snap-1.json",
                                       "sha256": hashlib.sha256(snapshot_bytes).hexdigest()},
                 "amends": [], "supersedes": []}
        protocol.publish_state(self.repo, run_id, state, 0)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "graph": state["graph"], "approved_plan": state["approved_plan"],
                  "accepted_snapshot": state["accepted_snapshot"], "amends": state["amends"],
                  "supersedes": state["supersedes"]}
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        planned = protocol.reserve_operation(self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                                             {"path": request_path, "sha256": request_digest}, packet["adapter_binding"])
        planned_bytes = canonical_json(planned)
        uncertain_bytes = canonical_json({**planned, "status": "dispatch-uncertain"})
        evidence = [
            {"kind": "protocol", "path": f"invocations/{operation_id}/planned.json", "sha256": hashlib.sha256(planned_bytes).hexdigest()},
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {"kind": "graph", "path": state["graph"]["path"], "sha256": state["graph"]["sha256"]},
            {"kind": "approved-plan", "path": state["approved_plan"]["path"], "sha256": state["approved_plan"]["sha256"]},
            {"kind": "snapshot", "path": state["accepted_snapshot"]["path"], "sha256": state["accepted_snapshot"]["sha256"]},
            {"kind": "protocol", "path": f"invocations/{operation_id}/dispatch-uncertain.json", "sha256": hashlib.sha256(uncertain_bytes).hexdigest()},
        ]
        observation = {**stage, "sequence": 1, "status": "dispatch-uncertain", "evidence": evidence}
        graph_b = canonical_json({"plan_id": "plan-2", "nodes": []})
        plan_b = canonical_json({"plan_id": "plan-2", "approved": True})
        (graph_path.parent / "plan-2.json").write_bytes(graph_b)
        (plan_path.parent / "plan-2.json").write_bytes(plan_b)
        proposed = {**state, "revision": 2, "history": [stage, observation],
                    "graph": {"path": "graphs/plan-2.json", "sha256": hashlib.sha256(graph_b).hexdigest()},
                    "approved_plan": {"plan_id": "plan-2", "path": "plans/plan-2.json",
                                      "sha256": hashlib.sha256(plan_b).hexdigest()}}
        with self.assertRaisesRegex(ValueError, "preserve graph and approved plan bindings"):
            protocol.publish_uncertainty(self.repo, run_id, proposed, 1, operation_id)
        self.assertEqual(protocol.load_state(self.repo, run_id)["graph"], state["graph"])
        self.assertFalse((run_root / "invocations" / operation_id / "dispatch-uncertain.json").exists())

        correct = {**proposed, "graph": state["graph"], "approved_plan": state["approved_plan"]}
        protocol.publish_uncertainty(self.repo, run_id, correct, 1, operation_id)
        current = protocol.load_state(self.repo, run_id)
        rebound = {**current, "revision": current["revision"] + 1,
                   "graph": proposed["graph"], "approved_plan": proposed["approved_plan"]}
        with self.assertRaisesRegex(ValueError, "immutable after operation binding"):
            protocol.publish_state(self.repo, run_id, rebound, current["revision"])

    def test_uncertainty_publication_preserves_snapshot_relationships(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id, operation_id = "run-snapshot-authority", "op-00000000000000000000000000000021"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        snapshot_a = canonical_json({"protocol_version": 3, "snapshot_id": "snap-a", "decision": "accepted",
                                     "scope": "task", "dependencies": [], "amends": [], "supersedes": []})
        ref_a = {"snapshot_id": "snap-a", "path": "snapshots/snap-a.json",
                 "sha256": hashlib.sha256(snapshot_a).hexdigest()}
        snapshot_b = canonical_json({"protocol_version": 3, "snapshot_id": "snap-b", "decision": "accepted",
                                     "scope": "task", "dependencies": [{"kind": "snapshot", **ref_a}],
                                     "amends": ["snap-a"], "supersedes": []})
        ref_b = {"snapshot_id": "snap-b", "path": "snapshots/snap-b.json",
                 "sha256": hashlib.sha256(snapshot_b).hexdigest()}
        for name, data in (("snap-a.json", snapshot_a), ("snap-b.json", snapshot_b)):
            path = run_root / "snapshots" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref_a, amends=[], supersedes=[])
        protocol.publish_state(self.repo, run_id, state, -1)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "accepted_snapshot": ref_a, "amends": [], "supersedes": [],
                  "inputs": [{"path": ref_a["path"], "sha256": ref_a["sha256"]}]}
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        persisted_packet = json.loads((run_root / request_path).read_bytes())
        planned = protocol.reserve_operation(self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                                             {"path": request_path, "sha256": request_digest}, packet["adapter_binding"])
        planned_bytes = canonical_json(planned)
        uncertain_bytes = canonical_json({**planned, "status": "dispatch-uncertain"})
        evidence = [
            {"kind": "protocol", "path": f"invocations/{operation_id}/planned.json", "sha256": hashlib.sha256(planned_bytes).hexdigest()},
            {"kind": "request", "path": request_path, "sha256": request_digest},
            {"kind": "snapshot", "path": persisted_packet["accepted_snapshot"]["path"], "sha256": persisted_packet["accepted_snapshot"]["sha256"]},
            {"kind": "snapshot", "path": persisted_packet["inputs"][0]["path"], "sha256": persisted_packet["inputs"][0]["sha256"]},
            {"kind": "protocol", "path": f"invocations/{operation_id}/dispatch-uncertain.json", "sha256": hashlib.sha256(uncertain_bytes).hexdigest()},
        ]
        observation = {**stage, "sequence": 1, "status": "dispatch-uncertain", "evidence": evidence}
        proposed = {**state, "revision": 1, "history": [stage, observation],
                    "accepted_snapshot": ref_b, "amends": ["snap-a"], "supersedes": []}
        with self.assertRaisesRegex(ValueError, "preserve graph and approved plan bindings"):
            protocol.publish_uncertainty(self.repo, run_id, proposed, 0, operation_id)
        changed_current = {**state, "revision": 1, "accepted_snapshot": ref_b,
                           "amends": ["snap-a"], "supersedes": []}
        protocol.publish_state(self.repo, run_id, changed_current, 0)
        mismatch = {**changed_current, "revision": 2, "history": [stage, observation]}
        with self.assertRaisesRegex(ValueError, "current accepted snapshot authority"):
            protocol.publish_uncertainty(self.repo, run_id, mismatch, 1, operation_id)
        self.assertFalse((run_root / "invocations" / operation_id / "dispatch-uncertain.json").exists())
        restore = {**state, "revision": 2}
        protocol.publish_state(self.repo, run_id, restore, 1)
        correct = {**state, "revision": 3, "history": [stage, observation]}
        protocol.publish_uncertainty(self.repo, run_id, correct, 2, operation_id)
        current = protocol.load_state(self.repo, run_id)
        rebound = {**current, "revision": current["revision"] + 1,
                   "accepted_snapshot": ref_b, "amends": ["snap-a"], "supersedes": []}
        protocol.publish_state(self.repo, run_id, rebound, current["revision"])
        saved_packet = json.loads((run_root / request_path).read_bytes())
        self.assertEqual(protocol.load_state(self.repo, run_id)["accepted_snapshot"], ref_b)
        self.assertEqual(saved_packet["accepted_snapshot"], ref_a)
        self.assertEqual(saved_packet["amends"], [])

    def test_reservation_rejects_snapshot_change_after_request_publication(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id, operation_id = "run-snapshot-reservation-race", "op-00000000000000000000000000000022"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        snapshot_a = canonical_json({"protocol_version": 3, "snapshot_id": "snap-a", "decision": "accepted",
                                     "scope": "task", "dependencies": [], "amends": [], "supersedes": []})
        ref_a = {"snapshot_id": "snap-a", "path": "snapshots/snap-a.json",
                 "sha256": hashlib.sha256(snapshot_a).hexdigest()}
        snapshot_b = canonical_json({"protocol_version": 3, "snapshot_id": "snap-b", "decision": "accepted",
                                     "scope": "task", "dependencies": [{"kind": "snapshot", **ref_a}],
                                     "amends": ["snap-a"], "supersedes": []})
        ref_b = {"snapshot_id": "snap-b", "path": "snapshots/snap-b.json",
                 "sha256": hashlib.sha256(snapshot_b).hexdigest()}
        for name, data in (("snap-a.json", snapshot_a), ("snap-b.json", snapshot_b)):
            path = run_root / "snapshots" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref_a, amends=[], supersedes=[])
        protocol.publish_state(self.repo, run_id, state, -1)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "accepted_snapshot": ref_a, "amends": [], "supersedes": []}
        request_path, request_digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        changed = {**state, "revision": 1, "accepted_snapshot": ref_b,
                   "amends": ["snap-a"], "supersedes": []}
        protocol.publish_state(self.repo, run_id, changed, 0)
        self.assertEqual(protocol.load_state(self.repo, run_id)["accepted_snapshot"], ref_b)
        with self.assertRaisesRegex(ValueError, "current accepted snapshot authority"):
            protocol.reserve_operation(self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                                       {"path": request_path, "sha256": request_digest}, packet["adapter_binding"])
        self.assertFalse((run_root / "invocations" / operation_id / "planned.json").exists())

    def test_request_accepts_snapshot_relationships_bound_to_prior_artifact(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id, operation_id = "run-valid-snapshot-edge", "op-00000000000000000000000000000025"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        snapshot_a = canonical_json({"protocol_version": 3, "snapshot_id": "snap-a", "decision": "accepted",
                                    "scope": "task", "dependencies": [], "amends": [], "supersedes": []})
        path_a = run_root / "snapshots/snap-a.json"
        path_a.parent.mkdir(parents=True)
        path_a.write_bytes(snapshot_a)
        ref_a = {"snapshot_id": "snap-a", "path": "snapshots/snap-a.json",
                 "sha256": hashlib.sha256(snapshot_a).hexdigest()}
        snapshot_b = canonical_json({"protocol_version": 3, "snapshot_id": "snap-b", "decision": "accepted",
                                     "scope": "task", "dependencies": [{"kind": "snapshot", **ref_a}],
                                     "amends": ["snap-a"], "supersedes": []})
        path_b = run_root / "snapshots/snap-b.json"
        path_b.write_bytes(snapshot_b)
        ref_b = {"snapshot_id": "snap-b", "path": "snapshots/snap-b.json",
                 "sha256": hashlib.sha256(snapshot_b).hexdigest()}
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref_b, amends=["snap-a"], supersedes=[])
        protocol.publish_state(self.repo, run_id, state, -1)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "accepted_snapshot": ref_b, "amends": ["snap-a"], "supersedes": []}
        request_path, digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        request_bytes = (run_root / request_path).read_bytes()
        self.assertEqual(hashlib.sha256(request_bytes).hexdigest(), digest)
        self.assertEqual(json.loads(request_bytes)["accepted_snapshot"], ref_b)

    def test_request_accepts_decision_dependency_dual_id_for_snapshot_edge(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id, operation_id = "run-dual-id-snapshot-edge", "op-00000000000000000000000000000026"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        decision_bytes = canonical_json({
            "protocol_version": 3, "approval_id": "approval-a", "run_id": run_id,
            "gate": "human-decision", "decision_id": "decision-a", "decision": "accept",
            "target": "snap-a", "scope_digest": "0" * 64,
            "source": {"reference": "human-input.txt", "sha256": "0" * 64,
                       "source": "externally-supplied"},
        })
        decision_path = run_root / "decisions/decision-a.json"
        decision_path.parent.mkdir(parents=True)
        decision_path.write_bytes(decision_bytes)
        decision = {"kind": "decision", "path": "decisions/decision-a.json",
                    "sha256": hashlib.sha256(decision_bytes).hexdigest(),
                    "decision_id": "decision-a", "snapshot_id": "snap-a"}
        snapshot_a = canonical_json({"protocol_version": 3, "snapshot_id": "snap-a", "decision": "accepted",
                                     "scope": "task", "dependencies": [decision], "amends": [], "supersedes": []})
        path_a = run_root / "snapshots/snap-a.json"
        path_a.parent.mkdir(parents=True)
        path_a.write_bytes(snapshot_a)
        ref_a = {"kind": "snapshot", "path": "snapshots/snap-a.json",
                 "sha256": hashlib.sha256(snapshot_a).hexdigest(), "snapshot_id": "snap-a"}
        snapshot_b = canonical_json({"protocol_version": 3, "snapshot_id": "snap-b", "decision": "accepted",
                                     "scope": "task", "dependencies": [decision, ref_a],
                                     "amends": ["snap-a"], "supersedes": []})
        snapshot_path = run_root / "snapshots/snap-b.json"
        snapshot_path.write_bytes(snapshot_b)
        ref_b = {"snapshot_id": "snap-b", "path": "snapshots/snap-b.json",
                 "sha256": hashlib.sha256(snapshot_b).hexdigest()}
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref_b, amends=["snap-a"], supersedes=[])
        protocol.publish_state(self.repo, run_id, state, -1)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "accepted_snapshot": ref_b, "amends": ["snap-a"], "supersedes": []}
        request_path, _ = protocol.persist_request(self.repo, run_id, operation_id, packet)
        self.assertTrue((run_root / request_path).is_file())

    def test_current_decision_binding_is_distinct_from_predecessor_edge(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id = "run-current-decision-and-prior-snapshot"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        decision_bytes = canonical_json({
            "protocol_version": 3, "approval_id": "approval-current", "run_id": run_id,
            "gate": "human-decision", "decision_id": "decision-current", "decision": "accept",
            "target": "current", "scope_digest": "0" * 64,
            "source": {"reference": "human-input.txt", "sha256": "0" * 64,
                       "source": "externally-supplied"},
        })
        decision_path = run_root / "decisions/current.json"
        decision_path.parent.mkdir(parents=True)
        decision_path.write_bytes(decision_bytes)
        decision = {"kind": "decision", "path": "decisions/current.json",
                    "sha256": hashlib.sha256(decision_bytes).hexdigest(),
                    "decision_id": "decision-current", "snapshot_id": "current"}
        prior = canonical_json({"protocol_version": 3, "snapshot_id": "prior", "decision": "accepted",
                                "scope": "task", "dependencies": [], "amends": [], "supersedes": []})
        prior_path = run_root / "snapshots/prior.json"
        prior_path.parent.mkdir(parents=True)
        prior_path.write_bytes(prior)
        prior_ref = {"kind": "snapshot", "path": "snapshots/prior.json",
                     "sha256": hashlib.sha256(prior).hexdigest(), "snapshot_id": "prior"}
        current = canonical_json({"protocol_version": 3, "snapshot_id": "current", "decision": "accepted",
                                  "scope": "task", "dependencies": [decision, prior_ref],
                                  "amends": ["prior"], "supersedes": []})
        current_path = run_root / "snapshots/current.json"
        current_path.write_bytes(current)
        ref = {"snapshot_id": "current", "path": "snapshots/current.json",
               "sha256": hashlib.sha256(current).hexdigest()}
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref, amends=["prior"], supersedes=[])
        protocol.publish_state(self.repo, run_id, state, -1)

    def test_snapshot_edge_rejects_dual_id_decision_stub_without_prior_snapshot(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id = "run-snapshot-decision-stub"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        decision_bytes = canonical_json({"decision_id": "decision-a", "snapshot_id": "snap-a"})
        decision_path = run_root / "decisions/snap-a.json"
        decision_path.parent.mkdir(parents=True)
        decision_path.write_bytes(decision_bytes)
        dependency = {"kind": "decision", "path": "decisions/snap-a.json",
                      "sha256": hashlib.sha256(decision_bytes).hexdigest(),
                      "decision_id": "decision-a", "snapshot_id": "snap-a"}
        snapshot = canonical_json({"protocol_version": 3, "snapshot_id": "snap-b", "decision": "accepted",
                                   "scope": "task", "dependencies": [dependency],
                                   "amends": ["snap-a"], "supersedes": []})
        snapshot_path = run_root / "snapshots/snap-b.json"
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_bytes(snapshot)
        ref = {"snapshot_id": "snap-b", "path": "snapshots/snap-b.json",
               "sha256": hashlib.sha256(snapshot).hexdigest()}
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref, amends=["snap-a"], supersedes=[])
        with self.assertRaisesRegex(ValueError, "snapshot dependency snapshot binding is unresolved"):
            protocol.publish_state(self.repo, run_id, state, -1)

    def test_snapshot_lineage_rejects_invalid_predecessor_dependency_ids(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id = "run-invalid-predecessor-dependency"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        decision_bytes = canonical_json({"decision": "accepted", "decision_id": "actual"})
        decision_path = run_root / "decisions/actual.json"
        decision_path.parent.mkdir(parents=True)
        decision_path.write_bytes(decision_bytes)
        prior = canonical_json({"protocol_version": 3, "snapshot_id": "prior", "decision": "accepted",
                                "scope": "task", "dependencies": [{
                                    "kind": "decision", "path": "decisions/actual.json",
                                    "sha256": hashlib.sha256(decision_bytes).hexdigest(),
                                    "decision_id": "wrong"}], "amends": [], "supersedes": []})
        prior_path = run_root / "snapshots/prior.json"
        prior_path.parent.mkdir(parents=True)
        prior_path.write_bytes(prior)
        prior_ref = {"kind": "snapshot", "path": "snapshots/prior.json",
                     "sha256": hashlib.sha256(prior).hexdigest(), "snapshot_id": "prior"}
        current = canonical_json({"protocol_version": 3, "snapshot_id": "current", "decision": "accepted",
                                  "scope": "task", "dependencies": [prior_ref],
                                  "amends": ["prior"], "supersedes": []})
        current_path = run_root / "snapshots/current.json"
        current_path.write_bytes(current)
        ref = {"snapshot_id": "current", "path": "snapshots/current.json",
               "sha256": hashlib.sha256(current).hexdigest()}
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref, amends=["prior"], supersedes=[])
        with self.assertRaisesRegex(ValueError, "snapshot dependency identity does not match artifact"):
            protocol.publish_state(self.repo, run_id, state, -1)
        (run_root / "state.json").write_bytes(canonical_json(state))
        with self.assertRaisesRegex(ValueError, "snapshot dependency identity does not match artifact"):
            protocol.load_state(self.repo, run_id)

    def test_snapshot_dependency_resolves_decision_id_inside_predecessor(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id, operation_id = "run-snapshot-contained-decision", "op-00000000000000000000000000000027"
        stage = _stage("planned")
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        decision_bytes = canonical_json({"decision": "approved", "decision_id": "decision-a"})
        decision_path = run_root / "decisions/decision-a.json"
        decision_path.parent.mkdir(parents=True)
        decision_path.write_bytes(decision_bytes)
        decision = {"kind": "decision", "path": "decisions/decision-a.json",
                    "sha256": hashlib.sha256(decision_bytes).hexdigest(), "decision_id": "decision-a"}
        prior = canonical_json({"protocol_version": 3, "snapshot_id": "prior", "decision": "accepted",
                                "scope": "task", "dependencies": [decision], "amends": [], "supersedes": []})
        prior_path = run_root / "snapshots/prior.json"
        prior_path.parent.mkdir(parents=True)
        prior_path.write_bytes(prior)
        prior_ref = {"kind": "snapshot", "path": "snapshots/prior.json",
                     "sha256": hashlib.sha256(prior).hexdigest(), "snapshot_id": "prior",
                     "decision_id": "decision-a"}
        current = canonical_json({"protocol_version": 3, "snapshot_id": "current", "decision": "accepted",
                                  "scope": "task", "dependencies": [prior_ref],
                                  "amends": ["prior"], "supersedes": []})
        current_path = run_root / "snapshots/current.json"
        current_path.write_bytes(current)
        ref = {"snapshot_id": "current", "path": "snapshots/current.json",
               "sha256": hashlib.sha256(current).hexdigest()}
        state = self._state(run_id, history=[stage])
        state.update(accepted_snapshot=ref, amends=["prior"], supersedes=[])
        protocol.publish_state(self.repo, run_id, state, -1)
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "accepted_snapshot": ref, "amends": ["prior"], "supersedes": []}
        request_path, _ = protocol.persist_request(self.repo, run_id, operation_id, packet)
        self.assertTrue((run_root / request_path).is_file())

    def test_snapshot_state_and_cold_load_reject_invalid_bindings(self) -> None:
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        def snapshot(snapshot_id, dependencies=(), amends=(), supersedes=()):
            return canonical_json({"protocol_version": 3, "snapshot_id": snapshot_id,
                                  "decision": "accepted", "scope": "task",
                                  "dependencies": list(dependencies), "amends": list(amends),
                                  "supersedes": list(supersedes)})

        expected_source = b"required source bytes"
        cases = (
            ("edge-mismatch", snapshot("snap-current", amends=("snap-old",)), [], {},
             "snapshot relationship bindings do not match artifact"),
            ("unresolved-edge", snapshot("snap-current", amends=("snap-missing",)), ["snap-missing"], {},
             "snapshot relationship target is unresolved"),
            ("missing-snapshot", snapshot("snap-current"), [], {},
             "accepted snapshot artifact is unavailable"),
            ("corrupt-snapshot", snapshot("snap-current"), [], {"snapshots/current.json": b"corrupt"},
             "accepted snapshot artifact digest changed"),
            ("missing-dependency", snapshot("snap-current", dependencies=(
                {"kind": "repository-file", "path": "sources/context.txt",
                 "sha256": hashlib.sha256(expected_source).hexdigest()},)), [],
             {"snapshots/current.json": snapshot("snap-current", dependencies=(
                 {"kind": "repository-file", "path": "sources/context.txt",
                  "sha256": hashlib.sha256(expected_source).hexdigest()},))},
             "snapshot dependency artifact is unavailable"),
            ("changed-dependency", snapshot("snap-current", dependencies=(
                {"kind": "repository-file", "path": "sources/context.txt",
                 "sha256": hashlib.sha256(expected_source).hexdigest()},)), [],
             {"snapshots/current.json": snapshot("snap-current", dependencies=(
                 {"kind": "repository-file", "path": "sources/context.txt",
                  "sha256": hashlib.sha256(expected_source).hexdigest()},)),
              "sources/context.txt": b"changed source bytes"},
             "snapshot dependency artifact digest changed"),
            ("wrong-decision-id", snapshot("snap-current", dependencies=(
                {"kind": "decision", "path": "decisions/decision.json",
                 "sha256": hashlib.sha256(canonical_json({"decision_id": "decision-actual"})).hexdigest(),
                 "decision_id": "decision-wrong"},)), [],
             {"decisions/decision.json": canonical_json({"decision_id": "decision-actual"})},
             "snapshot dependency identity does not match artifact"),
            ("wrong-snapshot-id", snapshot("snap-current", dependencies=(
                {"kind": "snapshot", "path": "snapshots/prior.json",
                 "sha256": hashlib.sha256(snapshot("snap-actual")).hexdigest(),
                 "snapshot_id": "snap-wrong"},)), [],
             {"snapshots/prior.json": snapshot("snap-actual")},
             "snapshot dependency identity does not match artifact"),
        )
        for label, snapshot_bytes, state_amends, files, error in cases:
            run_id = f"run-snapshot-{label}"
            run_root = self.repo / ".kapisch/v3/runs" / run_id
            artifacts = {} if label == "missing-snapshot" else {"snapshots/current.json": snapshot_bytes}
            artifacts.update(files)
            for relative, data in artifacts.items():
                path = run_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            ref = {"snapshot_id": "snap-current", "path": "snapshots/current.json",
                   "sha256": hashlib.sha256(snapshot_bytes).hexdigest()}
            state = self._state(run_id, history=[_stage("planned")])
            state.update(accepted_snapshot=ref, amends=state_amends, supersedes=[])
            with self.subTest(case=label, check="publish"):
                with self.assertRaisesRegex(ValueError, error):
                    protocol.publish_state(self.repo, run_id, state, -1)
            with self.subTest(case=label, check="cold-load"):
                run_root.mkdir(parents=True, exist_ok=True)
                (run_root / "state.json").write_bytes(canonical_json(state))
                with self.assertRaisesRegex(ValueError, error):
                    protocol.load_state(self.repo, run_id)

    def test_adapter_binding_requires_nonempty_string_values(self) -> None:
        from kapisch_core import protocol

        invalid_values = (42, True, {"namespace": "fake"}, ["ctx-1"])
        index = 32
        for field in ("adapter_id", "lookup_context"):
            for value in invalid_values:
                run_id = f"run-bad-binding-{index}"
                operation_id = f"op-{index:032x}"
                stage = _stage("planned")
                state = self._state(run_id, history=[stage])
                protocol.publish_state(self.repo, run_id, state, -1)
                packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                          "role": stage["role"], "bundle_digest": self.digest,
                          "scope_digest": stage["scope_digest"],
                          "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"}}
                packet["adapter_binding"][field] = value
                with self.assertRaisesRegex(ValueError, "adapter binding must contain nonempty strings"):
                    protocol.persist_request(self.repo, run_id, operation_id, packet)
                index += 1

        run_id, operation_id = "run-bad-reservation-binding", f"op-{index:032x}"
        protocol, _, stage, packet, path, digest = self._begin(run_id, operation_id)
        bad_binding = {"adapter_id": "fake", "lookup_context": 42}
        with self.assertRaisesRegex(ValueError, "adapter binding must contain nonempty strings"):
            protocol.reserve_operation(self.repo, run_id, operation_id, stage["stage_id"], "implementer",
                                       {"path": path, "sha256": digest}, bad_binding)
        fact = {"protocol_version": 3, "operation_id": operation_id, "run_id": run_id,
                "stage_id": stage["stage_id"], "role": "implementer", "request_digest": digest,
                "status": "planned", "request": {"path": path, "sha256": digest},
                "adapter_binding": bad_binding}
        with self.assertRaisesRegex(ValueError, "adapter binding must contain nonempty strings"):
            _invocation._validate_reservation(self.repo, run_id, operation_id, fact)

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
        original = _invocation._publish_immutable
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

        with patch.object(_invocation, "_publish_immutable", side_effect=pause_request):
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
        with patch.object(_invocation, "_publish_immutable", side_effect=OSError("request write failed")):
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
        with patch.object(_invocation, "_publish_immutable", side_effect=OSError("reservation write failed")):
            with self.assertRaisesRegex(OSError, "reservation write failed"):
                protocol.reserve_operation(*args)
        planned = self.repo / ".kapisch/v3/runs/run-reservation-before/invocations" / operation_id / "planned.json"
        self.assertFalse(planned.exists())
        self.assertEqual(protocol.load_state(self.repo, "run-reservation-before")["revision"], 0)

    def test_step_three_failure_before_uncertainty_publication_leaves_state_planned(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000009"
        protocol, _, proposed = self._dispatch_state("run-uncertainty-before", operation_id)
        with patch.object(_invocation, "_publish_immutable", side_effect=OSError("uncertainty write failed")):
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
        original = _invocation._publish_immutable

        def publish_then_lose_ack(directory, name, data):
            original(directory, name, data)
            if name == f"{operation_id}.json":
                raise OSError("request publication acknowledgment lost")

        with patch.object(_invocation, "_publish_immutable", side_effect=publish_then_lose_ack):
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

    def test_step_one_snapshots_input_bytes_without_overwrite(self) -> None:
        from kapisch_core import protocol

        run_id, operation_id = "run-input-snapshot", "op-00000000000000000000000000000019"
        stage = _stage("planned")
        state = self._state(run_id, history=[stage])
        protocol.publish_state(self.repo, run_id, state, -1)
        source_path = self.repo / ".kapisch/v3/runs" / run_id / "evidence/input.json"
        source_path.parent.mkdir()
        source_path.write_bytes(b"approved input")
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "inputs": [{"path": "evidence/input.json", "sha256": hashlib.sha256(b"approved input").hexdigest()}]}
        request_path, _ = protocol.persist_request(self.repo, run_id, operation_id, packet)
        request_packet = json.loads((self.repo / ".kapisch/v3/runs" / run_id / request_path).read_bytes())
        retained = request_packet["inputs"][0]
        self.assertEqual(retained["source_path"], "evidence/input.json")
        self.assertNotEqual(retained["path"], retained["source_path"])
        retained_path = self.repo / ".kapisch/v3/runs" / run_id / retained["path"]
        self.assertEqual(retained_path.read_bytes(), b"approved input")

        source_path.write_bytes(b"changed input")
        changed_packet = {**packet, "inputs": [{"path": "evidence/input.json",
                                                   "sha256": hashlib.sha256(b"changed input").hexdigest()}]}
        with self.assertRaisesRegex(ValueError, "request input publication conflict"):
            protocol.persist_request(self.repo, run_id, operation_id, changed_packet)
        self.assertEqual(retained_path.read_bytes(), b"approved input")

    def test_step_one_input_publication_failure_precedes_request_and_reservation(self) -> None:
        from unittest.mock import patch
        from kapisch_core import protocol

        run_id, operation_id = "run-input-publication-failure", "op-00000000000000000000000000000020"
        stage = _stage("planned")
        protocol.publish_state(self.repo, run_id, self._state(run_id, history=[stage]), -1)
        input_path = self.repo / ".kapisch/v3/runs" / run_id / "evidence/input.json"
        input_path.parent.mkdir()
        input_path.write_bytes(b"approved input")
        packet = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
                  "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
                  "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-1"},
                  "inputs": [{"path": "evidence/input.json", "sha256": hashlib.sha256(b"approved input").hexdigest()}]}
        with patch.object(_invocation, "_publish_immutable", side_effect=OSError("input publication failed")):
            with self.assertRaisesRegex(OSError, "input publication failed"):
                protocol.persist_request(self.repo, run_id, operation_id, packet)
        run_root = self.repo / ".kapisch/v3/runs" / run_id
        self.assertFalse((run_root / "requests" / f"{operation_id}.json").exists())
        self.assertFalse((run_root / "invocations" / operation_id / "planned.json").exists())

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
        request_packet = json.loads((self.repo / ".kapisch/v3/runs" / run_id / request_path).read_bytes())
        retained_path = self.repo / ".kapisch/v3/runs" / run_id / request_packet["inputs"][0]["path"]
        retained_path.write_bytes(b"changed input")
        with self.assertRaisesRegex(ValueError, "request input evidence changed"):
            protocol.reserve_operation(
                self.repo, run_id, operation_id, stage["stage_id"], "implementer",
                {"path": request_path, "sha256": request_digest}, packet["adapter_binding"],
            )
        self.assertFalse((self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json").exists())

    def test_read_contained_closes_intermediate_directory_after_later_failure(self) -> None:
        import os
        from unittest.mock import patch
        from kapisch_core import protocol, storage

        run_id = "run-contained-descriptor-cleanup"
        protocol.publish_state(self.repo, run_id, self._state(run_id), -1)
        existing = self.repo / ".kapisch/v3/runs" / run_id / "existing"
        existing.mkdir()
        opened = []
        original_open_dir = storage._open_dir

        def track_open_dir(parent, name, *, create=False):
            descriptor = original_open_dir(parent, name, create=create)
            if name == "existing":
                opened.append(descriptor)
            return descriptor

        with patch.object(storage, "_open_dir", side_effect=track_open_dir):
            with self.assertRaises(FileNotFoundError):
                storage._read_contained(self.repo, run_id, "existing/missing/file.json")
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0])

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
        original = _invocation._publish_immutable

        def publish_then_lose_ack(directory, name, data):
            original(directory, name, data)
            if name == "planned.json":
                raise OSError("reservation acknowledgment lost")

        args = (self.repo, "run-reservation-orphan", operation_id, stage["stage_id"], "implementer",
                {"path": path, "sha256": digest}, packet["adapter_binding"])
        with patch.object(_invocation, "_publish_immutable", side_effect=publish_then_lose_ack):
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

    def test_retry_resyncs_authority_directories_after_creation_ack_loss(self) -> None:
        import os
        from unittest.mock import patch
        from kapisch_core import protocol, storage

        def assert_retry_syncs_directory_entry(parent_path: Path, action) -> None:
            parent = os.stat(parent_path)
            original_fsync = os.fsync
            sync = {"failed": False, "retried": False}

            def fail_once_for_parent(fd: int) -> None:
                current = os.fstat(fd)
                if (current.st_dev, current.st_ino) == (parent.st_dev, parent.st_ino):
                    if not sync["failed"]:
                        sync["failed"] = True
                        raise OSError("injected parent directory fsync failure")
                    sync["retried"] = True
                original_fsync(fd)

            with patch.object(storage.os, "fsync", side_effect=fail_once_for_parent):
                with self.assertRaisesRegex(OSError, "injected parent directory fsync failure"):
                    action()
                action()
            self.assertTrue(sync["failed"])
            self.assertTrue(sync["retried"])

        state_run = "run-directory-sync"
        runs = self.repo / ".kapisch/v3/runs"
        runs.mkdir(parents=True)
        state = self._state(state_run)
        assert_retry_syncs_directory_entry(
            runs, lambda: protocol.publish_state(self.repo, state_run, state, -1)
        )

        request_run = "run-request-directory-sync"
        request_stage = _stage("planned")
        protocol.publish_state(self.repo, request_run, self._state(request_run, history=[request_stage]), -1)
        request_parent = self.repo / ".kapisch/v3/runs" / request_run
        request_packet = {
            "run_id": request_run,
            "operation_id": "op-0000000000000000000000000000002a",
            "stage_id": request_stage["stage_id"],
            "role": request_stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": request_stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
        }
        assert_retry_syncs_directory_entry(
            request_parent,
            lambda: protocol.persist_request(self.repo, request_run, request_packet["operation_id"], request_packet),
        )

        invocation_run = "run-invocation-directory-sync"
        invocation_stage = _stage("planned")
        protocol.publish_state(self.repo, invocation_run,
                               self._state(invocation_run, history=[invocation_stage]), -1)
        invocation_packet = {
            "run_id": invocation_run,
            "operation_id": "op-0000000000000000000000000000002b",
            "stage_id": invocation_stage["stage_id"],
            "role": invocation_stage["role"],
            "bundle_digest": self.digest,
            "scope_digest": invocation_stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx"},
        }
        request_path, request_digest = protocol.persist_request(
            self.repo, invocation_run, invocation_packet["operation_id"], invocation_packet
        )
        assert_retry_syncs_directory_entry(
            self.repo / ".kapisch/v3/runs" / invocation_run,
            lambda: protocol.reserve_operation(
                self.repo, invocation_run, invocation_packet["operation_id"], invocation_stage["stage_id"],
                invocation_stage["role"], {"path": request_path, "sha256": request_digest},
                invocation_packet["adapter_binding"],
            ),
        )

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

    def test_reservation_detaches_request_reference_before_validation(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import patch
        from kapisch_core import protocol
        from kapisch_core.bundle import canonical_json

        run_id = "run-reservation-input-snapshot-request"
        operation_id = "op-0000000000000000000000000000002d"
        protocol, _, stage, packet, path, digest = self._begin(run_id, operation_id)
        request = {"path": path, "sha256": digest}
        request_file = self.repo / ".kapisch/v3/runs" / run_id / path
        changed_bytes = canonical_json({**packet, "extra": "changed after serialization"})
        changed_digest = hashlib.sha256(changed_bytes).hexdigest()
        original_locked = _invocation._locked

        @contextmanager
        def mutate_request_after_body(repo, locked_run_id):
            request_file.write_bytes(changed_bytes)
            request["sha256"] = changed_digest
            with original_locked(repo, locked_run_id):
                yield

        with patch.object(_invocation, "_locked", side_effect=mutate_request_after_body):
            with self.assertRaisesRegex(ValueError, "request packet bytes are noncanonical or mismatched"):
                protocol.reserve_operation(
                    self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                    request, dict(packet["adapter_binding"]),
                )
        planned_path = self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json"
        self.assertFalse(planned_path.exists())

    def test_reservation_detaches_adapter_binding_before_validation(self) -> None:
        from contextlib import contextmanager
        from unittest.mock import patch
        from kapisch_core import protocol

        run_id = "run-reservation-input-snapshot-adapter"
        operation_id = "op-0000000000000000000000000000002e"
        stage = _stage("planned")
        protocol.publish_state(self.repo, run_id, self._state(run_id, history=[stage]), -1)
        packet = {
            "run_id": run_id, "operation_id": operation_id, "stage_id": stage["stage_id"],
            "role": stage["role"], "bundle_digest": self.digest, "scope_digest": stage["scope_digest"],
            "adapter_binding": {"adapter_id": "fake", "lookup_context": "ctx-mutated"},
        }
        path, digest = protocol.persist_request(self.repo, run_id, operation_id, packet)
        request = {"path": path, "sha256": digest}
        adapter_binding = {"adapter_id": "fake", "lookup_context": "ctx-1"}
        original_locked = _invocation._locked

        @contextmanager
        def mutate_adapter_after_body(repo, locked_run_id):
            adapter_binding["lookup_context"] = "ctx-mutated"
            with original_locked(repo, locked_run_id):
                yield

        with patch.object(_invocation, "_locked", side_effect=mutate_adapter_after_body):
            with self.assertRaisesRegex(ValueError, "request packet differs from reservation binding"):
                protocol.reserve_operation(
                    self.repo, run_id, operation_id, stage["stage_id"], stage["role"],
                    request, adapter_binding,
                )
        planned_path = self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id / "planned.json"
        self.assertFalse(planned_path.exists())

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

    def test_uncertainty_publication_commits_the_validated_state_snapshot(self) -> None:
        from unittest.mock import patch

        operation_id = "op-0000000000000000000000000000002d"
        protocol, _, proposed = self._dispatch_state("run-validated-state-snapshot", operation_id)
        expected_evidence = [dict(ref) for ref in proposed["history"][-1]["evidence"]]
        original = _invocation._publish_state_locked

        def mutate_caller_before_commit(*args, **kwargs):
            proposed["history"][-1]["evidence"].clear()
            return original(*args, **kwargs)

        with patch.object(_invocation, "_publish_state_locked", side_effect=mutate_caller_before_commit):
            protocol.publish_uncertainty(self.repo, "run-validated-state-snapshot", proposed, 0, operation_id)
        persisted = protocol.load_state(self.repo, "run-validated-state-snapshot")
        self.assertEqual(persisted["history"][-1]["evidence"], expected_evidence)

    def test_uncertainty_publication_ack_loss_preserves_veto(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000005"
        protocol, state, proposed = self._dispatch_state("run-uncertain-orphan", operation_id)
        original = _invocation._publish_immutable

        def publish_then_lose_ack(directory, name, data):
            original(directory, name, data)
            if name == "dispatch-uncertain.json":
                raise OSError("uncertainty acknowledgment lost")

        with patch.object(_invocation, "_publish_immutable", side_effect=publish_then_lose_ack):
            with self.assertRaisesRegex(OSError, "acknowledgment lost"):
                protocol.publish_uncertainty(self.repo, "run-uncertain-orphan", proposed, 0, operation_id)
        self.assertEqual(protocol.load_state(self.repo, "run-uncertain-orphan")["revision"], 0)
        self.assertTrue((self.repo / ".kapisch/v3/runs/run-uncertain-orphan/invocations" / operation_id / "dispatch-uncertain.json").is_file())

    def test_state_replace_ack_loss_keeps_published_uncertain_state(self) -> None:
        from unittest.mock import patch

        operation_id = "op-00000000000000000000000000000006"
        protocol, _, proposed = self._dispatch_state("run-state-ack-loss", operation_id)
        original = _state._write_atomic

        def publish_then_lose_ack(directory, name, data, *, replace):
            original(directory, name, data, replace=replace)
            if name == "state.json":
                raise OSError("state acknowledgment lost")

        with patch.object(_state, "_write_atomic", side_effect=publish_then_lose_ack):
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
        with patch.object(_state, "_write_atomic", side_effect=OSError("injected state fsync failure")):
            with self.assertRaisesRegex(OSError, "injected state fsync failure"):
                protocol.publish_uncertainty(self.repo, run_id, proposed, 0, operation_id)
        invocation = self.repo / ".kapisch/v3/runs" / run_id / "invocations" / operation_id
        self.assertTrue((invocation / "planned.json").is_file())
        self.assertTrue((invocation / "dispatch-uncertain.json").is_file())
        self.assertEqual(protocol.load_state(self.repo, run_id)["revision"], 0)


if __name__ == "__main__":
    unittest.main()
