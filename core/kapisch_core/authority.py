from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
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
class _AuthorityBinding:
    origin_run_id: str
    snapshot_id: str
    decision_id: str
    acceptance_record_sha256: str
    scope_ref: ProposedScopeRef
    applicability: Mapping[str, Any]
    source_dependencies: tuple[Mapping[str, str], ...]

    def __post_init__(self) -> None:
        applicability = dict(self.applicability)
        if "keys" in applicability:
            applicability["keys"] = tuple(applicability["keys"])
        object.__setattr__(self, "applicability", MappingProxyType(applicability))
        object.__setattr__(
            self,
            "source_dependencies",
            tuple(
                MappingProxyType(dict(dependency))
                for dependency in self.source_dependencies
            ),
        )


def active_authority(
    repo: Path, scope_ref: ProposedScopeRef
) -> tuple[_AuthorityBinding, ...]:
    return tuple(
        _AuthorityBinding(
            binding["origin_run_id"],
            binding["snapshot_id"],
            binding["decision_id"],
            binding["acceptance_record_sha256"],
            ProposedScopeRef(**binding["scope_ref"]),
            binding["applicability"],
            tuple(binding["source_dependencies"]),
        )
        for binding in _census_bindings(Path(repo), scope_ref)
    )


__all__ = [
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
