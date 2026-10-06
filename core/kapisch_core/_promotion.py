from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ._locking import _locked
from ._plan_candidate import (
    load_plan_approval_candidate,
    retain_plan_approval_artifact,
    store_plan_approval_candidate,
    validate_plan_approval_candidate,
)
from ._state import (
    _publish_state_locked,
    _resync_state_locked,
    load_state,
    publish_state,
)
from .advisory import (
    ProposedScopeRef,
    _reference,
    load_proposed_scope,
)
from .bundle import canonical_json
from .storage import (
    _read_contained,
    _read_repository_file,
    load_authority_record,
    load_plan,
    retain_plan,
)

_PLAN_ROOT = ".kapisch/v3/authority/plans"


def _scope_ref(state: Mapping[str, Any]) -> ProposedScopeRef:
    value = state.get("scope_ref")
    if not isinstance(value, dict):
        raise ValueError("plan approval requires a persisted proposed scope")
    return _reference(value)


def validate_source_dependencies(
    repo: Path, dependencies: list[dict[str, str]]
) -> None:
    for dependency in dependencies:
        data = _read_repository_file(repo, dependency["path"])
        if hashlib.sha256(data).hexdigest() != dependency["sha256"]:
            raise ValueError("source dependency changed since GateApproval")


def _milestone_plan_document(
    plan_bytes: bytes, plan_id: str
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    from ._validation_json import _json

    document = _json(plan_bytes, "approved milestone plan")
    if not isinstance(document, dict) or document.get("plan_id") != plan_id:
        raise ValueError("milestone plan identity mismatch")
    graph_ref = document.get("graph")
    if not isinstance(graph_ref, dict) or set(graph_ref) != {"path", "sha256"}:
        raise ValueError("milestone plan must bind exact graph reference")
    return document, graph_ref


def _validate_current_graph(
    repo: Path,
    state: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    from ._validation_graph import _GraphAuthority, _validate_graph

    execution = candidate["execution_binding"]
    if state.get("graph") != execution["graph_ref"]:
        raise ValueError("current milestone graph differs from approved candidate")
    plan = {
        "plan_id": candidate["plan_ref"]["plan_id"],
        "path": candidate["plan_ref"]["path"],
        "sha256": candidate["plan_sha256"],
    }
    plan_doc, _ = _milestone_plan_document(
        load_plan(repo, plan["path"], plan["sha256"]), plan["plan_id"]
    )
    authority = _GraphAuthority(
        workflow="milestone",
        bundle_digest=candidate["bundle_digest"],
        graph=state["graph"],
        approved_plan=plan,
        history=tuple(state["history"]),
    )
    _validate_graph(repo, state["run_id"], authority, plan_doc)


def _candidate_execution_binding(
    repo: Path,
    state: Mapping[str, Any],
    plan_id: str,
    plan_ref: Mapping[str, str],
    plan_bytes: bytes,
) -> dict[str, Any]:
    if state["workflow"] != "milestone":
        if "graph" in state:
            raise ValueError("graph-free plan approval cannot contain a graph")
        return {"mode": "graph-free"}

    from ._validation_graph import _GraphAuthority, _validate_graph
    from ._validation_json import _json

    graph_ref = state.get("graph")
    if not isinstance(graph_ref, dict):
        raise ValueError("milestone plan approval requires retained graph bytes")
    plan_doc, bound_graph_ref = _milestone_plan_document(plan_bytes, plan_id)
    if bound_graph_ref != graph_ref:
        raise ValueError("milestone plan does not bind current graph reference")
    plan = {
        "plan_id": plan_id,
        "path": plan_ref["path"],
        "sha256": plan_ref["sha256"],
    }
    authority = _GraphAuthority(
        workflow="milestone",
        bundle_digest=state["bundle_digest"],
        graph=graph_ref,
        approved_plan=plan,
        history=tuple(state["history"]),
    )
    _validate_graph(repo, state["run_id"], authority, plan_doc)
    graph_bytes = _read_contained(repo, state["run_id"], graph_ref["path"])
    graph_doc = _json(graph_bytes, "milestone graph")
    retained_graph_ref = retain_plan_approval_artifact(repo, graph_bytes)
    node_scope_refs = []
    for node in graph_doc["nodes"]:
        scope_ref = node["scope"]
        scope_bytes = _read_contained(repo, state["run_id"], scope_ref["path"])
        if hashlib.sha256(scope_bytes).hexdigest() != scope_ref["sha256"]:
            raise ValueError("milestone scope digest mismatch")
        node_scope_refs.append(
            {
                "node_id": node["node_id"],
                "scope_ref": dict(scope_ref),
                "retained_ref": retain_plan_approval_artifact(repo, scope_bytes),
            }
        )
    node_scope_refs.sort(key=canonical_json)
    return {
        "mode": "milestone",
        "graph_ref": dict(graph_ref),
        "retained_graph_ref": retained_graph_ref,
        "node_scope_refs": node_scope_refs,
    }


def _payload_for_candidate(
    candidate: Mapping[str, Any], candidate_ref: Mapping[str, str]
) -> dict[str, Any]:
    return {
        "protocol_version": 3,
        "gate_contract": "human-gate/1",
        "run_id": candidate["run_id"],
        "gate_id": candidate["gate_id"],
        "identity": {"kind": "plan", "id": candidate["plan_ref"]["plan_id"]},
        "scope_digest": candidate["scope_ref"]["sha256"],
        "gate_kind": "plan-approval",
        "subject": {"plan_candidate_ref": dict(candidate_ref)},
    }


def _approval_reference_for_candidate(
    repo: Path,
    candidate: Mapping[str, Any],
    candidate_ref: Mapping[str, str],
    *,
    lock_held: bool = False,
) -> dict[str, str] | None:
    from ._gate_approval import _approval_id, _commit_record, load_gate_approval

    payload = _payload_for_candidate(candidate, candidate_ref)
    target_digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    approval_id = _approval_id(payload, target_digest)
    try:
        data = load_authority_record(repo, "gate-approvals", approval_id)
    except FileNotFoundError:
        return None
    reference = {"approval_id": approval_id, "sha256": hashlib.sha256(data).hexdigest()}
    _commit_record(repo, approval_id, data, lock_held=lock_held)
    record = load_gate_approval(repo, reference)
    if record["payload"] != payload:
        raise ValueError("retained GateApproval differs from exact candidate")
    return reference


def _repair_prior_candidate(
    repo: Path, state: Mapping[str, Any], new_reference: Mapping[str, str]
) -> None:
    old_reference = state.get("plan_candidate_ref")
    if old_reference is None or old_reference == new_reference:
        return
    candidate, _ = validate_plan_approval_candidate(repo, old_reference)
    reference = _approval_reference_for_candidate(
        repo, candidate, old_reference, lock_held=True
    )
    if reference is not None:
        from ._gate_approval import load_gate_approval

        record = load_gate_approval(repo, reference)
        old_plan_ref = _plan_ref_for_repo(repo, record, reference)
        current = load_state(repo, state["run_id"])
        _publish_plan_ref(
            repo, state["run_id"], old_plan_ref, state=current, lock_held=True
        )


def prepare_plan_approval(
    repo: Path,
    run_id: str,
    gate_id: str,
    plan_id: str,
    plan_bytes: bytes,
) -> dict[str, Any]:
    from ._authority_census import _active_authority_locked
    from ._gate_approval import _require_global_bundle
    from .storage import load_bundle

    repo = Path(repo)
    if not isinstance(plan_bytes, bytes):
        raise TypeError("plan bytes are required")
    if not isinstance(gate_id, str) or not gate_id:
        raise ValueError("gate_id must be a nonempty string")
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        _require_global_bundle(load_bundle(repo, state["bundle_digest"]))
        scope_ref = _scope_ref(state)
        scope = load_proposed_scope(repo, scope_ref)
        bindings = [dict(binding) for binding in _active_authority_locked(repo, scope_ref)]
        for binding in bindings:
            validate_source_dependencies(repo, binding["source_dependencies"])
        plan_ref = retain_plan(repo, plan_bytes)
        plan_reference = {
            "plan_id": plan_id,
            "path": plan_ref["path"],
        }
        execution_binding = _candidate_execution_binding(
            repo, state, plan_id, plan_ref, plan_bytes
        )
        candidate = {
            "protocol_version": 3,
            "candidate_contract": "plan-approval-candidate/1",
            "run_id": run_id,
            "gate_id": gate_id,
            "plan_ref": plan_reference,
            "plan_sha256": plan_ref["sha256"],
            "scope_ref": {
                "origin_run_id": scope["origin_run_id"],
                "scope_id": scope["scope_id"],
                "sha256": scope_ref.sha256,
            },
            "bundle_digest": state["bundle_digest"],
            "authority_basis": bindings,
            "execution_binding": execution_binding,
        }
        candidate_ref = store_plan_approval_candidate(repo, candidate)
        validate_plan_approval_candidate(repo, candidate_ref)
        _repair_prior_candidate(repo, state, candidate_ref)
        state = load_state(repo, run_id)
        if state.get("plan_candidate_ref") != candidate_ref:
            updated = dict(state)
            revision = state["revision"]
            updated["revision"] = revision + 1
            updated["plan_candidate_ref"] = candidate_ref
            _publish_state_locked(repo, run_id, updated, revision)
        else:
            _resync_state_locked(repo, run_id, state)
    candidate, _ = load_plan_approval_candidate(repo, candidate_ref)
    return _payload_for_candidate(candidate, candidate_ref)


def validate_plan_payload(
    repo: Path,
    payload: dict[str, Any],
    state: Mapping[str, Any] | None,
    *,
    require_current_authority: bool = False,
    lock_held: bool = False,
) -> None:
    candidate_ref = payload["subject"]["plan_candidate_ref"]
    candidate, _ = validate_plan_approval_candidate(repo, candidate_ref)
    plan_id = candidate["plan_ref"]["plan_id"]
    if (
        payload["run_id"] != candidate["run_id"]
        or payload["gate_id"] != candidate["gate_id"]
        or payload["identity"] != {"kind": "plan", "id": plan_id}
        or payload["scope_digest"] != candidate["scope_ref"]["sha256"]
        or payload["subject"] != {"plan_candidate_ref": dict(candidate_ref)}
    ):
        raise ValueError("GateApproval payload differs from exact plan candidate")
    if require_current_authority:
        if state is None:
            raise ValueError("plan approval requires current run state")
        if lock_held:
            _validate_current_candidate(repo, state, candidate, candidate_ref)
        else:
            with _locked(Path(repo), payload["run_id"]):
                current = load_state(repo, payload["run_id"])
                _validate_current_candidate(repo, current, candidate, candidate_ref)


def _validate_current_candidate(
    repo: Path,
    state: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_ref: Mapping[str, str],
) -> None:
    from ._authority_census import _active_authority_locked

    if (
        state["run_id"] != candidate["run_id"]
        or state["bundle_digest"] != candidate["bundle_digest"]
        or state.get("plan_candidate_ref") != dict(candidate_ref)
    ):
        raise ValueError("current run does not anchor exact plan candidate")
    current_scope = _scope_ref(state)
    if {
        "origin_run_id": current_scope.origin_run_id,
        "scope_id": current_scope.scope_id,
        "sha256": current_scope.sha256,
    } != candidate["scope_ref"]:
        raise ValueError("plan approval scope differs from current run scope")
    load_proposed_scope(repo, current_scope)
    execution = candidate["execution_binding"]
    if execution["mode"] == "milestone":
        if state["workflow"] != "milestone":
            raise ValueError("milestone candidate requires milestone run")
        _validate_current_graph(repo, state, candidate)
    elif state["workflow"] == "milestone" or "graph" in state:
        raise ValueError("graph-free candidate cannot authorize milestone graph")
    current_bindings = list(_active_authority_locked(repo, current_scope))
    if canonical_json(current_bindings) != canonical_json(candidate["authority_basis"]):
        raise ValueError("plan approval authority bindings are stale")
    for binding in current_bindings:
        validate_source_dependencies(repo, binding["source_dependencies"])


def _publish_plan_ref(
    repo: Path,
    run_id: str,
    plan_ref: dict[str, Any],
    *,
    state: Mapping[str, Any] | None = None,
    lock_held: bool = False,
) -> dict[str, Any]:
    state = load_state(repo, run_id) if state is None else state
    if state.get("approved_plan") == plan_ref:
        return plan_ref
    expected_revision = state["revision"]
    updated = dict(state)
    updated["revision"] = expected_revision + 1
    updated["approved_plan"] = plan_ref
    if lock_held:
        _publish_state_locked(repo, run_id, updated, expected_revision)
    else:
        publish_state(repo, run_id, updated, expected_revision=expected_revision)
    return plan_ref


def publish_plan_approval(
    repo: Path, payload: dict[str, Any], evidence: Any
) -> dict[str, Any]:
    from ._gate_approval import load_gate_approval, publish_gate_approval
    from ._locking import _locked

    if not isinstance(payload, dict):
        raise TypeError("plan approval payload must be an object")
    try:
        payload = json.loads(canonical_json(payload))
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("plan approval payload is not canonical JSON") from error
    subject = payload.get("subject")
    if not isinstance(subject, dict):
        raise ValueError("plan approval payload subject must be an object")
    if "plan_candidate_ref" not in subject:
        raise ValueError("plan approval payload subject must contain candidate reference")
    if set(subject) != {"plan_candidate_ref"}:
        raise ValueError("plan approval payload subject has invalid shape")
    candidate_reference = subject["plan_candidate_ref"]
    if not isinstance(candidate_reference, dict):
        raise ValueError("plan approval candidate reference must be an object")
    reference = dict(candidate_reference)
    candidate, _ = validate_plan_approval_candidate(repo, reference)
    if _payload_for_candidate(candidate, reference) != payload:
        raise ValueError("plan approval payload differs from exact candidate")
    existing = _approval_reference_for_candidate(repo, candidate, reference)
    if existing is None:
        existing = publish_gate_approval(repo, payload, evidence)
    record = load_gate_approval(repo, existing)
    if record["payload"] != payload:
        raise ValueError("retained plan approval differs from requested payload")
    run_id = payload["run_id"]
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        if state.get("plan_candidate_ref") != reference:
            raise ValueError("plan approval candidate is not current run anchor")
        return _publish_plan_ref(
            repo,
            run_id,
            _plan_ref_for_repo(repo, record, existing),
            state=state,
            lock_held=True,
        )


def _plan_ref_for_repo(
    repo: Path, record: dict[str, Any], reference: dict[str, str]
) -> dict[str, Any]:
    candidate, _ = load_plan_approval_candidate(
        repo, record["payload"]["subject"]["plan_candidate_ref"]
    )
    return {
        "plan_id": candidate["plan_ref"]["plan_id"],
        "path": candidate["plan_ref"]["path"],
        "plan_sha256": candidate["plan_sha256"],
        "gate_approval_ref": dict(reference),
    }


def recover_plan_approval(repo: Path, run_id: str, plan_id: str) -> dict[str, Any]:
    from ._gate_approval import load_gate_approval
    from ._locking import _locked

    repo = Path(repo)
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        candidate_ref = state.get("plan_candidate_ref")
        if not isinstance(candidate_ref, dict):
            raise ValueError("run has no exact plan candidate recovery reference")
        candidate, _ = validate_plan_approval_candidate(repo, candidate_ref)
        if candidate["run_id"] != run_id or candidate["plan_ref"]["plan_id"] != plan_id:
            raise ValueError(
                "persisted plan candidate identity differs from recovery request"
            )
        reference = _approval_reference_for_candidate(
            repo, candidate, candidate_ref, lock_held=True
        )
        if reference is None:
            raise ValueError("no GateApproval exists for exact plan candidate")
        record = load_gate_approval(repo, reference)
        return _publish_plan_ref(
            repo,
            run_id,
            _plan_ref_for_repo(repo, record, reference),
            state=state,
            lock_held=True,
        )


def promote_plan(repo: Path, run_id: str, plan_id: str) -> dict[str, Any]:
    repo = Path(repo)
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        plan_ref = state.get("approved_plan")
        if not isinstance(plan_ref, dict) or plan_ref.get("plan_id") != plan_id:
            raise ValueError("plan has no checked approval reference")
        from ._gate_approval import load_gate_approval

        record = load_gate_approval(repo, plan_ref["gate_approval_ref"])
        if record["payload"]["run_id"] != run_id:
            raise ValueError("approved plan belongs to another run")
        expected = _plan_ref_for_repo(repo, record, plan_ref["gate_approval_ref"])
        if expected != plan_ref:
            raise ValueError("checked PlanRef differs from GateApprovalRecord")
        validate_plan_payload(
            repo,
            record["payload"],
            state,
            require_current_authority=True,
            lock_held=True,
        )
        return plan_ref
