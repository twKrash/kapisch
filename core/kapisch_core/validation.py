from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._authority import _validate_state_snapshot
from ._state import _load_run_context
from ._validation_graph import _GraphAuthority, _validate_graph, _validate_plan
from ._validation_inventory import _inventory
from ._validation_schema import _validate_identity_contract, _validate_schema
from .bundle import CoreBundle, canonical_json
from .storage import (
    _close,
    _id,
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

def _validate_state(repo: Path, run_id: str, state_data: bytes) -> tuple[CoreBundle, Mapping[str, Any]]:
    try:
        state, bundle = _load_run_context(repo, run_id, state_data)
    except FileNotFoundError as error:
        raise _ValidationFailure("bundle-unavailable", "retained CoreBundle is missing") from error
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
    loaded_state, loaded_bundle = _load_run_context(repo, run_id)
    if canonical_json(dict(loaded_state)) != state_data or loaded_bundle.payload != bundle.payload:
        raise ValueError("run state changed during validation")
        raise ValueError("run state changed during validation")
    state = loaded_state
    _validate_state_snapshot(repo, run_id, state, bundle)
    _validate_schema(state, "run", bundle)
    for row in state["history"]:
        _validate_schema(row, "stage", bundle)
        for evidence in row["evidence"]:
            body = _read_contained(repo, run_id, evidence["path"])
            if hashlib.sha256(body).hexdigest() != evidence["sha256"]:
                raise ValueError("run history evidence digest mismatch")
    if bundle.payload.get("authority_contract") == "global-authority/1" and "approved_plan" in state:
        raise _ValidationFailure("unsupported-gate", "global-authority checked plan consumer is not implemented")
    plan_doc = _validate_plan(repo, run_id, state["approved_plan"]) if "approved_plan" in state else None
    graph_authority = _GraphAuthority(
        state["workflow"], state["bundle_digest"], state.get("graph"), state.get("approved_plan"),
        tuple(state["history"]),
    )
    _validate_graph(repo, run_id, graph_authority, plan_doc)
    try:
        _inventory(repo, run_id, state, bundle)
    except Exception as error:
        if "unsupported-gate:" in str(error):
            raise _ValidationFailure("unsupported-gate", str(error)) from error
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
        _validate_state(repo, run_id, state_data)
        if gate is not None:
            return [_error("unsupported-gate", f"gate {gate!r} is not implemented")]
        return []
    except _ValidationFailure as error:
        return [_error(error.code, str(error))]
    except FileNotFoundError:
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
        if "alters supported stage-attempt/1" in message:
            code = "identity-contract-unsupported"
        elif "bundle" in message.lower():
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
