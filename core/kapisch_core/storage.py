from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
from contextlib import suppress
from pathlib import Path
from typing import Any

from .bundle import CoreBundle, verify_bundle

_DIRECTORY_FLAGS = (
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
_REQUIRED_SUPPORT = (
    hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_NONBLOCK")
    and os.open in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
    and os.unlink in os.supports_dir_fd
    and os.link in os.supports_dir_fd
)


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_AUTHORITY_NAMESPACES = frozenset(
    {"scopes", "human-actions", "gate-approvals", "human-artifacts", "acceptances"}
)
_HUMAN_ARTIFACT_ROOT = ".kapisch/v3/authority/human-artifacts"


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"invalid {label}")
    return value


def _open_dir(parent: int, name: str, *, create: bool = False) -> int:
    try:
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
    except FileNotFoundError:
        if not create:
            raise
        with suppress(FileExistsError):
            os.mkdir(name, 0o700, dir_fd=parent)
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
    if create:
        try:
            os.fsync(parent)
        except BaseException:
            os.close(descriptor)
            raise
    return descriptor


def _open_tree(
    repo: Path, *components: str, create: bool = False
) -> tuple[int, list[int]]:
    if not _REQUIRED_SUPPORT:
        raise OSError(
            "safe descriptor-relative authority storage is unsupported on this platform"
        )
    descriptors = [os.open(os.fspath(repo), _DIRECTORY_FLAGS)]
    try:
        for component in (".kapisch", "v3", *components):
            descriptors.append(_open_dir(descriptors[-1], component, create=create))
        return descriptors[-1], descriptors
    except BaseException:
        for fd in reversed(descriptors):
            os.close(fd)
        raise


def _close(fds: list[int]) -> None:
    for fd in reversed(fds):
        os.close(fd)


def _read_file(directory: int, name: str) -> bytes:
    fd = os.open(name, _FILE_FLAGS, dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("authority artifact is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _runs_dir(repo: Path, *, create: bool) -> tuple[int, list[int]]:
    return _open_tree(repo, "runs", create=create)


def _run_dir(repo: Path, run_id: str, *, create: bool) -> tuple[int, list[int]]:
    runs, fds = _runs_dir(repo, create=create)
    try:
        run = _open_dir(runs, _id(run_id, "run_id"), create=create)
        fds.append(run)
        return run, fds
    except BaseException:
        _close(fds)
        raise


def _read_contained(repo: Path, run_id: str, relative: str) -> bytes:
    if (
        not isinstance(relative, str)
        or not relative
        or relative.startswith("/")
        or "\\" in relative
        or "\x00" in relative
    ):
        raise ValueError("request input path must be run-relative")
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        parent = run
        extra: list[int] = []
        try:
            parts = relative.split("/")
            if any(part in {"", ".", ".."} for part in parts):
                raise ValueError("request input path escapes run")
            for part in parts[:-1]:
                parent = _open_dir(parent, part)
                extra.append(parent)
            file_fd = os.open(parts[-1], _FILE_FLAGS, dir_fd=parent)
            try:
                if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                    raise ValueError("authority artifact is not a regular file")
                chunks: list[bytes] = []
                while chunk := os.read(file_fd, 1024 * 1024):
                    chunks.append(chunk)
                os.fsync(file_fd)
                for descriptor in [*extra, parent, run]:
                    os.fsync(descriptor)
                return b"".join(chunks)
            finally:
                os.close(file_fd)
        finally:
            _close(extra)
    finally:
        _close(fds)


def _safe_relative(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and "\x00" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _validate_digest(digest: str) -> None:
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("invalid bundle digest")


def _open_bundles(repo: Path, create: bool) -> tuple[int, list[int]]:
    if not _REQUIRED_SUPPORT:
        raise OSError(
            "safe descriptor-relative bundle storage is unsupported on this platform"
        )
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


def _atomic_write_at(directory: int, name: str, data: bytes, *, replace: bool) -> None:
    """Durably publish bytes in a verified directory descriptor."""
    temporary = f".{name}.{secrets.token_hex(12)}.tmp"
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
            if written <= 0:
                raise OSError("authority write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        if replace:
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        else:
            os.link(
                temporary,
                name,
                src_dir_fd=directory,
                dst_dir_fd=directory,
                follow_symlinks=False,
            )
        os.fsync(directory)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)


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


def load_authority_record(repo: Path, namespace: str, identity: str) -> bytes:
    if namespace not in _AUTHORITY_NAMESPACES:
        raise ValueError("invalid authority namespace")
    name = f"{_id(identity, 'identity')}.json"
    directory, opened = _open_tree(Path(repo), "authority", namespace, create=False)
    try:
        return _read_file(directory, name)
    finally:
        _close(opened)


def load_authority_records(repo: Path, namespace: str) -> list[tuple[str, bytes]]:
    if namespace not in _AUTHORITY_NAMESPACES:
        raise ValueError("invalid authority namespace")
    if os.listdir not in os.supports_fd:
        raise OSError(
            "safe descriptor-relative authority listing is unsupported on this platform"
        )
    try:
        directory, opened = _open_tree(Path(repo), "authority", namespace, create=False)
    except FileNotFoundError:
        return []
    try:
        records = []
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            identity = name[:-5]
            _id(identity, "identity")
            try:
                data = _read_file(directory, name)
            except FileNotFoundError as error:
                raise ValueError("authority record disappeared during census") from error
            records.append((identity, data))
        return records
    finally:
        _close(opened)


def store_authority_record(
    repo: Path, namespace: str, identity: str, data: bytes
) -> bool:
    """Publish immutable canonical bytes; return False for an identical retry."""
    if namespace not in _AUTHORITY_NAMESPACES:
        raise ValueError("invalid authority namespace")
    name = f"{_id(identity, 'identity')}.json"
    if not isinstance(data, bytes):
        raise TypeError("authority record must be bytes")
    directory, opened = _open_tree(Path(repo), "authority", namespace, create=True)
    try:
        try:
            _atomic_write_at(directory, name, data, replace=False)
        except FileExistsError:
            existing = _read_file(directory, name)
            if existing == data:
                _sync_hierarchy(opened)
                return False
            raise
        _sync_hierarchy(opened)
        return True
    finally:
        _close(opened)


def retain_human_approval_artifact(repo: Path, data: bytes) -> dict[str, str]:
    """Retain exact external approval bytes at their digest-derived immutable path."""
    if not isinstance(data, bytes):
        raise TypeError("human approval artifact must be bytes")
    digest = hashlib.sha256(data).hexdigest()
    try:
        store_authority_record(Path(repo), "human-artifacts", digest, data)
    except OSError as error:
        try:
            retained = load_authority_record(Path(repo), "human-artifacts", digest)
        except OSError:
            raise error from None
        if retained != data or hashlib.sha256(retained).hexdigest() != digest:
            raise ValueError(
                "retained human approval artifact differs from expected bytes"
            ) from error
        store_authority_record(Path(repo), "human-artifacts", digest, data)
    retained = load_authority_record(Path(repo), "human-artifacts", digest)
    if retained != data or hashlib.sha256(retained).hexdigest() != digest:
        raise ValueError("retained human approval artifact read-back mismatch")
    return {"path": f"{_HUMAN_ARTIFACT_ROOT}/{digest}.json", "sha256": digest}


def load_human_approval_artifact(repo: Path, path: str, digest: str) -> bytes:
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("human approval artifact digest must be lowercase SHA-256")
    expected_path = f"{_HUMAN_ARTIFACT_ROOT}/{digest}.json"
    if path != expected_path:
        raise ValueError("human approval artifact path is not canonical")
    data = load_authority_record(Path(repo), "human-artifacts", digest)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("human approval artifact digest mismatch")
    return data


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
                os.link(
                    temporary,
                    name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
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
