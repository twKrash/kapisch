from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

from .advisory import STATE_PATH, repository_root, validate_advisory
from .artifact_io import load_toml_artifact
from .errors import ValidationError, sorted_errors
from .path_atoms import validate_relative_posix_path

PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "status",
        "approval_source",
        "source_revision",
        "decision_dependencies_reviewed",
        "architecture_bindings",
        "decision_dependencies",
    }
)
BINDING_FIELDS = frozenset({"snapshot_id", "path", "digest"})
DEPENDENCY_FIELDS = frozenset(
    {"decision_id", "kind", "path", "digest", "snapshot_id"}
)
RELATION_FIELDS = frozenset({"kind", "target_path", "target_digest", "decision_id"})
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
PLAN_PATH_RE = re.compile(r"plans/([0-9a-f]{64})\.md\Z")


def _error(code: str, path: Path, field: str, message: str) -> ValidationError:
    return ValidationError(code, str(path), field, message)


def _closed(
    value: dict[str, object], allowed: frozenset[str], path: Path, prefix: str
) -> list[ValidationError]:
    return [
        _error(
            "ADV-PLAN-SCHEMA",
            path,
            f"{prefix}.{key}" if prefix else key,
            "unknown field is not permitted",
        )
        for key in sorted(value.keys() - allowed)
    ]


def _safe_file(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str):
        return None
    try:
        validate_relative_posix_path(relative)
        resolved_root = root.resolve()
        resolved = (resolved_root / relative).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if resolved_root not in resolved.parents or not resolved.is_file():
        return None
    return resolved


def _dependency_key(record: dict[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(record.get("decision_id", "")),
        str(record.get("kind", "")),
        str(record.get("path", "")),
        str(record.get("digest", "")),
        str(record.get("snapshot_id", "")),
    )


def _record_accepted_snapshot(
    project_root: Path,
    relative: object,
    snapshot_id: object,
    digest: object,
    errors: list[ValidationError],
    field: str,
) -> tuple[Path, dict[str, object]] | None:
    plan_path = project_root / "00-advisory.toml"
    snapshot_path = _safe_file(project_root, relative)
    if snapshot_path is None:
        errors.append(_error("ADV-AUTHORITY-MISSING", plan_path, field, "accepted architecture reference must exist inside repository"))
        return None
    if not isinstance(snapshot_id, str) or not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
        errors.append(_error("ADV-AUTHORITY-IDENTITY", snapshot_path, field, "snapshot ID and 64-character digest are required"))
        return None
    actual_digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if actual_digest != digest or not snapshot_path.name.endswith(f"-{digest}.toml"):
        errors.append(_error("ADV-AUTHORITY-STALE", snapshot_path, field, "accepted architecture bytes differ from bound digest"))
        return None
    snapshot, failure = load_toml_artifact(snapshot_path)
    if failure is not None or snapshot is None:
        errors.append(_error("ADV-AUTHORITY-INVALID", snapshot_path, field, "accepted architecture snapshot is invalid TOML"))
        return None
    if snapshot.get("status") != "accepted" or snapshot.get("snapshot_id") != snapshot_id:
        errors.append(_error("ADV-AUTHORITY-IDENTITY", snapshot_path, field, "snapshot identity or accepted status does not match"))
        return None
    owner_dir = snapshot_path.parent.parent
    owner_state_path = owner_dir / STATE_PATH
    owner_state, state_failure = load_toml_artifact(owner_state_path)
    if state_failure is not None or owner_state is None:
        errors.append(_error("ADV-AUTHORITY-INVALID", owner_state_path, "state", "owning advisory state is missing or invalid"))
        return None
    expected_path = snapshot_path.relative_to(owner_dir).as_posix()
    accepted = owner_state.get("accepted_architectures")
    if not isinstance(accepted, list) or not any(
        isinstance(entry, dict)
        and entry.get("id") == snapshot_id
        and entry.get("path") == expected_path
        and entry.get("digest") == digest
        for entry in accepted
    ):
        errors.append(_error("ADV-AUTHORITY-UNACCEPTED", snapshot_path, field, "snapshot is not listed as accepted by its owning run"))
        return None
    owner_errors = validate_advisory(owner_dir)
    if owner_errors:
        errors.extend(owner_errors)
        return None
    return snapshot_path, snapshot


def _is_superseded(
    project_root: Path, target_path: str, target_digest: str, errors: list[ValidationError]
) -> bool:
    runs_dir = project_root / ".kapisch" / "runs"
    if not runs_dir.is_dir():
        return False
    # ponytail: scan accepted run snapshots per validation; add an index only if run count makes this costly.
    validation_cache: dict[Path, list[ValidationError]] = {}
    reported_invalid_owners: set[Path] = set()
    for candidate in sorted(runs_dir.glob("*/architectures/*.toml")):
        try:
            candidate.resolve(strict=True).relative_to(runs_dir.resolve())
        except (OSError, RuntimeError, ValueError):
            continue
        owner_dir = candidate.parent.parent
        owner_state, state_failure = load_toml_artifact(owner_dir / STATE_PATH)
        if state_failure is not None or not isinstance(owner_state, dict):
            continue
        relative = candidate.relative_to(owner_dir).as_posix()
        accepted = owner_state.get("accepted_architectures")
        if not isinstance(accepted, list) or not any(
            isinstance(entry, dict) and entry.get("path") == relative for entry in accepted
        ):
            continue
        if owner_dir not in validation_cache:
            validation_cache[owner_dir] = validate_advisory(owner_dir)
        owner_errors = validation_cache[owner_dir]
        if owner_errors:
            if owner_dir not in reported_invalid_owners:
                errors.extend(owner_errors)
                reported_invalid_owners.add(owner_dir)
            continue
        candidate_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        snapshot, failure = load_toml_artifact(candidate)
        if failure is not None or snapshot is None or snapshot.get("status") != "accepted":
            errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "snapshot", "accepted architecture snapshot is invalid"))
            continue
        if not candidate.name.endswith(f"-{candidate_digest}.toml"):
            errors.append(_error("ADV-AUTHORITY-STALE", candidate, "snapshot", "accepted architecture bytes differ from their content-addressed filename"))
            continue
        relations = snapshot.get("relationships", [])
        if not isinstance(relations, list):
            errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships", "must be an array"))
            continue
        for relation in relations:
            if not isinstance(relation, dict):
                errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships", "relationship must be a table"))
                continue
            if set(relation) != RELATION_FIELDS:
                errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships", "relationship must contain kind, target_path, target_digest, and decision_id only"))
                continue
            if relation.get("kind") not in {"amends", "supersedes"}:
                errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships.kind", "must be amends or supersedes"))
                continue
            snapshot_decisions = snapshot.get("decisions")
            decision_ids = {
                item.get("id")
                for item in snapshot_decisions
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            } if isinstance(snapshot_decisions, list) else set()
            if not isinstance(relation.get("decision_id"), str) or relation["decision_id"] not in decision_ids:
                errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships.decision_id", "must reference a decision in the accepted snapshot"))
                continue
            if not isinstance(relation.get("target_path"), str) or not relation["target_path"].strip():
                errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships.target_path", "must be non-empty text"))
                continue
            if not isinstance(relation.get("target_digest"), str) or DIGEST_RE.fullmatch(relation["target_digest"]) is None:
                errors.append(_error("ADV-AUTHORITY-INVALID", candidate, "relationships.target_digest", "must be a SHA-256 digest"))
                continue
            if relation.get("target_path") == target_path and relation.get("target_digest") == target_digest:
                return True
    return False


def _validate_dependency(
    record: object,
    project_root: Path,
    snapshot_decisions: set[str],
    errors: list[ValidationError],
    field: str,
) -> tuple[str, str, str, str, str] | None:
    if not isinstance(record, dict):
        errors.append(_error("ADV-PLAN-DEPENDENCY", project_root, field, "dependency must be a table"))
        return None
    errors.extend(_closed(record, DEPENDENCY_FIELDS, project_root, field))
    decision_id, kind, relative, digest = (
        record.get("decision_id"),
        record.get("kind"),
        record.get("path"),
        record.get("digest"),
    )
    if not isinstance(decision_id, str) or decision_id not in snapshot_decisions:
        errors.append(_error("ADV-PLAN-DEPENDENCY", project_root, f"{field}.decision_id", "must reference a decision in a bound accepted architecture"))
    if kind not in {"repository-file", "accepted-architecture"}:
        errors.append(_error("ADV-PLAN-DEPENDENCY", project_root, f"{field}.kind", "must be repository-file or accepted-architecture"))
    if not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
        errors.append(_error("ADV-PLAN-DEPENDENCY", project_root, f"{field}.digest", "must be 64 lowercase hexadecimal characters"))
        return None
    path = _safe_file(project_root, relative)
    if path is None:
        errors.append(_error("ADV-AUTHORITY-MISSING", project_root, f"{field}.path", "decision dependency must exist inside repository"))
        return None
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        errors.append(_error("ADV-AUTHORITY-STALE", path, field, "decision dependency bytes differ from bound digest"))
    if kind == "accepted-architecture":
        snapshot_id = record.get("snapshot_id")
        if not isinstance(snapshot_id, str):
            errors.append(_error("ADV-PLAN-DEPENDENCY", path, f"{field}.snapshot_id", "required for accepted-architecture dependency"))
        else:
            _record_accepted_snapshot(project_root, relative, snapshot_id, digest, errors, field)
            if _is_superseded(project_root, str(relative), digest, errors):
                errors.append(_error("ADV-AUTHORITY-STALE", path, field, "decision dependency was amended or superseded"))
    elif "snapshot_id" in record:
        errors.append(_error("ADV-PLAN-DEPENDENCY", path, f"{field}.snapshot_id", "only accepted-architecture dependencies have snapshot_id"))
    return _dependency_key(record)


def validate_plan_authority(
    task_dir: Path, source_plan: str, advisory_task_dir: Path | None = None
) -> list[ValidationError]:
    """Validate content-addressed approval plan and its accepted decision inputs."""
    task_dir = Path(task_dir)
    plan_path = _safe_file(task_dir, source_plan)
    state, state_failure = load_toml_artifact(task_dir / STATE_PATH)
    has_accepted_architecture = (
        state_failure is None
        and state is not None
        and isinstance(state.get("accepted_architectures"), list)
        and bool(state["accepted_architectures"])
    )
    if not source_plan.startswith("plans/"):
        if has_accepted_architecture:
            return [
                _error(
                    "ADV-PLAN-AUTHORITY-MISSING",
                    task_dir / STATE_PATH,
                    "source_plan",
                    "architecture-derived execution requires a content-addressed approved plan",
                )
            ]
        return []
    if plan_path is None:
        return [_error("ADV-PLAN-MISSING", task_dir / STATE_PATH, "source_plan", "approved plan artifact is missing or unsafe")]
    match = PLAN_PATH_RE.fullmatch(source_plan)
    errors: list[ValidationError] = []
    if match is None:
        return [_error("ADV-PLAN-PATH", plan_path, "source_plan", "approved plans must use plans/<sha256>.md")]
    plan_digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if plan_digest != match.group(1):
        return [_error("ADV-PLAN-DIGEST", plan_path, "source_plan", "plan bytes differ from content-addressed filename")]
    try:
        data = plan_path.read_bytes()
        text = data.decode("utf-8")
        if not text.startswith("+++\n"):
            raise ValueError("frontmatter opening marker missing")
        end = data.find(b"\n+++\n", 4)
        if end < 0:
            raise ValueError("frontmatter closing marker missing")
        frontmatter = tomllib.loads(data[4 : end + 1].decode("utf-8"))
    except (UnicodeError, ValueError, tomllib.TOMLDecodeError, RecursionError):
        return [_error("ADV-PLAN-PARSE", plan_path, "frontmatter", "plan requires valid UTF-8 TOML frontmatter")]
    errors.extend(_closed(frontmatter, PLAN_FIELDS, plan_path, ""))
    for required in PLAN_FIELDS:
        if required not in frontmatter:
            errors.append(_error("ADV-PLAN-SCHEMA", plan_path, required, "required field is missing"))
    if frontmatter.get("schema_version") != 1 or isinstance(frontmatter.get("schema_version"), bool):
        errors.append(_error("ADV-PLAN-SCHEMA", plan_path, "schema_version", "must equal 1"))
    if frontmatter.get("task_id") != task_dir.name:
        errors.append(_error("ADV-PLAN-IDENTITY", plan_path, "task_id", "must match run directory"))
    if frontmatter.get("status") != "approved" or frontmatter.get("approval_source") != "human":
        errors.append(_error("ADV-PLAN-APPROVAL", plan_path, "status", "plan must record human approval"))
    reviewed = frontmatter.get("decision_dependencies_reviewed")
    if not isinstance(reviewed, bool) or not reviewed:
        errors.append(_error("ADV-PLAN-REVIEW", plan_path, "decision_dependencies_reviewed", "plan approval requires review of candidate decision dependencies"))
    if not isinstance(frontmatter.get("source_revision"), str) or not frontmatter["source_revision"].strip():
        errors.append(_error("ADV-PLAN-SCHEMA", plan_path, "source_revision", "must be a non-empty source revision"))

    project_root = repository_root(task_dir)
    if project_root is None:
        return list(sorted_errors(errors + [_error("ADV-PLAN-ROOT", plan_path, "task_dir", "run must be beneath <repository>/.kapisch/runs/<task-id>")]))
    expected_advisory_dir = advisory_task_dir
    if expected_advisory_dir is None and (task_dir / STATE_PATH).is_file():
        expected_advisory_dir = task_dir.resolve()
    elif expected_advisory_dir is not None:
        expected_advisory_dir = Path(expected_advisory_dir).resolve()
    if expected_advisory_dir is not None and repository_root(expected_advisory_dir) != project_root:
        errors.append(_error("ADV-PLAN-BINDINGS", plan_path, "architecture_bindings", "advisory source must be a run in the same repository"))

    bindings = frontmatter.get("architecture_bindings")
    if not isinstance(bindings, list):
        errors.append(_error("ADV-PLAN-BINDINGS", plan_path, "architecture_bindings", "must be an array of accepted snapshot references"))
        bindings = []
    elif expected_advisory_dir is not None and not bindings:
        errors.append(_error("ADV-PLAN-BINDINGS", plan_path, "architecture_bindings", "promoted advisory requires at least one accepted architecture binding"))
    expected_dependencies: set[tuple[str, str, str, str, str]] = set()
    binding_ids: set[str] = set()
    binding_paths: set[str] = set()
    for index, binding in enumerate(bindings):
        field = f"architecture_bindings[{index}]"
        if not isinstance(binding, dict):
            errors.append(_error("ADV-PLAN-BINDINGS", plan_path, field, "must be a table"))
            continue
        errors.extend(_closed(binding, BINDING_FIELDS, plan_path, field))
        snapshot_id = binding.get("snapshot_id")
        relative = binding.get("path")
        digest = binding.get("digest")
        if not isinstance(snapshot_id, str) or not snapshot_id or not isinstance(relative, str):
            errors.append(_error("ADV-PLAN-BINDINGS", plan_path, field, "snapshot_id and path are required"))
            continue
        if snapshot_id in binding_ids or relative in binding_paths:
            errors.append(_error("ADV-PLAN-BINDINGS", plan_path, field, "architecture bindings must be unique"))
        binding_ids.add(snapshot_id)
        binding_paths.add(relative)
        accepted = _record_accepted_snapshot(project_root, relative, snapshot_id, digest, errors, field)
        if accepted is None:
            continue
        snapshot_path, snapshot = accepted
        if expected_advisory_dir is not None and snapshot_path.parent.parent.resolve() != expected_advisory_dir:
            errors.append(_error("ADV-PLAN-BINDINGS", plan_path, field, "snapshot must belong to the advisory run being promoted"))
            continue
        if _is_superseded(project_root, relative, str(digest), errors):
            errors.append(_error("ADV-AUTHORITY-STALE", snapshot_path, field, "bound architecture was amended or superseded"))
        decisions = snapshot.get("decisions")
        decision_ids: set[str] = set()
        if isinstance(decisions, list):
            for decision in decisions:
                if isinstance(decision, dict) and isinstance(decision.get("id"), str):
                    decision_ids.add(decision["id"])
        dependencies = snapshot.get("dependencies", [])
        if not isinstance(dependencies, list):
            errors.append(_error("ADV-PLAN-DEPENDENCY", snapshot_path, "dependencies", "must be an array"))
            continue
        for dep_index, dependency in enumerate(dependencies):
            key = _validate_dependency(
                dependency,
                project_root,
                decision_ids,
                errors,
                f"{field}.dependencies[{dep_index}]",
            )
            if key is not None:
                expected_dependencies.add(key)

    plan_dependencies = frontmatter.get("decision_dependencies")
    if not isinstance(plan_dependencies, list):
        errors.append(_error("ADV-PLAN-DEPENDENCY", plan_path, "decision_dependencies", "must be an array"))
        plan_dependencies = []
    all_decision_ids: set[str] = set()
    for binding in bindings:
        if isinstance(binding, dict):
            accepted = _record_accepted_snapshot(
                project_root,
                binding.get("path"),
                binding.get("snapshot_id"),
                binding.get("digest"),
                errors,
                "architecture_bindings",
            )
            if accepted is not None:
                decisions = accepted[1].get("decisions")
                if isinstance(decisions, list):
                    for decision in decisions:
                        if isinstance(decision, dict) and isinstance(decision.get("id"), str):
                            all_decision_ids.add(decision["id"])
    actual_dependencies: set[tuple[str, str, str, str, str]] = set()
    for index, dependency in enumerate(plan_dependencies):
        key = _validate_dependency(
            dependency,
            project_root,
            all_decision_ids,
            errors,
            f"decision_dependencies[{index}]",
        )
        if key is not None:
            if key in actual_dependencies:
                errors.append(_error("ADV-PLAN-DEPENDENCY", plan_path, f"decision_dependencies[{index}]", "duplicate dependency"))
            actual_dependencies.add(key)
    if actual_dependencies != expected_dependencies:
        errors.append(_error("ADV-PLAN-DEPENDENCY-MISMATCH", plan_path, "decision_dependencies", "plan dependencies must exactly match bound architecture dependencies"))
    return list(sorted_errors(errors))
