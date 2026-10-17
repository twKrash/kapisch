"""Contained discovery of pre-dispatch witnesses, including request-only orphans."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ._review_target_records import _files
from ._validation_json import _json
from .storage import _close, _open_dir, _read_file, _run_dir, load_bundle


def _tree(repo: Path, run_id: str, directory: str) -> tuple[tuple[str, bytes], ...]:
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        try:
            root = _open_dir(run, directory)
        except FileNotFoundError:
            return ()
        fds.append(root)
        found = []
        for operation_id in sorted(os.listdir(root)):
            if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
                raise ValueError("dispatch inventory has invalid operation identity")
            operation = _open_dir(root, operation_id)
            try:
                names = sorted(os.listdir(operation))
                if not names:
                    raise ValueError(
                        "dispatch inventory contains ambiguous empty operation"
                    )
                for name in names:
                    found.append(
                        (
                            f"{directory}/{operation_id}/{name}",
                            _read_file(operation, name),
                        )
                    )
            finally:
                os.close(operation)
        return tuple(found)
    finally:
        _close(fds)


def _pre_dispatch_veto(
    repo: Path, run_id: str, state: Mapping[str, Any], stage_id: str
) -> None:
    attempts = {row["stage_id"]: row for row in state["history"]}
    packets_by_operation = {}
    for name, data in _files(repo, run_id, "requests"):
        if not re.fullmatch(r"op-[0-9a-f]{32}\.json", name):
            raise ValueError("request inventory has invalid operation name")
        packet = _json(data, "request inventory")
        operation_id = name[:-5]
        if not isinstance(packet, dict):
            raise ValueError("request inventory ownership is malformed")
        if not isinstance(packet.get("stage_id"), str):
            raise ValueError("request stage identity is malformed")
        owner = attempts.get(packet["stage_id"])
        if owner is None or any(
            packet.get(key) != value
            for key, value in {
                "run_id": run_id,
                "operation_id": operation_id,
                "bundle_digest": state["bundle_digest"],
                "role": owner["role"],
                "scope_digest": owner["scope_digest"],
            }.items()
        ):
            raise ValueError("request inventory ownership is ambiguous")
        binding = packet.get("adapter_binding")
        if (
            not isinstance(binding, dict)
            or set(binding) != {"adapter_id", "lookup_context"}
            or not all(isinstance(v, str) and v for v in binding.values())
        ):
            raise ValueError("request adapter binding is malformed")
        if packet["stage_id"] == stage_id:
            raise ValueError("request fact vetoes new stage binding")
        from ._authority import _validate_graph_free_request
        from ._invocation import _validate_packet_inputs, _validate_request_owner

        _validate_request_owner(packet, owner)
        _validate_graph_free_request(packet, state, owner)
        _validate_packet_inputs(
            repo,
            run_id,
            operation_id,
            packet,
            load_bundle(repo, state["bundle_digest"]),
        )
        packets_by_operation[operation_id] = packet
    for path, data in _tree(repo, run_id, "request-inputs"):
        _, operation_id, name = path.split("/")
        packet = packets_by_operation.get(operation_id)
        refs = packet.get("inputs", []) if packet else []
        if not isinstance(refs, list) or not any(
            isinstance(ref, dict)
            and ref.get("path") == path
            and ref.get("sha256") == hashlib.sha256(data).hexdigest()
            for ref in refs
        ):
            raise ValueError("orphan request input vetoes new stage binding")
    # Any operation-scoped review input is dispatch evidence whose Stage 6.5
    # consumer is gated; it cannot be ignored while establishing a new binding.
    if _review_operation_inputs(repo, run_id):
        raise ValueError("operation review input vetoes new stage binding")


def _review_operation_inputs(repo: Path, run_id: str) -> tuple[tuple[str, bytes], ...]:
    run, fds = _run_dir(repo, run_id, create=False)
    try:
        try:
            review = _open_dir(run, "review-inputs")
        except FileNotFoundError:
            return ()
        fds.append(review)
        found = []
        namespaces = {
            "comparison-roots",
            "review-target-bindings",
            "review-targets",
            "comparison-bases",
            "scopes",
        }
        for name in sorted(os.listdir(review)):
            if name in namespaces:
                continue
            if not re.fullmatch(r"op-[0-9a-f]{32}", name):
                raise ValueError("unknown review-input inventory namespace")
            operation = _open_dir(review, name)
            try:
                names = sorted(os.listdir(operation))
                if not names:
                    raise ValueError("ambiguous empty operation review input")
                found.extend(
                    (f"review-inputs/{name}/{item}", _read_file(operation, item))
                    for item in names
                )
            finally:
                os.close(operation)
        return tuple(found)
    finally:
        _close(fds)


def _downstream_veto(
    repo: Path,
    run_id: str,
    state: Mapping[str, Any],
    stage_id: str,
    reservation: Mapping[str, Any],
) -> None:
    attempts = {row["stage_id"] for row in state["history"]}
    for namespace in ("review-targets", "comparison-bases", "scopes"):
        for name, data in _files(repo, run_id, f"review-inputs/{namespace}"):
            fact = _json(data, "downstream review fact")
            contract_key, contract = {
                "review-targets": ("review_target_contract", "review-target/1"),
                "comparison-bases": ("comparison_base_contract", "comparison-base/1"),
                "scopes": ("scope_contract", "review-scope/1"),
            }[namespace]
            if (
                not isinstance(fact, dict)
                or type(fact.get("protocol_version")) is not int
                or fact["protocol_version"] != 3
                or fact.get(contract_key) != contract
                or name != f"{hashlib.sha256(data).hexdigest()}.json"
            ):
                raise ValueError("downstream fact inventory is malformed")
            if (
                not isinstance(fact, dict)
                or fact.get("run_id") != run_id
                or not isinstance(fact.get("stage_id"), str)
                or fact["stage_id"] not in attempts
            ):
                raise ValueError("downstream fact ownership is ambiguous")
            if fact["stage_id"] == stage_id:
                raise ValueError("premature target/base/scope vetoes binding")
            expected = f".kapisch/v3/runs/{run_id}/review-inputs/{namespace}/{name}"
            if any(
                reservation[field]["path"] == expected
                for field in ("review_target_ref", "comparison_base_ref")
            ):
                raise ValueError("conflicting downstream producer identity")


@dataclass(frozen=True)
class _LoadedOperation:
    operation_id: str
    facts: Mapping[str, tuple[Any, str]]


def _read_invocation_inventory(invocations: int) -> tuple[_LoadedOperation, ...]:
    """Discover and parse each immutable invocation fact once, retaining its digest."""
    try:
        operation_ids = sorted(os.listdir(invocations))
    except OSError as error:
        raise ValueError("invocation inventory is unavailable") from error
    loaded: list[_LoadedOperation] = []
    for operation_id in operation_ids:
        if not re.fullmatch(r"op-[0-9a-f]{32}", operation_id):
            raise ValueError("invocation inventory contains invalid operation name")
        try:
            operation = _open_dir(invocations, operation_id)
        except OSError as error:
            raise ValueError("invocation inventory entry is unavailable") from error
        try:
            try:
                names = sorted(os.listdir(operation))
            except OSError as error:
                raise ValueError("invocation inventory entry is unavailable") from error
            facts: dict[str, tuple[Any, str]] = {}
            for filename in names:
                if not filename.endswith(".json"):
                    raise ValueError("invocation inventory contains unknown artifact")
                relative = f"invocations/{operation_id}/{filename}"
                data = _read_file(operation, filename)
                facts[filename] = (
                    _json(data, relative),
                    hashlib.sha256(data).hexdigest(),
                )
            loaded.append(_LoadedOperation(operation_id, MappingProxyType(facts)))
        finally:
            os.close(operation)
    return tuple(loaded)
