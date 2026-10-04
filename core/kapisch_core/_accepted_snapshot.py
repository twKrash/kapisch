from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._authority_records import _active_bindings, _load_acceptances, _validate_graph
from ._gate_approval import load_gate_approval
from ._locking import _locked
from ._validation_schema import _validate_schema
from .advisory import _reference, load_proposed_scope
from .bundle import canonical_json
from .storage import (
    _read_repository_file,
    load_authority_record,
    load_bundle,
    store_authority_record,
)

_NAMESPACE = "acceptances"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_RECORD_FIELDS = {
    "acceptance_contract",
    "origin_run_id",
    "snapshot_id",
    "gate_approval_ref",
}


@dataclass(frozen=True)
class AcceptanceRef:
    origin_run_id: str
    snapshot_id: str
    sha256: str


def _identity_key(origin_run_id: str, snapshot_id: str) -> str:
    return hashlib.sha256(
        canonical_json({"origin_run_id": origin_run_id, "snapshot_id": snapshot_id})
    ).hexdigest()


def _parse_reference(value: Any) -> AcceptanceRef:
    if isinstance(value, AcceptanceRef):
        reference = value
    elif type(value) is dict and set(value) == {
        "origin_run_id",
        "snapshot_id",
        "sha256",
    }:
        reference = AcceptanceRef(**value)
    else:
        raise ValueError("acceptance reference has invalid shape")
    if (
        type(reference.origin_run_id) is not str
        or not reference.origin_run_id
        or type(reference.snapshot_id) is not str
        or not reference.snapshot_id
        or type(reference.sha256) is not str
        or not _DIGEST.fullmatch(reference.sha256)
    ):
        raise ValueError("acceptance reference is invalid")
    return reference


def _record(approval: dict[str, Any]) -> dict[str, Any]:
    payload = approval["payload"]
    subject = payload["subject"]
    return {
        "acceptance_contract": "global-authority/1",
        "origin_run_id": subject["origin_run_id"],
        "snapshot_id": subject["snapshot_id"],
        "gate_approval_ref": {
            "approval_id": approval["approval_id"],
            "sha256": hashlib.sha256(canonical_json(approval)).hexdigest(),
        },
    }


def _validate_source_dependencies(
    repo: Path, dependencies: list[dict[str, str]]
) -> None:
    for dependency in dependencies:
        data = _read_repository_file(repo, dependency["path"])
        if hashlib.sha256(data).hexdigest() != dependency["sha256"]:
            raise ValueError("source dependency changed since GateApproval")


def _validate_candidate_relationships(repo: Path, payload: dict[str, Any]) -> None:
    acceptances = _load_acceptances(repo)
    _validate_graph(acceptances)
    by_decision = {
        (
            item.origin_run_id,
            item.snapshot_id,
            item.payload["subject"]["decision_id"],
        ): item
        for item in acceptances
    }
    retired = {
        (relation["origin_run_id"], relation["snapshot_id"])
        for item in acceptances
        for relation in item.payload["subject"]["supersedes"]
    }
    subject = payload["subject"]
    amends = subject["amends"]
    supersedes = subject["supersedes"]
    if {canonical_json(item) for item in amends} & {
        canonical_json(item) for item in supersedes
    }:
        raise ValueError("acceptance relationship target appears in both arrays")
    seen = set()
    for relation in (*amends, *supersedes):
        identity = (
            relation["origin_run_id"],
            relation["snapshot_id"],
            relation["decision_id"],
        )
        if identity in seen:
            raise ValueError("acceptance relationship target is duplicated")
        seen.add(identity)
        target = by_decision.get(identity)
        if target is None or target.digest != relation["sha256"]:
            raise ValueError("acceptance relationship target is missing or changed")
        if (target.origin_run_id, target.snapshot_id) == (
            subject["origin_run_id"],
            subject["snapshot_id"],
        ):
            raise ValueError("acceptance cannot relate to itself")
        if relation in supersedes:
            target_identity = (target.origin_run_id, target.snapshot_id)
            if target_identity in retired:
                raise ValueError("supersession target is no longer active")
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


def _validate_new_publication(repo: Path, approval: dict[str, Any]) -> None:
    payload = approval["payload"]
    if payload["gate_kind"] != "repository-decision":
        raise ValueError("AcceptanceRecord requires repository-decision approval")
    subject = payload["subject"]
    scope_ref = _reference(subject["scope_ref"])
    scope = load_proposed_scope(repo, scope_ref)
    if scope_ref.sha256 != payload["scope_digest"]:
        raise ValueError("acceptance scope digest differs from GateApproval")
    if scope["applicability"] != subject["applicability"]:
        raise ValueError("acceptance applicability differs from persisted scope")

    current_basis = _active_bindings(repo, scope_ref)
    if canonical_json(current_basis) != canonical_json(subject["authority_basis"]):
        raise ValueError("acceptance authority basis is stale")
    _validate_candidate_relationships(repo, payload)
    _validate_source_dependencies(repo, subject["source_dependencies"])
    for binding in subject["authority_basis"]:
        _validate_source_dependencies(repo, binding["source_dependencies"])

    bundle = load_bundle(repo, subject["bundle_digest"])
    _validate_schema(_record(approval), "snapshot", bundle)


def _load_record(repo: Path, reference: AcceptanceRef) -> dict[str, Any]:
    identity = _identity_key(reference.origin_run_id, reference.snapshot_id)
    data = load_authority_record(repo, _NAMESPACE, identity)
    if hashlib.sha256(data).hexdigest() != reference.sha256:
        raise ValueError("acceptance reference digest mismatch")
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("acceptance record is malformed") from error
    if (
        type(record) is not dict
        or set(record) != _RECORD_FIELDS
        or canonical_json(record) != data
        or record["acceptance_contract"] != "global-authority/1"
        or record["origin_run_id"] != reference.origin_run_id
        or record["snapshot_id"] != reference.snapshot_id
    ):
        raise ValueError("acceptance record identity or shape is invalid")
    approval = load_gate_approval(repo, record["gate_approval_ref"])
    if _record(approval) != record:
        raise ValueError("acceptance record differs from referenced GateApproval")
    _validate_schema(
        record,
        "snapshot",
        load_bundle(repo, approval["payload"]["subject"]["bundle_digest"]),
    )
    records = _load_acceptances(repo)
    _validate_graph(records)
    return record


def load_acceptance(
    repo: Path, reference: AcceptanceRef | dict[str, Any]
) -> dict[str, Any]:
    parsed = _parse_reference(reference)
    with _locked(Path(repo)):
        return _load_record(Path(repo), parsed)


def publish_acceptance(
    repo: Path, approval_reference: dict[str, Any]
) -> dict[str, str]:
    repo = Path(repo)
    with _locked(repo):
        approval = load_gate_approval(repo, approval_reference)
        if approval["payload"].get("gate_kind") != "repository-decision":
            raise ValueError("AcceptanceRecord requires repository-decision approval")
        record = _record(approval)
        data = canonical_json(record)
        identity = _identity_key(record["origin_run_id"], record["snapshot_id"])
        reference = {
            "origin_run_id": record["origin_run_id"],
            "snapshot_id": record["snapshot_id"],
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        try:
            existing = load_authority_record(repo, _NAMESPACE, identity)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing != data:
                raise ValueError("acceptance identity is occupied by different bytes")
            # An exact retry re-syncs a previously visible but uncertain commit.
            store_authority_record(repo, _NAMESPACE, identity, data)
            _load_record(repo, _parse_reference(reference))
            return reference

        _validate_new_publication(repo, approval)
        try:
            store_authority_record(repo, _NAMESPACE, identity, data)
        except OSError as error:
            # Visibility alone is not a durable commit; retrying identical bytes
            # re-syncs the linked record and its directory chain.
            try:
                store_authority_record(repo, _NAMESPACE, identity, data)
            except OSError as retry_error:
                raise retry_error from error
        retained = load_authority_record(repo, _NAMESPACE, identity)
        if retained != data:
            raise ValueError("acceptance read-back differs from published bytes")
        if _load_record(repo, _parse_reference(reference)) != record:
            raise ValueError("acceptance recovery differs from published record")
        return reference


__all__ = ["AcceptanceRef", "load_acceptance", "publish_acceptance"]
