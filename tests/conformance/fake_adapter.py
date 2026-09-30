from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from kapisch_core.bundle import verify_bundle
from kapisch_core.capabilities import CapabilityClaims
from kapisch_core.domain import PolicyEvaluation, ProposedAction, Workflow
from kapisch_core.policy import evaluate_action_policy
from tooling.conformance.adapter import (
    AdapterManifest,
    GeneratedAsset,
    HumanActionReceipt,
    RuntimeProfile,
)


class FakeHarnessAdapter:
    """In-memory conformance adapter; has no host filesystem or dispatch integration."""

    capabilities: CapabilityClaims

    def __init__(
        self,
        capabilities: CapabilityClaims | None = None,
        human_action: HumanActionReceipt | None = None,
    ) -> None:
        self.capabilities = capabilities or CapabilityClaims()
        self._human_action = human_action

    def observe_human_action(self) -> HumanActionReceipt | None:
        return self._human_action

    def compile(
        self, bundle_bytes: bytes, bundle_digest: str, profile: RuntimeProfile
    ) -> tuple[tuple[GeneratedAsset, ...], bytes]:
        bundle = verify_bundle(bundle_bytes, bundle_digest)
        assets = tuple(
            GeneratedAsset(f"agents/kapisch-{role}.md", entry["contract"].encode("utf-8"))
            for role, entry in sorted(bundle.payload["roles"].items())
        )
        manifest = AdapterManifest(
            adapter_id="fake",
            adapter_version="1.0.0",
            protocol_version=bundle.protocol_version,
            supported_protocol_range=(3, 3),
            bundle_digest=bundle_digest,
            profile_id=profile.profile_id,
            asset_digests=tuple(
                (asset.path, _digest(asset.content)) for asset in assets
            ),
            capabilities=self.capabilities,
        )
        return assets, manifest.to_bytes()

    def evaluate_action(
        self,
        bundle_bytes: bytes,
        bundle_digest: str,
        workflow: Workflow,
        action: ProposedAction,
        *,
        workflow_metadata: Mapping[str, Any] | None = None,
    ) -> PolicyEvaluation:
        # Metadata is descriptive only. It cannot alter static policy decisions.
        verify_bundle(bundle_bytes, bundle_digest)
        _ = workflow_metadata
        return evaluate_action_policy(workflow, action, self.capabilities)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
