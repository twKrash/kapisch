"""Pure structural validation of immutable stage observations."""

from __future__ import annotations

import re
from typing import Any


def _validate_observation(row: Any, index: int, workflow: str) -> None:
    required = {
        "stage_id",
        "stage_kind",
        "sequence",
        "role",
        "status",
        "producer",
        "evidence",
        "scope_digest",
    }
    allowed = required | {"node_id", "retry_of_stage_id"}
    kinds = {
        "research",
        "design",
        "implement",
        "review",
        "final",
        "gate",
        "bounded-delegate",
    }
    roles = {
        "architect",
        "researcher",
        "implementer",
        "implementer-lite",
        "mechanic",
        "reviewer",
    }
    statuses = {
        "planned",
        "dispatch-uncertain",
        "complete",
        "blocked",
        "failed",
        "interrupted",
    }
    if not isinstance(row, dict) or set(row) - allowed or required - row.keys():
        raise ValueError("stage observation has missing or unknown fields")
    if row["sequence"] != index or isinstance(row["sequence"], bool):
        raise ValueError("run history must have contiguous ordered sequence")
    if not re.fullmatch(r"s-[0-9a-f]{32}", str(row["stage_id"])):
        raise ValueError("invalid stage_id")
    if (
        not isinstance(row["stage_kind"], str)
        or row["stage_kind"] not in kinds
        or not isinstance(row["role"], str)
        or row["role"] not in roles
        or not isinstance(row["status"], str)
        or row["status"] not in statuses
    ):
        raise ValueError("invalid stage vocabulary")
    if "node_id" in row and (
        not isinstance(row["node_id"], str)
        or not re.fullmatch(r"n-[0-9a-f]{32}", row["node_id"])
    ):
        raise ValueError("invalid node_id")
    if "retry_of_stage_id" in row and (
        not isinstance(row["retry_of_stage_id"], str)
        or not re.fullmatch(r"s-[0-9a-f]{32}", row["retry_of_stage_id"])
    ):
        raise ValueError("invalid retry_of_stage_id")
    if (
        row["producer"] != "controller"
        or not isinstance(row["scope_digest"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", row["scope_digest"])
    ):
        raise ValueError("invalid stage producer or scope digest")
    if not isinstance(row["evidence"], list):
        raise ValueError("stage evidence must be an array")
    for evidence in row["evidence"]:
        if (
            not isinstance(evidence, dict)
            or set(evidence) != {"kind", "path", "sha256"}
            or not all(
                isinstance(evidence[key], str) and evidence[key]
                for key in ("kind", "path")
            )
            or evidence["path"].startswith("/")
            or "\\" in evidence["path"]
            or any(part in {"", ".", ".."} for part in evidence["path"].split("/"))
            or not isinstance(evidence["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", evidence["sha256"])
        ):
            raise ValueError("invalid stage evidence reference")
    if workflow != "milestone" and "node_id" in row:
        raise ValueError("graph-free workflow cannot contain node_id")


def _validate_history(history: list[Any], workflow: str) -> None:
    attempts: dict[str, dict[str, Any]] = {}
    retries: set[str] = set()
    bound: set[str] = set()
    last_observations: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(history):
        _validate_observation(row, index, workflow)
        identity = {
            key: row[key]
            for key in (
                "stage_id",
                "stage_kind",
                "role",
                "scope_digest",
                "node_id",
                "retry_of_stage_id",
            )
            if key in row
        }
        bindings = [
            item
            for item in row["evidence"]
            if item["kind"] == "review-target-binding/1"
        ]
        if len(bindings) > 1:
            raise ValueError("attempt must retain exactly one binding locator")
        if bindings and bindings[0]["path"] != (
            f"review-inputs/review-target-bindings/{bindings[0]['sha256']}.json"
        ):
            raise ValueError("binding locator path is not canonical")
        existing = attempts.get(row["stage_id"])
        if existing is None:
            if bindings:
                raise ValueError("creation cannot contain a binding")
            if row["status"] != "planned":
                raise ValueError("first stage observation must be planned")
            predecessor = row.get("retry_of_stage_id")
            if predecessor is not None:
                prior = attempts.get(predecessor)
                if (
                    prior is None
                    or predecessor in retries
                    or prior["status"] not in {"failed", "blocked", "interrupted"}
                ):
                    raise ValueError(
                        "retry predecessor is missing, branched, or ineligible"
                    )
                prior_identity = prior["identity"]
                if any(
                    identity.get(key) != prior_identity.get(key)
                    for key in ("stage_kind", "role", "scope_digest", "node_id")
                ):
                    raise ValueError("retry changed attempt binding")
                retries.add(predecessor)
            attempts[row["stage_id"]] = {
                "creation_index": index,
                "identity": identity,
                "status": row["status"],
                "evidence": row["evidence"],
            }
        else:
            if existing["status"] in {"complete", "blocked", "failed", "interrupted"}:
                raise ValueError("terminal attempt is immutable")
            prior_evidence = existing["evidence"]
            previous = last_observations.get(row["stage_id"])
            same_observation = previous is not None and {
                key: value for key, value in row.items() if key != "sequence"
            } == {key: value for key, value in previous.items() if key != "sequence"}
            new_binding = bool(bindings) and row["stage_id"] not in bound
            binding_observation = (
                new_binding
                and existing["status"] == row["status"] == "planned"
                and previous is not None
                and previous is history[existing["creation_index"]]
                and workflow == "task"
                and row["stage_kind"] in {"review", "final"}
                and row["role"] == "reviewer"
                and row["evidence"] == prior_evidence + bindings
            )
            if new_binding and not binding_observation:
                raise ValueError("binding must be the second planned observation")
            if binding_observation:
                bound.add(row["stage_id"])
            if (
                (row["status"] == "planned" and not binding_observation)
                or identity != existing["identity"]
                or same_observation
            ):
                raise ValueError(
                    "duplicate creation, changed binding, or duplicate observation"
                )
            if row["evidence"][: len(prior_evidence)] != prior_evidence:
                raise ValueError("stage evidence is not cumulative")
            existing["status"] = row["status"]
            existing["evidence"] = row["evidence"]
        last_observations[row["stage_id"]] = row


def _binding_rows(history: list[Any]) -> tuple[dict[str, Any], ...]:
    """Project binding positions only after structural history validation."""
    return tuple(
        row
        for row in history
        if row["status"] == "planned"
        and any(item["kind"] == "review-target-binding/1" for item in row["evidence"])
    )
