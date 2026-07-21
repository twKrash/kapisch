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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kapisch_validation.cli import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--approve", action="store_true", help="confirm the copy")
    args = parser.parse_args(argv)
    if not args.approve:
        parser.error("migration requires explicit --approve")

    project = args.project_dir.resolve()
    source = project / ".planning" / "KAPISCH" / args.task_id
    destination = project / ".kapisch" / "runs" / args.task_id
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
        os.rename(staged, destination)
    print(f"source={source}")
    print(f"destination={destination}")
    print("status=migrated; source retained without mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
