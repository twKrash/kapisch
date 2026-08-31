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
    ASSIGNMENT_VALUES,
    NODE_ROUTING_VALUES,
    POLICY_VALUES,
    WORKFLOW_STATUS_TRANSITIONS,
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
        cases = (
            ("mechanic", "cheap", "behavioral"),
            ("implementer-lite", "cheap", "behavioral"),
            ("implementer", "standard", "behavioral"),
            ("architect", "high", "behavioral"),
            ("researcher", "cheap", "research"),
            ("reviewer", "high", "review"),
        )
        for executor_class, model_tier, kind in cases:
            with self.subTest(executor_class=executor_class), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-v3-no-delegation")
                manifest_path = root / "02-execution-graph.toml"
                self.replace_first_string(manifest_path, "dispatch", "auto")
                self.replace_first_node_string(manifest_path, "executor_class", executor_class)
                self.replace_first_node_string(manifest_path, "model_tier", model_tier)
                self.replace_first_node_string(manifest_path, "kind", kind)
                parsed = parse_manifest(manifest_path)
                self.assertEqual(parsed.errors, (), parsed.errors)

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

    def test_controller_view_state_bindings_are_version_bound(self) -> None:
        state_bindings = (
            'controller_view_path="04-controller-view.toml"\n'
            'controller_view_sha256="' + "0" * 64 + '"\n'
        )
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary, "valid-v3-durable")
            manifest_path = root / "02-execution-graph.toml"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").replace(
                    "version = 3",
                    'version = 4\ncontroller_view = "04-controller-view.toml"',
                    1,
                ),
                encoding="utf-8",
            )
            code, findings = self.run_cli(root)
            self.assertEqual(code, 2)
            self.assertEqual(
                [(finding["code"], finding["reference"]) for finding in findings],
                [
                    ("TWV-SCHEMA-MISSING-FIELD", "controller_view_path"),
                    ("TWV-SCHEMA-MISSING-FIELD", "controller_view_sha256"),
                ],
            )

            state_path = root / "03-state.toml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8") + state_bindings,
                encoding="utf-8",
            )
            code, findings = self.run_cli(root)
            self.assertEqual(code, 0, findings)

        for binding in state_bindings.splitlines():
            with self.subTest(binding=binding), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-v3-durable")
                state_path = root / "03-state.toml"
                state_path.write_text(
                    state_path.read_text(encoding="utf-8") + binding + "\n",
                    encoding="utf-8",
                )
                code, findings = self.run_cli(root)
                self.assertEqual(code, 2)
                self.assertEqual(
                    [(finding["code"], finding["reference"]) for finding in findings],
                    [
                        (
                            "TWV-SCHEMA-UNSUPPORTED-V4-FIELD",
                            binding.split("=", 1)[0],
                        )
                    ],
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

    def test_context_invalid_routing_exits_two(self) -> None:
        cases = (
            ("executor_class", "architect"),
            ("executor_class", "reviewer"),
            ("executor_class", "researcher"),
            ("model_tier", "cheap"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-sequential-v2")
                self.replace_first_node_string(root / "02-execution-graph.toml", field, value)
                code, findings = self.run_cli(root)
                self.assertEqual(code, 2)
                self.assertTrue(
                    any(finding["code"] == "TWV-SCHEMA-INVALID-ROUTING" for finding in findings),
                    findings,
                )

    def test_ready_review_and_final_require_reviewer_routing(self) -> None:
        for node_id, completed, ready in (
            ("R01", '["T01"]', '["R01"]'),
            ("F01", '["R01","T01"]', '["F01"]'),
        ):
            with self.subTest(node_id=node_id), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary, "valid-sequential-v2")
                manifest_path = root / "02-execution-graph.toml"
                content = manifest_path.read_text(encoding="utf-8")
                before, node = content.split(f'[[nodes]]\nid="{node_id}"', 1)
                node, after = node.split("[[nodes]]", 1) if "[[nodes]]" in node else (node, "")
                node = node.replace('status="complete"', 'status="ready"', 1)
                node = node.replace('executor_class="reviewer"', 'executor_class="implementer"')
                node = node.replace('model_tier="high"', 'model_tier="standard"')
                manifest_path.write_text(
                    before + f'[[nodes]]\nid="{node_id}"' + node + "[[nodes]]" + after,
                    encoding="utf-8",
                )
                state_path = root / "03-state.toml"
                state = state_path.read_text(encoding="utf-8")
                state = state.replace('workflow_status="complete"', 'workflow_status="running"')
                state = state.replace('completed_node_ids=["F01","R01","T01"]', f"completed_node_ids={completed}")
                state = state.replace('ready_node_ids=[]', f"ready_node_ids={ready}")
                state = state.replace('next_action="complete"', f'next_action="select:{node_id}"')
                state_path.write_text(state, encoding="utf-8")
                code, findings = self.run_cli(root)
                self.assertEqual(code, 2)
                self.assertTrue(
                    any(
                        finding["code"] == "TWV-SCHEMA-INVALID-ROUTING"
                        and finding["reference"] == f"nodes[{1 if node_id == 'R01' else 2}]"
                        for finding in findings
                    ),
                    findings,
                )

    def test_unknown_assignment_execution_class_exits_two(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary, "valid-sequential-v2")
            manifest_path = root / "02-execution-graph.toml"
            content = manifest_path.read_text(encoding="utf-8")
            manifest_path.write_text(
                content.replace(
                    'head="head"\n[[nodes]]',
                    'head="head"\n[nodes.assignment]\nid="A-T01-1"\n'
                    'schema_version=1\nexecution_class="banana"\n'
                    'reason_codes=[]\nsource_revision="base"\ncontext_refs=[]\n'
                    'escalations=[]\n[[nodes]]',
                    1,
                ),
                encoding="utf-8",
            )
            code, findings = self.run_cli(root)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                finding["reference"] == "nodes[0].assignment.execution_class"
                and finding["code"] == "TWV-SCHEMA-INVALID-VALUE"
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
        documented.update(
            {
                f"nodes[].assignment.{field}": values
                for field, values in ASSIGNMENT_VALUES.items()
            }
        )
        documented["workflow_status"] = WORKFLOW_STATUS_VALUES
        table = re.search(
            r"### Closed persisted vocabularies\n\n.*?\n\n(?P<table>(?:\|[^\n]*\n)+)",
            contract,
            re.DOTALL,
        )
        self.assertIsNotNone(table)
        rows = table.group("table").splitlines()[2:]
        actual = {
            cells[0].strip().strip("`"): tuple(
                value.strip().strip("`") for value in cells[1].split(",")
            )
            for row in rows
            if len(cells := row.strip("|").split("|")) == 2
        }
        self.assertEqual(actual, documented)
        self.assertIn(
            "A persisted `workflow_status` is `complete` if and only if "
            "`next_action` is `complete`.",
            normalized_contract,
        )
        documented_transitions = set(
            re.findall(r"`(running|complete) -> (running|complete)`", contract)
        )
        expected_transitions = {
            (source, target)
            for source, targets in WORKFLOW_STATUS_TRANSITIONS.items()
            for target in targets
        }
        self.assertEqual(documented_transitions, expected_transitions)
        self.assertIn(
            "`running -> running`, `running -> complete`, and `complete -> complete`",
            normalized_contract,
        )


if __name__ == "__main__":
    unittest.main()
