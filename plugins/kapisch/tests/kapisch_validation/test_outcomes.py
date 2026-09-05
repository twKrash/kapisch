from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from kapisch_validation.manifest import parse_manifest
from kapisch_validation.outcomes import _finding_binding_errors, _normalized_claim_errors, _redispatch_errors, _report_authorizes_finding, validate_outcomes
from kapisch_validation.references import parse_state

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


class OutcomeTests(unittest.TestCase):
    def make_v4_task(self, temporary: str) -> tuple[Path, object, object]:
        task_dir = Path(temporary) / "task"
        shutil.copytree(FIXTURES / "valid-v3-durable", task_dir)
        manifest_path = task_dir / "02-execution-graph.toml"
        manifest = manifest_path.read_text(encoding="utf-8").replace(
            "version = 3",
            'version = 4\ncontroller_view = "04-controller-view.toml"',
            1,
        )
        manifest = manifest.replace(
            "[nodes.revision]",
            'assignment={id="A-T01-1",schema_version=1,execution_class="bounded",reason_codes=[],source_revision="base",context_refs=[],attempts=[{id="AT-T01-1",source_revision="base",context_scope_ref="tasks/T01-context.md",status="complete",verification=[],outcome_path="stage-outcomes/AT-T01-1.toml"}],escalations=[]}\n[nodes.revision]',
            1,
        )
        manifest_path.write_text(manifest, encoding="utf-8")
        state_path = task_dir / "03-state.toml"
        state_path.write_text(
            state_path.read_text(encoding="utf-8")
            + 'controller_view_path="04-controller-view.toml"\n'
            + 'controller_view_sha256="' + "0" * 64 + '"\n',
            encoding="utf-8",
        )
        parsed = parse_manifest(manifest_path)
        state, errors = parse_state(state_path)
        self.assertEqual(parsed.errors, ())
        self.assertEqual(errors, [])
        return task_dir, parsed.manifest, state

    def full_validation_codes(self, task_dir: Path) -> set[str]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_kapisch.py"), "--task-dir", str(task_dir)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        return {line.split(maxsplit=1)[0] for line in result.stdout.splitlines() if line}

    def write_outcome(self, task_dir: Path, *, report_sha256: str | None = None) -> None:
        report_path = task_dir / "tasks/T01-report.md"
        digest = report_sha256 or hashlib.sha256(report_path.read_bytes()).hexdigest()
        outcome_dir = task_dir / "stage-outcomes"
        outcome_dir.mkdir()
        (outcome_dir / "AT-T01-1.toml").write_text(
            "\n".join(
                (
                    "version = 1",
                    'task_id = "valid"',
                    'node_id = "T01"',
                    'role = "implementer"',
                    'assignment_id = "A-T01-1"',
                    'attempt_id = "AT-T01-1"',
                    'lifecycle = "complete"',
                    'role_status = "done"',
                    'base_revision = "base"',
                    'head_revision = "head"',
                    'working_tree_state_sha256 = "unavailable"',
                    'report_path = "tasks/T01-report.md"',
                    f'report_sha256 = "{digest}"',
                    'invocation_path = "unavailable"',
                    'invocation_id = "unavailable"',
                    'invocation_sha256 = "unavailable"',
                    'reviewer_decision = "unavailable"',
                    'redispatch_reason = "none"',
                    'predecessor_attempt_id = "unavailable"',
                    "retry_budget_delta = 0",
                    'next_action_reason = "completed"',
                    "findings = []",
                    f'verification = [{{check = "tests", result = "pass", evidence_ref = "tasks/T01-report.md", output_sha256 = "{digest}"}}]',
                    "",
                )
            ),
            encoding="utf-8",
        )

    def test_valid_terminal_outcome_binds_to_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, manifest, state = self.make_v4_task(temporary)
            self.write_outcome(task_dir)
            self.assertEqual(validate_outcomes(manifest, state, task_dir), [])
    def test_outcome_version_requires_an_integer_one(self) -> None:
        for value in ("true", "1.0"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                task_dir, manifest, state = self.make_v4_task(temporary)
                self.write_outcome(task_dir)
                outcome = task_dir / "stage-outcomes/AT-T01-1.toml"
                outcome.write_text(outcome.read_text(encoding="utf-8").replace("version = 1", f"version = {value}", 1), encoding="utf-8")
                errors = validate_outcomes(manifest, state, task_dir)
                self.assertIn("TWV-OUTCOME-INVALID-VERSION", {error.code for error in errors})

    def test_full_validator_rejects_fabricated_compact_claims(self) -> None:
        mutations = {
            "finding": (
                "findings = []",
                'findings = [{id = "F01", severity = "P1", summary = "invented", evidence_ref = "../../outside.txt"}]',
                "TWV-OUTCOME-EVIDENCE-REF",
            ),
            "worktree": (
                'working_tree_state_sha256 = "unavailable"',
                'working_tree_state_sha256 = "' + "0" * 64 + '"',
                "TWV-OUTCOME-WORKTREE-EVIDENCE",
            ),
            "disposition": (
                'role_status = "done"',
                'role_status = "failed"',
                "TWV-OUTCOME-DISPOSITION",
            ),
        }
        for name, (before, after, code) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / "task"
                shutil.copytree(FIXTURES / "valid-v4-controller", task_dir)
                outcome = task_dir / "stage-outcomes" / "AT-T01-1.toml"
                outcome.write_text(outcome.read_text(encoding="utf-8").replace(before, after, 1), encoding="utf-8")
                self.assertIn(code, self.full_validation_codes(task_dir))

    def test_full_validator_rejects_omitted_canonical_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-v4-controller", task_dir)
            outcome = task_dir / "stage-outcomes" / "AT-T01-1.toml"
            lines = outcome.read_text(encoding="utf-8").splitlines()
            outcome.write_text(
                "\n".join("verification = []" if line.startswith("verification = ") else line for line in lines) + "\n",
                encoding="utf-8",
            )
            self.assertIn("TWV-OUTCOME-VERIFICATION-EVIDENCE", self.full_validation_codes(task_dir))
    def test_report_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, manifest, state = self.make_v4_task(temporary)
            self.write_outcome(task_dir, report_sha256="0" * 64)
            errors = validate_outcomes(manifest, state, task_dir)
        self.assertIn("TWV-OUTCOME-REPORT-DIGEST", {error.code for error in errors})

    def test_nonexistent_redispatch_predecessor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, manifest, state = self.make_v4_task(temporary)
            self.write_outcome(task_dir)
            outcome = task_dir / "stage-outcomes/AT-T01-1.toml"
            outcome.write_text(
                outcome.read_text().replace('redispatch_reason = "none"', 'redispatch_reason = "failed-attempt"').replace(
                    'predecessor_attempt_id = "unavailable"', 'predecessor_attempt_id = "AT-NOT-REAL"'
                ).replace("retry_budget_delta = 0", "retry_budget_delta = 1"),
                encoding="utf-8",
            )
            errors = validate_outcomes(manifest, state, task_dir)
        self.assertIn("TWV-OUTCOME-REDISPATCH-PREDECESSOR", {error.code for error in errors})
    def test_no_redispatch_requires_unavailable_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, manifest, state = self.make_v4_task(temporary)
            self.write_outcome(task_dir)
            outcome = task_dir / "stage-outcomes/AT-T01-1.toml"
            outcome.write_text(
                outcome.read_text(encoding="utf-8").replace(
                    'predecessor_attempt_id = "unavailable"', 'predecessor_attempt_id = "AT-FABRICATED"', 1
                ),
                encoding="utf-8",
            )
            errors = validate_outcomes(manifest, state, task_dir)
        self.assertIn("TWV-OUTCOME-REDISPATCH-PREDECESSOR", {error.code for error in errors})
    def test_retry_authorized_requires_redispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, manifest, state = self.make_v4_task(temporary)
            self.write_outcome(task_dir)
            outcome = task_dir / "stage-outcomes/AT-T01-1.toml"
            outcome.write_text(
                outcome.read_text(encoding="utf-8").replace(
                    'next_action_reason = "completed"', 'next_action_reason = "retry-authorized"', 1
                ),
                encoding="utf-8",
            )
            errors = validate_outcomes(manifest, state, task_dir)
        self.assertIn("TWV-OUTCOME-NEXT-ACTION", {error.code for error in errors})
    def test_complete_outcome_rejects_blocked_next_action(self) -> None:
        node = SimpleNamespace(raw={"executor_class": "implementer"})
        raw = {
            "lifecycle": "complete",
            "role_status": "done",
            "redispatch_reason": "none",
            "next_action_reason": "blocked",
        }
        self.assertTrue(_normalized_claim_errors(raw, Path("outcome.toml"), node))

    def test_nonexecuted_verification_binds_without_artifact_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-v4-controller", task_dir)
            graph = task_dir / "02-execution-graph.toml"
            graph.write_text(
                graph.read_text(encoding="utf-8").replace(
                    'evidence_ref = "tasks/T01-report.md", id = "V01", output_sha256 = "331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95", result = "pass"',
                    'evidence_ref = "unavailable", id = "V01", output_sha256 = "unavailable", result = "not-run"',
                    1,
                ),
                encoding="utf-8",
            )
            outcome = task_dir / "stage-outcomes/AT-T01-1.toml"
            outcome.write_text(
                outcome.read_text(encoding="utf-8").replace(
                    'verification = [{check = "tests", result = "pass", evidence_ref = "tasks/T01-report.md", output_sha256 = "331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95"}]',
                    'verification = [{check = "tests", result = "not-run", evidence_ref = "unavailable", output_sha256 = "unavailable"}]',
                    1,
                ),
                encoding="utf-8",
            )
            manifest = parse_manifest(graph).manifest
            state, errors = parse_state(task_dir / "03-state.toml")
            self.assertEqual(errors, [])
            self.assertEqual(validate_outcomes(manifest, state, task_dir), [])




    def test_terminal_outcome_requires_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir, _, _ = self.make_v4_task(temporary)
            manifest_path = task_dir / "02-execution-graph.toml"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "stage-outcomes/AT-T01-1.toml", "odd/location.toml"
                ),
                encoding="utf-8",
            )
            parsed = parse_manifest(manifest_path)
        self.assertTrue(parsed.errors)


    def test_reviewer_finding_requires_canonical_report_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            report = task_dir / "review.md"
            finding = {"id": "F01", "severity": "high", "summary": "missing proof"}
            report.write_text(
                "finding_id: F01\nfinding_severity: high\n"
                "finding_summary: missing proof\nfinding_scope: R01\n",
                encoding="utf-8",
            )
            outcome = {"report_path": "review.md"}
            self.assertTrue(_report_authorizes_finding(outcome, finding, task_dir, "R01"))
            report.write_text("finding_id: F01\n", encoding="utf-8")
            self.assertFalse(_report_authorizes_finding(outcome, finding, task_dir, "R01"))
    def test_reviewer_finding_cannot_match_prefixes_or_separate_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            report = task_dir / "review.md"
            finding = {"id": "F01", "severity": "P1", "summary": "missing proof"}
            outcome = {"report_path": "review.md"}
            report.write_text(
                "finding_id: F010\nfinding_severity: P1\n"
                "finding_summary: missing proof of authorization\nfinding_scope: R010\n",
                encoding="utf-8",
            )
            self.assertFalse(_report_authorizes_finding(outcome, finding, task_dir, "R01"))
            report.write_text(
                "finding_id: F01\nfinding_severity: P1\n"
                "finding_summary: another finding\nfinding_scope: R01\n\n"
                "finding_id: F02\nfinding_severity: P2\n"
                "finding_summary: missing proof\nfinding_scope: R02\n",
                encoding="utf-8",
            )
            self.assertFalse(_report_authorizes_finding(outcome, finding, task_dir, "R01"))

    def test_nonreviewer_concern_binds_to_its_canonical_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            report = task_dir / "implement.md"
            report.write_text(
                "finding_id: F01\nfinding_severity: P2\n"
                "finding_summary: incomplete proof\nfinding_scope: T01\n",
                encoding="utf-8",
            )
            node = SimpleNamespace(id="T01", raw={"executor_class": "implementer"})
            raw = {
                "lifecycle": "complete",
                "role_status": "done-with-concerns",
                "redispatch_reason": "none",
                "next_action_reason": "await-user",
                "report_path": "implement.md",
                "findings": [{"id": "F01", "severity": "P2", "summary": "incomplete proof", "evidence_ref": "implement.md"}],
            }
            self.assertEqual(_normalized_claim_errors(raw, report, node), [])
            self.assertEqual(_finding_binding_errors(raw, report, report, task_dir, node), [])
    def test_redispatch_reasons_require_predecessor_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            (task_dir / "review.md").write_text(
                "finding_id: F01\nfinding_severity: P1\nfinding_summary: missing proof\nfinding_scope: R01\n",
                encoding="utf-8",
            )

            def errors_for(reason: str, predecessor_status: str, predecessor_outcome: dict[str, object], *, same_node: bool = True):
                predecessor_node = SimpleNamespace(id="R01" if not same_node else "T01", sequence=1)
                node = SimpleNamespace(id="T01", sequence=2)
                predecessor = {"id": "AT-1", "status": predecessor_status, "outcome_path": "stage-outcomes/AT-1.toml"}
                current = {"id": "AT-2", "status": "complete"}
                raw = {"redispatch_reason": reason, "predecessor_attempt_id": "AT-1"}
                return _redispatch_errors(
                    raw,
                    task_dir / "stage-outcomes/AT-2.toml",
                    node,
                    current,
                    [(predecessor_node, {}, predecessor), (node, {}, current)],
                    {"stage-outcomes/AT-1.toml": predecessor_outcome},
                    task_dir,
                )

            supported = (
                (
                    "reviewer-finding",
                    "complete",
                    {
                        "role": "reviewer",
                        "role_status": "done-with-concerns",
                        "report_path": "review.md",
                        "findings": [{"id": "F01", "severity": "P1", "summary": "missing proof", "evidence_ref": "review.md"}],
                    },
                    False,
                ),
            )
            for reason, status, outcome, same_node in supported:
                with self.subTest(reason=reason):
                    self.assertEqual(errors_for(reason, status, outcome, same_node=same_node), [])
                    self.assertTrue(errors_for(reason, "complete", {"lifecycle": "complete", "role_status": "done"}, same_node=same_node))
            rejected = (
                ("failed-attempt", "failed", {"lifecycle": "failed", "role_status": "failed"}),
                ("interrupted-active-stage", "blocked", {"lifecycle": "blocked", "role_status": "blocked"}),
                ("stale-review-state", "complete", {"lifecycle": "complete", "role_status": "done"}),
                ("dispatch-no-work", "complete", {"lifecycle": "complete", "role_status": "done"}),
                ("approved-amendment", "complete", {"lifecycle": "complete", "role_status": "done"}),
            )
            for reason, status, outcome in rejected:
                with self.subTest(reason=reason):
                    self.assertTrue(errors_for(reason, status, outcome))
if __name__ == "__main__":
    unittest.main()
