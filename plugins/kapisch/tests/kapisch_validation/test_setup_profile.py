from __future__ import annotations

import hashlib
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
            valid = b'name = "kapisch-reviewer"\n'
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
