"""Freshness validation for tracked Git inputs to task WorkOrders."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from ._task_artifacts import _DIGEST, _REF, ContractError


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError("cannot validate current Git inputs") from exc
    return result.stdout.strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError("cannot validate current Git inputs") from exc
    return result.stdout


def _validate_governing_inputs(root: Path, inputs: Any) -> None:
    if not isinstance(inputs, list) or not inputs:
        raise ContractError("work order requires governing Git inputs")
    seen_refs = set()
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {"ref", "digest"}:
            raise ContractError("malformed governing Git input")
        ref, digest = item["ref"], item["digest"]
        if (
            not isinstance(ref, str)
            or not _REF.fullmatch(ref)
            or ".." in ref.split("/")
            or not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)
        ):
            raise ContractError("malformed governing Git input")
        if ref in seen_refs:
            raise ContractError("duplicate governing Git input")
        seen_refs.add(ref)
        path = (root / ref).resolve()
        if not path.is_relative_to(root):
            raise ContractError("governing Git input escapes project root")
        _git(root, "ls-files", "--error-unmatch", "--", ref)
        try:
            current = path.read_bytes()
            committed = _git_bytes(root, "show", f"HEAD:{ref}")
            staged = _git_bytes(root, "show", f":{ref}")
        except OSError as exc:
            raise ContractError(
                "current governing inputs require reassessment"
            ) from exc
        if (
            hashlib.sha256(committed).hexdigest() != digest
            or hashlib.sha256(staged).hexdigest() != digest
            or hashlib.sha256(current).hexdigest() != digest
        ):
            raise ContractError("current governing inputs require reassessment")
