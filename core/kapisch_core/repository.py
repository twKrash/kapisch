"""Typed repository facts and the Stage 6.1 canonical encoding facade."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._repository_encoding import encode_fact, encode_git_path

_HEX = re.compile(r"^[0-9a-f]+$")


def _path(path: object) -> None:
    if (
        type(path) is not bytes
        or not path
        or path.startswith(b"/")
        or b"\0" in path
        or any(part in (b"", b".", b"..") for part in path.split(b"/"))
    ):
        raise ValueError("unsafe Git path")


def _digest(digest: object) -> None:
    if type(digest) is not str or len(digest) != 64 or not _HEX.fullmatch(digest):
        raise ValueError("invalid digest")


def _ordered(items: object, key) -> None:
    if type(items) is not tuple:
        raise ValueError("records must be tuples")
    if tuple(sorted(items, key=key)) != items:
        raise ValueError("records are not sorted")
    if len({key(item) for item in items}) != len(items):
        raise ValueError("duplicate records")


@dataclass(frozen=True)
class HeadIdentity:
    object_format: str
    commit: str

    def __post_init__(self) -> None:
        if self.object_format not in ("sha1", "sha256"):
            raise ValueError("invalid object format")
        width = 40 if self.object_format == "sha1" else 64
        if type(self.commit) is not str or len(self.commit) != width or not _HEX.fullmatch(self.commit):
            raise ValueError("invalid commit")


@dataclass(frozen=True)
class IndexEntry:
    path: bytes
    stage: int
    object_id: str
    mode: str

    def __post_init__(self) -> None:
        _path(self.path)
        if type(self.stage) is not int or self.stage not in range(4):
            raise ValueError("invalid stage")
        if type(self.object_id) is not str or len(self.object_id) not in (40, 64) or not _HEX.fullmatch(self.object_id):
            raise ValueError("invalid object id")
        if self.mode not in ("100644", "100755", "120000", "160000"):
            raise ValueError("invalid index mode")

    def __getitem__(self, key: str):
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, object]:
        return {"path_hex": self.path.hex(), "stage": self.stage, "object_id": self.object_id, "mode": self.mode}


@dataclass(frozen=True)
class WorktreeEntry:
    path: bytes
    kind: str
    mode: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        _path(self.path)
        if self.kind not in {"file", "symlink", "deletion"}:
            raise ValueError("invalid worktree kind")
        if self.mode not in ("100644", "100755", "120000", "000000"):
            raise ValueError("invalid worktree mode")
        expected = {"file": {"100644", "100755"}, "symlink": {"120000"}, "deletion": {"000000"}}
        if self.mode not in expected[self.kind]:
            raise ValueError("worktree kind/mode mismatch")
        if self.kind == "deletion":
            if self.sha256 is not None:
                raise ValueError("deletion cannot have a digest")
        else:
            _digest(self.sha256)

    def __getitem__(self, key: str):
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"path_hex": self.path.hex(), "kind": self.kind, "mode": self.mode}
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        return result


@dataclass(frozen=True)
class UntrackedEntry:
    path: bytes
    included: bool
    sha256: str | None = None

    def __post_init__(self) -> None:
        _path(self.path)
        if type(self.included) is not bool:
            raise ValueError("invalid inclusion flag")
        if self.included:
            _digest(self.sha256)
        elif self.sha256 is not None:
            raise ValueError("unincluded entry cannot have a digest")

    def __getitem__(self, key: str):
        return self.to_dict()[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"path_hex": self.path.hex(), "included": self.included}
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        return result


@dataclass(frozen=True)
class WorktreeFacts:
    worktree: tuple[WorktreeEntry, ...]
    untracked: tuple[UntrackedEntry, ...]

    def __post_init__(self) -> None:
        _ordered(self.worktree, lambda item: item.path)
        _ordered(self.untracked, lambda item: item.path)
        if any(type(item) is not WorktreeEntry for item in self.worktree):
            raise ValueError("invalid worktree records")
        if any(type(item) is not UntrackedEntry for item in self.untracked):
            raise ValueError("invalid untracked records")


@dataclass(frozen=True)
class RepositoryStateFingerprint:
    object_format: str
    head: str
    index: tuple[IndexEntry, ...]
    worktree: tuple[WorktreeEntry, ...]
    untracked: tuple[UntrackedEntry, ...]

    def __post_init__(self) -> None:
        HeadIdentity(self.object_format, self.head)
        if type(self.index) is not tuple or any(type(item) is not IndexEntry for item in self.index):
            raise ValueError("invalid index records")
        object_id_width = 40 if self.object_format == "sha1" else 64
        if any(len(item.object_id) != object_id_width for item in self.index):
            raise ValueError("index object ID does not match object format")
        _ordered(self.index, lambda item: (item.path, item.stage))
        _ordered(self.worktree, lambda item: item.path)
        _ordered(self.untracked, lambda item: item.path)
        if any(type(item) is not WorktreeEntry for item in self.worktree):
            raise ValueError("invalid worktree records")
        if any(type(item) is not UntrackedEntry for item in self.untracked):
            raise ValueError("invalid untracked records")

    def as_dict(self) -> dict[str, object]:
        return {
            "object_format": self.object_format,
            "head": self.head,
            "index": [item.to_dict() for item in self.index],
            "worktree": [item.to_dict() for item in self.worktree],
            "untracked": [item.to_dict() for item in self.untracked],
        }

    def canonical_bytes(self) -> bytes:
        return encode_fact(self)


RepositoryFact = HeadIdentity | IndexEntry | WorktreeEntry | UntrackedEntry | WorktreeFacts | RepositoryStateFingerprint


class RepositoryCaptureError(ValueError):
    """Stable error boundary used by later repository capture stages."""


__all__ = [
    "HeadIdentity",
    "IndexEntry",
    "RepositoryCaptureError",
    "RepositoryFact",
    "RepositoryStateFingerprint",
    "UntrackedEntry",
    "WorktreeEntry",
    "WorktreeFacts",
    "encode_fact",
    "encode_git_path",
]
