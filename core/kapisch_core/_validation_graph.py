from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ._validation_json import _json
from ._validation_schema import _matches
from .bundle import CoreBundle
from .storage import _read_contained, load_bundle


@dataclass(frozen=True)
class _GraphAuthority:
    workflow: str
    bundle_digest: str
    graph: Mapping[str, Any] | None
    approved_plan: Mapping[str, Any] | None
    history: tuple[Mapping[str, Any], ...]


def _validate_plan(
    repo: Path, run_id: str, ref: Mapping[str, Any]
) -> Mapping[str, Any]:
    body = _read_contained(repo, run_id, ref["path"])
    if hashlib.sha256(body).hexdigest() != ref["sha256"]:
        raise ValueError("approved plan digest mismatch")
    plan = _json(body, "approved plan")
    if not isinstance(plan, dict) or plan.get("plan_id") != ref["plan_id"]:
        raise ValueError("approved plan identity mismatch")
    return plan


def _validate_node_attempt_binding(
    graph: Mapping[str, Any] | None,
    plan: Mapping[str, Any] | None,
    attempt: Mapping[str, Any],
) -> None:
    if graph is None or plan is None:
        raise ValueError("node attempt lacks its approved graph/plan binding")
    evidence = attempt["evidence"]
    graph_refs = [ref for ref in evidence if ref["kind"] == "graph"]
    plan_refs = [ref for ref in evidence if ref["kind"] == "plan"]
    if (
        len(graph_refs) != 1
        or graph_refs[0]["path"] != graph["path"]
        or graph_refs[0]["sha256"] != graph["sha256"]
        or len(plan_refs) != 1
        or plan_refs[0]["path"] != plan["path"]
        or plan_refs[0]["sha256"] != plan["sha256"]
    ):
        raise ValueError(
            "node attempt creation evidence does not bind exact graph and plan version"
        )


def _validate_graph(
    repo: Path,
    run_id: str,
    authority: _GraphAuthority,
    plan_doc: Mapping[str, Any] | None,
) -> None:
    if authority.workflow != "milestone":
        return
    graph_ref = authority.graph
    if graph_ref is None:
        if any("node_id" in row for row in authority.history):
            raise ValueError("node-scoped attempt has no graph")
        return
    graph, bundle = _read_graph_document(repo, run_id, authority, graph_ref, plan_doc)
    nodes = _validate_graph_nodes(repo, run_id, graph, bundle)
    _validate_graph_attempts(authority, graph_ref, nodes)


def _read_graph_document(
    repo: Path,
    run_id: str,
    authority: _GraphAuthority,
    graph_ref: Mapping[str, Any],
    plan_doc: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], CoreBundle]:
    body = _read_contained(repo, run_id, graph_ref["path"])
    if hashlib.sha256(body).hexdigest() != graph_ref["sha256"]:
        raise ValueError("graph digest mismatch")
    graph = _json(body, "milestone graph")
    bundle = load_bundle(repo, authority.bundle_digest)
    root = bundle.payload["schemas"]["run"]
    errors: list[str] = []
    _matches(graph, root["$defs"]["graph_document"], root, bundle, errors, "graph")
    if errors:
        raise ValueError("; ".join(errors))
    if graph["run_id"] != run_id:
        raise ValueError("graph run identity mismatch")
    plan = authority.approved_plan
    if plan is None or plan_doc is None or plan["plan_id"] != graph["plan_id"]:
        raise ValueError("graph is not bound to current approved plan")
    if plan_doc.get("graph") != graph_ref:
        raise ValueError("approved plan does not bind exact graph path and digest")
    return graph, bundle


def _validate_graph_nodes(
    repo: Path, run_id: str, graph: Mapping[str, Any], bundle: CoreBundle
) -> Mapping[str, Mapping[str, Any]]:
    root = bundle.payload["schemas"]["run"]
    nodes: dict[str, Mapping[str, Any]] = {}
    for node in graph["nodes"]:
        node_id = node["node_id"]
        if re.fullmatch(r"n-[0-9a-f]{32}", node_id) is None:
            raise ValueError("graph node_id is invalid")
        if node_id in nodes:
            raise ValueError("duplicate milestone node identity")
        nodes[node_id] = node
        _validate_scope_document(repo, run_id, node, root, bundle)
    _validate_dependencies(nodes)
    return nodes


def _validate_scope_document(
    repo: Path,
    run_id: str,
    node: Mapping[str, Any],
    root: Mapping[str, Any],
    bundle: CoreBundle,
) -> None:
    scope_ref = node["scope"]
    scope_bytes = _read_contained(repo, run_id, scope_ref["path"])
    if hashlib.sha256(scope_bytes).hexdigest() != scope_ref["sha256"]:
        raise ValueError("milestone scope digest mismatch")
    scope = _json(scope_bytes, "milestone scope")
    errors: list[str] = []
    _matches(scope, root["$defs"]["scope_document"], root, bundle, errors, "scope")
    if errors:
        raise ValueError("; ".join(errors))
    if re.fullmatch(r"n-[0-9a-f]{32}", scope["node_id"]) is None:
        raise ValueError("scope node_id is invalid")
    if scope["run_id"] != run_id or scope["node_id"] != node["node_id"]:
        raise ValueError("scope run/node identity mismatch")


def _validate_dependencies(nodes: Mapping[str, Mapping[str, Any]]) -> None:
    for node in nodes.values():
        if any(
            re.fullmatch(r"n-[0-9a-f]{32}", dep) is None for dep in node["depends_on"]
        ):
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


def _validate_graph_attempts(
    authority: _GraphAuthority,
    graph_ref: Mapping[str, Any],
    nodes: Mapping[str, Mapping[str, Any]],
) -> None:
    attempts: set[str] = set()
    for row in authority.history:
        node_id = row.get("node_id")
        if node_id is None:
            continue
        node = nodes.get(node_id)
        if node is None or row["scope_digest"] != node["scope"]["sha256"]:
            raise ValueError("stage attempt does not bind exact milestone node scope")
        if row["stage_id"] not in attempts:
            _validate_node_attempt_binding(graph_ref, authority.approved_plan, row)
            attempts.add(row["stage_id"])
