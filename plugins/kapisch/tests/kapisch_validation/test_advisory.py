from __future__ import annotations

import hashlib
import tempfile
import tomllib
import unittest
from pathlib import Path

from kapisch_validation.advisory import validate_advisory
from kapisch_validation.canonical_toml import render_toml
from kapisch_validation.cli import validate

REVISION = "a" * 40


def write_advisory(task_dir: Path) -> tuple[Path, str]:
    task_dir.mkdir(parents=True)
    proposal_content = "# Session history architecture\n\nKeep history in durable storage.\n"
    (task_dir / "01-architecture.md").write_bytes(proposal_content.encode("utf-8"))
    decision = {
        "id": "D01",
        "kind": "architecture",
        "answer": "Keep history in durable storage.",
        "source": "human",
    }
    architecture_content = "# Session history architecture\n\nKeep history in durable storage.\n"
    snapshot = {
        "schema_version": 1,
        "task_id": task_dir.name,
        "snapshot_id": "A01",
        "status": "accepted",
        "source_revision": REVISION,
        "architecture_content": architecture_content,
        "content_sha256": hashlib.sha256(architecture_content.encode("utf-8")).hexdigest(),
        "decisions": [decision],
        "evidence_refs": [],
        "dependencies": [],
        "relationships": [],
    }
    snapshot_bytes = render_toml(snapshot)
    digest = hashlib.sha256(snapshot_bytes).hexdigest()
    snapshot_path = Path("architectures") / f"A01-{digest}.toml"
    (task_dir / snapshot_path).parent.mkdir()
    (task_dir / snapshot_path).write_bytes(snapshot_bytes)
    state = {
        "schema_version": 1,
        "task_id": task_dir.name,
        "repository_revision": REVISION,
        "status": "accepted",
        "intent": "Design session-history architecture.",
        "scope": ["session-history storage"],
        "exclusions": ["implementation"],
        "evidence_refs": [],
        "decisions": [decision],
        "unresolved_decisions": [],
        "proposal_path": "01-architecture.md",
        "proposal_sha256": hashlib.sha256(proposal_content.encode("utf-8")).hexdigest(),
        "proposal_status": "accepted",
        "accepted_architectures": [
            {"id": "A01", "path": snapshot_path.as_posix(), "digest": digest}
        ],
    }
    (task_dir / "00-advisory.toml").write_bytes(render_toml(state))
    return task_dir / "00-advisory.toml", digest


class AdvisoryArtifactTests(unittest.TestCase):
    def test_accepted_advisory_run_validates_without_execution_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            write_advisory(task_dir)

            errors = validate_advisory(task_dir)
            cli_errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", task_dir)

            self.assertEqual(errors, [])
            self.assertEqual(list(cli_errors), [])
            self.assertFalse((task_dir / "02-execution-graph.toml").exists())

    def test_advisory_state_must_live_under_repository_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "other" / "session-history-design"
            write_advisory(task_dir)

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-STATE-ROOT", {error.code for error in errors})

    def test_accepted_snapshot_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            _, digest = write_advisory(task_dir)
            snapshot_path = next((task_dir / "architectures").glob("*.toml"))
            snapshot_path.write_bytes(snapshot_path.read_bytes() + b"# changed\\n")

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-SNAPSHOT-DIGEST", {error.code for error in errors})
            self.assertEqual(len(digest), 64)

    def test_accepted_decision_cannot_be_rewritten_in_advisory_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            state["decisions"][0]["answer"] = "Different decision from prior acceptance."
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-DECISION-REWRITE", {error.code for error in errors})

    def test_resume_cannot_drop_previously_accepted_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous = root / "previous" / ".kapisch" / "runs" / "session-history-design"
            current = root / "current" / ".kapisch" / "runs" / "session-history-design"
            write_advisory(previous)
            current_state_path, _ = write_advisory(current)
            current_state = tomllib.loads(current_state_path.read_text(encoding="utf-8"))
            current_state["status"] = "proposal-ready"
            current_state["accepted_architectures"] = []
            current_state_path.write_bytes(render_toml(current_state))

            errors = validate_advisory(current, previous)
            cli_errors = validate(Path(__file__).resolve().parents[2] / "skills/kapisch", current, previous)

            self.assertIn("ADV-RESUME-ARCHITECTURE", {error.code for error in errors})
            self.assertIn("ADV-RESUME-ARCHITECTURE", {error.code for error in cli_errors})

    def test_implementation_planning_requires_human_accepted_snapshot_and_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            accepted_architectures = state["accepted_architectures"]
            state["status"] = "implementation-planning"
            state["accepted_architectures"] = []
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-STATE-ACCEPTANCE", {error.code for error in errors})

            state["accepted_architectures"] = accepted_architectures
            state["proposal_status"] = "proposed"
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-STATE-ACCEPTANCE", {error.code for error in errors})

    def test_decision_packet_allows_fewer_than_three_options_but_not_more(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "decision-required"
            state["unresolved_decisions"] = [
                {
                    "id": "Q01",
                    "kind": "architecture",
                    "problem": "Where should history live?",
                    "why": "Storage choice affects recovery.",
                    "decision_required": "Choose a storage model.",
                    "options": [
                        {"id": f"O{i}", "description": f"Choice {i}", "consequences": f"Trade-off {i}"}
                        for i in range(1, 5)
                    ],
                    "recommendation": "O1",
                }
            ]
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-DECISION-OPTIONS", {error.code for error in errors})

    def test_non_string_decision_kinds_return_schema_errors(self) -> None:
        for field in ("decisions", "unresolved_decisions"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
                state_path, _ = write_advisory(task_dir)
                state = tomllib.loads(state_path.read_text(encoding="utf-8"))
                if field == "decisions":
                    state[field][0]["kind"] = ["architecture"]
                else:
                    state["status"] = "decision-required"
                    state[field] = [
                        {
                            "id": "Q01",
                            "kind": ["architecture"],
                            "problem": "Where should history live?",
                            "why": "Storage choice affects recovery.",
                            "decision_required": "Choose a storage model.",
                            "options": [
                                {"id": "O1", "description": "Choice 1", "consequences": "Trade-off 1"},
                                {"id": "O2", "description": "Choice 2", "consequences": "Trade-off 2"},
                            ],
                            "recommendation": "O1",
                        }
                    ]
                state_path.write_bytes(render_toml(state))

                errors = validate_advisory(task_dir)

                self.assertIn("ADV-DECISION-KIND", {error.code for error in errors})

    def test_duplicate_snapshot_id_with_different_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            original = state["accepted_architectures"][0]
            original_path = task_dir / original["path"]
            snapshot = tomllib.loads(original_path.read_text(encoding="utf-8"))
            content = snapshot["architecture_content"] + "\nA second accepted version.\n"
            snapshot["architecture_content"] = content
            snapshot["content_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
            snapshot_bytes = render_toml(snapshot)
            digest = hashlib.sha256(snapshot_bytes).hexdigest()
            alternate_path = task_dir / "architectures" / f"{original['id']}-{digest}.toml"
            alternate_path.write_bytes(snapshot_bytes)
            alternate = {"id": original["id"], "path": alternate_path.relative_to(task_dir).as_posix(), "digest": digest}
            state["accepted_architectures"].append(alternate)
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-SNAPSHOT-REFERENCE", {error.code for error in errors})

    def test_malformed_enum_values_return_diagnostics(self) -> None:
        for field, value in (("status", ["accepted"]), ("proposal_status", {"bad": "value"})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
                state_path, _ = write_advisory(task_dir)
                state = tomllib.loads(state_path.read_text(encoding="utf-8"))
                state[field] = value
                state_path.write_bytes(render_toml(state))
                expected_code = "ADV-STATE-STATUS" if field == "status" else "ADV-PROPOSAL-STATUS"
                self.assertIn(expected_code, {error.code for error in validate_advisory(task_dir)})

    def test_malformed_recommendation_returns_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "decision-required"
            state["unresolved_decisions"] = [{"id": "Q01", "kind": "architecture", "problem": "p", "why": "w", "decision_required": "d", "options": [], "recommendation": ["O1"]}]
            state_path.write_bytes(render_toml(state))
            self.assertIn("ADV-DECISION-RECOMMENDATION", {error.code for error in validate_advisory(task_dir)})

    def test_list_snapshot_digest_returns_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            state["accepted_architectures"][0]["digest"] = ["bad"]
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-SNAPSHOT-DIGEST", {error.code for error in errors})

    def test_off_path_accepted_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            snapshot_ref = state["accepted_architectures"][0]
            off_path = task_dir / "elsewhere" / Path(snapshot_ref["path"]).name
            off_path.parent.mkdir()
            off_path.write_bytes((task_dir / snapshot_ref["path"]).read_bytes())
            snapshot_ref["path"] = off_path.relative_to(task_dir).as_posix()
            state_path.write_bytes(render_toml(state))

            errors = validate_advisory(task_dir)

            self.assertIn("ADV-SNAPSHOT-REFERENCE", {error.code for error in errors})

    def test_empty_decisions_remain_valid_for_human_accepted_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            reference = state["accepted_architectures"][0]
            snapshot_path = task_dir / reference["path"]
            snapshot = tomllib.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["decisions"] = []
            snapshot_bytes = render_toml(snapshot)
            digest = hashlib.sha256(snapshot_bytes).hexdigest()
            accepted_path = snapshot_path.with_name(f"A01-{digest}.toml")
            accepted_path.write_bytes(snapshot_bytes)
            snapshot_path.unlink()
            reference["path"] = accepted_path.relative_to(task_dir).as_posix()
            reference["digest"] = digest
            state["decisions"] = []
            state_path.write_bytes(render_toml(state))

            self.assertEqual(validate_advisory(task_dir), [])

    def test_advisory_schema_does_not_grant_implementation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / ".kapisch" / "runs" / "session-history-design"
            state_path, _ = write_advisory(task_dir)
            state = tomllib.loads(state_path.read_text(encoding="utf-8"))
            state["implementation_authorized"] = True
            state_path.write_bytes(render_toml(state))
            errors = validate_advisory(task_dir)
            self.assertIn("ADV-SCHEMA-UNKNOWN-FIELD", {error.code for error in errors})


if __name__ == "__main__":
    unittest.main()
