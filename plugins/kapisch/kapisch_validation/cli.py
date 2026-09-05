from __future__ import annotations

import argparse
from contextlib import ExitStack
from importlib import resources
import json
from pathlib import Path
import sys

from .errors import ValidationError, sorted_errors
from .delegations import parse_route, validate_route_references
from .manifest import parse_manifest
from .references import parse_state, validate_references
from .outcomes import validate_outcomes
from .controller_view import validate_controller_view
from .review_evidence import validate_review_evidence
from .transitions import validate_lifecycle, validate_transition


BUNDLED_CONTRACT_ERROR = (
    "kapisch-validate: bundled contract resources are missing or corrupt. "
    "Reinstall kapisch-validation or pass --contract-dir PATH."
)
REQUIRED_CONTRACT_FILES = (
    "SKILL.md",
    "references/execution-graph.md",
    "references/resume.md",
    "references/review.md",
    "references/handoffs.md",
    "references/pressure-scenarios.md",
)


def _bundled_contract_resource():
    try:
        return resources.files("kapisch_validation.contracts")
    except ModuleNotFoundError:
        # The mapped contracts package exists only after a build. This fallback
        # keeps direct source-checkout execution working before installation.
        return Path(__file__).resolve().parents[1] / "skills" / "kapisch"


def _contract_is_usable(contract_dir: Path) -> bool:
    try:
        for relative_path in REQUIRED_CONTRACT_FILES:
            path = contract_dir / relative_path
            if not path.is_file():
                return False
            path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return True


def validate_delegation_snapshot(manifest, task_dir: Path) -> list[ValidationError]:
    if manifest.version not in {3, 4}:
        return []
    errors: list[ValidationError] = []
    route_path = task_dir / "delegations" / "00-route.toml"
    route_exists = route_path.is_file()
    routing = manifest.policies.get("ecosystem_routing")
    has_delegation_ids = any(
        node.raw.get("delegation_ids") for node in manifest.nodes
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
            errors.extend(validate_route_references(manifest, task_dir))
    return errors


def validate_snapshot(
    manifest, state, task_dir: Path, contract_dir: Path, *, include_controller_view: bool = True
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    errors.extend(validate_delegation_snapshot(manifest, task_dir))
    errors.extend(validate_references(manifest, state, task_dir, contract_dir))
    errors.extend(validate_lifecycle(manifest, state))
    errors.extend(validate_review_evidence(manifest, state, task_dir))
    errors.extend(validate_outcomes(manifest, state, task_dir))
    if include_controller_view and not errors:
        errors.extend(validate_controller_view(manifest, state, task_dir))
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
                    task_dir,
                    previous_task_dir,
                )
            )
    return sorted_errors(errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kapisch-validate")
    parser.add_argument(
        "--contract-dir",
        type=Path,
        help="contract directory override (defaults to bundled contracts)",
    )
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--previous-task-dir", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        contract_dir = args.contract_dir
        if contract_dir is None:
            try:
                contract_dir = stack.enter_context(
                    resources.as_file(_bundled_contract_resource())
                )
            except (FileNotFoundError, ModuleNotFoundError, OSError, TypeError):
                print(BUNDLED_CONTRACT_ERROR, file=sys.stderr)
                return 2
            if not _contract_is_usable(contract_dir):
                print(BUNDLED_CONTRACT_ERROR, file=sys.stderr)
                return 2
        errors = validate(contract_dir, args.task_dir, args.previous_task_dir)
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
