"""Inspect or explicitly install optional KAPISCH agent profiles."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import secrets
from typing import Any, Callable, Iterator
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
PROFILE_SET_CATALOG = ("balanced", "quality", "budget")
PROFILE_SET_ROUTING = {
    "balanced": {
        "architect": ("gpt-5.6-sol", "high"),
        "researcher": ("gpt-5.6-terra", "medium"),
        "implementer": ("gpt-5.6-terra", "medium"),
        "implementer-lite": ("gpt-5.6-luna", "low"),
        "mechanic": ("gpt-5.6-luna", "low"),
        "reviewer": ("gpt-5.6-terra", "high"),
    },
    "quality": {
        "architect": ("gpt-5.6-sol", "high"),
        "researcher": ("gpt-5.6-sol", "high"),
        "implementer": ("gpt-5.6-terra", "medium"),
        "implementer-lite": ("gpt-5.6-luna", "low"),
        "mechanic": ("gpt-5.6-luna", "low"),
        "reviewer": ("gpt-5.6-sol", "high"),
    },
    "budget": {
        "architect": ("gpt-5.6-terra", "high"),
        "researcher": ("gpt-5.6-luna", "medium"),
        "implementer": ("gpt-5.6-terra", "low"),
        "implementer-lite": ("gpt-5.6-luna", "low"),
        "mechanic": ("gpt-5.6-luna", "low"),
        "reviewer": ("gpt-5.6-terra", "medium"),
    },
}


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


def _render_profile_bytes(canonical: bytes, *, role: str, profile_set: str) -> bytes:
    """Render one deterministic runtime profile from the canonical role contract."""
    values = _parse_profile_bytes(canonical)
    expected_identity = f"kapisch-{role}"
    if values.get("name") != expected_identity:
        raise ProfileReadError(
            f"source template has unexpected profile identity: {values.get('name')!r}"
        )
    quality_model, quality_effort = PROFILE_SET_ROUTING["quality"][role]
    if (
        values.get("model") != quality_model
        or values.get("model_reasoning_effort") != quality_effort
    ):
        raise ProfileReadError(
            "source template runtime settings do not match the quality baseline"
        )
    model, effort = PROFILE_SET_ROUTING[profile_set][role]
    try:
        lines = canonical.decode("utf-8").splitlines(keepends=True)
    except UnicodeError as exc:
        raise ProfileReadError(str(exc)) from exc
    rendered: list[str] = []
    model_fields = 0
    effort_fields = 0
    for line in lines:
        if line.startswith("model = "):
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            rendered.append(f'model = "{model}"{ending}')
            model_fields += 1
        elif line.startswith("model_reasoning_effort = "):
            ending = "\r\n" if line.endswith("\r\n") else "\n"
            rendered.append(f'model_reasoning_effort = "{effort}"{ending}')
            effort_fields += 1
        else:
            rendered.append(line)
    if model_fields != 1 or effort_fields != 1:
        raise ProfileReadError("source template must contain one model and effort field")
    result = "".join(rendered).encode("utf-8")
    rendered_values = _parse_profile_bytes(result)
    if (
        rendered_values.get("name") != expected_identity
        or rendered_values.get("model") != model
        or rendered_values.get("model_reasoning_effort") != effort
        or rendered_values.get("developer_instructions")
        != values.get("developer_instructions")
    ):
        raise ProfileReadError("rendered profile failed contract validation")
    return result


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
            raise ValueError("TOML strings cannot contain unpaired Unicode surrogates")
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


def _template_provenance_matches(saved: object, template: Path) -> bool:
    if not isinstance(saved, str) or not saved:
        return False
    if saved == template.name:
        return True
    return any(
        candidate.is_absolute()
        and candidate.parent.name == "agents"
        and candidate.name == template.name
        for candidate in (PurePosixPath(saved), PureWindowsPath(saved))
    )


def _record_text(
    *,
    template: Path,
    template_digest: str,
    target: Path,
    scope: str,
    role: str,
    profile_set: str,
    installed_digest: str,
) -> str:
    fields = (
        ("template", template.name),
        ("template_sha256", template_digest),
        ("installed_profile", target),
        ("scope", scope),
        ("profile_set", profile_set),
        ("profile_identity", f"kapisch-{role}"),
        ("installed_sha256", installed_digest),
    )
    return "".join(f"{name}={toml_basic_string(value)}\n" for name, value in fields)


def _print_plan(plan: dict[str, Any], scope: str) -> None:
    print(f"profile={plan['target']}")
    print(f"scope={scope}")
    print(f"status={plan['status']}")
    print(f"desired_profile_set={plan['profile_set']}")
    if plan.get("installed_profile_set") is not None:
        print(f"installed_profile_set={plan['installed_profile_set']}")
    for key in ("expected_identity", "installed_identity", "template_digest", "installed_digest"):
        if plan.get(key) is not None:
            label = {"template_digest": "template_sha256", "installed_digest": "installed_sha256"}.get(key, key)
            print(f"{label}={plan[key]}")
    for key in ("drift", "template_drift", "error", "cleanup"):
        if plan.get(key) is not None:
            print(f"{key}={plan[key]}")
    for collision in plan.get("collision", ()):
        print(f"identity_collision={collision}")
    if plan["status"] == "verification-failed":
        print("action=committed transaction needs manual state repair; no profile set is claimed active")
    elif plan["status"] == "installed" and plan.get("cleanup"):
        print("action=committed profile set is active; rerun inspection to finish cleanup")
    elif plan["status"] == "installed" and plan.get("replaced_now"):
        print("action=managed profile replaced after identity and digest verification")
    elif plan["status"] == "installed" and plan.get("installed_now"):
        print("action=profile copied; no existing profile was overwritten")
    elif plan["status"] == "not-installed":
        print("action=rerun with --install after human review")
    elif plan["status"] == "installed" and plan.get("switch_required"):
        print("action=rerun with --install --replace-managed after human review")
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
        paths = sorted(path for path in agent_dir.iterdir() if path.suffix == ".toml")
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
        if path.stem in expected_names and values.get("name") != path.stem:
            failures.append((path, f"unexpected profile identity: {values.get('name')!r}"))
    return failures


def _prepare_role(
    *,
    root: Path,
    scope: str,
    role: str,
    install: bool,
    profile_set: str,
    replace_managed: bool,
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
        "profile_set": profile_set,
    }
    try:
        template_bytes = template.read_bytes()
        template_values = _parse_profile_bytes(template_bytes)
        desired_bytes = _render_profile_bytes(
            template_bytes, role=role, profile_set=profile_set
        )
        template_digest = hashlib.sha256(template_bytes).hexdigest()
        desired_digest = hashlib.sha256(desired_bytes).hexdigest()
    except (OSError, ProfileReadError) as exc:
        plan.update(status="collision", error=f"source template is unreadable or malformed: {exc}")
        return plan
    plan.update(
        template_digest=template_digest,
        desired_digest=desired_digest,
        template_bytes=desired_bytes,
        canonical_template_bytes=template_bytes,
    )
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
        if target.is_symlink():
            plan.update(status="collision", error="existing destination is a symbolic link")
            return plan
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
            record_bytes = record.read_bytes()
            saved = _parse_profile_bytes(record_bytes)
        except ProfileReadError as exc:
            plan.update(status="collision", error=f"state record is unreadable or malformed: {exc}")
            return plan
        except OSError as exc:
            plan.update(status="collision", error=f"state record is unreadable or malformed: {exc}")
            return plan
        if (
            saved.get("profile_identity") != expected_identity
            or saved.get("installed_profile") != str(target)
            or not _template_provenance_matches(saved.get("template"), template)
            or not isinstance(saved.get("installed_sha256"), str)
            or not isinstance(saved.get("template_sha256"), str)
        ):
            plan.update(
                status="collision",
                error="state record identity or template provenance cannot be verified",
            )
            return plan
        recorded_set = saved.get("profile_set")
        if recorded_set is None:
            quality_bytes = _render_profile_bytes(
                template_bytes, role=role, profile_set="quality"
            )
            quality_digest = hashlib.sha256(quality_bytes).hexdigest()
            if (
                saved.get("template_sha256") != template_digest
                or saved.get("installed_sha256") != quality_digest
            ):
                plan.update(
                    status="collision",
                    error="legacy state record does not match the verified quality profile",
                )
                return plan
            installed_profile_set = "quality"
        elif recorded_set in PROFILE_SET_CATALOG:
            installed_profile_set = recorded_set
        else:
            plan.update(status="collision", error="state record has an unknown profile set")
            return plan
        expected_model, expected_effort = PROFILE_SET_ROUTING[installed_profile_set][
            role
        ]
        if (
            installed_values.get("model"),
            installed_values.get("model_reasoning_effort"),
        ) != (expected_model, expected_effort):
            plan.update(
                status="collision",
                error="state record profile set does not match installed profile routing",
            )
            return plan
        plan.update(
            installed_profile_set=installed_profile_set,
            installed_bytes=installed_bytes,
            record_original_bytes=record_bytes,
        )
        plan["drift"] = "none" if saved.get("installed_sha256") == installed_digest else "user-modified"
        plan["template_drift"] = "none" if saved.get("template_sha256") == template_digest else "updated"
        if installed_profile_set != profile_set:
            plan["switch_required"] = True
            if install and replace_managed:
                if plan["drift"] != "none":
                    plan.update(
                        status="collision",
                        error="managed replacement refused because the installed profile drifted",
                    )
                    return plan
                try:
                    plan["record_bytes"] = _record_text(
                        template=template,
                        template_digest=template_digest,
                        target=target,
                        scope=scope,
                        role=role,
                        profile_set=profile_set,
                        installed_digest=desired_digest,
                    ).encode("utf-8")
                except (UnicodeError, ValueError) as exc:
                    plan.update(status="collision", error=f"state record cannot be encoded safely: {exc}")
                    return plan
                plan["status"] = "replace-pending"
                return plan
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
    try:
        plan["record_bytes"] = _record_text(
            template=template,
            template_digest=template_digest,
            target=target,
            scope=scope,
            role=role,
            profile_set=profile_set,
            installed_digest=desired_digest,
        ).encode("utf-8")
    except (UnicodeError, ValueError) as exc:
        plan.update(status="collision", error=f"state record cannot be encoded safely: {exc}")
        return plan
    plan["status"] = "install-pending" if install else "not-installed"
    return plan


def _write_exclusive(
    path: Path,
    contents: bytes,
    *,
    on_created: Callable[[], None] | None = None,
) -> None:
    stream = path.open("xb")
    if on_created is not None:
        on_created()
    with stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def _switch_journal_path(root: Path) -> Path:
    return root / ".kapisch" / "local-state" / "profile-switch.toml"


def _switch_prepare_path(root: Path) -> Path:
    return root / ".kapisch" / "local-state" / ".profile-switch.prepare.tmp"


def _switch_journal_text(status: str, entries: list[dict[str, Any]]) -> bytes:
    version = 2 if entries and all("recovery" in entry for entry in entries) else 1
    lines = [f"version={version}\n", f"status={toml_basic_string(status)}\n"]
    fields = (
        "role",
        "kind",
        "destination",
        "backup",
        "staged",
        "recovery",
        "original_sha256",
        "desired_sha256",
    )
    for entry in entries:
        lines.append("[[entries]]\n")
        for key in fields:
            if key in entry:
                lines.append(f"{key}={toml_basic_string(entry[key])}\n")
    return "".join(lines).encode("utf-8")


def _read_switch_journal(root: Path) -> tuple[str, list[dict[str, Any]]]:
    journal = _switch_journal_path(root)
    if journal.is_symlink():
        raise OSError("profile-switch journal is a symbolic link")
    values = _parse_profile_bytes(journal.read_bytes())
    version = values.get("version")
    if version not in {1, 2} or values.get("status") not in {"prepared", "committed"}:
        raise OSError("profile-switch journal has an unsupported version or status")
    entries = values.get("entries")
    if not isinstance(entries, list) or not entries:
        raise OSError("profile-switch journal has no entries")
    expected_fields = {
        "role",
        "kind",
        "destination",
        "backup",
        "staged",
        "original_sha256",
        "desired_sha256",
    }
    if version == 2:
        expected_fields.add("recovery")
    seen: set[tuple[str, str]] = set()
    checked: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != expected_fields:
            raise OSError("profile-switch journal entry has an invalid shape")
        if any(not isinstance(entry[key], str) or not entry[key] for key in expected_fields):
            raise OSError("profile-switch journal entry contains an invalid value")
        role = entry["role"]
        kind = entry["kind"]
        if role not in ROLE_CATALOG or kind not in {"profile", "state"}:
            raise OSError("profile-switch journal entry has an unknown role or kind")
        key = (role, kind)
        if key in seen:
            raise OSError("profile-switch journal contains a duplicate entry")
        seen.add(key)
        destination = (
            root / ".codex" / "agents" / f"kapisch-{role}.toml"
            if kind == "profile"
            else root / ".kapisch" / "local-state" / "profiles" / f"{role}.toml"
        )
        backup = destination.with_name(f".{destination.name}.kapisch-switch.bak")
        staged = destination.with_name(f".{destination.name}.kapisch-switch.tmp")
        if (
            entry["destination"] != str(destination)
            or entry["backup"] != str(backup)
            or entry["staged"] != str(staged)
        ):
            raise OSError("profile-switch journal paths cannot be verified")
        if version == 2:
            recovery = Path(entry["recovery"])
            prefix = f".{destination.name}.kapisch-switch.recover."
            suffix = ".tmp"
            token = recovery.name.removeprefix(prefix).removesuffix(suffix)
            if (
                recovery.parent != destination.parent
                or not recovery.name.startswith(prefix)
                or not recovery.name.endswith(suffix)
                or len(token) != 32
                or any(character not in "0123456789abcdef" for character in token)
            ):
                raise OSError("profile-switch recovery staging path cannot be verified")
        for digest_key in ("original_sha256", "desired_sha256"):
            digest_value = entry[digest_key]
            if len(digest_value) != 64 or any(
                character not in "0123456789abcdef" for character in digest_value
            ):
                raise OSError("profile-switch journal contains an invalid digest")
        checked.append(entry)
    return str(values["status"]), checked


def _path_digest(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()



def _remove_switch_artifact(path: Path) -> None:
    path.unlink()


def _recovery_staging_path(entry: dict[str, Any], destination: Path) -> Path:
    return Path(entry["recovery"]) if "recovery" in entry else destination.with_name(
        f".{destination.name}.kapisch-switch.recover.tmp"
    )

def _is_owned_recovery_staging(path: Path, contents: bytes) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        staging = path.read_bytes()
    except OSError:
        return False
    return len(staging) <= len(contents) and contents.startswith(staging)


def _write_recovery_staging(path: Path, contents: bytes) -> None:
    created = False

    def mark_created() -> None:
        nonlocal created
        created = True

    try:
        _write_exclusive(path, contents, on_created=mark_created)
    except BaseException:
        if created and _is_owned_recovery_staging(path, contents):
            try:
                _remove_switch_artifact(path)
            except OSError:
                pass
        raise


def _recover_interrupted_switch(root: Path) -> tuple[bool, str | None]:
    """Recover a prepared switch or finish cleanup for a committed switch."""
    journal = _switch_journal_path(root)
    if not journal.exists() and not journal.is_symlink():
        prepare = _switch_prepare_path(root)
        if prepare.exists() or prepare.is_symlink():
            try:
                _remove_switch_artifact(prepare)
            except OSError as exc:
                return False, f"incomplete switch preparation could not be removed: {exc}"
        return True, None
    try:
        status, entries = _read_switch_journal(root)
        if status == "prepared":
            preserved_external: dict[str, str] = {}
            for entry in entries:
                destination = Path(entry["destination"])
                destination_digest = _path_digest(destination)
                if destination_digest == entry["original_sha256"]:
                    continue
                if (
                    destination_digest is not None
                    and destination_digest != entry["desired_sha256"]
                ):
                    preserved_external[entry["destination"]] = destination_digest
                    continue
                backup = Path(entry["backup"])
                if _path_digest(backup) == entry["original_sha256"]:
                    continue
                else:
                    raise OSError(
                        f"cannot recover {destination}: verified original backup is unavailable"
                    )
            for entry in entries:
                destination = Path(entry["destination"])
                if entry["destination"] in preserved_external:
                    continue
                if _path_digest(destination) == entry["original_sha256"]:
                    continue
                backup = Path(entry["backup"])
                backup_bytes = backup.read_bytes()
                restore = _recovery_staging_path(entry, destination)
                if restore.exists() or restore.is_symlink():
                    if _path_digest(restore) != entry["original_sha256"]:
                        # Version-1 journals used this deterministic sibling path.
                        # A verified prefix of the authoritative backup is the
                        # legacy transaction's only staging identity; any other
                        # object remains fail-closed.
                        if not _is_owned_recovery_staging(restore, backup_bytes):
                            raise OSError(f"recovery staging path is unsafe: {restore}")
                        _remove_switch_artifact(restore)
                if not restore.exists() and not restore.is_symlink():
                    _write_recovery_staging(restore, backup_bytes)
                os.replace(restore, destination)
            for entry in entries:
                destination = Path(entry["destination"])
                expected_digest = preserved_external.get(
                    entry["destination"], entry["original_sha256"]
                )
                if _path_digest(destination) != expected_digest:
                    raise OSError(f"recovery verification failed: {destination}")
            for entry in entries:
                if "recovery" not in entry:
                    continue
                restore = _recovery_staging_path(entry, Path(entry["destination"]))
                if not restore.exists() and not restore.is_symlink():
                    continue
                backup_bytes = Path(entry["backup"]).read_bytes()
                if (
                    _path_digest(restore) != entry["original_sha256"]
                    and not _is_owned_recovery_staging(restore, backup_bytes)
                ):
                    raise OSError(f"recovery staging path is unsafe: {restore}")
                _remove_switch_artifact(restore)
        else:
            for entry in entries:
                destination = Path(entry["destination"])
                if _path_digest(destination) != entry["desired_sha256"]:
                    raise OSError(f"committed switch verification failed: {destination}")

        cleanup_paths = [
            Path(entry[key])
            for entry in entries
            for key in ("backup", "staged")
        ]
        cleanup_paths.append(journal.with_name(".profile-switch.commit.tmp"))
        cleanup_paths.append(_switch_prepare_path(root))
        for path in cleanup_paths:
            if path.exists() or path.is_symlink():
                _remove_switch_artifact(path)
        _remove_switch_artifact(journal)
    except (OSError, ProfileReadError, ValueError) as exc:
        return False, str(exc)
    return True, None


def _committed_destinations_match(root: Path) -> bool:
    """Whether a committed journal still describes the published catalog."""
    try:
        status, entries = _read_switch_journal(root)
    except (OSError, ProfileReadError, ValueError):
        return False
    return status == "committed" and all(
        _path_digest(Path(entry["destination"])) == entry["desired_sha256"]
        for entry in entries
    )


def _commit(plans: list[dict[str, Any]], *, root: Path) -> tuple[str, str | None]:
    """Install missing profiles or replace a managed catalog transactionally."""
    created: list[Path] = []
    created_directories: list[Path] = []
    staged: list[Path] = []
    backups: list[Path] = []
    switch_entries: list[dict[str, Any]] = []
    switch_committed = False
    original_by_destination: dict[Path, bytes] = {}
    desired_by_destination: dict[Path, bytes] = {}

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
            _write_exclusive(
                target,
                plan["template_bytes"],
                on_created=lambda target=target: created.append(target),
            )
            _write_exclusive(
                record,
                plan["record_bytes"],
                on_created=lambda record=record: created.append(record),
            )
        replacement_plans = [plan for plan in plans if plan["status"] == "replace-pending"]
        for plan in replacement_plans:
            if (
                plan["target"].read_bytes() != plan["installed_bytes"]
                or plan["record"].read_bytes() != plan["record_original_bytes"]
            ):
                raise OSError("managed profile or state changed after preflight")
        for plan in replacement_plans:
            for kind, destination, original, contents in (
                (
                    "profile",
                    plan["target"],
                    plan["installed_bytes"],
                    plan["template_bytes"],
                ),
                (
                    "state",
                    plan["record"],
                    plan["record_original_bytes"],
                    plan["record_bytes"],
                ),
            ):
                backup = destination.with_name(
                    f".{destination.name}.kapisch-switch.bak"
                )
                candidate = destination.with_name(
                    f".{destination.name}.kapisch-switch.tmp"
                )
                recovery = destination.with_name(
                    f".{destination.name}.kapisch-switch.recover.{secrets.token_hex(16)}.tmp"
                )
                if (
                    backup.exists()
                    or backup.is_symlink()
                    or candidate.exists()
                    or candidate.is_symlink()
                    or recovery.exists()
                    or recovery.is_symlink()
                ):
                    raise OSError(f"switch staging path already exists for {destination}")
                original_by_destination[destination] = original
                desired_by_destination[destination] = contents
                switch_entries.append(
                    {
                        "role": plan["role"],
                        "kind": kind,
                        "destination": str(destination),
                        "backup": str(backup),
                        "staged": str(candidate),
                        "recovery": str(recovery),
                        "original_sha256": hashlib.sha256(original).hexdigest(),
                        "desired_sha256": hashlib.sha256(contents).hexdigest(),
                    }
                )
        journal = _switch_journal_path(root)
        if switch_entries:
            prepare = _switch_prepare_path(root)
            if (
                journal.exists()
                or journal.is_symlink()
                or prepare.exists()
                or prepare.is_symlink()
            ):
                raise OSError("profile-switch journal or preparation path already exists")
            _write_exclusive(
                prepare,
                _switch_journal_text("prepared", switch_entries),
            )
            os.replace(prepare, journal)
            for entry in switch_entries:
                destination = Path(entry["destination"])
                candidate = Path(entry["staged"])
                backup = Path(entry["backup"])
                original = original_by_destination[destination]
                _write_exclusive(candidate, desired_by_destination[destination])
                staged.append(candidate)
                if _path_digest(destination) != entry["original_sha256"]:
                    raise OSError("managed profile or state changed before backup")
                os.link(destination, backup, follow_symlinks=False)
                backups.append(backup)
                if _path_digest(backup) != hashlib.sha256(original).hexdigest():
                    raise OSError("managed profile or state changed while creating backup")
            for entry in switch_entries:
                destination = Path(entry["destination"])
                if _path_digest(destination) != entry["original_sha256"]:
                    raise OSError("managed profile or state changed before replacement")
                os.replace(Path(entry["staged"]), destination)
                backup_digest = _path_digest(Path(entry["backup"]))
                if backup_digest != entry["original_sha256"]:
                    if backup_digest is None:
                        raise OSError("managed profile or state backup became unavailable")
                    entry["original_sha256"] = backup_digest
                    update_candidate = journal.with_name(".profile-switch.commit.tmp")
                    _write_exclusive(
                        update_candidate,
                        _switch_journal_text("prepared", switch_entries),
                    )
                    os.replace(update_candidate, journal)
                    raise OSError("managed profile or state changed during replacement")
            for entry in switch_entries:
                if _path_digest(Path(entry["destination"])) != entry["desired_sha256"]:
                    raise OSError("managed profile or state replacement failed verification")
            agent_dir = root / ".codex" / "agents"
            targets = {plan["target"] for plan in replacement_plans}
            adjacent_failures = _adjacent_errors(
                agent_dir,
                expected_names={f"kapisch-{role}" for role in ROLE_CATALOG},
                targets=targets,
            )
            collisions = [
                collision
                for plan in replacement_plans
                for collision in identity_collisions(
                    agent_dir, plan["expected_identity"], plan["target"]
                )
            ]
            if adjacent_failures or collisions:
                raise OSError("agent catalog changed during managed replacement")
            commit_candidate = journal.with_name(".profile-switch.commit.tmp")
            _write_exclusive(
                commit_candidate,
                _switch_journal_text("committed", switch_entries),
            )
            os.replace(commit_candidate, journal)
            switch_committed = True
            recovered, recovery_error = _recover_interrupted_switch(root)
            if not recovered:
                raise OSError(f"committed switch cleanup failed: {recovery_error}")
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        durably_committed = switch_committed
        if not durably_committed:
            journal = _switch_journal_path(root)
            if journal.exists() or journal.is_symlink():
                try:
                    journal_status, _ = _read_switch_journal(root)
                    durably_committed = journal_status == "committed"
                except (OSError, ProfileReadError, ValueError):
                    pass
        recovered, recovery_error = _recover_interrupted_switch(root)
        journal = _switch_journal_path(root)
        if not journal.exists() and not journal.is_symlink():
            for path in staged:
                try:
                    if path.exists() or path.is_symlink():
                        path.unlink()
                except OSError:
                    pass
            for path in backups:
                try:
                    if path.exists() or path.is_symlink():
                        path.unlink()
                except OSError:
                    pass
            for path in reversed(created):
                try:
                    path.unlink()
                except OSError:
                    pass
            for directory in sorted(
                set(created_directories), key=lambda path: len(path.parts), reverse=True
            ):
                try:
                    directory.rmdir()
                except OSError:
                    pass
        if durably_committed:
            if recovered:
                return "complete", None
            detail = str(exc)
            if recovery_error:
                detail = f"{detail}; recovery failed: {recovery_error}"
            if _committed_destinations_match(root):
                return "cleanup-pending", detail
            return "verification-failed", detail
        detail = str(exc)
        if not recovered:
            detail = f"{detail}; recovery failed: {recovery_error}"
        return "rolled-back", detail
    return "complete", None


def _process_is_alive(pid: int) -> bool:
    if pid <= 0 or pid > 0xFFFFFFFF:
        raise ValueError("profile-switch lock PID is out of range")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        error_access_denied = 5
        error_invalid_parameter = 87
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == error_invalid_parameter:
                return False
            if error == error_access_denied:
                return True
            raise ctypes.WinError(error)
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                raise ctypes.WinError(ctypes.get_last_error())
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def _switch_lock(root: Path, *, create: bool) -> Iterator[None]:
    state_dir = root / ".kapisch" / "local-state"
    if not state_dir.is_dir():
        if not create:
            yield
            return
        created_directories: list[Path] = []
        missing: list[Path] = []
        current = state_dir
        while not current.exists():
            missing.append(current)
            current = current.parent
        if not current.is_dir():
            raise OSError(f"profile setup lock parent is not a directory: {current}")
        for directory in reversed(missing):
            try:
                directory.mkdir()
            except FileExistsError:
                if not directory.is_dir():
                    raise
            else:
                created_directories.append(directory)
    else:
        created_directories = []
    lock = state_dir / "profile-switch.lock"
    current_pid = os.getpid()
    try:
        _write_exclusive(lock, f"pid={current_pid}\n".encode("ascii"))
    except FileExistsError:
        if lock.is_symlink():
            raise OSError("profile-switch lock is a symbolic link")
        try:
            contents = lock.read_text(encoding="ascii")
            saved_pid = int(contents.removeprefix("pid=").strip())
            if saved_pid <= 0 or saved_pid > 0xFFFFFFFF:
                raise ValueError("PID is out of range")
        except (OSError, OverflowError, UnicodeError, ValueError) as exc:
            raise OSError(f"profile-switch lock cannot be verified: {exc}") from exc
        if _process_is_alive(saved_pid):
            raise OSError(f"another profile setup process is active with pid {saved_pid}")
        lock.unlink()
        _write_exclusive(lock, f"pid={current_pid}\n".encode("ascii"))
    try:
        yield
    finally:
        try:
            if not lock.is_symlink() and lock.read_text(encoding="ascii") == f"pid={current_pid}\n":
                lock.unlink()
        except OSError:
            pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass


def _switch_recovery_needed(root: Path) -> bool:
    return (
        _switch_journal_path(root).exists()
        or _switch_journal_path(root).is_symlink()
        or _switch_prepare_path(root).exists()
        or _switch_prepare_path(root).is_symlink()
    )


def _run_setup(
    args: argparse.Namespace,
    root: Path,
    *,
    allow_recovery: bool,
) -> int:
    recovery_needed = _switch_recovery_needed(root)
    if recovery_needed and not allow_recovery:
        print("status=collision")
        print("error=interrupted managed switch requires serialized recovery")
        print("action=rerun inspection to recover the interrupted transaction")
        return 2
    if allow_recovery:
        recovered, recovery_error = _recover_interrupted_switch(root)
        if not recovered:
            print("status=collision")
            print(f"error=interrupted managed switch could not be recovered: {recovery_error}")
            print("action=review local state; no new profile operation was attempted")
            return 2
        if recovery_needed:
            print("recovery=completed interrupted managed-profile transaction")
    roles = list(ROLE_CATALOG if args.all else (args.role,))
    agent_dir = root / ".codex" / "agents"
    targets = {agent_dir / f"kapisch-{role}.toml" for role in roles}
    adjacent_failures = _adjacent_errors(
        agent_dir,
        expected_names={f"kapisch-{role}" for role in ROLE_CATALOG},
        targets=targets,
    )
    plans = [
        _prepare_role(
            root=root,
            scope=args.scope,
            role=role,
            install=args.install,
            profile_set=args.profile_set,
            replace_managed=args.replace_managed,
            adjacent_failures=adjacent_failures,
        )
        for role in roles
    ]
    for plan in plans:
        plan["scope"] = args.scope

    if args.install and args.all:
        missing = [plan for plan in plans if plan["status"] == "install-pending"]
        switching = [plan for plan in plans if plan.get("switch_required")]
        if missing and switching:
            for plan in plans:
                if plan["status"] != "collision":
                    plan.update(
                        status="collision",
                        error=(
                            "complete-catalog operation refused because it would mix "
                            "new installation and managed switching"
                        ),
                    )

    failures = [plan for plan in plans if plan["status"] == "collision"]
    cleanup_pending = False
    if args.install and not failures:
        commit_outcome, error = _commit(plans, root=root)
        if commit_outcome == "rolled-back":
            for plan in plans:
                if plan["status"] in {"install-pending", "replace-pending"}:
                    plan.update(
                        status="collision",
                        error=f"catalog installation rolled back: {error}",
                    )
            failures = [plan for plan in plans if plan["status"] == "collision"]
        elif commit_outcome == "verification-failed":
            for plan in plans:
                if plan["status"] in {"install-pending", "replace-pending"}:
                    plan.pop("installed_profile_set", None)
                    plan.update(
                        status="verification-failed",
                        error=f"committed switch verification failed: {error}",
                    )
            cleanup_pending = True
        else:
            for plan in plans:
                if plan["status"] in {"install-pending", "replace-pending"}:
                    was_replacement = plan["status"] == "replace-pending"
                    plan["status"] = "installed"
                    plan["installed_now"] = not was_replacement
                    plan["replaced_now"] = was_replacement
                    plan["installed_profile_set"] = plan["profile_set"]
                    plan["installed_digest"] = digest(plan["target"])
                    if commit_outcome == "cleanup-pending":
                        plan["cleanup"] = f"committed switch cleanup pending: {error}"
            cleanup_pending = commit_outcome == "cleanup-pending"

    for plan in plans:
        _print_plan(plan, args.scope)
    return 2 if failures or cleanup_pending else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--role", choices=ROLE_CATALOG)
    selector.add_argument("--all", action="store_true", help="install the complete six-role catalog atomically")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--user-dir", type=Path, default=Path.home(), help="user home for --scope user")
    parser.add_argument(
        "--profile-set",
        choices=PROFILE_SET_CATALOG,
        default="balanced",
        help="Codex model/reasoning configuration to render (default: balanced)",
    )
    parser.add_argument("--install", action="store_true")
    parser.add_argument(
        "--replace-managed",
        action="store_true",
        help="explicitly replace verified KAPISCH-managed profiles during --install",
    )
    args = parser.parse_args(argv)
    if args.replace_managed and not args.install:
        parser.error("--replace-managed requires --install")

    root = (args.project_dir if args.scope == "project" else args.user_dir).resolve()
    try:
        recovery_needed = _switch_recovery_needed(root)
        if not args.install and not recovery_needed:
            return _run_setup(args, root, allow_recovery=False)
        with _switch_lock(root, create=args.install):
            return _run_setup(args, root, allow_recovery=True)
    except OSError as exc:
        print("status=collision")
        print(f"error=profile setup lock failed: {exc}")
        print("action=review local state; no new profile operation was attempted")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
