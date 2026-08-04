from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import ValidationError, sorted_errors
from .delegations import parse_route, validate_route_references
from .manifest import parse_manifest
from .references import parse_state, validate_references
from .review_evidence import validate_review_evidence
from .transitions import validate_lifecycle


def validate(
    contract_dir: Path,
    task_dir: Path,
    previous_task_dir: Path | None = None,
    *,
    scope: str = "durable",
) -> tuple[ValidationError, ...]:
    if scope == "delegations":
        _, errors = parse_route(task_dir)
        return errors
    parsed = parse_manifest(task_dir / "02-execution-graph.toml")
    errors = list(parsed.errors)
    if parsed.manifest is None:
        return sorted_errors(errors)
    if parsed.manifest.version == 3:
        route, route_errors = parse_route(task_dir)
        errors.extend(route_errors)
        if route is not None:
            errors.extend(validate_route_references(parsed.manifest, task_dir))
    state, state_errors = parse_state(task_dir / "03-state.toml")
    errors.extend(state_errors)
    if state is None:
        return sorted_errors(errors)
    previous = None
    if previous_task_dir:
        previous_result = parse_manifest(previous_task_dir / "02-execution-graph.toml")
        errors.extend(previous_result.errors)
        previous = previous_result.manifest
    errors.extend(validate_references(parsed.manifest, state, task_dir, contract_dir))
    errors.extend(validate_lifecycle(parsed.manifest, state, previous))
    errors.extend(validate_review_evidence(parsed.manifest, state, task_dir))
    return sorted_errors(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_kapisch.py")
    parser.add_argument("--contract-dir", required=True, type=Path)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--previous-task-dir", type=Path)
    parser.add_argument(
        "--scope",
        choices=("durable", "delegations"),
        default="durable",
        help="durable validates the execution graph plus state, review evidence, and "
        "version-3 delegation records; delegations validates only the graph-free "
        "delegations/00-route.toml record",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    errors = validate(
        args.contract_dir, args.task_dir, args.previous_task_dir, scope=args.scope
    )
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
