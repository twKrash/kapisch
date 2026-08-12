from __future__ import annotations

import math
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


def nonfinite_float_references(value: object, reference: str = "") -> list[str]:
    if isinstance(value, float):
        return [reference] if not math.isfinite(value) else []
    if isinstance(value, dict):
        return [
            nested
            for key, item in value.items()
            for nested in nonfinite_float_references(
                item, f"{reference}.{key}" if reference else str(key)
            )
        ]
    if isinstance(value, list):
        return [
            nested
            for index, item in enumerate(value)
            for nested in nonfinite_float_references(item, f"{reference}[{index}]")
        ]
    return []
