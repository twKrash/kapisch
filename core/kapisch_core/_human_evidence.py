from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from ._protocol_formats import is_rfc3339_timestamp, is_sha256_digest
from .domain import EvidenceRef


class ExternalInputSource(str, Enum):
    EXTERNALLY_SUPPLIED = "externally-supplied"


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


__all__ = ["GateTarget", "HumanActionOrigin", "ObservedHumanAction", "bind_human_receipt"]
