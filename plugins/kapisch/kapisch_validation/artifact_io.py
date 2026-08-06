from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import stat


class ArtifactFailureKind(str, Enum):
    MISSING = "missing"
    UNREADABLE = "unreadable"
    NOT_REGULAR = "not_regular"
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
        flags = (
            os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        )
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None, ArtifactFailure(ArtifactFailureKind.MISSING)
    except OSError:
        return None, ArtifactFailure(ArtifactFailureKind.UNREADABLE)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None, ArtifactFailure(ArtifactFailureKind.NOT_REGULAR)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        data = b"".join(chunks)
    except OSError:
        return None, ArtifactFailure(ArtifactFailureKind.UNREADABLE)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
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
    except (ValueError, RecursionError):
        return None, ArtifactFailure(
            ArtifactFailureKind.MALFORMED_TOML, "TOML input is malformed"
        )
