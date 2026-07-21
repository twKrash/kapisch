from __future__ import annotations

import hashlib
import io
import re
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from kapisch_validation.cli import main, validate
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.models import Manifest, Node, State
from kapisch_validation.references import parse_state
from kapisch_validation.review_evidence import validate_review_evidence
from kapisch_validation.transitions import (
    determine_next_action,
    validate_lifecycle,
)

FIXTURES = Path(__file__).parent / "fixtures"
CONTRACT = Path("skills/kapisch")


class ValidatorHardeningTests(unittest.TestCase):
    def copy_fixture(self, temporary: str) -> Path:
        root = Path(temporary) / "task"
        shutil.copytree(FIXTURES / "valid-sequential-v2", root)
        return root

    def replace(self, path: Path, old: str, new: str) -> None:
        content = path.read_text()
        self.assertIn(old, content)
        path.write_text(content.replace(old, new, 1))

    def historical_identity_findings(
        self,
        root: Path,
        *,
        historical_id: str,
        current_id: str = "I-REVIEW",
        historical_external_id: str = "unavailable",
        current_external_id: str = "unavailable",
        historical_url: str = "unavailable",
        current_url: str = "unavailable",
        historical_ref: str = "unavailable",
        current_ref: str = "unavailable",
        historical_first: bool = True,
    ) -> list:
        invocation_path = root / "reviews/round-0/00-review-invocation.toml"
        result_path = root / "reviews/round-0/03-review.md"
        invocation = invocation_path.read_text()
        result = result_path.read_text()
        if current_id != "I-REVIEW":
            invocation = invocation.replace(
                'invocation_id="I-REVIEW"', f'invocation_id="{current_id}"'
            )
            result = result.replace(
                "invocation_id=I-REVIEW", f"invocation_id={current_id}"
            )
        if any(
            value != "unavailable"
            for value in (current_external_id, current_url, current_ref)
        ):
            invocation = invocation.replace(
                'dispatch_mode="runtime-named-spawn"',
                'dispatch_mode="external-named-task"',
            )
            invocation = invocation.replace(
                'external_task_id="unavailable"',
                f'external_task_id="{current_external_id}"',
            )
            invocation = invocation.replace(
                'external_task_url="unavailable"',
                f'external_task_url="{current_url}"',
            )
            invocation = invocation.replace(
                'external_task_ref="unavailable"',
                f'external_task_ref="{current_ref}"',
            )
            request = "Review the staged target."
            if current_ref != "unavailable":
                request += f"\\nexternal_task_ref={current_ref}\\n"
            invocation = invocation.replace(
                'external_task_request="unavailable"',
                f'external_task_request="{request}"',
            )
            invocation = invocation.replace(
                'identity_assurance="observable-named-dispatch"',
                (
                    'identity_assurance="user-attested-external-reference"'
                    if current_ref != "unavailable"
                    else 'identity_assurance="external-named-task"'
                ),
            )
            invocation = invocation.replace(
                "reviewer_selection_attested=false",
                "reviewer_selection_attested=true",
            )
            invocation = invocation.replace(
                'spawn_agent_type="reviewer"',
                'spawn_agent_type="unavailable"',
            )
            invocation = invocation.replace(
                'spawn_fork_turns="none"',
                'spawn_fork_turns="unavailable"',
            )
            invocation = invocation.replace(
                'spawn_result_task_name="review-task"',
                'spawn_result_task_name="unavailable"',
            )
            if current_ref != "unavailable":
                result += f"external_task_ref={current_ref}\n"
        result_path.write_text(result)
        invocation = re.sub(
            r'result_sha256="[0-9a-f]{64}"',
            f'result_sha256="{hashlib.sha256(result_path.read_bytes()).hexdigest()}"',
            invocation,
        )
        invocation_path.write_text(invocation)

        historical_path = root / "historical-invocation.toml"
        historical_path.write_text(
            f'invocation_id="{historical_id}"\n'
            f'external_task_id="{historical_external_id}"\n'
            f'external_task_url="{historical_url}"\n'
            f'external_task_ref="{historical_ref}"\n'
            'obsolete_field="legacy"\n'
        )
        implementation = Node("T01", 1, "behavioral", "complete", (), (), None, {})
        historical = Node(
            "R00",
            2,
            "review",
            "failed",
            ("T01",),
            ("", "", "historical-result.md", "historical-invocation.toml"),
            {"terminal_node_ids": ["T01"]},
            {"executor_class": "reviewer", "model_tier": "high", "batching": "off"},
        )
        current = Node(
            "R01",
            3,
            "review",
            "complete",
            ("T01",),
            (
                "",
                "",
                "reviews/round-0/03-review.md",
                "reviews/round-0/00-review-invocation.toml",
            ),
            {"terminal_node_ids": ["T01"]},
            {"executor_class": "reviewer", "model_tier": "high", "batching": "off"},
        )
        final = Node(
            "F01",
            4,
            "final",
            "pending",
            ("R01",),
            ("", "", "reviews/final/05-final.md", ""),
            None,
            {},
        )
        reviews = (historical, current) if historical_first else (current, historical)
        manifest = Manifest(
            2, "x", "base", {}, (implementation, *reviews, final), "graph.toml"
        )
        state = State(
            "x",
            "head",
            "running",
            ("T01", "R01"),
            (),
            (),
            (),
            ("R00",),
            "block:no-ready-node",
            {
                "latest_approving_review_path": "unavailable",
                "latest_approving_invocation_id": "unavailable",
            },
        )
        return validate_review_evidence(manifest, state, root)

    def test_manifest_rejects_unsafe_scalar_and_array_types(self) -> None:
        cases = {
            "sequence=1": "sequence=true",
            "depends_on=[]": "depends_on=[42]",
        }
        for old, new in cases.items():
            with self.subTest(replacement=new), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary)
                self.replace(root / "02-execution-graph.toml", old, new)
                parsed = parse_manifest(root / "02-execution-graph.toml")
                self.assertIsNone(parsed.manifest)
                self.assertTrue(
                    any(error.code.startswith("TWV-SCHEMA-") for error in parsed.errors)
                )

    def test_manifest_rejects_non_integer_sequence_and_duplicate_dependencies(
        self,
    ) -> None:
        for old, new in (
            ("sequence=1", 'sequence="one"'),
            ("depends_on=[]", 'depends_on=["T01", "T01"]'),
        ):
            with self.subTest(replacement=new), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary)
                self.replace(root / "02-execution-graph.toml", old, new)
                self.assertIsNone(
                    parse_manifest(root / "02-execution-graph.toml").manifest
                )

    def test_manifest_rejects_malformed_review_scope_member(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            self.replace(
                root / "02-execution-graph.toml",
                'terminal_node_ids=["T01"]',
                "terminal_node_ids=[42]",
            )
            self.assertIsNone(parse_manifest(root / "02-execution-graph.toml").manifest)

    def test_canonical_attempt_verification_array_is_valid(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            manifest = root / "02-execution-graph.toml"
            marker = 'head="head"\n[[nodes]]\nid="R01"'
            assignment = """head="head"
[nodes.assignment]
id="A-T01-1"
schema_version=1
execution_class="implementer"
reason_codes=["behavioral"]
source_revision="base"
context_refs=[]
context_fingerprint="context"
scope_fingerprint="scope"
escalations=[]
[[nodes.assignment.attempts]]
id="AT-T01-1"
source_revision="base"
context_scope_ref="A-T01-1"
status="pending"
verification=[]
[[nodes]]
id="R01"
"""
            self.replace(manifest, marker, assignment)
            parsed = parse_manifest(manifest)
            self.assertEqual(parsed.errors, ())
            self.assertIsNotNone(parsed.manifest)

    def test_state_rejects_mixed_node_ids_and_non_string_next_action(self) -> None:
        for old, new in (
            ('completed_node_ids=["F01","R01","T01"]', 'completed_node_ids=["T01",42]'),
            ('next_action="complete"', "next_action=42"),
        ):
            with self.subTest(replacement=new), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary)
                self.replace(root / "03-state.toml", old, new)
                state, errors = parse_state(root / "03-state.toml")
                self.assertIsNone(state)
                self.assertTrue(
                    any(error.code.startswith("TWV-SCHEMA-") for error in errors)
                )

    def test_invalid_invocation_types_fail_before_path_or_digest_use(self) -> None:
        cases = {
            "reviewer_selection_attested=false": 'reviewer_selection_attested="true"',
            'produced_result_path="reviews/round-0/03-review.md"': "produced_result_path=42",
            'result_sha256="': "result_sha256=42\n# ",
        }
        for old, new in cases.items():
            with self.subTest(replacement=new), TemporaryDirectory() as temporary:
                root = self.copy_fixture(temporary)
                self.replace(
                    root / "reviews/round-0/00-review-invocation.toml", old, new
                )
                findings = validate(CONTRACT, root)
                self.assertTrue(
                    any(error.code == "TWV-SCHEMA-WRONG-SHAPE" for error in findings)
                )

    def test_unknown_ready_dependency_is_a_finding_not_an_exception(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            self.replace(
                root / "02-execution-graph.toml",
                'status="complete"\ndepends_on=[]',
                'status="ready"\ndepends_on=["MISSING"]',
            )
            self.replace(
                root / "03-state.toml",
                'completed_node_ids=["F01","R01","T01"]',
                'completed_node_ids=["F01","R01"]\nready_node_ids=["T01"]',
            )
            self.replace(root / "03-state.toml", "ready_node_ids=[]", "")
            self.replace(
                root / "03-state.toml",
                'next_action="complete"',
                'next_action="block:no-ready-node"',
            )
            findings = validate(CONTRACT, root)
            self.assertTrue(
                any(error.code == "TWV-REF-UNKNOWN-DEPENDENCY" for error in findings)
            )

    def test_incomplete_dependencies_are_persisted_lifecycle_findings(self) -> None:
        pending = Node("T01", 1, "behavioral", "pending", (), (), None, {})
        for status in ("ready", "running", "implemented", "complete"):
            with self.subTest(status=status):
                node = Node("T02", 2, "behavioral", status, ("T01",), (), None, {})
                graph = Manifest(2, "x", "base", {}, (pending, node), "graph.toml")
                state = State(
                    "x",
                    "head",
                    "running",
                    (),
                    (),
                    (),
                    (),
                    (),
                    "block:no-ready-node",
                    {},
                )
                findings = validate_lifecycle(graph, state)
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPLETE-DEPENDENCY"
                        for error in findings
                    )
                )

    def test_review_and_final_gates_block_completion(self) -> None:
        implementation = Node("T01", 1, "behavioral", "complete", (), (), None, {})
        state = State(
            "x",
            "head",
            "complete",
            ("T01",),
            (),
            (),
            (),
            (),
            "block:missing-review-final",
            {},
        )
        graph = Manifest(2, "x", "base", {}, (implementation,), "graph.toml")
        self.assertEqual(
            determine_next_action(graph, state), "block:missing-review-final"
        )
        with TemporaryDirectory() as temporary:
            findings = validate(CONTRACT, FIXTURES / "valid-sequential-v2")
            self.assertEqual(findings, ())
            root = self.copy_fixture(temporary)
            manifest = root / "02-execution-graph.toml"
            content = manifest.read_text()
            manifest.write_text(content[: content.index('[[nodes]]\nid="R01"')])
            self.replace(
                root / "03-state.toml",
                'completed_node_ids=["F01","R01","T01"]',
                'completed_node_ids=["T01"]',
            )
            self.replace(
                root / "03-state.toml",
                'next_action="complete"',
                'next_action="block:missing-review-final"',
            )
            findings = validate(CONTRACT, root)
            codes = {error.code for error in findings}
            self.assertIn("TWV-REVIEW-MISSING-REVIEW", codes)
            self.assertIn("TWV-REVIEW-MISSING-FINAL", codes)

    def test_cancelled_review_and_final_gates_cannot_complete(self) -> None:
        implementation = Node("T01", 1, "behavioral", "complete", (), (), None, {})
        review = Node("R01", 2, "review", "cancelled", ("T01",), (), None, {})
        final = Node(
            "F01",
            3,
            "final",
            "cancelled",
            ("R01",),
            ("", "", "reviews/final/05-final.md", ""),
            None,
            {},
        )
        graph = Manifest(
            2,
            "x",
            "base",
            {},
            (implementation, review, final),
            "graph.toml",
        )
        state = State(
            "x",
            "head",
            "running",
            ("T01",),
            (),
            (),
            (),
            (),
            "block:missing-review-final",
            {},
        )
        self.assertEqual(
            determine_next_action(graph, state), "block:missing-review-final"
        )

    def test_final_must_depend_on_a_preceding_review(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            self.replace(
                root / "02-execution-graph.toml",
                'id="F01"\nsequence=3\ntitle="final"\nkind="final"\nrisk="high"\nstatus="complete"\ndepends_on=["R01"]',
                'id="F01"\nsequence=3\ntitle="final"\nkind="final"\nrisk="high"\nstatus="complete"\ndepends_on=[]',
            )
            findings = validate(CONTRACT, root)
            self.assertTrue(
                any(error.code == "TWV-REVIEW-ORDERING" for error in findings)
            )

    def test_completed_fix_round_allows_historical_failed_review(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            manifest = root / "02-execution-graph.toml"
            content = manifest.read_text()
            current_review = content.index('[[nodes]]\nid="R01"')
            historical_nodes = """[[nodes]]
id="R00"
sequence=2
title="historical review"
kind="review"
risk="high"
status="failed"
depends_on=["T01"]
brief="tasks/T01-brief.md"
context="tasks/T01-context.md"
report="reviews/round-0/03-historical-review.md"
reviewer_invocation="reviews/round-0/00-historical-invocation.toml"
reads=[]
writes=[]
shared_resources=[]
verification=[]
context_refs=[]
executor_class="reviewer"
model_tier="high"
batching="off"
[nodes.review_scope]
terminal_node_ids=["T01"]
integrated_wave_ids=[]
wave_terminal_dependencies=[]
[[nodes]]
id="T02"
sequence=3
title="fix"
kind="behavioral"
risk="low"
status="complete"
depends_on=["T01"]
brief="tasks/T01-brief.md"
context="tasks/T01-context.md"
report="tasks/T01-report.md"
reads=[]
writes=[]
shared_resources=[]
verification=[]
context_refs=[]
executor_class="implementer"
model_tier="standard"
batching="off"
verification_evidence=[{id="V04",check="tests",result="pass",evidence_ref="tasks/T01-report.md",output_sha256="evidence",revision="head"}]
[nodes.revision]
base="base"
head="head"
"""
            content = (
                content[:current_review] + historical_nodes + content[current_review:]
            )
            content = content.replace('id="R01"\nsequence=2', 'id="R01"\nsequence=4')
            content = content.replace(
                'depends_on=["T01"]\nbrief="tasks/R01-brief.md"',
                'depends_on=["T02"]\nbrief="tasks/R01-brief.md"',
            )
            current_scope = content.index(
                'terminal_node_ids=["T01"]', current_review + len(historical_nodes)
            )
            content = content[:current_scope] + content[current_scope:].replace(
                'terminal_node_ids=["T01"]', 'terminal_node_ids=["T02"]', 1
            )
            content = content.replace('id="F01"\nsequence=3', 'id="F01"\nsequence=5')
            manifest.write_text(content)

            historical_invocation = (
                root / "reviews/round-0/00-historical-invocation.toml"
            )
            (root / "reviews/round-0/03-historical-review.md").write_text(
                "historical non-approving review\n"
            )
            current_invocation = root / "reviews/round-0/00-review-invocation.toml"
            result = root / "reviews/round-0/03-review.md"
            result.write_text(result.read_text() + "invocation_id=I-HISTORICAL\n")
            result_digest = hashlib.sha256(result.read_bytes()).hexdigest()
            invocation = current_invocation.read_text().replace(
                'result_sha256="7ca5080409fcb44e4e39af86bf963399db66108f37fbe1ce9d50fdc3842884d6"',
                f'result_sha256="{result_digest}"',
            )
            current_invocation.write_text(invocation)
            invocation = invocation.replace(
                'invocation_id="I-REVIEW"', 'invocation_id="I-HISTORICAL"'
            )
            invocation = invocation.replace(
                'task_name="review-task"', 'task_name="historical-review"'
            )
            invocation = invocation.replace(
                'spawn_result_task_name="review-task"',
                'spawn_result_task_name="historical-review"',
            )
            invocation = invocation.replace(
                'returned_decision="approve"',
                'returned_decision="do-not-approve"',
            )
            invocation = invocation.replace(
                'dispatching_controller="controller-task"\n', ""
            )
            invocation += 'assurance_level="observable-named-dispatch"\n'
            historical_invocation.write_text(invocation)

            state = root / "03-state.toml"
            self.replace(
                state,
                'completed_node_ids=["F01","R01","T01"]',
                'completed_node_ids=["F01","R01","T01","T02"]',
            )
            self.replace(state, "failed_node_ids=[]", 'failed_node_ids=["R00"]')
            self.assertEqual(validate(CONTRACT, root), ())

    def test_schema_old_history_reserves_invocation_id_in_any_order(self) -> None:
        for historical_first in (True, False):
            with (
                self.subTest(historical_first=historical_first),
                TemporaryDirectory() as temporary,
            ):
                root = self.copy_fixture(temporary)
                findings = self.historical_identity_findings(
                    root,
                    historical_id="I-REVIEW",
                    historical_first=historical_first,
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-REVIEW-REUSED-INVOCATION"
                        and error.reference == "I-REVIEW"
                        for error in findings
                    )
                )

    def test_schema_old_history_reserves_external_reference_in_any_order(self) -> None:
        reference = "ext-history-123"
        for historical_first in (True, False):
            with (
                self.subTest(historical_first=historical_first),
                TemporaryDirectory() as temporary,
            ):
                root = self.copy_fixture(temporary)
                findings = self.historical_identity_findings(
                    root,
                    historical_id="I-HISTORICAL",
                    historical_ref=reference,
                    current_ref=reference,
                    historical_first=historical_first,
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-REVIEW-REUSED-INVOCATION"
                        and error.reference == reference
                        for error in findings
                    )
                )

    def test_schema_old_history_reserves_external_id_in_any_order(self) -> None:
        identity = "external-history-123"
        for historical_first in (True, False):
            with (
                self.subTest(historical_first=historical_first),
                TemporaryDirectory() as temporary,
            ):
                root = self.copy_fixture(temporary)
                findings = self.historical_identity_findings(
                    root,
                    historical_id="I-HISTORICAL",
                    historical_external_id=identity,
                    current_external_id=identity,
                    historical_first=historical_first,
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-REVIEW-REUSED-INVOCATION"
                        and error.reference == identity
                        for error in findings
                    )
                )

    def test_schema_old_history_reserves_external_url_in_any_order(self) -> None:
        identity = "https://tasks.example/reviewer-history-123"
        for historical_first in (True, False):
            with (
                self.subTest(historical_first=historical_first),
                TemporaryDirectory() as temporary,
            ):
                root = self.copy_fixture(temporary)
                findings = self.historical_identity_findings(
                    root,
                    historical_id="I-HISTORICAL",
                    historical_url=identity,
                    current_url=identity,
                    historical_first=historical_first,
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-REVIEW-REUSED-INVOCATION"
                        and error.reference == identity
                        for error in findings
                    )
                )

    def test_external_identity_namespace_rejects_cross_field_reuse(self) -> None:
        identity = "external-shared-123"
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            findings = self.historical_identity_findings(
                root,
                historical_id="I-HISTORICAL",
                historical_external_id=identity,
                current_url=identity,
            )
        self.assertTrue(
            any(
                error.code == "TWV-REVIEW-REUSED-INVOCATION"
                and error.reference == identity
                for error in findings
            )
        )

    def test_distinct_schema_old_and_current_identities_remain_compatible(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            findings = self.historical_identity_findings(
                root,
                historical_id="I-HISTORICAL",
                historical_external_id="external-history-123",
                current_url="https://tasks.example/current-456",
                historical_ref="ext-history-123",
            )
        self.assertEqual(findings, [])

    def test_invocation_and_external_identity_namespaces_are_distinct(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            findings = self.historical_identity_findings(
                root,
                historical_id="I-HISTORICAL",
                historical_external_id="I-REVIEW",
            )
        self.assertEqual(findings, [])

    def test_schema_old_history_requires_a_reservable_invocation_id(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            findings = self.historical_identity_findings(
                root,
                historical_id="unavailable",
            )
        self.assertTrue(
            any(error.code == "TWV-SCHEMA-MISSING-FIELD" for error in findings)
        )

    def test_scenario_112_uses_canonical_final_decision(self) -> None:
        scenarios = (CONTRACT / "references/pressure-scenarios.md").read_text()

        def scenario(number: int) -> str:
            match = re.search(rf"(?ms)^{number}\. .*?(?=^\d+\. |\Z)", scenarios)
            self.assertIsNotNone(match)
            return match.group(0) if match is not None else ""

        scenario_112 = scenario(112)
        self.assertIn("`not-ready`", scenario_112)
        obsolete = re.compile(r"\bnot\s+ready\b")
        self.assertIsNone(obsolete.search(scenario_112))
        self.assertIsNotNone(
            obsolete.search(scenario_112.replace("not-ready", "not\n     ready"))
        )
        self.assertIn("`not ready`", scenario(153))

    def test_malformed_cli_input_is_read_only_and_deterministic(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.copy_fixture(temporary)
            self.replace(
                root / "03-state.toml", 'next_action="complete"', "next_action=42"
            )
            before = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*")
                if path.is_file()
            }
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--contract-dir", str(CONTRACT), "--task-dir", str(root)])
            lines = output.getvalue().splitlines()
            after = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(code, 2)
            self.assertTrue(
                any(line.startswith("TWV-SCHEMA-WRONG-SHAPE") for line in lines)
            )
            self.assertEqual(
                lines, sorted(lines, key=lambda line: line.split(" ", 3)[:3])
            )
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
