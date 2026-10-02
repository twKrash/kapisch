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
            shutil.copytree(ROOT / "core", source,
                            ignore=shutil.ignore_patterns("build", "*.egg-info"))
            subprocess.run([sys.executable, "-m", "pip", "wheel", str(source),
                            "--no-deps", "--wheel-dir", str(wheelhouse)], check=True,
                           capture_output=True, text=True)
            self.assertFalse((ROOT / "core" / "build").exists())
            self.assertEqual(list((ROOT / "core").glob("*.egg-info")), [])
            venv = root / "venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True,
                           capture_output=True, text=True)
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                            str(next(wheelhouse.glob("*.whl")))], check=True,
                           capture_output=True, text=True)
            executable = venv / ("Scripts/kapisch-validate.exe" if os.name == "nt"
                                 else "bin/kapisch-validate")
            runtime_env = os.environ.copy()
            runtime_env.pop("PYTHONPATH", None)
            runtime_env.pop("PYTHONHOME", None)
            probe = subprocess.run(
                [str(python), "-c", "import kapisch_core.cli; print(kapisch_core.cli.__file__)"],
                check=True, capture_output=True, text=True, cwd=root, env=runtime_env,
            )
            self.assertTrue(Path(probe.stdout.strip()).resolve().is_relative_to(venv.resolve()))
            for command in ([str(python), "-m", "kapisch_core.cli", "--help"],
                            [str(executable), "--help"]):
                result = subprocess.run(command, check=True, capture_output=True, text=True,
                                        cwd=root, env=runtime_env)
                self.assertIn("--repo", result.stdout)

            repo = root / "repo"
            repo.mkdir()
            commands = ([str(python), "-m", "kapisch_core.cli", "--repo", str(repo),
                         "--run", "missing"],
                        [str(executable), "--repo", str(repo), "--run", "missing"])
            results = [subprocess.run(command, capture_output=True, text=True, cwd=root,
                                      env=runtime_env) for command in commands]
            self.assertEqual([result.returncode for result in results], [1, 1])
            self.assertEqual(results[0].stdout, results[1].stdout)


if __name__ == "__main__":
    unittest.main()
