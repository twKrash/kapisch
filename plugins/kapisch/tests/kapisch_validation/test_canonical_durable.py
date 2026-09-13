from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

from kapisch_validation.cli import validate
from kapisch_validation.manifest import render_manifest
from kapisch_validation.references import render_state


FIXTURES = Path(__file__).parent / "fixtures"
PLUGIN = Path(__file__).resolve().parents[2]


class CanonicalDurableArtifactTests(unittest.TestCase):
    def load_manifest(self, fixture: str = "valid-v4-controller") -> dict[str, object]:
        return tomllib.loads(
            (FIXTURES / fixture / "02-execution-graph.toml").read_text(encoding="utf-8")
        )

    def load_state(self) -> dict[str, object]:
        return tomllib.loads(
            (FIXTURES / "valid-v4-controller/03-state.toml").read_text(encoding="utf-8")
        )

    def test_initial_manifest_and_state_ignore_unordered_input_order(self) -> None:
        root = FIXTURES / "valid-v4-controller"
        manifest_a = tomllib.loads((root / "02-execution-graph.toml").read_text(encoding="utf-8"))
        manifest_b = deepcopy(manifest_a)
        manifest_a["nodes"] = list(reversed(manifest_a["nodes"]))
        manifest_a["nodes"][0]["depends_on"] = list(reversed(manifest_a["nodes"][0]["depends_on"]))
        manifest_a["nodes"][0]["reads"] = ["src/z.py", "src/a.py", "src/z.py"]
        manifest_b["nodes"][-1]["reads"] = ["src/a.py", "src/z.py"]
        state_a = tomllib.loads((root / "03-state.toml").read_text(encoding="utf-8"))
        state_b = deepcopy(state_a)
        state_a["completed_node_ids"] = list(reversed(state_a["completed_node_ids"]))
        self.assertEqual(render_manifest(manifest_a, initial=True), render_manifest(manifest_b, initial=True))
        self.assertEqual(render_state(state_a), render_state(state_b))
        self.assertTrue(render_manifest(manifest_a, initial=True).startswith(b'"version" = 4\n"task_id" = '))
        self.assertTrue(render_state(state_a).startswith(b'"task_id" = '))

    def test_semantic_sequence_order_is_preserved(self) -> None:
        raw = tomllib.loads((FIXTURES / "valid-v4-controller/02-execution-graph.toml").read_text(encoding="utf-8"))
        first = deepcopy(raw)
        second = deepcopy(raw)
        first["nodes"][0]["verification"] = ["first", "second"]
        second["nodes"][0]["verification"] = ["second", "first"]
        self.assertNotEqual(render_manifest(first, initial=True), render_manifest(second, initial=True))

    def test_reencoded_snapshot_passes_full_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-v4-controller", task)
            graph = task / "02-execution-graph.toml"
            state = task / "03-state.toml"
            graph.write_bytes(render_manifest(tomllib.loads(graph.read_text(encoding="utf-8")), initial=False))
            state.write_bytes(render_state(tomllib.loads(state.read_text(encoding="utf-8"))))
            result = subprocess.run(
                [sys.executable, str(PLUGIN / "scripts/render_controller_view.py"), "--task-dir", str(task)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(list(validate(PLUGIN / "skills/kapisch", task)), [])

    def test_manifest_renderer_accepts_each_supported_version(self) -> None:
        for fixture in (
            "valid-v1-defaults", "valid-sequential-v2",
            "valid-v3-durable", "valid-v4-controller",
        ):
            with self.subTest(fixture=fixture):
                rendered = render_manifest(self.load_manifest(fixture), initial=False)
                self.assertTrue(rendered.endswith(b"\n"))

    def test_v1_renderer_preserves_omitted_compatibility_defaults(self) -> None:
        raw = self.load_manifest("valid-v1-defaults")
        raw["policies"] = {}
        parsed = tomllib.loads(render_manifest(raw, initial=False).decode("utf-8"))
        self.assertEqual(parsed["policies"], {})

    def test_manifest_renderer_rejects_illegal_versions_and_nested_shapes(self) -> None:
        cases = []
        missing_view = self.load_manifest()
        del missing_view["controller_view"]
        cases.append(missing_view)
        legacy_view = self.load_manifest("valid-v3-durable")
        legacy_view["controller_view"] = "04-controller-view.toml"
        cases.append(legacy_view)
        unknown_attempt = self.load_manifest()
        unknown_attempt["nodes"][0]["assignment"]["attempts"][0]["unknown"] = "value"
        cases.append(unknown_attempt)
        missing_attempt_field = self.load_manifest()
        del missing_attempt_field["nodes"][0]["assignment"]["attempts"][0]["status"]
        cases.append(missing_attempt_field)
        invalid_evidence = self.load_manifest()
        invalid_evidence["nodes"][0]["verification_evidence"][0]["output_sha256"] = "ABC"
        cases.append(invalid_evidence)
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    render_manifest(raw, initial=False)

    def test_manifest_renderer_validates_declared_paths_but_preserves_globs(self) -> None:
        raw = self.load_manifest()
        raw["nodes"][0]["writes"] = ["src/**/*.py", "https://example.test/data"]
        render_manifest(raw, initial=False)
        for mutate in (
            lambda data: data.update(source_plan="../outside.md"),
            lambda data: data["nodes"][0].update(context="/absolute.md"),
            lambda data: data["nodes"][0]["verification_evidence"][0].update(
                evidence_ref="../evidence.md"
            ),
            lambda data: data["nodes"][0].update(reads=["/absolute/path.py"]),
            lambda data: data["nodes"][0].update(writes=["C:\\checkout\\path.py"]),
            lambda data: data["nodes"][0].update(reads=["../escape.py"]),
        ):
            invalid = self.load_manifest()
            mutate(invalid)
            with self.assertRaises(ValueError):
                render_manifest(invalid, initial=False)

    def test_manifest_renderer_preserves_opaque_context_references(self) -> None:
        raw = self.load_manifest()
        node = raw["nodes"][0]
        node["context_refs"] = ["https://example.test/evidence", "knowledge:D-001"]
        node["assignment"]["context_refs"] = ["assignment:A-previous"]
        node["assignment"]["attempts"][0]["context_scope_ref"] = "scope:bounded"
        node["assignment"]["escalations"] = []
        parsed = tomllib.loads(render_manifest(raw, initial=False).decode("utf-8"))
        self.assertEqual(parsed["nodes"][0]["context_refs"], node["context_refs"])
        self.assertEqual(
            parsed["nodes"][0]["assignment"]["context_refs"],
            node["assignment"]["context_refs"],
        )

    def test_mutation_preserves_empty_node_extension_presence(self) -> None:
        raw = self.load_manifest()
        raw["nodes"][0]["extensions"] = {}
        mutated = tomllib.loads(render_manifest(raw, initial=False).decode("utf-8"))
        created = tomllib.loads(render_manifest(raw, initial=True).decode("utf-8"))
        self.assertEqual(mutated["nodes"][0]["extensions"], {})
        self.assertNotIn("extensions", created["nodes"][0])

    def test_state_renderer_requires_and_validates_complete_schema(self) -> None:
        cases = []
        missing = self.load_state()
        del missing["next_action"]
        cases.append(missing)
        partial_view = self.load_state()
        del partial_view["controller_view_sha256"]
        cases.append(partial_view)
        bad_digest = self.load_state()
        bad_digest["controller_view_sha256"] = "ABC"
        cases.append(bad_digest)
        bad_path = self.load_state()
        bad_path["latest_approving_review_path"] = "../review.md"
        cases.append(bad_path)
        bad_status = self.load_state()
        bad_status["workflow_status"] = "done"
        cases.append(bad_status)
        bad_extension = self.load_state()
        bad_extension["extensions"] = {"not-a-namespace": {"enabled": True}}
        cases.append(bad_extension)
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    render_state(raw)

    def test_state_renderer_rejects_duplicate_membership_instead_of_masking_it(self) -> None:
        duplicate = self.load_state()
        duplicate["completed_node_ids"].append("T01")
        with self.assertRaises(ValueError):
            render_state(duplicate)

        overlap = self.load_state()
        overlap["running_node_ids"] = ["T01"]
        with self.assertRaises(ValueError):
            render_state(overlap)


if __name__ == "__main__":
    unittest.main()
