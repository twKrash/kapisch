from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .storage import _close, _open_dir, _open_tree


def _acquire_lock(fd: int) -> None:
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_EX)


def _release_lock(fd: int) -> None:
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def _locked(repo: Path, run_id: str | None = None) -> Iterator[None]:
    # Always lock repository namespace before individual run namespace.
    lock_dir, fds = _open_tree(repo, "locks", create=True)
    locks: list[int] = []
    try:
        for name in ("repository.lock", f"run-{run_id}.lock" if run_id else None):
            if name is None:
                continue
            fd = os.open(name, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=lock_dir)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise ValueError("authority lock is not a regular file")
            try:
                _acquire_lock(fd)
            except BaseException:
                os.close(fd)
                raise
            locks.append(fd)
        yield
    finally:
        for fd in reversed(locks):
            _release_lock(fd)
            os.close(fd)
        _close(fds)