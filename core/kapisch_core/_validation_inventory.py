from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ._authority import _validate_graph_free_request, _validate_packet_authority
from ._invocation import _validate_reservation
from ._invocation_inventory import _LoadedOperation, _read_invocation_inventory
from ._validation_schema import _validate_schema
from .bundle import CoreBundle
from .storage import _close, _open_dir, _run_dir


@dataclass(frozen=True)
class _Citation:
    index: int
    row: Mapping[str, Any]


@dataclass(frozen=True)
class _HistoryIndex:
    first_citation: Mapping[str, _Citation]
    creation_index: Mapping[str, int]
    latest_attempt: Mapping[str, Mapping[str, Any]]
    cited_digests: Mapping[str, str]


@dataclass(frozen=True)
class _OperationInventory:
    facts: Mapping[str, tuple[Any, str]]
    packet: Mapping[str, Any]


def _index_history(history: Sequence[Mapping[str, Any]]) -> _HistoryIndex:
    first: dict[str, _Citation] = {}
    created: dict[str, int] = {}
    latest: dict[str, Mapping[str, Any]] = {}
    cited: dict[str, str] = {}
    for index, row in enumerate(history):
        created.setdefault(row["stage_id"], index)
        latest[row["stage_id"]] = row
        for evidence in row["evidence"]:
            path = evidence["path"]
            first.setdefault(path, _Citation(index, row))
            if path.startswith("invocations/"):
                cited[path] = evidence["sha256"]
    return _HistoryIndex(
        MappingProxyType(first),
        MappingProxyType(created),
        MappingProxyType(latest),
        MappingProxyType(cited),
    )


def _inventory(
    repo: Path,
    run_id: str,
    state: Mapping[str, Any],
    bundle: CoreBundle,
    *,
    validate_current_authority: bool = True,
) -> None:
    """Coordinate independent read, indexing, operation-validation, and chronology phases."""
    history = state["history"]
    authority = MappingProxyType(
        {
            key: state[key]
            for key in (
                "workflow",
                "bundle_digest",
                "graph",
                "approved_plan",
                "accepted_snapshot",
                "amends",
                "supersedes",
            )
            if key in state
        }
    )
    history_index = _index_history(history)
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        try:
            invocations = _open_dir(run, "invocations")
        except FileNotFoundError:
            if any(row["status"] == "dispatch-uncertain" for row in history):
                raise ValueError("uncertain history has no invocation inventory")
            return
        try:
            loaded = _read_invocation_inventory(invocations)
            inventory = _validate_inventory_operations(
                repo,
                run_id,
                loaded,
                authority,
                bundle,
                history_index,
                validate_current_authority=validate_current_authority,
            )
            _validate_uncertain_history(
                history,
                authority,
                inventory,
                bundle,
                validate_current_authority=validate_current_authority,
            )
        finally:
            os.close(invocations)
    finally:
        _close(fds)


def _validate_inventory_operations(
    repo: Path,
    run_id: str,
    operations: Sequence[_LoadedOperation],
    authority: Mapping[str, Any],
    bundle: CoreBundle,
    index: _HistoryIndex,
    *,
    validate_current_authority: bool = True,
) -> Mapping[str, _OperationInventory]:
    """Validate loaded operations against the shared history index."""
    operation_by_attempt: dict[str, str] = {}
    inventory: dict[str, _OperationInventory] = {}
    for operation in operations:
        inventory[operation.operation_id] = _validate_operation(
            repo,
            run_id,
            operation,
            authority,
            bundle,
            index,
            operation_by_attempt,
            validate_current_authority=validate_current_authority,
        )
    return MappingProxyType(inventory)


def _validate_operation(
    repo: Path,
    run_id: str,
    operation: _LoadedOperation,
    authority: Mapping[str, Any],
    bundle: CoreBundle,
    index: _HistoryIndex,
    operation_by_attempt: dict[str, str],
    *,
    validate_current_authority: bool = True,
) -> _OperationInventory:
    operation_id = operation.operation_id
    facts = operation.facts
    planned_entry = facts.get("planned.json")
    if planned_entry is None:
        raise ValueError("invocation inventory entry lacks original reservation")
    planned, _ = planned_entry
    stage_id = planned.get("stage_id") if isinstance(planned, dict) else None
    attempt = index.latest_attempt.get(stage_id) if isinstance(stage_id, str) else None
    historical_binding = attempt is not None and any(
        ref["kind"] == "review-target-binding/1" for ref in attempt["evidence"]
    )
    packet = _validate_reservation(
        repo,
        run_id,
        operation_id,
        planned,
        validate_current_authority=validate_current_authority
        and not historical_binding,
    )
    _validate_request_producers(planned, packet, index)
    allowed = {
        "planned.json",
        "dispatch-uncertain.json",
        "observed.json",
        "blocked.json",
    }
    if facts.keys() - allowed:
        raise ValueError("invocation inventory contains unsupported fact")
    for filename, (fact, digest) in facts.items():
        relative = f"invocations/{operation_id}/{filename}"
        if index.cited_digests.get(relative) != digest:
            raise ValueError("unreferenced invocation fact vetoes authority")
        if filename == "planned.json":
            _validate_planned_fact(
                fact,
                digest,
                relative,
                operation_id,
                run_id,
                packet,
                authority,
                bundle,
                index,
                operation_by_attempt,
                validate_current_authority=validate_current_authority,
            )
        else:
            _validate_observation_fact(
                fact,
                filename,
                digest,
                relative,
                operation_id,
                run_id,
                planned,
                packet,
                index,
            )
    return _OperationInventory(facts, packet)


def _validate_request_producers(
    planned: Mapping[str, Any], packet: Mapping[str, Any], index: _HistoryIndex
) -> None:
    creation_index = index.creation_index.get(planned["stage_id"])
    request_owner = index.first_citation.get(planned["request"]["path"])
    if request_owner is None or creation_index is None:
        raise ValueError("operation request has no earlier owning-attempt producer")
    if (
        request_owner.index <= creation_index
        or request_owner.row["stage_id"] != planned["stage_id"]
        or request_owner.row["role"] != planned["role"]
    ):
        raise ValueError(
            "operation request is consumed before its owning attempt creation"
        )
    for input_ref in packet.get("inputs", []):
        owner = index.first_citation.get(input_ref["path"])
        if owner is None:
            raise ValueError("operation input snapshot has no owning-attempt producer")
        if (
            owner.index <= creation_index
            or owner.row["stage_id"] != planned["stage_id"]
            or owner.row["role"] != planned["role"]
        ):
            raise ValueError(
                "operation input snapshot is consumed before its owning attempt creation"
            )


def _validate_planned_fact(
    fact: Mapping[str, Any],
    digest: str,
    relative: str,
    operation_id: str,
    run_id: str,
    packet: Mapping[str, Any],
    authority: Mapping[str, Any],
    bundle: CoreBundle,
    index: _HistoryIndex,
    operation_by_attempt: dict[str, str],
    *,
    validate_current_authority: bool = True,
) -> None:
    _validate_schema(fact, "invocation", bundle)
    stage_id = fact["stage_id"]
    previous = operation_by_attempt.setdefault(stage_id, operation_id)
    if previous != operation_id:
        raise ValueError("attempt owns multiple operation reservations")
    attempt = index.latest_attempt.get(stage_id)
    if attempt is None or fact["role"] != attempt["role"]:
        raise ValueError(
            "operation reservation does not resolve to an existing attempt"
        )
    evidence = {ref["path"]: ref["sha256"] for ref in attempt["evidence"]}
    if evidence.get(relative) != digest:
        raise ValueError("reservation is not owned by its attempt history")
    if (
        packet.get("bundle_digest") != authority["bundle_digest"]
        or packet.get("scope_digest") != attempt["scope_digest"]
        or packet.get("node_id") != attempt.get("node_id")
    ):
        raise ValueError(
            "operation reservation scope, node, or bundle binding mismatch"
        )
    if validate_current_authority:
        _validate_packet_authority(packet, authority, attempt, bundle)
    else:
        _validate_graph_free_request(packet, authority, attempt)
    _validate_fact_identity_and_producer(fact, relative, operation_id, run_id, index)


def _validate_observation_fact(
    fact: Mapping[str, Any],
    filename: str,
    digest: str,
    relative: str,
    operation_id: str,
    run_id: str,
    planned: Mapping[str, Any],
    packet: Mapping[str, Any],
    index: _HistoryIndex,
) -> None:
    expected_status = {
        "dispatch-uncertain.json": "dispatch-uncertain",
        "observed.json": "observed",
        "blocked.json": "blocked",
    }[filename]
    if any(
        fact.get(key) != planned.get(key)
        for key in (
            "protocol_version",
            "operation_id",
            "run_id",
            "stage_id",
            "role",
            "request_digest",
            "request",
            "adapter_binding",
        )
    ):
        raise ValueError("invocation fact changed original reservation binding")
    if fact.get("status") != expected_status:
        raise ValueError("invocation fact has invalid status")
    latest = index.latest_attempt.get(fact["stage_id"])
    if latest is None:
        raise ValueError("invocation fact does not resolve to an existing attempt")
    evidence = {ref["path"]: ref["sha256"] for ref in latest["evidence"]}
    if evidence.get(relative) != digest:
        raise ValueError("invocation fact is not produced by its owning attempt")
    _validate_fact_identity_and_producer(fact, relative, operation_id, run_id, index)
    _validate_observation_chronology(
        fact, filename, relative, operation_id, planned, index
    )


def _validate_fact_identity_and_producer(
    fact: Mapping[str, Any],
    relative: str,
    operation_id: str,
    run_id: str,
    index: _HistoryIndex,
) -> None:
    if fact.get("operation_id") != operation_id or fact.get("run_id") != run_id:
        raise ValueError("invocation fact identity mismatch")
    owner = index.first_citation.get(relative)
    creation_index = index.creation_index.get(fact["stage_id"])
    if owner is None:
        raise ValueError("invocation fact has no owning producer observation")
    if (
        creation_index is None
        or owner.index <= creation_index
        or owner.row["stage_id"] != fact["stage_id"]
        or owner.row["role"] != fact["role"]
    ):
        raise ValueError("invocation fact is consumed before its owning attempt exists")


def _validate_observation_chronology(
    fact: Mapping[str, Any],
    filename: str,
    relative: str,
    operation_id: str,
    planned: Mapping[str, Any],
    index: _HistoryIndex,
) -> None:
    owner = index.first_citation[relative].row
    if filename == "dispatch-uncertain.json":
        if owner["status"] != "dispatch-uncertain":
            raise ValueError(
                "uncertainty fact is not first produced by its owning attempt"
            )
    elif filename == "observed.json":
        uncertainty = index.first_citation.get(
            f"invocations/{operation_id}/dispatch-uncertain.json"
        )
        if (
            uncertainty is None
            or uncertainty.index >= index.first_citation[relative].index
            or uncertainty.row["stage_id"] != fact["stage_id"]
            or uncertainty.row["status"] != "dispatch-uncertain"
        ):
            raise ValueError("observed fact precedes its owning uncertainty producer")
    elif filename == "blocked.json":
        if owner["status"] != "blocked":
            raise ValueError("blocked fact is not first produced by its owning attempt")
        for prerequisite in (
            f"invocations/{operation_id}/planned.json",
            planned["request"]["path"],
        ):
            producer = index.first_citation.get(prerequisite)
            if (
                producer is None
                or producer.index > index.first_citation[relative].index
                or producer.row["stage_id"] != fact["stage_id"]
            ):
                raise ValueError(
                    "blocked fact precedes its request or reservation producer"
                )


def _validate_uncertain_history(
    history: Sequence[Mapping[str, Any]],
    authority: Mapping[str, Any],
    inventory: Mapping[str, _OperationInventory],
    bundle: CoreBundle,
    *,
    validate_current_authority: bool = True,
) -> None:
    for row in history:
        if row["status"] == "dispatch-uncertain":
            _validate_uncertain_observation(
                row,
                authority,
                inventory,
                bundle,
                validate_current_authority=validate_current_authority,
            )


def _validate_uncertain_observation(
    row: Mapping[str, Any],
    authority: Mapping[str, Any],
    inventory: Mapping[str, _OperationInventory],
    bundle: CoreBundle,
    *,
    validate_current_authority: bool = True,
) -> None:
    evidence = {ref["path"]: ref["sha256"] for ref in row["evidence"]}
    reservations = [
        path
        for path in evidence
        if re.fullmatch(r"invocations/op-[0-9a-f]{32}/planned\.json", path)
    ]
    if len(reservations) != 1:
        raise ValueError(
            "uncertain history must cite exactly one operation reservation"
        )
    planned_path = reservations[0]
    operation_id = planned_path.split("/")[1]
    operation = inventory[operation_id]
    planned, planned_digest = operation.facts["planned.json"]
    packet = operation.packet
    if planned["stage_id"] != row["stage_id"] or planned["role"] != row["role"]:
        raise ValueError("uncertain history cites another attempt's reservation")
    if validate_current_authority:
        _validate_packet_authority(packet, authority, row, bundle)
    uncertain_path = f"invocations/{operation_id}/dispatch-uncertain.json"
    uncertain, uncertain_digest = operation.facts["dispatch-uncertain.json"]
    required_refs = {
        planned_path: planned_digest,
        planned["request"]["path"]: planned["request_digest"],
        uncertain_path: uncertain_digest,
    }
    for item in packet.get("inputs", []):
        required_refs[item["path"]] = item["sha256"]
    for field in ("graph", "approved_plan", "accepted_snapshot"):
        if field in packet:
            ref = packet[field]
            required_refs[ref["path"]] = ref["sha256"]
    if uncertain.get("status") != "dispatch-uncertain" or any(
        evidence.get(path) != digest for path, digest in required_refs.items()
    ):
        raise ValueError(
            "uncertain observation lacks exact operation and prerequisite evidence"
        )
