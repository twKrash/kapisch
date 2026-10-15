"""Lock-scoped Stage 4 binding publication and read-only historical consumption."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ._gate_approval import load_gate_approval
from ._history import _binding_rows
from ._invocation_inventory import _downstream_veto, _pre_dispatch_veto
from ._locking import _locked
from ._plan_candidate import validate_plan_approval_candidate
from ._review_target_records import _reservation_census, _unique_reservation
from ._state import (
    RunState,
    _commit_state_locked,
    _load_run_context,
    _prepare_state_locked,
)
from ._state import load_state as _load_state
from ._validation_inventory import _inventory as _validate_invocation_facts
from .bundle import canonical_json, supports_review_evidence, supports_stage_evidence
from .storage import _id


def _historical_plan(
    repo: Path, state: Mapping[str, Any], bundle: Any
) -> dict[str, Any]:
    if not supports_stage_evidence(bundle) or not supports_review_evidence(bundle):
        raise ValueError("retained bundle does not support stage and review evidence")
    if state["workflow"] != "task" or "graph" in state:
        raise ValueError("binding requires a graph-free task")
    candidate_ref = state.get("plan_candidate_ref")
    if not isinstance(candidate_ref, dict):
        raise ValueError("binding requires an exact approved candidate")
    candidate, _ = validate_plan_approval_candidate(repo, candidate_ref)
    if (
        candidate["run_id"] != state["run_id"]
        or candidate["bundle_digest"] != state["bundle_digest"]
        or candidate["execution_binding"] != {"mode": "graph-free"}
    ):
        raise ValueError(
            "binding candidate run, bundle, or execution identity mismatch"
        )
    plan = state.get("approved_plan")
    if not isinstance(plan, dict) or "gate_approval_ref" not in plan:
        raise ValueError("binding requires checked PlanRef and GateApproval")
    record = load_gate_approval(repo, plan["gate_approval_ref"])
    expected_plan = {
        "plan_id": candidate["plan_ref"]["plan_id"],
        "path": candidate["plan_ref"]["path"],
        "plan_sha256": candidate["plan_sha256"],
        "gate_approval_ref": plan["gate_approval_ref"],
    }
    payload = record["payload"]
    if (
        payload["gate_kind"] != "plan-approval"
        or payload["run_id"] != state["run_id"]
        or payload["subject"] != {"plan_candidate_ref": candidate_ref}
        or plan != expected_plan
    ):
        raise ValueError("checked PlanRef differs from exact historical approval chain")
    return candidate


def _checked_binding(
    row: Mapping[str, Any],
    records: tuple,
    state: Mapping[str, Any],
    candidate: Mapping[str, Any],
):
    if (
        row["role"] != "reviewer"
        or "node_id" in row
        or row["stage_kind"] not in {"review", "final"}
    ):
        raise ValueError("binding attempt is not an eligible reviewer")
    reservation, locator = _unique_reservation(
        records,
        row["stage_id"],
        state["plan_candidate_ref"],
        candidate["plan_ref"]["plan_id"],
    )
    purpose = {"review": "iteration", "final": "final"}[row["stage_kind"]]
    if reservation["purpose"] != purpose:
        raise ValueError("reservation purpose differs from attempt kind")
    if [
        item for item in row["evidence"] if item["kind"] == "review-target-binding/1"
    ] != [locator]:
        raise ValueError("proposed binding differs from unique persisted reservation")
    return reservation


def validate_existing_binding_locked(
    repo: Path, state: Mapping[str, Any], bundle: Any
) -> bool:
    """Validate historical facts only; no current authority or new-append gates."""
    rows = _binding_rows(state["history"])
    if not rows:
        return False
    candidate = _historical_plan(repo, state, bundle)
    records = _reservation_census(repo, state["run_id"])
    for row in rows:
        _checked_binding(row, records, state, candidate)
    return True


def validate_new_binding_locked(
    repo: Path, previous: RunState | None, proposed: RunState, bundle: Any
) -> None:
    old_rows = _binding_rows(previous["history"]) if previous else ()
    new_rows = _binding_rows(proposed["history"])
    additions = new_rows[len(old_rows) :]
    if not additions:
        return
    if previous is None or len(additions) != 1:
        raise ValueError("binding requires one separately durable creation")
    row = additions[0]
    if proposed["history"][len(previous["history"]) :] != [row]:
        raise ValueError("binding publication cannot batch creation or progression")
    prior = [
        item for item in previous["history"] if item["stage_id"] == row["stage_id"]
    ]
    if len(prior) != 1 or prior[0]["status"] != "planned":
        raise ValueError("binding requires the sole original planned observation")
    if any(
        proposed.get(field) != previous.get(field)
        for field in ("approved_plan", "plan_candidate_ref")
    ):
        raise ValueError("binding must cite the already persisted approval chain")
    candidate = _historical_plan(repo, previous, bundle)
    records = _reservation_census(repo, previous["run_id"])
    reservation = _checked_binding(row, records, previous, candidate)
    _pre_dispatch_veto(repo, previous["run_id"], previous, row["stage_id"])
    _validate_invocation_facts(
        repo,
        previous["run_id"],
        previous,
        bundle,
        validate_current_authority=False,
    )
    _downstream_veto(repo, previous["run_id"], previous, row["stage_id"], reservation)


def load_state(repo: Path, run_id: str) -> RunState:
    repo, run_id = Path(repo), _id(run_id, "run_id")
    with _locked(repo, run_id):
        state = _load_state(repo, run_id)
        _, bundle = _load_run_context(repo, run_id)
        if validate_existing_binding_locked(repo, state, bundle):
            from .validation import _validate_state

            _validate_state(repo, run_id, canonical_json(dict(state)))
        return state


def publish_state(
    repo: Path, run_id: str, state: Mapping[str, Any], expected_revision: int
) -> None:
    repo, run_id = Path(repo), _id(run_id, "run_id")
    with _locked(repo, run_id):
        previous, proposed = _prepare_state_locked(
            repo, run_id, state, expected_revision
        )
        _, bundle = _load_run_context(repo, run_id) if previous else (None, None)
        if previous:
            validate_existing_binding_locked(repo, previous, bundle)
            validate_new_binding_locked(repo, previous, proposed, bundle)
        elif _binding_rows(proposed["history"]):
            raise ValueError("binding requires separately durable creation")
        _commit_state_locked(repo, run_id, proposed)
