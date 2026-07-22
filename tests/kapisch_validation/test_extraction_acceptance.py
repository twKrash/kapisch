from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from kapisch_validation.review_evidence import CANONICAL_REVIEWER_PROFILE
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
    def test_reviewer_setup_target_matches_canonical_evidence_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.assertEqual(
                setup_profile(
                    ["--role", "reviewer", "--project-dir", str(project), "--install"]
                ),
                0,
            )
            installed = project / CANONICAL_REVIEWER_PROFILE
            self.assertTrue(installed.is_file())
            self.assertEqual(
                installed.read_bytes(),
                (ROOT / "agents/kapisch-reviewer.toml").read_bytes(),
            )
            reviewer_contract = (ROOT / "roles/reviewer.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("explicit user attestation", reviewer_contract)
            for role_contract in (ROOT / "roles").glob("*.md"):
                self.assertNotIn(
                    ".codex/",
                    role_contract.read_text(encoding="utf-8"),
                    f"portable role contract embeds Codex layout: {role_contract}",
                )

    def test_change5_roadmap_tracks_canonical_review_history(self) -> None:
        roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
        change5 = roadmap.split(
            "## Change 5 — project understanding and architecture documentation",
            1,
        )[1].split("## Change 6", 1)[0]
        normalized = " ".join(change5.split())
        self.assertIn("Policy B", normalized)
        self.assertIn("preserved Round 0 negative review", normalized)
        self.assertIn("canonical Round 1 approved", normalized)
        self.assertIn("final-readiness pass returned `not-ready`", normalized)
        self.assertIn("fresh whole-delta approving review", normalized)
        self.assertIn("distinct final-readiness decision", normalized)

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

    def test_project_understanding_contract_separates_research_writing_and_review(self) -> None:
        skill_path = ROOT / "skills/kapisch/SKILL.md"
        contract_path = ROOT / "skills/kapisch/references/project-understanding.md"
        skill = skill_path.read_text(encoding="utf-8")
        contract = contract_path.read_text(encoding="utf-8")
        normalized_contract = " ".join(contract.split())
        researcher = (ROOT / "roles/researcher.md").read_text(encoding="utf-8")
        mechanic = (ROOT / "roles/mechanic.md").read_text(encoding="utf-8")
        mechanic_profile = (ROOT / "agents/kapisch-mechanic.toml").read_text(
            encoding="utf-8"
        )
        role_resolution = (
            ROOT / "skills/kapisch/references/role-resolution.md"
        ).read_text(encoding="utf-8")
        review = (ROOT / "skills/kapisch/references/review.md").read_text(
            encoding="utf-8"
        )
        handoffs = (ROOT / "skills/kapisch/references/handoffs.md").read_text(
            encoding="utf-8"
        )
        normalized_handoffs = " ".join(handoffs.split())
        acceptance = (ROOT / "docs/acceptance.md").read_text(encoding="utf-8")
        frontmatter = skill.split("---", 2)[1]
        description_lines = frontmatter.split("description: >-", 1)[1].splitlines()
        frontmatter_description = " ".join(
            line.strip() for line in description_lines if line.startswith("  ")
        )
        for intent in (
            "read-only project understanding",
            "architecture questions and maps",
            "documentation-drift checks",
            "onboarding summaries",
            "decision-record preparation",
        ):
            self.assertIn(intent, frontmatter_description)
        self.assertIn("project-understanding.md", skill)
        self.assertIn("Research is advisory and read-only", contract)
        self.assertIn("separate implementation step", contract)
        self.assertIn("closed-catalog `implementer` role", normalized_contract)
        for assigned_role in (
            "`researcher`",
            "`architect`",
            "`implementer`",
            "`mechanic`",
        ):
            self.assertIn(assigned_role, role_resolution)
        self.assertNotIn("The writer", contract)
        self.assertNotIn("a writer", contract)
        self.assertIn("independent review", contract)
        self.assertIn(
            "every versioned project-understanding or architecture-documentation",
            normalized_contract,
        )
        self.assertIn(
            "even when they do not change behaviour or a public contract",
            normalized_contract,
        )
        self.assertIn("does not choose or approve", normalized_contract)
        self.assertIn("input acceptance only", normalized_contract)
        self.assertIn("every mechanic condition", normalized_contract)
        self.assertIn("verbatim synchronization", mechanic)
        self.assertIn("already approved authoritative", mechanic)
        self.assertIn("any synchronization requiring", mechanic)
        self.assertIn("verbatim synchronization", mechanic_profile)
        self.assertIn("approved authoritative", mechanic_profile)
        self.assertIn("escalate adaptation or source-authority", mechanic_profile)
        self.assertIn("00-research.md", contract)
        self.assertIn("00-research.md", handoffs)
        self.assertIn("root directory for research", normalized_handoffs)
        self.assertIn("Research, plan, implementation", normalized_handoffs)
        self.assertIn("researcher remains read-only", normalized_handoffs)
        self.assertIn("Project-understanding procedures, role boundaries", acceptance)
        self.assertIn(
            "Versioned project-understanding or architecture-documentation output",
            review,
        )
        self.assertIn("takes precedence", review)
        self.assertIn("under `review=auto`", review)
        self.assertIn("never outrank the current", contract)
        self.assertIn("architecture maps", researcher)
        for heading in (
            "## Architecture question",
            "## Architecture map",
            "## Documentation-drift check",
            "## Onboarding summary",
            "## Decision-record preparation",
        ):
            self.assertIn(heading, contract)
        for document in (skill_path, contract_path):
            contents = document.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", contents):
                local_target = target.split("#", 1)[0]
                if not local_target or "://" in local_target:
                    continue
                self.assertTrue(
                    (document.parent / local_target).resolve().exists(),
                    f"broken local Markdown target in {document}: {target}",
                )

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
