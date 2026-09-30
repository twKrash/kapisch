from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from kapisch_core.bundle import canonical_json
from kapisch_core.capabilities import CapabilityClaims
from kapisch_core.domain import CapabilityEffect, PolicyEvaluation, ProposedAction, Workflow


_DIGEST = re.compile(r"[0-9a-f]{64}")


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
    """Private manifest; supported protocol bounds are inclusive."""

    adapter_id: str
    adapter_version: str
    protocol_version: int
    supported_protocol_range: tuple[int, int]
    bundle_digest: str
    profile_id: str
    asset_digests: tuple[tuple[str, str], ...]
    capabilities: CapabilityClaims

    def __post_init__(self) -> None:
        if not isinstance(self.adapter_version, str) or not self.adapter_version.strip():
            raise ValueError("adapter version must be non-empty")
        if (
            not isinstance(self.supported_protocol_range, tuple)
            or len(self.supported_protocol_range) != 2
            or any(
                isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
                for version in self.supported_protocol_range
            )
        ):
            raise ValueError("supported protocol range must contain two positive integer versions")
        minimum, maximum = self.supported_protocol_range
        if minimum > maximum:
            raise ValueError("supported protocol range minimum exceeds maximum")
        if (
            isinstance(self.protocol_version, bool)
            or not isinstance(self.protocol_version, int)
            or not minimum <= self.protocol_version <= maximum
        ):
            raise ValueError("bundle protocol version is outside supported protocol range")
        if (
            not isinstance(self.bundle_digest, str)
            or not _DIGEST.fullmatch(self.bundle_digest)
        ):
            raise ValueError("bundle digest must be lowercase SHA-256")
        if any(
            not isinstance(path, str)
            or not path
            or not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)
            for path, digest in self.asset_digests
        ):
            raise ValueError("asset digests must bind paths to lowercase SHA-256")

    def to_bytes(self) -> bytes:
        minimum, maximum = self.supported_protocol_range
        payload = {
            "adapter": self.adapter_id,
            "adapter_version": self.adapter_version,
            "protocol_version": self.protocol_version,
            "supported_protocol_range": {"minimum": minimum, "maximum": maximum},
            "bundle_digest": self.bundle_digest,
            "profile_id": self.profile_id,
            "asset_digests": [
                {"path": path, "sha256": digest}
                for path, digest in sorted(self.asset_digests)
            ],
            "capability_claims": {
                "effects": {
                    effect.value: self.capabilities.status_for(effect).value
                    for effect in sorted(CapabilityEffect, key=lambda item: item.value)
                },
                "mutation_free_reviewer": self.capabilities.mutation_free_reviewer.value,
            },
        }
        return canonical_json(payload)


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


# RFC 3339 permits second 60 only on known leap-second days; datetime rejects 60.
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
# fromisoformat accepts broader ISO 8601 forms; this constrains the RFC 3339 shape.
_RFC3339_SHAPE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})"
)


def _valid_rfc3339_timestamp(value: str) -> bool:
    if not _RFC3339_SHAPE.fullmatch(value):
        return False
    normalized = value[:10] + "T" + value[11:]
    if normalized[-1] in "Zz":
        normalized = normalized[:-1] + "+00:00"
    if int(normalized[-2:]) >= 60:
        return False

    leap_second = normalized[17:19] == "60"
    if leap_second:
        normalized = normalized[:17] + "59" + normalized[19:]
    try:
        parsed = datetime.fromisoformat(normalized)
        if not leap_second:
            return parsed.utcoffset() is not None
        utc = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return False
    return utc.hour == 23 and utc.minute == 59 and utc.date().isoformat() in _LEAP_SECOND_DAYS


def human_receipt_matches(
    receipt: HumanActionReceipt | None, target: HumanActionTarget
) -> bool:
    """Check schema shape and exact target binding only.

    Origin and digest values are shape-checked, not authenticated or recomputed.
    Stage 5 verifies input digests, provenance, and durable authority; this does
    not authenticate human identity or establish approval.
    """
    if not isinstance(receipt, HumanActionReceipt) or not isinstance(target, HumanActionTarget):
        return False
    target_fields = (
        target.run_id, target.gate, target.decision_id, target.target, target.scope_digest
    )
    receipt_fields = (
        receipt.run_id, receipt.gate, receipt.decision_id, receipt.target, receipt.scope_digest
    )
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
        or not _DIGEST.fullmatch(receipt.scope_digest)
        or not _DIGEST.fullmatch(receipt.text_digest)
        or receipt_fields != target_fields
    ):
        return False
    return _valid_rfc3339_timestamp(receipt.observed_at)
