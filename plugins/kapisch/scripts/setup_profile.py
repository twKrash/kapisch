"""Inspect or explicitly install optional KAPISCH agent profiles."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any
import tomllib


AGENT_DIR = Path(__file__).resolve().parents[1] / "agents"
ROLE_CATALOG = (
    "architect",
    "implementer-lite",
    "implementer",
    "mechanic",
    "researcher",
    "reviewer",
)


class ProfileReadError(Exception):
    """A profile could not be safely read or parsed."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_profile(path: Path) -> dict[str, Any]:
    try:
        contents = path.read_bytes()
    except OSError as exc:
        raise ProfileReadError(str(exc)) from exc
    return _parse_profile_bytes(contents)


def _parse_profile_bytes(contents: bytes) -> dict[str, Any]:
    try:
        value = tomllib.loads(contents.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ProfileReadError(str(exc)) from exc
    if not isinstance(value, dict):
        raise ProfileReadError("profile TOML is not a table")
    return value


def profile_name(path: Path) -> str | None:
    """Return the profile identity when a TOML file is readable, else None."""
    try:
        value = _read_profile(path).get("name")
    except ProfileReadError:
        return None
    return value if isinstance(value, str) else None


def toml_basic_string(value: str | Path) -> str:
    """Encode a value as a TOML basic string without a runtime dependency."""
    text = str(value)
    escapes = {
        "\\": "\\\\",
        '"': '\\"',
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
    }
    result = ['"']
    for character in text:
        if character in escapes:
            result.append(escapes[character])
        elif ord(character) < 0x20 or ord(character) == 0x7F:
            result.append(f"\\u{ord(character):04x}")
        elif 0xD800 <= ord(character) <= 0xDFFF:
            result.append(f"\\u{ord(character):04x}")
        else:
            result.append(character)
    result.append('"')
    return "".join(result)


def identity_collisions(agent_dir: Path, expected_name: str, target: Path) -> list[Path]:
    """Find other readable agent profiles with the identity we would install."""
    if not agent_dir.is_dir():
        return []
    return [
        path
        for path in sorted(agent_dir.glob("*.toml"))
        if path != target and profile_name(path) == expected_name
    ]


def _record_values(path: Path) -> dict[str, Any]:
    try:
        return _read_profile(path)
    except ProfileReadError as exc:
        raise ProfileReadError(f"state record is unreadable or malformed: {exc}") from exc


def _record_text(
    *,
    template: Path,
    template_digest: str,
    target: Path,
    scope: str,
    role: str,
    installed_digest: str,
) -> str:
    fields = (
        ("template", template),
        ("template_sha256", template_digest),
        ("installed_profile", target),
        ("scope", scope),
        ("profile_identity", f"kapisch-{role}"),
        ("installed_sha256", installed_digest),
    )
    return "".join(f"{name}={toml_basic_string(value)}\n" for name, value in fields)


def _print_plan(plan: dict[str, Any], scope: str) -> None:
    print(f"profile={plan['target']}")
    print(f"scope={scope}")
    print(f"status={plan['status']}")
    for key in ("expected_identity", "installed_identity", "template_digest", "installed_digest"):
        if plan.get(key) is not None:
            label = {"template_digest": "template_sha256", "installed_digest": "installed_sha256"}.get(key, key)
            print(f"{label}={plan[key]}")
    for key in ("drift", "template_drift", "error"):
        if plan.get(key) is not None:
            print(f"{key}={plan[key]}")
    for collision in plan.get("collision", ()):
        print(f"identity_collision={collision}")
    if plan["status"] == "installed" and plan.get("installed_now"):
        print("action=profile copied; no existing profile was overwritten")
    elif plan["status"] == "not-installed":
        print("action=rerun with --install after human review")
    else:
        print("action=review; profile was not changed")


def _adjacent_errors(
    agent_dir: Path,
    *,
    expected_names: set[str],
    targets: set[Path],
) -> list[tuple[Path, str]]:
    """Reject unreadable/malformed adjacent profiles before any installation."""
    try:
        agent_dir.stat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        return [(agent_dir, f"agent directory is unreadable: {exc}")]
    if not agent_dir.is_dir():
        return [(agent_dir, "agent destination is not a directory")]
    try:
        paths = sorted(agent_dir.glob("*.toml"))
    except OSError as exc:
        return [(agent_dir, f"agent directory is unreadable: {exc}")]
    failures: list[tuple[Path, str]] = []
    for path in paths:
        # Destination targets are read once, atomically as a byte snapshot,
        # by _prepare_role. Reading them here would reintroduce a TOCTOU
        # window between adjacent validation and identity/digest validation.
        if path in targets:
            continue
        try:
            values = _read_profile(path)
        except ProfileReadError as exc:
            failures.append((path, f"unreadable or malformed TOML: {exc}"))
            continue
        if path in targets and values.get("name") not in expected_names:
            failures.append((path, f"unexpected profile identity: {values.get('name')!r}"))
    return failures


def _prepare_role(
    *,
    root: Path,
    scope: str,
    role: str,
    install: bool,
    adjacent_failures: list[tuple[Path, str]],
) -> dict[str, Any]:
    expected_identity = f"kapisch-{role}"
    template = AGENT_DIR / f"{expected_identity}.toml"
    target = root / ".codex" / "agents" / template.name
    record = root / ".kapisch" / "local-state" / "profiles" / f"{role}.toml"
    plan: dict[str, Any] = {
        "role": role,
        "template": template,
        "target": target,
        "record": record,
        "expected_identity": expected_identity,
    }
    try:
        template_bytes = template.read_bytes()
        template_values = _parse_profile_bytes(template_bytes)
        template_digest = hashlib.sha256(template_bytes).hexdigest()
    except (OSError, ProfileReadError) as exc:
        plan.update(status="collision", error=f"source template is unreadable or malformed: {exc}")
        return plan
    plan.update(template_digest=template_digest, template_bytes=template_bytes)
    if template_values.get("name") != expected_identity:
        plan.update(
            status="collision",
            error=f"source template has unexpected profile identity: {template_values.get('name')!r}",
        )
        return plan
    if adjacent_failures:
        plan.update(
            status="collision",
            error="adjacent profile safety check failed",
            collision=[f"{path}: {reason}" for path, reason in adjacent_failures],
        )
        return plan

    target_exists = target.exists() or target.is_symlink()
    if target_exists:
        try:
            installed_bytes = target.read_bytes()
            installed_digest = hashlib.sha256(installed_bytes).hexdigest()
            installed_values = _parse_profile_bytes(installed_bytes)
        except (OSError, ProfileReadError) as exc:
            plan.update(status="collision", installed_identity="unreadable", error=f"existing destination is unreadable or malformed: {exc}")
            return plan
        installed_identity = installed_values.get("name")
        plan.update(
            installed_digest=installed_digest,
            installed_identity=installed_identity if isinstance(installed_identity, str) else "unreadable",
        )
        if installed_identity != expected_identity:
            plan.update(status="collision", error="existing destination has unexpected profile identity")
            return plan
        try:
            collisions = identity_collisions(target.parent, expected_identity, target)
        except OSError as exc:
            plan.update(status="collision", error=f"adjacent profile directory is unreadable: {exc}")
            return plan
        if collisions:
            plan.update(status="collision", collision=collisions, error="identity collision")
            return plan
        if not record.exists() or record.is_symlink():
            plan.update(status="collision", error="installed profile has no verifiable state record")
            return plan
        try:
            saved = _record_values(record)
        except ProfileReadError as exc:
            plan.update(status="collision", error=str(exc))
            return plan
        if (
            saved.get("profile_identity") != expected_identity
            or saved.get("installed_profile") != str(target)
            or saved.get("template") != str(template)
            or not isinstance(saved.get("installed_sha256"), str)
            or not isinstance(saved.get("template_sha256"), str)
        ):
            plan.update(status="collision", error="state record identity or paths cannot be verified")
            return plan
        plan["drift"] = "none" if saved.get("installed_sha256") == installed_digest else "user-modified"
        plan["template_drift"] = "none" if saved.get("template_sha256") == template_digest else "updated"
        plan["status"] = "installed"
        return plan

    try:
        collisions = identity_collisions(target.parent, expected_identity, target)
    except OSError as exc:
        plan.update(status="collision", error=f"adjacent profile directory is unreadable: {exc}")
        return plan
    if collisions:
        plan.update(status="collision", collision=collisions, error="identity collision")
        return plan
    if record.exists() or record.is_symlink():
        plan.update(status="collision", error="state record exists without an installed profile")
        return plan
    plan["status"] = "install-pending" if install else "not-installed"
    return plan


def _commit(plans: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Commit missing profiles exclusively, rolling back files on failure."""
    created: list[Path] = []
    created_directories: list[Path] = []

    def ensure_directory(path: Path) -> None:
        current = path
        missing: list[Path] = []
        while True:
            try:
                current.stat()
            except FileNotFoundError:
                missing.append(current)
                current = current.parent
                continue
            except OSError:
                raise
            if not current.is_dir():
                raise OSError(f"destination parent is not a directory: {current}")
            break
        for directory in reversed(missing):
            try:
                directory.mkdir()
            except FileExistsError:
                # Another process may have created it. Only remove
                # directories this operation itself successfully created.
                if not directory.is_dir():
                    raise
            except OSError:
                # A platform/filesystem may report failure after creating
                # the directory. Capture that case before propagating the
                # error so rollback can still remove the partial tree.
                if directory.is_dir():
                    created_directories.append(directory)
                raise
            else:
                # Register immediately so later failures can remove every
                # directory created by this operation.
                created_directories.append(directory)

    try:
        for plan in plans:
            if plan["status"] != "install-pending":
                continue
            target = plan["target"]
            record = plan["record"]
            ensure_directory(target.parent)
            ensure_directory(record.parent)
            stream = target.open("xb")
            created.append(target)
            with stream:
                stream.write(plan["template_bytes"])
            stream = record.open("xb")
            created.append(record)
            with stream:
                stream.write(
                    _record_text(
                        template=plan["template"],
                        template_digest=plan["template_digest"],
                        target=target,
                        scope=plan["scope"],
                        role=plan["role"],
                        installed_digest=digest(target),
                    ).encode("utf-8")
                )
    except (OSError, ValueError) as exc:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        for directory in sorted(set(created_directories), key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        return False, str(exc)
    return True, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--role", choices=ROLE_CATALOG)
    selector.add_argument("--all", action="store_true", help="install the complete six-role catalog atomically")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--user-dir", type=Path, default=Path.home(), help="user home for --scope user")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)

    root = (args.project_dir if args.scope == "project" else args.user_dir).resolve()
    roles = list(ROLE_CATALOG if args.all else (args.role,))
    agent_dir = root / ".codex" / "agents"
    targets = {agent_dir / f"kapisch-{role}.toml" for role in roles}
    adjacent_failures = _adjacent_errors(
        agent_dir,
        expected_names={f"kapisch-{role}" for role in roles},
        targets=targets,
    )
    plans = [
        _prepare_role(root=root, scope=args.scope, role=role, install=args.install, adjacent_failures=adjacent_failures)
        for role in roles
    ]
    for plan in plans:
        plan["scope"] = args.scope

    failures = [plan for plan in plans if plan["status"] == "collision"]
    if args.install and not failures:
        committed, error = _commit(plans)
        if not committed:
            for plan in plans:
                if plan["status"] == "install-pending":
                    plan.update(status="collision", error=f"catalog installation rolled back: {error}")
            failures = [plan for plan in plans if plan["status"] == "collision"]
        else:
            for plan in plans:
                if plan["status"] == "install-pending":
                    plan["status"] = "installed"
                    plan["installed_now"] = True
                    plan["installed_digest"] = digest(plan["target"])

    for plan in plans:
        _print_plan(plan, args.scope)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
