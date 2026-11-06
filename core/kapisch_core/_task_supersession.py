"""Dispatch-only validation of explicit persisted decision supersession."""

from __future__ import annotations

import heapq
from pathlib import Path
from typing import Any

from ._task_artifacts import _DIGEST, ContractError, _required_id
from ._task_decisions import (
    _DecisionRecord,
    _read_decision_record,
    _validate_decision_path,
)

_SUPERSEDES_FIELDS = frozenset({"decision_id", "decision_ref", "decision_digest"})
_SUPERSEDES_OUTSIDE_RUN = "supersedes target is outside its Run"


def _validate_supersedes_entry(
    root: Path, run_directory: str, entry: Any, ids: set[str], refs: set[str]
) -> None:
    if not isinstance(entry, dict) or set(entry) != _SUPERSEDES_FIELDS:
        raise ContractError("invalid supersedes entry")
    identity = _required_id(entry, "decision_id", "supersedes decision identity")
    ref = entry["decision_ref"]
    _validate_decision_path(
        root,
        run_directory,
        ref,
        outside_run_message=_SUPERSEDES_OUTSIDE_RUN,
    )
    digest = entry["decision_digest"]
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ContractError("invalid supersedes decision digest")
    if identity in ids or ref in refs:
        raise ContractError("duplicate supersedes target")
    ids.add(identity)
    refs.add(ref)


def _supersedes_entries(
    root: Path, run_directory: str, decision: dict[str, Any]
) -> list[dict[str, str]]:
    if "supersedes" not in decision:
        return []
    entries = decision["supersedes"]
    if not isinstance(entries, list) or not entries:
        raise ContractError("invalid decision supersedes")
    ids, refs = set(), set()
    for entry in entries:
        _validate_supersedes_entry(root, run_directory, entry, ids, refs)
    return entries


def _validate_acyclic(edges: dict[str, list[str]]) -> None:
    incoming = dict.fromkeys(edges, 0)
    for targets in edges.values():
        for target in targets:
            incoming[target] += 1
    ready = [identity for identity, count in incoming.items() if count == 0]
    heapq.heapify(ready)
    visited = 0
    while ready:
        identity = heapq.heappop(ready)
        visited += 1
        for target in edges[identity]:
            incoming[target] -= 1
            if incoming[target] == 0:
                heapq.heappush(ready, target)
    if visited != len(edges):
        raise ContractError("decision supersession cycle")


_SUPERSESSION_DIAGNOSTICS = {
    "missing_target": "supersedes target is missing",
    "superseded": "decision is superseded",
}


def _scan_decisions(root: Path, run_directory: str) -> dict[str, _DecisionRecord]:
    """One invocation-local byte/parse snapshot, never persisted or cached."""
    records = {}
    identities = {}
    for path in sorted((root / run_directory / "decisions").glob("*.json")):
        ref = path.relative_to(root).as_posix()
        record = _read_decision_record(root, run_directory, ref, require_digest=False)
        identity = record.decision["decision_id"]
        if identity in identities:
            raise ContractError(
                "decision identity is not unique or reference mismatches"
            )
        identities[identity] = record
        records[ref] = record
    return records


def _validate_supersession_edges(
    root: Path,
    run_directory: str,
    identities: dict[str, _DecisionRecord],
    records: dict[str, _DecisionRecord],
) -> tuple[dict[str, list[str]], list[tuple[dict[str, str], _DecisionRecord]]]:
    edges = {identity: [] for identity in identities}
    bindings = []
    for identity, record in identities.items():
        for entry in _supersedes_entries(root, run_directory, record.decision):
            target_id = entry["decision_id"]
            target_ref = entry["decision_ref"]
            if target_id == identity or target_ref == record.ref:
                raise ContractError("decision cannot supersede itself")
            target = identities.get(target_id)
            if target_ref not in records:
                raise ContractError(_SUPERSESSION_DIAGNOSTICS["missing_target"])
            if target is None or target.ref != target_ref:
                raise ContractError("supersedes target identity mismatch")
            edges[identity].append(target_id)
            bindings.append((entry, target))
    return edges, bindings


def _validate_supersession_digests(
    bindings: list[tuple[dict[str, str], _DecisionRecord]],
) -> None:
    for entry, target in bindings:
        if entry["decision_digest"] != target.digest:
            raise ContractError(f"artifact digest mismatch: {target.ref}")


def _validate_supersession_graph(
    root: Path,
    run_directory: str,
    records: dict[str, _DecisionRecord] | None = None,
) -> frozenset[str]:
    """Validate structure and cycles before exact-byte edge digests."""
    if records is None:
        records = _scan_decisions(root, run_directory)
    identities = {r.decision["decision_id"]: r for r in records.values()}
    edges, bindings = _validate_supersession_edges(
        root, run_directory, identities, records
    )
    _validate_acyclic(edges)
    _validate_supersession_digests(bindings)
    return frozenset(target for targets in edges.values() for target in targets)


def _validate_decision_eligibility(
    root: Path,
    run_directory: str,
    decision_id: str,
    records: dict[str, _DecisionRecord] | None = None,
) -> None:
    if decision_id in _validate_supersession_graph(root, run_directory, records):
        raise ContractError(f"{_SUPERSESSION_DIAGNOSTICS['superseded']}: {decision_id}")
