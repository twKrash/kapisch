"""Strict Git semantic observations."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .repository import HeadIdentity, IndexEntry, RepositoryCaptureError

_INTENT_TO_ADD = 1 << 29

_REDIRECT = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_KEY_0",
    "GIT_CONFIG_VALUE_0",
)


def _env(*, no_replace=False):
    e = os.environ.copy()
    for k in list(e):
        if k in _REDIRECT or k.startswith(
            ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
        ):
            e.pop(k, None)
    e["GIT_NO_LAZY_FETCH"] = "1"
    if no_replace:
        e["GIT_NO_REPLACE_OBJECTS"] = "1"
    return e


def _identity(p):
    try:
        s = p.stat()
        return (s.st_dev, s.st_ino)
    except OSError as e:
        raise RepositoryCaptureError("worktree unavailable") from e


def _root(repo, identity=None):
    p = Path(repo)
    if not p.is_dir():
        raise RepositoryCaptureError("worktree is not a directory")
    try:
        root = p.resolve()
        fd = os.open(
            os.fspath(root),
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            ident = (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
            if identity is not None and ident != identity:
                raise RepositoryCaptureError("worktree replaced")
            r = subprocess.run(
                (
                    "git",
                    "-c",
                    "core.fsmonitor=false",
                    "-C",
                    str(root),
                    "rev-parse",
                    "--is-bare-repository",
                    "--show-toplevel",
                ),
                env=_env(),
                capture_output=True,
                check=True,
            )
            expected = b"false\n" + os.fsencode(str(root)) + b"\n"
            if r.stdout != expected:
                raise RepositoryCaptureError(
                    "path is not supplied worktree root"
                )
            after = os.fstat(fd)
            if (
                (after.st_dev, after.st_ino) != ident
                or _identity(root) != ident
            ):
                raise RepositoryCaptureError("worktree replaced")
        finally:
            os.close(fd)
    except RepositoryCaptureError:
        raise
    except (OSError, RuntimeError) as e:
        raise RepositoryCaptureError("worktree unavailable") from e
    except subprocess.CalledProcessError as e:
        raise RepositoryCaptureError("not a Git worktree") from e
    return root, ident


def _git(repo, *args, identity=None, no_replace=False):
    root, ident = _root(repo, identity)
    try:
        r = subprocess.run(
            ("git", "-c", "core.fsmonitor=false", "-C", str(root), *args),
            env=_env(no_replace=no_replace),
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        raise RepositoryCaptureError("git observation failed") from e
    if _identity(root) != ident:
        raise RepositoryCaptureError("worktree replaced")
    return r.stdout


def _line(raw):
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise RepositoryCaptureError("malformed Git framing")
    return raw[:-1]


def _oid(raw, width):
    if len(raw) != width or not re.fullmatch(rb"[0-9a-f]+", raw):
        raise RepositoryCaptureError("invalid object id")
    return raw.decode("ascii")


def capture_head(repo, identity=None):
    try:
        fmt = _line(
            _git(
                repo,
                "rev-parse",
                "--show-object-format=storage",
                identity=identity,
            )
        ).decode("ascii")
    except (UnicodeError, ValueError) as e:
        raise RepositoryCaptureError("malformed Git output") from e
    if fmt not in ("sha1", "sha256"):
        raise RepositoryCaptureError("unsupported object format")
    width = 40 if fmt == "sha1" else 64
    raw = _line(_git(repo, "rev-parse", "--verify", "HEAD", identity=identity))
    commit = _oid(raw, width)
    typ = _line(
        _git(
            repo,
            "cat-file",
            "-t",
            commit,
            identity=identity,
            no_replace=True,
        )
    )
    if typ != b"commit":
        raise RepositoryCaptureError("HEAD is not a commit")
    return HeadIdentity(fmt, commit)


def _config(repo, name, identity=None):
    root, ident = _root(repo, identity)
    try:
        r = subprocess.run(
            (
                "git",
                "-c",
                "core.fsmonitor=false",
                "-C",
                str(root),
                "config",
                "--bool",
                "--get",
                name,
            ),
            env=_env(),
            capture_output=True,
            check=False,
        )
    except OSError as e:
        raise RepositoryCaptureError("git config failed") from e
    if _identity(root) != ident:
        raise RepositoryCaptureError("worktree replaced")
    if r.returncode == 1:
        return None
    if r.returncode != 0:
        raise RepositoryCaptureError("git config failed")
    try:
        return _line(r.stdout).decode("ascii").lower()
    except UnicodeDecodeError as e:
        raise RepositoryCaptureError("malformed Git config output") from e


def _records(raw):
    if raw == b"":
        return []
    if not raw.endswith(b"\0"):
        raise RepositoryCaptureError("truncated Git output")
    rec = raw[:-1].split(b"\0")
    if any(not x for x in rec):
        raise RepositoryCaptureError("malformed Git output")
    return rec


def _validate_path(p):
    if (
        type(p) is not bytes
        or not p
        or p.startswith(b"/")
        or b"\0" in p
        or any(x in (b"", b".", b"..") for x in p.split(b"/"))
    ):
        raise RepositoryCaptureError("unsafe Git path")


def _debug_flags(raw):
    flags = {}
    offset = 0
    while offset < len(raw):
        path_end = raw.find(b"\0", offset)
        if path_end < 0:
            raise RepositoryCaptureError("malformed index debug output")
        path = raw[offset:path_end]
        _validate_path(path)
        marker = raw.find(b"flags: ", path_end + 1)
        if marker < 0:
            raise RepositoryCaptureError("malformed index debug output")
        value_start = marker + len(b"flags: ")
        value_end = raw.find(b"\n", value_start)
        if value_end < 0:
            raise RepositoryCaptureError("malformed index debug output")
        value = raw[value_start:value_end]
        if not re.fullmatch(rb"[0-9a-f]+", value):
            raise RepositoryCaptureError("malformed index debug flags")
        flags.setdefault(path, []).append(int(value, 16))
        offset = value_end + 1
    return flags


def capture_index(repo, identity=None):
    head = capture_head(repo, identity)
    width = 40 if head.object_format == "sha1" else 64
    if (
        _config(repo, "core.sparseCheckout", identity) == "true"
        or _config(repo, "index.sparse", identity) == "true"
    ):
        raise RepositoryCaptureError("sparse checkout unsupported")
    debug_flags = _debug_flags(
        _git(repo, "ls-files", "--debug", "-z", identity=identity)
    )
    out = []
    seen = set()
    for rec in _records(
        _git(repo, "ls-files", "--stage", "--sparse", "-z", identity=identity)
    ):
        try:
            header, path = rec.split(b"\t", 1)
            mode, oid, stage = header.split(b" ")
        except ValueError as e:
            raise RepositoryCaptureError("malformed index record") from e
        _validate_path(path)
        if stage not in (b"0", b"1", b"2", b"3") or mode not in (
            b"100644",
            b"100755",
            b"120000",
            b"160000",
        ):
            raise RepositoryCaptureError("invalid index mode/stage")
        if mode == b"160000":
            raise RepositoryCaptureError("Gitlinks unsupported")
        key = (path, stage)
        if key in seen:
            raise RepositoryCaptureError("duplicate index record")
        seen.add(key)
        out.append(
            IndexEntry(path, int(stage), _oid(oid, width), mode.decode())
        )
    flags = {}
    for rec in _records(_git(repo, "ls-files", "-v", "-z", identity=identity)):
        if len(rec) < 3 or rec[1:2] != b" ":
            raise RepositoryCaptureError("malformed flags")
        flag, path = rec[:1], rec[2:]
        _validate_path(path)
        if flag not in (b" ", b"H", b"h", b"S", b"s", b"M", b"R", b"C", b"U"):
            raise RepositoryCaptureError("unknown index flag")
        flags.setdefault(path, []).append(flag)
    paths = {x.path for x in out}
    if set(flags) != paths or set(debug_flags) != paths:
        raise RepositoryCaptureError("flag/index mismatch")
    if any(
        value & _INTENT_TO_ADD
        for values in debug_flags.values()
        for value in values
    ):
        raise RepositoryCaptureError("intent-to-add index entry unsupported")
    stages = {}
    for entry in out:
        stages.setdefault(entry.path, set()).add(entry.stage)
    for path, records in flags.items():
        if len(records) > 1 and not any(stage != 0 for stage in stages[path]):
            raise RepositoryCaptureError("duplicate flag record")
        if any(flag in (b"S", b"s") for flag in records):
            raise RepositoryCaptureError("skip-worktree unsupported")
    return tuple(sorted(out, key=lambda x: (x.path, x.stage)))


def capture_untracked(repo, identity=None):
    seen = set()
    paths = []
    for path in _records(
        _git(
            repo,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            identity=identity,
        )
    ):
        _validate_path(path)
        if path in seen:
            raise RepositoryCaptureError("duplicate untracked path")
        seen.add(path)
        paths.append(path)
    return tuple(sorted(paths))
