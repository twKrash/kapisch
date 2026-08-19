from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from kapisch_validation.cli import BUNDLED_CONTRACT_ERROR, main


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "valid-sequential-v2"
CONTRACT = PLUGIN_ROOT / "skills" / "kapisch"


class ContractDiscoveryTests(unittest.TestCase):
    def test_automatic_bundled_contract_discovery(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--task-dir", str(FIXTURE), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), [])

    def test_explicit_contract_override(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "--contract-dir",
                    str(CONTRACT),
                    "--task-dir",
                    str(FIXTURE),
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), [])

    def test_missing_or_corrupt_bundled_contract_is_actionable(self) -> None:
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as temporary:
                contract = Path(temporary)
                if corrupt:
                    (contract / "SKILL.md").write_bytes(b"\xff")
                stderr = io.StringIO()
                with mock.patch(
                    "kapisch_validation.cli._bundled_contract_resource",
                    return_value=contract,
                ), redirect_stderr(stderr):
                    code = main(["--task-dir", str(FIXTURE)])
                self.assertEqual(code, 2)
                self.assertEqual(stderr.getvalue().strip(), BUNDLED_CONTRACT_ERROR)
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_compatibility_wrapper_uses_automatic_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as unrelated:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts" / "validate_kapisch.py"),
                    "--task-dir",
                    str(FIXTURE),
                    "--format",
                    "json",
                ],
                cwd=unrelated,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), [])


class WheelInstallationTests(unittest.TestCase):
    def test_installed_console_help_and_unrelated_cwd_validation(self) -> None:
        build_python = sys.executable
        if subprocess.run(
            [build_python, "-c", "import setuptools.build_meta"],
            capture_output=True,
            check=False,
        ).returncode:
            build_python = shutil.which("python3.11") or build_python
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            shutil.copytree(
                PLUGIN_ROOT,
                source,
                ignore=shutil.ignore_patterns(
                    "build", "dist", "*.egg-info", "__pycache__", "*.pyc"
                ),
            )
            wheelhouse = root / "wheelhouse"
            wheelhouse.mkdir()
            built = subprocess.run(
                [
                    build_python,
                    "-m",
                    "pip",
                    "wheel",
                    ".",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(wheelhouse),
                ],
                cwd=source,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            wheel = next(wheelhouse.glob("kapisch_validation-*.whl"))
            venv = root / "venv"
            subprocess.run([build_python, "-m", "venv", str(venv)], check=True)
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            command = venv / ("Scripts/kapisch-validate.exe" if os.name == "nt" else "bin/kapisch-validate")
            installed = subprocess.run(
                [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

            help_result = subprocess.run(
                [str(command), "--help"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("usage: kapisch-validate", help_result.stdout)
            self.assertIn("--contract-dir", help_result.stdout)

            validation = subprocess.run(
                [str(command), "--task-dir", str(FIXTURE), "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(json.loads(validation.stdout), [])


if __name__ == "__main__":
    unittest.main()
