from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._gate_approval import load_gate_approval
from .advisory import ProposedScopeRef, _reference, load_proposed_scope
from .bundle import canonical_json
from .storage import load_authority_records

_ACCEPTANCE_NAMESPACE = "acceptances"


@dataclass(frozen=True)
class _Acceptance:
    origin_run_id: str
    snapshot_id: str
    digest: str
    record: dict[str, Any]
    payload: dict[str, Any]


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("acceptance record contains duplicate object key")
        result[key] = value
    return result


def _load_acceptances(repo: Path) -> tuple[_Acceptance, ...]:
    records = load_authority_records(repo, _ACCEPTANCE_NAMESPACE)
    acceptances = []
    for identity, data in records:
        try:
            record = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("acceptance record is malformed") from error
        if (
            type(record) is not dict
            or set(record)
            != {
                "acceptance_contract",
                "origin_run_id",
                "snapshot_id",
                "gate_approval_ref",
            }
            or record["acceptance_contract"] != "global-authority/1"
            or type(record["origin_run_id"]) is not str
            or not record["origin_run_id"]
            or type(record["snapshot_id"]) is not str
            or not record["snapshot_id"]
            or canonical_json(record) != data
        ):
            raise ValueError("acceptance record has invalid canonical shape")
        record_identity = hashlib.sha256(
            canonical_json(
                {
                    "origin_run_id": record["origin_run_id"],
                    "snapshot_id": record["snapshot_id"],
                }
            )
        ).hexdigest()
        if record_identity != identity:
            raise ValueError("acceptance record identity path mismatch")
        approval = load_gate_approval(repo, record["gate_approval_ref"])
        payload = approval["payload"]
        subject = payload["subject"]
        if (
            payload["gate_kind"] != "repository-decision"
            or subject["acceptance_contract"] != record["acceptance_contract"]
            or subject["origin_run_id"] != record["origin_run_id"]
            or subject["snapshot_id"] != record["snapshot_id"]
        ):
            raise ValueError(
                "acceptance record does not match repository-decision approval"
            )
        acceptances.append(
            _Acceptance(
                record["origin_run_id"],
                record["snapshot_id"],
                hashlib.sha256(data).hexdigest(),
                record,
                payload,
            )
        )
    return tuple(acceptances)


def _validate_graph(acceptances: tuple[_Acceptance, ...]) -> None:
    by_id: dict[tuple[str, str], _Acceptance] = {}
    by_decision: dict[tuple[str, str, str], _Acceptance] = {}
    for acceptance in acceptances:
        payload = acceptance.payload
        subject = payload["subject"]
        key = (acceptance.origin_run_id, acceptance.snapshot_id)
        if key in by_id:
            raise ValueError("acceptance identity collision")
        by_id[key] = acceptance
        decision_key = (*key, subject["decision_id"])
        if decision_key in by_decision:
            raise ValueError("qualified decision identity collision")
        by_decision[decision_key] = acceptance
    for acceptance in acceptances:
        for binding in acceptance.payload["subject"]["authority_basis"]:
            identity = (
                binding["origin_run_id"],
                binding["snapshot_id"],
                binding["decision_id"],
            )
            target = by_decision.get(identity)
            if target is None:
                raise ValueError("authority basis target is missing")
            target_subject = target.payload["subject"]
            expected = {
                "origin_run_id": target.origin_run_id,
                "snapshot_id": target.snapshot_id,
                "decision_id": target_subject["decision_id"],
                "acceptance_record_sha256": target.digest,
                "scope_ref": target_subject["scope_ref"],
                "applicability": target_subject["applicability"],
                "source_dependencies": target_subject["source_dependencies"],
            }
            if binding != expected:
                raise ValueError("authority basis binding differs from committed target")
    edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    superseded: dict[tuple[str, str], int] = {}
    for acceptance in acceptances:
        subject = acceptance.payload["subject"]
        amends = subject["amends"]
        supersedes = subject["supersedes"]
        if set(map(canonical_json, amends)) & set(map(canonical_json, supersedes)):
            raise ValueError("acceptance relationship target appears in both arrays")
        related = set()
        for relation in (*amends, *supersedes):
            key = (
                relation["origin_run_id"],
                relation["snapshot_id"],
                relation["decision_id"],
            )
            target = by_decision.get(key)
            if target is None or target.digest != relation["sha256"]:
                raise ValueError("acceptance relationship target is missing or changed")
            if target is acceptance:
                raise ValueError("acceptance cannot relate to itself")
            related.add((target.origin_run_id, target.snapshot_id))
        edges[(acceptance.origin_run_id, acceptance.snapshot_id)] = related
        for relation in supersedes:
            target = by_decision[
                (
                    relation["origin_run_id"],
                    relation["snapshot_id"],
                    relation["decision_id"],
                )
            ]
            superseded_key = (target.origin_run_id, target.snapshot_id)
            superseded[superseded_key] = superseded.get(superseded_key, 0) + 1
            if superseded[superseded_key] > 1:
                raise ValueError("acceptance predecessor has competing supersessions")
            old = target.payload["subject"]["applicability"]
            new = subject["applicability"]
            if old["mode"] == "all" and new["mode"] != "all":
                raise ValueError(
                    "supersession does not cover predecessor applicability"
                )
            if (
                old["mode"] == "keys"
                and new["mode"] == "keys"
                and not set(old["keys"]) <= set(new["keys"])
            ):
                raise ValueError(
                    "supersession does not cover predecessor applicability"
                )
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(key: tuple[str, str]) -> None:
        if key in visiting:
            raise ValueError("acceptance relationship cycle detected")
        if key in visited:
            return
        visiting.add(key)
        for target in edges[key]:
            visit(target)
        visiting.remove(key)
        visited.add(key)

    for key in edges:
        visit(key)


def _active_bindings(
    repo: Path, scope_ref: ProposedScopeRef
) -> tuple[dict[str, Any], ...]:
    consuming = load_proposed_scope(repo, _reference(scope_ref))["applicability"]
    acceptances = _load_acceptances(repo)
    _validate_graph(acceptances)
    retired = {
        (relation["origin_run_id"], relation["snapshot_id"])
        for item in acceptances
        for relation in item.payload["subject"]["supersedes"]
    }
    results = []
    for item in acceptances:
        subject = item.payload["subject"]
        applicability = subject["applicability"]
        match = (
            applicability["mode"] == "all"
            or consuming["mode"] == "all"
            or bool(set(applicability.get("keys", ())) & set(consuming.get("keys", ())))
        )
        if not match or (item.origin_run_id, item.snapshot_id) in retired:
            continue
        results.append(
            {
                "origin_run_id": item.origin_run_id,
                "snapshot_id": item.snapshot_id,
                "decision_id": subject["decision_id"],
                "acceptance_record_sha256": item.digest,
                "scope_ref": subject["scope_ref"],
                "applicability": applicability,
                "source_dependencies": subject["source_dependencies"],
            }
        )
    return tuple(sorted(results, key=canonical_json))


__all__ = ["_active_bindings"]
