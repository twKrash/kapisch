from __future__ import annotations

import hashlib
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from kapisch_validation.advisory import validate_advisory
from kapisch_validation.canonical_toml import render_toml
from kapisch_validation.cli import validate
from kapisch_validation.controller_view import (
    build_controller_view,
    render_controller_view,
)
from kapisch_validation.execution_authority import validate_plan_authority
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.references import parse_state

REVISION = "b" * 40


def write_snapshot(
    task_dir: Path,
    snapshot_id: str,
    content: str,
    relationships: list[dict[str, str]] | None = None,
    dependencies: list[dict[str, str]] | None = None,
) -> tuple[Path, str]:
    decision_id = f"D{snapshot_id[1:]}"
    snapshot = {
        "schema_version": 1,
        "task_id": task_dir.name,
        "snapshot_id": snapshot_id,
        "status": "accepted",
        "source_revision": REVISION,
        "architecture_content": content,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "decisions": [
            {"id": decision_id, "kind": "architecture", "answer": content, "source": "human"}
        ],
        "evidence_refs": [],
        "dependencies": dependencies or [],
        "relationships": relationships or [],
    }
    encoded = render_toml(snapshot)
    digest = hashlib.sha256(encoded).hexdigest()
    path = task_dir / "architectures" / f"{snapshot_id}-{digest}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return path, digest


def add_snapshot_to_state(task_dir: Path, snapshot_id: str, path: Path, digest: str) -> None:
    state_path = task_dir / "00-advisory.toml"
    state = tomllib.loads(state_path.read_text(encoding="utf-8"))
    state["accepted_architectures"].append(
        {"id": snapshot_id, "path": path.relative_to(task_dir).as_posix(), "digest": digest}
    )
    snapshot = tomllib.loads(path.read_text(encoding="utf-8"))
    state["decisions"].extend(snapshot["decisions"])
    state_path.write_bytes(render_toml(state))


def write_plan(
    task_dir: Path,
    snapshot_path: Path,
    snapshot_id: str,
    snapshot_digest: str,
    decision_dependencies: list[dict[str, str]] | None = None,
    *,
    reviewed: bool = True,
    architecture_bindings: list[dict[str, str]] | None = None,
) -> str:
    project_root = task_dir.parents[2]
    binding_path = snapshot_path.relative_to(project_root).as_posix()
    frontmatter = {
        "schema_version": 1,
        "task_id": task_dir.name,
        "status": "approved",
        "approval_source": "human",
        "source_revision": REVISION,
        "decision_dependencies_reviewed": reviewed,
        "architecture_bindings": architecture_bindings
        if architecture_bindings is not None
        else [{"snapshot_id": snapshot_id, "path": binding_path, "digest": snapshot_digest}],
        "decision_dependencies": decision_dependencies or [],
    }
    data = b"+++\n" + render_toml(frontmatter) + b"+++\n\n# Approved implementation plan\n\nImplement accepted architecture.\n"
    digest = hashlib.sha256(data).hexdigest()
    relative = Path("plans") / f"{digest}.md"
    (task_dir / relative).parent.mkdir(parents=True, exist_ok=True)
    (task_dir / relative).write_bytes(data)
    return relative.as_posix()


class ExecutionAuthorityTests(unittest.TestCase):
    def make_run(
        self,
        root: Path,
        dependencies: list[dict[str, str]] | None = None,
        task_id: str = "session-history-design",
        status: str = "accepted",
    ) -> tuple[Path, Path, str]:
        task_dir = root / ".kapisch" / "runs" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "01-architecture.md").write_bytes(b"Draft architecture.\n")
        path, digest = write_snapshot(
            task_dir, "A01", "Accepted architecture.\n", dependencies=dependencies
        )
        decision = {
            "id": "D01",
            "kind": "architecture",
            "answer": "Accepted architecture.\n",
            "source": "human",
        }
        state = {
            "schema_version": 1,
            "task_id": task_dir.name,
            "repository_revision": REVISION,
            "status": status,
            "intent": "Design session history.",
            "scope": ["history"],
            "exclusions": ["implementation"],
            "evidence_refs": [],
            "decisions": [decision],
            "unresolved_decisions": [],
            "proposal_path": "01-architecture.md",
            "proposal_sha256": hashlib.sha256(b"Draft architecture.\n").hexdigest(),
            "proposal_status": "accepted",
            "accepted_architectures": [
                {"id": "A01", "path": path.relative_to(task_dir).as_posix(), "digest": digest}
            ],
        }
        (task_dir / "00-advisory.toml").write_bytes(render_toml(state))
        return task_dir, path, digest

    def update_graph_source_plan(self, task_dir: Path, source_plan: str) -> None:
        manifest_path = task_dir / "02-execution-graph.toml"
        manifest_data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_data["source_plan"] = source_plan
        manifest_bytes = render_toml(manifest_data)
        manifest_path.write_bytes(manifest_bytes)

        state_path = task_dir / "03-state.toml"
        state_data = tomllib.loads(state_path.read_text(encoding="utf-8"))
        state_data["source_plan"] = source_plan
        state_path.write_bytes(render_toml(state_data))
        manifest = parse_manifest(manifest_path).manifest
        state, errors = parse_state(state_path)
        if manifest is None or state is None or errors:
            raise AssertionError(f"fixture became invalid before controller-view regeneration: {errors}")
        view = build_controller_view(manifest, state, {}, manifest_bytes)
        view_bytes = render_controller_view(view)
        (task_dir / "04-controller-view.toml").write_bytes(view_bytes)
        state_data["controller_view_sha256"] = hashlib.sha256(view_bytes).hexdigest()
        state_path.write_bytes(render_toml(state_data))
        state_path.write_bytes(render_toml(state_data))

    def test_cli_rejects_missing_graph_when_execution_state_survives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, _, _ = self.make_run(Path(temporary), task_id="valid")
            (task_dir / "03-state.toml").write_bytes(b"state = true\\n")
            errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", task_dir)
            self.assertIn("TWV-GRAPH-MISSING", {error.code for error in errors})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            task_dir, snapshot_path, snapshot_digest = self.make_run(
                root, task_id="valid", status="implementation-planning"
            )
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)
            self.update_graph_source_plan(task_dir, plan_path)

            errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", task_dir)

            self.assertEqual(errors, ())
            manifest = tomllib.loads((task_dir / "02-execution-graph.toml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], 4)

    def test_cli_rejects_unbound_plan_for_advisory_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            self.make_run(root, task_id="valid", status="implementation-planning")

            errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", task_dir)

            self.assertIn("ADV-PLAN-AUTHORITY-MISSING", {error.code for error in errors})

    def test_cli_promotes_accepted_advisory_into_new_v4_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            advisory_dir, snapshot_path, snapshot_digest = self.make_run(root)
            advisory_state_path = advisory_dir / "00-advisory.toml"
            advisory_state = tomllib.loads(advisory_state_path.read_text(encoding="utf-8"))
            advisory_state["status"] = "implementation-planning"
            advisory_state_path.write_bytes(render_toml(advisory_state))
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)
            self.update_graph_source_plan(task_dir, plan_path)

            errors = validate(
                Path(__file__).resolve().parents[2] / "skills/kapisch",
                task_dir,
                advisory_dir,
            )

            self.assertEqual(errors, ())

    def test_cli_rejects_promotion_without_architecture_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            advisory_dir, snapshot_path, snapshot_digest = self.make_run(root)
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            plan_path = write_plan(
                task_dir,
                snapshot_path,
                "A01",
                snapshot_digest,
                architecture_bindings=[],
            )
            self.update_graph_source_plan(task_dir, plan_path)

            errors = validate(
                Path(__file__).resolve().parents[2] / "skills/kapisch",
                task_dir,
                advisory_dir,
            )

            self.assertIn("ADV-PLAN-BINDINGS", {error.code for error in errors})

    def test_cli_rejects_binding_from_another_advisory_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            advisory_dir, _, _ = self.make_run(root)
            _, other_snapshot, other_digest = self.make_run(root, task_id="other-design")
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            plan_path = write_plan(task_dir, other_snapshot, "A01", other_digest)
            self.update_graph_source_plan(task_dir, plan_path)

            errors = validate(
                Path(__file__).resolve().parents[2] / "skills/kapisch",
                task_dir,
                advisory_dir,
            )

            self.assertIn("ADV-PLAN-BINDINGS", {error.code for error in errors})

    def test_cli_requires_content_addressed_plan_when_promoting_prior_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            advisory_dir, snapshot_path, snapshot_digest = self.make_run(root)
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)
            self.update_graph_source_plan(task_dir, plan_path)
            state_path = task_dir / "03-state.toml"
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            state["source_plan"] = "01-plan.md"
            state_path.write_bytes(render_toml(state))

            errors = validate(
                Path(__file__).resolve().parents[2] / "skills/kapisch",
                task_dir,
                advisory_dir,
            )

            self.assertIn("ADV-PLAN-AUTHORITY-MISSING", {error.code for error in errors})

    def test_cli_requires_explicit_promotion_before_graph_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / ".kapisch" / "runs" / "valid"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            task_dir, snapshot_path, snapshot_digest = self.make_run(root, task_id="valid")
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)
            self.update_graph_source_plan(task_dir, plan_path)

            errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", task_dir)

            self.assertIn("ADV-PROMOTION-REQUIRED", {error.code for error in errors})

    def test_approved_plan_binds_exact_accepted_snapshot_without_new_graph_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, snapshot_path, snapshot_digest = self.make_run(Path(temporary))
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertEqual(errors, [])
            self.assertFalse((task_dir / "02-execution-graph.toml").exists())

    def test_mutated_content_addressed_plan_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, snapshot_path, snapshot_digest = self.make_run(Path(temporary))
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)
            (task_dir / plan_path).write_bytes((task_dir / plan_path).read_bytes() + b"tampered")

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertIn("ADV-PLAN-DIGEST", {error.code for error in errors})

    def test_invalid_accepted_successor_blocks_predecessor_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir, predecessor, predecessor_digest = self.make_run(root)
            plan_path = write_plan(task_dir, predecessor, "A01", predecessor_digest)
            successor_dir, _, _ = self.make_run(root, task_id="architecture-amendment")
            successor, _ = write_snapshot(
                successor_dir,
                "A02",
                "Amended architecture.\\n",
                relationships=[
                    {
                        "kind": "supersedes",
                        "target_path": predecessor.relative_to(root).as_posix(),
                        "target_digest": predecessor_digest,
                    }
                ],
            )
            add_snapshot_to_state(successor_dir, "A02", successor, hashlib.sha256(successor.read_bytes()).hexdigest())
            successor.write_bytes(successor.read_bytes() + b"corruption")

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertIn("ADV-SNAPSHOT-DIGEST", {error.code for error in errors})

    def test_superseding_architecture_stales_plan_bound_to_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, snapshot_path, snapshot_digest = self.make_run(Path(temporary))
            old_path = snapshot_path.relative_to(task_dir.parents[2]).as_posix()
            new_path, new_digest = write_snapshot(
                task_dir,
                "A02",
                "Amended architecture.\n",
                relationships=[
                    {
                        "kind": "supersedes",
                        "target_path": old_path,
                        "target_digest": snapshot_digest,
                        "decision_id": "D02",
                    }
                ],
            )
            add_snapshot_to_state(task_dir, "A02", new_path, new_digest)
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest)

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertIn("ADV-AUTHORITY-STALE", {error.code for error in errors})
            self.assertEqual(validate_advisory(task_dir), [])

    def test_nested_snapshot_id_cannot_bypass_supersession_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            predecessor_dir, predecessor, predecessor_digest = self.make_run(root, task_id="predecessor")
            plan_path = write_plan(predecessor_dir, predecessor, "A01", predecessor_digest)
            successor_dir, _, _ = self.make_run(root, task_id="successor")
            successor, successor_digest = write_snapshot(
                successor_dir,
                "A/B",
                "Superseding architecture.\n",
                relationships=[
                    {
                        "kind": "supersedes",
                        "target_path": predecessor.relative_to(root).as_posix(),
                        "target_digest": predecessor_digest,
                        "decision_id": "D/B",
                    }
                ],
            )
            add_snapshot_to_state(successor_dir, "A/B", successor, successor_digest)

            errors = validate_plan_authority(predecessor_dir, plan_path)

            self.assertIn("ADV-SNAPSHOT-IDENTITY", {error.code for error in errors})

    def test_changed_decision_dependency_stales_approved_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency_path = root / "docs" / "adr.md"
            dependency_path.parent.mkdir()
            dependency_path.write_text("Accepted storage decision.\n", encoding="utf-8")
            digest = hashlib.sha256(dependency_path.read_bytes()).hexdigest()
            dependencies = [
                {
                    "decision_id": "D01",
                    "kind": "repository-file",
                    "path": "docs/adr.md",
                    "digest": digest,
                }
            ]
            task_dir, snapshot_path, snapshot_digest = self.make_run(root, dependencies)
            plan_path = write_plan(
                task_dir, snapshot_path, "A01", snapshot_digest, dependencies
            )
            dependency_path.write_text("Changed storage decision.\n", encoding="utf-8")

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertIn("ADV-AUTHORITY-STALE", {error.code for error in errors})

    def test_plan_dependency_kind_array_returns_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency_path = root / "docs" / "adr.md"
            dependency_path.parent.mkdir()
            dependency_path.write_text("Accepted decision.\n", encoding="utf-8")
            digest = hashlib.sha256(dependency_path.read_bytes()).hexdigest()
            dependency = {
                "decision_id": "D01", "kind": ["repository-file"],
                "path": "docs/adr.md", "digest": digest,
            }
            task_dir, snapshot_path, snapshot_digest = self.make_run(root, [dependency])
            plan_path = write_plan(task_dir, snapshot_path, "A01", snapshot_digest, [dependency])
            errors = validate_plan_authority(task_dir, plan_path)
            self.assertIn("ADV-PLAN-DEPENDENCY", {error.code for error in errors})

    def test_malformed_architecture_binding_returns_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, snapshot_path, digest = self.make_run(Path(temporary))
            plan_path = write_plan(task_dir, snapshot_path, "A01", digest)
            plan_file = task_dir / plan_path
            data = plan_file.read_bytes().replace(b'"A01"', b'["A01"]', 1)
            plan_file.write_bytes(data)
            # Re-address the changed plan, preserving syntactically valid TOML.
            new_digest = hashlib.sha256(data).hexdigest()
            renamed = task_dir / "plans" / f"{new_digest}.md"
            plan_file.rename(renamed)

            errors = validate_plan_authority(task_dir, renamed.relative_to(task_dir).as_posix())

            self.assertIn("ADV-PLAN-BINDINGS", {error.code for error in errors})

    def test_relationship_kind_table_returns_diagnostic_through_plan_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir, predecessor, predecessor_digest = self.make_run(root)
            plan_path = write_plan(task_dir, predecessor, "A01", predecessor_digest)
            successor_dir, _, _ = self.make_run(root, task_id="successor")
            successor, _ = write_snapshot(successor_dir, "A02", "successor", relationships=[{"kind": "supersedes", "target_path": predecessor.relative_to(root).as_posix(), "target_digest": predecessor_digest, "decision_id": "D02"}])
            snapshot = tomllib.loads(successor.read_text(encoding="utf-8"))
            snapshot["relationships"][0]["kind"] = {"bad": "kind"}
            encoded = render_toml(snapshot)
            new_digest = hashlib.sha256(encoded).hexdigest()
            new_successor = successor.with_name(f"A02-{new_digest}.toml")
            new_successor.write_bytes(encoded)
            successor.unlink()
            add_snapshot_to_state(successor_dir, "A02", new_successor, new_digest)

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertIn("ADV-AUTHORITY-INVALID", {error.code for error in errors})

    def test_cli_rejects_array_status_in_prior_graph_free_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior, _, _ = self.make_run(root, task_id="prior")
            prior_state_path = prior / "00-advisory.toml"
            prior_state = tomllib.loads(prior_state_path.read_text(encoding="utf-8"))
            prior_state["status"] = ["accepted"]
            prior_state_path.write_bytes(render_toml(prior_state))

            task_dir = root / ".kapisch" / "runs" / "current"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", task_dir)
            errors = validate(
                Path(__file__).resolve().parents[2] / "skills/kapisch", task_dir, prior
            )

            self.assertIn("ADV-STATE-STATUS", {error.code for error in errors})

    def test_cli_rejects_prior_state_without_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior, _, _ = self.make_run(root, task_id="prior", status="accepted")
            (prior / "03-state.toml").write_text("state = true\n", encoding="utf-8")
            current = root / ".kapisch" / "runs" / "current"
            shutil.copytree(Path(__file__).parent / "fixtures/valid-v4-controller", current)

            errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", current, prior)

            self.assertIn("TWV-GRAPH-MISSING", {error.code for error in errors})


    def test_cli_rejects_missing_graph_with_prior_durable_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current, _, _ = self.make_run(root, task_id="current", status="accepted")
            prior, _, _ = self.make_run(root, task_id="prior")
            (prior / "03-state.toml").write_text("state = true\n", encoding="utf-8")
            errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", current, prior)
            self.assertIn("TWV-GRAPH-MISSING", {error.code for error in errors})

    def test_cli_rejects_promotion_of_legacy_graph_versions(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        skill_dir = Path(__file__).resolve().parents[2] / "skills/kapisch"
        for version, fixture in (
            (1, "valid-v1-defaults"),
            (2, "valid-sequential-v2"),
            (3, "valid-v3-durable"),
            (4, "valid-v4-controller"),
        ):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                task_dir = root / ".kapisch" / "runs" / "valid"
                shutil.copytree(fixtures / fixture, task_dir)
                self.assertEqual(validate(skill_dir, task_dir), ())
                if version == 4:
                    task_dir, snapshot, digest = self.make_run(
                        root, task_id="valid", status="implementation-planning"
                    )
                    plan = write_plan(task_dir, snapshot, "A01", digest)
                    self.update_graph_source_plan(task_dir, plan)
                else:
                    task_dir, snapshot, digest = self.make_run(
                        root, task_id="valid", status="implementation-planning"
                    )
                    plan = write_plan(task_dir, snapshot, "A01", digest)
                    manifest_path = task_dir / "02-execution-graph.toml"
                    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["source_plan"] = plan
                    manifest_path.write_bytes(render_toml(manifest))
                    state_path = task_dir / "03-state.toml"
                    state = tomllib.loads(state_path.read_text(encoding="utf-8"))
                    state["source_plan"] = plan
                    state_path.write_bytes(render_toml(state))
                errors = validate(skill_dir, task_dir)
                codes = {error.code for error in errors}
                if version in (1, 2):
                    self.assertIn("ADV-GRAPH-VERSION", codes)
                else:
                    self.assertNotIn("ADV-GRAPH-VERSION", codes)
                    self.assertEqual(errors, ())


    def test_plan_requires_explicit_dependency_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, snapshot_path, snapshot_digest = self.make_run(Path(temporary))
            plan_path = write_plan(
                task_dir, snapshot_path, "A01", snapshot_digest, reviewed=False
            )

            errors = validate_plan_authority(task_dir, plan_path)

            self.assertIn("ADV-PLAN-REVIEW", {error.code for error in errors})


if __name__ == "__main__":
    unittest.main()
