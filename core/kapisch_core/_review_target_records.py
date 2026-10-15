"""Closed, read-only consumers of externally produced Stage 5 target facts."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Mapping

from ._validation_json import _json
from .storage import _close, _open_dir, _read_contained, _read_file, _run_dir

_BINDINGS = "review-inputs/review-target-bindings"
_ROOTS = "review-inputs/comparison-roots"
_COMMON = {
    "protocol_version",
    "run_id",
    "plan_candidate_ref",
    "plan_id",
    "target",
    "object_format",
}
_ROOT_FIELDS = _COMMON | {"comparison_root_contract", "anchor"}
_BINDING_FIELDS = _COMMON | {
    "review_target_binding_contract",
    "stage_id",
    "purpose",
    "comparison_root_ref",
    "comparison_root",
    "comparison_base_ref",
    "base",
    "head",
    "review_target_ref",
}


def _files(repo: Path, run_id: str, directory: str) -> tuple[tuple[str, bytes], ...]:
    """Contained flat census: absence is optional; every present entry must be readable."""
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        current = run
        for part in directory.split("/"):
            try:
                current = _open_dir(current, part)
            except FileNotFoundError:
                return ()
            fds.append(current)
        return tuple(
            (name, _read_file(current, name)) for name in sorted(os.listdir(current))
        )
    finally:
        _close(fds)


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} has missing or unknown fields")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid target artifact digest")
    return value


def _reference(value: Any, directory: str) -> dict[str, Any]:
    ref = _exact(value, {"path", "sha256"}, "target reference")
    digest = _digest(ref["sha256"])
    if ref["path"] != f"{directory}/{digest}.json":
        raise ValueError("target reference path is not exact")
    return ref


def _anchor(value: Any, object_format: str) -> None:
    length = {"sha1": 40, "sha256": 64}.get(object_format)
    if (
        length is None
        or not isinstance(value, str)
        or not re.fullmatch(rf"{object_format}:[0-9a-f]{{{length}}}", value)
    ):
        raise ValueError("invalid target object anchor")


def _target(value: Any) -> None:
    target = _exact(value, {"kind", "ref"}, "whole-branch target")
    ref = target["ref"]
    if (
        target["kind"] != "whole-branch"
        or not isinstance(ref, str)
        or not ref.startswith("refs/heads/")
        or ref.endswith(("/", "."))
        or any(char in ref for char in " ~^:?*[\\")
        or ".." in ref
        or "@{" in ref
        or "//" in ref
        or any(ord(char) < 32 or ord(char) == 127 for char in ref)
        or any(
            not part or part.startswith(".") or part.endswith(".lock")
            for part in ref.split("/")
        )
    ):
        raise ValueError("target is not a canonical whole-branch reference")


def _common(record: dict[str, Any], run_id: str) -> None:
    if type(record["protocol_version"]) is not int or record["protocol_version"] != 3:
        raise ValueError("unsupported target record protocol")
    if record["run_id"] != run_id:
        raise ValueError("target record belongs to another run")
    _reference(
        record["plan_candidate_ref"], ".kapisch/v3/authority/plan-approval-candidates"
    )
    if not isinstance(record["plan_id"], str) or not record["plan_id"]:
        raise ValueError("invalid target plan identity")
    _target(record["target"])
    if record["object_format"] not in ("sha1", "sha256"):
        raise ValueError("invalid target object format")


def _read_binding(repo: Path, run_id: str, name: str, data: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(data).hexdigest()
    if name != f"{digest}.json":
        raise ValueError("reservation filename differs from full-byte digest")
    record = _exact(_json(data, "target reservation"), _BINDING_FIELDS, "reservation")
    _common(record, run_id)
    if record["review_target_binding_contract"] != "review-target-binding/1":
        raise ValueError("unsupported reservation contract")
    if not isinstance(record["stage_id"], str) or not re.fullmatch(
        r"s-[0-9a-f]{32}", record["stage_id"]
    ):
        raise ValueError("invalid reservation stage identity")
    if record["purpose"] not in ("iteration", "final"):
        raise ValueError("invalid reservation purpose")
    prefix = f".kapisch/v3/runs/{run_id}/review-inputs"
    for field, directory in (
        ("comparison_base_ref", "comparison-bases"),
        ("review_target_ref", "review-targets"),
    ):
        _reference(record[field], f"{prefix}/{directory}")
    root_ref = _exact(
        record["comparison_root_ref"], {"path", "sha256"}, "root reference"
    )
    _digest(root_ref["sha256"])
    root_path = f"{_ROOTS}/{record['plan_candidate_ref']['sha256']}.json"
    if root_ref["path"] != f".kapisch/v3/runs/{run_id}/{root_path}":
        raise ValueError("comparison root path is not candidate-addressed")
    root_bytes = _read_contained(repo, run_id, root_path)
    if hashlib.sha256(root_bytes).hexdigest() != root_ref["sha256"]:
        raise ValueError("comparison root digest mismatch")
    root = _exact(_json(root_bytes, "comparison root"), _ROOT_FIELDS, "root")
    _common(root, run_id)
    if root["comparison_root_contract"] != "comparison-root/1" or any(
        root[key] != record[key] for key in _COMMON
    ):
        raise ValueError("comparison root identity mismatch")
    comparison = _exact(
        record["comparison_root"],
        {"source", "anchor", "must_differ_from_head"},
        "root binding",
    )
    strict = comparison["must_differ_from_head"]
    if (
        comparison["source"] != "stage5-target-binding"
        or type(strict) is not bool
        or comparison["anchor"] != root["anchor"]
        or record["base"] != root["anchor"]
    ):
        raise ValueError("reservation changed comparison root")
    for anchor in (root["anchor"], record["base"], record["head"]):
        _anchor(anchor, record["object_format"])
    if (record["purpose"] == "final" and not strict) or (
        strict and record["base"] == record["head"]
    ):
        raise ValueError("reservation violates persisted strict comparison rule")
    return record


def _reservation_census(
    repo: Path, run_id: str
) -> tuple[tuple[dict[str, Any], dict[str, str]], ...]:
    for name, data in _files(repo, run_id, _ROOTS):
        root = _exact(_json(data, "comparison root census"), _ROOT_FIELDS, "root")
        _common(root, run_id)
        if (
            root["comparison_root_contract"] != "comparison-root/1"
            or name != f"{root['plan_candidate_ref']['sha256']}.json"
        ):
            raise ValueError("comparison root census identity mismatch")
        _anchor(root["anchor"], root["object_format"])
    records = []
    for name, data in _files(repo, run_id, _BINDINGS):
        record = _read_binding(repo, run_id, name, data)
        digest = hashlib.sha256(data).hexdigest()
        records.append(
            (
                record,
                {
                    "kind": "review-target-binding/1",
                    "path": f"{_BINDINGS}/{name}",
                    "sha256": digest,
                },
            )
        )
    # Reading every root above also detects cross-stage root replacement: each earlier
    # reservation must still cite the same candidate-addressed immutable bytes.
    return tuple(records)


def _unique_reservation(
    records: tuple, stage_id: str, candidate_ref: Mapping[str, Any], plan_id: str
):
    matching = [
        (record, ref) for record, ref in records if record["stage_id"] == stage_id
    ]
    if len(matching) != 1:
        raise ValueError(
            "attempt requires exactly one reservation across all candidates"
        )
    record, ref = matching[0]
    if record["plan_candidate_ref"] != candidate_ref or record["plan_id"] != plan_id:
        raise ValueError("reservation candidate or plan identity mismatch")
    return record, ref
