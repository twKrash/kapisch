from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kapisch_validation.manifest import parse_manifest

FIXTURES = Path(__file__).parent / "fixtures"

V2_BODY = """version = 2
task_id = "t"
source_plan = "01-plan.md"
base_revision = "base"
[policies]
execution="sequential"
executor="implementer"
dispatch="single"
model_tier="standard"
batching="off"
parallelism="off"
max_parallel_agents=1
commit="manual"
push="manual"
fix_policy="manual"
max_fix_rounds=1
[[nodes]]
id="T01"
sequence=1
title="implement"
kind="behavioral"
risk="low"
status="complete"
depends_on=[]
brief="b.md"
context="c.md"
report="r.md"
reads=[]
writes=[]
shared_resources=[]
verification=[]
context_refs=[]
executor_class="implementer"
model_tier="standard"
batching="off"
[nodes.revision]
base="base"
head="head"
"""


class ManifestTests(unittest.TestCase):
    def test_valid_v2_manifest_has_no_findings(self) -> None:
        result = parse_manifest(
            FIXTURES / "valid-sequential-v2" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(result.manifest.version, 2)

    def test_unknown_field_is_a_stable_schema_error(self) -> None:
        result = parse_manifest(
            FIXTURES / "unknown-normative-field" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors[0].code, "TWV-SCHEMA-UNKNOWN-FIELD")

    def test_legacy_yaml_is_rejected_without_parsing_it(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-legacy-yaml" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors[0].code, "TWV-PARSE-UNSUPPORTED-LEGACY-YAML")

    def test_toml_load_failures_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            for content, expected in (
                (b"\xff", "TWV-PARSE-INVALID-UTF8"),
                (b"version = [", "TWV-PARSE-MALFORMED-TOML"),
            ):
                with self.subTest(expected=expected):
                    path.write_bytes(content)
                    result = parse_manifest(path)
                    self.assertEqual(result.errors[0].code, expected)
            path.write_text(V2_BODY, encoding="utf-8")
            with mock.patch(
                "kapisch_validation.artifact_io.os.open",
                side_effect=PermissionError("denied"),
            ):
                result = parse_manifest(path)
        self.assertEqual(result.errors[0].code, "TWV-PARSE-UNREADABLE-ARTIFACT")

    def test_version_one_defaults_to_sequential_policy(self) -> None:
        result = parse_manifest(
            FIXTURES / "valid-v1-defaults" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(result.manifest.policies["parallelism"], "off")
        self.assertEqual(result.manifest.policies["max_fix_rounds"], 1)

    def test_preserves_optional_roadmap_item(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            path.write_text(
                V2_BODY.replace(
                    'source_plan = "01-plan.md"',
                    'source_plan = "01-plan.md"\nroadmap_item = "milestone-old"',
                ),
                encoding="utf-8",
            )
            result = parse_manifest(path)
        self.assertEqual(result.errors, ())
        self.assertEqual(result.manifest.roadmap_item, "milestone-old")

    def test_rejects_nonfinite_extension_float(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            path.write_text(
                V2_BODY + '\n[extensions."org.example"]\nvalue = nan\n',
                encoding="utf-8",
            )
            result = parse_manifest(path)
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [("TWV-SCHEMA-NONFINITE-FLOAT", "extensions.org.example.value")],
        )

    def test_rejects_duplicate_runtime_record_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            path.write_text(
                V2_BODY.replace(
                    '[nodes.revision]',
                    'verification_evidence=[{id="V01",check="tests",result="pass",evidence_ref="r.md",output_sha256="digest",revision="head"},{id="V01",check="tests",result="pass",evidence_ref="r.md",output_sha256="digest",revision="head"}]\n[nodes.revision]',
                ),
                encoding="utf-8",
            )
            result = parse_manifest(path)
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [
                ("TWV-SCHEMA-DUPLICATE-RUNTIME-ID", "nodes[0].verification_evidence"),
                ("TWV-SCHEMA-INVALID-DIGEST", "nodes[0].verification_evidence[0].output_sha256"),
                ("TWV-SCHEMA-INVALID-DIGEST", "nodes[0].verification_evidence[1].output_sha256"),
            ],
        )

    def test_operational_wave_fixture_fails_closed(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-operational-wave" / "02-execution-graph.toml"
        )
        self.assertTrue(result.errors)
        self.assertTrue(
            all(
                error.code == "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE"
                for error in result.errors
            )
        )

    def test_empty_legacy_wave_scope_fields_remain_readable(self) -> None:
        result = parse_manifest(
            FIXTURES / "valid-empty-legacy-wave-scope" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors, ())

    def test_non_empty_legacy_wave_scope_fails_closed(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-nonempty-wave-scope" / "02-execution-graph.toml"
        )
        self.assertEqual(
            [error.reference for error in result.errors],
            ["nodes[0].review_scope.integrated_wave_ids"],
        )
        self.assertEqual(
            result.errors[0].code, "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE"
        )

    def test_empty_root_waves_key_fails_closed(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-empty-root-waves" / "02-execution-graph.toml"
        )
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [("TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE", "root.waves")],
        )

    def test_non_off_parallelism_fails_closed_independently(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-parallelism" / "02-execution-graph.toml"
        )
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [
                (
                    "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
                    "policies.parallelism",
                )
            ],
        )

    def test_parallel_agent_limit_fails_closed_independently(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-parallel-agent-limit" / "02-execution-graph.toml"
        )
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [
                (
                    "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
                    "policies.max_parallel_agents",
                )
            ],
        )

    def test_terminal_root_wave_fails_closed(self) -> None:
        result = parse_manifest(
            FIXTURES / "unsupported-terminal-root-wave" / "02-execution-graph.toml"
        )
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [("TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE", "root.waves")],
        )

    def test_non_empty_wave_terminal_dependency_fails_closed(self) -> None:
        result = parse_manifest(
            FIXTURES
            / "unsupported-nonempty-wave-terminal-dependencies"
            / "02-execution-graph.toml"
        )
        self.assertEqual(
            [(error.code, error.reference) for error in result.errors],
            [
                (
                    "TWV-SCHEMA-UNSUPPORTED-OPERATIONAL-WAVE",
                    "nodes[0].review_scope.wave_terminal_dependencies",
                )
            ],
        )

    def _v3_body(self, policy_value: str = "auto") -> str:
        body = V2_BODY.replace("version = 2", "version = 3")
        body = body.replace(
            'id="T01"\nsequence=1', 'id="T01"\nsequence=1\ndelegation_ids=[]'
        )
        return body.replace(
            "max_fix_rounds=1", f'max_fix_rounds=1\necosystem_routing="{policy_value}"'
        )

    def test_version_three_requires_ecosystem_routing_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            body = self._v3_body()
            body = body.replace(
                'ecosystem_routing="auto"', ""
            ).replace("\n\n[[nodes]]", "\n[[nodes]]")
            path.write_text(body, encoding="utf-8")
            result = parse_manifest(path)
            self.assertEqual(
                [(error.code, error.reference) for error in result.errors],
                [("TWV-SCHEMA-MISSING-FIELD", "policies.ecosystem_routing")],
            )

    def test_version_three_accepts_ecosystem_routing_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            path.write_text(self._v3_body(), encoding="utf-8")
            result = parse_manifest(path)
            self.assertEqual(result.errors, ())
            self.assertEqual(result.manifest.version, 3)
            self.assertEqual(result.manifest.policies["ecosystem_routing"], "auto")

    def test_version_three_rejects_invalid_ecosystem_routing_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            path.write_text(self._v3_body(policy_value="sometimes"), encoding="utf-8")
            result = parse_manifest(path)
            self.assertEqual(
                [(error.code, error.reference) for error in result.errors],
                [("TWV-SCHEMA-INVALID-VALUE", "policies.ecosystem_routing")],
            )

    def test_version_three_requires_delegation_ids_on_every_node(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            body = self._v3_body().replace("delegation_ids=[]\n", "", 1)
            path.write_text(body, encoding="utf-8")
            result = parse_manifest(path)
            self.assertEqual(
                [(error.code, error.reference) for error in result.errors],
                [("TWV-SCHEMA-MISSING-FIELD", "nodes[0].delegation_ids")],
            )

    def test_version_two_rejects_version_three_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            body = V2_BODY.replace("max_fix_rounds=1", 'max_fix_rounds=1\necosystem_routing="auto"')
            path.write_text(body, encoding="utf-8")
            result = parse_manifest(path)
            self.assertEqual(
                [(error.code, error.reference) for error in result.errors],
                [("TWV-SCHEMA-UNSUPPORTED-V3-FIELD", "policies.ecosystem_routing")],
            )

    def test_version_two_rejects_version_three_node_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "02-execution-graph.toml"
            body = V2_BODY.replace(
                'id="T01"\nsequence=1', 'id="T01"\nsequence=1\ndelegation_ids=["D01"]'
            )
            path.write_text(body, encoding="utf-8")
            result = parse_manifest(path)
            self.assertEqual(
                [(error.code, error.reference) for error in result.errors],
                [("TWV-SCHEMA-UNSUPPORTED-V3-FIELD", "nodes[0].delegation_ids")],
            )

    def test_valid_v3_durable_fixture_parses(self) -> None:
        result = parse_manifest(
            FIXTURES / "valid-v3-durable" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(result.manifest.version, 3)


if __name__ == "__main__":
    unittest.main()
