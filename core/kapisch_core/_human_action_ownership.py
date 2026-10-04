from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ._human_evidence import (
    GateApprovalTarget,
    ObservedGateAction,
    _validate_gate_approval_target,
    bind_gate_action,
)
from ._locking import _locked
from ._protocol_formats import is_rfc3339_timestamp, is_sha256_digest
from .bundle import canonical_json
from .storage import load_authority_record, store_authority_record

_NAMESPACE = "human-actions"
_CLAIM_FIELDS = {
    "protocol_version",
    "claim_contract",
    "identity",
    "receipt",
    "gate_target",
    "approved_target_sha256",
}
_IDENTITY_FIELDS = {"session_namespace", "session_id", "action_id"}
_GATE_IDENTITY_FIELDS = {"kind", "id"}
_RECEIPT_FIELDS = {
    "origin",
    "session_namespace",
    "session_id",
    "action_id",
    "run_id",
    "gate_id",
    "identity",
    "target",
    "scope_digest",
    "text_digest",
    "observed_at",
}
_TARGET_FIELDS = {"run_id", "gate_id", "identity", "target", "scope_digest"}


def _identity_key(namespace: str, session: str, action: str) -> str:
    return hashlib.sha256(
        canonical_json(
            {"session_namespace": namespace, "session_id": session, "action_id": action}
        )
    ).hexdigest()


def _claim(receipt: ObservedGateAction, target: GateApprovalTarget) -> dict:
    bind_gate_action(receipt, target)
    identity = {
        "session_namespace": receipt.session_namespace,
        "session_id": receipt.session_id,
        "action_id": receipt.action_id,
    }
    projection = {
        "origin": receipt.origin.value,
        **identity,
        "run_id": receipt.run_id,
        "gate_id": receipt.gate_id,
        "identity": {"kind": receipt.identity.kind, "id": receipt.identity.id},
        "target": receipt.target,
        "scope_digest": receipt.scope_digest,
        "text_digest": receipt.text_digest,
        "observed_at": receipt.observed_at,
    }
    gate_target = {
        "run_id": target.run_id,
        "gate_id": target.gate_id,
        "identity": {"kind": target.identity.kind, "id": target.identity.id},
        "target": target.target,
        "scope_digest": target.scope_digest,
    }
    return {
        "protocol_version": 3,
        "claim_contract": "human-action-claim/1",
        "identity": identity,
        "receipt": projection,
        "gate_target": gate_target,
        "approved_target_sha256": target.target,
    }


def publish_human_action_claim(
    repo: Path, receipt: ObservedGateAction, target: GateApprovalTarget
) -> dict:
    claim = _claim(receipt, target)
    identity = claim["identity"]
    key = _identity_key(
        identity["session_namespace"], identity["session_id"], identity["action_id"]
    )
    data = canonical_json(claim)
    with _locked(Path(repo)):
        try:
            store_authority_record(Path(repo), _NAMESPACE, key, data)
        except FileExistsError as exc:
            raise ValueError(
                "human action identity is already occupied by a different claim"
            ) from exc
    return {"identity": identity, "sha256": hashlib.sha256(data).hexdigest()}


def _exact(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"human action claim {label} has invalid shape")
    return value


def load_human_action_claim(
    repo: Path, ref: dict, expected_target: GateApprovalTarget
) -> dict:
    _validate_gate_approval_target(expected_target)
    ref = _exact(ref, {"identity", "sha256"}, "reference")
    identity = _exact(ref["identity"], _IDENTITY_FIELDS, "reference identity")
    if any(
        not isinstance(v, str) or not v for v in identity.values()
    ) or not is_sha256_digest(ref["sha256"]):
        raise ValueError("human action claim reference is invalid")
    key = _identity_key(
        identity["session_namespace"], identity["session_id"], identity["action_id"]
    )
    try:
        data = load_authority_record(Path(repo), _NAMESPACE, key)
    except FileNotFoundError as exc:
        raise ValueError(
            "human action claim reference identity is not retained"
        ) from exc
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("human action claim digest mismatch")
    try:
        value = json.loads(data, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("human action claim is invalid JSON") from exc
    if canonical_json(value) != data:
        raise ValueError("human action claim is noncanonical")
    _exact(value, _CLAIM_FIELDS, "record")
    stored_identity = _exact(value["identity"], _IDENTITY_FIELDS, "identity")
    receipt = _exact(value["receipt"], _RECEIPT_FIELDS, "receipt")
    gate_target = _exact(value["gate_target"], _TARGET_FIELDS, "gate target")
    ri = _exact(receipt["identity"], _GATE_IDENTITY_FIELDS, "receipt gate identity")
    ti = _exact(gate_target["identity"], _GATE_IDENTITY_FIELDS, "target gate identity")
    if (
        value["protocol_version"] != 3
        or isinstance(value["protocol_version"], bool)
        or value["claim_contract"] != "human-action-claim/1"
    ):
        raise ValueError("human action claim version is invalid")
    if stored_identity != identity or any(
        receipt[k] != identity[k] for k in _IDENTITY_FIELDS
    ):
        raise ValueError("human action claim identity mismatch")
    text_fields = (
        receipt["session_namespace"],
        receipt["session_id"],
        receipt["action_id"],
        receipt["run_id"],
        receipt["gate_id"],
        ri["kind"],
        ri["id"],
    )
    if any(not isinstance(x, str) or not x for x in text_fields) or ri["kind"] not in {
        "decision",
        "plan",
        "effect",
    }:
        raise ValueError("human action receipt identity is invalid")
    if (
        receipt["origin"] != "inbound-human"
        or any(
            not is_sha256_digest(receipt[k])
            for k in ("target", "scope_digest", "text_digest")
        )
        or not is_rfc3339_timestamp(receipt["observed_at"])
    ):
        raise ValueError("human action receipt evidence is invalid")
    target_fields = (
        gate_target["run_id"],
        gate_target["gate_id"],
        ti["kind"],
        ti["id"],
    )
    if (
        any(not isinstance(x, str) or not x for x in target_fields)
        or ti["kind"] not in {"decision", "plan", "effect"}
        or any(not is_sha256_digest(gate_target[k]) for k in ("target", "scope_digest"))
    ):
        raise ValueError("human action gate target is invalid")
    if not is_sha256_digest(value["approved_target_sha256"]):
        raise ValueError("human action approved target digest is invalid")
    if (
        receipt["run_id"],
        receipt["gate_id"],
        ri,
        receipt["target"],
        receipt["scope_digest"],
    ) != (
        gate_target["run_id"],
        gate_target["gate_id"],
        ti,
        gate_target["target"],
        gate_target["scope_digest"],
    ):
        raise ValueError("human action receipt and gate target mismatch")
    expected = {
        "run_id": expected_target.run_id,
        "gate_id": expected_target.gate_id,
        "identity": {
            "kind": expected_target.identity.kind,
            "id": expected_target.identity.id,
        },
        "target": expected_target.target,
        "scope_digest": expected_target.scope_digest,
    }
    if (
        gate_target != expected
        or value["approved_target_sha256"] != expected_target.target
    ):
        raise ValueError("human action claim expected target mismatch")
    return value


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("human action claim has duplicate fields")
        result[key] = value
    return result


__all__ = ["load_human_action_claim", "publish_human_action_claim"]
