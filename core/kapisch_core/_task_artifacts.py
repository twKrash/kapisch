"""Portable artifact reading and primitive validation for task contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

_REF = re.compile(
    r"^(?:[A-Za-z0-9][A-Za-z0-9._-]*|\.kapisch)(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*$"
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """A durable task contract record is malformed or fails acceptance."""


def _read_bytes(root: Path, ref: Any, digest: Any) -> bytes:
    if (
        not isinstance(ref, str)
        or not _REF.fullmatch(ref)
        or any(part in {"", ".", ".."} for part in ref.split("/"))
    ):
        raise ContractError("malformed portable reference")
    path = (root / ref).resolve()
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
    if require_digest and digest is None:
        raise ContractError(f"missing artifact digest: {ref}")
    try:
        raw = (
            _read_bytes(root, ref, digest)
            if digest is not None
            else _read_bytes_without_digest(root, ref)
        )
        value = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON artifact: {ref}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"artifact must be an object: {ref}")
    return value


def _read_bytes_without_digest(root: Path, ref: Any) -> bytes:
    if (
        not isinstance(ref, str)
        or not _REF.fullmatch(ref)
        or any(part in {"", ".", ".."} for part in ref.split("/"))
    ):
        raise ContractError("malformed portable reference")
    path = (root / ref).resolve()
    if not path.is_relative_to(root):
        raise ContractError("portable reference escapes project root")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"unreadable artifact: {ref}") from exc


def _create_exclusive(root: Path, ref: str, record: dict[str, Any]) -> None:
    if not isinstance(ref, str) or not _REF.fullmatch(ref) or ".." in ref.split("/"):
        raise ContractError("malformed portable reference")
    parts = ref.split("/")
    parent = (root / Path(*parts[:-1])).resolve()
    if not parent.is_relative_to(root):
        raise ContractError("portable reference escapes project root")
    target = parent / parts[-1]
    payload = (
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
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
            output.flush()
            os.fsync(output.fileno())
    except OSError as exc:
        # Remove the partial claim so a reported failure never leaves behind a
        # claim that blocks every later dispatch of this Run. Cleanup failure
        # must not replace the contract error with a raw filesystem error.
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise ContractError("could not persist dispatch claim") from exc
    # The claim file is already durable; directory sync only hardens the entry.
    # Some filesystems reject fsync on directories, and reporting failure here
    # would strand a claim that already exists and cannot be reclaimed.
    try:
        directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
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
