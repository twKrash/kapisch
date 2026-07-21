from __future__ import annotations

import hashlib
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.migrate_legacy_run import main as migrate
from scripts.setup_profile import main as setup_profile


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


class ExtractionAcceptanceTests(unittest.TestCase):
    def test_user_profile_install_records_revisions_and_reports_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "user"
            self.assertEqual(
                setup_profile(["--role", "reviewer", "--scope", "user", "--user-dir", str(user), "--install"]),
                0,
            )
            profile = user / ".codex/agents/kapisch-reviewer.toml"
            record = user / ".kapisch/local-state/profiles/reviewer.toml"
            self.assertTrue(profile.is_file())
            self.assertIn('profile_identity="kapisch-reviewer"', record.read_text())
            profile.write_text(profile.read_text() + "# user change\n", encoding="utf-8")
            record.write_text(record.read_text().replace("template_sha256=", "template_sha256=\"old\" # "), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    setup_profile(["--role", "reviewer", "--scope", "user", "--user-dir", str(user)]),
                    0,
                )
            self.assertIn("# user change", profile.read_text())
            self.assertIn("drift=user-modified", output.getvalue())
            self.assertIn("template_drift=updated", output.getvalue())

    def test_primary_skill_keeps_routing_and_degraded_review_contract_explicit(self) -> None:
        skill = (ROOT / "skills/kapisch/SKILL.md").read_text(encoding="utf-8")
        roles = (ROOT / "skills/kapisch/references/role-resolution.md").read_text(encoding="utf-8")
        self.assertIn("Natural language is the complete normal interface", skill)
        self.assertIn("approval is blocked", skill)
        self.assertIn("Python does not resolve roles", roles)

    def test_profile_identity_collision_is_not_adopted_or_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            target = project / ".codex/agents"
            target.mkdir(parents=True)
            profile = target / "kapisch-reviewer.toml"
            profile.write_text('name = "someone-else"\n', encoding="utf-8")
            self.assertEqual(setup_profile(["--role", "reviewer", "--project-dir", str(project)]), 2)
            self.assertEqual(profile.read_text(), 'name = "someone-else"\n')

    def test_profile_identity_collision_in_another_filename_blocks_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            agent_dir = project / ".codex/agents"
            agent_dir.mkdir(parents=True)
            other = agent_dir / "reviewer.toml"
            other.write_text('name = "kapisch-reviewer"\n', encoding="utf-8")
            self.assertEqual(
                setup_profile(["--role", "reviewer", "--project-dir", str(project), "--install"]),
                2,
            )
            self.assertFalse((agent_dir / "kapisch-reviewer.toml").exists())
            self.assertEqual(other.read_text(), 'name = "kapisch-reviewer"\n')

    def test_approved_legacy_copy_validates_and_preserves_source_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / ".planning/task-workflow/valid"
            shutil.copytree(FIXTURES / "valid-sequential-v2", source)
            before = digests(source)
            self.assertEqual(migrate(["--project-dir", str(project), "--task-id", "valid", "--approve"]), 0)
            self.assertEqual(before, digests(source))
            self.assertEqual(before, digests(project / ".kapisch/runs/valid"))

    def test_invalid_legacy_copy_leaves_source_and_creates_no_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / ".planning/task-workflow/missing-scope"
            shutil.copytree(FIXTURES / "missing-review-scope", source)
            before = digests(source)
            self.assertEqual(migrate(["--project-dir", str(project), "--task-id", "missing-scope", "--approve"]), 2)
            self.assertEqual(before, digests(source))
            self.assertFalse((project / ".kapisch/runs/missing-scope").exists())

    def test_migration_rejects_embedded_task_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / ".planning/task-workflow/example"
            shutil.copytree(FIXTURES / "valid-sequential-v2", source)
            before = digests(source)
            self.assertEqual(migrate(["--project-dir", str(project), "--task-id", "example", "--approve"]), 2)
            self.assertEqual(before, digests(source))
            self.assertFalse((project / ".kapisch/runs/example").exists())

    def test_migration_rejects_task_id_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with self.assertRaises(SystemExit):
                migrate(["--project-dir", str(project), "--task-id", "../valid", "--approve"])
            self.assertFalse((project / ".planning").exists())
            self.assertFalse((project / ".kapisch").exists())

    def test_migration_rejects_symlinked_legacy_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            source = project / ".planning/task-workflow/valid"
            shutil.copytree(FIXTURES / "valid-sequential-v2", source)
            link = source / "linked-report.md"
            os.symlink("tasks/T01-report.md", link)
            self.assertTrue(link.is_symlink())
            self.assertEqual(migrate(["--project-dir", str(project), "--task-id", "valid", "--approve"]), 2)
            self.assertTrue(link.is_symlink())
            self.assertFalse((project / ".kapisch/runs/valid").exists())

    def test_migration_never_writes_a_legacy_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.assertRaises(
                SystemExit,
                migrate,
                ["--project-dir", str(project), "--task-id", "new-artifact"],
            )
            self.assertFalse((project / ".planning").exists())


if __name__ == "__main__":
    unittest.main()
