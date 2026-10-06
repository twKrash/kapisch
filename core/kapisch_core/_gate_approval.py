from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._human_action_ownership import load_human_action_claim, publish_human_action_claim
from ._human_evidence import (
    ExternalArtifactInput,
    GateApprovalTarget,
    GateIdentity,
    ObservedGateAction,
    _validate_gate_approval_target,
    _validate_human_approval_bytes,
    validate_external_human_approval_artifact,
)
from ._locking import _locked
from ._state import _resync_state_locked, load_state
from ._validation_schema import _validate_identity_contract, _validate_schema
from .advisory import (
    _validate_applicability,
    load_proposed_scope,
    load_proposed_scope_by_digest,
)
from .bundle import CoreBundle, canonical_json
from .storage import (
    _close,
    _run_dir,
    load_authority_record,
    load_bundle,
    load_human_approval_artifact,
    retain_human_approval_artifact,
    store_authority_record,
)

_NAMESPACE = "gate-approvals"
_RECORD_FIELDS = {
    "protocol_version",
    "approval_contract",
    "approval_id",
    "payload",
    "approved_target_sha256",
    "human_authority",
}
_REFERENCE_FIELDS = {"approval_id", "sha256"}
_APPROVAL_ID = re.compile(r"^ga-[0-9a-f]{64}$")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("gate approval contains duplicate object key")
        result[key] = value
    return result


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"gate approval {label} has invalid shape")
    return value


def _parse_record(data: bytes) -> dict[str, Any]:
    try:
        record = json.loads(data, object_pairs_hook=_unique_pairs)
    except RecursionError as error:
        raise ValueError("gate approval exceeds supported nesting depth") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("gate approval is invalid JSON") from error
    if not isinstance(record, dict) or canonical_json(record) != data:
        raise ValueError("gate approval is noncanonical")
    return record


def _approval_id(payload: Mapping[str, Any], target_digest: str) -> str:
    identity = {
        "run_id": payload["run_id"],
        "gate_id": payload["gate_id"],
        "identity": payload["identity"],
        "approved_target_sha256": target_digest,
    }
    return f"ga-{hashlib.sha256(canonical_json(identity)).hexdigest()}"


def _target(payload: Mapping[str, Any], payload_digest: str) -> GateApprovalTarget:
    identity = payload["identity"]
    return GateApprovalTarget(
        payload["run_id"],
        payload["gate_id"],
        GateIdentity(identity["kind"], identity["id"]),
        payload_digest,
        payload["scope_digest"],
    )


def _require_global_bundle(bundle: CoreBundle) -> CoreBundle:
    if bundle.payload.get("authority_contract") != "global-authority/1":
        raise ValueError("unsupported-gate: GateApproval requires global-authority/1")
    _validate_identity_contract(bundle)
    return bundle


def _record_bundle(
    repo: Path, payload: Mapping[str, Any]
) -> tuple[CoreBundle, Mapping[str, Any] | None]:
    gate_kind = payload.get("gate_kind")
    if gate_kind == "repository-decision":
        subject = payload.get("subject")
        if not isinstance(subject, Mapping) or not isinstance(
            subject.get("bundle_digest"), str
        ):
            raise ValueError("gate approval payload is missing bundle routing data")
        return _require_global_bundle(load_bundle(repo, subject["bundle_digest"])), None
    if gate_kind == "plan-approval":
        subject = payload.get("subject")
        if not isinstance(subject, Mapping):
            raise ValueError("plan approval payload subject is invalid")
        candidate_ref = subject.get("plan_candidate_ref")
        if not isinstance(candidate_ref, Mapping):
            raise ValueError("plan approval candidate reference is invalid")
        from ._plan_candidate import load_plan_approval_candidate

        candidate, bundle = load_plan_approval_candidate(repo, candidate_ref)
        if candidate.get("run_id") != payload.get("run_id"):
            raise ValueError("plan approval candidate run identity mismatch")
        return _require_global_bundle(bundle), None

    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("gate approval payload run_id is required to select contract")
    try:
        _, opened = _run_dir(repo, run_id, create=False)
    except FileNotFoundError as error:
        raise ValueError(
            "gate approval producer run is missing; cannot load its retained bundle"
        ) from error
    else:
        _close(opened)
    state = load_state(repo, run_id)
    return _require_global_bundle(load_bundle(repo, state["bundle_digest"])), state

def _require_sorted_unique(values: list[Any], label: str) -> None:
    encoded = [canonical_json(value) for value in values]
    if encoded != sorted(encoded) or len(encoded) != len(set(encoded)):
        raise ValueError(f"{label} must be sorted and unique by canonical JSON bytes")


def _validate_authority_basis(bindings: list[dict[str, Any]]) -> None:
    _require_sorted_unique(bindings, "authority_basis")
    for binding in bindings:
        _validate_applicability(binding["applicability"])
        _require_sorted_unique(
            binding["source_dependencies"],
            "authority_basis source_dependencies",
        )


def _validate_payload(
    repo: Path,
    payload: dict[str, Any],
    bundle: CoreBundle,
    state: Mapping[str, Any] | None,
    *,
    require_run_scope: bool = False,
    require_current_authority: bool = False,
    lock_held: bool = False,
) -> None:
    _validate_schema(
        payload, "approval", bundle, definition_name="gate_approval_payload"
    )
    gate_kind = payload["gate_kind"]
    subject = payload["subject"]
    if gate_kind == "repository-decision":
        _require_sorted_unique(subject["source_dependencies"], "source_dependencies")
        _validate_authority_basis(subject["authority_basis"])
        _require_sorted_unique(subject["amends"], "amends")
        _require_sorted_unique(subject["supersedes"], "supersedes")
        expected_identity = subject["decision_id"]
        if state is not None and subject["bundle_digest"] != state["bundle_digest"]:
            raise ValueError("repository-decision payload bundle differs from its run")
        scope_ref = subject["scope_ref"]
        if scope_ref["sha256"] != payload["scope_digest"]:
            raise ValueError("repository-decision payload scope digest mismatch")
        _validate_applicability(subject["applicability"])
        scope_record = load_proposed_scope(repo, scope_ref)
        if subject["applicability"] != scope_record["applicability"]:
            raise ValueError(
                "repository-decision applicability differs from proposed "
                "scope descriptor"
            )
    elif gate_kind == "plan-approval":
        expected_identity = payload["identity"]["id"]
        from ._promotion import validate_plan_payload

        validate_plan_payload(
            repo,
            payload,
            state,
            require_current_authority=require_current_authority,
            lock_held=lock_held,
        )
    else:
        expected_identity = subject["effect_identity"]
    if payload["identity"]["id"] != expected_identity:
        raise ValueError("GateApproval identity differs from its subject")

    if gate_kind != "repository-decision":
        retained_scope = load_proposed_scope_by_digest(repo, payload["scope_digest"])
        if require_run_scope:
            if state is None:
                raise ValueError(
                    "GateApproval publication requires retained run scope references"
                )
            references = []
            if "scope_ref" in state:
                references.append(state["scope_ref"])
            references.extend(state.get("work_scope_refs", ()))
            matching = [
                ref
                for ref in references
                if ref.get("sha256") == payload["scope_digest"]
            ]
            if len(matching) != 1:
                raise ValueError(
                    "GateApproval scope is not uniquely retained by its run"
                )
            run_scope = load_proposed_scope(repo, matching[0])
            if run_scope != retained_scope:
                raise ValueError(
                    "GateApproval run scope identity differs from retained descriptor"
                )


def _record_evidence(
    repo: Path, authority: Mapping[str, Any], target: GateApprovalTarget
) -> None:
    if authority.get("kind") == "host-action":
        claim_ref = _exact(
            authority.get("claim_ref"), {"identity", "sha256"}, "claim reference"
        )
        load_human_action_claim(repo, claim_ref, target)
        return
    if authority.get("kind") == "external-artifact":
        artifact_path = authority.get("path")
        artifact_digest = authority.get("sha256")
        if not isinstance(artifact_path, str) or not isinstance(artifact_digest, str):
            raise ValueError("gate approval external artifact reference is invalid")
        try:
            artifact = load_human_approval_artifact(
                repo, artifact_path, artifact_digest
            )
        except FileNotFoundError as error:
            raise ValueError(
                "referenced external human approval artifact is missing"
            ) from error
        try:
            _validate_human_approval_bytes(artifact, target)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "referenced external human approval artifact is invalid"
            ) from error
        return
    raise ValueError("gate approval human evidence kind is unsupported")


def _commit_record(
    repo: Path, approval_id: str, data: bytes, *, lock_held: bool = False
) -> dict[str, str]:
    digest = hashlib.sha256(data).hexdigest()

    def commit() -> None:
        try:
            store_authority_record(repo, _NAMESPACE, approval_id, data)
        except FileExistsError as error:
            try:
                retained = load_authority_record(repo, _NAMESPACE, approval_id)
            except OSError:
                raise error from None
            if retained != data or hashlib.sha256(retained).hexdigest() != digest:
                raise ValueError(
                    "gate approval identity is occupied by different bytes"
                ) from error
        retained = load_authority_record(repo, _NAMESPACE, approval_id)
        if retained != data or hashlib.sha256(retained).hexdigest() != digest:
            raise ValueError("gate approval read-back differs from published bytes")

    if lock_held:
        commit()
    else:
        with _locked(repo):
            commit()
    return {"approval_id": approval_id, "sha256": digest}


def publish_gate_approval(
    repo: Path,
    payload: dict[str, Any],
    evidence: ObservedGateAction | ExternalArtifactInput,
) -> dict[str, str]:
    repo = Path(repo)
    if not isinstance(payload, dict):
        raise TypeError("GateApproval payload must be an object")
    try:
        payload_bytes = canonical_json(payload)
        payload = json.loads(payload_bytes)
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("GateApproval payload is not canonical JSON") from error
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("GateApproval payload run_id is required")
    is_plan_approval = payload.get("gate_kind") == "plan-approval"
    if is_plan_approval:
        with _locked(repo, run_id):
            state = load_state(repo, run_id)
            bundle = _require_global_bundle(load_bundle(repo, state["bundle_digest"]))
            _validate_payload(
                repo,
                payload,
                bundle,
                state,
                require_run_scope=True,
                require_current_authority=True,
                lock_held=True,
            )
            _resync_state_locked(repo, run_id, state)
    else:
        state = load_state(repo, run_id)
        bundle = _require_global_bundle(load_bundle(repo, state["bundle_digest"]))
        _validate_payload(
            repo,
            payload,
            bundle,
            state,
            require_run_scope=True,
        )
    if payload["gate_kind"] == "side-effect-permission":
        raise ValueError(
            "unsupported-gate: side-effect request producer is not implemented"
        )

    payload_digest = hashlib.sha256(payload_bytes).hexdigest()
    target = _target(payload, payload_digest)
    _validate_gate_approval_target(target)
    if isinstance(evidence, ExternalArtifactInput):
        validate_external_human_approval_artifact(evidence, target)
        with _locked(repo):
            artifact_ref = retain_human_approval_artifact(repo, evidence.exact_bytes)
        human_authority = {"kind": "external-artifact", **artifact_ref}
    elif type(evidence) is ObservedGateAction:
        claim_ref = publish_human_action_claim(repo, evidence, target)
        human_authority = {"kind": "host-action", "claim_ref": claim_ref}
    else:
        raise TypeError(
            "gate evidence must be observed host action or exact external "
            "artifact bytes"
        )

    approval_id = _approval_id(payload, payload_digest)
    record = {
        "protocol_version": 3,
        "approval_contract": "human-gate-approval/1",
        "approval_id": approval_id,
        "payload": payload,
        "approved_target_sha256": payload_digest,
        "human_authority": human_authority,
    }
    _validate_schema(record, "approval", bundle)
    with _locked(repo, run_id):
        state = load_state(repo, run_id)
        bundle = _require_global_bundle(load_bundle(repo, state["bundle_digest"]))
        _validate_payload(
            repo,
            payload,
            bundle,
            state,
            require_run_scope=True,
            require_current_authority=is_plan_approval,
            lock_held=True,
        )
        _record_evidence(repo, human_authority, target)
        return _commit_record(repo, approval_id, canonical_json(record), lock_held=True)


def load_gate_approval(repo: Path, reference: dict[str, Any]) -> dict[str, Any]:
    repo = Path(repo)
    reference = _exact(reference, _REFERENCE_FIELDS, "reference")
    approval_id = reference["approval_id"]
    digest = reference["sha256"]
    if not isinstance(approval_id, str) or not _APPROVAL_ID.fullmatch(approval_id):
        raise ValueError("gate approval reference identity is invalid")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("gate approval reference digest is invalid")
    try:
        data = load_authority_record(repo, _NAMESPACE, approval_id)
    except FileNotFoundError as error:
        raise ValueError("gate approval reference is not retained") from error
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("gate approval reference digest mismatch")
    record = _parse_record(data)
    if set(record) != _RECORD_FIELDS:
        raise ValueError("gate approval record has invalid shape")
    payload = record["payload"]
    if not isinstance(payload, dict):
        raise ValueError("gate approval payload is invalid")
    bundle, state = _record_bundle(repo, payload)
    _validate_schema(record, "approval", bundle)
    if record["approval_id"] != approval_id:
        raise ValueError("GateApproval embedded approval ID mismatch")
    payload_digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    if record["approved_target_sha256"] != payload_digest:
        raise ValueError("gate approval target digest mismatch")
    if approval_id != _approval_id(payload, payload_digest):
        raise ValueError("gate approval identity derivation mismatch")
    _validate_payload(repo, payload, bundle, state)
    if payload["gate_kind"] == "side-effect-permission":
        raise ValueError(
            "unsupported-gate: side-effect request producer is not implemented"
        )
    target = _target(payload, payload_digest)
    _validate_gate_approval_target(target)
    _record_evidence(repo, record["human_authority"], target)
    return record


__all__ = ["load_gate_approval", "publish_gate_approval"]
