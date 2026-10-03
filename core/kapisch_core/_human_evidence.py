from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re

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


_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_LEAP_DAYS = {"1972-06-30", "1972-12-31", "1973-12-31", "1974-12-31", "1975-12-31", "1976-12-31", "1977-12-31", "1978-12-31", "1979-12-31", "1981-06-30", "1982-06-30", "1983-06-30", "1985-06-30", "1987-12-31", "1989-12-31", "1990-12-31", "1992-06-30", "1993-06-30", "1994-06-30", "1995-12-31", "1997-06-30", "1998-12-31", "2005-12-31", "2008-12-31", "2012-06-30", "2015-06-30", "2016-12-31"}


def _valid_timestamp(value: str) -> bool:
    if not _SHAPE.fullmatch(value):
        return False
    normalized = value[:10] + "T" + value[11:]
    if normalized[-1] in "Zz":
        normalized = normalized[:-1] + "+00:00"
    if int(normalized[11:13]) > 23 or int(normalized[14:16]) > 59 or int(normalized[17:19]) > 60 or int(normalized[-5:-3]) > 23 or int(normalized[-2:]) > 59:
        return False
    leap = normalized[17:19] == "60"
    if leap:
        normalized = normalized[:17] + "59" + normalized[19:]
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.utcoffset() is not None and (not leap or (parsed.astimezone(timezone.utc).strftime("%H:%M:%S") == "23:59:59" and parsed.astimezone(timezone.utc).date().isoformat() in _LEAP_DAYS))
    except (ValueError, OverflowError):
        return False


def bind_external_human_artifact(evidence: ExternalArtifactInput, target: GateTarget) -> EvidenceRef:
    if not isinstance(evidence, ExternalArtifactInput) or not isinstance(target, GateTarget):
        raise TypeError("evidence and target must use authority types")
    if evidence.source is not ExternalInputSource.EXTERNALLY_SUPPLIED:
        raise ValueError("artifact source is not externally supplied")
    if not isinstance(evidence.reference, str) or not evidence.reference or not isinstance(evidence.exact_bytes, bytes):
        raise ValueError("artifact reference and exact bytes are required")
    try:
        record = json.loads(evidence.exact_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        record = None
    required = ("approval_id", "run_id", "gate", "decision_id", "decision", "target", "scope_digest", "source")
    if isinstance(record, dict) and record.get("protocol_version") == 3 and all(key in record for key in required):
        raise ValueError("controller-produced approval record cannot be external artifact evidence")
    if any(not isinstance(value, str) or not value for value in (target.run_id, target.gate_id, target.decision_id, target.target, target.scope_digest)):
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
    if not _DIGEST.fullmatch(receipt.scope_digest) or not _DIGEST.fullmatch(receipt.text_digest) or not _valid_timestamp(receipt.observed_at):
        raise ValueError("receipt digest or timestamp is invalid")
    if (receipt.run_id, receipt.gate_id, receipt.decision_id, receipt.target, receipt.scope_digest) != (target.run_id, target.gate_id, target.decision_id, target.target, target.scope_digest):
        raise ValueError("receipt does not bind the exact gate target")
    payload = {"origin": receipt.origin.value, "action_id": receipt.action_id, "session_id": receipt.session_id, "run_id": receipt.run_id, "gate_id": receipt.gate_id, "decision_id": receipt.decision_id, "target": receipt.target, "scope_digest": receipt.scope_digest, "text_digest": receipt.text_digest, "observed_at": receipt.observed_at}
    return EvidenceRef("host-observed-human-action", json.dumps(payload, sort_keys=True, separators=(",", ":")))


__all__ = ["GateTarget", "HumanActionOrigin", "ObservedHumanAction", "bind_human_receipt"]
