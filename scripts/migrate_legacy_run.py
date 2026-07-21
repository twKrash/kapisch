#!/usr/bin/env python3
"""Explicitly copy a legacy KAPISCH run only after validation succeeds.

This is deliberately not part of kapisch_validation: migration writes and the
validator must remain a read-only structural verifier.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kapisch_validation.cli import validate
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.references import parse_state


TASK_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,79}\Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--approve", action="store_true", help="confirm the copy")
    args = parser.parse_args(argv)
    if not args.approve:
        parser.error("migration requires explicit --approve")
    if TASK_ID_RE.fullmatch(args.task_id) is None:
        parser.error("task ID must match [a-z0-9][a-z0-9-]{2,79}")

    project = args.project_dir.resolve()
    legacy_root = (project / ".planning" / "task-workflow").resolve()
    runs_root = (project / ".kapisch" / "runs").resolve()
    source = (legacy_root / args.task_id).resolve()
    destination = (runs_root / args.task_id).resolve()
    if source.parent != legacy_root or destination.parent != runs_root:
        parser.error("task ID escapes the legacy migration namespace")
    if not source.is_dir():
        parser.error(f"legacy source is missing: {source}")
    if destination.exists():
        parser.error(f"destination already exists and will not be replaced: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kapisch-migration-", dir=destination.parent) as tmp:
        staged = Path(tmp) / args.task_id
        shutil.copytree(source, staged, copy_function=shutil.copy2)
        errors = validate(ROOT / "skills" / "kapisch", staged)
        if errors:
            for error in errors:
                print(error)
            print("status=not-migrated; legacy source was retained")
            return 2
        manifest = parse_manifest(staged / "02-execution-graph.toml").manifest
        state, _ = parse_state(staged / "03-state.toml")
        assert manifest is not None and state is not None
        if manifest.task_id != args.task_id or state.task_id != args.task_id:
            print("migration task_id must match manifest and state task_id")
            print("status=not-migrated; legacy source was retained")
            return 2
        os.rename(staged, destination)
    print(f"source={source}")
    print(f"destination={destination}")
    print("status=migrated; source retained without mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
