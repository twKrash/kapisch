from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._locking import _locked
from .bundle import canonical_json
from .storage import (
    load_authority_record,
    load_authority_records,
    store_authority_record,
)


@dataclass(frozen=True)
class ProposedScopeRef:
    origin_run_id: str
    scope_id: str
    sha256: str


def _validate_string(value: Any, name: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a nonempty string")


def _validate_applicability(applicability: Any) -> None:
    if type(applicability) is not dict:
        raise ValueError("applicability must be an object")
    if applicability == {"mode": "all"}:
        return
    if set(applicability) != {"mode", "keys"} or applicability.get("mode") != "keys":
        raise ValueError("invalid applicability")
    keys = applicability["keys"]
    if type(keys) is not list or not keys:
        raise ValueError("applicability keys must be a nonempty array")
    for key in keys:
        _validate_string(key, "applicability key")
    if len(set(keys)) != len(keys) or keys != sorted(
        keys, key=lambda key: key.encode("utf-8")
    ):
        raise ValueError("applicability keys must be unique and UTF-8-byte sorted")


def _reference(value: ProposedScopeRef | dict[str, Any]) -> ProposedScopeRef:
    if isinstance(value, ProposedScopeRef):
        result = value
    elif type(value) is dict and set(value) == {"origin_run_id", "scope_id", "sha256"}:
        result = ProposedScopeRef(**value)
    else:
        raise ValueError("invalid proposed scope reference")
    _validate_string(result.origin_run_id, "origin_run_id")
    _validate_string(result.scope_id, "scope_id")
    if (
        type(result.sha256) is not str
        or len(result.sha256) != 64
        or any(c not in "0123456789abcdef" for c in result.sha256)
    ):
        raise ValueError("invalid scope digest")
    return result


def _identity_key(origin_run_id: str, scope_id: str) -> str:
    identity = {"origin_run_id": origin_run_id, "scope_id": scope_id}
    return hashlib.sha256(canonical_json(identity)).hexdigest()


def _record(
    origin_run_id: str,
    scope_id: str,
    requirements: str,
    applicability: Any,
) -> dict[str, Any]:
    _validate_string(origin_run_id, "origin_run_id")
    _validate_string(scope_id, "scope_id")
    _validate_string(requirements, "requirements")
    _validate_applicability(applicability)
    return {
        "protocol_version": 3,
        "scope_contract": "applicability-scope/1",
        "origin_run_id": origin_run_id,
        "scope_id": scope_id,
        "requirements": requirements,
        "applicability": applicability,
    }


def propose_scope(
    repo: Path,
    origin_run_id: str,
    scope_id: str,
    requirements: str,
    applicability: dict,
) -> ProposedScopeRef:
    record = _record(origin_run_id, scope_id, requirements, applicability)
    data = canonical_json(record)
    key = _identity_key(origin_run_id, scope_id)
    with _locked(Path(repo)):
        try:
            store_authority_record(Path(repo), "scopes", key, data)
        except FileExistsError as error:
            raise ValueError("proposed scope identity is already occupied") from error
    return ProposedScopeRef(
        origin_run_id,
        scope_id,
        hashlib.sha256(data).hexdigest(),
    )


def load_proposed_scope_by_digest(repo: Path, digest: str) -> dict:
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("invalid scope digest")
    try:
        records = load_authority_records(Path(repo), "scopes")
    except FileNotFoundError as error:
        raise ValueError("proposed scope digest is not retained") from error

    matches = []
    for identity, data in records:
        if hashlib.sha256(data).hexdigest() != digest:
            continue
        try:
            record = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid proposed scope JSON") from error
        if type(record) is not dict or set(record) != {
            "protocol_version",
            "scope_contract",
            "origin_run_id",
            "scope_id",
            "requirements",
            "applicability",
        }:
            raise ValueError("invalid proposed scope record")
        reference = ProposedScopeRef(
            record["origin_run_id"],
            record["scope_id"],
            digest,
        )
        if _identity_key(reference.origin_run_id, reference.scope_id) != identity:
            raise ValueError("proposed scope identity path mismatch")
        matches.append(load_proposed_scope(repo, reference))
    if len(matches) != 1:
        raise ValueError("proposed scope digest is missing or ambiguous")
    return matches[0]


def load_proposed_scope(repo: Path, ref: ProposedScopeRef | dict) -> dict:
    reference = _reference(ref)
    key = _identity_key(reference.origin_run_id, reference.scope_id)
    try:
        data = load_authority_record(Path(repo), "scopes", key)
    except FileNotFoundError as error:
        raise ValueError("proposed scope record is missing") from error
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid proposed scope JSON") from error
    if (
        canonical_json(record) != data
        or type(record) is not dict
        or set(record)
        != {
            "protocol_version",
            "scope_contract",
            "origin_run_id",
            "scope_id",
            "requirements",
            "applicability",
        }
    ):
        raise ValueError("invalid proposed scope record")
    expected = _record(
        reference.origin_run_id,
        reference.scope_id,
        record["requirements"],
        record["applicability"],
    )
    if record != expected or hashlib.sha256(data).hexdigest() != reference.sha256:
        raise ValueError("proposed scope reference or descriptor mismatch")
    return record


def accept_repository_decision(
    repo: Path, approval_reference: dict[str, Any]
) -> dict[str, str]:
    """Commit repository authority from one exact persisted gate approval."""
    from ._accepted_snapshot import publish_acceptance

    return publish_acceptance(Path(repo), approval_reference)
