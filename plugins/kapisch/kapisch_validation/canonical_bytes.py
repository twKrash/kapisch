"""Pure byte primitives for KAPISCH-owned generated artifacts."""

from __future__ import annotations

import hashlib
import json
import math


def _validate_json_value(value: object) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise ValueError("JSON strings cannot contain unpaired Unicode surrogates")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            if any(0xD800 <= ord(char) <= 0xDFFF for char in key):
                raise ValueError("JSON object keys cannot contain unpaired Unicode surrogates")
            _validate_json_value(item)
        return
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


def canonical_text_bytes(text: str) -> bytes:
    """Return strict UTF-8 text with LF newlines and exactly one final LF."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if text.startswith("\ufeff"):
        raise ValueError("UTF-8 BOM is not permitted")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValueError("text cannot contain unpaired Unicode surrogates")
    return (text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n").encode("utf-8")


def normalize_utf8_text(data: bytes) -> bytes:
    """Strictly decode UTF-8 data and return canonical generated text bytes."""
    if not isinstance(data, bytes):
        raise ValueError("data must be bytes")
    try:
        return canonical_text_bytes(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("data is not valid UTF-8") from exc


def canonical_json_bytes(value: object) -> bytes:
    """Encode a JSON-compatible value with deterministic UTF-8 JSON spelling."""
    _validate_json_value(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_json_line(value: object) -> bytes:
    """Return canonical JSON followed by one LF."""
    return canonical_json_bytes(value) + b"\n"


def sha256_hex(data: bytes) -> str:
    """Return the lowercase SHA-256 digest of exactly *data*."""
    if not isinstance(data, bytes):
        raise ValueError("data must be bytes")
    return hashlib.sha256(data).hexdigest()
