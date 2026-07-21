"""Inspect or explicitly install an optional KAPISCH agent profile."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path
import tomllib


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile_name(path: Path) -> str | None:
    """Return the profile identity when a TOML file is readable, else None."""
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8")).get("name")
    except (OSError, tomllib.TOMLDecodeError):
        return None
    return value if isinstance(value, str) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument(
        "--user-dir",
        type=Path,
        default=Path.home(),
        help="user home for --scope user (primarily useful for controlled setup)",
    )
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)

    root = (args.project_dir if args.scope == "project" else args.user_dir).resolve()
    template = Path(__file__).resolve().parents[1] / "agents" / f"kapisch-{args.role}.toml"
    if not template.is_file():
        parser.error(f"unknown KAPISCH role: {args.role}")
    target = root / ".codex" / "agents" / template.name
    record = root / ".kapisch" / "local-state" / "profiles" / f"{args.role}.toml"
    template_digest = digest(template)

    if target.exists():
        installed_digest = digest(target)
        actual_name = profile_name(target)
        print(f"profile={target}")
        print(f"scope={args.scope}")
        print(
            "status=collision"
            if not record.exists() or actual_name != f"kapisch-{args.role}"
            else "status=installed"
        )
        print(f"expected_identity=kapisch-{args.role}")
        print(f"installed_identity={actual_name or 'unreadable'}")
        print(f"template_sha256={template_digest}")
        print(f"installed_sha256={installed_digest}")
        if record.exists():
            saved = record.read_text(encoding="utf-8")
            expected_installed = next(
                (line.split("=", 1)[1].strip().strip('"')
                 for line in saved.splitlines()
                 if line.startswith("installed_sha256=")),
                None,
            )
            expected_template = next(
                (line.split("=", 1)[1].strip().strip('"')
                 for line in saved.splitlines()
                 if line.startswith("template_sha256=")),
                None,
            )
            print("drift=user-modified" if expected_installed != installed_digest else "drift=none")
            print("template_drift=updated" if expected_template != template_digest else "template_drift=none")
        print("action=review; profile was not changed")
        return 2 if not record.exists() or actual_name != f"kapisch-{args.role}" else 0
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
        f'scope="{args.scope}"\n'
        f'profile_identity="kapisch-{args.role}"\n'
        f'installed_sha256="{digest(target)}"\n',
        encoding="utf-8",
    )
    print(f"profile={target}")
    print(f"scope={args.scope}")
    print("status=installed")
    print("action=profile copied; no existing profile was overwritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
