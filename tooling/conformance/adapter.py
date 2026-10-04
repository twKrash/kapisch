from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from kapisch_core._protocol_formats import is_rfc3339_timestamp, is_sha256_digest
from kapisch_core.bundle import canonical_json
from kapisch_core.capabilities import CapabilityClaims
from kapisch_core.domain import (
    CapabilityEffect,
    PolicyEvaluation,
    ProposedAction,
    Workflow,
)


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
        if (
            not isinstance(self.adapter_version, str)
            or not self.adapter_version.strip()
        ):
            raise ValueError("adapter version must be non-empty")
        if (
            not isinstance(self.supported_protocol_range, tuple)
            or len(self.supported_protocol_range) != 2
            or any(
                isinstance(version, bool) or not isinstance(version, int) or version < 1
                for version in self.supported_protocol_range
            )
        ):
            raise ValueError(
                "supported protocol range must contain two positive integer versions"
            )
        minimum, maximum = self.supported_protocol_range
        if minimum > maximum:
            raise ValueError("supported protocol range minimum exceeds maximum")
        if (
            isinstance(self.protocol_version, bool)
            or not isinstance(self.protocol_version, int)
            or not minimum <= self.protocol_version <= maximum
        ):
            raise ValueError(
                "bundle protocol version is outside supported protocol range"
            )
        if not isinstance(self.bundle_digest, str) or not is_sha256_digest(
            self.bundle_digest
        ):
            raise ValueError("bundle digest must be lowercase SHA-256")
        if any(
            not isinstance(path, str)
            or not path
            or not isinstance(digest, str)
            or not is_sha256_digest(digest)
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


def human_receipt_matches(
    receipt: HumanActionReceipt | None, target: HumanActionTarget
) -> bool:
    """Check schema shape and exact target binding only.

    Origin and digest values are shape-checked, not authenticated or recomputed.
    Stage 5 verifies input digests, provenance, and durable authority; this does
    not authenticate human identity or establish approval.
    """
    if not isinstance(receipt, HumanActionReceipt) or not isinstance(
        target, HumanActionTarget
    ):
        return False
    target_fields = (
        target.run_id,
        target.gate,
        target.decision_id,
        target.target,
        target.scope_digest,
    )
    receipt_fields = (
        receipt.run_id,
        receipt.gate,
        receipt.decision_id,
        receipt.target,
        receipt.scope_digest,
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
        or not is_sha256_digest(receipt.scope_digest)
        or not is_sha256_digest(receipt.text_digest)
        or receipt_fields != target_fields
    ):
        return False
    return is_rfc3339_timestamp(receipt.observed_at)
