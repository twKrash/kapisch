from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .errors import ValidationError, sorted_errors
from .helpers import is_integer, non_empty_string, string_list
from .models import Manifest, Node, ParseResult

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
BATCH = {"id", "member_node_ids", "member_assignment_ids", "member_outcomes", "outcome"}
ATTEMPT = {"id", "source_revision", "context_scope_ref", "status", "verification"}
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
}


def _e(c: str, p: Path, r: str, m: str) -> ValidationError:
    return ValidationError(c, str(p), r, m)


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
    if not path.is_file():
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
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        return ParseResult(
            None,
            sorted_errors([_e("TWV-PARSE-MALFORMED-TOML", path, "toml", str(exc))]),
        )
    _closed(raw, ROOT, path, "root", errors)
    _extensions(raw.get("extensions"), path, "extensions", errors)
    _closed(raw.get("policies"), POLICIES, path, "policies", errors)
    version = raw.get("version")
    if not is_integer(version) or version not in (1, 2):
        errors.append(
            _e("TWV-SCHEMA-INVALID-VERSION", path, "version", "must be integer 1 or 2")
        )
    for key in ("task_id", "source_plan", "base_revision", "nodes"):
        if key not in raw:
            errors.append(
                _e("TWV-SCHEMA-MISSING-FIELD", path, key, "required field is missing")
            )
    for key in ("task_id", "source_plan", "base_revision"):
        if key in raw:
            non_empty_string(
                raw[key],
                errors,
                _e("TWV-SCHEMA-WRONG-SHAPE", path, key, "must be a non-empty string"),
            )
    policies = (
        dict(raw.get("policies", {})) if isinstance(raw.get("policies"), dict) else {}
    )
    if version == 1:
        for key, value in V1.items():
            policies.setdefault(key, value)
    if version == 2:
        for key in POLICIES:
            if key not in policies:
                errors.append(
                    _e(
                        "TWV-SCHEMA-MISSING-FIELD",
                        path,
                        f"policies.{key}",
                        "required version-2 policy is missing",
                    )
                )
    for key, value in policies.items():
        reference = f"policies.{key}"
        if key == "max_parallel_agents":
            valid, message = is_integer(value), "must be an integer"
        elif key == "max_fix_rounds":
            valid, message = (
                is_integer(value) and value >= 0,
                "must be a non-negative integer",
            )
        else:
            valid, message = (
                isinstance(value, str) and bool(value),
                "must be a non-empty string",
            )
        if not valid:
            errors.append(_e("TWV-SCHEMA-WRONG-SHAPE", path, reference, message))
    unsupported_wave_fields = (
        ("policies.parallelism", policies.get("parallelism") != "off"),
        ("policies.max_parallel_agents", policies.get("max_parallel_agents") != 1),
        ("root.waves", "waves" in raw),
    )
    for reference, unsupported in unsupported_wave_fields:
        if not unsupported:
            continue
        errors.append(
            _e(
                "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
                path,
                reference,
                "operational waves are unsupported",
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
                for value_index, value in enumerate(values):
                    _closed(value, allowed, path, f"{ref}.{key}[{value_index}]", errors)
                    if isinstance(value, dict):
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
        ),
        (),
    )
