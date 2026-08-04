from __future__ import annotations

import hashlib
import tempfile
import unittest
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
) -> Path:
    (task_dir / "delegations").mkdir(parents=True, exist_ok=True)
    path = task_dir / "delegations/00-route.toml"
    path.write_text(route_toml(task_id, route_id, steps), encoding="utf-8")
    return path


def write_step_files(
    task_dir: Path, step_id: str, context: str, evidence: str
) -> tuple[str, str, str, str]:
    cpath = f"delegations/{step_id}/00-context.md"
    epath = f"delegations/{step_id}/01-evidence.md"
    (task_dir / cpath).parent.mkdir(parents=True, exist_ok=True)
    (task_dir / cpath).write_text(context, encoding="utf-8")
    (task_dir / epath).write_text(evidence, encoding="utf-8")
    return cpath, sha256(context), epath, sha256(evidence)


def completed_step(
    step_id: str,
    sequence: int,
    *,
    parent: str = "unavailable",
    selection_mode: str = "explicit",
    capability_kind: str = "skill",
    requested: str = "instruction-only-skill",
    resolved: str = "instruction-only-skill",
    source_plugin: str = "unavailable",
    effect_class: str = "repository-read",
    authority_mode: str = "request-scoped",
    authority_ref: str = "request:test",
    result_revision: str = "head",
    context: str = "# context\n",
    evidence: str = "# evidence\n",
) -> dict[str, object]:
    cpath = csha = epath = esha = None
    return {
        "id": step_id,
        "sequence": sequence,
        "parent_node_id": parent,
        "status": "completed",
        "selection_mode": selection_mode,
        "capability_kind": capability_kind,
        "requested_capability": requested,
        "resolved_capability": resolved,
        "source_plugin": source_plugin,
        "effect_class": effect_class,
        "authority_mode": authority_mode,
        "authority_ref": authority_ref,
        "context_path": cpath,
        "context_sha256": csha,
        "evidence_path": epath,
        "evidence_sha256": esha,
        "source_revision": "base",
        "result_revision": result_revision,
    }


def make_manifest(
    nodes: list[Node], version: int = 3
) -> Manifest:
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


class DelegationBuilderTests(unittest.TestCase):
    """In-test builders must produce a valid route record."""

    def test_builder_produces_valid_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(
                task, "D01", "# context\n", "# evidence\n"
            )
            step = completed_step("D01", 1)
            step.update(
                {
                    "context_path": cpath,
                    "context_sha256": csha,
                    "evidence_path": epath,
                    "evidence_sha256": esha,
                }
            )
            write_route(task, "graph-free", "route-1", [step])
            route, errors = parse_route(task)
            self.assertEqual(errors, ())
            self.assertIsNotNone(route)

    def test_valid_route_parses_idempotently_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(
                task, "D01", "# context\n", "# evidence\n"
            )
            step = completed_step("D01", 1)
            step.update(
                {
                    "context_path": cpath,
                    "context_sha256": csha,
                    "evidence_path": epath,
                    "evidence_sha256": esha,
                }
            )
            write_route(task, "graph-free", "route-1", [step])
            _, first = parse_route(task)
            _, second = parse_route(task)
            self.assertEqual(first, ())
            self.assertEqual(second, ())


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

    def test_invalid_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(path.read_text(encoding="utf-8").replace("version = 1", "version = 2"), encoding="utf-8")
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-VERSION")

    def test_unknown_root_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(path.read_text(encoding="utf-8") + 'bogus="x"\n', encoding="utf-8")
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-SCHEMA-UNKNOWN-FIELD")

    def test_unknown_step_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha, "bogus": "x"})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-SCHEMA-UNKNOWN-FIELD")

    def test_invalid_step_id_grammar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"id": "X1", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-STEP-ID")

    def test_invalid_route_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            path = task / "delegations/00-route.toml"
            path.write_text(path.read_text(encoding="utf-8").replace('route_id = "r-1"', 'route_id = "!"'), encoding="utf-8")
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-ROUTE-ID")

    def test_duplicate_step_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            first = completed_step("D01", 1)
            first.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            second = completed_step("D01", 2)
            second.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [first, second])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-DUPLICATE-STEP-ID")

    def test_duplicate_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            first = completed_step("D01", 1)
            first.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            second = completed_step("D02", 1)
            second.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [first, second])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-DUPLICATE-SEQUENCE")

    def test_invalid_status_enum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"status": "running", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-ENUM")

    def test_parallel_started_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            first = completed_step("D01", 1)
            first.update({"status": "started", "resolved_capability": "skill-a", "context_path": cpath, "context_sha256": csha, "evidence_path": "unavailable", "evidence_sha256": "unavailable"})
            second = completed_step("D02", 2)
            second.update({"status": "started", "resolved_capability": "skill-b", "context_path": cpath, "context_sha256": csha, "evidence_path": "unavailable", "evidence_sha256": "unavailable"})
            write_route(task, "t", "r-1", [first, second])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-PARALLEL-STARTED")

    def test_ordering_later_step_before_earlier_completes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            first = completed_step("D01", 1)
            first.update({"status": "planned", "resolved_capability": "unavailable", "evidence_path": "unavailable", "evidence_sha256": "unavailable", "context_path": cpath, "context_sha256": csha})
            second = completed_step("D02", 2)
            second.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [first, second])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-ORDERING")

    def test_external_write_requires_explicit_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"effect_class": "external-write", "authority_mode": "request-scoped", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-EXPLICIT-AUTHORITY")

    def test_explicit_authority_requires_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"effect_class": "external-write", "authority_mode": "explicit-step", "authority_ref": "unavailable", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-AUTHORITY-REF")

    def test_completed_step_requires_resolved_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"resolved_capability": "unavailable", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-UNRESOLVED-CAPABILITY")

    def test_completed_step_requires_result_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"result_revision": "unavailable", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-RESULT-REVISION")

    def test_planned_step_requires_unavailable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"status": "planned", "resolved_capability": "unavailable", "context_path": cpath, "context_sha256": csha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-PREMATURE-EVIDENCE")

    def test_self_delegation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1)
            step.update({"requested_capability": "$kapisch", "context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-SELF-DELEGATION")


class EvidenceFileTests(unittest.TestCase):
    def _route_with_files(self, task: Path) -> dict[str, object]:
        cpath, csha, epath, esha = write_step_files(task, "D01", "# context\n", "# evidence\n")
        step = completed_step("D01", 1)
        step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
        return step

    def test_missing_context_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["context_path"] = "unavailable"
            step["context_sha256"] = "unavailable"
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-CONTEXT")

    def test_unreadable_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            evidence = task / "delegations/D01/01-evidence.md"
            evidence.chmod(0)
            try:
                write_route(task, "t", "r-1", [step])
                _, errors = parse_route(task)
                self.assertEqual(errors[0].code, "TWV-DELEG-UNREADABLE-EVIDENCE")
            finally:
                evidence.chmod(0o644)

    def test_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["context_path"] = "../../escape.md"
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-PATH-ESCAPE")

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
            csha = sha256("# context\n")
            step = completed_step("D01", 1)
            step.update({"context_path": "delegations/D01/00-context.md", "context_sha256": csha, "evidence_path": "delegations/D01/01-evidence.md", "evidence_sha256": sha256("# evidence\n")})
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-PATH-ESCAPE")

    def test_missing_evidence_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            (task / "delegations/D01/01-evidence.md").unlink()
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-MISSING-EVIDENCE")

    def test_invalid_utf8_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            (task / "delegations/D01/01-evidence.md").write_bytes(b"\xff\xfe\x00\x01")
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-EVIDENCE-ENCODING")

    def test_stale_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["evidence_sha256"] = sha256("# different\n")
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-STALE-EVIDENCE")

    def test_invalid_digest_format(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            step = self._route_with_files(task)
            step["evidence_sha256"] = "not-a-digest"
            write_route(task, "t", "r-1", [step])
            _, errors = parse_route(task)
            self.assertEqual(errors[0].code, "TWV-DELEG-INVALID-DIGEST")


class RouteReferenceTests(unittest.TestCase):
    def test_unresolved_step_reference(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D99"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="T01")
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
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
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="T01")
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-REUSED-STEP")

    def test_owner_mismatch(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="OTHER")
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-OWNER-MISMATCH")

    def test_orphan_owner(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral")])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="MISSING")
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-ORPHAN-OWNER")

    def test_orphaned_step_not_referenced(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral")])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="T01")
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-ORPHANED-STEP")

    def test_completed_node_with_incomplete_delegation(self) -> None:
        manifest = make_manifest([make_node("T01", "behavioral", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="T01")
            step.update({"status": "started", "resolved_capability": "skill-a", "evidence_path": "unavailable", "evidence_sha256": "unavailable", "context_path": cpath, "context_sha256": csha})
            write_route(task, "t", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-UNRESOLVED-DELEGATION")

    def test_review_node_write_delegation(self) -> None:
        manifest = make_manifest([make_node("R01", "review", delegation_ids=["D01"])])
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            step = completed_step("D01", 1, parent="R01", effect_class="external-write", authority_mode="explicit-step", authority_ref="gate:test")
            step.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [step])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors[0].code, "TWV-DELEG-REVIEW-WRITE")

    def test_valid_graph_references_have_no_findings(self) -> None:
        manifest = make_manifest(
            [
                make_node("T01", "behavioral", delegation_ids=["D01", "D02"]),
                make_node("R01", "review", delegation_ids=["D03"]),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            cpath, csha, epath, esha = write_step_files(task, "D01", "# c\n", "# e\n")
            first = completed_step("D01", 1, parent="T01", effect_class="repository-read")
            first.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            second = completed_step("D02", 2, parent="T01", effect_class="external-read")
            second.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            third = completed_step("D03", 3, parent="R01", effect_class="external-read")
            third.update({"context_path": cpath, "context_sha256": csha, "evidence_path": epath, "evidence_sha256": esha})
            write_route(task, "t", "r-1", [first, second, third])
            errors = validate_route_references(manifest, task)
            self.assertEqual(errors, ())


class DelegationScopeCliTests(unittest.TestCase):
    def test_cli_scope_delegations_validates_graph_free_route(self) -> None:
        errors = validate(Path("contracts"), FIXTURES / "valid-delegations-graph-free", scope="delegations")
        self.assertEqual(errors, ())

    def test_cli_scope_delegations_rejects_invalid_route(self) -> None:
        errors = validate(Path("contracts"), FIXTURES / "delegations-ordering", scope="delegations")
        self.assertTrue(errors)
        self.assertEqual(errors[0].code, "TWV-DELEG-ORDERING")

    def test_cli_durable_v3_validates_route_automatically(self) -> None:
        errors = validate(
            FIXTURES.parents[2] / "skills/kapisch",
            FIXTURES / "valid-v3-durable",
        )
        self.assertEqual(errors, ())

    def test_cli_durable_v3_rejects_bad_route(self) -> None:
        errors = validate(
            FIXTURES.parents[2] / "skills/kapisch",
            FIXTURES / "valid-v3-durable-unresolved",
        )
        self.assertTrue(any(error.code == "TWV-DELEG-UNRESOLVED-DELEGATION" for error in errors))


if __name__ == "__main__":
    unittest.main()
