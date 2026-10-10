from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ._authority import _validate_packet_authority
from ._invocation import _validate_reservation
from ._validation_json import _json
from ._validation_schema import _validate_schema
from .bundle import CoreBundle
from .storage import _close, _open_dir, _read_file, _run_dir


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
class _LoadedOperation:
    operation_id: str
    facts: Mapping[str, tuple[Any, str]]


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
    repo: Path, run_id: str, state: Mapping[str, Any], bundle: CoreBundle
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
            if "review_result_ref" in state:
                raise ValueError("review backlinks have no invocation inventory")
            return
        try:
            loaded = _read_invocation_inventory(invocations)
            inventory = _validate_inventory_operations(
                repo, run_id, loaded, authority, bundle, history_index, state
            )
            _validate_uncertain_history(history, authority, inventory, bundle)
        finally:
            os.close(invocations)
    finally:
        _close(fds)


def _read_invocation_inventory(invocations: int) -> tuple[_LoadedOperation, ...]:
    """Discover and parse each immutable invocation fact once, retaining its digest."""
    try:
        operation_ids = sorted(os.listdir(invocations))
    except OSError as error:
        raise ValueError("invocation inventory is unavailable") from error
    loaded: list[_LoadedOperation] = []
    for operation_id in operation_ids:
        if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
            raise ValueError("invocation inventory contains invalid operation name")
        try:
            operation = _open_dir(invocations, operation_id)
        except OSError as error:
            raise ValueError("invocation inventory entry is unavailable") from error
        try:
            try:
                names = sorted(os.listdir(operation))
            except OSError as error:
                raise ValueError("invocation inventory entry is unavailable") from error
            facts: dict[str, tuple[Any, str]] = {}
            for filename in names:
                if not filename.endswith(".json"):
                    raise ValueError("invocation inventory contains unknown artifact")
                relative = f"invocations/{operation_id}/{filename}"
                data = _read_file(operation, filename)
                facts[filename] = (
                    _json(data, relative),
                    hashlib.sha256(data).hexdigest(),
                )
            loaded.append(_LoadedOperation(operation_id, MappingProxyType(facts)))
        finally:
            os.close(operation)
    return tuple(loaded)


def _validate_inventory_operations(
    repo: Path,
    run_id: str,
    operations: Sequence[_LoadedOperation],
    authority: Mapping[str, Any],
    bundle: CoreBundle,
    index: _HistoryIndex,
    state: Mapping[str, Any],
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
            state,
        )
    _validate_review_backlinks(run_id, inventory, state)
    return MappingProxyType(inventory)


def _validate_operation(
    repo: Path,
    run_id: str,
    operation: _LoadedOperation,
    authority: Mapping[str, Any],
    bundle: CoreBundle,
    index: _HistoryIndex,
    operation_by_attempt: dict[str, str],
    state: Mapping[str, Any],
) -> _OperationInventory:
    operation_id = operation.operation_id
    facts = operation.facts
    planned_entry = facts.get("planned.json")
    if planned_entry is None:
        raise ValueError("invocation inventory entry lacks original reservation")
    planned, _ = planned_entry
    packet = _validate_reservation(repo, run_id, operation_id, planned)
    _validate_request_producers(planned, packet, index)
    review_names = {
        "review-invocation.json",
        "reviewer-return.json",
        "host-provenance-attestation.json",
        "post-result.json",
        "review-result.json",
    }
    allowed = {
        "planned.json",
        "dispatch-uncertain.json",
        "observed.json",
        "blocked.json",
        *review_names,
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
            )
        elif filename not in review_names:
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
    if facts.keys() & review_names:
        from ._review_chain import _load_result_chain

        if _load_result_chain(repo, run_id, operation_id, state) is None:
            raise ValueError("review result chain is incomplete")
    return _OperationInventory(facts, packet)


def _validate_review_backlinks(
    run_id: str,
    inventory: Mapping[str, _OperationInventory],
    state: Mapping[str, Any],
) -> None:
    references = state.get("review_result_ref", {})
    if not isinstance(references, Mapping):
        raise ValueError("review_result_ref has invalid shape")
    for operation_id, reference in references.items():
        if not isinstance(reference, Mapping):
            raise ValueError("review_result_ref has invalid entry")
        operation = inventory.get(operation_id)
        if operation is None or "review-result.json" not in operation.facts:
            raise ValueError("review backlink has no complete result chain")
        expected_path = f"invocations/{operation_id}/review-result.json"
        if reference.get("path") != f".kapisch/v3/runs/{run_id}/{expected_path}" or reference.get("sha256") != operation.facts["review-result.json"][1]:
            raise ValueError("review backlink conflicts with complete result chain")


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
    _validate_packet_authority(packet, authority, attempt, bundle)
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
) -> None:
    for row in history:
        if row["status"] == "dispatch-uncertain":
            _validate_uncertain_observation(row, authority, inventory, bundle)


def _validate_uncertain_observation(
    row: Mapping[str, Any],
    authority: Mapping[str, Any],
    inventory: Mapping[str, _OperationInventory],
    bundle: CoreBundle,
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
