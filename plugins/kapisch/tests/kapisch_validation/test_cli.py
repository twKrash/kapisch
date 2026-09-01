from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from kapisch_validation.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
CONTRACT = Path("skills/kapisch")
PLUGIN_ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def _run(self, fixture: str, *extra: str) -> tuple[int, list[str]]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "--contract-dir",
                    str(CONTRACT),
                    "--task-dir",
                    str(FIXTURES / fixture),
                    *extra,
                ]
            )
        return code, output.getvalue().splitlines()

    def _run_subprocess(self, task_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PLUGIN_ROOT / "scripts/validate_kapisch.py"),
                "--contract-dir",
                str(PLUGIN_ROOT / CONTRACT),
                "--task-dir",
                str(task_dir),
                "--format",
                "json",
            ],
            capture_output=True,
            cwd=PLUGIN_ROOT,
            text=True,
            check=False,
            timeout=5,
        )

    def _run_paths(
        self, task_dir: Path, previous_task_dir: Path | None = None
    ) -> tuple[int, list[dict[str, str]]]:
        output = io.StringIO()
        args = [
            "--contract-dir",
            str(CONTRACT),
            "--task-dir",
            str(task_dir),
            "--format",
            "json",
        ]
        if previous_task_dir is not None:
            args.extend(["--previous-task-dir", str(previous_task_dir)])
        with redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def assert_subprocess_failure(
        self, task_dir: Path, expected_code: str
    ) -> None:
        completed = self._run_subprocess(task_dir)
        findings = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 2)
        self.assertTrue(
            any(finding["code"] == expected_code for finding in findings), findings
        )
        self.assertNotIn("Traceback", completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)

    def make_running_task(self, task_dir: Path) -> None:
        """Turn the completed fixture into a standalone-valid active T01 snapshot."""
        manifest = task_dir / "02-execution-graph.toml"
        content = manifest.read_text(encoding="utf-8")
        content = content.replace('status="complete"', 'status="running"', 1)
        content = content.replace('status="complete"', 'status="pending"', 2)
        manifest.write_text(content, encoding="utf-8")
        state = task_dir / "03-state.toml"
        state.write_text(
            state.read_text(encoding="utf-8")
            .replace('workflow_status="complete"', 'workflow_status="running"')
            .replace('completed_node_ids=["F01","R01","T01"]', 'completed_node_ids=[]')
            .replace('running_node_ids=[]', 'running_node_ids=["T01"]')
            .replace(
                'latest_approving_review_path="reviews/round-0/03-review.md"',
                'latest_approving_review_path="unavailable"',
            )
            .replace('latest_approving_invocation_id="I-REVIEW"', 'latest_approving_invocation_id="unavailable"')
            .replace('next_action="complete"', 'next_action="resolve:T01"'),
            encoding="utf-8",
        )

    def add_runtime_history(self, task_dir: Path) -> None:
        manifest = task_dir / "02-execution-graph.toml"
        content = manifest.read_text(encoding="utf-8")
        evidence = (
            'verification_evidence=['
            '{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",'
            'output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"},'
            '{id="V02",check="context",result="pass",evidence_ref="tasks/T01-context.md",'
            'output_sha256="1ee232df47462fa4a561adbe24ea4a0b67b6d79f9b5f6e15cb8a7ba80f2de117",revision="head"}'
            ']'
        )
        content = content.replace(
            'verification_evidence=[{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"}]',
            evidence,
            1,
        )
        runtime = """[nodes.assignment]
id="A-T01-1"
schema_version=1
execution_class="bounded"
reason_codes=[]
source_revision="base"
context_refs=[]
attempts=[{id="AT-T01-1",source_revision="base",context_scope_ref="scope-1",status="pending",verification=[]},{id="AT-T01-2",source_revision="base",context_scope_ref="scope-2",status="running",verification=[]}]
escalations=[{id="E-T01-1",trigger="scope",prior_assignment_id="A-T01-0",new_assignment_id="A-T01-1",prior_attempt_id="AT-T01-0",new_attempt_id="AT-T01-1",source_revision="base",attempt_revision="head",context_refs=[]},{id="E-T01-2",trigger="scope",prior_assignment_id="A-T01-1",new_assignment_id="A-T01-2",prior_attempt_id="AT-T01-1",new_attempt_id="AT-T01-2",source_revision="base",attempt_revision="head",context_refs=[]}]
[nodes.batch]
id="B-T01-1"
member_node_ids=["T01"]
member_assignment_ids=["A-T01-1"]
member_outcomes=["running"]
outcome="running"
"""
        marker = '[nodes.revision]\nbase="base"\nhead="head"\n[[nodes]]\nid="R01"'
        content = content.replace(
            marker,
            '[nodes.revision]\nbase="base"\nhead="head"\n' + runtime + '[[nodes]]\nid="R01"',
            1,
        )
        manifest.write_text(content, encoding="utf-8")

    def test_missing_required_arguments_is_usage_error(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)

    def test_required_cli_fixture_matrix_has_stable_primary_codes(self) -> None:
        cases = {
            "valid-sequential-v2": (0, None),
            "valid-v1-defaults": (0, None),
            "valid-v4-controller": (0, None),
            "missing-review-scope": (2, "TWV-REVIEW-MISSING-SCOPE"),
            "invalid-v4-missing-view": (2, "TWV-VIEW-MISSING"),
            "invalid-v4-stale-view-digest": (2, "TWV-VIEW-STATE-BINDING"),
            "invalid-v4-unknown-outcome-field": (2, "TWV-OUTCOME-UNKNOWN-FIELD"),
            "invalid-v4-report-digest": (2, "TWV-OUTCOME-REPORT-DIGEST"),
            "invalid-v4-reviewer-invocation": (2, "TWV-OUTCOME-INVOCATION"),
            "stale-review-evidence": (2, "TWV-REVIEW-STALE-EVIDENCE"),
            "malformed-invocation-envelope": (2, "TWV-SCHEMA-MISSING-FIELD"),
            "dependency-cycle": (2, "TWV-REF-DEPENDENCY-CYCLE"),
            "unknown-normative-field": (2, "TWV-SCHEMA-UNKNOWN-FIELD"),
            "unsupported-operational-wave": (
                2,
                "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
            ),
            "unsupported-legacy-yaml": (2, "TWV-PARSE-UNSUPPORTED-LEGACY-YAML"),
        }
        for fixture, (expected_code, primary) in cases.items():
            with self.subTest(fixture=fixture):
                code, lines = self._run(fixture)
                self.assertEqual(code, expected_code)
                if primary is None:
                    self.assertEqual(lines, [])
                else:
                    self.assertTrue(any(line.startswith(primary) for line in lines))

    def test_illegal_transition_uses_a_valid_previous_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-sequential-v2", current)
            shutil.copytree(FIXTURES / "valid-sequential-v2", previous)
            manifest = current / "02-execution-graph.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                .replace('status="complete"', 'status="ready"', 1)
                .replace('status="complete"', 'status="pending"'),
                encoding="utf-8",
            )
            state = current / "03-state.toml"
            state.write_text(
                state.read_text(encoding="utf-8")
                .replace('workflow_status="complete"', 'workflow_status="running"')
                .replace('completed_node_ids=["F01","R01","T01"]', 'completed_node_ids=[]')
                .replace('ready_node_ids=[]', 'ready_node_ids=["T01"]')
                .replace('next_action="complete"', 'next_action="select:T01"'),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-ILLEGAL-TRANSITION"
                for finding in findings
            ),
            findings,
        )
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-ILLEGAL-WORKFLOW-TRANSITION"
                for finding in findings
            ),
            findings,
        )

    def test_previous_snapshot_rejects_immutable_node_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-sequential-v2", current)
            shutil.copytree(FIXTURES / "valid-sequential-v2", previous)
            manifest_path = current / "02-execution-graph.toml"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "sequence=1", "sequence=10", 1
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and finding["reference"] == "nodes[T01].sequence"
                and finding["path"] == str(manifest_path)
                for finding in findings
            ),
            findings,
        )

    def test_unchanged_previous_snapshot_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-sequential-v2", current)
            shutil.copytree(FIXTURES / "valid-sequential-v2", previous)
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])
    def test_unchanged_legacy_terminal_snapshot_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-v3-durable", current)
            shutil.copytree(FIXTURES / "valid-v3-durable", previous)
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])

    def test_unchanged_runtime_history_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            for task_dir in (current, previous):
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                self.make_running_task(task_dir)
                self.add_runtime_history(task_dir)
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])

    def test_sparse_or_invalid_runtime_history_fails_standalone_validation(self) -> None:
        cases = (
            (
                "assignment",
                'source_revision="base"\ncontext_refs=[]\nattempts=',
                'context_refs=[]\nattempts=',
                "TWV-SCHEMA-MISSING-FIELD",
            ),
            (
                "attempt",
                'id="AT-T01-1",source_revision="base",context_scope_ref=',
                'id="AT-T01-1",context_scope_ref=',
                "TWV-SCHEMA-MISSING-FIELD",
            ),
            (
                "escalation",
                'id="E-T01-1",trigger="scope",prior_assignment_id=',
                'id="E-T01-1",prior_assignment_id=',
                "TWV-SCHEMA-MISSING-FIELD",
            ),
            (
                "batch-outcome",
                'member_outcomes=["running"]\noutcome="running"',
                'member_outcomes=["running"]\noutcome="implemented"',
                "TWV-SCHEMA-INVALID-VALUE",
            ),
        )
        for name, old, new, expected_code in cases:
            with self.subTest(record=name), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / "task"
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                self.make_running_task(task_dir)
                self.add_runtime_history(task_dir)
                manifest = task_dir / "02-execution-graph.toml"
                manifest.write_text(
                    manifest.read_text(encoding="utf-8").replace(old, new, 1),
                    encoding="utf-8",
                )
                code, findings = self._run_paths(task_dir)
            self.assertEqual(code, 2)
            self.assertTrue(
                any(finding["code"] == expected_code for finding in findings), findings
            )

    def test_previous_snapshot_rejects_runtime_late_binding_and_reordering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            for task_dir in (current, previous):
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                self.make_running_task(task_dir)
                self.add_runtime_history(task_dir)
            manifest = current / "02-execution-graph.toml"
            content = manifest.read_text(encoding="utf-8")
            content = content.replace('context_refs=[]\nattempts=', 'context_refs=[]\ncontext_fingerprint="new"\nattempts=', 1)
            content = content.replace(
                'id="AT-T01-1",source_revision="base",context_scope_ref="scope-1",status="pending",verification=[]},{id="AT-T01-2",source_revision="base",context_scope_ref="scope-2",status="running",verification=[]}',
                'id="AT-T01-2",source_revision="base",context_scope_ref="scope-2",status="running",verification=[]},{id="AT-T01-1",source_revision="base",context_scope_ref="scope-1",status="pending",verification=[]}',
                1,
            )
            content = content.replace(
                'id="E-T01-1",trigger="scope",prior_assignment_id="A-T01-0",new_assignment_id="A-T01-1",prior_attempt_id="AT-T01-0",new_attempt_id="AT-T01-1",source_revision="base",attempt_revision="head",context_refs=[]},{id="E-T01-2",trigger="scope",prior_assignment_id="A-T01-1",new_assignment_id="A-T01-2",prior_attempt_id="AT-T01-1",new_attempt_id="AT-T01-2",source_revision="base",attempt_revision="head",context_refs=[]}',
                'id="E-T01-2",trigger="scope",prior_assignment_id="A-T01-1",new_assignment_id="A-T01-2",prior_attempt_id="AT-T01-1",new_attempt_id="AT-T01-2",source_revision="base",attempt_revision="head",context_refs=[]},{id="E-T01-1",trigger="scope",prior_assignment_id="A-T01-0",new_assignment_id="A-T01-1",prior_attempt_id="AT-T01-0",new_attempt_id="AT-T01-1",source_revision="base",attempt_revision="head",context_refs=[]}',
                1,
            )
            content = content.replace(
                '{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"},{id="V02",check="context",result="pass",evidence_ref="tasks/T01-context.md",output_sha256="1ee232df47462fa4a561adbe24ea4a0b67b6d79f9b5f6e15cb8a7ba80f2de117",revision="head"}',
                '{id="V02",check="context",result="pass",evidence_ref="tasks/T01-context.md",output_sha256="1ee232df47462fa4a561adbe24ea4a0b67b6d79f9b5f6e15cb8a7ba80f2de117",revision="head"},{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"}',
                1,
            )
            manifest.write_text(content, encoding="utf-8")
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and finding["reference"] == "nodes[T01].assignment"
                for finding in findings
            ),
            findings,
        )
        self.assertTrue(
            any(
                finding["reference"] == "nodes[T01].assignment.attempts"
                for finding in findings
            ),
            findings,
        )
        self.assertTrue(
            any(
                finding["reference"] == "nodes[T01].assignment.escalations"
                for finding in findings
            ),
            findings,
        )
        self.assertTrue(
            any(
                finding["reference"] == "nodes[T01].verification_evidence"
                for finding in findings
            ),
            findings,
        )

    def test_previous_snapshot_rejects_terminal_report_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-sequential-v2", current)
            shutil.copytree(FIXTURES / "valid-sequential-v2", previous)
            report = current / "tasks" / "T01-report.md"
            report.write_text("rewritten report\n", encoding="utf-8")
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and finding["reference"] == "nodes[T01].report"
                for finding in findings
            ),
            findings,
        )

    def test_completed_node_requires_complete_verification_evidence_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
            manifest = task_dir / "02-execution-graph.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    '{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"}',
                    '{id="V01"}',
                    1,
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(task_dir)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(finding["code"] == "TWV-SCHEMA-MISSING-FIELD" for finding in findings),
            findings,
        )

    def test_previous_snapshot_rejects_nonterminal_evidence_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            for task_dir in (current, previous):
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                self.make_running_task(task_dir)
            report = current / "tasks/T01-report.md"
            report.write_text("rewritten nonterminal evidence\n", encoding="utf-8")
            digest = hashlib.sha256(report.read_bytes()).hexdigest()
            manifest = current / "02-execution-graph.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95"',
                    f'output_sha256="{digest}"',
                    1,
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and finding["reference"] == "nodes[T01].verification_evidence"
                for finding in findings
            ),
            findings,
        )

    def test_previous_snapshot_allows_appended_nonterminal_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            for task_dir in (current, previous):
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                self.make_running_task(task_dir)
            manifest = current / "02-execution-graph.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'verification_evidence=[{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"}]',
                    'verification_evidence=[{id="V01",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="331d26d6d8f862e46ba900811be8a7a1e4dbaa229b14c99becfd5e5151490d95",revision="head"},{id="V02",check="context",result="pass",evidence_ref="tasks/T01-context.md",output_sha256="1ee232df47462fa4a561adbe24ea4a0b67b6d79f9b5f6e15cb8a7ba80f2de117",revision="head"}]',
                    1,
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])

    def test_legacy_route_files_do_not_affect_v2_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            for task_dir, content in ((current, "not valid TOML"), (previous, "changed = [")):
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                route = task_dir / "delegations/00-route.toml"
                route.parent.mkdir()
                route.write_text(content, encoding="utf-8")
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 0)
        self.assertEqual(findings, [])

    def test_previous_snapshot_rejects_delegation_route_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-v3-durable", current)
            shutil.copytree(FIXTURES / "valid-v3-durable", previous)
            route = current / "delegations" / "00-route.toml"
            route.write_text(
                route.read_text(encoding="utf-8").replace(
                    'route_id = "valid-route"', 'route_id = "rewritten-route"'
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and finding["reference"] == "delegations.route_id"
                for finding in findings
            ),
            findings,
        )

    def test_invalid_previous_snapshot_is_not_used_for_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-sequential-v2", current)
            shutil.copytree(FIXTURES / "valid-sequential-v2", previous)
            state_path = previous / "03-state.toml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace(
                    'workflow_status="complete"', 'workflow_status="running"'
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        status_findings = [
            finding
            for finding in findings
            if finding["code"] == "TWV-LIFECYCLE-WORKFLOW-STATUS"
        ]
        self.assertEqual(len(status_findings), 1, findings)
        self.assertEqual(status_findings[0]["path"], str(previous / "03-state.toml"))

    def test_previous_snapshot_must_match_its_manifest_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-sequential-v2", current)
            shutil.copytree(FIXTURES / "valid-sequential-v2", previous)
            state_path = previous / "03-state.toml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace(
                    'task_id="valid"', 'task_id="other"'
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-REF-STATE-MANIFEST-MISMATCH"
                and finding["reference"] == "task_id"
                and finding["path"] == str(previous / "03-state.toml")
                for finding in findings
            ),
            findings,
        )

    def test_previous_v3_route_must_be_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "current"
            previous = root / "previous"
            shutil.copytree(FIXTURES / "valid-v3-durable", current)
            shutil.copytree(FIXTURES / "valid-v3-durable", previous)
            route_path = previous / "delegations" / "00-route.toml"
            route_path.write_text(
                route_path.read_text(encoding="utf-8").replace(
                    'task_id = "valid"', 'task_id = "wrong"'
                ),
                encoding="utf-8",
            )
            code, findings = self._run_paths(current, previous)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["code"] == "TWV-DELEG-TASK-MISMATCH"
                and finding["path"] == str(route_path)
                for finding in findings
            ),
            findings,
        )

    def test_valid_fixture_is_read_only_and_has_deterministic_json(self) -> None:
        root = FIXTURES / "valid-sequential-v2"
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }
        code, lines = self._run("valid-sequential-v2", "--format", "json")
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["[]"])
        self.assertEqual(before, after)

    def test_corrupt_artifacts_exit_two_without_traceback(self) -> None:
        cases = (
            ("02-execution-graph.toml", "TWV-PARSE-INVALID-UTF8"),
            ("03-state.toml", "TWV-PARSE-INVALID-UTF8"),
            (
                "reviews/round-0/00-review-invocation.toml",
                "TWV-PARSE-INVALID-UTF8",
            ),
            ("reviews/round-0/03-review.md", "TWV-REVIEW-RESULT-ENCODING"),
        )
        for relative_path, expected_code in cases:
            with self.subTest(
                artifact=relative_path
            ), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / "task"
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                (task_dir / relative_path).write_bytes(b"\xff")
                self.assert_subprocess_failure(task_dir, expected_code)

    def test_parser_overflows_exit_two_without_traceback(self) -> None:
        cases = (
            b"version = " + b"9" * 5_000,
            b"version = " + b"[" * 1_500 + b"]" * 1_500,
        )
        for content in cases:
            with self.subTest(content_prefix=content[:10]), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / "task"
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                (task_dir / "02-execution-graph.toml").write_bytes(content)
                self.assert_subprocess_failure(task_dir, "TWV-PARSE-MALFORMED-TOML")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_fifo_artifact_exits_two_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            manifest = task_dir / "02-execution-graph.toml"
            shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
            manifest.unlink()
            os.mkfifo(manifest)
            self.assert_subprocess_failure(task_dir, "TWV-PARSE-UNREADABLE-ARTIFACT")

    def test_invalid_containment_paths_exit_two_without_traceback(self) -> None:
        cases = (
            ('report="tasks/T01-report.md"', 'report="\\u0000"'),
            (
                'reviewer_invocation="reviews/round-0/00-review-invocation.toml"',
                'reviewer_invocation="\\u0000"',
            ),
        )
        for old, new in cases:
            with self.subTest(replacement=new), tempfile.TemporaryDirectory() as temporary:
                task_dir = Path(temporary) / "task"
                manifest = task_dir / "02-execution-graph.toml"
                shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
                manifest.write_text(manifest.read_text().replace(old, new, 1))
                self.assert_subprocess_failure(task_dir, "TWV-REF-ARTIFACT")

    def test_invalid_delegation_context_path_exits_two_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            route = task_dir / "delegations/00-route.toml"
            shutil.copytree(FIXTURES / "valid-v3-durable", task_dir)
            route.write_text(
                route.read_text(encoding="utf-8").replace(
                    'context_path="delegations/D01/00-context.md"',
                    'context_path="\\u0000"',
                    1,
                ),
                encoding="utf-8",
            )
            self.assert_subprocess_failure(task_dir, "TWV-DELEG-PATH-ESCAPE")

    @unittest.skipIf(os.name == "nt", "symlink creation requires extra privileges")
    def test_symlink_loop_artifact_exits_two_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            manifest = task_dir / "02-execution-graph.toml"
            loop = task_dir / "loop"
            shutil.copytree(FIXTURES / "valid-sequential-v2", task_dir)
            loop.symlink_to(loop)
            manifest.write_text(
                manifest.read_text().replace('brief="tasks/T01-brief.md"', 'brief="loop"', 1)
            )
            self.assert_subprocess_failure(task_dir, "TWV-REF-ARTIFACT")


if __name__ == "__main__":
    unittest.main()
