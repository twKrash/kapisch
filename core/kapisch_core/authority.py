from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._authority_census import active_authority as _census_bindings
from ._gate_approval import load_gate_approval, publish_gate_approval
from ._human_action_ownership import load_human_action_claim, publish_human_action_claim
from ._human_evidence import (
    ExternalArtifactInput,
    ExternalInputSource,
    GateApprovalTarget,
    GateIdentity,
    GateTarget,
    HumanActionOrigin,
    ObservedGateAction,
    ObservedHumanAction,
    bind_external_human_artifact,
    bind_gate_action,
    bind_human_receipt,
)
from .advisory import ProposedScopeRef


@dataclass(frozen=True)
class AuthorityBinding:
    origin_run_id: str
    snapshot_id: str
    decision_id: str
    acceptance_record_sha256: str
    scope_ref: dict[str, str]
    applicability: dict[str, Any]
    source_dependencies: tuple[dict[str, str], ...]


def active_authority(
    repo: Path, scope_ref: ProposedScopeRef
) -> tuple[AuthorityBinding, ...]:
    return tuple(
        AuthorityBinding(
            binding["origin_run_id"],
            binding["snapshot_id"],
            binding["decision_id"],
            binding["acceptance_record_sha256"],
            binding["scope_ref"],
            binding["applicability"],
            tuple(binding["source_dependencies"]),
        )
        for binding in _census_bindings(Path(repo), scope_ref)
    )


__all__ = [
    "AuthorityBinding",
    "ExternalArtifactInput",
    "ExternalInputSource",
    "GateApprovalTarget",
    "GateIdentity",
    "GateTarget",
    "HumanActionOrigin",
    "ObservedGateAction",
    "ObservedHumanAction",
    "active_authority",
    "bind_external_human_artifact",
    "bind_gate_action",
    "bind_human_receipt",
    "load_gate_approval",
    "load_human_action_claim",
    "publish_gate_approval",
    "publish_human_action_claim",
]
