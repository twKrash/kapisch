"""Descriptor-relative, non-following worktree observations."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from contextlib import suppress
from pathlib import Path

from ._repository_git import _identity, _root, capture_untracked
from .repository import (
    IndexEntry,
    RepositoryCaptureError,
    UntrackedEntry,
    WorktreeEntry,
    WorktreeFacts,
)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _parts(path):
    if (
        type(path) is not bytes
        or not path
        or path.startswith(b"/")
        or b"\0" in path
        or any(x in (b"", b".", b"..") for x in path.split(b"/"))
    ):
        raise RepositoryCaptureError("unsafe path")
    return path.split(b"/")


def _walk(rootfd, path):
    parts = _parts(path)
    fd = os.dup(rootfd)
    seen = []
    try:
        for index, part in enumerate(parts[:-1]):
            try:
                n = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=fd,
                )
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise RepositoryCaptureError("unsafe path traversal") from e
                check = os.dup(rootfd)
                try:
                    for prior, expected in zip(parts[:index], seen, strict=True):
                        current = os.open(
                            prior,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=check,
                        )
                        try:
                            if not _same(os.fstat(current), expected):
                                raise RepositoryCaptureError("parent replaced")
                        except BaseException:
                            os.close(current)
                            raise
                        os.close(check)
                        check = current
                    try:
                        probe = os.open(
                            part,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=check,
                        )
                        os.close(probe)
                    except OSError as missing:
                        if missing.errno == errno.ENOENT:
                            # Re-check the retained chain before classifying absence;
                            # a replacement race must fail closed, not look deleted.
                            verify = os.dup(rootfd)
                            try:
                                for prefix_index, prior in enumerate(
                                    parts[: index + 1]
                                ):
                                    try:
                                        current = os.open(
                                            prior,
                                            os.O_RDONLY
                                            | os.O_DIRECTORY
                                            | os.O_NOFOLLOW
                                            | os.O_CLOEXEC,
                                            dir_fd=verify,
                                        )
                                    except OSError as retry:
                                        if (
                                            prefix_index == index
                                            and retry.errno == errno.ENOENT
                                        ):
                                            os.close(fd)
                                            return None, None
                                        if (
                                            prefix_index < index
                                            and retry.errno == errno.ENOENT
                                        ):
                                            raise RepositoryCaptureError(
                                                "parent replaced"
                                            ) from retry
                                        raise RepositoryCaptureError(
                                            "unsafe path traversal"
                                        ) from retry
                                    try:
                                        if prefix_index < index and not _same(
                                            os.fstat(current), seen[prefix_index]
                                        ):
                                            raise RepositoryCaptureError(
                                                "parent replaced"
                                            )
                                    except BaseException:
                                        os.close(current)
                                        raise
                                    os.close(verify)
                                    verify = current
                                raise RepositoryCaptureError(
                                    "parent replaced"
                                ) from None
                            finally:
                                os.close(verify)
                        raise RepositoryCaptureError(
                            "unsafe path traversal"
                        ) from missing
                finally:
                    os.close(check)
                raise RepositoryCaptureError("parent replaced") from None
            try:
                seen.append(os.fstat(n))
                os.close(fd)
            except BaseException:
                os.close(n)
                raise
            fd = n
        return fd, parts[-1]
    except BaseException:
        with suppress(OSError):
            os.close(fd)
        raise


def _same(a, b):
    return (a.st_dev, a.st_ino, a.st_mode) == (b.st_dev, b.st_ino, b.st_mode)


def _verify_parent(rootfd, path, parent):
    fd = os.dup(rootfd)
    try:
        for part in _parts(path)[:-1]:
            nxt = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            try:
                os.close(fd)
            except BaseException:
                os.close(nxt)
                raise
            fd = nxt
        if not _same(os.fstat(fd), os.fstat(parent)):
            raise RepositoryCaptureError("parent replaced")
    except OSError as e:
        raise RepositoryCaptureError("parent replaced") from e
    finally:
        with suppress(OSError):
            os.close(fd)


def _read(rootfd, path):
    parent, name = _walk(rootfd, path)
    if parent is None:
        return None
    assert name is not None
    try:
        _verify_parent(rootfd, path, parent)
        try:
            st = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            _verify_parent(rootfd, path, parent)
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                _verify_parent(rootfd, path, parent)
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    _verify_parent(rootfd, path, parent)
                    return None
                raise RepositoryCaptureError("replacement race") from None
            raise RepositoryCaptureError("replacement race") from None
        if stat.S_ISLNK(st.st_mode):
            target = os.readlink(name, dir_fd=parent)
            target = os.fsencode(target) if isinstance(target, str) else target
            _verify_parent(rootfd, path, parent)
            if not _same(st, os.stat(name, dir_fd=parent, follow_symlinks=False)):
                raise RepositoryCaptureError("replacement race")
            return "symlink", target, st.st_mode
        if not stat.S_ISREG(st.st_mode):
            raise RepositoryCaptureError("special file rejected")
        try:
            fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent,
            )
        except OSError as e:
            raise RepositoryCaptureError("file open failed") from e
        try:
            got = os.fstat(fd)
            if not _same(got, st):
                raise RepositoryCaptureError("replacement race")
            chunks = []
            while True:
                b = os.read(fd, 1024 * 1024)
                if not b:
                    break
                chunks.append(b)
            end = os.fstat(fd)
            final = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _verify_parent(rootfd, path, parent)
            if (
                not _same(end, got)
                or not _same(final, got)
                or end.st_size != got.st_size
                or end.st_mtime_ns != got.st_mtime_ns
                or end.st_ctime_ns != got.st_ctime_ns
            ):
                raise RepositoryCaptureError("file mutated during read")
            return "file", b"".join(chunks), got.st_mode
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def _tracked(rootfd, e):
    got = _read(rootfd, e.path)
    if got is None:
        return WorktreeEntry(e.path, "deletion", "000000")
    kind, data, mode = got
    if kind == "symlink":
        return WorktreeEntry(e.path, "symlink", "120000", _digest(data))
    return WorktreeEntry(
        e.path, "file", "100755" if mode & stat.S_IXUSR else "100644", _digest(data)
    )


def capture_worktree(
    repo: Path,
    index: tuple[IndexEntry, ...],
    included_untracked: tuple[bytes, ...] = (),
    identity=None,
):
    if type(index) is not tuple or any(type(item) is not IndexEntry for item in index):
        raise RepositoryCaptureError("invalid index records")
    if type(included_untracked) is not tuple or any(
        type(path) is not bytes for path in included_untracked
    ):
        raise RepositoryCaptureError("invalid included paths")
    try:
        root, ident = _root(Path(repo), identity)
        rootfd = os.open(
            os.fspath(root), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
    except RepositoryCaptureError:
        raise
    except OSError as e:
        raise RepositoryCaptureError("worktree open failed") from e
    try:
        bound = os.fstat(rootfd)
        if (bound.st_dev, bound.st_ino) != ident:
            raise RepositoryCaptureError("worktree replaced")
        if _identity(root) != ident:
            raise RepositoryCaptureError("worktree replaced")
        inventory = capture_untracked(root, ident)
        inc = set(included_untracked)
        if not inc.issubset(set(inventory)):
            raise RepositoryCaptureError("included path is not untracked")
        tracked = tuple(
            sorted((_tracked(rootfd, e) for e in index), key=lambda x: x.path)
        )
        unknown = []
        for p in inventory:
            got = _read(rootfd, p)
            if got is None:
                raise RepositoryCaptureError("untracked disappeared")
            kind, data, _ = got
            if p in inc:
                if kind != "file":
                    raise RepositoryCaptureError("included untracked is not regular")
                unknown.append(UntrackedEntry(p, True, _digest(data)))
            else:
                unknown.append(UntrackedEntry(p, False))
        root_stat = os.fstat(rootfd)
        if (root_stat.st_dev, root_stat.st_ino) != ident or _identity(root) != ident:
            raise RepositoryCaptureError("worktree replaced")
        return WorktreeFacts(tracked, tuple(sorted(unknown, key=lambda x: x.path)))
    except RepositoryCaptureError:
        raise
    except (OSError, ValueError, TypeError) as e:
        raise RepositoryCaptureError("worktree observation failed") from e
    finally:
        os.close(rootfd)
