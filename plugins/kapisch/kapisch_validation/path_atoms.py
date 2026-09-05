from __future__ import annotations


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
