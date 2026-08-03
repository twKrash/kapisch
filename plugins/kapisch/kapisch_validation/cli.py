from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import ValidationError, sorted_errors
from .manifest import parse_manifest
from .references import parse_state, validate_references
from .review_evidence import validate_review_evidence
from .transitions import validate_lifecycle


def validate(
    contract_dir: Path, task_dir: Path, previous_task_dir: Path | None = None
) -> tuple[ValidationError, ...]:
    parsed = parse_manifest(task_dir / "02-execution-graph.toml")
    errors = list(parsed.errors)
    if parsed.manifest is None:
        return sorted_errors(errors)
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
