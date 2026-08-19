from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from kapisch_validation.cli import validate
from kapisch_validation.delegations import parse_route, validate_route_references
from kapisch_validation.models import Manifest, Node

FIXTURES = Path(__file__).parent / "fixtures"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def route_toml(task_id: str, route_id: str, steps: list[dict[str, object]]) -> str:
    lines = [
        "version = 1",
        f'task_id = "{task_id}"',
        f'route_id = "{route_id}"',
        'source_revision = "base"',
    ]
    for step in steps:
        lines.append("[[steps]]")
        for key, value in step.items():
            if isinstance(value, bool):
                lines.append(f"{key}={str(value).lower()}")
            elif isinstance(value, int):
                lines.append(f"{key}={value}")
            else:
                lines.append(f'{key}="{value}"')
    return "\n".join(lines) + "\n"


def write_route(
    task_dir: Path,
    task_id: str,
    route_id: str,
    steps: list[dict[str, object]],
) -> None:
    (task_dir / "delegations").mkdir(parents=True, exist_ok=True)
    (task_dir / "delegations/00-route.toml").write_text(
        route_toml(task_id, route_id, steps), encoding="utf-8"
    )


def write_step_files(
    task_dir: Path, step_id: str, context: str, evidence: str
) -> tuple[str, str, str, str]:
    cpath = f"delegations/{step_id}/00-context.md"
    epath = f"delegations/{step_id}/01-evidence.md"
    (task_dir / cpath).parent.mkdir(parents=True, exist_ok=True)
    (task_dir / cpath).write_text(context, encoding="utf-8")
    (task_dir / epath).write_text(evidence, encoding="utf-8")
    return cpath, sha256(context), epath, sha256(evidence)


def minimal_step(
    step_id: str,
    sequence: int,
    *,
    parent: str = "T01",
    selection_mode: str = "explicit",
    capability_kind: str = "skill",
    requested: str = "instruction-only-skill",
    resolved: str = "instruction-only-skill",
    source_plugin: str = "unavailable",
    effect_class: str = "repository-read",
    authority_mode: str = "request-scoped",
    authority_ref: str = "request:test",
) -> dict[str, object]:
    return {
        "id": step_id,
        "sequence": sequence,
        "parent_node_id": parent,
        "selection_mode": selection_mode,
        "capability_kind": capability_kind,
        "requested_capability": requested,
        "resolved_capability": resolved,
        "source_plugin": source_plugin,
        "effect_class": effect_class,
        "authority_mode": authority_mode,
        "authority_ref": authority_ref,
        "context_path": f"delegations/{step_id}/00-context.md",
        "context_sha256": sha256("# context\n"),
        "evidence_path": f"delegations/{step_id}/01-evidence.md",
        "evidence_sha256": sha256("# evidence\n"),
    }


def materialize(task_dir: Path, step: dict[str, object]) -> dict[str, object]:
    """Write the step's context/evidence files and fix its digests."""
    step_id = step["id"]
    cpath = f"delegations/{step_id}/00-context.md"
    epath = f"delegations/{step_id}/01-evidence.md"
    (task_dir / cpath).parent.mkdir(parents=True, exist_ok=True)
    (task_dir / cpath).write_text("# context\n", encoding="utf-8")
    (task_dir / epath).write_text("# evidence\n", encoding="utf-8")
    step = dict(step)
    step["context_path"] = cpath
    step["context_sha256"] = sha256("# context\n")
    step["evidence_path"] = epath
    step["evidence_sha256"] = sha256("# evidence\n")
    return step


def make_manifest(nodes: list[Node], version: int = 3) -> Manifest:
    return Manifest(
        version,
        "test-task",
        "base",
        {
            "execution": "sequential",
            "executor": "implementer",
            "dispatch": "single",
            "model_tier": "standard",
            "batching": "off",
            "parallelism": "off",
            "max_parallel_agents": 1,
            "commit": "manual",
            "push": "manual",
            "fix_policy": "manual",
            "max_fix_rounds": 1,
            "ecosystem_routing": "auto",
        },
        tuple(nodes),
        "/virtual/02-execution-graph.toml",
        "01-plan.md",
    )


def make_node(
    node_id: str,
    kind: str,
    status: str = "complete",
    delegation_ids: list[str] | None = None,
) -> Node:
    raw: dict[str, object] = {
        "id": node_id,
        "kind": kind,
        "status": status,
        "depends_on": [],
    }
    if delegation_ids:
        raw["delegation_ids"] = delegation_ids
    return Node(node_id, 1, kind, status, (), ("", "", "", ""), None, raw)


class RouteSchemaTests(unittest.TestCase):
    def test_missing_route_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, errors = parse_route(Path(temporary))
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-ARTIFACT")

    def test_malformed_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "delegations").mkdir()
            (task / "delegations/00-route.toml").write_text("version = [", encoding="utf-8")
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MALFORMED-TOML")

    def test_invalid_utf8_route_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "delegations").mkdir()
            (task / "delegations/00-route.toml").write_bytes(
                b'version = 1\ntask_id = "\xff\xfe"'
            )
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MALFORMED-TOML")

    def test_unreadable_route_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "delegations").mkdir()
            path = task / "delegations/00-route.toml"
            path.write_text("version = 1\n", encoding="utf-8")
            with mock.patch.object(Path, "open", side_effect=PermissionError("denied")):
                _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-UNREADABLE-ROUTE")

    def test_empty_route_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "delegations").mkdir()
            (task / "delegations/00-route.toml").write_text(
                '\n'.join(
                    [
                        "version = 1",
                        'task_id = "test-task"',
                        'route_id = "r-1"',
                        'source_revision = "base"',
                        "steps = []",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-EMPTY-ROUTE")

    def test_invalid_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            write_route(task, "test-task", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace("version = 1", "version = 2"),
                encoding="utf-8",
            )
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-VERSION")

    def test_unknown_root_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            write_route(task, "test-task", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(
                path.read_text(encoding="utf-8") + 'bogus="x"\n', encoding="utf-8"
            )
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-SCHEMA-UNKNOWN-FIELD")

    def test_unknown_step_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["bogus"] = "x"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-SCHEMA-UNKNOWN-FIELD")

    def test_invalid_step_id_grammar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["id"] = "X1"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-INVALID-STEP-ID" for error in errors)
            )

    def test_non_string_step_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["id"] = 1
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-STEP-ID")

    def test_invalid_route_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            write_route(task, "test-task", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace('route_id = "r-1"', 'route_id = "!"'),
                encoding="utf-8",
            )
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-ROUTE-ID")

    def test_duplicate_step_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            first = materialize(task, minimal_step("D01", 1))
            second = dict(first)
            second["sequence"] = 2
            write_route(task, "test-task", "r-1", [first, second])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-DUPLICATE-STEP-ID")

    def test_duplicate_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            first = materialize(task, minimal_step("D01", 1))
            second = materialize(task, minimal_step("D02", 1))
            write_route(task, "test-task", "r-1", [first, second])
            _, errors = parse_route(task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-DUPLICATE-SEQUENCE" for error in errors)
            )

    def test_invalid_enum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["capability_kind"] = "watcher"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-ENUM")

    def test_enum_list_value_fails_closed_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            lines = route_toml("test-task", "r-1", [step]).splitlines()
            lines = [
                line if not line.startswith("capability_kind=") else 'capability_kind=["skill"]'
                for line in lines
            ]
            (task / "delegations/00-route.toml").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            _, errors = parse_route(task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-INVALID-ENUM" for error in errors)
            )

    def test_every_enum_rejects_non_scalar_values_without_crashing(self) -> None:
        allowed_values = {
            "selection_mode": "explicit",
            "capability_kind": "skill",
            "effect_class": "repository-read",
            "authority_mode": "request-scoped",
        }
        for field, value in allowed_values.items():
            for malformed in (f'["{value}"]', '{ value = "x" }'):
                with self.subTest(field=field, malformed=malformed), tempfile.TemporaryDirectory() as temporary:
                    task = Path(temporary)
                    step = materialize(task, minimal_step("D01", 1))
                    lines = route_toml("test-task", "r-1", [step]).splitlines()
                    lines = [
                        line if not line.startswith(f"{field}=") else f"{field}={malformed}"
                        for line in lines
                    ]
                    (task / "delegations/00-route.toml").write_text(
                        "\n".join(lines) + "\n", encoding="utf-8"
                    )
                    _, errors = parse_route(task)
                    self.assertTrue(
                        any(error.code == "TWV-DELEG-INVALID-ENUM" for error in errors)
                    )

    def test_self_delegation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["requested_capability"] = "$kapisch"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-SELF-DELEGATION")

    def test_self_delegation_list_value_fails_closed_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            lines = route_toml("test-task", "r-1", [step]).splitlines()
            lines = [
                line if not line.startswith("requested_capability=") else 'requested_capability=["$kapisch"]'
                for line in lines
            ]
            (task / "delegations/00-route.toml").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
            _, errors = parse_route(task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-WRONG-SHAPE" for error in errors)
            )

    def test_read_only_effect_classes_are_accepted(self) -> None:
        for effect_class in ("repository-read", "external-read"):
            with (
                self.subTest(effect_class=effect_class),
                tempfile.TemporaryDirectory() as temporary,
            ):
                task = Path(temporary)
                step = materialize(
                    task, minimal_step("D01", 1, effect_class=effect_class)
                )
                write_route(task, "test-task", "r-1", [step])
                _, errors = parse_route(task)
                self.assertEqual(errors, ())

    def test_external_effect_classes_are_rejected_even_with_authority(self) -> None:
        for effect_class in ("external-write", "destructive"):
            with (
                self.subTest(effect_class=effect_class),
                tempfile.TemporaryDirectory() as temporary,
            ):
                task = Path(temporary)
                step = materialize(
                    task,
                    minimal_step(
                        "D01",
                        1,
                        effect_class=effect_class,
                        authority_mode="explicit-step",
                        authority_ref="gate:test",
                    ),
                )
                write_route(task, "test-task", "r-1", [step])
                _, errors = parse_route(task)
                self.assertEqual(
                    [error.code for error in errors],
                    ["TWV-DELEG-UNSUPPORTED-EXTERNAL-EFFECT"],
                )

    def test_unsupported_interrupted_external_write_is_not_safely_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            for task in (current, previous):
                shutil.copytree(FIXTURES / "valid-v3-durable", task)
                route = task / "delegations/00-route.toml"
                route.write_text(
                    route.read_text(encoding="utf-8")
                    .replace(
                        'effect_class="repository-read"',
                        'effect_class="external-write"',
                        1,
                    )
                    .replace(
                        'authority_mode="request-scoped"',
                        'authority_mode="explicit-step"',
                        1,
                    ),
                    encoding="utf-8",
                )

            errors = validate(
                FIXTURES.parents[2] / "skills/kapisch",
                current,
                previous,
            )

            self.assertTrue(
                any(
                    error.code == "TWV-DELEG-UNSUPPORTED-EXTERNAL-EFFECT"
                    for error in errors
                ),
                errors,
            )

    def test_explicit_authority_requires_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(
                task,
                minimal_step("D01", 1, effect_class="external-write", authority_mode="explicit-step", authority_ref="unavailable"),
            )
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-AUTHORITY-REF")

    def test_request_scoped_authority_requires_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(
                task,
                minimal_step("D01", 1, authority_ref="unavailable"),
            )
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-AUTHORITY-REF")

    def test_parent_node_must_not_use_graph_free_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="unavailable"))
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-OWNER")

    def test_capability_unavailable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["requested_capability"] = "unavailable"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-WRONG-SHAPE")
            self.assertEqual(errors[0].reference, "steps[0].requested_capability")
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["resolved_capability"] = "unavailable"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-WRONG-SHAPE")
            self.assertEqual(errors[0].reference, "steps[0].resolved_capability")

    def test_resolved_capability_non_string_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            step["resolved_capability"] = 5
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-WRONG-SHAPE")

    def test_missing_required_step_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1))
            del step["source_plugin"]
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-FIELD")
            self.assertEqual(errors[0].reference, "steps[0].source_plugin")


class EvidenceFileTests(unittest.TestCase):
    def _route_with_files(self, task: Path) -> dict[str, object]:
        return materialize(task, minimal_step("D01", 1))

    def test_evidence_path_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["context_path"] = "delegations/D01/other.md"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-EVIDENCE-PATH-BINDING")

    def test_missing_context_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["context_path"] = "unavailable"
            step["context_sha256"] = "unavailable"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(
                [(error.code, error.reference) for error in errors],
                [("TWV-DELEG-MISSING-CONTEXT", "steps[0].context_path")],
            )

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["context_path"] = "../../escape.md"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-PATH-ESCAPE" for error in errors)
            )

    @unittest.skipIf(os.name == "nt", "symlink creation requires privileges on Windows")
    def test_symlinked_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "task"
            (task / "delegations").mkdir(parents=True)
            outside = root / "outside.md"
            outside.write_text("# evidence\n", encoding="utf-8")
            link = task / "delegations/D01"
            link.mkdir()
            (link / "01-evidence.md").symlink_to(outside)
            (task / "delegations/D01/00-context.md").write_text("# context\n", encoding="utf-8")
            step = minimal_step("D01", 1)
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-PATH-ESCAPE" for error in errors)
            )

    def test_missing_evidence_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            (task / "delegations/D01/01-evidence.md").unlink()
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-EVIDENCE")

    def test_invalid_utf8_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            (task / "delegations/D01/01-evidence.md").write_bytes(b"\xff\xfe\x00\x01")
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-EVIDENCE-ENCODING")

    @unittest.skipIf(os.name == "nt", "chmod does not revoke read access on Windows")
    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "root bypasses mode-based read denial",
    )
    def test_unreadable_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            evidence = task / "delegations/D01/01-evidence.md"
            evidence.chmod(0)
            try:
                write_route(task, "test-task", "r-1", [step])
                _, errors = parse_route(task)
                self.assertEqual(errors[0].code, "TWV-DELEG-UNREADABLE-EVIDENCE")
            finally:
                evidence.chmod(0o644)

    def test_stale_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["evidence_sha256"] = sha256("# different\n")
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-STALE-EVIDENCE")

    def test_invalid_digest_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["evidence_sha256"] = "not-a-digest"
            write_route(task, "test-task", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-DIGEST")


class RouteReferenceTests(unittest.TestCase):
    def test_unresolved_step_reference(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D99"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="T01"))
            write_route(task, "test-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-UNRESOLVED-STEP")

    def test_reused_step_reference(self) -> None:
        manifest = make_manifest(
            [
                make_node("T01", "behavioral", delegation_ids=["D01"]),
                make_node("T02", "behavioral", delegation_ids=["D01"]),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="T01"))
            write_route(task, "test-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-REUSED-STEP")

    def test_owner_mismatch(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="OTHER"))
            write_route(task, "test-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-OWNER-MISMATCH")

    def test_orphan_owner(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral")])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="MISSING"))
            write_route(task, "test-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-ORPHAN-OWNER")

    def test_orphaned_step_not_referenced(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral")])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="T01"))
            write_route(task, "test-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-ORPHANED-STEP")

    def test_review_node_write_delegation(self) -> None:
        manifest = make_manifest([make_node("R01", "review", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(
                task,
                minimal_step("D01", 1, parent="R01", effect_class="repository-write"),
            )
            write_route(task, "test-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-REVIEW-WRITE")

    def test_route_task_id_mismatch(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="T01"))
            write_route(task, "other-task", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-TASK-MISMATCH")

    def test_route_source_revision_mismatch(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = materialize(task, minimal_step("D01", 1, parent="T01"))
            write_route(task, "test-task", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(
                path.read_text(encoding="utf-8").replace('source_revision = "base"', 'source_revision = "other"'),
                encoding="utf-8",
            )
            errors = validate_route_references(manifest, task)
            self.assertTrue(
                any(error.code == "TWV-DELEG-REVISION-MISMATCH" for error in errors)
            )

    def test_valid_graph_references_have_no_findings(self) -> None:
        manifest = make_manifest(
            [
                make_node("T01", "behavioral", delegation_ids=["D01", "D02"]),
                make_node("R01", "review", delegation_ids=["D03"]),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            first = materialize(task, minimal_step("D01", 1, parent="T01"))
            second = materialize(task, minimal_step("D02", 2, parent="T01", effect_class="external-read"))
            third = materialize(task, minimal_step("D03", 3, parent="R01", effect_class="external-read"))
            write_route(task, "test-task", "r-1", [first, second, third])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors, ())


class DelegationCliTests(unittest.TestCase):
    def test_cli_durable_v3_validates_route_automatically(self) -> None:
        errors = validate(
            FIXTURES.parents[2] / "skills/kapisch",
            FIXTURES / "valid-v3-durable",
        )
        self.assertEqual(errors, ())

    def test_cli_durable_v3_no_delegation_valid(self) -> None:
        errors = validate(
            FIXTURES.parents[2] / "skills/kapisch",
            FIXTURES / "valid-v3-no-delegation",
        )
        self.assertEqual(errors, ())

    def test_cli_durable_v3_off_with_refs_rejected(self) -> None:
        errors = validate(
            FIXTURES.parents[2] / "skills/kapisch",
            FIXTURES / "invalid-v3-off-with-refs",
        )
        self.assertEqual(
            {error.code for error in errors},
            {"TWV-DELEG-ROUTING-OFF-WITH-REFS", "TWV-DELEG-ROUTE-WITH-ROUTING-OFF"},
        )

    def test_cli_durable_v3_missing_route_with_refs_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            shutil.copytree(FIXTURES / "valid-v3-durable", task, dirs_exist_ok=True)
            (task / "delegations/00-route.toml").unlink()
            errors = validate(FIXTURES.parents[2] / "skills/kapisch", task)
        self.assertTrue(
            any(error.code == "TWV-DELEG-MISSING-ARTIFACT" for error in errors)
        )

    def test_cli_durable_v3_empty_route_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            shutil.copytree(FIXTURES / "valid-v3-no-delegation", task, dirs_exist_ok=True)
            (task / "delegations").mkdir(exist_ok=True)
            (task / "delegations/00-route.toml").write_text(
                '\n'.join(
                    [
                        "version = 1",
                        'task_id = "valid-v3-durable"',
                        'route_id = "route-empty"',
                        'source_revision = "base"',
                        "steps = []",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            errors = validate(FIXTURES.parents[2] / "skills/kapisch", task)
        self.assertTrue(any(error.code == "TWV-DELEG-EMPTY-ROUTE" for error in errors))


if __name__ == "__main__":
    unittest.main()
