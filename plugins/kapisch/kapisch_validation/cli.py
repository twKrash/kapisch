from __future__ import annotations

import argparse
import sys
from contextlib import ExitStack
from importlib import resources
from pathlib import Path

from .advisory import STATE_PATH as ADVISORY_STATE_PATH
from .advisory import validate_advisory
from .artifact_io import load_toml_artifact
from .canonical_bytes import canonical_json_line, canonical_text_bytes
from .controller_view import validate_controller_view
from .delegations import parse_route, validate_route_references
from .errors import ValidationError, sorted_errors
from .execution_authority import validate_plan_authority
from .manifest import parse_manifest
from .outcomes import validate_outcomes
from .references import parse_state, validate_references
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


def _write_stdout(data: bytes) -> None:
    """Write canonical bytes, while supporting StringIO-based callers."""
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
    else:
        stream.write(data.decode("utf-8"))
        stream.flush()


def _diagnostic_text(value: str) -> str:
    """Keep diagnostics valid UTF-8 when native paths use surrogate escapes."""
    return value.encode("utf-8", errors="backslashreplace").decode("utf-8")


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
    advisory_errors: list[ValidationError] = []
    advisory_state = task_dir / ADVISORY_STATE_PATH
    if advisory_state.is_file():
        advisory_errors.extend(validate_advisory(task_dir))
        if not (task_dir / "02-execution-graph.toml").is_file():
            if (task_dir / "03-state.toml").exists():
                return sorted_errors(advisory_errors + [ValidationError(
                    "TWV-GRAPH-MISSING", str(task_dir / "02-execution-graph.toml"), "graph",
                    "execution state requires its execution graph",
                )])
            if previous_task_dir is not None and (
                (previous_task_dir / "02-execution-graph.toml").is_file()
                or (previous_task_dir / "03-state.toml").is_file()
            ):
                return sorted_errors(advisory_errors + [ValidationError(
                    "TWV-GRAPH-MISSING", str(task_dir / "02-execution-graph.toml"), "graph",
                    "prior execution history requires an execution graph",
                )])
            return sorted_errors(validate_advisory(task_dir, previous_task_dir))
    parsed = parse_manifest(task_dir / "02-execution-graph.toml")
    errors = advisory_errors + list(parsed.errors)
    if parsed.manifest is None:
        return sorted_errors(errors)
    state, state_errors = parse_state(task_dir / "03-state.toml")
    errors.extend(state_errors)
    if state is None:
        return sorted_errors(errors)
    if previous_task_dir is not None and (
        previous_task_dir / "03-state.toml"
    ).is_file() and not (previous_task_dir / "02-execution-graph.toml").is_file():
        errors.append(ValidationError(
            "TWV-GRAPH-MISSING",
            str(previous_task_dir / "02-execution-graph.toml"),
            "graph",
            "prior execution state requires its execution graph",
        ))
    current_advisory = advisory_state.is_file()
    previous_advisory = (
        previous_task_dir is not None
        and (previous_task_dir / ADVISORY_STATE_PATH).is_file()
        and not (previous_task_dir / "02-execution-graph.toml").is_file()
    )
    if current_advisory:
        advisory_data, advisory_failure = load_toml_artifact(advisory_state)
        accepted = advisory_data.get("accepted_architectures") if advisory_data else None
        if (
            advisory_failure is None
            and advisory_data is not None
            and (
                advisory_data.get("status") != "implementation-planning"
                or not isinstance(accepted, list)
                or not accepted
            )
        ):
            errors.append(
                ValidationError(
                    "ADV-PROMOTION-REQUIRED",
                    str(advisory_state),
                    "status",
                    "human acceptance and explicit promotion are required before creating an execution graph",
                )
            )
    source_plan = state.raw.get("source_plan")
    needs_advisory_authority = current_advisory or previous_advisory
    advisory_source = (
        task_dir if current_advisory else previous_task_dir if previous_advisory else None
    )
    if needs_advisory_authority and parsed.manifest.version not in {3, 4}:
        errors.append(ValidationError(
            "ADV-GRAPH-VERSION", str(task_dir / "02-execution-graph.toml"), "version",
            "advisory-authorized execution requires graph version 3 or 4",
        ))
    if needs_advisory_authority and (
        not isinstance(source_plan, str) or not source_plan.startswith("plans/")
    ):
        errors.append(
            ValidationError(
                "ADV-PLAN-AUTHORITY-MISSING",
                str(task_dir / "03-state.toml"),
                "source_plan",
                "promoted advisory work requires a content-addressed, human-approved plan",
            )
        )
    elif isinstance(source_plan, str) and source_plan.startswith("plans/"):
        errors.extend(validate_plan_authority(task_dir, source_plan, advisory_source))
    previous_manifest = None
    previous_state = None
    if previous_task_dir is not None:
        if previous_advisory:
            errors.extend(validate_advisory(previous_task_dir))
            prior, prior_failure = load_toml_artifact(
                previous_task_dir / ADVISORY_STATE_PATH
            )
            prior_architectures = prior.get("accepted_architectures") if prior else None
            if (
                prior_failure is None
                and prior is not None
                and (
                    not isinstance(prior.get("status"), str)
                    or prior.get("status") not in {"accepted", "implementation-planning"}
                    or not isinstance(prior_architectures, list)
                    or not prior_architectures
                )
            ):
                errors.append(
                    ValidationError(
                        "ADV-PROMOTION-REQUIRED",
                        str(previous_task_dir / ADVISORY_STATE_PATH),
                        "status",
                        "promotion requires a human-accepted architecture snapshot",
                    )
                )
        else:
            previous_result = parse_manifest(previous_task_dir / "02-execution-graph.toml")
            errors.extend(previous_result.errors)
            previous_manifest = previous_result.manifest
            previous_state, previous_state_errors = parse_state(
                previous_task_dir / "03-state.toml"
            )
            errors.extend(previous_state_errors)
    errors.extend(validate_snapshot(parsed.manifest, state, task_dir, contract_dir))
    if (
        previous_manifest is not None
        and previous_state is not None
        and previous_task_dir is not None
    ):
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
        records = [
            {key: _diagnostic_text(value) for key, value in error.to_dict().items()}
            for error in errors
        ]
        _write_stdout(canonical_json_line(records))
    elif errors:
        _write_stdout(
            canonical_text_bytes(
                "\n".join(_diagnostic_text(str(error)) for error in errors)
            )
        )
    return 2 if errors else 0
