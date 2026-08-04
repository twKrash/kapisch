from __future__ import annotations

from dataclasses import dataclass

_ORDER = {
    "PARSE": 0,
    "SCHEMA": 1,
    "REF": 2,
    "LIFECYCLE": 3,
    "REVIEW": 4,
    "DELEG": 5,
}


@dataclass(frozen=True)
class ValidationError:
    code: str
    path: str
    reference: str
    message: str

    def sort_key(self) -> tuple[int, str, str, str]:
        return (
            _ORDER.get(self.code.split("-")[1], 99),
            self.path,
            self.reference,
            self.code,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "reference": self.reference,
            "message": self.message,
        }

    def __str__(self) -> str:
        return f"{self.code} {self.path} {self.reference}: {self.message}"


def sorted_errors(errors: list[ValidationError]) -> tuple[ValidationError, ...]:
    return tuple(sorted(errors, key=ValidationError.sort_key))
