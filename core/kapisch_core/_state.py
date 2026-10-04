from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from ._authority import _unique_pairs, _validate_state_snapshot
from ._locking import _locked
from .bundle import canonical_json
from .storage import (
    _atomic_write_at,
    _close,
    _id,
    _read_contained,
    _read_file,
    _run_dir,
    _safe_relative,
    load_bundle,
)

_MAX_HISTORY = 10_000


class ConcurrentModificationError(RuntimeError):
    """Expected run revision or immutable prefix no longer matches."""

class RunState(dict[str, Any]):
    """JSON-compatible v3 run state."""

def _validate_history(history: list[Any], workflow: str) -> None:
    required = {"stage_id", "stage_kind", "sequence", "role", "status", "producer", "evidence", "scope_digest"}
    allowed = required | {"node_id", "retry_of_stage_id"}
    kinds = {"research", "design", "implement", "review", "final", "gate", "bounded-delegate"}
    roles = {"architect", "researcher", "implementer", "implementer-lite", "mechanic", "reviewer"}
    statuses = {"planned", "dispatch-uncertain", "complete", "blocked", "failed", "interrupted"}
    attempts: dict[str, dict[str, Any]] = {}
    retries: set[str] = set()
    last_observations: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(history):
        if not isinstance(row, dict) or set(row) - allowed or required - row.keys():
            raise ValueError("stage observation has missing or unknown fields")
        if row["sequence"] != index or isinstance(row["sequence"], bool):
            raise ValueError("run history must have contiguous ordered sequence")
        if not re.fullmatch(r"s-[0-9a-f]{32}", str(row["stage_id"])):
            raise ValueError("invalid stage_id")
        if (not isinstance(row["stage_kind"], str) or row["stage_kind"] not in kinds
                or not isinstance(row["role"], str) or row["role"] not in roles
                or not isinstance(row["status"], str) or row["status"] not in statuses):
            raise ValueError("invalid stage vocabulary")
        if "node_id" in row and (not isinstance(row["node_id"], str) or not re.fullmatch(r"n-[0-9a-f]{32}", row["node_id"])):
            raise ValueError("invalid node_id")
        if "retry_of_stage_id" in row and (not isinstance(row["retry_of_stage_id"], str) or not re.fullmatch(r"s-[0-9a-f]{32}", row["retry_of_stage_id"])):
            raise ValueError("invalid retry_of_stage_id")
        if row["producer"] != "controller" or not isinstance(row["scope_digest"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["scope_digest"]):
            raise ValueError("invalid stage producer or scope digest")
        if not isinstance(row["evidence"], list):
            raise ValueError("stage evidence must be an array")
        for evidence in row["evidence"]:
            if (not isinstance(evidence, dict) or set(evidence) != {"kind", "path", "sha256"}
                    or not all(isinstance(evidence[key], str) and evidence[key] for key in ("kind", "path"))
                    or evidence["path"].startswith("/") or "\\" in evidence["path"]
                    or any(part in {"", ".", ".."} for part in evidence["path"].split("/"))
                    or not isinstance(evidence["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", evidence["sha256"])):
                raise ValueError("invalid stage evidence reference")
        if workflow != "milestone" and "node_id" in row:
            raise ValueError("graph-free workflow cannot contain node_id")
        identity = {key: row[key] for key in ("stage_id", "stage_kind", "role", "scope_digest", "node_id", "retry_of_stage_id") if key in row}
        existing = attempts.get(row["stage_id"])
        if existing is None:
            if row["status"] != "planned":
                raise ValueError("first stage observation must be planned")
            predecessor = row.get("retry_of_stage_id")
            if predecessor is not None:
                prior = attempts.get(predecessor)
                if prior is None or predecessor in retries or prior["status"] not in {"failed", "blocked", "interrupted"}:
                    raise ValueError("retry predecessor is missing, branched, or ineligible")
                prior_identity = prior["identity"]
                if any(identity.get(key) != prior_identity.get(key) for key in ("stage_kind", "role", "scope_digest", "node_id")):
                    raise ValueError("retry changed attempt binding")
                retries.add(predecessor)
            attempts[row["stage_id"]] = {"identity": identity, "status": row["status"], "evidence": row["evidence"]}
        else:
            if existing["status"] in {"complete", "blocked", "failed", "interrupted"}:
                raise ValueError("terminal attempt is immutable")
            prior_evidence = existing["evidence"]
            previous = last_observations.get(row["stage_id"])
            same_observation = previous is not None and {key: value for key, value in row.items() if key != "sequence"} == {
                key: value for key, value in previous.items() if key != "sequence"
            }
            if row["status"] == "planned" or identity != existing["identity"] or same_observation:
                raise ValueError("duplicate creation, changed binding, or duplicate observation")
            if row["evidence"][:len(prior_evidence)] != prior_evidence:
                raise ValueError("stage evidence is not cumulative")
            existing["status"] = row["status"]
            existing["evidence"] = row["evidence"]
        last_observations[row["stage_id"]] = row

def _validate_ref(value: Any, keys: set[str], id_key: str | None = None) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("invalid immutable artifact reference")
    if id_key and (not isinstance(value[id_key], str) or not value[id_key]):
        raise ValueError("invalid immutable artifact identity")
    if "path" in value and not _safe_relative(value["path"]):
        raise ValueError("artifact reference path escapes run")
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise ValueError("invalid artifact reference digest")

def _parse_state(data: bytes, *, bundle: Any) -> RunState:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid run state JSON") from error
    if not isinstance(value, dict) or canonical_json(value) != data:
        raise ValueError("run state is not canonical JSON object")
    required = {"protocol_version", "run_id", "bundle_digest", "workflow", "revision", "history", "identity_contract"}
    authority_contract = bundle.payload.get("authority_contract")
    global_authority = authority_contract == "global-authority/1"
    allowed = required | {"accepted_snapshot", "approved_plan", "amends", "supersedes", "graph"}
    if global_authority:
        allowed |= {"acceptance_ref", "scope_ref", "work_scope_refs"}
    if required - value.keys() or value.keys() - allowed:
        raise ValueError("run state has missing or unknown fields")
    if value["protocol_version"] != 3 or value["identity_contract"] != "stage-attempt/1":
        raise ValueError("unsupported run protocol or identity contract")
    if not isinstance(value["workflow"], str) or value["workflow"] not in {"advisory", "review", "task", "milestone"}:
        raise ValueError("invalid workflow")
    if not isinstance(value["revision"], int) or isinstance(value["revision"], bool) or value["revision"] < 0:
        raise ValueError("invalid run revision")
    if not isinstance(value["history"], list) or len(value["history"]) > _MAX_HISTORY:
        raise ValueError("invalid or over-limit run history")
    if not re.fullmatch(r"[0-9a-f]{64}", value["bundle_digest"]):
        raise ValueError("invalid bundle digest")
    _id(value["run_id"], "run_id")
    if global_authority:
        # These are validated against the retained run schema by the caller.
        pass
    else:
        for field, id_key in (("accepted_snapshot", "snapshot_id"), ("approved_plan", "plan_id")):
            if field in value:
                _validate_ref(value[field], {id_key, "path", "sha256"}, id_key)
        has_snapshot = "accepted_snapshot" in value
        has_relationships = "amends" in value or "supersedes" in value
        if has_snapshot and not {"amends", "supersedes"} <= value.keys() or has_relationships and not has_snapshot:
            raise ValueError("accepted snapshot and relationship references must appear together")
        for field in ("amends", "supersedes"):
            if field in value and (not isinstance(value[field], list) or any(not isinstance(item, str) or not item for item in value[field]) or len(set(value[field])) != len(value[field])):
                raise ValueError(f"invalid {field} relationship list")
    if "graph" in value:
        _validate_ref(value["graph"], {"path", "sha256"})
    if value["workflow"] != "milestone" and "graph" in value:
        raise ValueError("graph is only valid for milestone runs")
    _validate_history(value["history"], value["workflow"])
    if any(row["stage_kind"] == "implement" and row.get("node_id") is None for row in value["history"] if value["workflow"] == "milestone"):
        raise ValueError("milestone implementation requires a node")
    if any("node_id" in row for row in value["history"]) and "graph" not in value:
        raise ValueError("node-scoped history requires a graph reference")
    return RunState(value)

def _load_run_context(repo: Path, run_id: str, data: bytes | None = None) -> tuple[RunState, Any]:
    if data is None:
        run, fds = _run_dir(Path(repo), run_id, create=False)
        try:
            data = _read_file(run, "state.json")
        finally:
            _close(fds)
    try:
        routing = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid run state JSON") from error
    if (not isinstance(routing, dict) or canonical_json(routing) != data
            or routing.get("run_id") != run_id
            or not isinstance(routing.get("bundle_digest"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", routing["bundle_digest"])):
        raise ValueError("invalid run state routing identity")
    bundle = load_bundle(Path(repo), routing["bundle_digest"])
    from ._validation_schema import _validate_identity_contract, _validate_schema
    _validate_identity_contract(bundle)
    state = _parse_state(data, bundle=bundle)
    _validate_schema(state, "run", bundle)
    return state, bundle

def load_state(repo: Path, run_id: str) -> RunState:
    run_id = _id(run_id, "run_id")
    run, fds = _run_dir(Path(repo), run_id, create=False)
    try:
        state, bundle = _load_run_context(Path(repo), run_id)
        _validate_state_snapshot(Path(repo), run_id, state, bundle)
        return state
    finally:
        _close(fds)

def _publish_state_locked(repo: Path, run_id: str, state: Mapping[str, Any], expected_revision: int, *, allow_dispatch_uncertain: bool = False) -> None:
    run, fds = _run_dir(repo, run_id, create=True)
    try:
        current_bytes: bytes | None
        try:
            current_bytes = _read_file(run, "state.json")
        except FileNotFoundError:
            current_bytes = None
        if current_bytes is None:
            if expected_revision != -1:
                raise ConcurrentModificationError("run state does not exist")
            previous = None
        else:
            previous, previous_bundle = _load_run_context(repo, run_id, current_bytes)
            _validate_state_snapshot(repo, run_id, previous, previous_bundle)
            if previous["revision"] != expected_revision:
                raise ConcurrentModificationError("run revision changed")
        proposed_bytes = canonical_json(dict(state))
        proposed_digest = _routing_digest(proposed_bytes, run_id)
        if previous is not None and proposed_digest != previous["bundle_digest"]:
            raise ValueError("run bundle and workflow are immutable")
        proposed_bundle = load_bundle(repo, proposed_digest)
        from ._validation_schema import _validate_identity_contract, _validate_schema
        _validate_identity_contract(proposed_bundle)
        proposed = _parse_state(proposed_bytes, bundle=proposed_bundle)
        _validate_schema(proposed, "run", proposed_bundle)
        if proposed["run_id"] != run_id:
            raise ValueError("run state ID does not match requested run")
        _validate_state_snapshot(repo, run_id, proposed, proposed_bundle)
        if proposed["revision"] != expected_revision + 1:
            raise ValueError("new run revision must increment by one")
        load_bundle(repo, proposed["bundle_digest"])
        if previous is not None:
            if proposed["bundle_digest"] != previous["bundle_digest"] or proposed["workflow"] != previous["workflow"]:
                raise ValueError("run bundle and workflow are immutable")
            old_history = previous["history"]
            new_history = proposed["history"]
            has_node_attempt = any("node_id" in row for row in old_history)
            has_operation_binding = any(
                evidence["path"].startswith("invocations/")
                for row in old_history for evidence in row["evidence"]
            )
            if (has_node_attempt or has_operation_binding) and any(
                proposed.get(field) != previous.get(field) for field in ("graph", "approved_plan")
            ):
                reason = "after operation binding" if has_operation_binding else "after node attempt creation"
                raise ValueError(f"execution authority references are immutable {reason}")
            if len(new_history) < len(old_history) or new_history[:len(old_history)] != old_history:
                raise ValueError("run history prefix is immutable")
        _validate_history(proposed["history"], proposed["workflow"])
        if not allow_dispatch_uncertain and any(
            row["status"] == "dispatch-uncertain" for row in proposed["history"][len(previous["history"]) if previous else 0:]
        ):
            raise ValueError("dispatch-uncertain state must use publish_uncertainty")
        for observation in proposed["history"]:
            for evidence in observation["evidence"]:
                data = _read_contained(repo, run_id, evidence["path"])
                if hashlib.sha256(data).hexdigest() != evidence["sha256"]:
                    raise ValueError("run history evidence digest mismatch")
        _write_atomic(run, "state.json", canonical_json(dict(proposed)), replace=True)
    finally:
        _close(fds)

def publish_state(repo: Path, run_id: str, state: Mapping[str, Any], expected_revision: int) -> None:
    repo = Path(repo)
    run_id = _id(run_id, "run_id")
    with _locked(repo, run_id):
        _publish_state_locked(repo, run_id, state, expected_revision)

def _routing_digest(data: bytes, run_id: str) -> str:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid run state JSON") from error
    if not isinstance(value, dict) or canonical_json(value) != data or value.get("run_id") != run_id or not isinstance(value.get("bundle_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["bundle_digest"]):
        raise ValueError("invalid run state routing identity")
    return value["bundle_digest"]

def _write_atomic(directory: int, name: str, data: bytes, *, replace: bool) -> None:
    _atomic_write_at(directory, name, data, replace=replace)
