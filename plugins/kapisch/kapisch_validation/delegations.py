from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

from .errors import ValidationError, sorted_errors
from .helpers import is_integer, non_empty_string, string_list
from .models import Manifest

ROUTE_FILE = "delegations/00-route.toml"
ROUTE_VERSION = 1

ROUTE = {
    "version",
    "task_id",
    "route_id",
    "source_revision",
    "steps",
    "extensions",
}
STEP = {
    "id",
    "sequence",
    "parent_node_id",
    "status",
    "selection_mode",
    "capability_kind",
    "requested_capability",
    "resolved_capability",
    "source_plugin",
    "effect_class",
    "authority_mode",
    "authority_ref",
    "context_path",
    "context_sha256",
    "evidence_path",
    "evidence_sha256",
    "source_revision",
    "result_revision",
    "extensions",
}
STATUSES = {"planned", "started", "completed", "blocked", "failed"}
SELECTION_MODES = {"explicit", "automatic"}
CAPABILITY_KINDS = {"skill", "plugin-skill", "plugin-tools"}
EFFECT_CLASSES = {
    "repository-read",
    "repository-write",
    "external-read",
    "external-write",
    "destructive",
}
AUTHORITY_MODES = {"request-scoped", "explicit-step"}
EXTERNAL_WRITE_CLASSES = {"external-write", "destructive"}
READ_CLASSES = {"repository-read", "external-read"}
UNAVAILABLE = "unavailable"
STEP_ID_RE = re.compile(r"^D\d{2,}$")
ROUTE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
IMPLEMENTATION_KIND = "behavioral"


def _e(c: str, p: Path, r: str, m: str) -> ValidationError:
    return ValidationError(c, str(p), r, m)


def _closed(
    data: object, allowed: set[str], p: Path, r: str, errors: list[ValidationError]
) -> None:
    if not isinstance(data, dict):
        errors.append(_e("TWV-DELEG-SCHEMA-WRONG-SHAPE", p, r, "must be a TOML table"))
        return
    for key in sorted(set(data) - allowed):
        errors.append(
            _e("TWV-DELEG-SCHEMA-UNKNOWN-FIELD", p, f"{r}.{key}", "unknown normative field")
        )


def _extensions(
    data: object, path: Path, reference: str, errors: list[ValidationError]
) -> None:
    if data is None:
        return
    if not isinstance(data, dict):
        errors.append(_e("TWV-DELEG-SCHEMA-WRONG-SHAPE", path, reference, "must be a table"))
        return
    for namespace in sorted(data):
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", namespace):
            errors.append(
                _e(
                    "TWV-DELEG-SCHEMA-INVALID-EXTENSION",
                    path,
                    f"{reference}.{namespace}",
                    "extension keys must be reverse-DNS namespaces",
                )
            )


def _contained(task_dir: Path, relative: str) -> Path | None:
    """Resolve a step-relative evidence path inside task_dir.

    Returns the resolved candidate when it stays inside task_dir and no path
    component under task_dir is a symlink; otherwise returns None (callers add
    the specific error).
    """
    candidate = (task_dir / relative).resolve()
    try:
        candidate.relative_to(task_dir.resolve())
    except ValueError:
        return None
    current = task_dir.resolve()
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return None
    return candidate


def _digest_file(path: Path, reference: str, errors: list[ValidationError]) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        errors.append(
            _e("TWV-DELEG-UNREADABLE-EVIDENCE", path, reference, "evidence file is unreadable")
        )
        return None


def _evidence_file(
    task_dir: Path,
    relative: str,
    declared: str,
    step_ref: str,
    field: str,
    errors: list[ValidationError],
) -> None:
    if declared == UNAVAILABLE:
        return
    if SHA256_RE.fullmatch(declared) is None:
        errors.append(
            _e(
                "TWV-DELEG-INVALID-DIGEST",
                task_dir / ROUTE_FILE,
                f"{step_ref}.{field}",
                "must be 64 lowercase hexadecimal characters",
            )
        )
        return
    candidate = _contained(task_dir, relative)
    if candidate is None:
        errors.append(
            _e(
                "TWV-DELEG-PATH-ESCAPE",
                task_dir / ROUTE_FILE,
                f"{step_ref}.{field}",
                "evidence path must stay inside the task directory without symlinks",
            )
        )
        return
    if not candidate.is_file():
        errors.append(
            _e(
                "TWV-DELEG-MISSING-EVIDENCE",
                task_dir / ROUTE_FILE,
                f"{step_ref}.{field}",
                "required evidence file is missing",
            )
        )
        return
    try:
        candidate.read_text(encoding="utf-8")
    except OSError:
        errors.append(
            _e(
                "TWV-DELEG-UNREADABLE-EVIDENCE",
                candidate,
                f"{step_ref}.{field}",
                "evidence file is unreadable",
            )
        )
        return
    except UnicodeDecodeError:
        errors.append(
            _e(
                "TWV-DELEG-EVIDENCE-ENCODING",
                candidate,
                f"{step_ref}.{field}",
                "evidence file must be valid UTF-8",
            )
        )
        return
    digest = _digest_file(candidate, f"{step_ref}.{field}", errors)
    if digest is not None and digest != declared:
        errors.append(
            _e(
                "TWV-DELEG-STALE-EVIDENCE",
                candidate,
                f"{step_ref}.{field}",
                "evidence file digest does not match the declared SHA-256",
            )
        )


def parse_route(task_dir: Path) -> tuple[dict[str, object] | None, tuple[ValidationError, ...]]:
    errors: list[ValidationError] = []
    path = task_dir / ROUTE_FILE
    if not path.is_file():
        return None, sorted_errors(
            [_e("TWV-DELEG-MISSING-ARTIFACT", path, ROUTE_FILE, "required route record is missing")]
        )
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return None, sorted_errors(
            [_e("TWV-DELEG-MALFORMED-TOML", path, "toml", str(exc))]
        )
    _closed(raw, ROUTE, path, "root", errors)
    _extensions(raw.get("extensions"), path, "extensions", errors)
    version = raw.get("version")
    if not is_integer(version) or version != ROUTE_VERSION:
        errors.append(
            _e(
                "TWV-DELEG-INVALID-VERSION",
                path,
                "version",
                "must be integer 1",
            )
        )
    for key in ("task_id", "route_id", "source_revision", "steps"):
        if key not in raw:
            errors.append(
                _e("TWV-DELEG-MISSING-FIELD", path, key, "required field is missing")
            )
    for key in ("task_id", "source_revision"):
        if key in raw:
            non_empty_string(
                raw[key],
                errors,
                _e("TWV-DELEG-WRONG-SHAPE", path, key, "must be a non-empty string"),
            )
    route_id = raw.get("route_id")
    if route_id is not None and (
        not isinstance(route_id, str) or ROUTE_ID_RE.fullmatch(route_id) is None
    ):
        errors.append(
            _e(
                "TWV-DELEG-INVALID-ROUTE-ID",
                path,
                "route_id",
                "must match [a-z0-9][a-z0-9-]{2,79}",
            )
        )
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list):
        errors.append(
            _e("TWV-DELEG-WRONG-SHAPE", path, "steps", "must be an array of tables")
        )
        raw_steps = []
    step_ids: list[str] = []
    sequences: list[int] = []
    for i, step in enumerate(raw_steps):
        ref = f"steps[{i}]"
        _closed(step, STEP, path, ref, errors)
        if not isinstance(step, dict):
            continue
        for key in (
            "id",
            "sequence",
            "parent_node_id",
            "status",
            "selection_mode",
            "capability_kind",
            "requested_capability",
            "effect_class",
            "authority_mode",
            "context_path",
            "context_sha256",
            "evidence_path",
            "evidence_sha256",
            "source_revision",
        ):
            if key not in step:
                errors.append(
                    _e("TWV-DELEG-MISSING-FIELD", path, f"{ref}.{key}", "required step field is missing")
                )
        for key in (
            "parent_node_id",
            "requested_capability",
            "context_path",
            "context_sha256",
            "evidence_path",
            "evidence_sha256",
            "source_revision",
        ):
            if key in step:
                non_empty_string(
                    step[key],
                    errors,
                    _e("TWV-DELEG-WRONG-SHAPE", path, f"{ref}.{key}", "must be a non-empty string"),
                )
        step_id = step.get("id")
        if isinstance(step_id, str) and STEP_ID_RE.fullmatch(step_id) is None:
            errors.append(
                _e(
                    "TWV-DELEG-INVALID-STEP-ID",
                    path,
                    f"{ref}.id",
                    "must match D followed by at least two digits (for example D01)",
                )
            )
        if isinstance(step_id, str):
            step_ids.append(step_id)
        sequence = step.get("sequence")
        if is_integer(sequence):
            if sequence < 0:
                errors.append(
                    _e(
                        "TWV-DELEG-WRONG-SHAPE",
                        path,
                        f"{ref}.sequence",
                        "must be a non-negative integer",
                    )
                )
            else:
                sequences.append(sequence)
        else:
            errors.append(
                _e(
                    "TWV-DELEG-WRONG-SHAPE",
                    path,
                    f"{ref}.sequence",
                    "must be a non-negative integer",
                )
            )
        for key, allowed in (
            ("status", STATUSES),
            ("selection_mode", SELECTION_MODES),
            ("capability_kind", CAPABILITY_KINDS),
            ("effect_class", EFFECT_CLASSES),
            ("authority_mode", AUTHORITY_MODES),
        ):
            if key in step and step[key] not in allowed:
                errors.append(
                    _e(
                        "TWV-DELEG-INVALID-ENUM",
                        path,
                        f"{ref}.{key}",
                        f"must be one of {sorted(allowed)}",
                    )
                )
        status = step.get("status")
        resolved = step.get("resolved_capability")
        if resolved is not None:
            if not isinstance(resolved, str) or not resolved:
                errors.append(
                    _e(
                        "TWV-DELEG-WRONG-SHAPE",
                        path,
                        f"{ref}.resolved_capability",
                        "must be a non-empty string",
                    )
                )
            elif status in {"started", "completed", "blocked", "failed"} and resolved == UNAVAILABLE:
                errors.append(
                    _e(
                        "TWV-DELEG-UNRESOLVED-CAPABILITY",
                        path,
                        f"{ref}.resolved_capability",
                        "a started, completed, blocked, or failed step must resolve a capability",
                    )
                )
        for capability_field in ("requested_capability", "resolved_capability"):
            capability = step.get(capability_field)
            if capability in {"kapisch", "$kapisch"}:
                errors.append(
                    _e(
                        "TWV-DELEG-SELF-DELEGATION",
                        path,
                        f"{ref}.{capability_field}",
                        "KAPISCH may not delegate its route to itself",
                    )
                )
        source_plugin = step.get("source_plugin")
        if source_plugin is not None and (
            not isinstance(source_plugin, str) or not source_plugin
        ):
            errors.append(
                _e(
                    "TWV-DELEG-WRONG-SHAPE",
                    path,
                    f"{ref}.source_plugin",
                    "must be a non-empty string or 'unavailable'",
                )
            )
        authority_mode = step.get("authority_mode")
        authority_ref = step.get("authority_ref")
        if authority_ref is not None and (
            not isinstance(authority_ref, str) or not authority_ref
        ):
            errors.append(
                _e(
                    "TWV-DELEG-WRONG-SHAPE",
                    path,
                    f"{ref}.authority_ref",
                    "must be a non-empty string",
                )
            )
        if authority_mode == "explicit-step" and (
            not isinstance(authority_ref, str)
            or not authority_ref
            or authority_ref == UNAVAILABLE
        ):
            errors.append(
                _e(
                    "TWV-DELEG-MISSING-AUTHORITY-REF",
                    path,
                    f"{ref}.authority_ref",
                    "explicit-step authority requires an in-context authority reference",
                )
            )
        effect_class = step.get("effect_class")
        if effect_class in EXTERNAL_WRITE_CLASSES and authority_mode != "explicit-step":
            errors.append(
                _e(
                    "TWV-DELEG-MISSING-EXPLICIT-AUTHORITY",
                    path,
                    f"{ref}.authority_mode",
                    "external-write and destructive steps require explicit-step authority",
                )
            )
        result_revision = step.get("result_revision")
        if result_revision is not None and (
            not isinstance(result_revision, str) or not result_revision
        ):
            errors.append(
                _e(
                    "TWV-DELEG-WRONG-SHAPE",
                    path,
                    f"{ref}.result_revision",
                    "must be a non-empty string or 'unavailable'",
                )
            )
        if status == "completed" and (
            not isinstance(result_revision, str) or result_revision == UNAVAILABLE
        ):
            errors.append(
                _e(
                    "TWV-DELEG-MISSING-RESULT-REVISION",
                    path,
                    f"{ref}.result_revision",
                    "a completed step must record its resulting repository revision",
                )
            )
        context_path = step.get("context_path")
        context_sha256 = step.get("context_sha256")
        if context_path == UNAVAILABLE or context_sha256 == UNAVAILABLE:
            errors.append(
                _e(
                    "TWV-DELEG-MISSING-CONTEXT",
                    path,
                    f"{ref}.context_path",
                    "every step must persist a context file and digest before invocation",
                )
            )
        elif isinstance(context_path, str) and isinstance(context_sha256, str):
            _evidence_file(task_dir, context_path, context_sha256, ref, "context_path", errors)
        evidence_path = step.get("evidence_path")
        evidence_sha256 = step.get("evidence_sha256")
        if status == "planned":
            if evidence_path != UNAVAILABLE or evidence_sha256 != UNAVAILABLE:
                errors.append(
                    _e(
                        "TWV-DELEG-PREMATURE-EVIDENCE",
                        path,
                        f"{ref}.evidence_path",
                        "a planned step must leave evidence fields 'unavailable'",
                    )
                )
        elif status in {"completed", "blocked", "failed"}:
            if evidence_path == UNAVAILABLE or evidence_sha256 == UNAVAILABLE:
                errors.append(
                    _e(
                        "TWV-DELEG-MISSING-EVIDENCE",
                        path,
                        f"{ref}.evidence_path",
                        "a completed, blocked, or failed step must record evidence paths and digests",
                    )
                )
            elif isinstance(evidence_path, str) and isinstance(evidence_sha256, str):
                _evidence_file(task_dir, evidence_path, evidence_sha256, ref, "evidence_path", errors)
        elif status == "started" and isinstance(evidence_path, str) and isinstance(evidence_sha256, str):
            if evidence_path != UNAVAILABLE:
                _evidence_file(task_dir, evidence_path, evidence_sha256, ref, "evidence_path", errors)
        _extensions(step.get("extensions"), path, f"{ref}.extensions", errors)
    if len(step_ids) != len(set(step_ids)):
        errors.append(
            _e(
                "TWV-DELEG-DUPLICATE-STEP-ID",
                path,
                "steps[].id",
                "step IDs must be unique",
            )
        )
    if len(sequences) != len(set(sequences)):
        errors.append(
            _e(
                "TWV-DELEG-DUPLICATE-SEQUENCE",
                path,
                "steps[].sequence",
                "step sequence values must be unique",
            )
        )
    ordered = sorted(
        (step for step in raw_steps if isinstance(step, dict) and is_integer(step.get("sequence"))),
        key=lambda s: int(s["sequence"]),
    )
    if len([s for s in ordered if s.get("status") == "started"]) > 1:
        errors.append(
            _e(
                "TWV-DELEG-PARALLEL-STARTED",
                path,
                "steps",
                "at most one delegated step may be started",
            )
        )
    for index, step in enumerate(ordered):
        status = step.get("status")
        if status not in {"started", "completed", "blocked", "failed"}:
            continue
        for earlier in ordered[:index]:
            if earlier.get("status") != "completed":
                errors.append(
                    _e(
                        "TWV-DELEG-ORDERING",
                        path,
                        f"steps[{step.get('id')}]",
                        "a step may start or complete only after every preceding step completes",
                    )
                )
                break
    if errors:
        return None, sorted_errors(errors)
    return raw, ()


def validate_route_references(
    manifest: Manifest, task_dir: Path
) -> tuple[ValidationError, ...]:
    if manifest.version != 3:
        return ()
    route, route_errors = parse_route(task_dir)
    if route is None:
        return route_errors
    errors: list[ValidationError] = []
    path = task_dir / ROUTE_FILE
    if route.get("task_id") != manifest.task_id:
        errors.append(
            _e(
                "TWV-DELEG-TASK-MISMATCH",
                path,
                "root.task_id",
                "route task_id must match the manifest task_id",
            )
        )
    if route.get("source_revision") != manifest.base_revision:
        errors.append(
            _e(
                "TWV-DELEG-REVISION-MISMATCH",
                path,
                "root.source_revision",
                "route source_revision must match the manifest base_revision",
            )
        )
    steps = [step for step in route["steps"] if isinstance(step, dict)]
    by_id: dict[str, dict[str, object]] = {}
    for step in steps:
        if isinstance(step.get("id"), str):
            by_id[step["id"]] = step
    nodes_by_id = {node.id: node for node in manifest.nodes}
    referenced_by: dict[str, str] = {}
    for node in manifest.nodes:
        for step_id in node.raw.get("delegation_ids", []):
            if not isinstance(step_id, str):
                continue
            if step_id not in by_id:
                errors.append(
                    _e(
                        "TWV-DELEG-UNRESOLVED-STEP",
                        path,
                        f"nodes[{node.id}].delegation_ids.{step_id}",
                        "delegation references a step that does not exist in the route record",
                    )
                )
                continue
            if step_id in referenced_by:
                errors.append(
                    _e(
                        "TWV-DELEG-REUSED-STEP",
                        path,
                        f"nodes[{node.id}].delegation_ids.{step_id}",
                        f"delegation step is already referenced by node {referenced_by[step_id]}",
                    )
                )
                continue
            referenced_by[step_id] = node.id
            step = by_id[step_id]
            parent = step.get("parent_node_id")
            if parent != node.id:
                errors.append(
                    _e(
                        "TWV-DELEG-OWNER-MISMATCH",
                        path,
                        f"nodes[{node.id}].delegation_ids.{step_id}",
                        "referenced step's parent_node_id must match the owning graph node",
                    )
                )
            if node.kind in {"review", "final"} and step.get("effect_class") not in READ_CLASSES:
                errors.append(
                    _e(
                        "TWV-DELEG-REVIEW-WRITE",
                        path,
                        f"nodes[{node.id}].delegation_ids.{step_id}",
                        "review and final nodes may reference only repository-read or external-read steps",
                    )
                )
            if node.kind == IMPLEMENTATION_KIND and node.status == "complete":
                if step.get("status") != "completed":
                    errors.append(
                        _e(
                            "TWV-DELEG-UNRESOLVED-DELEGATION",
                            path,
                            f"nodes[{node.id}].delegation_ids.{step_id}",
                            "a completed implementation node requires every referenced delegated step completed",
                        )
                    )
    for step in steps:
        parent = step.get("parent_node_id")
        step_id = step.get("id")
        if not isinstance(parent, str) or parent == UNAVAILABLE or not isinstance(step_id, str):
            continue
        if parent not in nodes_by_id:
            errors.append(
                _e(
                    "TWV-DELEG-ORPHAN-OWNER",
                    path,
                    f"steps[{step_id}].parent_node_id",
                    "parent_node_id must reference an existing graph node",
                )
            )
            continue
        if step_id not in referenced_by:
            errors.append(
                _e(
                    "TWV-DELEG-ORPHANED-STEP",
                    path,
                    f"steps[{step_id}].parent_node_id",
                    "a step owned by a graph node must be referenced by that node's delegation_ids",
                )
            )
    return sorted_errors(errors)
