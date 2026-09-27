from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .artifact_io import load_toml_artifact
from .errors import ValidationError, sorted_errors
from .path_atoms import validate_relative_posix_path

STATE_PATH = "00-advisory.toml"
STATE_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "repository_revision",
        "status",
        "intent",
        "scope",
        "exclusions",
        "evidence_refs",
        "decisions",
        "unresolved_decisions",
        "proposal_path",
        "proposal_sha256",
        "proposal_status",
        "accepted_architectures",
    }
)
SNAPSHOT_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "snapshot_id",
        "status",
        "source_revision",
        "architecture_content",
        "content_sha256",
        "decisions",
        "evidence_refs",
        "dependencies",
        "relationships",
    }
)
STATUSES = frozenset(
    {
        "intent-interrogation",
        "research",
        "architecture",
        "decision-required",
        "review",
        "proposal-ready",
        "accepted",
        "rejected",
        "stopped",
        "implementation-planning",
    }
)
DECISION_FIELDS = frozenset({"id", "kind", "answer", "source"})
PACKET_FIELDS = frozenset(
    {"id", "kind", "problem", "why", "decision_required", "options", "recommendation"}
)
OPTION_FIELDS = frozenset({"id", "description", "consequences"})
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


def _error(code: str, path: Path, field: str, message: str) -> ValidationError:
    return ValidationError(code, str(path), field, message)


def _closed(
    value: dict[str, object], allowed: frozenset[str], path: Path, field: str
) -> list[ValidationError]:
    return [
        _error(
            "ADV-SCHEMA-UNKNOWN-FIELD",
            path,
            f"{field}.{key}" if field else key,
            "unknown field is not permitted",
        )
        for key in sorted(value.keys() - allowed)
    ]


def _string(
    record: dict[str, object], key: str, path: Path, errors: list[ValidationError]
) -> str | None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(
            _error("ADV-SCHEMA-INVALID-FIELD", path, key, "must be a non-empty string")
        )
        return None
    return value


def _digest(value: object) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


def _safe_file(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str):
        return None
    try:
        validate_relative_posix_path(relative)
        resolved_root = root.resolve()
        resolved_path = (resolved_root / relative).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if resolved_root not in resolved_path.parents or not resolved_path.is_file():
        return None
    return resolved_path


def repository_root(task_dir: Path) -> Path | None:
    resolved = Path(task_dir).resolve()
    if resolved.parent.name != "runs" or resolved.parent.parent.name != ".kapisch":
        return None
    return resolved.parent.parent.parent


def _validate_decisions(
    value: object, path: Path, field: str, errors: list[ValidationError]
) -> None:
    if not isinstance(value, list):
        errors.append(
            _error("ADV-SCHEMA-INVALID-FIELD", path, field, "must be an array of tables")
        )
        return
    seen: set[str] = set()
    for index, record in enumerate(value):
        reference = f"{field}[{index}]"
        if not isinstance(record, dict):
            errors.append(_error("ADV-SCHEMA-INVALID-FIELD", path, reference, "must be a table"))
            continue
        errors.extend(_closed(record, DECISION_FIELDS, path, reference))
        decision_id = _string(record, "id", path, errors)
        kind = record.get("kind")
        if not isinstance(kind, str) or kind not in {"intent", "architecture"}:
            errors.append(
                _error("ADV-DECISION-KIND", path, f"{reference}.kind", "must be intent or architecture")
            )
        _string(record, "answer", path, errors)
        if record.get("source") != "human":
            errors.append(
                _error("ADV-DECISION-SOURCE", path, f"{reference}.source", "accepted decisions must record human authority")
            )
        if decision_id is not None:
            if decision_id in seen:
                errors.append(
                    _error("ADV-SCHEMA-DUPLICATE-ID", path, f"{reference}.id", "decision IDs must be unique")
                )
            seen.add(decision_id)


def _validate_packets(
    value: object, path: Path, errors: list[ValidationError]
) -> None:
    if not isinstance(value, list):
        errors.append(
            _error("ADV-SCHEMA-INVALID-FIELD", path, "unresolved_decisions", "must be an array of tables")
        )
        return
    seen: set[str] = set()
    for index, packet in enumerate(value):
        reference = f"unresolved_decisions[{index}]"
        if not isinstance(packet, dict):
            errors.append(_error("ADV-SCHEMA-INVALID-FIELD", path, reference, "must be a table"))
            continue
        errors.extend(_closed(packet, PACKET_FIELDS, path, reference))
        packet_id = _string(packet, "id", path, errors)
        if packet_id is not None:
            if packet_id in seen:
                errors.append(
                    _error("ADV-SCHEMA-DUPLICATE-ID", path, f"{reference}.id", "packet IDs must be unique")
                )
            seen.add(packet_id)
        kind = packet.get("kind")
        if not isinstance(kind, str) or kind not in {"intent", "architecture"}:
            errors.append(
                _error("ADV-DECISION-KIND", path, f"{reference}.kind", "must be intent or architecture")
            )
        for key in ("problem", "why", "decision_required"):
            _string(packet, key, path, errors)
        options = packet.get("options")
        if not isinstance(options, list):
            errors.append(
                _error("ADV-DECISION-OPTIONS", path, f"{reference}.options", "must be an array with at most three options")
            )
            continue
        if len(options) > 3:
            errors.append(
                _error("ADV-DECISION-OPTIONS", path, f"{reference}.options", "at most three materially different options are permitted")
            )
        option_ids: set[str] = set()
        for option_index, option in enumerate(options):
            option_ref = f"{reference}.options[{option_index}]"
            if not isinstance(option, dict):
                errors.append(_error("ADV-DECISION-OPTIONS", path, option_ref, "must be a table"))
                continue
            errors.extend(_closed(option, OPTION_FIELDS, path, option_ref))
            option_id = _string(option, "id", path, errors)
            _string(option, "description", path, errors)
            _string(option, "consequences", path, errors)
            if option_id is not None:
                if option_id in option_ids:
                    errors.append(_error("ADV-DECISION-OPTIONS", path, option_ref, "option IDs must be unique"))
                option_ids.add(option_id)
        recommendation = packet.get("recommendation", "unavailable")
        if recommendation != "unavailable" and (
            not isinstance(recommendation, str) or recommendation not in option_ids
        ):
            errors.append(
                _error("ADV-DECISION-RECOMMENDATION", path, f"{reference}.recommendation", "must name a listed option or be unavailable")
            )


def _validate_snapshot(
    task_dir: Path,
    task_id: str,
    entry: object,
    index: int,
    errors: list[ValidationError],
) -> dict[str, object] | None:
    state_path = task_dir / STATE_PATH
    field = f"accepted_architectures[{index}]"
    if not isinstance(entry, dict):
        errors.append(_error("ADV-SNAPSHOT-REFERENCE", state_path, field, "must be a table"))
        return None
    errors.extend(_closed(entry, frozenset({"id", "path", "digest"}), state_path, field))
    snapshot_id = _string(entry, "id", state_path, errors)
    relative = _string(entry, "path", state_path, errors)
    if snapshot_id is not None and ("/" in snapshot_id or "\\" in snapshot_id):
        errors.append(_error("ADV-SNAPSHOT-IDENTITY", state_path, f"{field}.id", "must be a single path component"))
    digest = entry.get("digest")
    if not _digest(digest):
        errors.append(
            _error("ADV-SNAPSHOT-DIGEST", state_path, f"{field}.digest", "must be 64 lowercase hexadecimal characters")
        )
    if not isinstance(relative, str) or relative != f"architectures/{snapshot_id}-{digest}.toml":
        errors.append(_error("ADV-SNAPSHOT-REFERENCE", state_path, f"{field}.path", "accepted snapshot path must be canonical and content-addressed"))
    snapshot_path = _safe_file(task_dir, relative)
    if snapshot_path is None:
        errors.append(
            _error("ADV-SNAPSHOT-MISSING", state_path, field, "accepted snapshot must exist beneath the run directory")
        )
        return None
    actual_digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if actual_digest != digest or not snapshot_path.name.endswith(f"-{actual_digest}.toml"):
        errors.append(
            _error("ADV-SNAPSHOT-DIGEST", snapshot_path, field, "snapshot bytes do not match their bound digest")
        )
        return None
    snapshot, failure = load_toml_artifact(snapshot_path)
    if failure is not None or snapshot is None:
        errors.append(_error("ADV-SNAPSHOT-PARSE", snapshot_path, "snapshot", "must be valid UTF-8 TOML"))
        return None
    errors.extend(_closed(snapshot, SNAPSHOT_FIELDS, snapshot_path, ""))
    for required in SNAPSHOT_FIELDS:
        if required not in snapshot:
            errors.append(_error("ADV-SNAPSHOT-SCHEMA", snapshot_path, required, "required field is missing"))
    if snapshot.get("schema_version") != 1 or isinstance(snapshot.get("schema_version"), bool):
        errors.append(_error("ADV-SNAPSHOT-SCHEMA", snapshot_path, "schema_version", "must equal 1"))
    if snapshot.get("task_id") != task_id or snapshot.get("snapshot_id") != snapshot_id:
        errors.append(_error("ADV-SNAPSHOT-IDENTITY", snapshot_path, "identity", "snapshot and state identities differ"))
    if snapshot.get("status") != "accepted":
        errors.append(_error("ADV-SNAPSHOT-STATUS", snapshot_path, "status", "only human-accepted architecture can be snapshotted"))
    _string(snapshot, "source_revision", snapshot_path, errors)
    content = snapshot.get("architecture_content")
    if not isinstance(content, str) or not content.strip():
        errors.append(_error("ADV-SNAPSHOT-CONTENT", snapshot_path, "architecture_content", "must be non-empty text"))
    elif hashlib.sha256(content.encode("utf-8")).hexdigest() != snapshot.get("content_sha256"):
        errors.append(_error("ADV-SNAPSHOT-CONTENT-DIGEST", snapshot_path, "content_sha256", "architecture content digest does not match"))
    _validate_decisions(snapshot.get("decisions"), snapshot_path, "decisions", errors)
    for field_name in ("evidence_refs", "dependencies", "relationships"):
        if not isinstance(snapshot.get(field_name), list):
            errors.append(_error("ADV-SNAPSHOT-SCHEMA", snapshot_path, field_name, "must be an array"))
    return snapshot


def _snapshot_identity(value: object) -> tuple[str, str, str] | None:
    if not isinstance(value, dict):
        return None
    snapshot_id, path, digest = value.get("id"), value.get("path"), value.get("digest")
    if not isinstance(snapshot_id, str) or not isinstance(path, str) or not isinstance(digest, str):
        return None
    return snapshot_id, path, digest



def validate_advisory(
    task_dir: Path, previous_task_dir: Path | None = None
) -> list[ValidationError]:
    """Validate graph-free advisory state, accepted snapshots, and resume history."""
    task_dir = Path(task_dir)
    state_path = task_dir / STATE_PATH
    if repository_root(task_dir) is None:
        return [_error("ADV-STATE-ROOT", state_path, "task_dir", "run must be beneath <repository>/.kapisch/runs/<task-id>")]
    state, failure = load_toml_artifact(state_path)
    if failure is not None or state is None:
        code = "ADV-STATE-MISSING" if failure and failure.kind.value == "missing" else "ADV-STATE-PARSE"
        return [_error(code, state_path, "state", "advisory state is missing or invalid")]
    if not isinstance(state, dict):
        return [_error("ADV-SCHEMA-INVALID", state_path, "root", "must be a TOML table")]
    errors = _closed(state, STATE_FIELDS, state_path, "")
    for required in STATE_FIELDS:
        if required not in state:
            errors.append(_error("ADV-STATE-SCHEMA", state_path, required, "required field is missing"))
    if state.get("schema_version") != 1 or isinstance(state.get("schema_version"), bool):
        errors.append(_error("ADV-STATE-SCHEMA", state_path, "schema_version", "must equal 1"))
    task_id = state.get("task_id")
    if not isinstance(task_id, str) or task_id != task_dir.name:
        errors.append(_error("ADV-STATE-IDENTITY", state_path, "task_id", "must match the run directory name"))
        task_id = task_dir.name
    _string(state, "repository_revision", state_path, errors)
    if not isinstance(state.get("status"), str) or state.get("status") not in STATUSES:
        errors.append(_error("ADV-STATE-STATUS", state_path, "status", "unsupported advisory lifecycle status"))
    _string(state, "intent", state_path, errors)
    for field_name in ("scope", "exclusions"):
        value = state.get(field_name)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(_error("ADV-STATE-SCHEMA", state_path, field_name, "must be an array of non-empty strings"))
    _validate_decisions(state.get("decisions"), state_path, "decisions", errors)
    _validate_packets(state.get("unresolved_decisions"), state_path, errors)

    proposal_path = _safe_file(task_dir, state.get("proposal_path"))
    if proposal_path is None:
        errors.append(_error("ADV-PROPOSAL-MISSING", state_path, "proposal_path", "proposal must exist beneath the run directory"))
    elif hashlib.sha256(proposal_path.read_bytes()).hexdigest() != state.get("proposal_sha256"):
        errors.append(_error("ADV-PROPOSAL-DIGEST", proposal_path, "proposal_sha256", "proposal bytes do not match advisory state"))
    if not isinstance(state.get("proposal_status"), str) or state.get("proposal_status") not in {"draft", "proposed", "accepted", "rejected", "superseded"}:
        errors.append(_error("ADV-PROPOSAL-STATUS", state_path, "proposal_status", "unsupported proposal status"))
    if not isinstance(state.get("evidence_refs"), list):
        errors.append(_error("ADV-STATE-SCHEMA", state_path, "evidence_refs", "must be an array"))

    snapshots = state.get("accepted_architectures")
    if not isinstance(snapshots, list):
        errors.append(_error("ADV-STATE-SCHEMA", state_path, "accepted_architectures", "must be an array of tables"))
        snapshots = []
    if isinstance(state.get("status"), str) and state.get("status") in {"accepted", "implementation-planning"}:
        if not snapshots:
            errors.append(_error("ADV-STATE-ACCEPTANCE", state_path, "accepted_architectures", "accepted or implementation-planning lifecycle requires an immutable accepted snapshot"))
        if state.get("proposal_status") != "accepted":
            errors.append(_error("ADV-STATE-ACCEPTANCE", state_path, "proposal_status", "accepted or implementation-planning lifecycle requires human acceptance of the proposal"))
    state_decisions = state.get("decisions")
    current_decisions = {
        decision.get("id"): decision
        for decision in state_decisions
        if isinstance(decision, dict) and isinstance(decision.get("id"), str)
    } if isinstance(state_decisions, list) else {}
    identities: set[tuple[object, object, object]] = set()
    snapshot_ids: set[str] = set()
    for index, entry in enumerate(snapshots):
        snapshot = _validate_snapshot(task_dir, task_id, entry, index, errors)
        identity = _snapshot_identity(entry)
        if identity is not None and (
            identity in identities or identity[0] in snapshot_ids
        ):
            errors.append(_error("ADV-SNAPSHOT-REFERENCE", state_path, f"accepted_architectures[{index}]", "snapshot references must be unique"))
        if identity is not None:
            identities.add(identity)
            snapshot_ids.add(identity[0])

        snapshot_decisions = snapshot.get("decisions") if snapshot is not None else None
        if isinstance(snapshot_decisions, list):
            for decision in snapshot_decisions:
                if isinstance(decision, dict) and current_decisions.get(decision.get("id")) != decision:
                    errors.append(_error("ADV-DECISION-REWRITE", state_path, "decisions", "accepted decisions must remain unchanged in advisory state"))
                    break

    if previous_task_dir is not None:
        previous_task_dir = Path(previous_task_dir)
        previous_path = previous_task_dir / STATE_PATH
        prior_errors = validate_advisory(previous_task_dir)
        previous, previous_failure = load_toml_artifact(previous_path)
        if prior_errors or previous_failure is not None or previous is None:
            errors.append(_error("ADV-RESUME-PRIOR-INVALID", previous_path, "state", "prior advisory snapshot must validate before resume"))
        elif isinstance(previous, dict):
            if previous.get("task_id") != state.get("task_id"):
                errors.append(_error("ADV-RESUME-IDENTITY", previous_path, "task_id", "resume must continue the same advisory task"))
            for field_name in ("intent", "scope", "exclusions"):
                if previous.get(field_name) != state.get(field_name):
                    errors.append(_error("ADV-RESUME-CONTRACT", state_path, field_name, "task intent, scope, and exclusions cannot change silently on resume"))
            previous_snapshots = previous.get("accepted_architectures", [])
            current_snapshots = state.get("accepted_architectures", [])
            prior_ids = [_snapshot_identity(entry) for entry in previous_snapshots] if isinstance(previous_snapshots, list) else []
            current_ids = [_snapshot_identity(entry) for entry in current_snapshots] if isinstance(current_snapshots, list) else []
            if current_ids[: len(prior_ids)] != prior_ids:
                errors.append(_error("ADV-RESUME-ARCHITECTURE", state_path, "accepted_architectures", "resume must preserve prior accepted snapshots in order"))
            prior_decision_list = previous.get("decisions")
            previous_decisions = {
                decision.get("id"): decision
                for decision in prior_decision_list
                if isinstance(decision, dict) and isinstance(decision.get("id"), str)
            } if isinstance(prior_decision_list, list) else {}
            if any(current_decisions.get(key) != value for key, value in previous_decisions.items()):
                errors.append(_error("ADV-RESUME-DECISIONS", state_path, "decisions", "resume must preserve accepted human decisions"))
    return list(sorted_errors(errors))
