"""Typed repository facts and the Stage 6.1 canonical encoding facade."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ._repository_encoding import encode_git_path, encode_projected_fact

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


def _ordered(items: object, key, item_type: type) -> None:
    if type(items) is not tuple or any(type(item) is not item_type for item in items):
        raise ValueError("invalid record collection")
    if tuple(sorted(items, key=key)) != items:
        raise ValueError("records are not sorted")
    if len({key(item) for item in items}) != len(items):
        raise ValueError("duplicate records")


@dataclass(frozen=True)
class HeadIdentity:
    object_format: str
    commit: str

    def __post_init__(self) -> None:
        if type(self.object_format) is not str or self.object_format not in (
            "sha1",
            "sha256",
        ):
            raise ValueError("invalid object format")
        width = 40 if self.object_format == "sha1" else 64
        if (
            type(self.commit) is not str
            or len(self.commit) != width
            or not _HEX.fullmatch(self.commit)
        ):
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
        if (
            type(self.object_id) is not str
            or len(self.object_id) not in (40, 64)
            or not _HEX.fullmatch(self.object_id)
        ):
            raise ValueError("invalid object id")
        if type(self.mode) is not str or self.mode not in (
            "100644",
            "100755",
            "120000",
            "160000",
        ):
            raise ValueError("invalid index mode")

    def __getitem__(self, key: str):
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, object]:
        return _project_entry(self)


@dataclass(frozen=True)
class WorktreeEntry:
    path: bytes
    kind: str
    mode: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        _path(self.path)
        if type(self.kind) is not str or self.kind not in {
            "file",
            "symlink",
            "deletion",
        }:
            raise ValueError("invalid worktree kind")
        if type(self.mode) is not str or self.mode not in (
            "100644",
            "100755",
            "120000",
            "000000",
        ):
            raise ValueError("invalid worktree mode")
        expected = {
            "file": {"100644", "100755"},
            "symlink": {"120000"},
            "deletion": {"000000"},
        }
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
        return _project_entry(self)


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
        return _project_entry(self)


@dataclass(frozen=True)
class WorktreeFacts:
    worktree: tuple[WorktreeEntry, ...]
    untracked: tuple[UntrackedEntry, ...]

    def __post_init__(self) -> None:
        _ordered(self.worktree, lambda item: item.path, WorktreeEntry)
        _ordered(self.untracked, lambda item: item.path, UntrackedEntry)


@dataclass(frozen=True)
class RepositoryStateFingerprint:
    object_format: str
    head: str
    index: tuple[IndexEntry, ...]
    worktree: tuple[WorktreeEntry, ...]
    untracked: tuple[UntrackedEntry, ...]

    def __post_init__(self) -> None:
        HeadIdentity(self.object_format, self.head)
        _ordered(self.index, lambda item: (item.path, item.stage), IndexEntry)
        object_id_width = 40 if self.object_format == "sha1" else 64
        if any(len(item.object_id) != object_id_width for item in self.index):
            raise ValueError("index object ID does not match object format")
        _ordered(self.worktree, lambda item: item.path, WorktreeEntry)
        _ordered(self.untracked, lambda item: item.path, UntrackedEntry)

    def as_dict(self) -> dict[str, object]:
        return _project_fact(self)

    def canonical_bytes(self) -> bytes:
        return encode_fact(self)


RepositoryFact = (
    HeadIdentity
    | IndexEntry
    | WorktreeEntry
    | UntrackedEntry
    | WorktreeFacts
    | RepositoryStateFingerprint
)


def _project_entry(entry: object) -> dict[str, object]:
    if type(entry) is IndexEntry:
        return {
            "path_hex": entry.path.hex(),
            "stage": entry.stage,
            "object_id": entry.object_id,
            "mode": entry.mode,
        }
    if type(entry) is WorktreeEntry:
        result: dict[str, object] = {
            "path_hex": entry.path.hex(),
            "kind": entry.kind,
            "mode": entry.mode,
        }
        if entry.sha256 is not None:
            result["sha256"] = entry.sha256
        return result
    if type(entry) is UntrackedEntry:
        result = {"path_hex": entry.path.hex(), "included": entry.included}
        if entry.sha256 is not None:
            result["sha256"] = entry.sha256
        return result
    raise TypeError("unsupported repository entry")


def _project_fact(fact: object) -> dict[str, object]:
    if type(fact) is HeadIdentity:
        return {"object_format": fact.object_format, "commit": fact.commit}
    if (
        type(fact) is IndexEntry
        or type(fact) is WorktreeEntry
        or type(fact) is UntrackedEntry
    ):
        return _project_entry(fact)
    if type(fact) is WorktreeFacts:
        return {
            "worktree": [_project_entry(item) for item in fact.worktree],
            "untracked": [_project_entry(item) for item in fact.untracked],
        }
    if type(fact) is RepositoryStateFingerprint:
        return {
            "object_format": fact.object_format,
            "head": fact.head,
            "index": [_project_entry(item) for item in fact.index],
            "worktree": [_project_entry(item) for item in fact.worktree],
            "untracked": [_project_entry(item) for item in fact.untracked],
        }
    raise TypeError("unsupported repository fact")


def encode_fact(fact: RepositoryFact) -> bytes:
    return encode_projected_fact(_project_fact(fact))


class RepositoryCaptureError(ValueError):
    """Stable error boundary used by repository capture stages."""


def capture_head(repo: Path) -> HeadIdentity:
    from ._repository_git import capture_head as _capture_head

    return _capture_head(repo)


def capture_index(repo: Path) -> tuple[IndexEntry, ...]:
    from ._repository_git import capture_index as _capture_index

    return _capture_index(repo)


def capture_worktree(
    repo: Path,
    index: tuple[IndexEntry, ...],
    included_untracked: tuple[bytes, ...] = (),
) -> WorktreeFacts:
    from ._repository_worktree import capture_worktree as _capture_worktree

    return _capture_worktree(repo, index, included_untracked)


def capture_repository_state(
    repo: Path,
    included_untracked: tuple[bytes, ...] = (),
) -> RepositoryStateFingerprint:
    from ._repository_fingerprint import capture_repository_state as _capture

    return _capture(repo, included_untracked)


__all__ = [
    "HeadIdentity",
    "IndexEntry",
    "RepositoryCaptureError",
    "RepositoryFact",
    "RepositoryStateFingerprint",
    "UntrackedEntry",
    "WorktreeEntry",
    "WorktreeFacts",
    "capture_head",
    "capture_index",
    "capture_repository_state",
    "capture_worktree",
    "encode_fact",
    "encode_git_path",
]
