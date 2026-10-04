from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._authority import (
    _unique_pairs,
    _validate_packet_authority,
    _validate_snapshot_authority,
    _validate_state_snapshot,
)
from ._locking import _locked
from ._state import (
    ConcurrentModificationError,
    _id,
    _load_run_context,
    _publish_state_locked,
    _routing_digest,
    load_state,
)
from .bundle import canonical_json
from .storage import (
    _NAME,
    _atomic_write_at,
    _close,
    _open_dir,
    _read_contained,
    _read_file,
    _run_dir,
    _runs_dir,
    _safe_relative,
)

_AUTHORITY_FIELDS = ("graph", "approved_plan", "accepted_snapshot", "amends", "supersedes")


def _valid_adapter_binding(binding: Any) -> bool:
    return (isinstance(binding, Mapping) and set(binding) == {"adapter_id", "lookup_context"}
            and all(isinstance(binding[field], str) and binding[field] for field in ("adapter_id", "lookup_context")))

def _validate_packet_inputs(repo: Path, run_id: str, operation_id: str, packet: Mapping[str, Any], bundle: Any) -> None:
    if bundle.payload.get("authority_contract") == "global-authority/1" and any(
            key in packet for key in ("accepted_snapshot", "amends", "supersedes", "approved_plan", "acceptance_ref")):
        raise ValueError("unsupported-gate: global authority consumers are not implemented")
    inputs = packet.get("inputs", [])
    if not isinstance(inputs, list):
        raise ValueError("operation request inputs are invalid")
    refs = []
    for index, item in enumerate(inputs):
        if (not isinstance(item, dict) or set(item) != {"path", "sha256", "source_path"}
                or item.get("path") != f"request-inputs/{operation_id}/{index:04d}.bin"
                or not _safe_relative(item.get("source_path"))):
            raise ValueError("operation request input must bind immutable published bytes and source path")
        refs.append({"path": item["path"], "sha256": item["sha256"]})
    for field, keys in (("graph", {"path", "sha256"}), ("approved_plan", {"plan_id", "path", "sha256"}),
                        ("accepted_snapshot", {"snapshot_id", "path", "sha256"})):
        if field in packet:
            ref = packet[field]
            if (not isinstance(ref, dict) or set(ref) != keys
                    or (field == "approved_plan" and not ref.get("plan_id"))
                    or (field == "accepted_snapshot" and not ref.get("snapshot_id"))):
                raise ValueError("operation request authority reference is invalid")
            refs.append({"path": ref["path"], "sha256": ref["sha256"]})
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
                or not _safe_relative(ref.get("path")) or not isinstance(ref.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])):
            raise ValueError("operation request input reference is invalid")
        if hashlib.sha256(_read_contained(repo, run_id, ref["path"])).hexdigest() != ref["sha256"]:
            raise ValueError("request input evidence changed")
    if "accepted_snapshot" in packet:
        _validate_snapshot_authority(repo, run_id, packet["accepted_snapshot"], packet["amends"], packet["supersedes"])

def _validate_reservation(repo: Path, run_id: str, operation_id: str, fact: Any, *, validate_current_authority: bool = True) -> dict[str, Any]:
    fields = {"protocol_version", "operation_id", "run_id", "stage_id", "role", "request_digest", "status", "request", "adapter_binding"}
    if not isinstance(fact, dict) or set(fact) != fields:
        raise ValueError("operation reservation has missing or unknown fields")
    if fact["protocol_version"] != 3 or fact["status"] != "planned":
        raise ValueError("operation reservation protocol or status is invalid")
    if (fact["run_id"] != run_id or fact["operation_id"] != operation_id
            or not re.fullmatch(r"op-[0-9a-f]{32}", str(fact["operation_id"]))
            or not re.fullmatch(r"s-[0-9a-f]{32}", str(fact["stage_id"]))):
        raise ValueError("operation reservation identity mismatch")
    if fact["role"] not in {"architect", "researcher", "implementer", "implementer-lite", "mechanic", "reviewer"}:
        raise ValueError("operation reservation role is invalid")
    request = fact["request"]
    binding = fact["adapter_binding"]
    if not isinstance(request, dict) or set(request) != {"path", "sha256"}:
        raise ValueError("operation reservation request binding is invalid")
    if request["path"] != f"requests/{operation_id}.json":
        raise ValueError("operation-specific request path is required")
    if (not _safe_relative(request.get("path"))
            or not isinstance(request.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", request["sha256"])
            or request["sha256"] != fact["request_digest"]):
        raise ValueError("operation reservation request binding is invalid")
    if not _valid_adapter_binding(binding):
        raise ValueError("adapter binding must contain nonempty strings")
    request_bytes = _read_contained(repo, run_id, request["path"])
    if hashlib.sha256(request_bytes).hexdigest() != request["sha256"]:
        raise ValueError("operation reservation request bytes changed")
    try:
        packet = json.loads(request_bytes.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("operation request packet is malformed") from error
    if canonical_json(packet) != request_bytes:
        raise ValueError("operation request packet is not canonical")
    expected = {"run_id": run_id, "operation_id": operation_id, "stage_id": fact["stage_id"],
                "role": fact["role"], "adapter_binding": binding}
    if any(packet.get(key) != value for key, value in expected.items()) or "request_digest" in packet:
        raise ValueError("operation request packet does not match reservation")
    state, bundle = _load_run_context(repo, run_id)
    if packet.get("bundle_digest") != state["bundle_digest"]:
        raise ValueError("operation request bundle differs from retained run context")
    if not isinstance(packet.get("scope_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", packet["scope_digest"]):
        raise ValueError("operation request scope digest is invalid")
    if "node_id" in packet and (not isinstance(packet["node_id"], str) or not re.fullmatch(r"n-[0-9a-f]{32}", packet["node_id"])):
        raise ValueError("operation request node binding is invalid")
    if packet.get("node_id") is not None and ("graph" not in packet or "approved_plan" not in packet):
        raise ValueError("node-scoped reservation lacks approved graph and plan binding")
    if validate_current_authority:
        attempt = next((row for row in reversed(state["history"]) if row["stage_id"] == packet.get("stage_id")), None)
        if attempt is None:
            raise ValueError("operation request does not resolve to retained run attempt")
        _validate_packet_authority(packet, state, attempt, bundle)
    _validate_packet_inputs(repo, run_id, operation_id, packet, bundle)
    return packet

def _persist_request_locked(repo: Path, run_id: str, operation_id: str, packet: Mapping[str, Any]) -> tuple[str, str]:
    """Publish canonical request bytes and cited input evidence before reservation."""
    run_id, operation_id = _id(run_id, "run_id"), _id(operation_id, "operation_id")
    if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
        raise ValueError("invalid operation_id")
    packet = copy.deepcopy(dict(packet))
    state, bundle = _load_run_context(Path(repo), run_id)
    stage_id = packet.get("stage_id")
    attempt = next((item for item in reversed(state["history"]) if item["stage_id"] == stage_id), None)
    if attempt is None or attempt["status"] != "planned" or attempt["role"] != packet.get("role"):
        raise ValueError("request must bind an existing planned attempt and role")
    if packet.get("bundle_digest") != state["bundle_digest"] or packet.get("scope_digest") != attempt["scope_digest"]:
        raise ValueError("request bundle or scope differs from run attempt")
    if packet.get("node_id", None) != attempt.get("node_id") or "request_digest" in packet:
        raise ValueError("request node binding or digest shape is invalid")
    if packet.get("run_id") != run_id or packet.get("operation_id") != operation_id:
        raise ValueError("request identity does not match publication target")
    if not _valid_adapter_binding(packet.get("adapter_binding")):
        raise ValueError("adapter binding must contain nonempty strings")
    _validate_packet_authority(packet, state, attempt, bundle)
    _validate_state_snapshot(Path(repo), run_id, state, bundle)
    _publish_request_inputs(Path(repo), run_id, operation_id, packet)
    _validate_packet_inputs(Path(repo), run_id, operation_id, packet, bundle)
    body = canonical_json(packet)
    digest = hashlib.sha256(body).hexdigest()
    run, fds = _run_dir(repo, run_id, create=True)
    try:
        requests = _open_dir(run, "requests", create=True)
        try:
            _publish_immutable(requests, f"{operation_id}.json", body)
        finally:
            os.close(requests)
        os.fsync(run)
    finally:
        _close(fds)
    return f"requests/{operation_id}.json", digest

def persist_request(repo: Path, run_id: str, operation_id: str, packet: Mapping[str, Any]) -> tuple[str, str]:
    repo = Path(repo)
    run_id, operation_id = _id(run_id, "run_id"), _id(operation_id, "operation_id")
    with _locked(repo, run_id):
        return _persist_request_locked(repo, run_id, operation_id, packet)

def _publish_request_inputs(repo: Path, run_id: str, operation_id: str, packet: dict[str, Any]) -> None:
    inputs = packet.get("inputs", [])
    if not isinstance(inputs, list):
        raise ValueError("operation request inputs are invalid")
    if not inputs:
        return
    run, fds = _run_dir(repo, run_id, create=True)
    try:
        root = _open_dir(run, "request-inputs", create=True)
        try:
            operation = _open_dir(root, operation_id, create=True)
            try:
                published = []
                for index, ref in enumerate(inputs):
                    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
                            or not _safe_relative(ref.get("path")) or not isinstance(ref.get("sha256"), str)
                            or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])):
                        raise ValueError("operation request input reference is invalid")
                    data = _read_contained(repo, run_id, ref["path"])
                    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
                        raise ValueError("request input evidence changed")
                    name = f"{index:04d}.bin"
                    try:
                        _publish_immutable(operation, name, data)
                    except FileExistsError:
                        if _read_file(operation, name) != data:
                            raise ValueError("request input publication conflict")
                    published.append({"path": f"request-inputs/{operation_id}/{name}",
                                      "sha256": ref["sha256"], "source_path": ref["path"]})
                packet["inputs"] = published
            finally:
                os.close(operation)
        finally:
            os.close(root)
    finally:
        _close(fds)

def _publish_immutable(directory: int, name: str, data: bytes) -> None:
    _atomic_write_at(directory, name, data, replace=False)

def reserve_operation(repo: Path, run_id: str, operation_id: str, stage_id: str, role: str, request: Mapping[str, str], adapter_binding: Mapping[str, str]) -> dict[str, Any]:
    """Atomically bind a persisted request to one repository-unique operation ID."""
    repo, run_id, operation_id = Path(repo), _id(run_id, "run_id"), _id(operation_id, "operation_id")
    if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id) or not re.fullmatch(r"s-[0-9a-f]{32}", stage_id):
        raise ValueError("invalid stage_id or operation_id")
    stage_id = _id(stage_id, "stage_id")
    request = dict(request)
    adapter_binding = dict(adapter_binding)
    if set(request) != {"path", "sha256"} or request["path"] != f"requests/{operation_id}.json":
        raise ValueError("operation-specific request path is required")
    if not _valid_adapter_binding(adapter_binding):
        raise ValueError("adapter binding must contain nonempty strings")
    body = canonical_json({"protocol_version": 3, "operation_id": operation_id, "run_id": run_id, "stage_id": stage_id,
                           "role": role, "request_digest": request["sha256"], "status": "planned",
                           "request": request, "adapter_binding": adapter_binding})
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        attempt = next((item for item in reversed(state["history"]) if item["stage_id"] == stage_id), None)
        if attempt is None or attempt["status"] != "planned" or attempt["role"] != role:
            raise ValueError("reservation must bind an existing planned attempt and role")
        request_packet = _read_contained(repo, run_id, request["path"])
        try:
            parsed_packet = json.loads(request_packet.decode("utf-8"), object_pairs_hook=_unique_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("request packet is invalid") from error
        if canonical_json(parsed_packet) != request_packet or hashlib.sha256(request_packet).hexdigest() != request["sha256"]:
            raise ValueError("request packet bytes are noncanonical or mismatched")
        expected = {"run_id": run_id, "operation_id": operation_id, "stage_id": stage_id,
                    "role": role, "bundle_digest": state["bundle_digest"],
                    "scope_digest": attempt["scope_digest"], "adapter_binding": dict(adapter_binding)}
        if parsed_packet.get("node_id") != attempt.get("node_id") or "request_digest" in parsed_packet:
            raise ValueError("request node binding or digest shape is invalid")
        if any(parsed_packet.get(key) != value for key, value in expected.items()):
            raise ValueError("request packet differs from reservation binding")
        _validate_packet_authority(parsed_packet, state, attempt, _load_run_context(repo, run_id)[1])
        _validate_packet_inputs(repo, run_id, operation_id, parsed_packet, _load_run_context(repo, run_id)[1])
        runs, fds = _runs_dir(repo, create=False)
        try:
            for entry in os.listdir(runs):
                if not _NAME.fullmatch(entry):
                    raise ValueError("unreadable run ownership namespace")
                owner_run, owner_fds = _run_dir(repo, entry, create=False)
                try:
                    try:
                        invocation_root = _open_dir(owner_run, "invocations")
                    except FileNotFoundError:
                        continue
                    try:
                        for op in os.listdir(invocation_root):
                            if not re.fullmatch(r"op-[0-9a-f]{32}", op):
                                raise ValueError("malformed operation ownership")
                            operation = _open_dir(invocation_root, op)
                            try:
                                planned = _read_file(operation, "planned.json")
                                fact = json.loads(planned.decode("utf-8"), object_pairs_hook=_unique_pairs)
                                if canonical_json(fact) != planned:
                                    raise ValueError("operation reservation is not canonical")
                                _validate_reservation(repo, entry, op, fact, validate_current_authority=False)
                                if op == operation_id:
                                    raise ValueError("operation ID is already reserved")
                                if fact.get("run_id") == run_id and fact.get("stage_id") == stage_id:
                                    raise ValueError("attempt already has an operation reservation")
                            finally:
                                os.close(operation)
                    finally:
                        os.close(invocation_root)
                finally:
                    _close(owner_fds)
            run, run_fds = _run_dir(repo, run_id, create=True)
            try:
                invocations = _open_dir(run, "invocations", create=True)
                try:
                    operation = _open_dir(invocations, operation_id, create=True)
                    try:
                        _publish_immutable(operation, "planned.json", body)
                    finally:
                        os.close(operation)
                finally:
                    os.close(invocations)
            finally:
                _close(run_fds)
        finally:
            _close(fds)
    return json.loads(body)

def publish_uncertainty(repo: Path, run_id: str, state: Mapping[str, Any], expected_revision: int, operation_id: str) -> None:
    """Durably publish the uncertainty fact and state pointer; never dispatches."""
    run_id, operation_id = _id(run_id, "run_id"), _id(operation_id, "operation_id")
    if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
        raise ValueError("invalid operation_id")
    repo = Path(repo)
    with _locked(repo, run_id):
        current = load_state(repo, run_id)
        if current["revision"] != expected_revision:
            raise ConcurrentModificationError("run revision changed")
        proposed_bytes = canonical_json(dict(state))
        proposed_digest = _routing_digest(proposed_bytes, run_id)
        if proposed_digest != current["bundle_digest"]:
            raise ValueError("uncertain state must preserve run bundle digest")
        proposed_state, proposed_bundle = _load_run_context(repo, run_id, proposed_bytes)
        if proposed_state["revision"] != expected_revision + 1 or proposed_state["run_id"] != run_id:
            raise ValueError("uncertain state revision or run ID is invalid")
        _validate_state_snapshot(repo, run_id, proposed_state, proposed_bundle)
        if (proposed_state["bundle_digest"] != current["bundle_digest"]
                or proposed_state["workflow"] != current["workflow"]
                or proposed_state["history"][:len(current["history"])] != current["history"]):
            raise ValueError("uncertain state must preserve run bindings and history prefix")
        if any(proposed_state.get(field) != current.get(field) for field in _AUTHORITY_FIELDS):
            raise ValueError("uncertain state must preserve graph and approved plan bindings and snapshot relationships")
        if len(proposed_state["history"]) <= len(current["history"]):
            raise ValueError("uncertain state must append an observation")
        run, fds = _run_dir(repo, run_id, create=False)
        try:
            invocations = _open_dir(run, "invocations")
            try:
                operation = _open_dir(invocations, operation_id)
            finally:
                os.close(invocations)
            try:
                planned_bytes = _read_file(operation, "planned.json")
                planned = json.loads(planned_bytes.decode("utf-8"), object_pairs_hook=_unique_pairs)
                packet = _validate_reservation(repo, run_id, operation_id, planned)
                uncertain_bytes = canonical_json({**planned, "status": "dispatch-uncertain"})
                required_refs = {
                    f"invocations/{operation_id}/planned.json": hashlib.sha256(planned_bytes).hexdigest(),
                    planned["request"]["path"]: planned["request_digest"],
                }
                for ref in packet.get("inputs", []):
                    required_refs[ref["path"]] = ref["sha256"]
                for field in ("graph", "approved_plan", "accepted_snapshot"):
                    if field in packet:
                        ref = packet[field]
                        required_refs[ref["path"]] = ref["sha256"]
                required_refs[f"invocations/{operation_id}/dispatch-uncertain.json"] = hashlib.sha256(uncertain_bytes).hexdigest()
            finally:
                os.close(operation)
        finally:
            _close(fds)
        new_rows = proposed_state["history"][len(current["history"]):]
        if len(new_rows) != 1:
            raise ValueError("uncertainty publication requires exactly one reserved attempt observation")
        observation = new_rows[0]
        attempt = next((row for row in reversed(current["history"]) if row["stage_id"] == planned["stage_id"]), None)
        if attempt is None or attempt["status"] != "planned" or attempt["role"] != planned["role"]:
            raise ValueError("operation must reserve an existing planned attempt")
        if observation is None or observation.get("status") != "dispatch-uncertain":
            raise ValueError("uncertain state must append matching attempt observation")
        if any(observation.get(key) != attempt.get(key) for key in ("stage_id", "stage_kind", "role", "scope_digest", "node_id")):
            raise ValueError("uncertain observation changed attempt binding")
        _validate_packet_authority(packet, current, attempt, _load_run_context(repo, run_id)[1])
        cited = {ref.get("path"): ref.get("sha256") for ref in observation.get("evidence", [])}
        if any(cited.get(path) != digest for path, digest in required_refs.items()):
            raise ValueError("uncertain observation must cite request and immutable invocation facts")
        marker_run, marker_fds = _run_dir(repo, run_id, create=False)
        try:
            marker_invocations = _open_dir(marker_run, "invocations")
            try:
                marker_operation = _open_dir(marker_invocations, operation_id)
            finally:
                os.close(marker_invocations)
            try:
                _publish_immutable(marker_operation, "dispatch-uncertain.json", uncertain_bytes)
            finally:
                os.close(marker_operation)
        finally:
            _close(marker_fds)
        _publish_state_locked(repo, run_id, proposed_state, expected_revision, allow_dispatch_uncertain=True)
