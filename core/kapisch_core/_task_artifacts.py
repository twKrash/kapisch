"""Portable artifact reading and primitive validation for task contracts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

_REF = re.compile(
    r"^(?:[A-Za-z0-9][A-Za-z0-9._-]*|\.kapisch)(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*$"
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _resolve(path: Path, label: str = "artifact") -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContractError(f"cannot resolve {label} path") from exc


class ContractError(ValueError):
    """A durable task contract record is malformed or fails acceptance."""


def _read_bytes(root: Path, ref: Any, digest: Any) -> bytes:
    if (
        not isinstance(ref, str)
        or not _REF.fullmatch(ref)
        or any(part in {"", ".", ".."} for part in ref.split("/"))
    ):
        raise ContractError("malformed portable reference")
    path = _resolve(root / ref)
    if not path.is_relative_to(root):
        raise ContractError("portable reference escapes project root")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"unreadable artifact: {ref}") from exc
    if (
        not isinstance(digest, str)
        or not _DIGEST.fullmatch(digest)
        or hashlib.sha256(raw).hexdigest() != digest
    ):
        raise ContractError(f"artifact digest mismatch: {ref}")
    return raw


def _finite_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ContractError("invalid JSON number") from exc
    if not math.isfinite(number):
        raise ContractError("non-finite JSON number")
    return number


def _reject_json_constant(value: str) -> None:
    raise ContractError(f"invalid JSON constant: {value}")


def _serialize_json(record: dict[str, Any], error_message: str) -> bytes:
    try:
        serialized = json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise ContractError(error_message) from exc
    return (serialized + "\n").encode("utf-8")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise ContractError(f"duplicate JSON object key: {key}")
        record[key] = value
    return record


def _load(
    root: Path, ref: Any, digest: Any = None, *, require_digest: bool = True
) -> dict[str, Any]:
    value, _ = _load_with_digest(root, ref, digest, require_digest=require_digest)
    return value


def _load_with_digest(
    root: Path, ref: Any, digest: Any = None, *, require_digest: bool = True
) -> tuple[dict[str, Any], str]:
    if require_digest and digest is None:
        raise ContractError(f"missing artifact digest: {ref}")
    try:
        raw = (
            _read_bytes(root, ref, digest)
            if digest is not None
            else _read_bytes_without_digest(root, ref)
        )
        value = json.loads(
            raw,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
            parse_float=_finite_float,
        )
    except ContractError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ) as exc:
        raise ContractError(f"invalid JSON artifact: {ref}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"artifact must be an object: {ref}")
    return value, hashlib.sha256(raw).hexdigest()


def _read_bytes_without_digest(root: Path, ref: Any) -> bytes:
    if (
        not isinstance(ref, str)
        or not _REF.fullmatch(ref)
        or any(part in {"", ".", ".."} for part in ref.split("/"))
    ):
        raise ContractError("malformed portable reference")
    path = _resolve(root / ref)
    if not path.is_relative_to(root):
        raise ContractError("portable reference escapes project root")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"unreadable artifact: {ref}") from exc


def _artifact_target(root: Path, ref: str) -> tuple[Path, Path]:
    if not isinstance(ref, str) or not _REF.fullmatch(ref) or ".." in ref.split("/"):
        raise ContractError("malformed portable reference")
    parts = ref.split("/")
    parent = _resolve(root / Path(*parts[:-1]), "artifact parent")
    if not parent.is_relative_to(root):
        raise ContractError("portable reference escapes project root")
    return parent, parent / parts[-1]


def _create_exclusive(root: Path, ref: str, record: dict[str, Any]) -> None:
    parent, target = _artifact_target(root, ref)
    payload = _serialize_json(record, "could not persist dispatch claim")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise ContractError("dispatch claim already exists") from exc
    except OSError as exc:
        raise ContractError("could not persist dispatch claim") from exc
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
    except OSError as exc:
        # Remove a partial claim; cleanup failure must not replace the contract
        # error with a raw filesystem error.
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise ContractError("could not persist dispatch claim") from exc


def _replace_json_atomically(root: Path, ref: str, record: dict[str, Any]) -> None:
    parent, target = _artifact_target(root, ref)
    try:
        mode = target.lstat().st_mode
    except OSError as exc:
        raise ContractError(
            "mutable artifact is missing or cannot be inspected"
        ) from exc
    if not stat.S_ISREG(mode):
        raise ContractError("mutable artifact is missing or is a symlink")

    payload = _serialize_json(record, "could not persist dispatch boundary")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=parent, prefix=f".{target.name}.", delete=False
        ) as output:
            temporary_path = Path(output.name)
            output.write(payload)
        os.replace(temporary_path, target)
    except OSError as exc:
        raise ContractError("could not persist dispatch boundary") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _required_text(record: dict[str, Any], key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"invalid {label}")
    return value


def _required_id(record: dict[str, Any], key: str, label: str) -> str:
    value = _required_text(record, key, label)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise ContractError(f"invalid {label}")
    return value
