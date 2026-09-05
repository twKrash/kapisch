from __future__ import annotations

import json
import re
from pathlib import Path

from .artifact_io import (
    ArtifactFailure,
    ArtifactFailureKind,
    load_toml_artifact,
)
from .errors import ValidationError
from .helpers import is_integer, non_empty_string, nonfinite_float_references, string_list
from .models import Manifest, State
from .vocabulary import (
    V4_CONTROLLER_VIEW_PATH,
    WORKFLOW_STATUS_VALUES,
    closed_string_error,
)

STATE = {
    "task_id",
    "source_plan",
    "base_revision",
    "current_revision",
    "workflow_status",
    "completed_node_ids",
    "running_node_ids",
    "ready_node_ids",
    "blocked_node_ids",
    "failed_node_ids",
    "latest_approving_review_path",
    "latest_approving_invocation_id",
    "current_fix_round",
    "max_fix_rounds",
    "next_action",
    "extensions",
    "controller_view_path",
    "controller_view_sha256",
}

def _e(c: str, p: Path, r: str, m: str) -> ValidationError:
    return ValidationError(c, str(p), r, m)


def _toml_load_error(
    path: Path, failure: ArtifactFailure, artifact_name: str
) -> ValidationError:
    if failure.kind is ArtifactFailureKind.UNREADABLE:
        return _e(
            "TWV-PARSE-UNREADABLE-ARTIFACT",
            path,
            "toml",
            f"{artifact_name} is unreadable",
        )
    if failure.kind is ArtifactFailureKind.NOT_REGULAR:
        return _e(
            "TWV-PARSE-UNREADABLE-ARTIFACT",
            path,
            "toml",
            f"{artifact_name} must be a regular file",
        )
    if failure.kind is ArtifactFailureKind.INVALID_UTF8:
        return _e(
            "TWV-PARSE-INVALID-UTF8",
            path,
            "toml",
            f"{artifact_name} must be valid UTF-8",
        )
    assert failure.kind is ArtifactFailureKind.MALFORMED_TOML
    return _e("TWV-PARSE-MALFORMED-TOML", path, "toml", failure.detail)


def parse_state(path: Path) -> tuple[State | None, list[ValidationError]]:
    raw, failure = load_toml_artifact(path)
    if failure is not None:
        if failure.kind is not ArtifactFailureKind.MISSING:
            return None, [_toml_load_error(path, failure, "persisted state")]
        return None, [
            _e(
                "TWV-PARSE-MISSING-ARTIFACT",
                path,
                path.name,
                "required state is missing",
            )
        ]
    assert raw is not None
    errors = [
        _e("TWV-SCHEMA-UNKNOWN-FIELD", path, key, "unknown normative field")
        for key in sorted(set(raw) - STATE)
    ]
    errors.extend(
        _e(
            "TWV-SCHEMA-NONFINITE-FLOAT",
            path,
            reference,
            "non-finite floats are not supported in durable snapshots",
        )
        for reference in nonfinite_float_references(raw)
    )
    extensions = raw.get("extensions")
    if extensions is not None and not isinstance(extensions, dict):
        errors.append(
            _e("TWV-SCHEMA-WRONG-SHAPE", path, "extensions", "must be a TOML table")
        )
    elif isinstance(extensions, dict):
        for namespace in sorted(extensions):
            if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", namespace):
                errors.append(
                    _e(
                        "TWV-SCHEMA-INVALID-EXTENSION",
                        path,
                        f"extensions.{namespace}",
                        "extension keys must be reverse-DNS namespaces",
                    )
                )
        if "controller_view_path" in raw or "controller_view_sha256" in raw:
            try:
                json.dumps(extensions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            except (TypeError, ValueError):
                errors.append(
                    _e(
                        "TWV-SCHEMA-INVALID-EXTENSION",
                        path,
                        "extensions",
                        "v4 extension values must use JSON-compatible scalar, array, and table values",
                    )
                )
    for key in STATE - {"extensions", "controller_view_path", "controller_view_sha256"}:
        if key not in raw:
            errors.append(
                _e("TWV-SCHEMA-MISSING-FIELD", path, key, "required field is missing")
            )
    if errors:
        return None, errors
    lists = {
        key: raw[key]
        for key in (
            "completed_node_ids",
            "running_node_ids",
            "ready_node_ids",
            "blocked_node_ids",
            "failed_node_ids",
        )
    }
    for key, values in lists.items():
        string_list(
            values,
            errors,
            _e(
                "TWV-SCHEMA-INVALID-NODE-LIST",
                path,
                key,
                "must be a sorted, unique array of non-empty strings",
            ),
            sorted_unique=True,
        )
    for key in (
        "task_id",
        "source_plan",
        "base_revision",
        "current_revision",
        "next_action",
    ):
        non_empty_string(
            raw.get(key),
            errors,
            _e("TWV-SCHEMA-WRONG-SHAPE", path, key, "must be a non-empty string"),
        )
    workflow_status_error = closed_string_error(
        raw["workflow_status"],
        WORKFLOW_STATUS_VALUES,
        path=str(path),
        reference="workflow_status",
    )
    if workflow_status_error is not None:
        errors.append(workflow_status_error)
    for key in ("latest_approving_review_path", "latest_approving_invocation_id"):
        non_empty_string(
            raw.get(key),
            errors,
            _e("TWV-SCHEMA-WRONG-SHAPE", path, key, "must be a non-empty string"),
        )
    for key in ("current_fix_round", "max_fix_rounds"):
        if not is_integer(raw.get(key)) or raw[key] < 0:
            errors.append(
                _e(
                    "TWV-SCHEMA-WRONG-SHAPE",
                    path,
                    key,
                    "must be a non-negative integer",
                )
            )
    if errors:
        return None, errors
    return State(
        str(raw["task_id"]),
        str(raw["current_revision"]),
        str(raw["workflow_status"]),
        tuple(raw["completed_node_ids"]),
        tuple(raw["running_node_ids"]),
        tuple(raw["ready_node_ids"]),
        tuple(raw["blocked_node_ids"]),
        tuple(raw["failed_node_ids"]),
        str(raw["next_action"]),
        raw,
        str(path),
        raw.get("controller_view_path"),
        raw.get("controller_view_sha256"),
    ), []


def validate_references(
    manifest: Manifest, state: State, task_dir: Path, contract_dir: Path
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    known = {n.id for n in manifest.nodes}
    nodes_by_id = {node.id: node for node in manifest.nodes}
    if len(known) != len(manifest.nodes):
        errors.append(
            _e(
                "TWV-REF-DUPLICATE-NODE-ID",
                Path(manifest.path),
                "nodes",
                "node IDs must be unique",
            )
        )
    sequences = [node.sequence for node in manifest.nodes]
    if len(set(sequences)) != len(sequences):
        errors.append(
            _e(
                "TWV-REF-DUPLICATE-NODE-SEQUENCE",
                Path(manifest.path),
                "nodes",
                "node sequences must be unique",
            )
        )
    for name in (
        "SKILL.md",
        "references/execution-graph.md",
        "references/resume.md",
        "references/review.md",
        "references/handoffs.md",
        "references/pressure-scenarios.md",
    ):
        if not (contract_dir / name).is_file():
            errors.append(
                _e(
                    "TWV-REF-MISSING-CONTRACT",
                    contract_dir,
                    name,
                    "required contract reference is missing",
                )
            )
    if state.task_id != manifest.task_id:
        errors.append(
            _e(
                "TWV-REF-STATE-MANIFEST-MISMATCH",
                task_dir / "03-state.toml",
                "task_id",
                "state and manifest task IDs differ",
            )
        )
    if state.raw["base_revision"] != manifest.base_revision:
        errors.append(
            _e(
                "TWV-REF-STATE-MANIFEST-MISMATCH",
                task_dir / "03-state.toml",
                "base_revision",
                "state and manifest base revisions differ",
            )
        )
    if state.raw["source_plan"] != manifest.source_plan:
        errors.append(
            _e(
                "TWV-REF-STATE-MANIFEST-MISMATCH",
                task_dir / "03-state.toml",
                "source_plan",
                "state and manifest source plans differ",
            )
        )
    if state.raw["max_fix_rounds"] != manifest.policies.get("max_fix_rounds", 1):
        errors.append(
            _e(
                "TWV-REF-STATE-MANIFEST-MISMATCH",
                task_dir / "03-state.toml",
                "max_fix_rounds",
                "state and manifest fix-round bounds differ",
            )
        )
    if state.raw["current_fix_round"] > state.raw["max_fix_rounds"]:
        errors.append(
            _e(
                "TWV-REF-INVALID-FIX-ROUND",
                task_dir / "03-state.toml",
                "current_fix_round",
                "current fix round exceeds the configured maximum",
            )
        )
    controller_view_fields = ("controller_view_path", "controller_view_sha256")
    if manifest.version == 4:
        for field in controller_view_fields:
            if field not in state.raw:
                errors.append(
                    _e(
                        "TWV-SCHEMA-MISSING-FIELD",
                        task_dir / "03-state.toml",
                        field,
                        "required version-4 state binding is missing",
                    )
                )
        if (
            "controller_view_path" in state.raw
            and state.raw["controller_view_path"] != V4_CONTROLLER_VIEW_PATH
        ):
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-VALUE",
                    task_dir / "03-state.toml",
                    "controller_view_path",
                    f"must be {V4_CONTROLLER_VIEW_PATH!r}",
                )
            )
        digest = state.raw.get("controller_view_sha256")
        if (
            digest is not None
            and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None)
        ):
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-DIGEST",
                    task_dir / "03-state.toml",
                    "controller_view_sha256",
                    "must be 64 lowercase hexadecimal characters",
                )
            )
    else:
        for field in controller_view_fields:
            if field in state.raw:
                errors.append(
                    _e(
                        "TWV-SCHEMA-UNSUPPORTED-V4-FIELD",
                        task_dir / "03-state.toml",
                        field,
                        "version-4-only state field on a legacy manifest",
                    )
                )
    for n in manifest.nodes:
        for dep in n.depends_on:
            if dep not in known:
                errors.append(
                    _e(
                        "TWV-REF-UNKNOWN-DEPENDENCY",
                        Path(manifest.path),
                        f"{n.id}->{dep}",
                        "dependency node does not exist",
                    )
                )
        for rel in filter(None, n.paths[:3]):
            if "\0" in rel:
                valid = False
            else:
                try:
                    root = task_dir.resolve()
                    target = (root / rel).resolve()
                    valid = root in target.parents and target.is_file()
                except (OSError, ValueError, RuntimeError):
                    valid = False
            if not valid:
                errors.append(
                    _e(
                        "TWV-REF-ARTIFACT",
                        Path(manifest.path),
                        f"{n.id}:{rel}",
                        "artifact must exist beneath task directory",
                    )
                )
    for ids, status in (
        (state.completed, "complete"),
        (state.running, "running"),
        (state.ready, "ready"),
        (state.blocked, "blocked"),
        (state.failed, "failed"),
    ):
        for node_id in ids:
            if node_id not in known:
                errors.append(
                    _e(
                        "TWV-REF-UNKNOWN-NODE",
                        task_dir / "03-state.toml",
                        node_id,
                        "state references an unknown node",
                    )
                )
            elif nodes_by_id[node_id].status != status:
                errors.append(
                    _e(
                        "TWV-REF-STATE-MANIFEST-MISMATCH",
                        task_dir / "03-state.toml",
                        node_id,
                        "state list disagrees with manifest status",
                    )
                )
    state_ids = (
        set(state.completed)
        | set(state.running)
        | set(state.ready)
        | set(state.blocked)
        | set(state.failed)
    )
    if sum(
        len(values)
        for values in (
            state.completed,
            state.running,
            state.ready,
            state.blocked,
            state.failed,
        )
    ) != len(state_ids):
        errors.append(
            _e(
                "TWV-REF-STATE-NODE-DUPLICATE",
                task_dir / "03-state.toml",
                "node lists",
                "a node may appear in only one state list",
            )
        )
    for node in manifest.nodes:
        if (
            node.status in {"complete", "running", "ready", "blocked", "failed"}
            and node.id not in state_ids
        ):
            errors.append(
                _e(
                    "TWV-REF-STATE-MANIFEST-MISMATCH",
                    task_dir / "03-state.toml",
                    node.id,
                    "manifest status is absent from authoritative state",
                )
            )
    for node in manifest.nodes:
        if node.status != "complete":
            continue
        revision = node.raw.get("revision")
        evidence = node.raw.get("verification_evidence")
        if (
            not isinstance(revision, dict)
            or not revision.get("base")
            or not revision.get("head")
        ):
            errors.append(
                _e(
                    "TWV-LIFECYCLE-MISSING-COMPLETION-EVIDENCE",
                    Path(manifest.path),
                    node.id,
                    "completed nodes require base and head revision evidence",
                )
            )
        if not isinstance(evidence, list) or not evidence:
            errors.append(
                _e(
                    "TWV-LIFECYCLE-MISSING-COMPLETION-EVIDENCE",
                    Path(manifest.path),
                    node.id,
                    "completed nodes require verification evidence",
                )
            )
    graph = {n.id: n.depends_on for n in manifest.nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(
                _e(
                    "TWV-REF-DEPENDENCY-CYCLE",
                    Path(manifest.path),
                    node,
                    "dependency cycle detected",
                )
            )
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in sorted(graph[node]):
            if dep in graph:
                visit(dep)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return errors
