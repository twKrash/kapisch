from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from .artifact_io import ArtifactFailure, ArtifactFailureKind, load_toml_artifact
from .errors import ValidationError, sorted_errors
from .helpers import is_integer, non_empty_string, nonfinite_float_references, string_list
from .models import Manifest, Node, ParseResult
from .path_atoms import is_portable_filename_atom, validate_relative_posix_path
from .canonical_toml import render_toml
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

MANIFEST_KEY_ORDER = (
    "version", "task_id", "source_plan", "roadmap_item", "base_revision",
    "policies", "nodes", "waves", "controller_view", "extensions",
)
ROOT = set(MANIFEST_KEY_ORDER)
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
NODE_REQUIRED = {"id", "sequence", "kind", "status", "depends_on", "brief", "context", "report"}
NODE_STATUS_VALUES = {
    "pending", "ready", "running", "implemented", "reviewing",
    "complete", "blocked", "failed", "cancelled",
}
GLOB_META = frozenset("*?[")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _render_error(message: str) -> ValueError:
    return ValueError(f"invalid manifest: {message}")


def _check_path(value: object, reference: str) -> None:
    if not isinstance(value, str) or value == "unavailable":
        raise _render_error(f"{reference} must be a portable relative path")
    try:
        validate_relative_posix_path(value)
    except ValueError as error:
        raise _render_error(f"{reference} must be a portable relative path") from error


def _check_path_or_unavailable(value: object, reference: str) -> None:
    if value == "unavailable":
        return
    _check_path(value, reference)


def _check_concrete_scope_path(value: str, reference: str) -> None:
    """Validate concrete repository paths while preserving globs and URLs."""
    if any(character in value for character in GLOB_META) or URL_RE.match(value):
        return
    _check_path(value, reference)


def _require(data: dict[str, object], fields: set[str], reference: str) -> None:
    missing = fields - set(data)
    if missing:
        raise _render_error(f"{reference} is missing field {sorted(missing)[0]!r}")


def _string(value: object, reference: str) -> str:
    if not isinstance(value, str) or not value:
        raise _render_error(f"{reference} must be a non-empty string")
    return value


def _integer(value: object, reference: str, *, minimum: int | None = None) -> int:
    if not is_integer(value) or (minimum is not None and value < minimum):
        qualifier = f" at least {minimum}" if minimum is not None else ""
        raise _render_error(f"{reference} must be an integer{qualifier}")
    return value


def _choice(value: object, choices: object, reference: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise _render_error(f"{reference} has unsupported value {value!r}")
    return value


def _extensions_render(value: object, reference: str) -> dict[str, object]:
    result = _closed_render(value, set(value) if isinstance(value, dict) else set(), reference)
    for namespace in result:
        if not isinstance(namespace, str) or re.fullmatch(
            r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", namespace
        ) is None:
            raise _render_error(f"{reference}.{namespace} must be a reverse-DNS namespace")
    return result


def _normalize_list(
    value: object, reference: str, *, normalize: bool, unique: bool = False
) -> list[str]:
    if not isinstance(value, list):
        raise _render_error(f"{reference} must be an array")
    if not all(isinstance(item, str) and item for item in value):
        raise _render_error(f"{reference} must contain non-empty strings")
    if unique and len(value) != len(set(value)):
        raise _render_error(f"{reference} must not contain duplicates")
    if normalize:
        return sorted(set(value))
    return list(value)


def _closed_render(data: object, allowed: set[str], reference: str) -> dict[str, object]:
    if not isinstance(data, dict):
        raise _render_error(f"{reference} must be a table")
    unknown = set(data) - allowed
    if unknown:
        raise _render_error(f"{reference} has unknown field {sorted(unknown)[0]!r}")
    return dict(data)


def _render_runtime_records(
    values: object,
    *,
    allowed: set[str],
    required: set[str],
    reference: str,
    version: int,
) -> list[dict[str, object]]:
    if not isinstance(values, list):
        raise _render_error(f"{reference} must be an array of tables")
    records: list[dict[str, object]] = []
    ids: set[str] = set()
    for index, value in enumerate(values):
        item_ref = f"{reference}[{index}]"
        record = _closed_render(value, allowed, item_ref)
        _require(record, required, item_ref)
        record_id = _string(record["id"], f"{item_ref}.id")
        if record_id in ids:
            raise _render_error(f"{reference} has duplicate runtime id {record_id!r}")
        ids.add(record_id)
        for key, item in record.items():
            field_ref = f"{item_ref}.{key}"
            if key in {"context_refs", "verification"}:
                record[key] = _normalize_list(item, field_ref, normalize=False)
            else:
                _string(item, field_ref)
        records.append(record)
    return records


def _render_node(node: object, *, initial: bool, version: int) -> dict[str, object]:
    raw = _closed_render(node, NODE, "nodes[]")
    _require(raw, NODE_REQUIRED, "nodes[]")
    _string(raw["id"], "nodes[].id")
    _integer(raw["sequence"], "nodes[].sequence", minimum=0)
    _string(raw["kind"], "nodes[].kind")
    _choice(raw["status"], NODE_STATUS_VALUES, "nodes[].status")
    for key in ("title", "risk", "blocker"):
        if key in raw:
            _string(raw[key], f"nodes[].{key}")
    for key in ("brief", "context", "report", "reviewer_invocation"):
        if key in raw:
            _check_path(raw[key], f"nodes[].{key}")
    for key in ("reads", "writes", "shared_resources"):
        if key in raw:
            raw[key] = _normalize_list(raw[key], f"nodes[].{key}", normalize=initial)
            if key in {"reads", "writes"}:
                for index, value in enumerate(raw[key]):
                    _check_concrete_scope_path(value, f"nodes[].{key}[{index}]")
    for key in ("depends_on", "delegation_ids", "verification", "context_refs"):
        if key in raw:
            raw[key] = _normalize_list(
                raw[key], f"nodes[].{key}", normalize=(key == "depends_on"),
                unique=key == "delegation_ids" or (key == "depends_on" and not initial),
            )
    if version in (1, 2) and "delegation_ids" in raw:
        raise _render_error("nodes[].delegation_ids is not legal before version 3")
    if version in (3, 4) and "delegation_ids" not in raw:
        raise _render_error("nodes[] is missing field 'delegation_ids'")
    for key, choices in NODE_ROUTING_VALUES.items():
        if key in raw:
            _choice(raw[key], choices, f"nodes[].{key}")
    executor_class = raw.get("executor_class")
    model_tier = raw.get("model_tier")
    is_implementation = raw["kind"] not in {"review", "final", "research"}
    if executor_class == "reviewer" and is_implementation:
        raise _render_error("nodes[].executor_class reviewer is invalid for implementation")
    if executor_class == "reviewer" and model_tier != "high":
        raise _render_error("nodes[].executor_class reviewer requires model_tier='high'")
    if executor_class == "researcher" and is_implementation:
        raise _render_error("nodes[].executor_class researcher is advisory only")
    if raw["kind"] in {"review", "final"} and any(
        key in raw for key in ("executor_class", "model_tier", "batching")
    ) and (
        executor_class != "reviewer"
        or model_tier != "high"
        or raw.get("batching") != "off"
    ):
        raise _render_error("review/final routing must be reviewer/high/off")
    if "review_scope" in raw:
        scope = _closed_render(raw["review_scope"], SCOPE, "nodes[].review_scope")
        for key, value in list(scope.items()):
            scope[key] = _normalize_list(
                value, f"nodes[].review_scope.{key}", normalize=True,
                unique=not initial,
            )
        if any(scope.get(key) for key in ("integrated_wave_ids", "wave_terminal_dependencies")):
            raise _render_error("nodes[].review_scope contains unsupported operational waves")
        raw["review_scope"] = scope
    if "revision" in raw:
        revision = _closed_render(raw["revision"], REVISION, "nodes[].revision")
        for key, value in revision.items():
            _string(value, f"nodes[].revision.{key}")
        raw["revision"] = revision
    if "assignment" in raw:
        assignment = _closed_render(raw["assignment"], ASSIGNMENT, "nodes[].assignment")
        _require(assignment, ASSIGNMENT_REQUIRED, "nodes[].assignment")
        _string(assignment["id"], "nodes[].assignment.id")
        _integer(assignment["schema_version"], "nodes[].assignment.schema_version")
        _choice(
            assignment["execution_class"], ASSIGNMENT_VALUES["execution_class"],
            "nodes[].assignment.execution_class",
        )
        _string(assignment["source_revision"], "nodes[].assignment.source_revision")
        if "reason_codes" in assignment:
            assignment["reason_codes"] = _normalize_list(
                assignment["reason_codes"], "nodes[].assignment.reason_codes", normalize=initial
            )
        if "context_refs" in assignment:
            assignment["context_refs"] = _normalize_list(
                assignment["context_refs"], "nodes[].assignment.context_refs", normalize=False
            )
        for key in ("context_fingerprint", "scope_fingerprint"):
            if key in assignment:
                _string(assignment[key], f"nodes[].assignment.{key}")
        attempt_required = ATTEMPT if version == 4 else ATTEMPT - {"outcome_path"}
        attempts = _render_runtime_records(
            assignment.get("attempts"), allowed=ATTEMPT, required=attempt_required,
            reference="nodes[].assignment.attempts", version=version,
        )
        for index, attempt in enumerate(attempts):
            ref = f"nodes[].assignment.attempts[{index}]"
            _choice(attempt["status"], RUNTIME_RECORD_STATUS_VALUES, f"{ref}.status")
            if not is_portable_filename_atom(attempt["id"]) and version == 4:
                raise _render_error(f"{ref}.id must be a portable filename atom")
            if "outcome_path" in attempt:
                if version != 4:
                    raise _render_error(f"{ref}.outcome_path is not legal before version 4")
                expected = (
                    UNAVAILABLE_OUTCOME_PATH
                    if attempt["status"] in {"pending", "running"}
                    else f"stage-outcomes/{attempt['id']}.toml"
                )
                if attempt["outcome_path"] != expected:
                    raise _render_error(f"{ref}.outcome_path does not match attempt status and id")
                _check_path_or_unavailable(attempt["outcome_path"], f"{ref}.outcome_path")
        assignment["attempts"] = attempts
        escalations = _render_runtime_records(
            assignment.get("escalations"), allowed=ESCALATION, required=ESCALATION,
            reference="nodes[].assignment.escalations", version=version,
        )
        assignment["escalations"] = escalations
        raw["assignment"] = assignment
    if "batch" in raw:
        batch = _closed_render(raw["batch"], BATCH, "nodes[].batch")
        _require(batch, BATCH, "nodes[].batch")
        _string(batch["id"], "nodes[].batch.id")
        for key in ("member_node_ids", "member_assignment_ids", "member_outcomes"):
            batch[key] = _normalize_list(batch[key], f"nodes[].batch.{key}", normalize=False)
        for index, value in enumerate(batch["member_outcomes"]):
            _choice(value, RUNTIME_RECORD_STATUS_VALUES, f"nodes[].batch.member_outcomes[{index}]")
        _choice(batch["outcome"], RUNTIME_RECORD_STATUS_VALUES, "nodes[].batch.outcome")
        raw["batch"] = batch
    if "verification_evidence" in raw:
        evidence = _render_runtime_records(
            raw["verification_evidence"], allowed=VERIFICATION_EVIDENCE,
            required=VERIFICATION_EVIDENCE, reference="nodes[].verification_evidence",
            version=version,
        )
        for index, record in enumerate(evidence):
            ref = f"nodes[].verification_evidence[{index}]"
            nonexecuted = record["result"] in {"not-run", "unavailable"}
            if version == 4 and nonexecuted:
                if record["output_sha256"] != "unavailable" or record["evidence_ref"] != "unavailable":
                    raise _render_error(f"{ref} must use unavailable evidence sentinels")
            elif re.fullmatch(r"[0-9a-f]{64}", record["output_sha256"]) is None:
                raise _render_error(f"{ref}.output_sha256 must be a lowercase SHA-256 digest")
            _check_path_or_unavailable(record["evidence_ref"], f"{ref}.evidence_ref")
        raw["verification_evidence"] = evidence
    if initial and "extensions" in raw and raw["extensions"] == {}:
        del raw["extensions"]
    elif "extensions" in raw:
        raw["extensions"] = _extensions_render(raw["extensions"], "nodes[].extensions")
    return raw


def render_manifest(raw: dict[str, object], *, initial: bool) -> bytes:
    """Return canonical bytes for a newly created or authorized graph snapshot."""
    data = _closed_render(deepcopy(raw), ROOT, "root")
    _require(data, {"version", "task_id", "source_plan", "base_revision", "policies", "nodes"}, "root")
    version = data["version"]
    if not is_integer(version) or version not in MANIFEST_VERSION_VALUES:
        raise _render_error("version must be integer 1, 2, 3, or 4")
    for key in ("task_id", "base_revision", "roadmap_item"):
        if key in data:
            _string(data[key], key)
    if "source_plan" in data:
        _check_path(data["source_plan"], "source_plan")
    if version == 4:
        if data.get("controller_view") != V4_CONTROLLER_VIEW_PATH:
            raise _render_error(f"controller_view must be {V4_CONTROLLER_VIEW_PATH!r} for version 4")
    elif "controller_view" in data:
        raise _render_error("controller_view is not legal before version 4")
    policies = data.get("policies")
    data["policies"] = _closed_render(policies, POLICIES, "policies")
    required_policies = POLICIES if version in (3, 4) else POLICIES - {"ecosystem_routing"}
    if version == 1:
        required_policies = set()
    _require(data["policies"], required_policies, "policies")
    if version in (1, 2) and "ecosystem_routing" in data["policies"]:
        raise _render_error("policies.ecosystem_routing is not legal before version 3")
    for key, value in data["policies"].items():
        if key == "max_parallel_agents":
            if value != 1 or not is_integer(value):
                raise _render_error("policies.max_parallel_agents must be integer 1")
        elif key == "max_fix_rounds":
            _integer(value, "policies.max_fix_rounds", minimum=0)
        elif key in POLICY_VALUES:
            _choice(value, POLICY_VALUES[key], f"policies.{key}")
    if "waves" in data:
        raise _render_error("root.waves is unsupported")
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise _render_error("nodes must be an array")
    rendered_nodes = [_render_node(node, initial=initial, version=version) for node in nodes]
    seen_ids: set[object] = set()
    seen_sequences: set[object] = set()
    for node in rendered_nodes:
        node_id, sequence = node.get("id"), node.get("sequence")
        if node_id in seen_ids:
            raise _render_error(f"duplicate node id {node_id!r}")
        if sequence in seen_sequences:
            raise _render_error(f"duplicate node sequence {sequence!r}")
        seen_ids.add(node_id)
        seen_sequences.add(sequence)
        if (
            node["kind"] not in {"review", "final", "research"}
            and data["policies"].get("dispatch") == "single"
            and ("executor_class" in node or "model_tier" in node)
            and (
                node.get("executor_class") != "implementer"
                or node.get("model_tier") != "standard"
            )
        ):
            raise _render_error(
                f"node {node_id!r} must use implementer/standard for single dispatch"
            )
    data["nodes"] = sorted(rendered_nodes, key=lambda node: (node.get("sequence"), node.get("id")))
    if "extensions" in data and data["extensions"] == {}:
        del data["extensions"]
    elif "extensions" in data:
        data["extensions"] = _extensions_render(data["extensions"], "extensions")
    return render_toml(data, key_order=MANIFEST_KEY_ORDER)


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
                        if key == "verification_evidence" and "output_sha256" in value and isinstance(value.get("result"), str):
                            digest = value["output_sha256"]
                            nonexecuted = value["result"] in {"not-run", "unavailable"}
                            invalid_digest = (
                                version == 4
                                and nonexecuted
                                and (digest != "unavailable" or value.get("evidence_ref") != "unavailable")
                            ) or (
                                (version != 4 or not nonexecuted)
                                and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None)
                            )
                            if invalid_digest:
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
