from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from ._validation_schema import (
    _matches,
    _validate_identity_contract,
    _validate_schema,
)
from .bundle import CoreBundle, canonical_json
from .storage import (
    load_authority_record,
    load_bundle,
    load_plan,
    store_authority_record,
)

_CANDIDATE_ROOT = ".kapisch/v3/authority/plan-approval-candidates"
_ARTIFACT_ROOT = ".kapisch/v3/authority/plan-approval-artifacts"
_PLAN_ROOT = ".kapisch/v3/authority/plans"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_FIELDS = {
    "protocol_version",
    "candidate_contract",
    "run_id",
    "gate_id",
    "plan_ref",
    "plan_sha256",
    "scope_ref",
    "bundle_digest",
    "authority_basis",
    "execution_binding",
}


def _exact_ref(value: object, root: str, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError(f"{label} reference has invalid shape")
    digest = value["sha256"]
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise ValueError(f"{label} reference digest is invalid")
    if value["path"] != f"{root}/{digest}.json":
        raise ValueError(f"{label} reference path is not canonical")
    return {"path": value["path"], "sha256": digest}


def _parse_candidate(data: bytes) -> dict[str, Any]:
    try:
        candidate = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("plan approval candidate is invalid JSON") from error
    if not isinstance(candidate, dict) or canonical_json(candidate) != data:
        raise ValueError("plan approval candidate is not canonical JSON")
    if set(candidate) != _CANDIDATE_FIELDS:
        raise ValueError("plan approval candidate has invalid shape")
    return candidate


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("plan approval candidate contains duplicate object key")
        result[key] = value
    return result


def _candidate_bundle(repo: Path, candidate: Mapping[str, Any]) -> CoreBundle:
    digest = candidate.get("bundle_digest")
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise ValueError("plan approval candidate bundle digest is invalid")
    try:
        bundle = load_bundle(repo, digest)
    except FileNotFoundError as error:
        raise ValueError("candidate's exact retained bundle is missing") from error
    if bundle.payload.get("authority_contract") != "global-authority/1":
        raise ValueError("unsupported-gate: candidate requires global-authority/1")
    approval_schema = bundle.payload["schemas"].get("approval")
    definitions = approval_schema.get("$defs") if isinstance(approval_schema, Mapping) else None
    if not isinstance(definitions, Mapping) or not isinstance(
        definitions.get("plan_approval_candidate"), Mapping
    ):
        raise ValueError(
            "unsupported-gate: retained bundle lacks plan-approval-candidate/1"
        )
    _validate_identity_contract(bundle)
    return bundle


def store_plan_approval_candidate(
    repo: Path, candidate: Mapping[str, Any]
) -> dict[str, str]:
    bundle = _candidate_bundle(Path(repo), candidate)
    _validate_schema(
        dict(candidate), "approval", bundle, definition_name="plan_approval_candidate"
    )
    data = canonical_json(dict(candidate))
    digest = hashlib.sha256(data).hexdigest()
    store_authority_record(Path(repo), "plan-approval-candidates", digest, data)
    if load_authority_record(Path(repo), "plan-approval-candidates", digest) != data:
        raise ValueError("plan approval candidate read-back mismatch")
    return {"path": f"{_CANDIDATE_ROOT}/{digest}.json", "sha256": digest}


def load_plan_approval_artifact(
    repo: Path, reference: Mapping[str, Any]
) -> bytes:
    ref = _exact_ref(reference, _ARTIFACT_ROOT, "plan approval artifact")
    data = load_authority_record(Path(repo), "plan-approval-artifacts", ref["sha256"])
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("retained plan approval artifact digest mismatch")
    return data


def retain_plan_approval_artifact(repo: Path, data: bytes) -> dict[str, str]:
    if not isinstance(data, bytes):
        raise TypeError("plan approval artifact must be bytes")
    digest = hashlib.sha256(data).hexdigest()
    store_authority_record(Path(repo), "plan-approval-artifacts", digest, data)
    reference = {"path": f"{_ARTIFACT_ROOT}/{digest}.json", "sha256": digest}
    if load_plan_approval_artifact(Path(repo), reference) != data:
        raise ValueError("retained plan approval artifact read-back mismatch")
    return reference


def load_plan_approval_candidate(
    repo: Path, reference: Mapping[str, Any]
) -> tuple[dict[str, Any], CoreBundle]:
    ref = _exact_ref(reference, _CANDIDATE_ROOT, "plan approval candidate")
    data = load_authority_record(Path(repo), "plan-approval-candidates", ref["sha256"])
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("plan approval candidate digest mismatch")
    candidate = _parse_candidate(data)
    bundle = _candidate_bundle(Path(repo), candidate)
    _validate_schema(
        candidate, "approval", bundle, definition_name="plan_approval_candidate"
    )
    return candidate, bundle


def _validate_authority_history(
    repo: Path, bindings: list[dict[str, Any]]
) -> None:
    from ._authority_records import _load_acceptance_history, _validate_graph
    from ._gate_approval import _validate_authority_basis

    _validate_authority_basis(bindings)
    acceptances = _load_acceptance_history(repo, bindings)
    _validate_graph(acceptances)
    by_identity = {
        (item.origin_run_id, item.snapshot_id, item.payload["subject"]["decision_id"]): item
        for item in acceptances
    }
    for binding in bindings:
        item = by_identity.get(
            (binding["origin_run_id"], binding["snapshot_id"], binding["decision_id"])
        )
        if item is None:
            raise ValueError("plan approval authority binding target is missing")
        subject = item.payload["subject"]
        expected = {
            "origin_run_id": item.origin_run_id,
            "snapshot_id": item.snapshot_id,
            "decision_id": subject["decision_id"],
            "acceptance_record_sha256": item.digest,
            "scope_ref": subject["scope_ref"],
            "applicability": subject["applicability"],
            "source_dependencies": subject["source_dependencies"],
        }
        if binding != expected:
            raise ValueError("plan approval authority binding differs from history")


def _validate_milestone_binding(
    repo: Path,
    candidate: Mapping[str, Any],
    plan: bytes,
    bundle: CoreBundle,
) -> None:
    from ._validation_graph import _validate_dependencies
    from ._validation_json import _json

    plan_doc = _json(plan, "approved milestone plan")
    execution = candidate["execution_binding"]
    graph_ref = execution["graph_ref"]
    if not isinstance(plan_doc, dict) or plan_doc.get("graph") != graph_ref:
        raise ValueError("approved plan does not bind exact milestone graph reference")
    if plan_doc.get("plan_id") != candidate["plan_ref"]["plan_id"]:
        raise ValueError("approved milestone plan identity mismatch")
    graph_bytes = load_plan_approval_artifact(repo, execution["retained_graph_ref"])
    if hashlib.sha256(graph_bytes).hexdigest() != graph_ref["sha256"]:
        raise ValueError("retained milestone graph differs from source reference")
    graph = _json(graph_bytes, "retained milestone graph")
    run_schema = bundle.payload["schemas"]["run"]
    errors: list[str] = []
    _matches(
        graph,
        run_schema["$defs"]["graph_document"],
        run_schema,
        bundle,
        errors,
        "graph",
    )
    if errors:
        raise ValueError("; ".join(errors))
    if (
        graph["run_id"] != candidate["run_id"]
        or graph["plan_id"] != candidate["plan_ref"]["plan_id"]
    ):
        raise ValueError("retained milestone graph identity mismatch")
    nodes: dict[str, Mapping[str, Any]] = {}
    for node in graph["nodes"]:
        node_id = node["node_id"]
        if node_id in nodes:
            raise ValueError("duplicate milestone node identity")
        nodes[node_id] = node
    _validate_dependencies(nodes)

    refs = execution["node_scope_refs"]
    encoded_refs = [canonical_json(ref) for ref in refs]
    if encoded_refs != sorted(encoded_refs) or len(encoded_refs) != len(set(encoded_refs)):
        raise ValueError("node_scope_refs must be sorted and unique")
    by_node = {ref["node_id"]: ref for ref in refs}
    if len(by_node) != len(refs) or set(by_node) != set(nodes):
        raise ValueError("candidate node-scope references do not match exact graph nodes")
    for node_id, node in nodes.items():
        ref = by_node[node_id]
        if ref["scope_ref"] != node["scope"]:
            raise ValueError("candidate node-scope reference differs from graph")
        retained_ref = _exact_ref(
            ref["retained_ref"], _ARTIFACT_ROOT, "retained node scope"
        )
        if retained_ref["sha256"] != node["scope"]["sha256"]:
            raise ValueError("retained node-scope digest differs from graph")
        scope_bytes = load_plan_approval_artifact(repo, retained_ref)
        scope = _json(scope_bytes, "retained milestone scope")
        errors = []
        _matches(
            scope,
            run_schema["$defs"]["scope_document"],
            run_schema,
            bundle,
            errors,
            "scope",
        )
        if errors:
            raise ValueError("; ".join(errors))
        if scope["run_id"] != candidate["run_id"] or scope["node_id"] != node_id:
            raise ValueError("retained scope run/node identity mismatch")


def validate_plan_approval_candidate(
    repo: Path, reference: Mapping[str, Any]
) -> tuple[dict[str, Any], CoreBundle]:
    candidate, bundle = load_plan_approval_candidate(repo, reference)
    plan_ref = candidate["plan_ref"]
    digest = candidate["plan_sha256"]
    if plan_ref["path"] != f"{_PLAN_ROOT}/{digest}.json":
        raise ValueError("candidate plan path is not canonical for its digest")
    try:
        plan = load_plan(repo, plan_ref["path"], digest)
    except FileNotFoundError as error:
        raise ValueError("exact plan bytes are not retained") from error
    if hashlib.sha256(plan).hexdigest() != digest:
        raise ValueError("candidate plan bytes digest mismatch")
    if not isinstance(plan_ref["plan_id"], str) or not plan_ref["plan_id"]:
        raise ValueError("candidate plan identity is invalid")
    from .advisory import load_proposed_scope_by_digest

    scope = load_proposed_scope_by_digest(repo, candidate["scope_ref"]["sha256"])
    if any(
        scope[key] != candidate["scope_ref"][key]
        for key in ("origin_run_id", "scope_id")
    ):
        raise ValueError("candidate scope reference differs from retained descriptor")
    _validate_authority_history(repo, candidate["authority_basis"])
    execution = candidate["execution_binding"]
    if execution["mode"] == "milestone":
        retained_graph_ref = _exact_ref(
            execution["retained_graph_ref"], _ARTIFACT_ROOT, "retained graph"
        )
        if retained_graph_ref["sha256"] != execution["graph_ref"]["sha256"]:
            raise ValueError("retained graph digest differs from source reference")
        _validate_milestone_binding(repo, candidate, plan, bundle)
    return candidate, bundle
