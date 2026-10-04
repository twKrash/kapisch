"""Descriptor-relative, non-following worktree observations."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from ._repository_git import _identity, _root, capture_untracked
from .repository import (
    IndexEntry,
    RepositoryCaptureError,
    UntrackedEntry,
    WorktreeEntry,
    WorktreeFacts,
)


@dataclass(frozen=True)
class _Parent:
    fd: int
    name: bytes
    parts: tuple[bytes, ...]
    seen: tuple[os.stat_result, ...]


@dataclass(frozen=True)
class _LeafObservation:
    kind: Literal["missing", "directory", "symlink", "regular", "special"]
    data: bytes | str | None = None
    mode: int | None = None


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


def _same(a, b):
    return (a.st_dev, a.st_ino, a.st_mode) == (b.st_dev, b.st_ino, b.st_mode)


def _same_file_state(a, b):
    return (
        _same(a, b)
        and a.st_size == b.st_size
        and a.st_mtime_ns == b.st_mtime_ns
        and a.st_ctime_ns == b.st_ctime_ns
    )


def _verify_non_directory(parentfd, name):
    try:
        observed = os.stat(name, dir_fd=parentfd, follow_symlinks=False)
        current = os.stat(name, dir_fd=parentfd, follow_symlinks=False)
    except OSError as e:
        raise RepositoryCaptureError("parent replaced") from e
    if stat.S_IFMT(observed.st_mode) not in (stat.S_IFREG, stat.S_IFLNK):
        raise RepositoryCaptureError("unsafe path traversal")
    if not _same(observed, current):
        raise RepositoryCaptureError("parent replaced")


def _open_chain_once(rootfd, parts, seen):
    chain = []
    try:
        parentfd = rootfd
        for index, part in enumerate(parts):
            current = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parentfd,
            )
            try:
                if not _same(os.fstat(current), seen[index]):
                    raise RepositoryCaptureError("parent replaced")
            except BaseException:
                os.close(current)
                raise
            chain.append(current)
            parentfd = current
        for index in range(len(parts) - 1, -1, -1):
            part = parts[index]
            parentfd = rootfd if index == 0 else chain[index - 1]
            try:
                attached = os.stat(part, dir_fd=parentfd, follow_symlinks=False)
            except OSError as e:
                raise RepositoryCaptureError("parent replaced") from e
            if not _same(attached, seen[index]):
                raise RepositoryCaptureError("parent replaced")
        for index in range(len(chain) - 1, -1, -1):
            current = chain[index]
            try:
                observed = os.fstat(current)
            except OSError as e:
                raise RepositoryCaptureError("parent replaced") from e
            if not _same_file_state(observed, seen[index]):
                raise RepositoryCaptureError("parent replaced")
        if not chain:
            return os.dup(rootfd)
        terminal = chain[-1]
        for fd in chain[:-1]:
            os.close(fd)
        return terminal
    except OSError as e:
        for fd in chain:
            with suppress(OSError):
                os.close(fd)
        raise RepositoryCaptureError("parent replaced") from e
    except BaseException:
        for fd in chain:
            with suppress(OSError):
                os.close(fd)
        raise


def _open_verified_chain(rootfd, parts, seen):
    if len(parts) != len(seen):
        raise RepositoryCaptureError("parent replaced")
    retained = _open_chain_once(rootfd, parts, seen)
    try:
        verified = _open_chain_once(rootfd, parts, seen)
    except BaseException:
        os.close(retained)
        raise
    os.close(verified)
    return retained


def _revalidate_chain(rootfd, parts, seen):
    current = _open_verified_chain(rootfd, parts, seen)
    os.close(current)


def _verify_parent(rootfd, parent):
    current = _open_verified_chain(rootfd, parent.parts, parent.seen)
    try:
        if not _same(os.fstat(current), os.fstat(parent.fd)):
            raise RepositoryCaptureError("parent replaced")
    except OSError as e:
        raise RepositoryCaptureError("parent replaced") from e
    finally:
        os.close(current)


def _open_parent_beneath(rootfd, path):
    parts = _parts(path)
    fd = os.dup(rootfd)
    seen = []
    try:
        for index, part in enumerate(parts[:-1]):
            try:
                current = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=fd,
                )
            except OSError as error:
                if error.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                    raise RepositoryCaptureError("unsafe path traversal") from error
                check = _open_verified_chain(rootfd, parts[:index], seen)
                try:
                    try:
                        probe = os.open(
                            part,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=check,
                        )
                    except OSError as missing:
                        if error.errno in (
                            errno.ENOTDIR,
                            errno.ELOOP,
                        ) and missing.errno in (errno.ENOTDIR, errno.ELOOP):
                            _verify_non_directory(check, part)
                            current_parent = _open_verified_chain(
                                rootfd, parts[:index], seen
                            )
                            try:
                                _verify_non_directory(current_parent, part)
                            finally:
                                os.close(current_parent)
                            _revalidate_chain(rootfd, parts[:index], seen)
                            os.close(fd)
                            return None
                        if missing.errno == errno.ENOENT:
                            # Revalidate the retained ancestor chain after the final
                            # probe before classifying the path as absent.
                            _revalidate_chain(rootfd, parts[:index], seen)
                            os.close(fd)
                            return None
                        raise RepositoryCaptureError(
                            "unsafe path traversal"
                        ) from missing
                    else:
                        os.close(probe)
                        raise RepositoryCaptureError("parent replaced")
                finally:
                    os.close(check)
            try:
                seen.append(os.fstat(current))
                os.close(fd)
            except BaseException:
                os.close(current)
                raise
            fd = current
        return _Parent(fd, parts[-1], tuple(parts[:-1]), tuple(seen))
    except BaseException:
        with suppress(OSError):
            os.close(fd)
        raise


def _observe_missing(rootfd, parent):
    for _ in range(2):
        _verify_parent(rootfd, parent)
        try:
            os.stat(parent.name, dir_fd=parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise RepositoryCaptureError("replacement race")
    _verify_parent(rootfd, parent)
    return _LeafObservation("missing")


def _observe_static(rootfd, parent, observed, kind, data=None):
    _verify_parent(rootfd, parent)
    try:
        final = os.stat(parent.name, dir_fd=parent.fd, follow_symlinks=False)
    except OSError as e:
        raise RepositoryCaptureError("replacement race") from e
    _verify_parent(rootfd, parent)
    if not _same(observed, final):
        raise RepositoryCaptureError("replacement race")
    return _LeafObservation(kind, data, observed.st_mode)


def _read_bound_symlink(parent, observed):
    path_flags = getattr(os, "O_PATH", None)
    if path_flags is None:
        raise RepositoryCaptureError("symlink open failed")
    try:
        fd = os.open(
            parent.name,
            path_flags | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent.fd,
        )
    except OSError as e:
        raise RepositoryCaptureError("symlink open failed") from e
    try:
        if not _same(os.fstat(fd), observed):
            raise RepositoryCaptureError("replacement race")
        target = os.readlink(b"", dir_fd=fd)
        if not _same(os.fstat(fd), observed):
            raise RepositoryCaptureError("replacement race")
        return os.fsencode(target) if isinstance(target, str) else target
    except OSError as e:
        raise RepositoryCaptureError("replacement race") from e
    finally:
        os.close(fd)


def _observe_regular(rootfd, parent, observed):
    try:
        fd = os.open(
            parent.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=parent.fd,
        )
    except OSError as e:
        raise RepositoryCaptureError("file open failed") from e
    try:
        got = os.fstat(fd)
        if not _same(got, observed):
            raise RepositoryCaptureError("replacement race")
        digest = hashlib.sha256()
        while True:
            data = os.read(fd, 1024 * 1024)
            if not data:
                break
            digest.update(data)
        end = os.fstat(fd)
        final = os.stat(parent.name, dir_fd=parent.fd, follow_symlinks=False)
        _verify_parent(rootfd, parent)
        if not _same_file_state(end, got) or not _same_file_state(final, got):
            raise RepositoryCaptureError("file mutated during read")
        return _LeafObservation("regular", digest.hexdigest(), got.st_mode)
    finally:
        os.close(fd)


def _observe_leaf(rootfd, path):
    parent = _open_parent_beneath(rootfd, path)
    if parent is None:
        return _LeafObservation("missing")
    try:
        _verify_parent(rootfd, parent)
        try:
            observed = os.stat(parent.name, dir_fd=parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            return _observe_missing(rootfd, parent)
        if stat.S_ISLNK(observed.st_mode):
            target = _read_bound_symlink(parent, observed)
            return _observe_static(rootfd, parent, observed, "symlink", target)
        if stat.S_ISDIR(observed.st_mode):
            return _observe_static(rootfd, parent, observed, "directory")
        if not stat.S_ISREG(observed.st_mode):
            return _LeafObservation("special", mode=observed.st_mode)
        return _observe_regular(rootfd, parent, observed)
    finally:
        os.close(parent.fd)


def _tracked(rootfd, path):
    observed = _observe_leaf(rootfd, path)
    if observed.kind in ("missing", "directory"):
        return WorktreeEntry(path, "deletion", "000000")
    if observed.kind == "symlink":
        return WorktreeEntry(
            path, "symlink", "120000", _digest(cast(bytes, observed.data))
        )
    if observed.kind == "special":
        raise RepositoryCaptureError("special file rejected")
    return WorktreeEntry(
        path,
        "file",
        "100755" if cast(int, observed.mode) & stat.S_IXUSR else "100644",
        cast(str, observed.data),
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
        inventory = capture_untracked(root, ident, rootfd)
        inc = set(included_untracked)
        if not inc.issubset(set(inventory)):
            raise RepositoryCaptureError("included path is not untracked")
        tracked = tuple(
            _tracked(rootfd, path) for path in sorted({entry.path for entry in index})
        )
        unknown = []
        for path in inventory:
            if path not in inc:
                unknown.append(UntrackedEntry(path, False))
                continue
            observed = _observe_leaf(rootfd, path)
            if observed.kind == "missing":
                raise RepositoryCaptureError("untracked disappeared")
            if observed.kind == "special":
                raise RepositoryCaptureError("special file rejected")
            if observed.kind != "regular":
                raise RepositoryCaptureError("included untracked is not regular")
            unknown.append(UntrackedEntry(path, True, cast(str, observed.data)))
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
