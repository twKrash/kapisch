"""Immutable Stage 6.5 review evidence records.

This module only owns the frozen in-memory format.  Publication, validation,
and writer enforcement remain outside this bounded unit.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ._repository_encoding import encode_git_path
from .bundle import canonical_json

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: Any, fields: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} has missing or unknown fields")
    try:
        snapshot = tuple(value.items())
    except (AttributeError, TypeError, ValueError, RuntimeError) as error:
        raise ValueError(f"{name} has missing or unknown fields") from error
    keys = tuple(key for key, _ in snapshot)
    if any(type(key) is not str for key in keys):
        raise ValueError(f"{name} keys must be strings")
    if len(keys) != len(set(keys)):
        raise ValueError(f"{name} has duplicate keys")
    for key in keys:
        _encode(key, f"{name} key")
    if set(keys) != fields:
        raise ValueError(f"{name} has missing or unknown fields")
    return MappingProxyType({key: _freeze(item) for key, item in snapshot})


def _encode(value: str, name: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must be UTF-8 encodable") from error


def _freeze(value: Any, active: set[int] | None = None) -> Any:
    active = set() if active is None else active
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ValueError("cyclic value")
        active.add(identity)
        try:
            try:
                snapshot = tuple(value.items())
            except (AttributeError, TypeError, ValueError, RuntimeError) as error:
                raise ValueError("mapping is not canonical JSON") from error
            keys = tuple(key for key, _ in snapshot)
            if any(type(key) is not str for key in keys):
                raise ValueError("mapping keys must be strings")
            if len(keys) != len(set(keys)):
                raise ValueError("mapping keys must be unique")
            for key in keys:
                _encode(key, "mapping key")
            return MappingProxyType({key: _freeze(item, active) for key, item in snapshot})
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError("cyclic value")
        active.add(identity)
        try:
            return tuple(_freeze(item, active) for item in value)
        finally:
            active.remove(identity)
    if value is None or type(value) in (str, bool, int):
        if type(value) is str:
            _encode(value, "string")
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("value is not canonical JSON")


def _locator(value: Any, name: str = "locator") -> None:
    if type(value) not in (ImmutableArtifactLocator, EvidenceLocator):
        raise ValueError(f"{name} must be an exact supported artifact locator")


def _thaw(value: Any) -> Any:
    if isinstance(value, ImmutableArtifactLocator):
        _locator(value)
        return {"path": value.path, "sha256": value.sha256}
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _path(value: Any, name: str = "path") -> str:
    _text(value, name)
    if (value.startswith(("/", "\\\\")) or "\\" in value or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)):
        raise ValueError(f"{name} must be a repository-relative path")
    return value


def _git_path_encoding(value: Any) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]+", value):
        raise ValueError("included_untracked path must be canonical Git path encoding")
    try:
        decoded = bytes.fromhex(value)
        canonical = encode_git_path(decoded)
    except ValueError as error:
        raise ValueError("included_untracked path must be canonical Git path encoding") from error
    if canonical != value:
        raise ValueError("included_untracked path must be canonical Git path encoding")
    return value


def _digest(value: Any, name: str) -> str:
    if type(value) is not str or not _DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be lowercase SHA-256")
    _encode(value, name)
    return value


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a nonempty string")
    _encode(value, name)
    return value


def _closed(value: Any, allowed: set[str], name: str) -> str:
    _text(value, name)
    if value not in allowed:
        raise ValueError(f"{name} is invalid")
    return value


@dataclass(frozen=True)
class ImmutableArtifactLocator:
    path: str
    sha256: str

    def __post_init__(self) -> None:
        _path(self.path)
        _digest(self.sha256, "sha256")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ImmutableArtifactLocator":
        if not isinstance(value, Mapping):
            raise ValueError("ImmutableArtifactLocator has missing or unknown fields")
        try:
            snapshot = tuple(value.items())
        except (AttributeError, TypeError, ValueError, RuntimeError) as error:
            raise ValueError("ImmutableArtifactLocator has missing or unknown fields") from error
        keys = tuple(key for key, _ in snapshot)
        if any(type(key) is not str for key in keys):
            raise ValueError("ImmutableArtifactLocator keys must be strings")
        if len(keys) != len(set(keys)):
            raise ValueError("ImmutableArtifactLocator has duplicate keys")
        for key in keys:
            _encode(key, "ImmutableArtifactLocator key")
        if set(keys) != {"path", "sha256"}:
            raise ValueError("ImmutableArtifactLocator has missing or unknown fields")
        fields = dict(snapshot)
        return cls(fields["path"], fields["sha256"])

    def to_dict(self) -> dict[str, Any]:
        _locator(self)
        return {"path": self.path, "sha256": self.sha256}

    def canonical_bytes(self) -> bytes:
        _locator(self)
        return canonical_json({"path": self.path, "sha256": self.sha256})


@dataclass(frozen=True)
class EvidenceLocator(ImmutableArtifactLocator):
    """Locator for retained evidence bytes, not an authority decision."""


class _Record:
    def to_dict(self) -> dict[str, Any]:
        return {field: _thaw(getattr(self, field)) for field in self.__dataclass_fields__}

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    @classmethod
    def _load(cls, value: Mapping[str, Any], fields: set[str]) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{cls.__name__} has missing or unknown fields")
        try:
            snapshot = tuple(value.items())
        except (AttributeError, TypeError, ValueError, RuntimeError) as error:
            raise ValueError(f"{cls.__name__} has missing or unknown fields") from error
        keys = tuple(key for key, _ in snapshot)
        if any(type(key) is not str for key in keys):
            raise ValueError(f"{cls.__name__} keys must be strings")
        if len(keys) != len(set(keys)):
            raise ValueError(f"{cls.__name__} has duplicate keys")
        for key in keys:
            _encode(key, f"{cls.__name__} key")
        if set(keys) != fields:
            raise ValueError(f"{cls.__name__} has missing or unknown fields")
        return dict(snapshot)


@dataclass(frozen=True)
class ReviewInvocation(_Record):
    retained_bundle: ImmutableArtifactLocator
    request: ImmutableArtifactLocator
    attempt: Mapping[str, Any]
    operation: Mapping[str, Any]
    scope: ImmutableArtifactLocator
    base: str
    head: str
    purpose: str
    included_untracked: tuple[str, ...]
    pre_dispatch_fingerprint: ImmutableArtifactLocator

    def __post_init__(self) -> None:
        for name in ("retained_bundle", "request", "scope", "pre_dispatch_fingerprint"):
            _locator(getattr(self, name), name)
        for name in ("base", "head"):
            _text(getattr(self, name), name)
        _closed(self.purpose, {"iteration", "final"}, "purpose")
        object.__setattr__(self, "attempt", _mapping(self.attempt, {"run_id", "stage_id"}, "attempt"))
        object.__setattr__(self, "operation", _mapping(self.operation, {"run_id", "operation_id"}, "operation"))
        for name, value in (("attempt", self.attempt), ("operation", self.operation)):
            for key in value:
                _text(value[key], f"{name}.{key}")
        if self.operation["run_id"] != self.attempt["run_id"]:
            raise ValueError("operation and attempt run_id must match")
        if type(self.included_untracked) not in (list, tuple):
            raise ValueError("included_untracked must be a sequence")
        paths = tuple(_git_path_encoding(path) for path in self.included_untracked)
        if len(paths) != len(set(paths)):
            raise ValueError("included_untracked must not contain duplicates")
        object.__setattr__(self, "included_untracked", paths)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReviewInvocation":
        raw = cls._load(value, set(cls.__dataclass_fields__))
        for field in ("retained_bundle", "request", "scope", "pre_dispatch_fingerprint"):
            raw[field] = ImmutableArtifactLocator.from_dict(raw[field])
        return cls(**raw)


@dataclass(frozen=True)
class ReviewerReturn(_Record):
    invocation: ImmutableArtifactLocator
    operation: Mapping[str, Any]
    request: ImmutableArtifactLocator
    target: Mapping[str, Any]
    fingerprint: ImmutableArtifactLocator
    report: ImmutableArtifactLocator
    report_digest: str
    decision: str

    def __post_init__(self) -> None:
        for name in ("invocation", "request", "fingerprint", "report"):
            _locator(getattr(self, name), name)
        _digest(self.report_digest, "report_digest")
        _closed(self.decision, {"clear", "findings", "inconclusive"}, "decision")
        object.__setattr__(self, "operation", _mapping(self.operation, {"run_id", "operation_id"}, "operation"))
        object.__setattr__(self, "target", _mapping(self.target, {"run_id", "stage_id", "operation_id", "base", "head"}, "target"))
        for name, value in (("operation", self.operation), ("target", self.target)):
            for key in value:
                _text(value[key], f"{name}.{key}")
        if any(self.operation[key] != self.target[key] for key in ("run_id", "operation_id")):
            raise ValueError("operation and target identity must match")
        if self.report_digest != self.report.sha256:
            raise ValueError("report_digest must match report.sha256")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReviewerReturn":
        raw = cls._load(value, set(cls.__dataclass_fields__))
        for field in ("invocation", "request", "fingerprint", "report"):
            raw[field] = ImmutableArtifactLocator.from_dict(raw[field])
        return cls(**raw)


@dataclass(frozen=True)
class HostProvenanceAttestation(_Record):
    reviewer_return: ImmutableArtifactLocator
    reviewer_return_digest: str
    execution_identity: Any
    execution_context: Any
    dispatch_facts: Any

    def __post_init__(self) -> None:
        _locator(self.reviewer_return, "reviewer_return")
        _digest(self.reviewer_return_digest, "reviewer_return_digest")
        if self.reviewer_return_digest != self.reviewer_return.sha256:
            raise ValueError("reviewer_return_digest must match reviewer_return.sha256")
        for name in ("execution_identity", "execution_context", "dispatch_facts"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HostProvenanceAttestation":
        raw = cls._load(value, set(cls.__dataclass_fields__))
        raw["reviewer_return"] = ImmutableArtifactLocator.from_dict(raw["reviewer_return"])
        return cls(**raw)


@dataclass(frozen=True)
class ReviewResult(_Record):
    invocation: ImmutableArtifactLocator
    request: ImmutableArtifactLocator
    target: Mapping[str, Any]
    scope: ImmutableArtifactLocator
    fingerprint: ImmutableArtifactLocator
    reviewer_return: ImmutableArtifactLocator
    post_result: ImmutableArtifactLocator
    provenance: ImmutableArtifactLocator

    def __post_init__(self) -> None:
        for name in ("invocation", "request", "scope", "fingerprint", "reviewer_return", "post_result", "provenance"):
            _locator(getattr(self, name), name)
        object.__setattr__(self, "target", _mapping(self.target, {"run_id", "stage_id", "operation_id", "base", "head"}, "target"))
        for key in self.target:
            _text(self.target[key], f"target.{key}")
        if self.fingerprint.sha256 != self.post_result.sha256:
            raise ValueError("fingerprint.sha256 must match post_result.sha256")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReviewResult":
        raw = cls._load(value, set(cls.__dataclass_fields__))
        for field in ("invocation", "request", "scope", "fingerprint", "reviewer_return", "post_result", "provenance"):
            raw[field] = ImmutableArtifactLocator.from_dict(raw[field])
        return cls(**raw)


__all__ = [
    "EvidenceLocator", "HostProvenanceAttestation", "ImmutableArtifactLocator",
    "ReviewInvocation", "ReviewResult", "ReviewerReturn",
]
