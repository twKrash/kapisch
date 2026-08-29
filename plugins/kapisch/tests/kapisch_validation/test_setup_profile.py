from __future__ import annotations

import hashlib
import os
import shutil
import tomllib
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import scripts.setup_profile as setup_profile


class SetupProfileSafetyTests(unittest.TestCase):
    def test_windows_style_paths_are_toml_safe(self) -> None:
        path = r"C:\Users\Example User\.codex\agents\kapisch-reviewer.toml"
        encoded = setup_profile.toml_basic_string(path)
        self.assertEqual(tomllib.loads(f"installed_profile={encoded}")["installed_profile"], path)

    def test_non_ascii_paths_are_toml_safe(self) -> None:
        path = "C:\\Users\\Élodie\\プロジェクト\\.codex\\agents\\kapisch-reviewer.toml"
        encoded = setup_profile.toml_basic_string(path)
        self.assertEqual(tomllib.loads(f"installed_profile={encoded}")["installed_profile"], path)

    def test_unpaired_surrogate_path_fails_before_installation(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary) / "project-\udcff"
            output = io.StringIO()
            with redirect_stdout(output):
                result = setup_profile.main(
                    ["--role", "reviewer", "--project-dir", str(project), "--install"]
                )
            self.assertEqual(result, 2)
            self.assertIn("error=state record cannot be encoded safely", output.getvalue())
            self.assertFalse(project.exists())

    def test_non_selected_canonical_profile_with_wrong_identity_blocks_install(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            adjacent = project / ".codex/agents/kapisch-architect.toml"
            adjacent.parent.mkdir(parents=True)
            adjacent.write_text('name = "wrong"\n', encoding="utf-8")
            before = adjacent.read_bytes()

            result = setup_profile.main(
                ["--role", "reviewer", "--project-dir", str(project), "--install"]
            )

            self.assertEqual(result, 2)
            self.assertEqual(adjacent.read_bytes(), before)
            self.assertFalse((adjacent.parent / "kapisch-reviewer.toml").exists())

    def test_adjacent_directory_enumeration_failure_blocks_install(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            agent_dir = (project / ".codex/agents").resolve()
            agent_dir.mkdir(parents=True)
            original_iterdir = Path.iterdir

            def unreadable_directory(path: Path):
                if path == agent_dir:
                    raise OSError("simulated enumeration failure")
                return original_iterdir(path)

            output = io.StringIO()
            with (
                mock.patch.object(Path, "iterdir", autospec=True, side_effect=unreadable_directory),
                redirect_stdout(output),
            ):
                result = setup_profile.main(
                    ["--role", "reviewer", "--project-dir", str(project), "--install"]
                )

            self.assertEqual(result, 2)
            self.assertIn("error=adjacent profile safety check failed", output.getvalue())
            self.assertIn("agent directory is unreadable", output.getvalue())
            self.assertFalse((agent_dir / "kapisch-reviewer.toml").exists())

    def test_template_filename_with_wrong_internal_name_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "agents"
            source.mkdir()
            template = source / "kapisch-reviewer.toml"
            template.write_text('name = "someone-else"\n', encoding="utf-8")
            project = Path(temporary) / "project"
            with mock.patch.object(setup_profile, "AGENT_DIR", source):
                self.assertEqual(setup_profile.main(["--role", "reviewer", "--project-dir", str(project), "--install"]), 2)
            self.assertFalse((project / ".codex/agents/kapisch-reviewer.toml").exists())

    def test_template_is_validated_from_the_same_single_read_that_is_installed(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "agents"
            source.mkdir()
            template = source / "kapisch-reviewer.toml"
            valid = (
                b'name = "kapisch-reviewer"\n'
                b'description = "test"\n'
                b'developer_instructions = "test"\n'
                b'model = "gpt-5.6-sol"\n'
                b'model_reasoning_effort = "high"\n'
            )
            wrong = b'name = "someone-else"\n'
            template.write_bytes(valid)
            project = Path(temporary) / "project"
            original_read_bytes = Path.read_bytes
            reads = 0

            def changing_read(path: Path) -> bytes:
                nonlocal reads
                if path == template:
                    reads += 1
                    return valid if reads == 1 else wrong
                return original_read_bytes(path)

            with (
                mock.patch.object(setup_profile, "AGENT_DIR", source),
                mock.patch.object(Path, "read_bytes", autospec=True, side_effect=changing_read),
            ):
                self.assertEqual(
                    setup_profile.main(
                        ["--role", "reviewer", "--project-dir", str(project), "--install"]
                        + ["--profile-set", "quality"]
                    ),
                    0,
                )
            self.assertEqual(reads, 1)
            self.assertEqual(
                (project / ".codex/agents/kapisch-reviewer.toml").read_bytes(), valid
            )

    def test_malformed_existing_destination_is_not_changed(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = project / ".codex/agents/kapisch-reviewer.toml"
            target.parent.mkdir(parents=True)
            target.write_text('name = [\n', encoding="utf-8")
            before = target.read_bytes()
            self.assertEqual(setup_profile.main(["--role", "reviewer", "--project-dir", str(project), "--install"]), 2)
            self.assertEqual(target.read_bytes(), before)

    def test_existing_destination_identity_and_digest_share_one_read(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(
                setup_profile.main(
                    ["--role", "reviewer", "--project-dir", str(project), "--install"]
                ),
                0,
            )
            target = (project / ".codex/agents/kapisch-reviewer.toml").resolve()
            actual = target.read_bytes()
            wrong_identity = b'name = "someone-else"\n'
            original_read_bytes = Path.read_bytes
            reads = 0

            def changing_read(path: Path) -> bytes:
                nonlocal reads
                if path == target:
                    reads += 1
                    return wrong_identity if reads == 1 else actual
                return original_read_bytes(path)

            output = io.StringIO()
            with (
                mock.patch.object(Path, "read_bytes", autospec=True, side_effect=changing_read),
                redirect_stdout(output),
            ):
                result = setup_profile.main(
                    ["--role", "reviewer", "--project-dir", str(project), "--install"]
                )
            self.assertEqual(result, 2)
            self.assertEqual(reads, 1)
            self.assertIn("status=collision", output.getvalue())
            self.assertEqual(target.read_bytes(), actual)

    def test_unreadable_existing_destination_is_not_changed(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = (project / ".codex/agents/kapisch-reviewer.toml").resolve()
            target.parent.mkdir(parents=True)
            target.write_text('name = "kapisch-reviewer"\n', encoding="utf-8")
            original_read_bytes = Path.read_bytes

            def unreadable(path: Path) -> bytes:
                if path == target:
                    raise OSError("simulated access failure")
                return original_read_bytes(path)

            output = io.StringIO()
            with (
                mock.patch.object(Path, "read_bytes", autospec=True, side_effect=unreadable),
                redirect_stdout(output),
            ):
                result = setup_profile.main(
                    ["--role", "reviewer", "--project-dir", str(project), "--install"]
                )
            self.assertEqual(result, 2)
            self.assertEqual(target.read_text(encoding="utf-8"), 'name = "kapisch-reviewer"\n')
            self.assertIn("error=existing destination is unreadable or malformed", output.getvalue())

    def test_complete_role_catalog_installs(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(setup_profile.main(["--all", "--project-dir", str(project), "--install"]), 0)
            self.assertEqual(len(list((project / ".codex/agents").glob("*.toml"))), 6)
            self.assertEqual(len(list((project / ".kapisch/local-state/profiles").glob("*.toml"))), 6)

    def test_interleaved_initial_install_is_blocked_by_the_setup_lock(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = (project / ".codex/agents/kapisch-architect.toml").resolve()
            original_write_exclusive = setup_profile._write_exclusive
            nested_results: list[int] = []

            def interleave(path: Path, contents: bytes, **kwargs):
                if path == target and not nested_results:
                    nested_results.append(
                        setup_profile.main(
                            ["--all", "--project-dir", str(project), "--install"]
                        )
                    )
                return original_write_exclusive(path, contents, **kwargs)

            with mock.patch.object(
                setup_profile,
                "_write_exclusive",
                side_effect=interleave,
            ):
                self.assertEqual(
                    setup_profile.main(
                        ["--all", "--project-dir", str(project), "--install"]
                    ),
                    0,
                )

            self.assertEqual(nested_results, [2])
            self.assertEqual(len(list((project / ".codex/agents").glob("*.toml"))), 6)
            self.assertEqual(
                len(list((project / ".kapisch/local-state/profiles").glob("*.toml"))),
                6,
            )

    def test_lost_exclusive_create_does_not_remove_the_other_writer_file(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = (project / ".codex/agents/kapisch-architect.toml").resolve()
            external = b'name = "external-writer"\n'
            original_write_exclusive = setup_profile._write_exclusive

            def lose_create(path: Path, contents: bytes, **kwargs):
                if path == target:
                    path.write_bytes(external)
                    raise FileExistsError("simulated concurrent exclusive create")
                return original_write_exclusive(path, contents, **kwargs)

            with mock.patch.object(
                setup_profile,
                "_write_exclusive",
                side_effect=lose_create,
            ):
                self.assertEqual(
                    setup_profile.main(
                        ["--all", "--project-dir", str(project), "--install"]
                    ),
                    2,
                )

            self.assertEqual(target.read_bytes(), external)
            self.assertFalse(
                (project / ".kapisch/local-state/profiles/architect.toml").exists()
            )

    def test_second_identical_catalog_run_is_idempotent(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(setup_profile.main(["--all", "--project-dir", str(project), "--install"]), 0)
            files = sorted(path for path in project.rglob("*") if path.is_file())
            before = {path.relative_to(project): hashlib.sha256(path.read_bytes()).digest() for path in files}
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(setup_profile.main(["--all", "--project-dir", str(project), "--install"]), 0)
            after = {path.relative_to(project): hashlib.sha256(path.read_bytes()).digest() for path in files}
            self.assertEqual(before, after)
            self.assertIn("action=review; profile was not changed", output.getvalue())
            self.assertNotIn("action=profile copied", output.getvalue())

    def test_invalid_catalog_template_prevents_partial_installation(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "agents"
            source.mkdir()
            original = setup_profile.AGENT_DIR
            for role in setup_profile.ROLE_CATALOG:
                shutil.copyfile(original / f"kapisch-{role}.toml", source / f"kapisch-{role}.toml")
            (source / "kapisch-reviewer.toml").write_text('name = "wrong"\n', encoding="utf-8")
            project = Path(temporary) / "project"
            with mock.patch.object(setup_profile, "AGENT_DIR", source):
                self.assertEqual(setup_profile.main(["--all", "--project-dir", str(project), "--install"]), 2)
            self.assertFalse((project / ".codex").exists())
            self.assertFalse((project / ".kapisch").exists())

    def test_partial_write_failure_removes_files_and_new_directories(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = (project / ".codex/agents/kapisch-reviewer.toml").resolve()
            original_open = Path.open

            class PartialWrite:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_value, traceback):
                    self.stream.close()
                    return False

                def write(self, contents):
                    self.stream.write(contents[:1])
                    raise OSError("simulated mid-write failure")

            def failing_open(path: Path, mode="r", *args, **kwargs):
                stream = original_open(path, mode, *args, **kwargs)
                return PartialWrite(stream) if path == target and mode == "xb" else stream

            with mock.patch.object(Path, "open", autospec=True, side_effect=failing_open):
                self.assertEqual(
                    setup_profile.main(
                        ["--role", "reviewer", "--project-dir", str(project), "--install"]
                    ),
                    2,
                )
            self.assertFalse(target.exists())
            self.assertFalse((project / ".kapisch/local-state/profiles/reviewer.toml").exists())
            self.assertFalse((project / ".codex").exists())
            self.assertFalse((project / ".kapisch").exists())

    def test_close_failure_after_exclusive_creation_is_rolled_back(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            target = (project / ".codex/agents/kapisch-reviewer.toml").resolve()
            original_open = Path.open

            class CloseFailure:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self.stream

                def __exit__(self, exc_type, exc_value, traceback):
                    self.stream.close()
                    raise OSError("simulated close failure")

            def failing_open(path: Path, mode="r", *args, **kwargs):
                stream = original_open(path, mode, *args, **kwargs)
                return CloseFailure(stream) if path == target and mode == "xb" else stream

            with mock.patch.object(Path, "open", autospec=True, side_effect=failing_open):
                self.assertEqual(
                    setup_profile.main(
                        ["--role", "reviewer", "--project-dir", str(project), "--install"]
                    ),
                    2,
                )
            self.assertFalse(target.exists())
            self.assertFalse((project / ".kapisch/local-state/profiles/reviewer.toml").exists())
            self.assertFalse((project / ".codex").exists())
            self.assertFalse((project / ".kapisch").exists())

    def test_directory_creation_failure_rolls_back_intermediate_parents(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary) / "new-project"
            original_mkdir = Path.mkdir

            def failing_mkdir(path: Path, mode=0o777, parents=False, exist_ok=False):
                if path.name == "codex":
                    original_mkdir(path, mode, parents, exist_ok)
                    raise OSError("simulated post-create directory failure")
                if path.name == "agents":
                    raise OSError("simulated directory creation failure")
                return original_mkdir(path, mode, parents, exist_ok)

            with mock.patch.object(Path, "mkdir", autospec=True, side_effect=failing_mkdir):
                self.assertEqual(
                    setup_profile.main(
                        ["--role", "reviewer", "--project-dir", str(project), "--install"]
                    ),
                    2,
                )
            self.assertFalse(project.exists())
            self.assertFalse(project.parent.joinpath(".codex").exists())
            self.assertFalse(project.parent.joinpath(".kapisch").exists())


class ProfileSetTests(unittest.TestCase):
    EXPECTED_ROUTING = {
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

    def _install(self, project: Path, profile_set: str | None = None) -> int:
        argv = ["--all", "--project-dir", str(project)]
        if profile_set is not None:
            argv.extend(("--profile-set", profile_set))
        argv.append("--install")
        return setup_profile.main(argv)

    def _snapshot(self, project: Path) -> dict[Path, bytes]:
        return {
            path.relative_to(project): path.read_bytes()
            for path in sorted(project.rglob("*"))
            if path.is_file()
        }

    def test_default_install_uses_balanced_and_records_the_set(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project), 0)
            researcher = tomllib.loads(
                (project / ".codex/agents/kapisch-researcher.toml").read_text(
                    encoding="utf-8"
                )
            )
            state = tomllib.loads(
                (project / ".kapisch/local-state/profiles/researcher.toml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(researcher["model"], "gpt-5.6-terra")
            self.assertEqual(researcher["model_reasoning_effort"], "medium")
            self.assertEqual(state["profile_set"], "balanced")
            self.assertEqual(
                state["template_sha256"],
                hashlib.sha256(
                    (setup_profile.AGENT_DIR / "kapisch-researcher.toml").read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                state["installed_sha256"],
                hashlib.sha256(
                    (project / ".codex/agents/kapisch-researcher.toml").read_bytes()
                ).hexdigest(),
            )

    def test_each_profile_set_installs_the_exact_six_role_routing_matrix(self) -> None:
        canonical_instructions = {
            role: tomllib.loads(
                (setup_profile.AGENT_DIR / f"kapisch-{role}.toml").read_text(
                    encoding="utf-8"
                )
            )["developer_instructions"]
            for role in setup_profile.ROLE_CATALOG
        }
        for profile_set, expected in self.EXPECTED_ROUTING.items():
            with self.subTest(profile_set=profile_set), TemporaryDirectory() as temporary:
                project = Path(temporary)
                self.assertEqual(self._install(project, profile_set), 0)
                profiles = sorted((project / ".codex/agents").glob("*.toml"))
                self.assertEqual(len(profiles), 6)
                for role, (model, effort) in expected.items():
                    values = tomllib.loads(
                        (project / f".codex/agents/kapisch-{role}.toml").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertEqual(values["name"], f"kapisch-{role}")
                    self.assertEqual(values["model"], model)
                    self.assertEqual(values["model_reasoning_effort"], effort)
                    self.assertEqual(
                        values["developer_instructions"], canonical_instructions[role]
                    )

    def test_profile_set_inspection_does_not_create_a_consumer(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary) / "consumer"
            self.assertEqual(
                setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "budget",
                    ]
                ),
                0,
            )
            self.assertFalse(project.exists())

    def test_managed_state_inspection_is_read_only_without_recovery(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            state_dir = project / ".kapisch/local-state"
            state_dir.chmod(0o555)
            try:
                with mock.patch.object(
                    setup_profile,
                    "_write_exclusive",
                    side_effect=AssertionError("inspection attempted a filesystem write"),
                ):
                    self.assertEqual(
                        setup_profile.main(
                            ["--all", "--project-dir", str(project)]
                        ),
                        0,
                    )
            finally:
                state_dir.chmod(0o755)
            self.assertEqual(self._snapshot(project), before)

    def test_managed_switch_requires_explicit_replace_and_updates_all_state(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(self._install(project, "budget"), 0)
            self.assertEqual(self._snapshot(project), before)
            self.assertIn("rerun with --install --replace-managed", output.getvalue())

            self.assertEqual(
                setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "budget",
                        "--install",
                        "--replace-managed",
                    ]
                ),
                0,
            )
            for role, (model, effort) in self.EXPECTED_ROUTING["budget"].items():
                profile = tomllib.loads(
                    (project / f".codex/agents/kapisch-{role}.toml").read_text(
                        encoding="utf-8"
                    )
                )
                state = tomllib.loads(
                    (project / f".kapisch/local-state/profiles/{role}.toml").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual((profile["model"], profile["model_reasoning_effort"]), (model, effort))
                self.assertEqual(state["profile_set"], "budget")
                self.assertEqual(
                    state["installed_sha256"],
                    hashlib.sha256(
                        (project / f".codex/agents/kapisch-{role}.toml").read_bytes()
                    ).hexdigest(),
                )

    def test_switch_refuses_a_user_modified_managed_profile(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            target = project / ".codex/agents/kapisch-reviewer.toml"
            target.write_text(target.read_text(encoding="utf-8") + "# local change\n", encoding="utf-8")
            before = self._snapshot(project)
            output = io.StringIO()
            with redirect_stdout(output):
                result = setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertEqual(self._snapshot(project), before)
            self.assertIn("drift=user-modified", output.getvalue())

    def test_failed_catalog_switch_restores_every_profile_and_state_byte(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            original_replace = setup_profile.os.replace
            calls = 0

            def fail_once(source, destination):
                nonlocal calls
                calls += 1
                if calls == 7:
                    raise OSError("simulated catalog switch interruption")
                return original_replace(source, destination)

            with mock.patch.object(setup_profile.os, "replace", side_effect=fail_once):
                result = setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertEqual(self._snapshot(project), before)

    def test_concurrent_profile_change_is_detected_and_preserved(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            expected = self._snapshot(project)
            target = project / ".codex/agents/kapisch-architect.toml"
            changed = target.read_bytes() + b"# concurrent user change\n"
            expected[target.relative_to(project)] = changed
            original_replace = setup_profile.os.replace
            first_replace = True

            def change_before_first_replace(source, destination):
                nonlocal first_replace
                if first_replace:
                    first_replace = False
                    target.write_bytes(changed)
                return original_replace(source, destination)

            with mock.patch.object(
                setup_profile.os,
                "replace",
                side_effect=change_before_first_replace,
            ):
                result = setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertEqual(self._snapshot(project), expected)

    def test_failed_backup_cleanup_finishes_the_committed_switch(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            original_unlink = Path.unlink
            backup_cleanup_calls = 0

            def fail_after_one_backup_cleanup(path: Path, *args, **kwargs):
                nonlocal backup_cleanup_calls
                if path.name.endswith(".bak"):
                    backup_cleanup_calls += 1
                    if backup_cleanup_calls == 2:
                        raise OSError("simulated backup cleanup failure")
                return original_unlink(path, *args, **kwargs)

            with mock.patch.object(
                Path,
                "unlink",
                autospec=True,
                side_effect=fail_after_one_backup_cleanup,
            ):
                result = setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertNotEqual(self._snapshot(project), before)
            for role, (model, effort) in self.EXPECTED_ROUTING["quality"].items():
                profile = tomllib.loads(
                    (project / f".codex/agents/kapisch-{role}.toml").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    (profile["model"], profile["model_reasoning_effort"]),
                    (model, effort),
                )
            self.assertFalse(
                (project / ".kapisch/local-state/profile-switch.toml").exists()
            )

    def test_persistent_cleanup_denial_reports_committed_set_and_recovers(self) -> None:
        for initial_set, target_set, denied_kind in (
            (initial_set, target_set, denied_kind)
            for initial_set, target_set in (
                ("balanced", "quality"),
                ("quality", "budget"),
                ("budget", "quality"),
            )
            for denied_kind in ("backup", "staging", "temporary", "prepare", "journal")
        ):
            with self.subTest(
                initial_set=initial_set,
                target_set=target_set,
                denied_kind=denied_kind,
            ), TemporaryDirectory() as temporary:
                project = Path(temporary).resolve()
                self.assertEqual(self._install(project, initial_set), 0)
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            target_set,
                            "--install",
                            "--replace-managed",
                        ]
                    ),
                    0,
                )
                journal = project / ".kapisch/local-state/profile-switch.toml"
                destination = project / ".codex/agents/kapisch-architect.toml"
                backup = destination.with_name(
                    f".{destination.name}.kapisch-switch.bak"
                )
                staged = destination.with_name(
                    f".{destination.name}.kapisch-switch.tmp"
                )
                commit_temporary = journal.with_name(".profile-switch.commit.tmp")
                prepare = journal.with_name(".profile-switch.prepare.tmp")
                artifacts = {
                    "backup": backup,
                    "staging": staged,
                    "temporary": commit_temporary,
                    "prepare": prepare,
                    "journal": journal,
                }
                denied_path = artifacts[denied_kind]
                if denied_kind != "journal":
                    denied_path.write_bytes(b"leftover switch artifact")
                destination_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
                setup_profile._write_exclusive(
                    journal,
                    setup_profile._switch_journal_text(
                        "committed",
                        [
                            {
                                "role": "architect",
                                "kind": "profile",
                                "destination": str(destination),
                                "backup": str(backup),
                                "staged": str(staged),
                                "original_sha256": destination_digest,
                                "desired_sha256": destination_digest,
                            }
                        ],
                    ),
                )
                original_remove_switch_artifact = setup_profile._remove_switch_artifact
                unlink_paths: list[str] = []

                def normalized_path(path: Path | str) -> str:
                    return os.path.normcase(os.path.abspath(os.fspath(path)))

                def deny_selected_cleanup(path: Path) -> None:
                    normalized = normalized_path(path)
                    unlink_paths.append(normalized)
                    if normalized == normalized_path(denied_path):
                        raise OSError(f"persistent {denied_kind} cleanup denial")
                    original_remove_switch_artifact(path)

                output = io.StringIO()
                with (
                    mock.patch.object(
                        setup_profile,
                        "_remove_switch_artifact",
                        side_effect=deny_selected_cleanup,
                    ),
                    redirect_stdout(output),
                ):
                    result = setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            target_set,
                        ]
                    )

                self.assertEqual(result, 2)
                self.assertIn(normalized_path(denied_path), unlink_paths)
                self.assertIn("status=collision", output.getvalue())
                self.assertIn(
                    "interrupted managed switch could not be recovered",
                    output.getvalue(),
                )
                self.assertTrue(journal.exists())
                self.assertEqual(
                    tomllib.loads(journal.read_text(encoding="utf-8"))["status"],
                    "committed",
                )
                for role, (model, effort) in self.EXPECTED_ROUTING[target_set].items():
                    profile = tomllib.loads(
                        (project / f".codex/agents/kapisch-{role}.toml").read_text(
                            encoding="utf-8"
                        )
                    )
                    state = tomllib.loads(
                        (project / f".kapisch/local-state/profiles/{role}.toml").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertEqual(
                        (profile["model"], profile["model_reasoning_effort"]),
                        (model, effort),
                    )
                    self.assertEqual(state["profile_set"], target_set)

                recovery_output = io.StringIO()
                with redirect_stdout(recovery_output):
                    self.assertEqual(
                        setup_profile.main(
                            [
                                "--all",
                                "--project-dir",
                                str(project),
                                "--profile-set",
                                target_set,
                            ]
                        ),
                        0,
                    )
                self.assertIn(
                    "recovery=completed interrupted managed-profile transaction",
                    recovery_output.getvalue(),
                )
                self.assertFalse(journal.exists())

    def test_committed_destination_divergence_is_not_reported_as_active(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            journal = project / ".kapisch/local-state/profile-switch.toml"
            target = project / ".codex/agents/kapisch-architect.toml"
            original_replace = setup_profile.os.replace
            committed_bytes: bytes | None = None

            def diverge_after_commit(source, destination):
                nonlocal committed_bytes
                result = original_replace(source, destination)
                if Path(source).name == ".profile-switch.commit.tmp":
                    committed_bytes = target.read_bytes()
                    target.write_bytes(b'name = "kapisch-architect"\n# later drift\n')
                return result

            output = io.StringIO()
            with (
                mock.patch.object(
                    setup_profile.os,
                    "replace",
                    side_effect=diverge_after_commit,
                ),
                redirect_stdout(output),
            ):
                result = setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )

            self.assertEqual(result, 2)
            self.assertIsNotNone(committed_bytes)
            assert committed_bytes is not None
            self.assertTrue(journal.exists())
            self.assertIn("status=verification-failed", output.getvalue())
            self.assertIn("committed switch verification failed", output.getvalue())
            self.assertNotIn("status=installed", output.getvalue())
            self.assertNotIn("installed_profile_set=quality", output.getvalue())
            self.assertNotIn("committed profile set is active", output.getvalue())

            target.write_bytes(committed_bytes)
            recovery_output = io.StringIO()
            with redirect_stdout(recovery_output):
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "quality",
                        ]
                    ),
                    0,
                )
            self.assertIn(
                "recovery=completed interrupted managed-profile transaction",
                recovery_output.getvalue(),
            )
            self.assertFalse(journal.exists())

    def test_interrupted_switch_recovers_at_every_profile_and_state_publish(self) -> None:
        class SimulatedPowerLoss(BaseException):
            pass

        for boundary in range(1, 13):
            with self.subTest(boundary=boundary), TemporaryDirectory() as temporary:
                project = Path(temporary)
                self.assertEqual(self._install(project, "balanced"), 0)
                before = self._snapshot(project)
                original_replace = setup_profile.os.replace
                publishes = 0

                def crash_after_publish(source, destination):
                    nonlocal publishes
                    result = original_replace(source, destination)
                    if Path(source).name.endswith(".kapisch-switch.tmp"):
                        publishes += 1
                        if publishes == boundary:
                            raise SimulatedPowerLoss
                    return result

                with (
                    mock.patch.object(
                        setup_profile.os,
                        "replace",
                        side_effect=crash_after_publish,
                    ),
                    self.assertRaises(SimulatedPowerLoss),
                ):
                    setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "quality",
                            "--install",
                            "--replace-managed",
                        ]
                    )
                self.assertTrue(
                    (project / ".kapisch/local-state/profile-switch.toml").is_file()
                )
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "balanced",
                        ]
                    ),
                    0,
                )
                self.assertEqual(self._snapshot(project), before)

    def test_interrupted_switch_preserves_a_later_user_edit(self) -> None:
        class SimulatedPowerLoss(BaseException):
            pass

        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            original_replace = setup_profile.os.replace

            def crash_after_first_publish(source, destination):
                result = original_replace(source, destination)
                if Path(source).name.endswith(".kapisch-switch.tmp"):
                    raise SimulatedPowerLoss
                return result

            with (
                mock.patch.object(
                    setup_profile.os,
                    "replace",
                    side_effect=crash_after_first_publish,
                ),
                self.assertRaises(SimulatedPowerLoss),
            ):
                setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )

            target = project / ".codex/agents/kapisch-architect.toml"
            user_edit = target.read_bytes() + b"# user edit after interruption\n"
            target.write_bytes(user_edit)

            self.assertEqual(
                setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "balanced",
                    ]
                ),
                0,
            )
            self.assertEqual(target.read_bytes(), user_edit)
            self.assertFalse(
                (project / ".kapisch/local-state/profile-switch.toml").exists()
            )

    def test_interrupted_journal_publish_recovers_and_commit_publish_finishes(self) -> None:
        class SimulatedPowerLoss(BaseException):
            pass

        for boundary, expect_quality in (
            (".profile-switch.prepare.tmp", False),
            (".profile-switch.commit.tmp", True),
        ):
            with self.subTest(boundary=boundary), TemporaryDirectory() as temporary:
                project = Path(temporary)
                self.assertEqual(self._install(project, "balanced"), 0)
                before = self._snapshot(project)
                original_replace = setup_profile.os.replace

                def crash_after_boundary(source, destination):
                    result = original_replace(source, destination)
                    if Path(source).name == boundary:
                        raise SimulatedPowerLoss
                    return result

                with (
                    mock.patch.object(
                        setup_profile.os,
                        "replace",
                        side_effect=crash_after_boundary,
                    ),
                    self.assertRaises(SimulatedPowerLoss),
                ):
                    setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "quality",
                            "--install",
                            "--replace-managed",
                        ]
                    )
                self.assertEqual(
                    setup_profile.main(
                        [
                            "--all",
                            "--project-dir",
                            str(project),
                            "--profile-set",
                            "quality" if expect_quality else "balanced",
                        ]
                    ),
                    0,
                )
                if expect_quality:
                    for role, (model, effort) in self.EXPECTED_ROUTING["quality"].items():
                        profile = tomllib.loads(
                            (
                                project / f".codex/agents/kapisch-{role}.toml"
                            ).read_text(encoding="utf-8")
                        )
                        self.assertEqual(
                            (profile["model"], profile["model_reasoning_effort"]),
                            (model, effort),
                        )
                else:
                    self.assertEqual(self._snapshot(project), before)

    def test_concurrent_identity_collision_rolls_back_without_deleting_it(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            expected = self._snapshot(project)
            collision = project / ".codex/agents/unrelated.toml"
            collision_bytes = b'name = "kapisch-reviewer"\n'
            expected[collision.relative_to(project)] = collision_bytes
            original_replace = setup_profile.os.replace
            inserted = False

            def insert_collision_before_publish(source, destination):
                nonlocal inserted
                if not inserted and Path(source).name.endswith(".kapisch-switch.tmp"):
                    inserted = True
                    collision.write_bytes(collision_bytes)
                return original_replace(source, destination)

            with mock.patch.object(
                setup_profile.os,
                "replace",
                side_effect=insert_collision_before_publish,
            ):
                result = setup_profile.main(
                    [
                        "--all",
                        "--project-dir",
                        str(project),
                        "--profile-set",
                        "quality",
                        "--install",
                        "--replace-managed",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertEqual(self._snapshot(project), expected)

    def test_active_setup_lock_blocks_and_stale_lock_is_recovered(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            lock = project / ".kapisch/local-state/profile-switch.lock"
            lock.write_text(f"pid={setup_profile.os.getpid()}\n", encoding="ascii")
            self.assertEqual(
                setup_profile.main(
                    ["--all", "--project-dir", str(project), "--install"]
                ),
                2,
            )
            self.assertTrue(lock.exists())
            lock.write_text("pid=999999\n", encoding="ascii")
            self.assertEqual(
                setup_profile.main(
                    ["--all", "--project-dir", str(project), "--install"]
                ),
                0,
            )
            self.assertFalse(lock.exists())
            self.assertEqual(self._snapshot(project), before)

    def test_oversized_setup_lock_pid_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "balanced"), 0)
            before = self._snapshot(project)
            lock = project / ".kapisch/local-state/profile-switch.lock"
            contents = "pid=999999999999999999999999999999999999999999\n"
            lock.write_text(contents, encoding="ascii")
            before[lock.relative_to(project)] = lock.read_bytes()

            self.assertEqual(
                setup_profile.main(
                    ["--all", "--project-dir", str(project), "--install"]
                ),
                2,
            )
            self.assertEqual(lock.read_text(encoding="ascii"), contents)
            self.assertEqual(self._snapshot(project), before)

    def test_verified_legacy_state_is_inspectable_as_quality_without_rewrite(self) -> None:
        with TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.assertEqual(self._install(project, "quality"), 0)
            for record in (project / ".kapisch/local-state/profiles").glob("*.toml"):
                lines = [
                    line
                    for line in record.read_text(encoding="utf-8").splitlines()
                    if not line.startswith("profile_set=")
                ]
                record.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before = self._snapshot(project)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    setup_profile.main(
                        ["--all", "--project-dir", str(project)]
                    ),
                    0,
                )
            self.assertEqual(self._snapshot(project), before)
            self.assertEqual(output.getvalue().count("installed_profile_set=quality"), 6)
