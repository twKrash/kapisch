from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import ValidationError, sorted_errors
from .delegations import parse_route, validate_route_references
from .manifest import parse_manifest
from .references import parse_state, validate_references
from .review_evidence import validate_review_evidence
from .transitions import validate_lifecycle, validate_transition


def validate_snapshot(
    manifest, state, task_dir: Path, contract_dir: Path
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    errors.extend(validate_references(manifest, state, task_dir, contract_dir))
    errors.extend(validate_lifecycle(manifest, state))
    errors.extend(validate_review_evidence(manifest, state, task_dir))
    return errors


def validate(
    contract_dir: Path,
    task_dir: Path,
    previous_task_dir: Path | None = None,
) -> tuple[ValidationError, ...]:
    parsed = parse_manifest(task_dir / "02-execution-graph.toml")
    errors = list(parsed.errors)
    if parsed.manifest is None:
        return sorted_errors(errors)
    if parsed.manifest.version == 3:
        route_path = task_dir / "delegations" / "00-route.toml"
        route_exists = route_path.is_file()
        routing = parsed.manifest.policies.get("ecosystem_routing")
        has_delegation_ids = any(
            node.raw.get("delegation_ids") for node in parsed.manifest.nodes
        )
        if routing == "off" and has_delegation_ids:
            errors.append(
                ValidationError(
                    "TWV-DELEG-ROUTING-OFF-WITH-REFS",
                    str(route_path),
                    "policies.ecosystem_routing",
                    "ecosystem_routing=off forbids delegation references",
                )
            )
        if routing == "off" and route_exists:
            errors.append(
                ValidationError(
                    "TWV-DELEG-ROUTE-WITH-ROUTING-OFF",
                    str(route_path),
                    "delegations/00-route.toml",
                    "ecosystem_routing=off forbids a delegation route record",
                )
            )
        if route_exists or has_delegation_ids:
            route, route_errors = parse_route(task_dir)
            errors.extend(route_errors)
            if route is not None and route_exists:
                errors.extend(validate_route_references(parsed.manifest, task_dir))
    state, state_errors = parse_state(task_dir / "03-state.toml")
    errors.extend(state_errors)
    if state is None:
        return sorted_errors(errors)
    previous_manifest = None
    previous_state = None
    if previous_task_dir:
        previous_result = parse_manifest(previous_task_dir / "02-execution-graph.toml")
        errors.extend(previous_result.errors)
        previous_manifest = previous_result.manifest
        previous_state, previous_state_errors = parse_state(
            previous_task_dir / "03-state.toml"
        )
        errors.extend(previous_state_errors)
    errors.extend(validate_snapshot(parsed.manifest, state, task_dir, contract_dir))
    if previous_manifest is not None and previous_state is not None:
        previous_errors = validate_snapshot(
            previous_manifest, previous_state, previous_task_dir, contract_dir
        )
        errors.extend(previous_errors)
        if not previous_errors:
            errors.extend(
                validate_transition(
                    parsed.manifest,
                    state,
                    previous_manifest,
                    previous_state,
                )
            )
    return sorted_errors(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_kapisch.py")
    parser.add_argument("--contract-dir", required=True, type=Path)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--previous-task-dir", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    errors = validate(args.contract_dir, args.task_dir, args.previous_task_dir)
    if args.format == "json":
        print(
            json.dumps(
                [error.to_dict() for error in errors],
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        for error in errors:
            print(error)
    return 2 if errors else 0
