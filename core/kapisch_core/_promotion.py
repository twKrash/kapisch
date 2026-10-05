from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ._authority_census import _active_authority_locked
from ._locking import _locked
from ._state import load_state, publish_state
from .advisory import (
    ProposedScopeRef,
    _reference,
    load_proposed_scope,
    load_proposed_scope_by_digest,
)
from .bundle import canonical_json
from .storage import (
    _read_contained,
    _read_repository_file,
    load_authority_record,
    load_authority_records,
    load_plan,
    retain_plan,
)

_PLAN_ROOT = ".kapisch/v3/authority/plans"


def _scope_ref(state: Mapping[str, Any]) -> ProposedScopeRef:
    value = state.get("scope_ref")
    if not isinstance(value, dict):
        raise ValueError("plan approval requires a persisted proposed scope")
    return _reference(value)


def _validate_plan_run_state(
    repo: Path, state: Mapping[str, Any], plan_id: str
) -> ProposedScopeRef:
    scope_ref = _scope_ref(state)
    load_proposed_scope(repo, scope_ref)
    if state.get("workflow") == "milestone":
        graph = state.get("graph")
        if not isinstance(graph, dict):
            raise ValueError("milestone plan approval requires retained graph bytes")
        try:
            graph_bytes = _read_contained(repo, state["run_id"], graph["path"])
            graph_doc = json.loads(graph_bytes.decode("utf-8"))
        except (
            FileNotFoundError,
            KeyError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError("milestone plan graph is missing or invalid") from error
        if (
            hashlib.sha256(graph_bytes).hexdigest() != graph["sha256"]
            or not isinstance(graph_doc, dict)
            or graph_doc.get("run_id") != state["run_id"]
            or graph_doc.get("plan_id") != plan_id
        ):
            raise ValueError("milestone plan graph does not match approved plan")
    elif "graph" in state:
        raise ValueError("graph-free plan approval cannot contain a graph")
    return scope_ref


def validate_source_dependencies(
    repo: Path, dependencies: list[dict[str, str]]
) -> None:
    for dependency in dependencies:
        data = _read_repository_file(repo, dependency["path"])
        if hashlib.sha256(data).hexdigest() != dependency["sha256"]:
            raise ValueError("source dependency changed since GateApproval")


def _validate_binding_history(repo: Path, bindings: list[dict[str, Any]]) -> None:
    from ._authority_records import _load_acceptances, _validate_graph

    acceptances = _load_acceptances(repo)
    _validate_graph(acceptances)
    by_identity = {
        (
            item.origin_run_id,
            item.snapshot_id,
            item.payload["subject"]["decision_id"],
        ): item
        for item in acceptances
    }
    for binding in bindings:
        identity = (
            binding["origin_run_id"],
            binding["snapshot_id"],
            binding["decision_id"],
        )
        acceptance = by_identity.get(identity)
        if acceptance is None:
            raise ValueError("plan approval authority binding target is missing")
        subject = acceptance.payload["subject"]
        expected = {
            "origin_run_id": acceptance.origin_run_id,
            "snapshot_id": acceptance.snapshot_id,
            "decision_id": subject["decision_id"],
            "acceptance_record_sha256": acceptance.digest,
            "scope_ref": subject["scope_ref"],
            "applicability": subject["applicability"],
            "source_dependencies": subject["source_dependencies"],
        }
        if binding != expected:
            raise ValueError("plan approval authority binding differs from history")


def prepare_plan_approval(
    repo: Path,
    run_id: str,
    gate_id: str,
    plan_id: str,
    plan_bytes: bytes,
) -> dict[str, Any]:
    from ._gate_approval import _require_global_bundle
    from .storage import load_bundle

    repo = Path(repo)
    if not isinstance(plan_bytes, bytes):
        raise TypeError("plan bytes are required")
    if not isinstance(gate_id, str) or not gate_id:
        raise ValueError("gate_id must be a nonempty string")
    state = load_state(repo, run_id)
    _require_global_bundle(load_bundle(repo, state["bundle_digest"]))
    scope_ref = _validate_plan_run_state(repo, state, plan_id)
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        scope_ref = _validate_plan_run_state(repo, state, plan_id)
        bindings = [
            dict(binding) for binding in _active_authority_locked(repo, scope_ref)
        ]
        for binding in bindings:
            validate_source_dependencies(repo, binding["source_dependencies"])
        plan_ref = retain_plan(repo, plan_bytes)
    digest = plan_ref["sha256"]
    return {
        "protocol_version": 3,
        "gate_contract": "human-gate/1",
        "run_id": run_id,
        "gate_id": gate_id,
        "identity": {"kind": "plan", "id": plan_id},
        "scope_digest": scope_ref.sha256,
        "gate_kind": "plan-approval",
        "subject": {
            "plan_ref": {
                "plan_id": plan_id,
                "path": f"{_PLAN_ROOT}/{digest}.json",
            },
            "plan_sha256": digest,
            "authority_basis": bindings,
        },
    }


def validate_plan_payload(
    repo: Path,
    payload: dict[str, Any],
    state: Mapping[str, Any] | None,
    *,
    require_current_authority: bool = False,
    lock_held: bool = False,
) -> None:
    subject = payload["subject"]
    plan_ref = subject["plan_ref"]
    plan_id = plan_ref["plan_id"]
    digest = subject["plan_sha256"]
    if payload["identity"]["id"] != plan_id:
        raise ValueError("GateApproval identity differs from plan reference")
    try:
        retained = load_plan(repo, plan_ref["path"], digest)
    except FileNotFoundError as error:
        raise ValueError("exact plan bytes are not retained") from error
    if hashlib.sha256(retained).hexdigest() != digest:
        raise ValueError("retained plan bytes differ from GateApproval")

    scope = load_proposed_scope_by_digest(repo, payload["scope_digest"])
    scope_ref = ProposedScopeRef(
        scope["origin_run_id"], scope["scope_id"], payload["scope_digest"]
    )
    if state is not None:
        if state["run_id"] != payload["run_id"]:
            raise ValueError("plan approval run identity mismatch")
        persisted_scope = _validate_plan_run_state(repo, state, plan_id)
        if persisted_scope != scope_ref:
            raise ValueError("plan approval scope differs from persisted run scope")

    bindings = subject["authority_basis"]
    _validate_binding_history(repo, bindings)
    if require_current_authority:
        if state is None:
            raise ValueError("plan approval requires its retained run state")

        def validate_current() -> None:
            current = list(_active_authority_locked(Path(repo), scope_ref))
            if canonical_json(current) != canonical_json(bindings):
                raise ValueError("plan approval authority bindings are stale")
            for binding in current:
                validate_source_dependencies(repo, binding["source_dependencies"])

        if lock_held:
            validate_current()
        else:
            with _locked(Path(repo), payload["run_id"]):
                validate_current()


def _approval_reference(repo: Path, approval_id: str) -> dict[str, str]:
    data = load_authority_record(repo, "gate-approvals", approval_id)
    return {
        "approval_id": approval_id,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _plan_ref(record: dict[str, Any], reference: dict[str, str]) -> dict[str, Any]:
    subject = record["payload"]["subject"]
    return {
        "plan_id": subject["plan_ref"]["plan_id"],
        "path": subject["plan_ref"]["path"],
        "plan_sha256": subject["plan_sha256"],
        "gate_approval_ref": dict(reference),
    }


def _publish_plan_ref(
    repo: Path, run_id: str, plan_ref: dict[str, Any]
) -> dict[str, Any]:
    state = load_state(repo, run_id)
    if state.get("approved_plan") == plan_ref:
        return plan_ref
    expected_revision = state["revision"]
    state["revision"] = expected_revision + 1
    state["approved_plan"] = plan_ref
    publish_state(repo, run_id, state, expected_revision=expected_revision)
    return plan_ref


def publish_plan_approval(
    repo: Path, payload: dict[str, Any], evidence: Any
) -> dict[str, Any]:
    from ._gate_approval import (
        _approval_id,
        load_gate_approval,
        publish_gate_approval,
    )

    repo = Path(repo)
    payload_bytes = canonical_json(payload)
    approval_id = _approval_id(payload, hashlib.sha256(payload_bytes).hexdigest())
    try:
        reference = _approval_reference(repo, approval_id)
    except FileNotFoundError:
        reference = publish_gate_approval(repo, payload, evidence)
    record = load_gate_approval(repo, reference)
    if record["payload"] != json.loads(payload_bytes.decode("utf-8")):
        raise ValueError("retained plan approval differs from requested payload")
    plan_ref = _plan_ref(record, reference)
    return _publish_plan_ref(repo, payload["run_id"], plan_ref)


def recover_plan_approval(repo: Path, run_id: str, plan_id: str) -> dict[str, Any]:
    from ._gate_approval import load_gate_approval

    repo = Path(repo)
    matches = []
    for approval_id, data in load_authority_records(repo, "gate-approvals"):
        try:
            record = json.loads(data.decode("utf-8"))
            payload = record["payload"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ValueError(
                "gate approval inventory contains malformed record"
            ) from error
        if (
            not isinstance(payload, dict)
            or payload.get("gate_kind") != "plan-approval"
            or payload.get("run_id") != run_id
            or payload.get("identity", {}).get("id") != plan_id
        ):
            continue
        reference = {
            "approval_id": approval_id,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        valid = load_gate_approval(repo, reference)
        validate_plan_payload(repo, valid["payload"], load_state(repo, run_id))
        matches.append((valid, reference))
    if len(matches) != 1:
        raise ValueError("plan approval recovery is missing or ambiguous")
    record, reference = matches[0]
    return _publish_plan_ref(repo, run_id, _plan_ref(record, reference))


def promote_plan(repo: Path, run_id: str, plan_id: str) -> dict[str, Any]:
    from ._gate_approval import load_gate_approval

    repo = Path(repo)
    state = load_state(repo, run_id)
    plan_ref = state.get("approved_plan")
    if not isinstance(plan_ref, dict) or plan_ref.get("plan_id") != plan_id:
        raise ValueError("plan has no checked approval reference")
    record = load_gate_approval(repo, plan_ref["gate_approval_ref"])
    if record["payload"]["run_id"] != run_id:
        raise ValueError("approved plan belongs to another run")
    expected = _plan_ref(record, plan_ref["gate_approval_ref"])
    if expected != plan_ref:
        raise ValueError("checked PlanRef differs from GateApprovalRecord")
    validate_plan_payload(
        repo, record["payload"], state, require_current_authority=True
    )
    return plan_ref
