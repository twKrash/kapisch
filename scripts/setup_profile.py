"""Install or inspect an optional KAPISCH project-scoped agent profile."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)

    root = args.project_dir.resolve()
    template = Path(__file__).resolve().parents[1] / "agents" / f"kapisch-{args.role}.toml"
    if not template.is_file():
        parser.error(f"unknown KAPISCH role: {args.role}")
    target = root / ".codex" / "agents" / template.name
    record = root / ".kapisch" / "local-state" / "profiles" / f"{args.role}.toml"
    template_digest = digest(template)

    if target.exists():
        installed_digest = digest(target)
        print(f"profile={target}")
        print("status=collision" if not record.exists() else "status=installed")
        print(f"template_sha256={template_digest}")
        print(f"installed_sha256={installed_digest}")
        if record.exists():
            saved = record.read_text(encoding="utf-8")
            expected = next(
                (line.split("=", 1)[1].strip().strip('"')
                 for line in saved.splitlines()
                 if line.startswith("installed_sha256=")),
                None,
            )
            print("drift=user-modified" if expected != installed_digest else "drift=none")
        print("action=review; profile was not changed")
        return 2 if not record.exists() else 0
    if not args.install:
        print(f"profile={target}")
        print("status=not-installed")
        print("action=rerun with --install after human review")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, target)
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        f'template="{template}"\n'
        f'template_sha256="{template_digest}"\n'
        f'installed_profile="{target}"\n'
        f'installed_sha256="{digest(target)}"\n',
        encoding="utf-8",
    )
    print(f"profile={target}")
    print("status=installed")
    print("action=profile copied; no existing profile was overwritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
