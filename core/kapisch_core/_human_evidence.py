from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib

from .domain import EvidenceRef


class HumanActionOrigin(str, Enum):
    INBOUND_HUMAN = "inbound-human"


@dataclass(frozen=True)
class ObservedHumanAction:
    origin: HumanActionOrigin
    action_id: str
    action: str
    text: str
    run_id: str
    gate_id: str
    target: str
    scope: str
    observed_at: str


@dataclass(frozen=True)
class GateTarget:
    run_id: str
    gate_id: str
    target: str
    scope: str


def bind_human_receipt(receipt: ObservedHumanAction, target: GateTarget) -> EvidenceRef:
    if not isinstance(receipt, ObservedHumanAction) or not isinstance(target, GateTarget):
        raise TypeError("receipt and target must use authority types")
    if receipt.origin is not HumanActionOrigin.INBOUND_HUMAN:
        raise ValueError("receipt origin is not factual inbound human evidence")
    if not all((receipt.action_id, receipt.action, receipt.text, receipt.run_id, receipt.gate_id,
                receipt.target, receipt.scope, receipt.observed_at)):
        raise ValueError("receipt fields must be non-empty")
    try:
        datetime.fromisoformat(receipt.observed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("receipt timestamp is invalid") from error
    if (receipt.run_id, receipt.gate_id, receipt.target, receipt.scope) != (
            target.run_id, target.gate_id, target.target, target.scope):
        raise ValueError("receipt does not bind the exact gate target")
    digest = hashlib.sha256((receipt.action + "\0" + receipt.text).encode("utf-8")).hexdigest()
    return EvidenceRef("host-observed-human-action", f"{receipt.action_id}:{digest}")
