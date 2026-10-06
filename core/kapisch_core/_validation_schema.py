from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from .bundle import CoreBundle, canonical_json


def _resolve_ref(
    bundle: CoreBundle, ref: str, local_root: Mapping[str, Any]
) -> tuple[Mapping[str, Any], str]:
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


def _matches(
    value: Any,
    schema: Mapping[str, Any],
    root: Mapping[str, Any],
    bundle: CoreBundle,
    errors: list[str],
    path: str,
) -> None:
    if "$ref" in schema:
        target, target_id = _resolve_ref(bundle, schema["$ref"], root)
        target_name = target_id.rsplit("/", 1)[-1]
        target_root = (
            root
            if schema["$ref"].startswith("#")
            else bundle.payload["schemas"][target_name]
        )
        _matches(value, target, target_root, bundle, errors, path)
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    type_ok = not types or any(
        (kind == "object" and isinstance(value, dict))
        or (kind == "array" and isinstance(value, list))
        or (kind == "string" and isinstance(value, str))
        or (
            kind == "integer" and isinstance(value, int) and not isinstance(value, bool)
        )
        or (
            kind == "number"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        )
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
        if (minimum is not None and value < minimum) or (
            maximum is not None and value > maximum
        ):
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
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(value) < minimum_items:
            errors.append(f"{path}: array has fewer than {minimum_items} items")
        if schema.get("uniqueItems") and len(
            {canonical_json(item) for item in value}
        ) != len(value):
            errors.append(f"{path}: duplicate array item")
        if "items" in schema:
            for index, item in enumerate(value):
                _matches(
                    item, schema["items"], root, bundle, errors, f"{path}[{index}]"
                )
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
            if (keyword == "anyOf" and not valid) or (
                keyword == "oneOf" and valid != 1
            ):
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


def _validate_schema(
    value: Any,
    schema_name: str,
    bundle: CoreBundle,
    *,
    definition_name: str | None = None,
) -> None:
    root = bundle.payload["schemas"][schema_name]
    schema = root
    if definition_name is not None:
        definitions = root.get("$defs")
        if not isinstance(definitions, Mapping) or not isinstance(
            definitions.get(definition_name), Mapping
        ):
            raise ValueError(
                f"schema definition is unavailable: {schema_name}#/$defs/{definition_name}"
            )
        schema = definitions[definition_name]
    errors: list[str] = []
    _matches(value, schema, root, bundle, errors, "$")
    if errors:
        raise ValueError("; ".join(errors))


def _require_schema_shape(
    label: str,
    schema: Any,
    required: set[str],
    constraints: Mapping[str, Mapping[str, Any]],
    allowed_properties: set[str] | None = None,
) -> None:
    schema_required = schema.get("required") if isinstance(schema, Mapping) else None
    if (
        not isinstance(schema, Mapping)
        or schema.get("type") != "object"
        or type(schema.get("additionalProperties")) is not bool
        or schema.get("additionalProperties")
        or not isinstance(schema_required, (list, tuple))
        or set(schema_required) != required
    ):
        raise ValueError(f"retained bundle weakens stage-attempt/1 {label} schema")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping) or (
        allowed_properties is not None and set(properties) != allowed_properties
    ):
        raise ValueError(f"retained bundle weakens stage-attempt/1 {label} schema")

    def matches(actual: Any, expected: Any) -> bool:
        if isinstance(actual, Mapping) and isinstance(expected, Mapping):
            return _identity_schema_shape(actual) == _identity_schema_shape(expected)
        return actual == expected

    for name, expected in constraints.items():
        actual = properties.get(name)
        if not isinstance(actual, Mapping) or any(
            (
                set(actual.get(key, [])) != set(value)
                if key == "enum"
                else not matches(actual.get(key), value)
            )
            for key, value in expected.items()
        ):
            raise ValueError(
                f"retained bundle weakens stage-attempt/1 {label}.{name} schema"
            )


_IDENTITY_SCHEMA_ANNOTATIONS = frozenset(
    {
        "$comment",
        "title",
        "description",
        "default",
        "deprecated",
        "readOnly",
        "writeOnly",
        "examples",
    }
)

_IDENTITY_SCHEMA_MAP_KEYWORDS = frozenset(
    {"$defs", "definitions", "properties", "patternProperties"}
)

_IDENTITY_SCHEMA_KEYWORDS = frozenset(
    {
        "additionalItems",
        "additionalProperties",
        "contains",
        "contentSchema",
        "else",
        "if",
        "items",
        "not",
        "propertyNames",
        "then",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
)

_IDENTITY_SCHEMA_ARRAY_KEYWORDS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})

_STAGE_ATTEMPT_SCHEMA_VARIANT = "stage-attempt/1"
_GLOBAL_AUTHORITY_STAGE_54_SCHEMA_VARIANT = "global-authority/1-stage-5.4"
_GLOBAL_AUTHORITY_STAGE_55_SCHEMA_VARIANT = "global-authority/1-stage-5.5"

_SUPPORTED_IDENTITY_SCHEMA_VARIANTS = {
    None: {
        "38ddaff3875010673d485689142ea500b3b6af85569942838ebbc91e1e22e108":
            _STAGE_ATTEMPT_SCHEMA_VARIANT,
    },
    "global-authority/1": {
        "48410162b2d3caa9518d26409e59eb929ee486a5837dbdfda324699f1b87a474":
            _GLOBAL_AUTHORITY_STAGE_54_SCHEMA_VARIANT,
        "e28299b3eb7f6a6084f480d870169c24d3da73a947591536b1f3bee39dba540b":
            _GLOBAL_AUTHORITY_STAGE_55_SCHEMA_VARIANT,
    },
}

# Preserve both gate-schema generations and pair each with its exact identity
# schema variant; cross-generation hybrids are not supported.
_SUPPORTED_GLOBAL_GATE_SCHEMA_DIGESTS = {
    "global-authority/1": frozenset(
        {
            "cf5cde51be87a37c5585c00dcc8ab64c66c4f83cff20a77d7bc2d6b0840332e0",
            "121b3d731ea2fd6b8e93f8c129ce3665c22763cacbbc43e075fef28f973dd980",
        }
    ),
}
_GLOBAL_GATE_SCHEMA_DIGEST_BY_IDENTITY_VARIANT = {
    _GLOBAL_AUTHORITY_STAGE_54_SCHEMA_VARIANT:
        "cf5cde51be87a37c5585c00dcc8ab64c66c4f83cff20a77d7bc2d6b0840332e0",
    _GLOBAL_AUTHORITY_STAGE_55_SCHEMA_VARIANT:
        "121b3d731ea2fd6b8e93f8c129ce3665c22763cacbbc43e075fef28f973dd980",
}

_RUN_COMMON_PROPERTIES = frozenset(
    {
        "protocol_version", "run_id", "bundle_digest", "workflow", "revision",
        "history", "identity_contract", "approved_plan", "graph", "amends",
        "supersedes",
    }
)
_RUN_DEFINITIONS = {
    _STAGE_ATTEMPT_SCHEMA_VARIANT: frozenset(
        {
            "graph_document", "graph_node", "graph_ref", "plan_ref",
            "scope_document", "scope_ref", "snapshot_ref",
        }
    ),
    _GLOBAL_AUTHORITY_STAGE_54_SCHEMA_VARIANT: frozenset(
        {
            "acceptance_ref", "graph_document", "graph_node", "graph_ref",
            "plan_ref", "scope_descriptor_ref", "scope_document", "scope_ref",
            "snapshot_ref",
        }
    ),
    _GLOBAL_AUTHORITY_STAGE_55_SCHEMA_VARIANT: frozenset(
        {
            "acceptance_ref", "graph_document", "graph_node", "graph_ref",
            "plan_ref", "scope_descriptor_ref", "scope_document", "scope_ref",
            "snapshot_ref",
        }
    ),
}
_RUN_PROPERTIES = {
    _STAGE_ATTEMPT_SCHEMA_VARIANT: _RUN_COMMON_PROPERTIES
    | frozenset({"accepted_snapshot"}),
    _GLOBAL_AUTHORITY_STAGE_54_SCHEMA_VARIANT: _RUN_COMMON_PROPERTIES
    | frozenset({"accepted_snapshot", "acceptance_ref", "scope_ref", "work_scope_refs"}),
    _GLOBAL_AUTHORITY_STAGE_55_SCHEMA_VARIANT: _RUN_COMMON_PROPERTIES
    | frozenset({
        "accepted_snapshot", "acceptance_ref", "scope_ref", "work_scope_refs",
        "plan_candidate_ref",
    }),
}


def _identity_schema_shape(value: Any, *, schema_node: bool = True) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, child in value.items():
            if schema_node and key in _IDENTITY_SCHEMA_ANNOTATIONS:
                continue
            if (
                schema_node
                and key in _IDENTITY_SCHEMA_MAP_KEYWORDS
                and isinstance(child, Mapping)
            ):
                result[key] = {
                    name: _identity_schema_shape(subschema)
                    for name, subschema in child.items()
                }
            elif schema_node and key in _IDENTITY_SCHEMA_KEYWORDS:
                result[key] = _identity_schema_shape(
                    child, schema_node=isinstance(child, Mapping)
                )
            elif (
                schema_node
                and key in _IDENTITY_SCHEMA_ARRAY_KEYWORDS
                and isinstance(child, (list, tuple))
            ):
                result[key] = [_identity_schema_shape(subschema) for subschema in child]
            else:
                result[key] = _identity_schema_shape(child, schema_node=False)
        return result
    if isinstance(value, (list, tuple)):
        return [_identity_schema_shape(child, schema_node=False) for child in value]
    return value


def _require_supported_identity_schemas(
    schemas: Mapping[str, Any], authority_contract: Any
) -> str:
    variants = _SUPPORTED_IDENTITY_SCHEMA_VARIANTS.get(authority_contract)
    shape = {
        name: _identity_schema_shape(schemas.get(name))
        for name in ("bundle", "invocation", "run", "stage")
    }
    if variants is None or any(
        not isinstance(schema, Mapping) for schema in shape.values()
    ):
        raise ValueError(
            "retained bundle alters supported stage-attempt/1 schema rules"
        )
    digest = hashlib.sha256(canonical_json(shape)).hexdigest()
    variant = variants.get(digest)
    if variant is None:
        raise ValueError(
            "retained bundle alters supported stage-attempt/1 schema rules"
        )
    return variant


def _require_supported_global_gate_schemas(
    schemas: Mapping[str, Any],
    authority_contract: str | None,
    identity_schema_variant: str,
) -> None:
    if authority_contract is None:
        return
    expected_digests = _SUPPORTED_GLOBAL_GATE_SCHEMA_DIGESTS.get(authority_contract)
    names = ("approval", "human-action", "scope")
    shape = {name: _identity_schema_shape(schemas.get(name)) for name in names}
    digest = hashlib.sha256(canonical_json(shape)).hexdigest()
    expected_variant_digest = _GLOBAL_GATE_SCHEMA_DIGEST_BY_IDENTITY_VARIANT.get(
        identity_schema_variant
    )
    if (
        expected_digests is None
        or any(not isinstance(schemas.get(name), Mapping) for name in names)
        or digest not in expected_digests
        or digest != expected_variant_digest
    ):
        raise ValueError(
            "retained bundle alters supported global-authority/1 gate schemas"
        )


def _validate_identity_contract(bundle: CoreBundle) -> None:
    schemas = bundle.payload["schemas"]
    contract = bundle.payload.get("authority_contract")
    if contract is not None and (
        not isinstance(contract, str) or contract != "global-authority/1"
    ):
        raise ValueError("unsupported authority contract")
    identity_schema_variant = _require_supported_identity_schemas(schemas, contract)
    _require_supported_global_gate_schemas(
        schemas, contract, identity_schema_variant
    )
    run = schemas.get("run")
    _validate_run_identity_schema(run, identity_schema_variant)
    definitions = run.get("$defs", {}) if isinstance(run, Mapping) else None
    _validate_graph_identity_schemas(definitions)
    _validate_stage_identity_schema(schemas.get("stage"))
    _validate_invocation_identity_schema(schemas.get("invocation"))


def _validate_run_identity_schema(run: Any, identity_schema_variant: str) -> None:
    if not isinstance(run, Mapping) or run.get("$id") != "kapisch://schemas/v3/run":
        raise ValueError("retained bundle lacks supported stage-attempt/1 run schema")
    _require_schema_shape(
        "run",
        run,
        {
            "protocol_version",
            "run_id",
            "bundle_digest",
            "workflow",
            "revision",
            "history",
            "identity_contract",
        },
        {
            "protocol_version": {"const": 3},
            "identity_contract": {"const": "stage-attempt/1"},
            "bundle_digest": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
            "workflow": {"enum": ["advisory", "review", "task", "milestone"]},
            "history": {
                "type": "array",
                "items": {"$ref": "kapisch://schemas/v3/stage"},
            },
            "approved_plan": {"$ref": "#/$defs/plan_ref"},
            "graph": {"$ref": "#/$defs/graph_ref"},
        },
        set(_RUN_PROPERTIES.get(identity_schema_variant, ())),
    )
    definitions = run.get("$defs")
    if (
        not isinstance(definitions, Mapping)
        or set(definitions) != set(_RUN_DEFINITIONS.get(identity_schema_variant, ()))
    ):
        raise ValueError("retained bundle alters supported stage-attempt/1 run definitions")


def _validate_graph_identity_schemas(definitions: Any) -> None:
    if not isinstance(definitions, Mapping):
        definitions = {}
    _require_schema_shape(
        "graph_ref",
        definitions.get("graph_ref"),
        {"path", "sha256"},
        {
            "path": {"type": "string", "minLength": 1},
            "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
        },
        {"path", "sha256"},
    )
    _require_schema_shape(
        "graph_document",
        definitions.get("graph_document"),
        {"protocol_version", "run_id", "plan_id", "nodes"},
        {
            "protocol_version": {"const": 3},
            "run_id": {"type": "string", "minLength": 1},
            "plan_id": {"type": "string", "minLength": 1},
            "nodes": {"type": "array", "items": {"$ref": "#/$defs/graph_node"}},
        },
        {"protocol_version", "run_id", "plan_id", "nodes"},
    )
    _require_schema_shape(
        "graph_node",
        definitions.get("graph_node"),
        {"node_id", "scope", "depends_on"},
        {
            "node_id": {"type": "string", "pattern": r"^n-[0-9a-f]{32}$"},
            "scope": {"$ref": "#/$defs/scope_ref"},
            "depends_on": {
                "type": "array",
                "items": {"type": "string", "pattern": r"^n-[0-9a-f]{32}$"},
                "uniqueItems": True,
            },
        },
        {"node_id", "scope", "depends_on"},
    )
    _require_schema_shape(
        "scope_ref",
        definitions.get("scope_ref"),
        {"path", "sha256"},
        {
            "path": {"type": "string", "minLength": 1},
            "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
        },
        {"path", "sha256"},
    )
    _require_schema_shape(
        "scope_document",
        definitions.get("scope_document"),
        {"protocol_version", "run_id", "node_id", "requirements"},
        {
            "protocol_version": {"const": 3},
            "run_id": {"type": "string", "minLength": 1},
            "node_id": {"type": "string", "pattern": r"^n-[0-9a-f]{32}$"},
            "requirements": {"type": "string", "minLength": 1},
        },
        {"protocol_version", "run_id", "node_id", "requirements"},
    )


def _validate_stage_identity_schema(stage: Any) -> None:
    if (
        not isinstance(stage, Mapping)
        or stage.get("$id") != "kapisch://schemas/v3/stage"
    ):
        raise ValueError("retained bundle lacks supported stage-attempt/1 stage schema")
    _require_schema_shape(
        "stage",
        stage,
        {
            "stage_id",
            "stage_kind",
            "sequence",
            "role",
            "status",
            "producer",
            "evidence",
            "scope_digest",
        },
        {
            "stage_id": {"type": "string", "pattern": r"^s-[0-9a-f]{32}$"},
            "stage_kind": {
                "enum": [
                    "bounded-delegate",
                    "design",
                    "final",
                    "gate",
                    "implement",
                    "research",
                    "review",
                ]
            },
            "sequence": {"type": "integer", "minimum": 0},
            "role": {
                "enum": [
                    "architect",
                    "researcher",
                    "implementer",
                    "implementer-lite",
                    "mechanic",
                    "reviewer",
                ]
            },
            "status": {
                "enum": [
                    "planned",
                    "dispatch-uncertain",
                    "complete",
                    "blocked",
                    "failed",
                    "interrupted",
                ]
            },
            "producer": {"const": "controller"},
            "scope_digest": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
            "evidence": {"type": "array", "items": {"$ref": "#/$defs/evidence"}},
            "node_id": {"pattern": r"^n-[0-9a-f]{32}$"},
            "retry_of_stage_id": {"pattern": r"^s-[0-9a-f]{32}$"},
        },
        {
            "stage_id",
            "stage_kind",
            "sequence",
            "role",
            "status",
            "producer",
            "evidence",
            "scope_digest",
            "node_id",
            "retry_of_stage_id",
        },
    )
    stage_defs = stage.get("$defs", {})
    evidence = stage_defs.get("evidence") if isinstance(stage_defs, Mapping) else None
    _require_schema_shape(
        "stage evidence",
        evidence,
        {"kind", "path", "sha256"},
        {
            "kind": {"type": "string"},
            "path": {"type": "string"},
            "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
        },
        {"kind", "path", "sha256"},
    )


def _validate_invocation_identity_schema(invocation: Any) -> None:
    if (
        not isinstance(invocation, Mapping)
        or invocation.get("$id") != "kapisch://schemas/v3/invocation"
    ):
        raise ValueError(
            "retained bundle lacks supported stage-attempt/1 invocation schema"
        )
    _require_schema_shape(
        "invocation",
        invocation,
        {
            "protocol_version",
            "run_id",
            "operation_id",
            "stage_id",
            "role",
            "request_digest",
            "status",
            "request",
            "adapter_binding",
        },
        {
            "protocol_version": {"const": 3},
            "operation_id": {"pattern": r"^op-[0-9a-f]{32}$"},
            "stage_id": {"pattern": r"^s-[0-9a-f]{32}$"},
            "role": {
                "enum": [
                    "architect",
                    "researcher",
                    "implementer",
                    "implementer-lite",
                    "mechanic",
                    "reviewer",
                ]
            },
            "request_digest": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
            "status": {
                "enum": ["planned", "dispatch-uncertain", "observed", "blocked"]
            },
            "request": {"type": "object", "additionalProperties": False},
            "adapter_binding": {"type": "object", "additionalProperties": False},
        },
        {
            "protocol_version",
            "run_id",
            "operation_id",
            "stage_id",
            "role",
            "request_digest",
            "status",
            "request",
            "adapter_binding",
        },
    )
    properties = invocation.get("properties", {})
    if not isinstance(properties, Mapping):
        properties = {}
    _require_schema_shape(
        "invocation request",
        properties.get("request"),
        {"path", "sha256"},
        {
            "path": {"type": "string", "minLength": 1},
            "sha256": {"$ref": "kapisch://schemas/v3/bundle#/$defs/digest"},
        },
        {"path", "sha256"},
    )
    _require_schema_shape(
        "adapter binding",
        properties.get("adapter_binding"),
        {"adapter_id", "lookup_context"},
        {
            "adapter_id": {"type": "string", "minLength": 1},
            "lookup_context": {"type": "string", "minLength": 1},
        },
        {"adapter_id", "lookup_context"},
    )
