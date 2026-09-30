from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from kapisch_core.capabilities import CapabilityClaims
from kapisch_core.domain import CapabilityEffect, PolicyEvaluation, ProposedAction, Workflow


@dataclass(frozen=True)
class RuntimeProfile:
    profile_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("runtime profile ID must be non-empty")


@dataclass(frozen=True)
class GeneratedAsset:
    path: str
    content: bytes


@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    protocol_version: int
    bundle_digest: str
    profile_id: str
    assets: tuple[tuple[str, str], ...]
    capabilities: CapabilityClaims

    def to_bytes(self) -> bytes:
        payload = {
            "adapter": self.adapter_id,
            "protocol_version": self.protocol_version,
            "bundle_digest": self.bundle_digest,
            "profile_id": self.profile_id,
            "assets": [
                {"path": path, "sha256": digest} for path, digest in self.assets
            ],
            "capabilities": {
                "effects": {
                    effect.value: self.capabilities.status_for(effect).value
                    for effect in sorted(CapabilityEffect, key=lambda item: item.value)
                },
                "mutation_free_reviewer": self.capabilities.mutation_free_reviewer.value,
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class HumanActionTarget:
    run_id: str
    gate: str
    decision_id: str
    target: str
    scope_digest: str


@dataclass(frozen=True)
class HumanActionReceipt:
    action_id: str
    session_id: str
    origin: str
    run_id: str
    gate: str
    decision_id: str
    target: str
    scope_digest: str
    text_digest: str
    observed_at: str


class HarnessAdapter(Protocol):
    capabilities: CapabilityClaims

    def compile(
        self, bundle_bytes: bytes, bundle_digest: str, profile: RuntimeProfile
    ) -> tuple[tuple[GeneratedAsset, ...], bytes]: ...

    def observe_human_action(self) -> HumanActionReceipt | None: ...

    def evaluate_action(
        self,
        bundle_bytes: bytes,
        bundle_digest: str,
        workflow: Workflow,
        action: ProposedAction,
        *,
        workflow_metadata: Mapping[str, Any] | None = None,
    ) -> PolicyEvaluation: ...


_DIGEST = re.compile(r"[0-9a-f]{64}")
# ponytail: IERS-listed leap seconds through Bulletin C 72; refresh set when IERS announces another.
_LEAP_SECOND_DAYS = frozenset(
    {
        "1972-06-30", "1972-12-31", "1973-12-31", "1974-12-31", "1975-12-31",
        "1976-12-31", "1977-12-31", "1978-12-31", "1979-12-31", "1981-06-30",
        "1982-06-30", "1983-06-30", "1985-06-30", "1987-12-31", "1989-12-31",
        "1990-12-31", "1992-06-30", "1993-06-30", "1994-06-30", "1995-12-31",
        "1997-06-30", "1998-12-31", "2005-12-31", "2008-12-31", "2012-06-30",
        "2015-06-30", "2016-12-31",
    }
)
_RFC3339 = re.compile(
    r"[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])[Tt]"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:(?:[0-5][0-9]|60)"
    r"(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def human_receipt_matches(
    receipt: HumanActionReceipt | None, target: HumanActionTarget
) -> bool:
    if not isinstance(receipt, HumanActionReceipt):
        return False
    target_fields = (target.run_id, target.gate, target.decision_id, target.target, target.scope_digest)
    receipt_fields = (receipt.run_id, receipt.gate, receipt.decision_id, receipt.target, receipt.scope_digest)
    required_strings = (
        *target_fields,
        *receipt_fields,
        receipt.action_id,
        receipt.session_id,
        receipt.origin,
        receipt.text_digest,
        receipt.observed_at,
    )
    if any(not isinstance(value, str) or not value for value in required_strings):
        return False
    if (
        receipt.origin != "inbound-human"
        or receipt.gate not in {"human-decision", "side-effect"}
        or not receipt.action_id
        or not receipt.session_id
        or not _DIGEST.fullmatch(receipt.scope_digest)
        or not _DIGEST.fullmatch(receipt.text_digest)
        or not _RFC3339.fullmatch(receipt.observed_at)
        or receipt_fields != target_fields
    ):
        return False
    normalized = receipt.observed_at[:10] + "T" + receipt.observed_at[11:]
    if normalized[-1] in "Zz":
        normalized = normalized[:-1] + "+00:00"
    if normalized[17:19] == "60":
        previous_second = normalized[:17] + "59" + normalized[19:]
        try:
            utc = datetime.fromisoformat(previous_second).astimezone(timezone.utc)
        except (ValueError, OverflowError):
            return False
        return utc.hour == 23 and utc.minute == 59 and utc.date().isoformat() in _LEAP_SECOND_DAYS
    try:
        return datetime.fromisoformat(normalized).utcoffset() is not None
    except ValueError:
        return False
