from __future__ import annotations

from pathlib import Path

from ._authority_records import _active_bindings
from ._locking import _locked
from .advisory import ProposedScopeRef


def active_authority(repo: Path, scope_ref: ProposedScopeRef):
    with _locked(Path(repo)):
        return _active_authority_locked(Path(repo), scope_ref)


def _active_authority_locked(repo: Path, scope_ref: ProposedScopeRef):
    """Recompute census for a caller already holding the repository lock."""
    return _active_bindings(Path(repo), scope_ref)


__all__ = ["active_authority"]
