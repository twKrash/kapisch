from __future__ import annotations

from pathlib import Path

from ._authority_records import _active_bindings
from .advisory import ProposedScopeRef


def active_authority(repo: Path, scope_ref: ProposedScopeRef):
    return _active_bindings(Path(repo), scope_ref)


__all__ = ["active_authority"]
