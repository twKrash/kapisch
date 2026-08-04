#!/usr/bin/env python3
"""Exercise the portable plugin package from an isolated copied root.

This is not a Codex installation test. It proves only that the bundled files,
primary skill, and validator suite do not import a source application.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MANIFEST_KEYS = {"name", "version", "description", "author", "skills", "interface"}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="kapisch-portable-package-") as tmp:
        installed = Path(tmp) / "kapisch"
        shutil.copytree(
            ROOT,
            installed,
            ignore=shutil.ignore_patterns(
                ".git", ".kapisch", ".codex", "__pycache__", ".venv"
            ),
        )
        manifest = installed / ".codex-plugin" / "plugin.json"
        skill = installed / "skills" / "kapisch" / "SKILL.md"
        themes = installed / "skills" / "kapisch" / "themes"
        if (
            not manifest.is_file()
            or not skill.is_file()
            or "name: kapisch" not in skill.read_text(encoding="utf-8")
            or not (themes / "default.toml").is_file()
            or not (themes / "foundry.toml").is_file()
        ):
            print(
                "portable package is missing the KAPISCH manifest, primary skill, "
                "or bundled themes"
            )
            return 1
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("portable package has an invalid plugin manifest")
            return 1
        if (
            not isinstance(payload, dict)
            or not REQUIRED_MANIFEST_KEYS <= payload.keys()
            or payload.get("name") != "kapisch"
            or payload.get("skills") != "./skills/"
            or not isinstance(payload.get("interface"), dict)
        ):
            print("portable package has an incompatible plugin manifest")
            return 1
        if (installed / ".codex" / "agents").exists():
            print("portable package isolation retained an installed Codex profile")
            return 1
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests/kapisch_validation"],
            cwd=installed,
            text=True,
        )
        if result.returncode:
            return result.returncode
        consumer = Path(tmp) / "consumer"
        run = consumer / ".kapisch" / "runs" / "dogfood"
        shutil.copytree(installed / "tests/kapisch_validation/fixtures/valid-sequential-v2", run)
        result = subprocess.run(
            [
                sys.executable,
                str(installed / "scripts/validate_kapisch.py"),
                "--contract-dir",
                str(installed / "skills/kapisch"),
                "--task-dir",
                str(run),
            ],
            cwd=consumer,
            text=True,
        )
        if result.returncode:
            return result.returncode
        graph_free = consumer / ".kapisch" / "runs" / "graph-free"
        shutil.copytree(
            installed / "tests/kapisch_validation/fixtures/valid-delegations-graph-free",
            graph_free,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(installed / "scripts/validate_kapisch.py"),
                "--contract-dir",
                str(installed / "skills/kapisch"),
                "--task-dir",
                str(graph_free),
                "--scope",
                "delegations",
            ],
            cwd=consumer,
            text=True,
        )
        if result.returncode:
            return result.returncode
        durable = consumer / ".kapisch" / "runs" / "durable-v3"
        shutil.copytree(
            installed / "tests/kapisch_validation/fixtures/valid-v3-durable",
            durable,
        )
        result = subprocess.run(
            [
                sys.executable,
                str(installed / "scripts/validate_kapisch.py"),
                "--contract-dir",
                str(installed / "skills/kapisch"),
                "--task-dir",
                str(durable),
            ],
            cwd=consumer,
            text=True,
        )
        if result.returncode:
            return result.returncode
    print("portable-package=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
