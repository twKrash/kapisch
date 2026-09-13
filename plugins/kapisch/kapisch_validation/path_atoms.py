from __future__ import annotations

from pathlib import Path


_RESERVED_WINDOWS_BASENAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_INVALID_FILENAME_CHARS = frozenset('<>:"/\\|?*')


def is_portable_filename_atom(value: object) -> bool:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        return False
    if value[-1] in {".", " "} or any(ord(character) < 32 or ord(character) == 127 or character in _INVALID_FILENAME_CHARS for character in value):
        return False
    return value.split(".", 1)[0].upper() not in _RESERVED_WINDOWS_BASENAMES


def _is_valid_path_component(value: object) -> bool:
    """Return whether a component meets the durable relative-path grammar."""
    return isinstance(value, str) and bool(value) and value not in {".", ".."} and "\x00" not in value


def validate_relative_posix_path(value: object) -> str:
    """Validate and return a relative, slash-separated portable path."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("path must be a non-empty string")
    drive_prefix = len(value) >= 2 and value[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" and value[1] == ":"
    if value.startswith("/") or drive_prefix or "\\" in value or value.endswith("/"):
        raise ValueError("path is not a relative POSIX path")
    components = value.split("/")
    if not components or any(not _is_valid_path_component(component) for component in components):
        raise ValueError("path contains an invalid component")
    return value


def canonical_relative_path(path: Path, *, root: Path) -> str:
    """Encode an absolute native path relative to an explicit absolute root.

    Artifact-specific regular-file, symlink, and reparse-point validation must
    precede this lexical conversion.
    """
    if not isinstance(path, Path) or not isinstance(root, Path) or not path.is_absolute() or not root.is_absolute():
        raise ValueError("path and root must be absolute native Paths")
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError("path is outside root") from error
    return validate_relative_posix_path("/".join(relative.parts))
