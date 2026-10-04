"""Two-pass repository composition."""

from pathlib import Path

from ._repository_git import _root, capture_head, capture_index
from ._repository_worktree import capture_worktree
from .repository import RepositoryCaptureError, RepositoryStateFingerprint


def _capture_once(repo, included, identity):
    head = capture_head(repo, identity)
    index = capture_index(repo, identity)
    if any(entry.stage != 0 for entry in index):
        raise RepositoryCaptureError("nonzero index stage")
    wt = capture_worktree(Path(repo), index, included, identity)
    final_index = capture_index(repo, identity)
    final_head = capture_head(repo, identity)
    if final_index != index or final_head != head:
        raise RepositoryCaptureError("repository changed during inspection")
    verified_wt = capture_worktree(Path(repo), index, included, identity)
    verified_index = capture_index(repo, identity)
    verified_head = capture_head(repo, identity)
    if (
        verified_wt != wt
        or verified_index != final_index
        or verified_head != final_head
    ):
        raise RepositoryCaptureError("repository changed during inspection")
    return RepositoryStateFingerprint(
        head.object_format,
        head.commit,
        index,
        verified_wt.worktree,
        verified_wt.untracked,
    )


def capture_repository_state(repo: Path, included_untracked: tuple[bytes, ...] = ()):
    try:
        _, identity = _root(Path(repo))
        first = _capture_once(repo, included_untracked, identity)
        _, identity2 = _root(Path(repo), identity)
        second = _capture_once(repo, included_untracked, identity2)
        if first.canonical_bytes() != second.canonical_bytes():
            raise RepositoryCaptureError("repository changed during inspection")
        return second
    except RepositoryCaptureError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as e:
        raise RepositoryCaptureError("repository capture failed") from e
