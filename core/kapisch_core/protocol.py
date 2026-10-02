from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from .bundle import canonical_json
from .storage import _atomic_write_at, load_bundle

_MAX_HISTORY = 10_000
_AUTHORITY_FIELDS = ("graph", "approved_plan", "accepted_snapshot", "amends", "supersedes")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


class ConcurrentModificationError(RuntimeError):
    """Expected run revision or immutable prefix no longer matches."""


class RunState(dict[str, Any]):
    """JSON-compatible v3 run state."""


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"invalid {label}")
    return value


def _acquire_lock(fd: int) -> None:
    try:
        import fcntl
    except ImportError:
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX)


def _release_lock(fd: int) -> None:
    try:
        import fcntl
    except ImportError:
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _open_dir(parent: int, name: str, *, create: bool = False) -> int:
    try:
        return os.open(name, _DIR_FLAGS, dir_fd=parent)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
        return os.open(name, _DIR_FLAGS, dir_fd=parent)


def _open_tree(repo: Path, *components: str, create: bool = False) -> tuple[int, list[int]]:
    if not (hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd):
        raise OSError("safe descriptor-relative authority storage is unsupported on this platform")
    descriptors = [os.open(os.fspath(repo), _DIR_FLAGS)]
    try:
        for component in (".kapisch", "v3", *components):
            descriptors.append(_open_dir(descriptors[-1], component, create=create))
        return descriptors[-1], descriptors
    except BaseException:
        for fd in reversed(descriptors):
            os.close(fd)
        raise


def _close(fds: list[int]) -> None:
    for fd in reversed(fds):
        os.close(fd)


@contextmanager
def _locked(repo: Path, run_id: str | None = None) -> Iterator[None]:
    # Always lock repository namespace before individual run namespace.
    lock_dir, fds = _open_tree(repo, "locks", create=True)
    locks: list[int] = []
    try:
        for name in ("repository.lock", f"run-{run_id}.lock" if run_id else None):
            if name is None:
                continue
            fd = os.open(name, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=lock_dir)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise ValueError("authority lock is not a regular file")
            _acquire_lock(fd)
            locks.append(fd)
        yield
    finally:
        for fd in reversed(locks):
            _release_lock(fd)
            os.close(fd)
        _close(fds)


def _write_atomic(directory: int, name: str, data: bytes, *, replace: bool) -> None:
    _atomic_write_at(directory, name, data, replace=replace)


def _read_file(directory: int, name: str) -> bytes:
    fd = os.open(name, _FILE_FLAGS, dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("authority artifact is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _valid_adapter_binding(binding: Any) -> bool:
    return (isinstance(binding, Mapping) and set(binding) == {"adapter_id", "lookup_context"}
            and all(isinstance(binding[field], str) and binding[field] for field in ("adapter_id", "lookup_context")))


def _validate_packet_inputs(repo: Path, run_id: str, operation_id: str, packet: Mapping[str, Any]) -> None:
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


def _snapshot_document(data: bytes, expected_id: str | None = None) -> dict[str, Any]:
    try:
        snapshot = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("accepted snapshot artifact is malformed") from error
    required = {"protocol_version", "snapshot_id", "decision", "scope", "dependencies", "amends", "supersedes"}
    if (not isinstance(snapshot, dict) or set(snapshot) != required or type(snapshot["protocol_version"]) is not int
            or snapshot["protocol_version"] != 3 or not isinstance(snapshot["snapshot_id"], str)
            or not snapshot["snapshot_id"] or (expected_id is not None and snapshot["snapshot_id"] != expected_id)
            or not isinstance(snapshot["decision"], str) or not snapshot["decision"]
            or not isinstance(snapshot["scope"], str) or not snapshot["scope"]
            or canonical_json(snapshot) != data):
        raise ValueError("accepted snapshot artifact identity or canonical shape is invalid")
    for field in ("amends", "supersedes"):
        values = snapshot[field]
        if (not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values)
                or len(values) != len(set(values))):
            raise ValueError("accepted snapshot relationships are invalid")
    if not isinstance(snapshot["dependencies"], list):
        raise ValueError("accepted snapshot dependencies are invalid")
    for dependency in snapshot["dependencies"]:
        allowed = {"kind", "path", "sha256", "decision_id", "snapshot_id"}
        if (not isinstance(dependency, dict) or not {"kind", "path", "sha256"} <= set(dependency)
                or set(dependency) - allowed or not all(isinstance(dependency[key], str) and dependency[key]
                                                        for key in ("kind", "path", "sha256"))
                or not _safe_relative(dependency["path"])
                or not re.fullmatch(r"[0-9a-f]{64}", dependency["sha256"])
                or any(key in dependency and (not isinstance(dependency[key], str) or not dependency[key])
                       for key in ("decision_id", "snapshot_id"))
                or (dependency["kind"] == "decision" and "decision_id" not in dependency)
                or (dependency["kind"] == "snapshot" and "snapshot_id" not in dependency)):
            raise ValueError("accepted snapshot dependency reference is invalid")
    return snapshot


def _validate_snapshot_authority(repo: Path, run_id: str, ref: Mapping[str, Any],
                                 amends: Any, supersedes: Any) -> None:
    try:
        data = _read_contained(repo, run_id, ref["path"])
    except OSError as error:
        raise ValueError("accepted snapshot artifact is unavailable") from error
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("accepted snapshot artifact digest changed")

    root_snapshot = _snapshot_document(data, ref["snapshot_id"])
    if root_snapshot["amends"] != amends or root_snapshot["supersedes"] != supersedes:
        raise ValueError("snapshot relationship bindings do not match artifact")

    active: set[str] = set()
    digests: dict[str, str] = {}
    validated: dict[str, dict[str, Any]] = {}

    def validate(snapshot_id: str, snapshot_bytes: bytes) -> dict[str, Any]:
        digest = hashlib.sha256(snapshot_bytes).hexdigest()
        if snapshot_id in active:
            raise ValueError("snapshot dependency cycle detected")
        if snapshot_id in digests and digests[snapshot_id] != digest:
            raise ValueError("snapshot ID has ambiguous artifacts")
        digests[snapshot_id] = digest
        if snapshot_id in validated:
            return validated[snapshot_id]
        snapshot = _snapshot_document(snapshot_bytes, snapshot_id)
        active.add(snapshot_id)
        snapshot_refs = {}
        for dependency in snapshot["dependencies"]:
            try:
                target = _read_contained(repo, run_id, dependency["path"])
            except OSError as error:
                raise ValueError("snapshot dependency artifact is unavailable") from error
            if hashlib.sha256(target).hexdigest() != dependency["sha256"]:
                raise ValueError("snapshot dependency artifact digest changed")
            identity = None
            if "decision_id" in dependency or "snapshot_id" in dependency:
                try:
                    identity = json.loads(target.decode("utf-8"), object_pairs_hook=_unique_pairs)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError("snapshot dependency identity artifact is malformed") from error
                if not isinstance(identity, dict) or canonical_json(identity) != target:
                    raise ValueError("snapshot dependency identity artifact is malformed")
                if (("decision_id" in dependency and dependency["kind"] != "snapshot"
                     and identity.get("decision_id") != dependency["decision_id"])
                        or ("snapshot_id" in dependency and dependency["kind"] != "decision"
                            and identity.get("snapshot_id") != dependency["snapshot_id"])):
                    raise ValueError("snapshot dependency identity does not match artifact")
            if dependency["kind"] == "snapshot":
                child_id = dependency["snapshot_id"]
                if child_id in snapshot_refs:
                    raise ValueError("accepted snapshot has ambiguous relationship targets")
                child_snapshot = validate(child_id, target)
                snapshot_refs[child_id] = child_snapshot
                if "decision_id" in dependency and not any(
                        row.get("kind") == "decision" and row.get("decision_id") == dependency["decision_id"]
                        for row in child_snapshot["dependencies"]):
                    raise ValueError("snapshot dependency decision binding is unresolved")
        for dependency in snapshot["dependencies"]:
            if dependency["kind"] != "decision" or "snapshot_id" not in dependency:
                continue
            parent_id = dependency["snapshot_id"]
            if parent_id == snapshot_id:
                continue
            parent = snapshot_refs.get(parent_id)
            if parent is None:
                raise ValueError("snapshot dependency snapshot binding is unresolved")
            if not any(row.get("kind") == "decision"
                       and row.get("decision_id") == dependency["decision_id"]
                       and row.get("path") == dependency["path"]
                       and row.get("sha256") == dependency["sha256"]
                       and row.get("snapshot_id", parent_id) == parent_id
                       for row in parent["dependencies"]):
                raise ValueError("snapshot decision is not bound through referenced snapshot")
        for related_id in (*snapshot["amends"], *snapshot["supersedes"]):
            if related_id == snapshot_id or related_id not in snapshot_refs:
                raise ValueError("snapshot relationship target is unresolved")
        active.remove(snapshot_id)
        validated[snapshot_id] = snapshot
        return snapshot

    # ponytail: recursive walk is bounded by Python's stack; make it iterative if lineages approach that limit.
    try:
        validate(ref["snapshot_id"], data)
    except RecursionError as error:
        raise ValueError("snapshot dependency lineage exceeds supported depth") from error

def _validate_state_snapshot(repo: Path, run_id: str, state: Mapping[str, Any]) -> None:
    if "accepted_snapshot" in state:
        _validate_snapshot_authority(repo, run_id, state["accepted_snapshot"], state["amends"], state["supersedes"])


def _validate_packet_authority(packet: Mapping[str, Any], state: Mapping[str, Any], attempt: Mapping[str, Any]) -> None:
    if any((field in packet) != (field in state) or packet.get(field) != state.get(field)
           for field in ("accepted_snapshot", "amends", "supersedes")):
        raise ValueError("request must bind current accepted snapshot authority")
    if packet.get("node_id") != attempt.get("node_id"):
        raise ValueError("request node binding does not match attempt")
    if attempt.get("node_id") is not None:
        if (state.get("workflow") != "milestone" or "graph" not in state or "approved_plan" not in state
                or packet.get("graph") != state["graph"] or packet.get("approved_plan") != state["approved_plan"]):
            raise ValueError("node-scoped request must bind the approved graph and plan binding")
    elif state.get("workflow") == "milestone":
        for field in ("graph", "approved_plan"):
            if field in state:
                if packet.get(field) != state[field]:
                    raise ValueError("run-wide milestone request must bind current approved authority")
            elif field in packet:
                raise ValueError("run-wide milestone request cites unavailable authority")
    elif "graph" in packet or "approved_plan" in packet:
        raise ValueError("graph references are forbidden in graph-free request")


def _validate_reservation(repo: Path, run_id: str, operation_id: str, fact: Any) -> dict[str, Any]:
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
    bundle_digest = packet.get("bundle_digest")
    if not isinstance(bundle_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", bundle_digest):
        raise ValueError("operation request bundle digest is invalid")
    load_bundle(repo, bundle_digest)
    if not isinstance(packet.get("scope_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", packet["scope_digest"]):
        raise ValueError("operation request scope digest is invalid")
    if "node_id" in packet and (not isinstance(packet["node_id"], str) or not re.fullmatch(r"n-[0-9a-f]{32}", packet["node_id"])):
        raise ValueError("operation request node binding is invalid")
    if packet.get("node_id") is not None and ("graph" not in packet or "approved_plan" not in packet):
        raise ValueError("node-scoped reservation lacks approved graph and plan binding")
    _validate_packet_inputs(repo, run_id, operation_id, packet)
    return packet


def _runs_dir(repo: Path, *, create: bool) -> tuple[int, list[int]]:
    return _open_tree(repo, "runs", create=create)


def _run_dir(repo: Path, run_id: str, *, create: bool) -> tuple[int, list[int]]:
    runs, fds = _runs_dir(repo, create=create)
    try:
        run = _open_dir(runs, _id(run_id, "run_id"), create=create)
        fds.append(run)
        return run, fds
    except BaseException:
        _close(fds)
        raise


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


def _safe_relative(value: Any) -> bool:
    return (isinstance(value, str) and bool(value) and not value.startswith("/") and "\\" not in value
            and "\x00" not in value and all(part not in {"", ".", ".."} for part in value.split("/")))


def _validate_ref(value: Any, keys: set[str], id_key: str | None = None) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("invalid immutable artifact reference")
    if id_key and (not isinstance(value[id_key], str) or not value[id_key]):
        raise ValueError("invalid immutable artifact identity")
    if "path" in value and not _safe_relative(value["path"]):
        raise ValueError("artifact reference path escapes run")
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise ValueError("invalid artifact reference digest")


def _parse_state(data: bytes) -> RunState:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid run state JSON") from error
    if not isinstance(value, dict) or canonical_json(value) != data:
        raise ValueError("run state is not canonical JSON object")
    required = {"protocol_version", "run_id", "bundle_digest", "workflow", "revision", "history", "identity_contract"}
    allowed = required | {"accepted_snapshot", "approved_plan", "amends", "supersedes", "graph"}
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
    for field, id_key in (("accepted_snapshot", "snapshot_id"), ("approved_plan", "plan_id")):
        if field in value:
            _validate_ref(value[field], {id_key, "path", "sha256"}, id_key)
    if "graph" in value:
        _validate_ref(value["graph"], {"path", "sha256"})
    has_snapshot = "accepted_snapshot" in value
    has_relationships = "amends" in value or "supersedes" in value
    if has_snapshot and not {"amends", "supersedes"} <= value.keys() or has_relationships and not has_snapshot:
        raise ValueError("accepted snapshot and relationship references must appear together")
    for field in ("amends", "supersedes"):
        if field in value and (not isinstance(value[field], list) or any(not isinstance(item, str) or not item for item in value[field]) or len(set(value[field])) != len(value[field])):
            raise ValueError(f"invalid {field} relationship list")
    if value["workflow"] != "milestone" and "graph" in value:
        raise ValueError("graph is only valid for milestone runs")
    _validate_history(value["history"], value["workflow"])
    if any(row["stage_kind"] == "implement" and row.get("node_id") is None for row in value["history"] if value["workflow"] == "milestone"):
        raise ValueError("milestone implementation requires a node")
    if any("node_id" in row for row in value["history"]) and "graph" not in value:
        raise ValueError("node-scoped history requires a graph reference")
    return RunState(value)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_state(repo: Path, run_id: str) -> RunState:
    run_id = _id(run_id, "run_id")
    run, fds = _run_dir(Path(repo), run_id, create=False)
    try:
        state = _parse_state(_read_file(run, "state.json"))
        if state["run_id"] != run_id:
            raise ValueError("run state ID does not match requested run")
        load_bundle(Path(repo), state["bundle_digest"])
        _validate_state_snapshot(Path(repo), run_id, state)
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
            previous = _parse_state(current_bytes)
            _validate_state_snapshot(repo, run_id, previous)
            if previous["revision"] != expected_revision:
                raise ConcurrentModificationError("run revision changed")
        proposed = _parse_state(canonical_json(dict(state)))
        if proposed["run_id"] != run_id:
            raise ValueError("run state ID does not match requested run")
        _validate_state_snapshot(repo, run_id, proposed)
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


def _persist_request_locked(repo: Path, run_id: str, operation_id: str, packet: Mapping[str, Any]) -> tuple[str, str]:
    """Publish canonical request bytes and cited input evidence before reservation."""
    run_id, operation_id = _id(run_id, "run_id"), _id(operation_id, "operation_id")
    if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
        raise ValueError("invalid operation_id")
    packet = copy.deepcopy(dict(packet))
    state = load_state(Path(repo), run_id)
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
    _validate_packet_authority(packet, state, attempt)
    _publish_request_inputs(Path(repo), run_id, operation_id, packet)
    _validate_packet_inputs(Path(repo), run_id, operation_id, packet)
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


def _read_contained(repo: Path, run_id: str, relative: str) -> bytes:
    if not isinstance(relative, str) or not relative or relative.startswith("/") or "\\" in relative or "\x00" in relative:
        raise ValueError("request input path must be run-relative")
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        parent = run
        extra: list[int] = []
        parts = relative.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("request input path escapes run")
        for part in parts[:-1]:
            parent = _open_dir(parent, part)
            extra.append(parent)
        try:
            file_fd = os.open(parts[-1], _FILE_FLAGS, dir_fd=parent)
            try:
                if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                    raise ValueError("authority artifact is not a regular file")
                chunks: list[bytes] = []
                while chunk := os.read(file_fd, 1024 * 1024):
                    chunks.append(chunk)
                os.fsync(file_fd)
                for descriptor in [*extra, parent, run]:
                    os.fsync(descriptor)
                return b"".join(chunks)
            finally:
                os.close(file_fd)
        finally:
            _close(extra)
    finally:
        _close(fds)


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
    if set(request) != {"path", "sha256"} or request["path"] != f"requests/{operation_id}.json":
        raise ValueError("operation-specific request path is required")
    if not _valid_adapter_binding(adapter_binding):
        raise ValueError("adapter binding must contain nonempty strings")
    body = canonical_json({"protocol_version": 3, "operation_id": operation_id, "run_id": run_id, "stage_id": stage_id,
                           "role": role, "request_digest": request["sha256"], "status": "planned",
                           "request": dict(request), "adapter_binding": dict(adapter_binding)})
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
        _validate_packet_authority(parsed_packet, state, attempt)
        _validate_packet_inputs(repo, run_id, operation_id, parsed_packet)
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
                                _validate_reservation(repo, entry, op, fact)
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
        proposed_state = _parse_state(canonical_json(dict(state)))
        if proposed_state["revision"] != expected_revision + 1 or proposed_state["run_id"] != run_id:
            raise ValueError("uncertain state revision or run ID is invalid")
        _validate_state_snapshot(repo, run_id, proposed_state)
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
        _validate_packet_authority(packet, current, attempt)
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
        _publish_state_locked(repo, run_id, state, expected_revision, allow_dispatch_uncertain=True)






__all__ = ["ConcurrentModificationError", "RunState", "load_state", "publish_state", "persist_request", "reserve_operation", "publish_uncertainty"]
