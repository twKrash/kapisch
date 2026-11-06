"""Fail-closed validation of canonical Kapisch state and Git source roots."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ._task_artifacts import ContractError
from ._task_governing_inputs import _git_environment

_INVALID_ROOT_MAPPING = "invalid state_root/source_root mapping"


def _git_value(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", *args],
            check=True,
            capture_output=True,
            text=True,
            env=_git_environment(),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(_INVALID_ROOT_MAPPING) from exc
    value = result.stdout.strip()
    if not value:
        raise ContractError(_INVALID_ROOT_MAPPING)
    return value


def _resolved_git_path(root: Path, option: str) -> Path:
    value = Path(_git_value(root, option))
    if not value.is_absolute():
        value = root / value
    try:
        return value.resolve(strict=True)
    except OSError as exc:
        raise ContractError(_INVALID_ROOT_MAPPING) from exc


def _checkout_root(value: str | Path) -> tuple[Path, Path, Path]:
    if not isinstance(value, (str, Path)) or (isinstance(value, str) and not value):
        raise ContractError(_INVALID_ROOT_MAPPING)
    try:
        root = Path(value).resolve(strict=True)
        if not root.is_dir():
            raise ContractError(_INVALID_ROOT_MAPPING)
        top_level = Path(_git_value(root, "--show-toplevel")).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError(_INVALID_ROOT_MAPPING) from exc
    if top_level != root:
        raise ContractError(_INVALID_ROOT_MAPPING)
    return (
        root,
        _resolved_git_path(root, "--git-dir"),
        _resolved_git_path(root, "--git-common-dir"),
    )


def _validated_roots(
    state_root: str | Path, source_root: str | Path
) -> tuple[Path, Path]:
    """Return resolved checkout roots; require primary state and same Git repository."""
    state, state_git, state_common = _checkout_root(state_root)
    source, _, source_common = _checkout_root(source_root)
    if (
        state_git != state_common
        or state_common != state / ".git"
        or source_common != state_common
    ):
        raise ContractError(_INVALID_ROOT_MAPPING)
    return state, source
