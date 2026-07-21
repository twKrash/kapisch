from __future__ import annotations

import unittest
from pathlib import Path

from kapisch_validation.manifest import parse_manifest

FIXTURES = Path(__file__).parent / "fixtures"


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

    def test_version_one_defaults_to_sequential_policy(self) -> None:
        result = parse_manifest(
            FIXTURES / "valid-v1-defaults" / "02-execution-graph.toml"
        )
        self.assertEqual(result.errors, ())
        self.assertEqual(result.manifest.policies["parallelism"], "off")

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


if __name__ == "__main__":
    unittest.main()
