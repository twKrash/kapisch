from __future__ import annotations

import hashlib
import os
import secrets
import stat
from contextlib import suppress
from pathlib import Path

from .bundle import CoreBundle, verify_bundle


_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_REQUIRED_SUPPORT = (
    hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and os.open in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
    and os.unlink in os.supports_dir_fd
    and os.link in os.supports_dir_fd
)


def _validate_digest(digest: str) -> None:
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("invalid bundle digest")


def _open_bundles(repo: Path, create: bool) -> tuple[int, list[int]]:
    if not _REQUIRED_SUPPORT:
        raise OSError("safe descriptor-relative bundle storage is unsupported on this platform")
    root = os.open(os.fspath(repo), _DIRECTORY_FLAGS)
    opened = [root]
    parent = root
    try:
        for component in (".kapisch", "v3", "bundles"):
            try:
                descriptor = os.open(component, _DIRECTORY_FLAGS, dir_fd=parent)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                else:
                    os.fsync(parent)
                descriptor = os.open(component, _DIRECTORY_FLAGS, dir_fd=parent)
            opened.append(descriptor)
            parent = descriptor
        return parent, opened
    except BaseException:
        for descriptor in reversed(opened):
            os.close(descriptor)
        raise


def _close_all(descriptors: list[int]) -> None:
    for descriptor in reversed(descriptors):
        os.close(descriptor)


def _read_bundle(directory: int, name: str) -> bytes:
    descriptor = os.open(name, _FILE_FLAGS, dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("retained bundle is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _sync_existing(directory: int, name: str, digest: str) -> None:
    descriptor = os.open(name, _FILE_FLAGS, dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("retained bundle is not a regular file")
        data = bytearray()
        while chunk := os.read(descriptor, 1024 * 1024):
            data.extend(chunk)
        verify_bundle(bytes(data), digest)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory)


def _sync_hierarchy(descriptors: list[int]) -> None:
    for descriptor in reversed(descriptors):
        os.fsync(descriptor)


def store_bundle(repo: Path, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    verify_bundle(data, digest)
    directory, opened = _open_bundles(Path(repo), create=True)
    name = f"{digest}.json"
    temporary = f".{digest}.{secrets.token_hex(16)}.tmp"
    try:
        try:
            _sync_existing(directory, name, digest)
            _sync_hierarchy(opened)
            return digest
        except FileNotFoundError:
            pass

        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory,
        )
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written == 0:
                    raise OSError("bundle write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            try:
                os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
                os.fsync(directory)
                _sync_hierarchy(opened)
            except FileExistsError:
                _sync_existing(directory, name, digest)
                _sync_hierarchy(opened)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary, dir_fd=directory)
            os.fsync(directory)
        return digest
    finally:
        _close_all(opened)


def load_bundle(repo: Path, digest: str) -> CoreBundle:
    _validate_digest(digest)
    directory, opened = _open_bundles(Path(repo), create=False)
    try:
        return verify_bundle(_read_bundle(directory, f"{digest}.json"), digest)
    finally:
        _close_all(opened)
