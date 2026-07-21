from __future__ import annotations

from collections.abc import Mapping

from .errors import ValidationError


def is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def non_empty_string(
    value: object,
    errors: list[ValidationError],
    error: ValidationError,
) -> bool:
    if not isinstance(value, str) or not value:
        errors.append(error)
        return False
    return True


def string_list(
    value: object,
    errors: list[ValidationError],
    error: ValidationError,
    *,
    sorted_unique: bool = False,
) -> bool:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(error)
        return False
    if sorted_unique and value != sorted(set(value)):
        errors.append(error)
        return False
    return True


def table(value: object) -> bool:
    return isinstance(value, Mapping)
