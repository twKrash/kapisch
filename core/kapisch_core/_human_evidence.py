from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from ._protocol_formats import is_rfc3339_timestamp, is_sha256_digest
from .bundle import canonical_json
from .domain import EvidenceRef


class ExternalInputSource(str, Enum):
    EXTERNALLY_SUPPLIED = "externally-supplied"


@dataclass(frozen=True)
class GateIdentity:
    kind: str
    id: str


@dataclass(frozen=True)
class GateApprovalTarget:
    run_id: str
    gate_id: str
    identity: GateIdentity
    target: str
    scope_digest: str


@dataclass(frozen=True)
class ObservedGateAction:
    origin: HumanActionOrigin
    session_namespace: str
    session_id: str
    action_id: str
    run_id: str
    gate_id: str
    identity: GateIdentity
    target: str
    scope_digest: str
    text_digest: str
    observed_at: str


_SUPPORTED_GATE_IDENTITY_KINDS = frozenset({"decision", "plan", "effect"})


def _validate_gate_identity_kind(kind: object, source: str) -> None:
    if not isinstance(kind, str) or not kind:
        raise ValueError(f"{source} identity kind must be a non-empty string")
    if kind not in _SUPPORTED_GATE_IDENTITY_KINDS:
        raise ValueError(f"{source} identity kind is unsupported")


def _validate_gate_approval_target(target: GateApprovalTarget) -> None:
    """Validate the complete caller target before it can influence persistence access."""
    if type(target) is not GateApprovalTarget or type(target.identity) is not GateIdentity:
        raise TypeError("target must use V3 authority type")
    _validate_gate_identity_kind(target.identity.kind, "gate target")
    fields = (target.run_id, target.gate_id, target.identity.id, target.target, target.scope_digest)
    if any(not isinstance(value, str) or not value for value in fields):
        raise ValueError("gate target fields must be non-empty strings")
    if not is_sha256_digest(target.target) or not is_sha256_digest(target.scope_digest):
        raise ValueError("gate target digest is invalid")


def bind_gate_action(receipt: ObservedGateAction, target: GateApprovalTarget) -> EvidenceRef:
    if type(receipt) is not ObservedGateAction or type(receipt.identity) is not GateIdentity:
        raise TypeError("receipt and target must use V3 authority types")
    _validate_gate_approval_target(target)
    _validate_gate_identity_kind(receipt.identity.kind, "receipt")
    if receipt.origin is not HumanActionOrigin.INBOUND_HUMAN:
        raise ValueError("receipt origin is not inbound human")
    fields = (receipt.session_namespace, receipt.session_id, receipt.action_id, receipt.run_id, receipt.gate_id, receipt.identity.kind, receipt.identity.id, receipt.target, receipt.scope_digest, receipt.text_digest, receipt.observed_at)
    if any(not isinstance(x, str) or not x for x in fields):
        raise ValueError("receipt fields must be non-empty strings")
    if any(not is_sha256_digest(x) for x in (receipt.target, receipt.scope_digest, receipt.text_digest)) or not is_rfc3339_timestamp(receipt.observed_at):
        raise ValueError("receipt digest or timestamp is invalid")
    if (receipt.run_id, receipt.gate_id, receipt.identity, receipt.target, receipt.scope_digest) != (target.run_id, target.gate_id, target.identity, target.target, target.scope_digest):
        raise ValueError("receipt does not bind exact gate target")
    return EvidenceRef("host-observed-gate-action", json.dumps({"origin":receipt.origin.value, **{k: getattr(receipt,k) for k in ("session_namespace", "session_id", "action_id", "run_id", "gate_id", "target", "scope_digest", "text_digest", "observed_at")}, "identity":{"kind":receipt.identity.kind,"id":receipt.identity.id}}, sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class ExternalArtifactInput:
    reference: str
    exact_bytes: bytes
    source: ExternalInputSource


class HumanActionOrigin(str, Enum):
    INBOUND_HUMAN = "inbound-human"


@dataclass(frozen=True)
class ObservedHumanAction:
    origin: HumanActionOrigin
    action_id: str
    session_id: str
    run_id: str
    gate_id: str
    decision_id: str
    target: str
    scope_digest: str
    text_digest: str
    observed_at: str


@dataclass(frozen=True)
class GateTarget:
    run_id: str
    gate_id: str
    decision_id: str
    target: str
    scope_digest: str


# Bound accepted JSON nesting independently of the runtime's recursion limit.
_MAX_EXTERNAL_JSON_NESTING = 128


# Reject duplicates before dict construction can hide overwritten subtrees.
def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("external artifact JSON contains duplicate object key")
        result[key] = value
    return result


def _ensure_supported_json_nesting(value: object) -> None:
    stack = [(iter((value,)), 0)]
    while stack:
        iterator, depth = stack[-1]
        try:
            current = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        if isinstance(current, (dict, list)):
            nested_depth = depth + 1
            if nested_depth > _MAX_EXTERNAL_JSON_NESTING:
                raise ValueError("external artifact JSON exceeds supported nesting depth")
            children = current.values() if isinstance(current, dict) else current
            stack.append((iter(children), nested_depth))


def validate_external_human_approval_artifact(
    evidence: ExternalArtifactInput,
    target: GateApprovalTarget,
) -> None:
    if not isinstance(evidence, ExternalArtifactInput):
        raise TypeError("external human approval must use ExternalArtifactInput")
    if evidence.source is not ExternalInputSource.EXTERNALLY_SUPPLIED:
        raise ValueError("external human approval source is not externally supplied")
    _validate_human_approval_bytes(evidence.exact_bytes, target)


def _validate_human_approval_bytes(exact_bytes: bytes, target: GateApprovalTarget) -> None:
    if not isinstance(exact_bytes, bytes):
        raise TypeError("external human approval artifact must be bytes")
    _validate_gate_approval_target(target)
    try:
        record = json.loads(
            exact_bytes,
            parse_int=lambda value: int(value) if len(value) <= 15 else value,
            object_pairs_hook=_unique_json_object,
        )
        _ensure_supported_json_nesting(record)
    except RecursionError as error:
        raise ValueError("external human approval artifact exceeds supported nesting depth") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("external human approval artifact is invalid JSON") from error
    fields = {"protocol_version", "run_id", "gate_id", "identity", "decision", "target", "scope_digest"}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("external human approval artifact has invalid shape")
    identity = record["identity"]
    if not isinstance(identity, dict) or set(identity) != {"kind", "id"}:
        raise ValueError("external human approval identity has invalid shape")
    string_fields = (record["run_id"], record["gate_id"], identity["kind"], identity["id"],
                     record["decision"], record["target"], record["scope_digest"])
    if any(not isinstance(value, str) or not value for value in string_fields):
        raise ValueError("external human approval fields must be non-empty strings")
    if not isinstance(record["protocol_version"], int) or isinstance(record["protocol_version"], bool) or record["protocol_version"] != 3:
        raise ValueError("external human approval protocol version is invalid")
    expected = {
        "protocol_version": 3,
        "run_id": target.run_id,
        "gate_id": target.gate_id,
        "identity": {"kind": target.identity.kind, "id": target.identity.id},
        "decision": "approve",
        "target": target.target,
        "scope_digest": target.scope_digest,
    }
    if record != expected:
        raise ValueError("external human approval does not bind exact GateTarget")
    try:
        canonical = canonical_json(record)
    except ValueError as error:
        raise ValueError("external human approval artifact is invalid canonical JSON") from error
    if canonical != exact_bytes:
        raise ValueError("external human approval artifact is noncanonical")


def bind_external_human_artifact(evidence: ExternalArtifactInput, target: GateTarget) -> EvidenceRef:
    if not isinstance(evidence, ExternalArtifactInput) or not isinstance(target, GateTarget):
        raise TypeError("evidence and target must use authority types")
    if evidence.source is not ExternalInputSource.EXTERNALLY_SUPPLIED:
        raise ValueError("artifact source is not externally supplied")
    if not isinstance(evidence.reference, str) or not evidence.reference or not isinstance(evidence.exact_bytes, bytes):
        raise ValueError("artifact reference and exact bytes are required")
    try:
        record = json.loads(
            evidence.exact_bytes,
            parse_int=lambda value: int(value) if len(value) <= 15 else value,
            object_pairs_hook=_unique_json_object,
        )
        _ensure_supported_json_nesting(record)
    except RecursionError as exc:
        raise ValueError("external artifact JSON exceeds supported nesting depth") from exc
    except (UnicodeDecodeError, json.JSONDecodeError):
        record = None
    required = ("approval_id", "run_id", "gate", "decision_id", "decision", "target", "scope_digest", "source")
    version = record.get("protocol_version") if isinstance(record, dict) else None
    if isinstance(record, dict) and isinstance(version, (int, float)) and not isinstance(version, bool) and version == 3 and all(key in record for key in required):
        raise ValueError("controller-produced approval record cannot be external artifact evidence")
    if not is_sha256_digest(target.scope_digest):
        raise ValueError("gate scope digest must be 64 lowercase hexadecimal characters")
    if any(not isinstance(value, str) or not value for value in (target.run_id, target.gate_id, target.decision_id, target.target)):
        raise ValueError("gate target fields must be non-empty strings")
    payload = {"reference": evidence.reference, "source": evidence.source.value, "sha256": hashlib.sha256(evidence.exact_bytes).hexdigest(), "run_id": target.run_id, "gate_id": target.gate_id, "decision_id": target.decision_id, "target": target.target, "scope_digest": target.scope_digest}
    return EvidenceRef("external-human-artifact", json.dumps(payload, sort_keys=True, separators=(",", ":")))


def bind_human_receipt(receipt: ObservedHumanAction, target: GateTarget) -> EvidenceRef:
    if not isinstance(receipt, ObservedHumanAction) or not isinstance(target, GateTarget):
        raise TypeError("receipt and target must use authority types")
    if receipt.origin is not HumanActionOrigin.INBOUND_HUMAN:
        raise ValueError("receipt origin is not factual inbound human evidence")
    values = (receipt.action_id, receipt.session_id, receipt.run_id, receipt.gate_id, receipt.decision_id, receipt.target, receipt.scope_digest, receipt.text_digest, receipt.observed_at)
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("receipt fields must be non-empty strings")
    if not is_sha256_digest(receipt.scope_digest) or not is_sha256_digest(receipt.text_digest) or not is_rfc3339_timestamp(receipt.observed_at):
        raise ValueError("receipt digest or timestamp is invalid")
    if (receipt.run_id, receipt.gate_id, receipt.decision_id, receipt.target, receipt.scope_digest) != (target.run_id, target.gate_id, target.decision_id, target.target, target.scope_digest):
        raise ValueError("receipt does not bind the exact gate target")
    payload = {"origin": receipt.origin.value, "action_id": receipt.action_id, "session_id": receipt.session_id, "run_id": receipt.run_id, "gate_id": receipt.gate_id, "decision_id": receipt.decision_id, "target": receipt.target, "scope_digest": receipt.scope_digest, "text_digest": receipt.text_digest, "observed_at": receipt.observed_at}
    return EvidenceRef("host-observed-human-action", json.dumps(payload, sort_keys=True, separators=(",", ":")))


__all__ = ["GateApprovalTarget", "GateIdentity", "GateTarget", "HumanActionOrigin", "ObservedGateAction", "ObservedHumanAction", "bind_gate_action", "bind_human_receipt"]
