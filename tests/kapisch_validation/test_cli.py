from __future__ import annotations

import hashlib
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from kapisch_validation.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
CONTRACT = Path("skills/kapisch")


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

    def test_missing_required_arguments_is_usage_error(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)

    def test_required_cli_fixture_matrix_has_stable_primary_codes(self) -> None:
        cases = {
            "valid-sequential-v2": (0, None),
            "valid-v1-defaults": (0, None),
            "missing-review-scope": (2, "TWV-REVIEW-MISSING-SCOPE"),
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
        code, lines = self._run(
            "illegal-transition",
            "--previous-task-dir",
            str(FIXTURES / "illegal-transition-previous"),
        )
        self.assertEqual(code, 2)
        self.assertTrue(
            any(line.startswith("TWV-LIFECYCLE-ILLEGAL-TRANSITION") for line in lines)
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


if __name__ == "__main__":
    unittest.main()
