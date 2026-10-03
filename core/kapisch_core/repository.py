"""Strict, schema-preserving repository observations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._repository_encoding import encode_git_path, encode_projected_fact

_HEX = re.compile(r"^[0-9a-f]+$")


def _path(p):
    if (
        type(p) is not bytes
        or not p
        or p.startswith(b"/")
        or b"\0" in p
        or any(x in (b"", b".", b"..") for x in p.split(b"/"))
    ):
        raise ValueError("unsafe Git path")


def _digest(d):
    if type(d) is not str or len(d) != 64 or not _HEX.fullmatch(d):
        raise ValueError("invalid digest")


def _kind(k):
    if type(k) is not str or k not in {"file", "symlink", "deletion"}:
        raise ValueError("invalid kind")


def _ordered(items, key):
    if (
        type(items) is not tuple
        or tuple(sorted(items, key=key)) != items
        or len({key(x) for x in items}) != len(items)
    ):
        raise ValueError("invalid ordering")


@dataclass(frozen=True)
class HeadIdentity:
    object_format: str
    commit: str

    def __post_init__(self):
        if type(self.object_format) is not str or self.object_format not in (
            "sha1",
            "sha256",
        ):
            raise ValueError("invalid format")
        if (
            type(self.commit) is not str
            or len(self.commit) != (40 if self.object_format == "sha1" else 64)
            or not _HEX.fullmatch(self.commit)
        ):
            raise ValueError("invalid commit")


@dataclass(frozen=True)
class IndexEntry:
    path: bytes
    stage: int
    object_id: str
    mode: str

    def __post_init__(self):
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
            raise ValueError("invalid mode")

    def __getitem__(self, key):
        return self.to_dict()[key]

    def to_dict(self):
        return {
            "path_hex": self.path.hex(),
            "stage": self.stage,
            "object_id": self.object_id,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class WorktreeEntry:
    path: bytes
    kind: str
    mode: str
    sha256: str | None = None

    def __post_init__(self):
        _path(self.path)
        _kind(self.kind)
        if type(self.mode) is not str or self.mode not in (
            "100644",
            "100755",
            "120000",
            "000000",
        ):
            raise ValueError("invalid mode")
        if (
            (self.kind == "deletion" and self.mode != "000000")
            or (self.kind == "symlink" and self.mode != "120000")
            or (self.kind == "file" and self.mode not in ("100644", "100755"))
        ):
            raise ValueError("mode mismatch")
        if self.kind == "deletion":
            if self.sha256 is not None:
                raise ValueError("deletion digest")
        else:
            _digest(self.sha256)

    def __getitem__(self, key):
        return self.to_dict()[key]

    def to_dict(self):
        d = {"path_hex": self.path.hex(), "kind": self.kind, "mode": self.mode}
        if self.sha256 is not None:
            d["sha256"] = self.sha256
        return d


@dataclass(frozen=True)
class UntrackedEntry:
    path: bytes
    included: bool
    sha256: str | None = None

    def __post_init__(self):
        _path(self.path)
        if type(self.included) is not bool:
            raise ValueError("invalid included")
        if self.included:
            _digest(self.sha256)
        elif self.sha256 is not None:
            raise ValueError("excluded digest")

    def __getitem__(self, key):
        return self.to_dict()[key]

    def __contains__(self, key):
        return key in self.to_dict()

    def to_dict(self):
        d = {"path_hex": self.path.hex(), "included": self.included}
        if self.sha256 is not None:
            d["sha256"] = self.sha256
        return d


@dataclass(frozen=True)
class WorktreeFacts:
    worktree: tuple[WorktreeEntry, ...]
    untracked: tuple[UntrackedEntry, ...]

    def __post_init__(self):
        _ordered(self.worktree, lambda x: x.path)
        _ordered(self.untracked, lambda x: x.path)
        if any(type(x) is not WorktreeEntry for x in self.worktree) or any(
            type(x) is not UntrackedEntry for x in self.untracked
        ):
            raise ValueError("invalid records")


@dataclass(frozen=True)
class RepositoryStateFingerprint:
    object_format: str
    head: str
    index: tuple[IndexEntry, ...]
    worktree: tuple[WorktreeEntry, ...]
    untracked: tuple[UntrackedEntry, ...]

    def __post_init__(self):
        HeadIdentity(self.object_format, self.head)
        if type(self.index) is not tuple or any(
            type(x) is not IndexEntry for x in self.index
        ):
            raise ValueError("invalid index")
        _ordered(self.index, lambda x: (x.path, x.stage))
        _ordered(self.worktree, lambda x: x.path)
        _ordered(self.untracked, lambda x: x.path)
        if any(type(x) is not WorktreeEntry for x in self.worktree) or any(
            type(x) is not UntrackedEntry for x in self.untracked
        ):
            raise ValueError("invalid records")

    def as_dict(self):
        return {
            "object_format": self.object_format,
            "head": self.head,
            "index": [x.to_dict() for x in self.index],
            "worktree": [x.to_dict() for x in self.worktree],
            "untracked": [x.to_dict() for x in self.untracked],
        }

    def canonical_bytes(self):
        return encode_fact(self)


RepositoryFact = (
    HeadIdentity
    | IndexEntry
    | WorktreeEntry
    | UntrackedEntry
    | WorktreeFacts
    | RepositoryStateFingerprint
)


def encode_fact(fact):
    if type(fact) is HeadIdentity:
        return encode_projected_fact({"object_format": fact.object_format, "commit": fact.commit})
    if type(fact) in (IndexEntry, WorktreeEntry, UntrackedEntry):
        return encode_projected_fact(fact.to_dict())
    if type(fact) is WorktreeFacts:
        return encode_projected_fact({"worktree": [item.to_dict() for item in fact.worktree], "untracked": [item.to_dict() for item in fact.untracked]})
    if type(fact) is RepositoryStateFingerprint:
        return encode_projected_fact(fact.as_dict())
    raise TypeError("unsupported repository fact")


class RepositoryCaptureError(ValueError):
    pass


def capture_head(*a, **k):
    from ._repository_git import capture_head as f

    return f(*a, **k)


def capture_index(*a, **k):
    from ._repository_git import capture_index as f

    return f(*a, **k)


def capture_worktree(*a, **k):
    from ._repository_worktree import capture_worktree as f

    return f(*a, **k)


def capture_repository_state(*a, **k):
    from ._repository_fingerprint import capture_repository_state as f

    return f(*a, **k)


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
