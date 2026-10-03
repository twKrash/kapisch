"""Canonical encoding for the closed repository fact union."""

from .bundle import canonical_json


def encode_git_path(path: bytes) -> str:
    if (
        type(path) is not bytes
        or not path
        or path.startswith(b"/")
        or b"\0" in path
        or any(x in (b"", b".", b"..") for x in path.split(b"/"))
    ):
        raise ValueError("invalid Git path")
    return path.hex()


def _entry(x):
    d = {"path_hex": x.path.hex()}
    if type(x).__name__ == "IndexEntry":
        d.update(stage=x.stage, object_id=x.object_id, mode=x.mode)
    elif type(x).__name__ == "WorktreeEntry":
        d.update(kind=x.kind, mode=x.mode)
        if x.sha256 is not None:
            d["sha256"] = x.sha256
    else:
        d["included"] = x.included
        if x.sha256 is not None:
            d["sha256"] = x.sha256
    return d


def encode_fact(fact) -> bytes:
    from .repository import (
        HeadIdentity,
        IndexEntry,
        RepositoryStateFingerprint,
        UntrackedEntry,
        WorktreeEntry,
        WorktreeFacts,
    )

    if type(fact) is HeadIdentity:
        return canonical_json(
            {"object_format": fact.object_format, "commit": fact.commit}
        )
    if type(fact) is IndexEntry:
        return canonical_json(_entry(fact))
    if type(fact) is WorktreeEntry:
        return canonical_json(_entry(fact))
    if type(fact) is UntrackedEntry:
        return canonical_json(_entry(fact))
    if type(fact) is WorktreeFacts:
        return canonical_json(
            {
                "worktree": [_entry(x) for x in fact.worktree],
                "untracked": [_entry(x) for x in fact.untracked],
            }
        )
    if type(fact) is RepositoryStateFingerprint:
        return canonical_json(
            {
                "object_format": fact.object_format,
                "head": fact.head,
                "index": [_entry(x) for x in fact.index],
                "worktree": [_entry(x) for x in fact.worktree],
                "untracked": [_entry(x) for x in fact.untracked],
            }
        )
    raise TypeError("unsupported repository fact")
