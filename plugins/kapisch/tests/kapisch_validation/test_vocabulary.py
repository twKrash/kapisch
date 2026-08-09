from __future__ import annotations

import io
import json
import re
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from kapisch_validation.cli import main
from kapisch_validation.manifest import POLICIES, parse_manifest
from kapisch_validation.references import parse_state
from kapisch_validation.vocabulary import (
    NODE_ROUTING_VALUES,
    POLICY_VALUES,
    WORKFLOW_STATUS_VALUES,
)

FIXTURES = Path(__file__).parent / "fixtures"
NUMERIC_POLICY_FIELDS = {"max_parallel_agents", "max_fix_rounds"}
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("skills/kapisch")


class VocabularyTests(unittest.TestCase):
    def run_cli(self, task_dir: Path) -> tuple[int, list[dict[str, str]]]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "--contract-dir",
                    str(CONTRACT),
                    "--task-dir",
                    str(task_dir),
                    "--format",
                    "json",
                ]
            )
        return code, json.loads(output.getvalue())

    def copy_fixture(self, temporary: str, fixture: str) -> Path:
        target = Path(temporary) / "task"
        shutil.copytree(FIXTURES / fixture, target)
        return target

    def replace_first_string(
        self, path: Path, field: str, value: str
    ) -> None:
        pattern = rf'^{re.escape(field)}\s*=\s*"[^"]*"$'
        content = path.read_text(encoding="utf-8")
        updated, count = re.subn(
            pattern,
            f'{field}="{value}"',
            content,
            count=1,
            flags=re.MULTILINE,
        )
        self.assertEqual(count, 1, field)
        path.write_text(updated, encoding="utf-8")

    def replace_first_node_string(
        self, path: Path, field: str, value: str
    ) -> None:
        content = path.read_text(encoding="utf-8")
        node_start = content.index("[[nodes]]")
        prefix, nodes = content[:node_start], content[node_start:]
        pattern = rf'^{re.escape(field)}\s*=\s*"[^"]*"$'
        updated_nodes, count = re.subn(
            pattern,
            f'{field}="{value}"',
            nodes,
            count=1,
            flags=re.MULTILINE,
        )
        self.assertEqual(count, 1, field)
        path.write_text(prefix + updated_nodes, encoding="utf-8")

    def assert_value_finding(
        self,
        errors: tuple | list,
        reference: str,
        invalid: str,
        supported: tuple[str, ...],
        expected_code: str = "TWV-SCHEMA-INVALID-VALUE",
    ) -> None:
        matches = [error for error in errors if error.reference == reference]
        self.assertEqual(len(matches), 1, errors)
        finding = matches[0]
        self.assertEqual(finding.code, expected_code)
        self.assertIn(repr(invalid), finding.message)
        for value in supported:
            self.assertIn(repr(value), finding.message)

    def test_vocabulary_covers_every_string_policy_field(self) -> None:
        self.assertEqual(set(POLICY_VALUES), POLICIES - NUMERIC_POLICY_FIELDS)

    def test_every_supported_policy_value_parses(self) -> None:
        for field, supported in POLICY_VALUES.items():
            for value in supported:
                with self.subTest(field=field, value=value), TemporaryDirectory() as temporary:
                    fixture = (
                        "valid-v3-no-delegation"
                        if field == "ecosystem_routing"
                        else "valid-sequential-v2"
                    )
                    root = self.copy_fixture(temporary, fixture)
                    manifest_path = root / "02-execution-graph.toml"
                    self.replace_first_string(manifest_path, field, value)
                    parsed = parse_manifest(manifest_path)
                    self.assertEqual(parsed.errors, (), (field, value, parsed.errors))

    def test_every_supported_node_routing_value_parses(self) -> None:
        for field, supported in NODE_ROUTING_VALUES.items():
            for value in supported:
                with self.subTest(field=field, value=value), TemporaryDirectory() as temporary:
                    root = self.copy_fixture(temporary, "valid-sequential-v2")
                    manifest_path = root / "02-execution-graph.toml"
                    self.replace_first_node_string(manifest_path, field, value)
                    parsed = parse_manifest(manifest_path)
                    self.assertEqual(parsed.errors, (), (field, value, parsed.errors))

    def test_unknown_policy_values_are_structured_findings(self) -> None:
        invalid_values = {
            "execution": "parallel",
            "executor": "banana",
            "dispatch": "banana",
            "model_tier": "unbounded",
            "batching": "parallel",
            "parallelism": "on",
            "commit": "automatic",
            "push": "automatic",
            "fix_policy": "unlimited",
            "ecosystem_routing": "sometimes",
        }
        for field, invalid in invalid_values.items():
            with self.subTest(field=field), TemporaryDirectory() as temporary:
                fixture = (
                    "valid-v3-no-delegation"
                    if field == "ecosystem_routing"
                    else "valid-sequential-v2"
                )
                root = self.copy_fixture(temporary, fixture)
                manifest_path = root / "02-execution-graph.toml"
                self.replace_first_string(manifest_path, field, invalid)
                parsed = parse_manifest(manifest_path)
                self.assertIsNone(parsed.manifest)
                self.assert_value_finding(
                    parsed.errors,
                    f"policies.{field}",
                    invalid,
                    POLICY_VALUES[field],
                    (
                        "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE"
                        if field == "parallelism"
                        else "TWV-SCHEMA-INVALID-VALUE"
                    ),
                )

    def test_unknown_node_routing_values_are_structured_findings(self) -> None:
        for field, supported in NODE_ROUTING_VALUES.items():
            with self.subTest(field=field), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-sequential-v2")
                manifest_path = root / "02-execution-graph.toml"
                self.replace_first_node_string(manifest_path, field, "banana")
                parsed = parse_manifest(manifest_path)
                self.assertIsNone(parsed.manifest)
                self.assert_value_finding(
                    parsed.errors,
                    f"nodes[0].{field}",
                    "banana",
                    supported,
                )

    def test_workflow_status_has_one_closed_vocabulary(self) -> None:
        for value in WORKFLOW_STATUS_VALUES:
            with self.subTest(value=value), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-sequential-v2")
                state_path = root / "03-state.toml"
                self.replace_first_string(state_path, "workflow_status", value)
                state, errors = parse_state(state_path)
                self.assertEqual(errors, [])
                self.assertEqual(state.workflow_status, value)

        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary, "valid-sequential-v2")
            state_path = root / "03-state.toml"
            self.replace_first_string(state_path, "workflow_status", "banana")
            state, errors = parse_state(state_path)
            self.assertIsNone(state)
            self.assert_value_finding(
                errors,
                "workflow_status",
                "banana",
                WORKFLOW_STATUS_VALUES,
            )

    def test_required_unknown_values_exit_two(self) -> None:
        cases = (
            ("02-execution-graph.toml", "execution", "parallel"),
            ("02-execution-graph.toml", "dispatch", "banana"),
            ("02-execution-graph.toml", "push", "automatic"),
            ("02-execution-graph.toml", "fix_policy", "unlimited"),
            ("03-state.toml", "workflow_status", "banana"),
        )
        for relative_path, field, invalid in cases:
            with self.subTest(field=field), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-sequential-v2")
                self.replace_first_string(root / relative_path, field, invalid)
                code, findings = self.run_cli(root)
                self.assertEqual(code, 2)
                reference = (
                    field if relative_path == "03-state.toml" else f"policies.{field}"
                )
                matching = [
                    finding
                    for finding in findings
                    if finding["reference"] == reference
                ]
                self.assertEqual(len(matching), 1, findings)
                self.assertIn(repr(invalid), matching[0]["message"])

    def test_inconsistent_terminal_pairs_exit_two(self) -> None:
        cases = (
            ("running", "complete"),
            ("complete", "block:no-ready-node"),
        )
        for workflow_status, next_action in cases:
            with self.subTest(
                workflow_status=workflow_status, next_action=next_action
            ), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-sequential-v2")
                state_path = root / "03-state.toml"
                self.replace_first_string(
                    state_path, "workflow_status", workflow_status
                )
                self.replace_first_string(state_path, "next_action", next_action)
                code, findings = self.run_cli(root)
                self.assertEqual(code, 2)
                self.assertTrue(
                    any(
                        finding["code"] == "TWV-LIFECYCLE-WORKFLOW-STATUS"
                        for finding in findings
                    ),
                    findings,
                )

    def test_normative_vocabulary_table_matches_code(self) -> None:
        contract = (
            PLUGIN_ROOT / "skills/kapisch/references/execution-graph.md"
        ).read_text(encoding="utf-8")
        normalized_contract = " ".join(contract.split())
        documented: dict[str, tuple[str, ...]] = {
            f"policies.{field}": values
            for field, values in POLICY_VALUES.items()
        }
        documented.update(
            {
                f"nodes[].{field}": values
                for field, values in NODE_ROUTING_VALUES.items()
            }
        )
        documented["workflow_status"] = WORKFLOW_STATUS_VALUES
        for field, values in documented.items():
            row = f"| `{field}` | {', '.join(f'`{value}`' for value in values)} |"
            with self.subTest(field=field):
                self.assertEqual(contract.count(row), 1)
        self.assertIn(
            "A persisted `workflow_status` is `complete` if and only if "
            "`next_action` is `complete`.",
            normalized_contract,
        )
        self.assertIn(
            "`running -> running`, `running -> complete`, and `complete -> complete`",
            normalized_contract,
        )


if __name__ == "__main__":
    unittest.main()
