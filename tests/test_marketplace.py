from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
PLUGIN = ROOT / "plugins/kapisch"


class MarketplaceTests(unittest.TestCase):
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
        self.assertIn(
            "codex plugin marketplace add twKrash/kapisch --ref main",
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
