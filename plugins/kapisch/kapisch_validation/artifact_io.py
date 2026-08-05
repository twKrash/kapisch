from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ArtifactFailureKind(str, Enum):
    MISSING = "missing"
    UNREADABLE = "unreadable"
    INVALID_UTF8 = "invalid_utf8"
    MALFORMED_TOML = "malformed_toml"


@dataclass(frozen=True)
class ArtifactFailure:
    kind: ArtifactFailureKind
    detail: str = ""


@dataclass(frozen=True)
class Utf8Artifact:
    data: bytes
    text: str


def read_utf8_artifact(
    path: Path,
) -> tuple[Utf8Artifact | None, ArtifactFailure | None]:
    """Read a user-controlled artifact without leaking expected I/O failures."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, ArtifactFailure(ArtifactFailureKind.MISSING)
    except OSError:
        return None, ArtifactFailure(ArtifactFailureKind.UNREADABLE)
    try:
        return Utf8Artifact(data, data.decode("utf-8")), None
    except UnicodeDecodeError:
        return None, ArtifactFailure(ArtifactFailureKind.INVALID_UTF8)


def load_toml_artifact(
    path: Path,
) -> tuple[dict[str, object] | None, ArtifactFailure | None]:
    artifact, failure = read_utf8_artifact(path)
    if failure is not None:
        return None, failure
    assert artifact is not None
    try:
        return tomllib.loads(artifact.text), None
    except tomllib.TOMLDecodeError as exc:
        return None, ArtifactFailure(ArtifactFailureKind.MALFORMED_TOML, str(exc))
