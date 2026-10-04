from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .bundle import canonical_json
from .storage import _read_contained, _safe_relative


def _snapshot_document(data: bytes, expected_id: str | None = None) -> dict[str, Any]:
    try:
        snapshot = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("accepted snapshot artifact is malformed") from error
    required = {
        "protocol_version",
        "snapshot_id",
        "decision",
        "scope",
        "dependencies",
        "amends",
        "supersedes",
    }
    if (
        not isinstance(snapshot, dict)
        or set(snapshot) != required
        or type(snapshot["protocol_version"]) is not int
        or snapshot["protocol_version"] != 3
        or not isinstance(snapshot["snapshot_id"], str)
        or not snapshot["snapshot_id"]
        or (expected_id is not None and snapshot["snapshot_id"] != expected_id)
        or not isinstance(snapshot["decision"], str)
        or not snapshot["decision"]
        or not isinstance(snapshot["scope"], str)
        or not snapshot["scope"]
        or canonical_json(snapshot) != data
    ):
        raise ValueError(
            "accepted snapshot artifact identity or canonical shape is invalid"
        )
    for field in ("amends", "supersedes"):
        values = snapshot[field]
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("accepted snapshot relationships are invalid")
    if not isinstance(snapshot["dependencies"], list):
        raise ValueError("accepted snapshot dependencies are invalid")
    for dependency in snapshot["dependencies"]:
        allowed = {"kind", "path", "sha256", "decision_id", "snapshot_id"}
        if (
            not isinstance(dependency, dict)
            or not {"kind", "path", "sha256"} <= set(dependency)
            or set(dependency) - allowed
            or not all(
                isinstance(dependency[key], str) and dependency[key]
                for key in ("kind", "path", "sha256")
            )
            or not _safe_relative(dependency["path"])
            or not re.fullmatch(r"[0-9a-f]{64}", dependency["sha256"])
            or any(
                key in dependency
                and (not isinstance(dependency[key], str) or not dependency[key])
                for key in ("decision_id", "snapshot_id")
            )
            or (dependency["kind"] == "decision" and "decision_id" not in dependency)
            or (dependency["kind"] == "snapshot" and "snapshot_id" not in dependency)
        ):
            raise ValueError("accepted snapshot dependency reference is invalid")
    return snapshot


def _validate_snapshot_authority(
    repo: Path, run_id: str, ref: Mapping[str, Any], amends: Any, supersedes: Any
) -> None:
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
                raise ValueError(
                    "snapshot dependency artifact is unavailable"
                ) from error
            if hashlib.sha256(target).hexdigest() != dependency["sha256"]:
                raise ValueError("snapshot dependency artifact digest changed")
            identity = None
            if "decision_id" in dependency or "snapshot_id" in dependency:
                try:
                    identity = json.loads(
                        target.decode("utf-8"), object_pairs_hook=_unique_pairs
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError(
                        "snapshot dependency identity artifact is malformed"
                    ) from error
                if not isinstance(identity, dict) or canonical_json(identity) != target:
                    raise ValueError(
                        "snapshot dependency identity artifact is malformed"
                    )
                if (
                    "decision_id" in dependency
                    and dependency["kind"] != "snapshot"
                    and identity.get("decision_id") != dependency["decision_id"]
                ) or (
                    "snapshot_id" in dependency
                    and dependency["kind"] != "decision"
                    and identity.get("snapshot_id") != dependency["snapshot_id"]
                ):
                    raise ValueError(
                        "snapshot dependency identity does not match artifact"
                    )
            if dependency["kind"] == "snapshot":
                child_id = dependency["snapshot_id"]
                if child_id in snapshot_refs:
                    raise ValueError(
                        "accepted snapshot has ambiguous relationship targets"
                    )
                child_snapshot = validate(child_id, target)
                snapshot_refs[child_id] = child_snapshot
                if "decision_id" in dependency and not any(
                    row.get("kind") == "decision"
                    and row.get("decision_id") == dependency["decision_id"]
                    for row in child_snapshot["dependencies"]
                ):
                    raise ValueError(
                        "snapshot dependency decision binding is unresolved"
                    )
        for dependency in snapshot["dependencies"]:
            if dependency["kind"] != "decision" or "snapshot_id" not in dependency:
                continue
            parent_id = dependency["snapshot_id"]
            if parent_id == snapshot_id:
                continue
            parent = snapshot_refs.get(parent_id)
            if parent is None:
                raise ValueError("snapshot dependency snapshot binding is unresolved")
            if not any(
                row.get("kind") == "decision"
                and row.get("decision_id") == dependency["decision_id"]
                and row.get("path") == dependency["path"]
                and row.get("sha256") == dependency["sha256"]
                and row.get("snapshot_id", parent_id) == parent_id
                for row in parent["dependencies"]
            ):
                raise ValueError(
                    "snapshot decision is not bound through referenced snapshot"
                )
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
        raise ValueError(
            "snapshot dependency lineage exceeds supported depth"
        ) from error


def _validate_state_snapshot(
    repo: Path, run_id: str, state: Mapping[str, Any], bundle: Any
) -> None:
    if (
        bundle.payload.get("authority_contract") != "global-authority/1"
        and "accepted_snapshot" in state
    ):
        _validate_snapshot_authority(
            repo,
            run_id,
            state["accepted_snapshot"],
            state["amends"],
            state["supersedes"],
        )


def _validate_packet_authority(
    packet: Mapping[str, Any],
    state: Mapping[str, Any],
    attempt: Mapping[str, Any],
    bundle: Any = None,
) -> None:
    if (
        bundle is not None
        and bundle.payload.get("authority_contract") == "global-authority/1"
        and (
            any(
                field in packet
                for field in (
                    "accepted_snapshot",
                    "amends",
                    "supersedes",
                    "approved_plan",
                    "acceptance_ref",
                )
            )
            or any(field in state for field in ("approved_plan", "acceptance_ref"))
        )
    ):
        raise ValueError(
            "unsupported-gate: global authority consumers are not implemented"
        )
    if any(
        (field in packet) != (field in state) or packet.get(field) != state.get(field)
        for field in ("accepted_snapshot", "amends", "supersedes")
    ):
        raise ValueError("request must bind current accepted snapshot authority")
    if packet.get("node_id") != attempt.get("node_id"):
        raise ValueError("request node binding does not match attempt")
    if attempt.get("node_id") is not None:
        if (
            state.get("workflow") != "milestone"
            or "graph" not in state
            or "approved_plan" not in state
            or packet.get("graph") != state["graph"]
            or packet.get("approved_plan") != state["approved_plan"]
        ):
            raise ValueError(
                "node-scoped request must bind the approved graph and plan binding"
            )
    elif state.get("workflow") == "milestone":
        for field in ("graph", "approved_plan"):
            if field in state:
                if packet.get(field) != state[field]:
                    raise ValueError(
                        "run-wide milestone request must bind current approved authority"
                    )
            elif field in packet:
                raise ValueError(
                    "run-wide milestone request cites unavailable authority"
                )
    else:
        if ("approved_plan" in packet) != ("approved_plan" in state) or packet.get(
            "approved_plan"
        ) != state.get("approved_plan"):
            raise ValueError("request must bind current approved plan authority")
        if "graph" in packet:
            raise ValueError("graph references are forbidden in graph-free request")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
