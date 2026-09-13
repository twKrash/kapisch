"""Canonical renderer for the task-local knowledge ledger (version 1)."""

from __future__ import annotations

import copy
import re
from .canonical_toml import render_toml


ROOT_FIELDS = ("version", "records", "extensions")
RECORD_FIELDS = (
    "id", "kind", "scope", "authority", "status", "statement", "source",
    "verified_at_revision", "superseded_by", "expires_at_revision",
    "applies_when", "preconditions", "forbidden_cases", "required_verification",
    "fallback_executor", "fallback_behavior", "extensions",
)
REQUIRED_RECORD_FIELDS = {
    "id", "kind", "scope", "authority", "status", "statement", "source", "applies_when",
}
OPTIONAL_RECORD_FIELDS = set(RECORD_FIELDS) - REQUIRED_RECORD_FIELDS
KINDS = {"fact", "decision", "tradeoff", "hint", "shortcut", "pitfall", "question"}
AUTHORITIES = {"binding", "advisory", "informational"}
STATUSES = {"candidate", "verified", "promoted", "rejected", "superseded", "expired"}
SCOPES = {
    "repository", "workflow:kapisch",
}
_EXTENSION_RE = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+\Z")


def _error(message: str) -> ValueError:
    return ValueError(f"invalid knowledge ledger: {message}")


def _string(value: object, field: str, *, non_empty: bool = True) -> str:
    if not isinstance(value, str) or (non_empty and not value):
        raise _error(f"{field} must be a non-empty string")
    return value


def _extensions(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _error(f"{field} must be a table")
    for namespace in value:
        if not isinstance(namespace, str) or _EXTENSION_RE.fullmatch(namespace) is None:
            raise _error(f"{field} keys must be reverse-DNS namespaces")
    return copy.deepcopy(value)


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise _error(f"{field} must be an array of strings")
    result: list[str] = []
    for item in value:
        result.append(_string(item, field))
    return result


def _record(raw: object, index: int) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise _error(f"records[{index}] must be a table")
    if not all(isinstance(key, str) for key in raw):
        raise _error(f"records[{index}] keys must be strings")
    unknown = set(raw) - set(RECORD_FIELDS)
    if unknown:
        raise _error(f"records[{index}] has unknown field {sorted(unknown)[0]!r}")
    missing = REQUIRED_RECORD_FIELDS - set(raw)
    if missing:
        raise _error(f"records[{index}] is missing field {sorted(missing)[0]!r}")
    data = copy.deepcopy(raw)
    for field in ("id", "scope", "statement", "source"):
        _string(data[field], f"records[{index}].{field}")
    _string(data["kind"], f"records[{index}].kind")
    _string(data["authority"], f"records[{index}].authority")
    _string(data["status"], f"records[{index}].status")
    if data["kind"] not in KINDS:
        raise _error(f"records[{index}].kind has unsupported value")
    if data["authority"] not in AUTHORITIES:
        raise _error(f"records[{index}].authority has unsupported value")
    if data["status"] not in STATUSES:
        raise _error(f"records[{index}].status has unsupported value")
    scope = data["scope"]
    if scope not in SCOPES and not (
        isinstance(scope, str)
        and any(scope.startswith(prefix) and len(scope) > len(prefix) for prefix in ("task:", "milestone:", "module:"))
    ):
        raise _error(f"records[{index}].scope has unsupported value")

    applies = _string_list(data["applies_when"], f"records[{index}].applies_when")
    data["applies_when"] = sorted(set(applies))
    for field in ("verified_at_revision", "superseded_by", "expires_at_revision", "fallback_executor", "fallback_behavior"):
        if field in data:
            _string(data[field], f"records[{index}].{field}")
    for field in ("preconditions", "forbidden_cases", "required_verification"):
        if field in data:
            data[field] = _string_list(data[field], f"records[{index}].{field}")
    if "extensions" in data:
        record_extensions = _extensions(
            data["extensions"], f"records[{index}].extensions"
        )
        if record_extensions == {}:
            data.pop("extensions")
        else:
            data["extensions"] = record_extensions
    if data["status"] == "superseded" and "superseded_by" not in data:
        raise _error(f"records[{index}].superseded_by is required for superseded records")
    if data["status"] == "expired" and "expires_at_revision" not in data:
        raise _error(f"records[{index}].expires_at_revision is required for expired records")
    if data["kind"] == "shortcut":
        for field in ("preconditions", "forbidden_cases", "required_verification"):
            if not data.get(field):
                raise _error(f"records[{index}].{field} is required for shortcut records")
        if not data.get("fallback_executor") and not data.get("fallback_behavior"):
            raise _error("shortcut records require fallback_executor or fallback_behavior")
    return data


def render_knowledge_records(raw: dict[str, object]) -> bytes:
    """Validate and render a complete, canonical version-1 knowledge ledger."""
    if not isinstance(raw, dict):
        raise _error("root must be a table")
    if not all(isinstance(key, str) for key in raw):
        raise _error("root keys must be strings")
    unknown = set(raw) - set(ROOT_FIELDS)
    if unknown:
        raise _error(f"root has unknown field {sorted(unknown)[0]!r}")
    if type(raw.get("version")) is not int or raw.get("version") != 1:
        raise _error("version must be integer 1")
    records = raw.get("records")
    if not isinstance(records, list):
        raise _error("records must be an array")
    extension_data = (
        _extensions(raw["extensions"], "root extensions")
        if "extensions" in raw
        else None
    )
    if extension_data == {}:
        extension_data = None
    rendered = [_record(record, index) for index, record in enumerate(records)]
    ids: set[str] = set()
    for index, record in enumerate(rendered):
        if record["id"] in ids:
            raise _error(f"records[{index}].id is duplicated")
        ids.add(record["id"])

    # Inline array-of-tables values keep the root extension in the root table
    # while allowing the required root ordering to remain version/records/extensions.
    root: dict[str, object] = {"version": 1, "records": rendered}
    if extension_data is not None:
        root["extensions"] = extension_data
    return render_toml(root, key_order=ROOT_FIELDS)
