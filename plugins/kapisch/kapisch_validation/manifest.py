from __future__ import annotations

import re
from pathlib import Path

from .artifact_io import ArtifactFailure, ArtifactFailureKind, load_toml_artifact
from .errors import ValidationError, sorted_errors
from .helpers import is_integer, non_empty_string, nonfinite_float_references, string_list
from .models import Manifest, Node, ParseResult
from .path_atoms import is_portable_filename_atom
from .vocabulary import (
    ASSIGNMENT_VALUES,
    MANIFEST_VERSION_VALUES,
    NODE_ROUTING_VALUES,
    POLICY_VALUES,
    RUNTIME_RECORD_STATUS_VALUES,
    UNAVAILABLE_OUTCOME_PATH,
    V4_CONTROLLER_VIEW_PATH,
    closed_string_error,
)

ROOT = {
    "version",
    "task_id",
    "source_plan",
    "roadmap_item",
    "base_revision",
    "policies",
    "nodes",
    "waves",
    "extensions",
    "controller_view",
}
POLICIES = {
    "execution",
    "executor",
    "dispatch",
    "model_tier",
    "batching",
    "parallelism",
    "max_parallel_agents",
    "commit",
    "push",
    "fix_policy",
    "max_fix_rounds",
    "ecosystem_routing",
}
NODE = {
    "id",
    "sequence",
    "title",
    "kind",
    "risk",
    "status",
    "depends_on",
    "brief",
    "context",
    "report",
    "reviewer_invocation",
    "reads",
    "writes",
    "shared_resources",
    "verification",
    "context_refs",
    "executor_class",
    "model_tier",
    "batching",
    "assignment",
    "batch",
    "verification_evidence",
    "blocker",
    "revision",
    "review_scope",
    "delegation_ids",
    "extensions",
}
REVISION = {"base", "head"}
SCOPE = {"terminal_node_ids", "integrated_wave_ids", "wave_terminal_dependencies"}
ASSIGNMENT = {
    "id",
    "schema_version",
    "execution_class",
    "reason_codes",
    "source_revision",
    "context_refs",
    "context_fingerprint",
    "scope_fingerprint",
    "attempts",
    "escalations",
}
ASSIGNMENT_REQUIRED = ASSIGNMENT - {"context_fingerprint", "scope_fingerprint"}
BATCH = {"id", "member_node_ids", "member_assignment_ids", "member_outcomes", "outcome"}
ATTEMPT = {
    "id",
    "source_revision",
    "context_scope_ref",
    "status",
    "verification",
    "outcome_path",
}
ESCALATION = {
    "id",
    "trigger",
    "prior_assignment_id",
    "new_assignment_id",
    "prior_attempt_id",
    "new_attempt_id",
    "source_revision",
    "attempt_revision",
    "context_refs",
}
VERIFICATION_EVIDENCE = {
    "id",
    "check",
    "result",
    "evidence_ref",
    "output_sha256",
    "revision",
}
V1 = {
    "execution": "sequential",
    "executor": "implementer",
    "dispatch": "single",
    "model_tier": "standard",
    "batching": "off",
    "parallelism": "off",
    "max_parallel_agents": 1,
    "max_fix_rounds": 1,
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


def _closed(
    data: object, allowed: set[str], p: Path, r: str, errors: list[ValidationError]
) -> None:
    if not isinstance(data, dict):
        errors.append(_e("TWV-SCHEMA-WRONG-SHAPE", p, r, "must be a TOML table"))
        return
    for key in sorted(set(data) - allowed):
        errors.append(
            _e("TWV-SCHEMA-UNKNOWN-FIELD", p, f"{r}.{key}", "unknown normative field")
        )


def _extensions(
    data: object, path: Path, reference: str, errors: list[ValidationError]
) -> None:
    if data is None:
        return
    if not isinstance(data, dict):
        errors.append(_e("TWV-SCHEMA-WRONG-SHAPE", path, reference, "must be a table"))
        return
    for namespace in sorted(data):
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", namespace):
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-EXTENSION",
                    path,
                    f"{reference}.{namespace}",
                    "extension keys must be reverse-DNS namespaces",
                )
            )


def parse_manifest(path: Path) -> ParseResult:
    errors: list[ValidationError] = []
    raw, failure = load_toml_artifact(path)
    if failure is not None:
        if failure.kind is not ArtifactFailureKind.MISSING:
            return ParseResult(
                None,
                sorted_errors([_toml_load_error(path, failure, "task manifest")]),
            )
        legacy = path.with_suffix(".yaml")
        code = (
            "TWV-PARSE-UNSUPPORTED-LEGACY-YAML"
            if legacy.is_file()
            else "TWV-PARSE-MISSING-ARTIFACT"
        )
        target = legacy if legacy.is_file() else path
        message = (
            "legacy YAML cannot resume; start a fresh workflow or revision-bound review"
            if legacy.is_file()
            else "required manifest is missing"
        )
        return ParseResult(
            None, sorted_errors([_e(code, target, target.name, message)])
        )
    assert raw is not None
    for reference in nonfinite_float_references(raw):
        errors.append(
            _e(
                "TWV-SCHEMA-NONFINITE-FLOAT",
                path,
                reference,
                "non-finite floats are not supported in durable snapshots",
            )
        )
    _closed(raw, ROOT, path, "root", errors)
    _extensions(raw.get("extensions"), path, "extensions", errors)
    _closed(raw.get("policies"), POLICIES, path, "policies", errors)
    version = raw.get("version")
    if not is_integer(version) or version not in MANIFEST_VERSION_VALUES:
        errors.append(
            _e(
                "TWV-SCHEMA-INVALID-VERSION",
                path,
                "version",
                "must be integer 1, 2, 3, or 4",
            )
        )
    required_root_fields = ["task_id", "source_plan", "base_revision", "nodes"]
    if version == 4:
        required_root_fields.append("controller_view")
    for key in required_root_fields:
        if key not in raw:
            errors.append(
                _e("TWV-SCHEMA-MISSING-FIELD", path, key, "required field is missing")
            )
    for key in (
        "task_id",
        "source_plan",
        "base_revision",
        "roadmap_item",
        "controller_view",
    ):
        if key in raw:
            non_empty_string(
                raw[key],
                errors,
                _e("TWV-SCHEMA-WRONG-SHAPE", path, key, "must be a non-empty string"),
            )
    if (
        version == 4
        and "controller_view" in raw
        and raw["controller_view"] != V4_CONTROLLER_VIEW_PATH
    ):
        errors.append(
            _e(
                "TWV-SCHEMA-INVALID-VALUE",
                path,
                "controller_view",
                f"must be {V4_CONTROLLER_VIEW_PATH!r}",
            )
        )
    if version in (1, 2, 3) and "controller_view" in raw:
        errors.append(
            _e(
                "TWV-SCHEMA-UNSUPPORTED-V4-FIELD",
                path,
                "controller_view",
                "version-4-only root field on a legacy manifest",
            )
        )
    policies = (
        dict(raw.get("policies", {})) if isinstance(raw.get("policies"), dict) else {}
    )
    if version == 1:
        for key, value in V1.items():
            policies.setdefault(key, value)
    if version == 2:
        for key in POLICIES - {"ecosystem_routing"}:
            if key not in policies:
                errors.append(
                    _e(
                        "TWV-SCHEMA-MISSING-FIELD",
                        path,
                        f"policies.{key}",
                        "required version-2 policy is missing",
                    )
                )
    if version in (3, 4):
        for key in POLICIES:
            if key not in policies:
                errors.append(
                    _e(
                        "TWV-SCHEMA-MISSING-FIELD",
                        path,
                        f"policies.{key}",
                        "required version-3 policy is missing",
                    )
                )
    if version in (1, 2) and "ecosystem_routing" in policies:
        errors.append(
            _e(
                "TWV-SCHEMA-UNSUPPORTED-V3-FIELD",
                path,
                "policies.ecosystem_routing",
                "version-3-only policy on a version-1 or version-2 manifest",
            )
        )
    for key, value in policies.items():
        reference = f"policies.{key}"
        if key == "max_parallel_agents":
            if not is_integer(value):
                errors.append(
                    _e("TWV-SCHEMA-WRONG-SHAPE", path, reference, "must be an integer")
                )
        elif key == "max_fix_rounds":
            if not is_integer(value) or value < 0:
                errors.append(
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        reference,
                        "must be a non-negative integer",
                    )
                )
        elif key == "parallelism":
            if not isinstance(value, str):
                error = closed_string_error(
                    value,
                    POLICY_VALUES[key],
                    path=str(path),
                    reference=reference,
                )
                assert error is not None
                errors.append(error)
        elif key == "ecosystem_routing" and version in (1, 2):
            pass
        elif key in POLICY_VALUES:
            error = closed_string_error(
                value,
                POLICY_VALUES[key],
                path=str(path),
                reference=reference,
            )
            if error is not None:
                errors.append(error)
    parallelism = policies.get("parallelism")
    max_parallel_agents = policies.get("max_parallel_agents")
    unsupported_wave_fields = (
        (
            "policies.parallelism",
            parallelism not in POLICY_VALUES["parallelism"],
            f"unsupported value {parallelism!r}; supported values: 'off'; "
            "operational waves are unsupported",
        ),
        (
            "policies.max_parallel_agents",
            max_parallel_agents != 1,
            f"unsupported value {max_parallel_agents!r}; supported value: 1; "
            "operational waves are unsupported",
        ),
        (
            "root.waves",
            "waves" in raw,
            "operational waves are unsupported",
        ),
    )
    for reference, unsupported, message in unsupported_wave_fields:
        if not unsupported:
            continue
        errors.append(
            _e(
                "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
                path,
                reference,
                message,
            )
        )
    validated_nodes: list[dict[str, object]] = []
    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, list):
        errors.append(
            _e("TWV-SCHEMA-WRONG-SHAPE", path, "nodes", "must be an array of tables")
        )
        raw_nodes = []
    for i, n in enumerate(raw_nodes):
        ref = f"nodes[{i}]"
        _closed(n, NODE, path, ref, errors)
        if not isinstance(n, dict):
            continue
        for key in (
            "id",
            "sequence",
            "kind",
            "status",
            "depends_on",
            "brief",
            "context",
            "report",
        ):
            if key not in n:
                errors.append(
                    _e(
                        "TWV-SCHEMA-MISSING-FIELD",
                        path,
                        f"{ref}.{key}",
                        "required node field is missing",
                    )
                )
        for key, supported in NODE_ROUTING_VALUES.items():
            if key not in n:
                continue
            error = closed_string_error(
                n[key],
                supported,
                path=str(path),
                reference=f"{ref}.{key}",
            )
            if error is not None:
                errors.append(error)
        for key in ("title", "risk"):
            if key in n:
                non_empty_string(
                    n[key],
                    errors,
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        f"{ref}.{key}",
                        "must be a non-empty string",
                    ),
                )
        executor_class = n.get("executor_class")
        model_tier = n.get("model_tier")
        is_implementation = n.get("kind") not in {"review", "final", "research"}
        if executor_class == "reviewer" and is_implementation:
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-ROUTING",
                    path,
                    f"{ref}.executor_class",
                    "reviewer is valid only for review or final nodes",
                )
            )
        if executor_class == "reviewer" and model_tier != "high":
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-ROUTING",
                    path,
                    f"{ref}.model_tier",
                    "reviewer requires model_tier='high'",
                )
            )
        if executor_class == "researcher" and is_implementation:
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-ROUTING",
                    path,
                    f"{ref}.executor_class",
                    "researcher is advisory and cannot be an implementation node",
                )
            )
        is_review_or_final = n.get("kind") in {"review", "final"}
        review_routing_fields = ("executor_class", "model_tier", "batching")
        if is_review_or_final and any(field in n for field in review_routing_fields):
            expected_routing = {
                "executor_class": "reviewer",
                "model_tier": "high",
                "batching": "off",
            }
            if any(n.get(field) != value for field, value in expected_routing.items()):
                errors.append(
                    _e(
                        "TWV-SCHEMA-INVALID-ROUTING",
                        path,
                        ref,
                        "review and final nodes require executor_class='reviewer', "
                        "model_tier='high', and batching='off'",
                    )
                )
        if (
            is_implementation
            and policies.get("dispatch") == "single"
            and (executor_class is not None or model_tier is not None)
            and (
            executor_class != "implementer" or model_tier != "standard"
            )
        ):
            errors.append(
                _e(
                    "TWV-SCHEMA-INVALID-ROUTING",
                    path,
                    ref,
                    "single dispatch requires implementation nodes to use "
                    "executor_class='implementer' and model_tier='standard'",
                )
            )
        for key in (
            "id",
            "kind",
            "status",
            "brief",
            "context",
            "report",
            "reviewer_invocation",
        ):
            if key in n:
                non_empty_string(
                    n[key],
                    errors,
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        f"{ref}.{key}",
                        "must be a non-empty string",
                    ),
                )
        if "sequence" in n and (not is_integer(n["sequence"]) or n["sequence"] < 0):
            errors.append(
                _e(
                    "TWV-SCHEMA-WRONG-SHAPE",
                    path,
                    f"{ref}.sequence",
                    "must be a non-negative integer",
                )
            )
        if "depends_on" in n:
            valid_dependencies = string_list(
                n["depends_on"],
                errors,
                _e(
                    "TWV-SCHEMA-WRONG-SHAPE",
                    path,
                    f"{ref}.depends_on",
                    "must be an array of unique non-empty strings",
                ),
            )
            if valid_dependencies and len(n["depends_on"]) != len(set(n["depends_on"])):
                errors.append(
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        f"{ref}.depends_on",
                        "must be an array of unique non-empty strings",
                    )
                )
        for key in (
            "reads",
            "writes",
            "shared_resources",
            "verification",
            "context_refs",
        ):
            if key in n:
                string_list(
                    n[key],
                    errors,
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        f"{ref}.{key}",
                        "must be an array of non-empty strings",
                    ),
                )
        if "delegation_ids" in n:
            valid_ids = string_list(
                n["delegation_ids"],
                errors,
                _e(
                    "TWV-SCHEMA-WRONG-SHAPE",
                    path,
                    f"{ref}.delegation_ids",
                    "must be an array of unique non-empty strings",
                ),
            )
            if valid_ids and len(n["delegation_ids"]) != len(set(n["delegation_ids"])):
                errors.append(
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        f"{ref}.delegation_ids",
                        "must be an array of unique non-empty strings",
                    )
                )
        if version in (1, 2) and "delegation_ids" in n:
            errors.append(
                _e(
                    "TWV-SCHEMA-UNSUPPORTED-V3-FIELD",
                    path,
                    f"{ref}.delegation_ids",
                    "version-3-only node field on a version-1 or version-2 manifest",
                )
            )
        if version in (3, 4) and "delegation_ids" not in n:
            errors.append(
                _e(
                    "TWV-SCHEMA-MISSING-FIELD",
                    path,
                    f"{ref}.delegation_ids",
                    "required version-3 node field is missing",
                )
            )
        for key, allowed in (("revision", REVISION), ("review_scope", SCOPE)):
            if key in n:
                _closed(n[key], allowed, path, f"{ref}.{key}", errors)
        revision = n.get("revision")
        if isinstance(revision, dict):
            for key in ("base", "head"):
                if key in revision:
                    non_empty_string(
                        revision[key],
                        errors,
                        _e(
                            "TWV-SCHEMA-WRONG-SHAPE",
                            path,
                            f"{ref}.revision.{key}",
                            "must be a non-empty string",
                        ),
                    )
        scope_value = n.get("review_scope")
        if isinstance(scope_value, dict):
            for key in SCOPE:
                if key in scope_value:
                    string_list(
                        scope_value[key],
                        errors,
                        _e(
                            "TWV-SCHEMA-WRONG-SHAPE",
                            path,
                            f"{ref}.review_scope.{key}",
                            "must be a sorted, unique array of non-empty strings",
                        ),
                        sorted_unique=True,
                    )
        for key, allowed in (("assignment", ASSIGNMENT), ("batch", BATCH)):
            if key in n:
                _closed(n[key], allowed, path, f"{ref}.{key}", errors)
                if isinstance(n[key], dict):
                    required_fields = ASSIGNMENT_REQUIRED if key == "assignment" else allowed
                    for required in required_fields:
                        if required not in n[key]:
                            errors.append(
                                _e(
                                    "TWV-SCHEMA-MISSING-FIELD",
                                    path,
                                    f"{ref}.{key}.{required}",
                                    "required runtime binding field is missing",
                                )
                            )
        for key in ("assignment", "batch"):
            nested = n.get(key)
            if isinstance(nested, dict):
                for field, value in nested.items():
                    nested_ref = f"{ref}.{key}.{field}"
                    if field == "schema_version":
                        if not is_integer(value):
                            errors.append(
                                _e(
                                    "TWV-SCHEMA-WRONG-SHAPE",
                                    path,
                                    nested_ref,
                                    "must be an integer",
                                )
                            )
                    elif field in ASSIGNMENT_VALUES:
                        error = closed_string_error(
                            value,
                            ASSIGNMENT_VALUES[field],
                            path=str(path),
                            reference=nested_ref,
                        )
                        if error is not None:
                            errors.append(error)
                    elif field in {
                        "reason_codes",
                        "context_refs",
                        "member_node_ids",
                        "member_assignment_ids",
                        "member_outcomes",
                    }:
                        string_list(
                            value,
                            errors,
                            _e(
                                "TWV-SCHEMA-WRONG-SHAPE",
                                path,
                                nested_ref,
                                "must be an array of non-empty strings",
                            ),
                        )
                        if field == "member_outcomes" and isinstance(value, list):
                            for outcome_index, outcome in enumerate(value):
                                outcome_error = closed_string_error(
                                    outcome,
                                    RUNTIME_RECORD_STATUS_VALUES,
                                    path=str(path),
                                    reference=f"{nested_ref}[{outcome_index}]",
                                )
                                if outcome_error is not None:
                                    errors.append(outcome_error)
                    elif field not in {"attempts", "escalations"}:
                        non_empty_string(
                            value,
                            errors,
                            _e(
                                "TWV-SCHEMA-WRONG-SHAPE",
                                path,
                                nested_ref,
                                "must be a non-empty string",
                            ),
                        )
                    if field == "outcome":
                        outcome_error = closed_string_error(
                            value,
                            RUNTIME_RECORD_STATUS_VALUES,
                            path=str(path),
                            reference=nested_ref,
                        )
                        if outcome_error is not None:
                            errors.append(outcome_error)
        for key, allowed in (
            ("attempts", ATTEMPT),
            ("escalations", ESCALATION),
            ("verification_evidence", VERIFICATION_EVIDENCE),
        ):
            values = (
                n.get("assignment", {}).get(key, [])
                if key in {"attempts", "escalations"}
                and isinstance(n.get("assignment"), dict)
                else n.get(key, [])
            )
            if not isinstance(values, list):
                errors.append(
                    _e(
                        "TWV-SCHEMA-WRONG-SHAPE",
                        path,
                        f"{ref}.{key}",
                        "must be an array",
                    )
                )
            elif isinstance(values, list):
                record_ids = [
                    value.get("id")
                    for value in values
                    if isinstance(value, dict) and isinstance(value.get("id"), str)
                ]
                if len(record_ids) != len(set(record_ids)):
                    errors.append(
                        _e(
                            "TWV-SCHEMA-DUPLICATE-RUNTIME-ID",
                            path,
                            f"{ref}.{key}",
                            "runtime record IDs must be unique",
                        )
                    )
                for value_index, value in enumerate(values):
                    _closed(value, allowed, path, f"{ref}.{key}[{value_index}]", errors)
                    if isinstance(value, dict):
                        required_fields = (
                            allowed
                            if key != "attempts" or version == 4
                            else allowed - {"outcome_path"}
                        )
                        for required in required_fields:
                            if required not in value:
                                errors.append(
                                    _e(
                                        "TWV-SCHEMA-MISSING-FIELD",
                                        path,
                                        f"{ref}.{key}[{value_index}].{required}",
                                        "required runtime record field is missing",
                                    )
                                )
                        for field, nested_value in value.items():
                            nested_ref = f"{ref}.{key}[{value_index}].{field}"
                            if field == "context_refs" or (
                                key == "attempts" and field == "verification"
                            ):
                                string_list(
                                    nested_value,
                                    errors,
                                    _e(
                                        "TWV-SCHEMA-WRONG-SHAPE",
                                        path,
                                        nested_ref,
                                        "must be an array of non-empty strings",
                                    ),
                                )
                            else:
                                non_empty_string(
                                    nested_value,
                                    errors,
                                    _e(
                                        "TWV-SCHEMA-WRONG-SHAPE",
                                        path,
                                        nested_ref,
                                        "must be a non-empty string",
                                    ),
                                )
                        if key == "attempts" and "status" in value:
                            status_error = closed_string_error(
                                value["status"],
                                RUNTIME_RECORD_STATUS_VALUES,
                                path=str(path),
                                reference=f"{ref}.{key}[{value_index}].status",
                            )
                            if status_error is not None:
                                errors.append(status_error)
                        if version == 4 and key == "attempts" and not is_portable_filename_atom(value.get("id")):
                            errors.append(
                                _e(
                                    "TWV-SCHEMA-INVALID-VALUE",
                                    path,
                                    f"{ref}.{key}[{value_index}].id",
                                    "must be a portable filename atom",
                                )
                            )
                        if key == "attempts" and "outcome_path" in value:
                            outcome_path = value["outcome_path"]
                            if version in (1, 2, 3):
                                errors.append(
                                    _e(
                                        "TWV-SCHEMA-UNSUPPORTED-V4-FIELD",
                                        path,
                                        f"{ref}.{key}[{value_index}].outcome_path",
                                        "version-4-only attempt field on a legacy manifest",
                                    )
                                )
                            elif (
                                isinstance(value.get("status"), str)
                                and isinstance(outcome_path, str)
                                and (
                                    (
                                        value["status"] in {"pending", "running"}
                                        and outcome_path != UNAVAILABLE_OUTCOME_PATH
                                    )
                                    or (
                                        value["status"] in {"complete", "blocked", "failed"}
                                        and outcome_path != f"stage-outcomes/{value.get('id')}.toml"
                                    )
                                )
                            ):
                                errors.append(
                                    _e(
                                        "TWV-SCHEMA-INVALID-VALUE",
                                        path,
                                        f"{ref}.{key}[{value_index}].outcome_path",
                                        "must be unavailable for pending/running attempts and a path for terminal attempts",
                                    )
                                )
                        if key == "verification_evidence" and "output_sha256" in value:
                            digest = value["output_sha256"]
                            nonexecuted = value.get("result") in {"not-run", "unavailable"}
                            if (nonexecuted and (digest != "unavailable" or value.get("evidence_ref") != "unavailable")) or (
                                not nonexecuted and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None)
                            ):
                                errors.append(
                                    _e(
                                        "TWV-SCHEMA-INVALID-DIGEST",
                                        path,
                                        f"{ref}.{key}[{value_index}].output_sha256",
                                        "must be unavailable for non-executed evidence and a 64-character lowercase digest otherwise",
                                    )
                                )
        _extensions(n.get("extensions"), path, f"{ref}.extensions", errors)
        scope = (
            n.get("review_scope") if isinstance(n.get("review_scope"), dict) else None
        )
        if scope:
            for field in ("integrated_wave_ids", "wave_terminal_dependencies"):
                if not scope.get(field):
                    continue
                errors.append(
                    _e(
                        "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
                        path,
                        f"{ref}.review_scope.{field}",
                        "operational waves are unsupported",
                    )
                )
        validated_nodes.append(n)
    if errors:
        return ParseResult(None, sorted_errors(errors))
    nodes = tuple(
        Node(
            n["id"],
            n["sequence"],
            n["kind"],
            n["status"],
            tuple(n["depends_on"]),
            tuple(
                n.get(key, "")
                for key in ("brief", "context", "report", "reviewer_invocation")
            ),
            n.get("review_scope"),
            n,
        )
        for n in validated_nodes
    )
    return ParseResult(
        Manifest(
            version,
            str(raw["task_id"]),
            str(raw["base_revision"]),
            policies,
            nodes,
            str(path),
            raw["source_plan"],
            raw.get("roadmap_item"),
            raw.get("controller_view"),
        ),
        (),
    )
