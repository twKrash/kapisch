from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import unquote

from .domain import (
    CapabilityEffect,
    ExecutionClass,
    Gate,
    LogicalTier,
    ReviewDepth,
    ReviewScope,
    Risk,
    Role,
    Stage,
    TransitionKind,
    Workflow,
)

_ROLE_IDS = tuple(sorted(role.value for role in Role))
_WORKFLOW_IDS = tuple(sorted(workflow.value for workflow in Workflow))
_POLICY_IDS = (
    "authority",
    "dispatch",
    "handoff",
    "normalization",
    "resume",
    "review",
    "risk",
)
_SCHEMA_IDS = (
    "approval",
    "bundle",
    "invocation",
    "repository-state",
    "run",
    "snapshot",
    "stage",
)
_SCHEMA_TYPES = frozenset({"array", "boolean", "integer", "null", "number", "object", "string"})
_SCHEMA_KEYWORDS = frozenset(
    {
        "$defs", "$id", "$ref", "$schema", "additionalProperties", "allOf", "anyOf",
        "const", "description", "enum", "format", "if", "items", "maximum", "minimum",
        "minLength", "not", "oneOf", "pattern", "properties", "required", "then", "title",
        "type", "uniqueItems",
    }
)
def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8") + b"\n"


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid UTF-8 JSON in {label}: {error}") from error


def _source_text(path: Path) -> str:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"contract is not UTF-8: {path}") from error
    if "\r" in text or not text.strip() or not text.endswith("\n"):
        raise ValueError(f"contract must be non-empty LF UTF-8 ending in newline: {path}")
    return text


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class CoreBundle:
    protocol_version: int
    payload: Mapping[str, Any]


def _enum_values(enum_type: type[Enum]) -> list[str]:
    return sorted(item.value for item in enum_type.__members__.values())


def _contract_entry(path: Path) -> dict[str, str]:
    contract = _source_text(path)
    return {"contract": contract, "sha256": hashlib.sha256(contract.encode("utf-8")).hexdigest()}


def _workflow_entry(path: Path, workflow_id: str) -> dict[str, Any]:
    text = _source_text(path)
    first, separator, body = text.partition("\n")
    match = re.fullmatch(r"<!-- kapisch-workflow: (\{.*\}) -->", first)
    if not separator or not match:
        raise ValueError(f"workflow metadata header missing: {path}")
    metadata = _json_bytes(match.group(1).encode("utf-8"), str(path))
    if set(metadata) != {"id", "stages", "gates"} or metadata["id"] != workflow_id:
        raise ValueError(f"invalid workflow metadata: {path}")
    if not isinstance(metadata["stages"], list) or not isinstance(metadata["gates"], list):
        raise ValueError(f"workflow stages and gates must be arrays: {path}")
    if any(stage not in _enum_values(Stage) for stage in metadata["stages"]):
        raise ValueError(f"unknown workflow stage: {path}")
    if any(gate not in _enum_values(Gate) for gate in metadata["gates"]):
        raise ValueError(f"unknown workflow gate: {path}")
    if not body.strip():
        raise ValueError(f"workflow contract is empty: {path}")
    return {
        "stages": metadata["stages"],
        "gates": metadata["gates"],
        "contract": body,
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }


def _require_sources(directory: Path, suffix: str, expected_ids: tuple[str, ...]) -> None:
    expected = {f"{name}{suffix}" for name in expected_ids}
    actual = {path.name for path in directory.glob(f"*{suffix}") if path.is_file()}
    if actual != expected:
        raise ValueError(f"unexpected semantic source set in {directory}")


def _validate_schema_set(schemas: Mapping[str, Any]) -> None:
    if set(schemas) != set(_SCHEMA_IDS):
        raise ValueError("CoreBundle must contain only v3 authority schemas")
    by_id: dict[str, dict[str, Any]] = {}
    for name, schema in schemas.items():
        expected_id = f"kapisch://schemas/v3/{name}"
        if (
            not isinstance(schema, dict)
            or schema.get("type") != "object"
            or schema.get("$id") != expected_id
            or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        ):
            raise ValueError(f"CoreBundle contains an invalid or non-v3 authority schema: {name}")
        by_id[expected_id] = schema

    def resolve_pointer(target: Any, pointer: str, label: str) -> Any:
        if not pointer:
            return target
        if not pointer.startswith("/"):
            raise ValueError(f"invalid JSON Schema reference fragment: {label}")
        for raw_segment in unquote(pointer[1:]).split("/"):
            segment = raw_segment.replace("~1", "/").replace("~0", "~")
            if isinstance(target, dict) and segment in target:
                target = target[segment]
            elif isinstance(target, list):
                try:
                    index = int(segment)
                except ValueError as error:
                    raise ValueError(f"unresolved JSON Schema reference: {label}") from error
                if index < 0 or index >= len(target) or str(index) != segment:
                    raise ValueError(f"unresolved JSON Schema reference: {label}")
                target = target[index]
            else:
                raise ValueError(f"unresolved JSON Schema reference: {label}")
        return target

    checked: set[tuple[int, int]] = set()

    def check_schema(node: Any, root: dict[str, Any], label: str) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, dict):
            raise ValueError(f"invalid JSON Schema object: {label}")
        identity = (id(node), id(root))
        if identity in checked:
            return
        checked.add(identity)
        unknown = set(node) - _SCHEMA_KEYWORDS
        if unknown:
            raise ValueError(f"unsupported JSON Schema keyword in {label}: {sorted(unknown)[0]}")
        for key in ("$id", "$ref", "$schema", "description", "format", "title", "pattern"):
            if key in node and not isinstance(node[key], str):
                raise ValueError(f"invalid JSON Schema {key}: {label}")
        if "$schema" in node and node["$schema"] != "https://json-schema.org/draft/2020-12/schema":
            raise ValueError(f"unsupported JSON Schema dialect: {label}")
        if "type" in node:
            types = node["type"] if isinstance(node["type"], list) else [node["type"]]
            if not types or any(
                not isinstance(value, str) or value not in _SCHEMA_TYPES for value in types
            ) or len(set(types)) != len(types):
                raise ValueError(f"invalid JSON Schema type: {label}")
        if "required" in node and (
            not isinstance(node["required"], list)
            or any(not isinstance(item, str) for item in node["required"])
            or len(set(node["required"])) != len(node["required"])
        ):
            raise ValueError(f"invalid JSON Schema required list: {label}")
        if "enum" in node and (not isinstance(node["enum"], list) or not node["enum"]):
            raise ValueError(f"invalid JSON Schema enum: {label}")
        if "pattern" in node:
            try:
                re.compile(node["pattern"])
            except re.error as error:
                raise ValueError(f"invalid JSON Schema pattern: {label}") from error
        for key in ("minimum", "maximum"):
            if key in node and (isinstance(node[key], bool) or not isinstance(node[key], (int, float))):
                raise ValueError(f"invalid JSON Schema {key}: {label}")
        if "minLength" in node and (
            isinstance(node["minLength"], bool)
            or not isinstance(node["minLength"], int)
            or node["minLength"] < 0
        ):
            raise ValueError(f"invalid JSON Schema minLength: {label}")
        if "uniqueItems" in node and not isinstance(node["uniqueItems"], bool):
            raise ValueError(f"invalid JSON Schema uniqueItems: {label}")
        for key in ("properties", "$defs"):
            if key in node:
                if not isinstance(node[key], dict):
                    raise ValueError(f"invalid JSON Schema {key}: {label}")
                for name, child in node[key].items():
                    if not isinstance(name, str):
                        raise ValueError(f"invalid JSON Schema {key} entry: {label}")
                    check_schema(child, root, f"{label}/{key}/{name}")
        for key in ("items", "additionalProperties", "if", "then", "not"):
            if key in node:
                check_schema(node[key], root, f"{label}/{key}")
        for key in ("allOf", "anyOf", "oneOf"):
            if key in node:
                if not isinstance(node[key], list) or not node[key]:
                    raise ValueError(f"invalid JSON Schema {key}: {label}")
                for index, child in enumerate(node[key]):
                    check_schema(child, root, f"{label}/{key}/{index}")
        if "$ref" in node:
            reference = node["$ref"]
            schema_id, marker, fragment = reference.partition("#")
            reference_root = root if not schema_id else by_id.get(schema_id)
            if reference_root is None:
                raise ValueError(f"unresolved JSON Schema reference: {label}: {reference}")
            target = resolve_pointer(reference_root, fragment, f"{label}: {reference}") if marker else reference_root
            if not isinstance(target, (dict, bool)):
                raise ValueError(f"JSON Schema reference does not identify a schema: {label}: {reference}")
            check_schema(target, reference_root, f"{label}: {reference}")

    for name, schema in schemas.items():
        check_schema(schema, schema, name)


def compile_bundle(source_root: Path) -> bytes:
    root = Path(source_root)
    contracts = root / "contracts"
    _require_sources(contracts / "roles", ".md", _ROLE_IDS)
    _require_sources(contracts / "workflows", ".md", _WORKFLOW_IDS)
    _require_sources(contracts / "policy", ".md", _POLICY_IDS)
    _require_sources(root / "schemas/v3", ".json", _SCHEMA_IDS)
    roles = {name: _contract_entry(contracts / "roles" / f"{name}.md") for name in _ROLE_IDS}
    workflows = {
        name: _workflow_entry(contracts / "workflows" / f"{name}.md", name)
        for name in _WORKFLOW_IDS
    }
    policies = {
        name: _contract_entry(contracts / "policy" / f"{name}.md") for name in _POLICY_IDS
    }
    controller_instructions = _source_text(contracts / "controller.md")
    schemas: dict[str, Any] = {}
    for name in _SCHEMA_IDS:
        value = _json_bytes((root / "schemas/v3" / f"{name}.json").read_bytes(), name)
        schemas[name] = value
    _validate_schema_set(schemas)

    payload = {
        "protocol_version": 3,
        "vocabulary": {
            "roles": _enum_values(Role),
            "workflows": _enum_values(Workflow),
            "stages": _enum_values(Stage),
            "gates": _enum_values(Gate),
            "risks": _enum_values(Risk),
            "execution_classes": _enum_values(ExecutionClass),
            "logical_tiers": _enum_values(LogicalTier),
            "review_depths": _enum_values(ReviewDepth),
            "review_scopes": _enum_values(ReviewScope),
            "capability_effects": _enum_values(CapabilityEffect),
            "transitions": _enum_values(TransitionKind),
        },
        "roles": roles,
        "workflows": workflows,
        "policies": policies,
        "controller_instructions": controller_instructions,
        "schemas": schemas,
    }
    return canonical_json(payload)


def verify_bundle(data: bytes, digest: str) -> CoreBundle:
    if not isinstance(data, bytes) or not isinstance(digest, str):
        raise TypeError("bundle bytes and digest string are required")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("bundle digest must be lowercase SHA-256")
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("bundle SHA-256 mismatch")
    payload = _json_bytes(data, "bundle")
    if canonical_json(payload) != data:
        raise ValueError("bundle bytes are not canonical JSON")
    required = {
        "protocol_version",
        "vocabulary",
        "roles",
        "workflows",
        "policies",
        "controller_instructions",
        "schemas",
    }
    if not isinstance(payload, dict) or set(payload) != required or payload["protocol_version"] != 3:
        raise ValueError("invalid CoreBundle v3 top-level fields or protocol version")
    groups = ("vocabulary", "roles", "workflows", "policies", "schemas")
    if any(not isinstance(payload[name], dict) for name in groups):
        raise ValueError("CoreBundle contract collections must be objects")
    if set(payload["roles"]) != set(_ROLE_IDS):
        raise ValueError("CoreBundle must contain exactly six roles")
    if set(payload["workflows"]) != set(_WORKFLOW_IDS):
        raise ValueError("CoreBundle must contain exactly four workflows")
    if set(payload["policies"]) != set(_POLICY_IDS):
        raise ValueError("CoreBundle policy set is not canonical")
    if set(payload["schemas"]) != set(_SCHEMA_IDS):
        raise ValueError("CoreBundle must contain only v3 authority schemas")
    expected_vocabulary = {
        "roles": _enum_values(Role),
        "workflows": _enum_values(Workflow),
        "stages": _enum_values(Stage),
        "gates": _enum_values(Gate),
        "risks": _enum_values(Risk),
        "execution_classes": _enum_values(ExecutionClass),
        "logical_tiers": _enum_values(LogicalTier),
        "review_depths": _enum_values(ReviewDepth),
        "review_scopes": _enum_values(ReviewScope),
        "capability_effects": _enum_values(CapabilityEffect),
        "transitions": _enum_values(TransitionKind),
    }
    if payload["vocabulary"] != expected_vocabulary:
        raise ValueError("CoreBundle vocabulary differs from core protocol types")
    if not isinstance(payload["controller_instructions"], str) or not payload["controller_instructions"].strip():
        raise ValueError("CoreBundle controller instructions are missing")
    for group_name in ("roles", "policies"):
        for name, contract in payload[group_name].items():
            if not isinstance(contract, dict) or set(contract) != {"contract", "sha256"}:
                raise ValueError(f"invalid {group_name} contract: {name}")
            text = contract["contract"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"empty {group_name} contract: {name}")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != contract["sha256"]:
                raise ValueError(f"contract digest mismatch: {name}")
    for name, workflow in payload["workflows"].items():
        if not isinstance(workflow, dict) or set(workflow) != {"stages", "gates", "contract", "sha256"}:
            raise ValueError(f"invalid workflow metadata: {name}")
        if not isinstance(workflow["stages"], list) or not isinstance(workflow["gates"], list):
            raise ValueError(f"invalid workflow stage/gate metadata: {name}")
        if any(stage not in expected_vocabulary["stages"] for stage in workflow["stages"]):
            raise ValueError(f"unknown stage in workflow metadata: {name}")
        if any(gate not in expected_vocabulary["gates"] for gate in workflow["gates"]):
            raise ValueError(f"unknown gate in workflow metadata: {name}")
        text = workflow["contract"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"empty workflow contract: {name}")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != workflow["sha256"]:
            raise ValueError(f"workflow digest mismatch: {name}")
    _validate_schema_set(payload["schemas"])
    return CoreBundle(protocol_version=3, payload=_freeze(payload))


__all__ = ["CoreBundle", "canonical_json", "compile_bundle", "verify_bundle"]
