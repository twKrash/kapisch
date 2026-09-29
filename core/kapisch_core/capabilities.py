from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .domain import CapabilityEffect


class CapabilityStatus(str, Enum):
    ENFORCED = "enforced"
    ADVISORY = "advisory"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CapabilityClaim:
    effect: CapabilityEffect
    status: CapabilityStatus


@dataclass(frozen=True)
class CapabilityClaims:
    claims: tuple[CapabilityClaim, ...] = ()
    mutation_free_reviewer: CapabilityStatus = CapabilityStatus.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.claims, tuple) or any(
            not isinstance(claim, CapabilityClaim)
            or not isinstance(claim.effect, CapabilityEffect)
            or not isinstance(claim.status, CapabilityStatus)
            for claim in self.claims
        ):
            raise TypeError("claims must be a tuple of valid CapabilityClaim")
        if not isinstance(self.mutation_free_reviewer, CapabilityStatus):
            raise TypeError("mutation_free_reviewer must be a CapabilityStatus")
        effects = [claim.effect for claim in self.claims]
        if len(effects) != len(set(effects)):
            raise ValueError("each capability effect may have one claim")

    def status_for(self, effect: CapabilityEffect) -> CapabilityStatus:
        return next((claim.status for claim in self.claims if claim.effect is effect), CapabilityStatus.UNKNOWN)


__all__ = ["CapabilityClaim", "CapabilityClaims", "CapabilityStatus"]
