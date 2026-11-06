from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PackageTests(unittest.TestCase):
    def test_installed_console_matches_module_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            source = root / "core"
            shutil.copytree(
                ROOT / "core",
                source,
                ignore=shutil.ignore_patterns("build", "*.egg-info"),
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    str(source),
                    "--no-deps",
                    "--wheel-dir",
                    str(wheelhouse),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertFalse((ROOT / "core" / "build").exists())
            self.assertEqual(list((ROOT / "core").glob("*.egg-info")), [])
            venv = root / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv)],
                check=True,
                capture_output=True,
                text=True,
            )
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(next(wheelhouse.glob("*.whl"))),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            executable = venv / (
                "Scripts/kapisch-validate.exe"
                if os.name == "nt"
                else "bin/kapisch-validate"
            )
            runtime_env = os.environ.copy()
            runtime_env.pop("PYTHONPATH", None)
            runtime_env.pop("PYTHONHOME", None)
            probe = subprocess.run(
                [
                    str(python),
                    "-c",
                    "import kapisch_core.cli; print(kapisch_core.cli.__file__)",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=root,
                env=runtime_env,
            )
            self.assertTrue(
                Path(probe.stdout.strip()).resolve().is_relative_to(venv.resolve())
            )
            for command in (
                [str(python), "-m", "kapisch_core.cli", "--help"],
                [str(executable), "--help"],
            ):
                result = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=root,
                    env=runtime_env,
                )
                self.assertIn("--repo", result.stdout)

            repo = root / "repo"
            repo.mkdir()
            commands = (
                [
                    str(python),
                    "-m",
                    "kapisch_core.cli",
                    "--repo",
                    str(repo),
                    "--run",
                    "missing",
                ],
                [str(executable), "--repo", str(repo), "--run", "missing"],
            )
            results = [
                subprocess.run(
                    command, capture_output=True, text=True, cwd=root, env=runtime_env
                )
                for command in commands
            ]
            self.assertEqual([result.returncode for result in results], [1, 1])
            self.assertEqual(results[0].stdout, results[1].stdout)

    def test_task_first_decision_guidance(self) -> None:
        import json
        import re

        from kapisch_core._task_artifacts import ContractError
        from kapisch_core._task_authority import (
            _APPLICABILITY_BINDING_FIELDS,
            _APPLICABILITY_CONTROL_FIELDS,
            _APPLICABILITY_DIAGNOSTICS,
            _APPLICABILITY_RESULTS,
            _ORIGINAL_GOVERNING_INPUTS,
        )
        from kapisch_core._task_decisions import (
            _DECISION_OUTSIDE_RUN,
            _DECISION_RUN_MISMATCH,
            _MISSING_DECISION,
        )
        from kapisch_core._task_roots import _INVALID_ROOT_MAPPING
        from kapisch_core._task_supersession import (
            _SUPERSEDES_FIELDS,
            _SUPERSEDES_OUTSIDE_RUN,
            _SUPERSESSION_DIAGNOSTICS,
        )
        from kapisch_core.task_contract import _INVALID_RUN_IDENTITY

        text = (ROOT / "core/contracts/task-first.md").read_text()
        headings = set(re.findall(r"^#{2,3} (.+)$", text, re.MULTILINE))
        self.assertTrue(
            {
                "Run-local decisions, reassessment, and supersession",
                "Retention of Run history",
                "Machine-checkable decision contract",
            }
            <= headings
        )
        blocks = re.findall(
            r"<!-- ws2-decision-contract -->\s*```json\n(.*?)\n```\s*"
            r"<!-- /ws2-decision-contract -->",
            text,
            re.DOTALL,
        )
        self.assertEqual(len(blocks), 1)
        contract = json.loads(blocks[0])
        self.assertEqual(
            contract["run_identity"],
            {
                "format": "canonical lowercase UUIDv4",
                "producer": "coordinator",
                "creation": "exclusive Run directory via create_run",
            },
        )
        self.assertEqual(
            contract["roots"],
            {"state_root": "primary checkout", "source_root": "Git checkout"},
        )
        self.assertEqual(contract["human_decision"]["run_id_required"], True)
        self.assertEqual(
            contract["applicability"],
            {
                "results": sorted(_APPLICABILITY_RESULTS),
                "binding_fields": list(_APPLICABILITY_BINDING_FIELDS),
                "optional_fields": [_ORIGINAL_GOVERNING_INPUTS],
                "required_fields": list(_APPLICABILITY_CONTROL_FIELDS),
            },
        )
        self.assertEqual(
            contract["supersedes"]["entry_fields"], sorted(_SUPERSEDES_FIELDS)
        )
        self.assertEqual(contract["error_classes"], [ContractError.__name__])
        self.assertEqual(
            contract["diagnostics"],
            {
                **_APPLICABILITY_DIAGNOSTICS,
                **_SUPERSESSION_DIAGNOSTICS,
                "missing_decision": _MISSING_DECISION,
                "invalid_run_identity": _INVALID_RUN_IDENTITY,
                "decision_outside_run": _DECISION_OUTSIDE_RUN,
                "supersedes_outside_run": _SUPERSEDES_OUTSIDE_RUN,
                "decision_run_mismatch": _DECISION_RUN_MISMATCH,
                "invalid_root_mapping": _INVALID_ROOT_MAPPING,
            },
        )


if __name__ == "__main__":
    unittest.main()
