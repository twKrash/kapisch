from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ._authority import _unique_pairs, _validate_packet_authority
from ._invocation import _validate_reservation
from ._state import _parse_state, load_state
from .bundle import CoreBundle, canonical_json
from .storage import (
    _close,
    _id,
    _open_dir,
    _read_contained,
    _read_file,
    _run_dir,
    load_bundle,
)


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str
    path: str | None = None


class _ValidationFailure(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _json(data: bytes, label: str) -> Any:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is malformed JSON") from error
    if canonical_json(value) != data:
        raise ValueError(f"{label} is not canonical JSON")
    return value


def _resolve_ref(bundle: CoreBundle, ref: str, local_root: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    schema_id, _, fragment = ref.partition("#")
    if ref.startswith("#"):
        schema_id = str(local_root.get("$id", ""))
        root: Any = local_root
    else:
        if not schema_id.startswith("kapisch://schemas/v3/"):
            raise ValueError(f"unsupported schema reference: {ref}")
        name = schema_id.rsplit("/", 1)[-1]
        root = bundle.payload["schemas"].get(name)
        if not isinstance(root, Mapping) or root["$id"] != schema_id:
            raise ValueError(f"unresolved schema reference: {ref}")
    target: Any = root
    for token in fragment.lstrip("/").split("/") if fragment else ():
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, Mapping) or token not in target:
            raise ValueError(f"unresolved schema reference: {ref}")
        target = target[token]
    if not isinstance(target, Mapping):
        raise ValueError(f"invalid schema reference: {ref}")
    return target, schema_id


def _matches(value: Any, schema: Mapping[str, Any], root: Mapping[str, Any], bundle: CoreBundle,
             errors: list[str], path: str) -> None:
    if "$ref" in schema:
        target, target_id = _resolve_ref(bundle, schema["$ref"], root)
        target_name = target_id.rsplit("/", 1)[-1]
        target_root = root if schema["$ref"].startswith("#") else bundle.payload["schemas"][target_name]
        _matches(value, target, target_root, bundle, errors, path)
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    type_ok = not types or any(
        (kind == "object" and isinstance(value, dict))
        or (kind == "array" and isinstance(value, list))
        or (kind == "string" and isinstance(value, str))
        or (kind == "integer" and isinstance(value, int) and not isinstance(value, bool))
        or (kind == "number" and isinstance(value, (int, float)) and not isinstance(value, bool))
        or (kind == "boolean" and isinstance(value, bool))
        or (kind == "null" and value is None)
        for kind in types
    )
    if not type_ok:
        errors.append(f"{path}: expected {expected}")
        return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match required pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        if ((minimum is not None and value < minimum)
                or (maximum is not None and value > maximum)):
            errors.append(f"{path}: number outside allowed range")
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing {key}")
        props = schema.get("properties", {})
        additional_properties = schema.get("additionalProperties", True)
        if isinstance(additional_properties, bool) and not additional_properties:
            for key in value.keys() - props.keys():
                errors.append(f"{path}: unknown field {key}")
        for key, child in props.items():
            if key in value:
                _matches(value[key], child, root, bundle, errors, f"{path}.{key}")
    if isinstance(value, list):
        if schema.get("uniqueItems") and len({canonical_json(item) for item in value}) != len(value):
            errors.append(f"{path}: duplicate array item")
        if "items" in schema:
            for index, item in enumerate(value):
                _matches(item, schema["items"], root, bundle, errors, f"{path}[{index}]")
    for child in schema.get("allOf", []):
        _matches(value, child, root, bundle, errors, path)
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            candidates: list[list[str]] = []
            for child in schema[keyword]:
                child_errors: list[str] = []
                _matches(value, child, root, bundle, child_errors, path)
                candidates.append(child_errors)
            valid = sum(not candidate for candidate in candidates)
            if (keyword == "anyOf" and not valid) or (keyword == "oneOf" and valid != 1):
                errors.append(f"{path}: does not satisfy {keyword}")
    if "if" in schema:
        condition: list[str] = []
        _matches(value, schema["if"], root, bundle, condition, path)
        branch = "then" if not condition else "else"
        if branch in schema:
            _matches(value, schema[branch], root, bundle, errors, path)
    if "not" in schema:
        condition: list[str] = []
        _matches(value, schema["not"], root, bundle, condition, path)
        if not condition:
            errors.append(f"{path}: forbidden shape")


def _validate_schema(value: Any, schema_name: str, bundle: CoreBundle) -> None:
    schema = bundle.payload["schemas"][schema_name]
    errors: list[str] = []
    _matches(value, schema, schema, bundle, errors, "$" )
    if errors:
        raise ValueError("; ".join(errors))


def _require_schema_shape(label: str, schema: Any, required: set[str],
                          constraints: Mapping[str, Mapping[str, Any]],
                          allowed_properties: set[str] | None = None) -> None:
    schema_required = schema.get("required") if isinstance(schema, Mapping) else None
    if (not isinstance(schema, Mapping) or schema.get("type") != "object"
            or schema.get("additionalProperties") is not False
            or not isinstance(schema_required, (list, tuple)) or set(schema_required) != required):
        raise ValueError(f"retained bundle weakens stage-attempt/1 {label} schema")
    properties = schema.get("properties")
    if (not isinstance(properties, Mapping)
            or (allowed_properties is not None and set(properties) != allowed_properties)):
        raise ValueError(f"retained bundle weakens stage-attempt/1 {label} schema")

    def matches(actual: Any, expected: Any) -> bool:
        if isinstance(actual, Mapping) and isinstance(expected, Mapping):
            return _identity_schema_shape(actual) == _identity_schema_shape(expected)
        return actual == expected

    for name, expected in constraints.items():
        actual = properties.get(name)
        if not isinstance(actual, Mapping) or any(
            (set(actual.get(key, [])) != set(value) if key == "enum" else not matches(actual.get(key), value))
            for key, value in expected.items()
        ):
            raise ValueError(f"retained bundle weakens stage-attempt/1 {label}.{name} schema")


_IDENTITY_SCHEMA_ANNOTATIONS = frozenset({"$comment", "title", "description", "default", "deprecated",
                                         "readOnly", "writeOnly", "examples"})
_IDENTITY_SCHEMA_MAP_KEYWORDS = frozenset({"$defs", "definitions", "properties", "patternProperties"})
_IDENTITY_SCHEMA_KEYWORDS = frozenset({"additionalItems", "additionalProperties", "contains", "contentSchema",
                                      "else", "if", "items", "not", "propertyNames", "then",
                                      "unevaluatedItems", "unevaluatedProperties"})
_IDENTITY_SCHEMA_ARRAY_KEYWORDS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
# Semantic fingerprints pin supported schemas while allowing documentation-only edits.
_SUPPORTED_IDENTITY_SCHEMA_DIGEST = "38ddaff3875010673d485689142ea500b3b6af85569942838ebbc91e1e22e108"


def _identity_schema_shape(value: Any, *, schema_node: bool = True) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, child in value.items():
            if schema_node and key in _IDENTITY_SCHEMA_ANNOTATIONS:
                continue
            if schema_node and key in _IDENTITY_SCHEMA_MAP_KEYWORDS and isinstance(child, Mapping):
                result[key] = {name: _identity_schema_shape(subschema) for name, subschema in child.items()}
            elif schema_node and key in _IDENTITY_SCHEMA_KEYWORDS:
                result[key] = _identity_schema_shape(child, schema_node=isinstance(child, Mapping))
            elif schema_node and key in _IDENTITY_SCHEMA_ARRAY_KEYWORDS and isinstance(child, (list, tuple)):
                result[key] = [_identity_schema_shape(subschema) for subschema in child]
            else:
                result[key] = _identity_schema_shape(child, schema_node=False)
        return result
    if isinstance(value, (list, tuple)):
        return [_identity_schema_shape(child, schema_node=False) for child in value]
    return value


def _require_supported_identity_schemas(schemas: Mapping[str, Any]) -> None:
    shape = {name: _identity_schema_shape(schemas.get(name))
             for name in ("bundle", "invocation", "run", "stage")}
    if any(not isinstance(schema, Mapping) for schema in shape.values()) or hashlib.sha256(
        canonical_json(shape)
    ).hexdigest() != _SUPPORTED_IDENTITY_SCHEMA_DIGEST:
        raise ValueError("retained bundle alters supported stage-attempt/1 schema rules")


def _validate_identity_contract(bundle: CoreBundle) -> None:
    schemas = bundle.payload["schemas"]
    _require_supported_identity_schemas(schemas)
    run = schemas.get("run")
    if not isinstance(run, Mapping) or run.get("$id") != "kapisch://schemas/v3/run":
        raise ValueError("retained bundle lacks supported stage-attempt/1 run schema")
    _require_schema_shape("run", run,
                          {"protocol_version", "run_id", "bundle_digest", "workflow", "revision", "history",
                           "identity_contract"},
                          {"protocol_version": {"const": 3},
                           "identity_contract": {"const": "stage-attempt/1"},
                           "bundle_digest": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
                           "workflow": {"enum": ["advisory", "review", "task", "milestone"]},
                           "history": {"type": "array", "items": {"$ref": "kapisch://schemas/v3/stage"}},
                           "approved_plan": {"$ref": "#/$defs/plan_ref"},
                           "graph": {"$ref": "#/$defs/graph_ref"}},
                          {"protocol_version", "run_id", "bundle_digest", "workflow", "revision", "history",
                           "accepted_snapshot", "approved_plan", "amends", "supersedes", "identity_contract", "graph"})

    definitions = run.get("$defs", {})
    _require_schema_shape("graph_ref", definitions.get("graph_ref") if isinstance(definitions, Mapping) else None,
                          {"path", "sha256"},
                          {"path": {"type": "string", "minLength": 1},
                           "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"}},
                          {"path", "sha256"})
    _require_schema_shape("graph_document", definitions.get("graph_document") if isinstance(definitions, Mapping) else None,
                          {"protocol_version", "run_id", "plan_id", "nodes"},
                          {"protocol_version": {"const": 3}, "run_id": {"type": "string", "minLength": 1},
                           "plan_id": {"type": "string", "minLength": 1},
                           "nodes": {"type": "array", "items": {"$ref": "#/$defs/graph_node"}}},
                          {"protocol_version", "run_id", "plan_id", "nodes"})
    _require_schema_shape("graph_node", definitions.get("graph_node") if isinstance(definitions, Mapping) else None,
                          {"node_id", "scope", "depends_on"},
                          {"node_id": {"type": "string", "pattern": r"^n-[0-9a-f]{32}$"},
                           "scope": {"$ref": "#/$defs/scope_ref"},
                           "depends_on": {"type": "array", "items": {"type": "string", "pattern": r"^n-[0-9a-f]{32}$"},
                                          "uniqueItems": True}},
                          {"node_id", "scope", "depends_on"})
    _require_schema_shape("scope_ref", definitions.get("scope_ref") if isinstance(definitions, Mapping) else None,
                          {"path", "sha256"},
                          {"path": {"type": "string", "minLength": 1},
                           "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"}},
                          {"path", "sha256"})
    _require_schema_shape("scope_document", definitions.get("scope_document") if isinstance(definitions, Mapping) else None,
                          {"protocol_version", "run_id", "node_id", "requirements"},
                          {"protocol_version": {"const": 3}, "run_id": {"type": "string", "minLength": 1},
                           "node_id": {"type": "string", "pattern": r"^n-[0-9a-f]{32}$"},
                           "requirements": {"type": "string", "minLength": 1}},
                          {"protocol_version", "run_id", "node_id", "requirements"})

    stage = schemas.get("stage")
    if not isinstance(stage, Mapping) or stage.get("$id") != "kapisch://schemas/v3/stage":
        raise ValueError("retained bundle lacks supported stage-attempt/1 stage schema")
    _require_schema_shape("stage", stage,
                          {"stage_id", "stage_kind", "sequence", "role", "status", "producer", "evidence",
                           "scope_digest"},
                          {"stage_id": {"type": "string", "pattern": r"^s-[0-9a-f]{32}$"},
                           "stage_kind": {"enum": ["bounded-delegate", "design", "final", "gate", "implement",
                                                    "research", "review"]},
                           "sequence": {"type": "integer", "minimum": 0},
                           "role": {"enum": ["architect", "researcher", "implementer", "implementer-lite",
                                              "mechanic", "reviewer"]},
                           "status": {"enum": ["planned", "dispatch-uncertain", "complete", "blocked", "failed",
                                                "interrupted"]},
                           "producer": {"const": "controller"},
                           "scope_digest": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
                           "evidence": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
                           "node_id": {"pattern": r"^n-[0-9a-f]{32}$"},
                           "retry_of_stage_id": {"pattern": r"^s-[0-9a-f]{32}$"}},
                          {"stage_id", "stage_kind", "sequence", "role", "status", "producer", "evidence",
                           "scope_digest", "node_id", "retry_of_stage_id"})
    evidence = stage.get("$defs", {}).get("evidence")
    _require_schema_shape("stage evidence", evidence, {"kind", "path", "sha256"},
                          {"kind": {"type": "string"}, "path": {"type": "string"},
                           "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"}},
                          {"kind", "path", "sha256"})

    invocation = schemas.get("invocation")
    if not isinstance(invocation, Mapping) or invocation.get("$id") != "kapisch://schemas/v3/invocation":
        raise ValueError("retained bundle lacks supported stage-attempt/1 invocation schema")
    _require_schema_shape("invocation", invocation,
                          {"protocol_version", "run_id", "operation_id", "stage_id", "role", "request_digest",
                           "status", "request", "adapter_binding"},
                          {"protocol_version": {"const": 3},
                           "operation_id": {"pattern": r"^op-[0-9a-f]{32}$"},
                           "stage_id": {"pattern": r"^s-[0-9a-f]{32}$"},
                           "role": {"enum": ["architect", "researcher", "implementer", "implementer-lite",
                                              "mechanic", "reviewer"]},
                           "request_digest": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
                           "status": {"enum": ["planned", "dispatch-uncertain", "observed", "blocked"]},
                           "request": {"type": "object", "additionalProperties": False},
                           "adapter_binding": {"type": "object", "additionalProperties": False}},
                          {"protocol_version", "run_id", "operation_id", "stage_id", "role", "request_digest",
                           "status", "request", "adapter_binding"})
    properties = invocation.get("properties")
    request = properties.get("request") if isinstance(properties, Mapping) else None
    _require_schema_shape("invocation request", request, {"path", "sha256"},
                          {"path": {"type": "string", "minLength": 1},
                           "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"}},
                          {"path", "sha256"})
    binding = properties.get("adapter_binding") if isinstance(properties, Mapping) else None
    _require_schema_shape("adapter binding", binding, {"adapter_id", "lookup_context"},
                          {"adapter_id": {"type": "string", "minLength": 1},
                           "lookup_context": {"type": "string", "minLength": 1}},
                          {"adapter_id", "lookup_context"})


def _inventory(repo: Path, run_id: str, state: Mapping[str, Any], bundle: CoreBundle) -> None:
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        try:
            invocations = _open_dir(run, "invocations")
        except FileNotFoundError:
            invocations = None
        if invocations is None:
            if any(row["status"] == "dispatch-uncertain" for row in state["history"]):
                raise ValueError("uncertain history has no invocation inventory")
            return
        try:
            cited: dict[str, str] = {}
            first_citation: dict[str, tuple[int, Mapping[str, Any]]] = {}
            operation_by_attempt: dict[str, str] = {}
            for row_index, row in enumerate(state["history"]):
                for evidence in row["evidence"]:
                    first_citation.setdefault(evidence["path"], (row_index, row))
                    if evidence["path"].startswith("invocations/"):
                        cited[evidence["path"]] = evidence["sha256"]
            for operation_id in sorted(os.listdir(invocations)):
                if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
                    raise ValueError("invocation inventory contains invalid operation name")
                operation = _open_dir(invocations, operation_id)
                try:
                    names = sorted(os.listdir(operation))
                    facts = {filename: _json(_read_file(operation, filename), f"invocations/{operation_id}/{filename}")
                             for filename in names if filename.endswith(".json")}
                    if len(facts) != len(names):
                        raise ValueError("invocation inventory contains unknown artifact")
                    planned = facts.get("planned.json")
                    if planned is None:
                        raise ValueError("invocation inventory entry lacks original reservation")
                    planned_packet = _validate_reservation(repo, run_id, operation_id, planned)
                    creation_index = next((index for index, row in enumerate(state["history"])
                                           if row["stage_id"] == planned["stage_id"]), None)
                    request_owner_info = first_citation.get(planned["request"]["path"])
                    if request_owner_info is None or creation_index is None:
                        raise ValueError("operation request has no earlier owning-attempt producer")
                    request_index, request_owner = request_owner_info
                    if (request_index <= creation_index or request_owner["stage_id"] != planned["stage_id"]
                            or request_owner["role"] != planned["role"]):
                        raise ValueError("operation request is consumed before its owning attempt creation")
                    for input_ref in planned_packet.get("inputs", []):
                        input_owner_info = first_citation.get(input_ref["path"])
                        if input_owner_info is None:
                            raise ValueError("operation input snapshot has no owning-attempt producer")
                        input_index, input_owner = input_owner_info
                        if (input_index <= creation_index or input_owner["stage_id"] != planned["stage_id"]
                                or input_owner["role"] != planned["role"]):
                            raise ValueError("operation input snapshot is consumed before its owning attempt creation")
                    for filename, fact in facts.items():
                        relative = f"invocations/{operation_id}/{filename}"
                        data = _read_file(operation, filename)
                        digest = hashlib.sha256(data).hexdigest()
                        if cited.get(relative) != digest:
                            raise ValueError("unreferenced invocation fact vetoes authority")
                        if filename == "planned.json":
                            _validate_schema(fact, "invocation", bundle)
                            packet = planned_packet
                            previous_operation = operation_by_attempt.setdefault(fact["stage_id"], operation_id)
                            if previous_operation != operation_id:
                                raise ValueError("attempt owns multiple operation reservations")
                            attempt = next((row for row in reversed(state["history"])
                                            if row["stage_id"] == fact["stage_id"]), None)
                            if attempt is None or fact["role"] != attempt["role"]:
                                raise ValueError("operation reservation does not resolve to an existing attempt")
                            attempt_evidence = {ref["path"]: ref["sha256"] for ref in attempt["evidence"]}
                            if attempt_evidence.get(relative) != digest:
                                raise ValueError("reservation is not owned by its attempt history")
                            if (packet.get("bundle_digest") != state["bundle_digest"]
                                    or packet.get("scope_digest") != attempt["scope_digest"]
                                    or packet.get("node_id") != attempt.get("node_id")):
                                raise ValueError("operation reservation scope, node, or bundle binding mismatch")
                            _validate_packet_authority(packet, state, attempt)
                        elif filename not in {"dispatch-uncertain.json", "observed.json", "blocked.json"}:
                            raise ValueError("invocation inventory contains unsupported fact")
                        else:
                            _validate_schema(fact, "invocation", bundle)
                            if any(fact.get(key) != planned.get(key) for key in
                                   ("protocol_version", "operation_id", "run_id", "stage_id", "role",
                                    "request_digest", "request", "adapter_binding")):
                                raise ValueError("invocation fact changed original reservation binding")
                            expected_status = {"dispatch-uncertain": "dispatch-uncertain",
                                               "observed": "observed", "blocked": "blocked"}[filename.removesuffix(".json")]
                            if fact.get("status") != expected_status:
                                raise ValueError("invocation fact has invalid status")
                            latest = next((row for row in reversed(state["history"])
                                           if row["stage_id"] == fact["stage_id"]), None)
                            if latest is None:
                                raise ValueError("invocation fact does not resolve to an existing attempt")
                            owner_evidence = {ref["path"]: ref["sha256"] for ref in latest["evidence"]}
                            if owner_evidence.get(relative) != digest:
                                raise ValueError("invocation fact is not produced by its owning attempt")
                            if filename == "dispatch-uncertain.json":
                                first_owner = next((row for row in state["history"]
                                                    if any(ref["path"] == relative for ref in row["evidence"])), None)
                                if (first_owner is None or first_owner["status"] != "dispatch-uncertain"
                                        or first_owner["stage_id"] != fact["stage_id"]
                                        or first_owner["role"] != fact["role"]):
                                    raise ValueError("uncertainty fact is not first produced by its owning attempt")
                        if fact.get("operation_id") != operation_id or fact.get("run_id") != run_id:
                            raise ValueError("invocation fact identity mismatch")
                        first_owner_info = first_citation.get(relative)
                        if first_owner_info is None:
                            raise ValueError("invocation fact has no owning producer observation")
                        first_index, first_owner = first_owner_info
                        creation_index = next((index for index, row in enumerate(state["history"])
                                                if row["stage_id"] == fact["stage_id"]), None)
                        if (creation_index is None or first_index <= creation_index
                                or first_owner["stage_id"] != fact["stage_id"]
                                or first_owner["role"] != fact["role"]):
                            raise ValueError("invocation fact is consumed before its owning attempt exists")
                        if filename == "dispatch-uncertain.json":
                            if first_owner["status"] != "dispatch-uncertain":
                                raise ValueError("uncertainty fact is not first produced by its owning attempt")
                        elif filename == "observed.json":
                            uncertainty = first_citation.get(f"invocations/{operation_id}/dispatch-uncertain.json")
                            if (uncertainty is None or uncertainty[0] >= first_index
                                    or uncertainty[1]["stage_id"] != fact["stage_id"]
                                    or uncertainty[1]["status"] != "dispatch-uncertain"):
                                raise ValueError("observed fact precedes its owning uncertainty producer")
                        elif filename == "blocked.json":
                            if first_owner["status"] != "blocked":
                                raise ValueError("blocked fact is not first produced by its owning attempt")
                            for prerequisite in (f"invocations/{operation_id}/planned.json", planned["request"]["path"]):
                                producer = first_citation.get(prerequisite)
                                if (producer is None or producer[0] > first_index
                                        or producer[1]["stage_id"] != fact["stage_id"]):
                                    raise ValueError("blocked fact precedes its request or reservation producer")
                finally:
                    os.close(operation)
            for row in state["history"]:
                if row["status"] != "dispatch-uncertain":
                    continue
                evidence = {ref["path"]: ref["sha256"] for ref in row["evidence"]}
                reservations = [path for path in evidence
                                if re.fullmatch(r"invocations/op-[0-9a-f]{32}/planned\.json", path)]
                if len(reservations) != 1:
                    raise ValueError("uncertain history must cite exactly one operation reservation")
                planned_path = reservations[0]
                operation_id = planned_path.split("/")[1]
                planned_bytes = _read_contained(repo, run_id, planned_path)
                planned = _json(planned_bytes, planned_path)
                packet = _validate_reservation(repo, run_id, operation_id, planned)
                if planned["stage_id"] != row["stage_id"] or planned["role"] != row["role"]:
                    raise ValueError("uncertain history cites another attempt's reservation")
                _validate_packet_authority(packet, state, row)
                uncertain_path = f"invocations/{operation_id}/dispatch-uncertain.json"
                uncertain_bytes = _read_contained(repo, run_id, uncertain_path)
                uncertain = _json(uncertain_bytes, uncertain_path)
                required_refs = {
                    planned_path: hashlib.sha256(planned_bytes).hexdigest(),
                    planned["request"]["path"]: planned["request_digest"],
                    uncertain_path: hashlib.sha256(uncertain_bytes).hexdigest(),
                }
                for item in packet.get("inputs", []):
                    required_refs[item["path"]] = item["sha256"]
                for field in ("graph", "approved_plan", "accepted_snapshot"):
                    if field in packet:
                        ref = packet[field]
                        required_refs[ref["path"]] = ref["sha256"]
                if (uncertain.get("status") != "dispatch-uncertain"
                        or any(evidence.get(path) != digest for path, digest in required_refs.items())):
                    raise ValueError("uncertain observation lacks exact operation and prerequisite evidence")
        finally:
            os.close(invocations)
    finally:
        _close(fds)


def _validate_plan(repo: Path, run_id: str, ref: Mapping[str, Any]) -> Mapping[str, Any]:
    body = _read_contained(repo, run_id, ref["path"])
    if hashlib.sha256(body).hexdigest() != ref["sha256"]:
        raise ValueError("approved plan digest mismatch")
    plan = _json(body, "approved plan")
    if not isinstance(plan, dict) or plan.get("plan_id") != ref["plan_id"]:
        raise ValueError("approved plan identity mismatch")
    return plan


def _validate_node_attempt_binding(state: Mapping[str, Any], attempt: Mapping[str, Any]) -> None:
    graph = state.get("graph")
    plan = state.get("approved_plan")
    if graph is None or plan is None:
        raise ValueError("node attempt lacks its approved graph/plan binding")
    evidence = attempt["evidence"]
    graph_refs = [ref for ref in evidence if ref["kind"] == "graph"]
    plan_refs = [ref for ref in evidence if ref["kind"] == "plan"]
    if (len(graph_refs) != 1 or graph_refs[0]["path"] != graph["path"]
            or graph_refs[0]["sha256"] != graph["sha256"]
            or len(plan_refs) != 1 or plan_refs[0]["path"] != plan["path"]
            or plan_refs[0]["sha256"] != plan["sha256"]):
        raise ValueError("node attempt creation evidence does not bind exact graph and plan version")


def _validate_graph(repo: Path, run_id: str, state: Mapping[str, Any],
                    plan_doc: Mapping[str, Any] | None) -> None:
    if state["workflow"] != "milestone":
        return
    graph_ref = state.get("graph")
    if graph_ref is None:
        if any("node_id" in row for row in state["history"]):
            raise ValueError("node-scoped attempt has no graph")
        return
    graph_bytes = _read_contained(repo, run_id, graph_ref["path"])
    if hashlib.sha256(graph_bytes).hexdigest() != graph_ref["sha256"]:
        raise ValueError("graph digest mismatch")
    graph = _json(graph_bytes, "milestone graph")
    bundle = load_bundle(repo, state["bundle_digest"])
    schema = bundle.payload["schemas"]["run"]["$defs"]["graph_document"]
    errors: list[str] = []
    _matches(graph, schema, bundle.payload["schemas"]["run"], bundle, errors, "graph")
    if errors:
        raise ValueError("; ".join(errors))
    if graph["run_id"] != run_id:
        raise ValueError("graph run identity mismatch")
    plan = state.get("approved_plan")
    if plan is None or plan_doc is None or plan["plan_id"] != graph["plan_id"]:
        raise ValueError("graph is not bound to current approved plan")
    if plan_doc.get("graph") != graph_ref:
        raise ValueError("approved plan does not bind exact graph path and digest")
    nodes: dict[str, Mapping[str, Any]] = {}
    for node in graph["nodes"]:
        node_id = node["node_id"]
        if re.fullmatch(r"n-[0-9a-f]{32}", node_id) is None:
            raise ValueError("graph node_id is invalid")
        if node_id in nodes:
            raise ValueError("duplicate milestone node identity")
        nodes[node_id] = node
        scope_bytes = _read_contained(repo, run_id, node["scope"]["path"])
        if hashlib.sha256(scope_bytes).hexdigest() != node["scope"]["sha256"]:
            raise ValueError("milestone scope digest mismatch")
        scope = _json(scope_bytes, "milestone scope")
        scope_schema = bundle.payload["schemas"]["run"]["$defs"]["scope_document"]
        errors = []
        _matches(scope, scope_schema, bundle.payload["schemas"]["run"], bundle, errors, "scope")
        if errors:
            raise ValueError("; ".join(errors))
        if not re.fullmatch(r"n-[0-9a-f]{32}", scope["node_id"]):
            raise ValueError("scope node_id is invalid")
        if scope["run_id"] != run_id or scope["node_id"] != node_id:
            raise ValueError("scope run/node identity mismatch")
    for node in nodes.values():
        if any(re.fullmatch(r"n-[0-9a-f]{32}", dep) is None for dep in node["depends_on"]):
            raise ValueError("graph dependency node_id is invalid")
        if any(dep not in nodes for dep in node["depends_on"]):
            raise ValueError("milestone dependency is unresolved")
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("milestone graph contains dependency cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in nodes[node_id]["depends_on"]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)
    for node_id in nodes:
        visit(node_id)
    validated_attempts: set[str] = set()
    for row in state["history"]:
        node_id = row.get("node_id")
        if node_id is None:
            continue
        node = nodes.get(node_id)
        if node is None or row["scope_digest"] != node["scope"]["sha256"]:
            raise ValueError("stage attempt does not bind exact milestone node scope")
        if row["stage_id"] not in validated_attempts:
            _validate_node_attempt_binding(state, row)
            validated_attempts.add(row["stage_id"])


def _validate_state(repo: Path, run_id: str, state_data: bytes) -> tuple[CoreBundle, Mapping[str, Any]]:
    state = _parse_state(state_data)
    if state["run_id"] != run_id:
        raise ValueError("run state ID does not match requested run")
    try:
        bundle = load_bundle(repo, state["bundle_digest"])
    except FileNotFoundError as error:
        raise _ValidationFailure("bundle-unavailable", "retained CoreBundle is missing") from error
    try:
        _validate_identity_contract(bundle)
    except ValueError as error:
        raise _ValidationFailure("identity-contract-unsupported", str(error)) from error
    loaded_state = load_state(repo, run_id)
    if canonical_json(dict(loaded_state)) != state_data:
        raise ValueError("run state changed during validation")
    state = loaded_state
    _validate_schema(state, "run", bundle)
    for row in state["history"]:
        _validate_schema(row, "stage", bundle)
        for evidence in row["evidence"]:
            body = _read_contained(repo, run_id, evidence["path"])
            if hashlib.sha256(body).hexdigest() != evidence["sha256"]:
                raise ValueError("run history evidence digest mismatch")
    plan_doc = _validate_plan(repo, run_id, state["approved_plan"]) if "approved_plan" in state else None
    _validate_graph(repo, run_id, state, plan_doc)
    try:
        _inventory(repo, run_id, state, bundle)
    except Exception as error:
        raise _ValidationFailure("inventory-veto", str(error)) from error
    return bundle, state


def validate_run(repo: Path, run_id: str, gate: str | None = None) -> list[ValidationError]:
    """Validate authority using only persisted run state and its retained bundle."""
    repo = Path(repo)
    try:
        run_id = _id(run_id, "run_id")
    except (TypeError, ValueError) as error:
        return [_error("invalid-run-id", str(error))]
    legacy = repo / ".kapisch/runs" / run_id
    try:
        try:
            legacy.lstat()
        except FileNotFoundError:
            pass
        else:
            return [_error("v2-refused", "v2 run state is not accepted by v3 validator", str(legacy))]
        run, fds = _run_dir(repo, run_id, create=False)
        try:
            state_data = _read_file(run, "state.json")
        finally:
            _close(fds)
        _, state = _validate_state(repo, run_id, state_data)
        if gate is not None:
            return [_error("unsupported-gate", f"gate {gate!r} is not implemented")]
        return []
    except _ValidationFailure as error:
        return [_error(error.code, str(error))]
    except FileNotFoundError as error:
        state_dir = repo / ".kapisch/v3/runs" / run_id
        try:
            state_dir.lstat()
        except FileNotFoundError:
            return [_error("run-unavailable", "v3 run state is missing")]
        except OSError as inspection_error:
            return [_error("state-unavailable", f"could not inspect v3 run state: {inspection_error}", str(state_dir))]
        return [_error("state-unavailable", "run state or required authority artifact is missing", str(state_dir))]
    except Exception as error:
        message = str(error)
        if "bundle" in message.lower():
            code = "bundle-invalid"
        elif "unreferenced invocation" in message or "vetoes authority" in message:
            code = "inventory-veto"
        elif "schema" in message or "unknown field" in message:
            code = "schema-invalid"
        else:
            code = "authority-invalid"
        return [_error(code, message)]


def _error(code: str, message: str, path: str | None = None) -> ValidationError:
    return ValidationError(code, message, path)
