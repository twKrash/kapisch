from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
PLUGIN = ROOT / "plugins/kapisch"


class MarketplaceTests(unittest.TestCase):
    TESTED_RUNTIME_SHA = "7ccc2b6a4987cac416f1566debc47e45fc1c2b14"

    def assert_release_provenance(self, matrix: str, acceptance: str) -> None:
        self.assertIn(
            f"tested runtime tree `{self.TESTED_RUNTIME_SHA}`",
            matrix,
        )
        self.assertIn("final release SHA pending", matrix)
        self.assertNotIn("current uncommitted candidate worktree", matrix)
        self.assertIn(
            f"- Tested runtime SHA: `{self.TESTED_RUNTIME_SHA}`.",
            acceptance,
        )
        self.assertIn("automated evidence is bound to this exact runtime tree", acceptance)
        self.assertRegex(acceptance, r"272 passed,\s+4 platform-capability skips")
        self.assertIn(
            "- Final release SHA: pending review, merge, and authorized release preparation.",
            acceptance,
        )
        self.assertNotIn("current uncommitted candidate worktree", acceptance)

    def test_release_metadata_is_consistent(self) -> None:
        manifest = json.loads(
            (PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )
        project = tomllib.loads(
            (PLUGIN / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        self.assertEqual(manifest["version"], project["version"])

        version = project["version"]
        release_tag = f"v{version}"
        catalog = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        self.assertEqual(catalog["name"], "kapisch-local")
        self.assertEqual(
            catalog["plugins"][0]["source"],
            {"source": "local", "path": "./plugins/kapisch"},
        )
        self.assertEqual(catalog["plugins"][0]["name"], manifest["name"])

        release_command = (
            f"codex plugin marketplace add twKrash/kapisch --ref {release_tag}"
        )
        for readme in (ROOT / "README.md", PLUGIN / "README.md"):
            contents = " ".join(readme.read_text(encoding="utf-8").split())
            self.assertIn(
                release_command,
                contents,
            )
            self.assertEqual(
                set(
                    re.findall(
                        r"codex plugin marketplace add twKrash/kapisch "
                        r"--ref (v[0-9A-Za-z.-]+)",
                        contents,
                    )
                ),
                {release_tag},
            )

        changelog = (PLUGIN / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {version} -", changelog)

        windows_acceptance = (
            PLUGIN / "docs" / f"acceptance-windows-v{version}.md"
        )
        self.assertTrue(windows_acceptance.is_file())
        acceptance = windows_acceptance.read_text(encoding="utf-8")
        self.assertIn(
            f"# Windows acceptance record — {version}",
            acceptance,
        )
        self.assertIn(
            f"- Release: `{version}`; intended immutable tag: `{release_tag}`.",
            acceptance,
        )
        matrix = (PLUGIN / "docs/acceptance.md").read_text(encoding="utf-8")
        self.assert_release_provenance(matrix, acceptance)


    def test_release_metadata_rejects_contradictory_provenance(self) -> None:
        version = tomllib.loads(
            (PLUGIN / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"]
        matrix = (PLUGIN / "docs/acceptance.md").read_text(encoding="utf-8")
        acceptance = (
            PLUGIN / "docs" / f"acceptance-windows-v{version}.md"
        ).read_text(encoding="utf-8")

        with self.assertRaisesRegex(
            AssertionError,
            "current uncommitted candidate worktree",
        ):
            self.assert_release_provenance(
                f"{matrix}\ncurrent uncommitted candidate worktree",
                acceptance,
            )

    def test_digest_sensitive_fixtures_are_checked_out_with_lf(self) -> None:
        fixture = (
            "plugins/kapisch/tests/kapisch_validation/fixtures/"
            "valid-sequential-v2/reviews/final/05-final.md"
        )
        result = subprocess.run(
            ["git", "check-attr", "eol", "--", fixture],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), f"{fixture}: eol: lf")

    def test_github_marketplace_resolves_the_canonical_plugin(self) -> None:
        catalog = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        self.assertEqual(
            set(catalog),
            {"name", "interface", "plugins"},
        )
        self.assertEqual(catalog["name"], "kapisch-local")
        self.assertEqual(catalog["interface"], {"displayName": "KAPISCH Local"})
        self.assertEqual(len(catalog["plugins"]), 1)

        entry = catalog["plugins"][0]
        self.assertEqual(
            entry,
            {
                "name": "kapisch",
                "source": {
                    "source": "local",
                    "path": "./plugins/kapisch",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            },
        )

        resolved = (ROOT / entry["source"]["path"]).resolve()
        self.assertEqual(resolved, PLUGIN.resolve())
        self.assertTrue(resolved.is_relative_to(ROOT.resolve()))

        manifest = json.loads(
            (resolved / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], entry["name"])
        self.assertEqual(manifest["repository"], "https://github.com/twKrash/kapisch")
        self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertIn(
            "name: kapisch",
            (resolved / "skills/kapisch/SKILL.md").read_text(encoding="utf-8"),
        )

        manifests = [
            path
            for path in ROOT.rglob(".codex-plugin/plugin.json")
            if ".git" not in path.parts
        ]
        self.assertEqual(manifests, [resolved / ".codex-plugin/plugin.json"])

    def test_documented_commands_use_the_github_marketplace(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        normalized = " ".join(readme.split())
        version = json.loads(
            (PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )["version"]
        # The released path is pinned to the versioned immutable tag.
        self.assertIn(
            "codex plugin marketplace add "
            f"twKrash/kapisch --ref v{version}",
            normalized,
        )
        # A runnable development path is preserved (against mutable code) and is
        # explicitly labeled as mutable/development-only.
        self.assertIn(
            "codex plugin marketplace add twKrash/kapisch --ref main",
            normalized,
        )
        self.assertIn(
            "This is the runnable development path",
            normalized,
        )
        self.assertIn("codex plugin add kapisch@kapisch-local", normalized)
        self.assertIn(
            "not an OpenAI public Plugin Directory submission",
            normalized,
        )
        for relative in (
            ".agents/plugins/marketplace.json",
            "plugins/kapisch/README.md",
            "LICENSE",
        ):
            self.assertTrue(ROOT.joinpath(relative).is_file())

    def test_moved_plugin_documents_explicit_consumer_targets(self) -> None:
        readme = " ".join(
            (PLUGIN / "README.md").read_text(encoding="utf-8").split()
        )
        skill = " ".join(
            (PLUGIN / "skills/kapisch/SKILL.md")
            .read_text(encoding="utf-8")
            .split()
        )
        self.assertIn(
            "python scripts/setup_profile.py --role reviewer --project-dir "
            "<consumer-repository>",
            readme,
        )
        for profile_set in ("balanced", "quality", "budget"):
            self.assertIn(
                "python scripts/setup_profile.py --all --project-dir "
                f"<consumer-repository> --profile-set {profile_set} --install",
                readme,
            )
        self.assertIn(
            "--profile-set budget --install --replace-managed",
            readme,
        )
        self.assertIn(
            "python scripts/migrate_legacy_run.py --project-dir "
            "<consumer-repository> --task-id <task-id> --approve",
            readme,
        )
        self.assertIn(
            "--task-dir <consumer-repository>/.kapisch/runs/example",
            readme,
        )
        self.assertIn(
            "--task-dir <consumer-repository>/.kapisch/runs/<task-id>",
            skill,
        )

    def test_moved_plugin_scripts_target_explicit_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            consumer = Path(temporary) / "consumer"
            consumer.mkdir()

            setup = subprocess.run(
                [
                    sys.executable,
                    "scripts/setup_profile.py",
                    "--role",
                    "reviewer",
                    "--project-dir",
                    str(consumer),
                    "--install",
                ],
                cwd=PLUGIN,
                capture_output=True,
                text=True,
            )
            self.assertEqual(setup.returncode, 0, setup.stdout + setup.stderr)
            self.assertTrue(
                (consumer / ".codex/agents/kapisch-reviewer.toml").is_file()
            )

            help_result = subprocess.run(
                [sys.executable, "scripts/setup_profile.py", "--help"],
                cwd=PLUGIN,
                capture_output=True,
                text=True,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("--profile-set {balanced,quality,budget}", help_result.stdout)
            self.assertIn("--replace-managed", help_result.stdout)

            legacy = consumer / ".planning/task-workflow/valid"
            shutil.copytree(
                PLUGIN
                / "tests/kapisch_validation/fixtures/valid-sequential-v2",
                legacy,
            )
            migration = subprocess.run(
                [
                    sys.executable,
                    "scripts/migrate_legacy_run.py",
                    "--project-dir",
                    str(consumer),
                    "--task-id",
                    "valid",
                    "--approve",
                ],
                cwd=PLUGIN,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                migration.returncode,
                0,
                migration.stdout + migration.stderr,
            )
            self.assertTrue((consumer / ".kapisch/runs/valid").is_dir())

    def test_validation_package_keeps_the_standard_library_runtime_boundary(self) -> None:
        project = tomllib.loads(
            (PLUGIN / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        self.assertNotIn("dependencies", project)

    def test_installed_plugin_validator_resolves_bundled_paths_from_plugin_root(
        self,
    ) -> None:
        """The documented validator command must work from a consumer repository
        against an installed plugin copy; cwd=PLUGIN in the unit suites masks
        the consumer-context defect this regression guards."""
        with tempfile.TemporaryDirectory() as temporary:
            consumer = Path(temporary) / "consumer"
            consumer.mkdir()
            installed = Path(temporary) / "installed-plugin"
            shutil.copytree(PLUGIN, installed)

            skill = installed / "skills/kapisch/SKILL.md"
            self.assertTrue(skill.is_file())
            plugin_root = skill.parents[2]
            self.assertEqual(plugin_root, installed)
            self.assertTrue((plugin_root / "scripts/validate_kapisch.py").is_file())

            run_dir = consumer / ".kapisch/runs/valid"
            shutil.copytree(
                PLUGIN / "tests/kapisch_validation/fixtures/valid-sequential-v2",
                run_dir,
            )

            consumer_relative = subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_kapisch.py",
                    "--contract-dir",
                    "skills/kapisch",
                    "--task-dir",
                    str(run_dir),
                ],
                cwd=consumer,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(consumer_relative.returncode, 0)

            installed_qualified = subprocess.run(
                [
                    sys.executable,
                    str(plugin_root / "scripts/validate_kapisch.py"),
                    "--contract-dir",
                    str(plugin_root / "skills/kapisch"),
                    "--task-dir",
                    str(run_dir),
                ],
                cwd=consumer,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                installed_qualified.returncode,
                0,
                installed_qualified.stdout + installed_qualified.stderr,
            )

    def test_foundry_theme_uses_original_vocabulary_boundary(self) -> None:
        roadmap = " ".join(
            (PLUGIN / "docs/roadmap.md").read_text(encoding="utf-8").split()
        )
        self.assertNotIn("Adeptus Mechanicus", roadmap)
        self.assertGreaterEqual(
            roadmap.count("original industrial-mystic `foundry` theme"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
