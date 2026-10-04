from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))


def _bundles() -> tuple[bytes, bytes]:
    from kapisch_core.bundle import canonical_json

    original = (ROOT / "core/dist/core-bundle.json").read_bytes()
    payload = json.loads(original)
    policy = payload["policies"]["dispatch"]
    policy["contract"] += "\nDistribution upgrade marker.\n"
    policy["sha256"] = hashlib.sha256(policy["contract"].encode()).hexdigest()
    return original, canonical_json(payload)


class StorageTests(unittest.TestCase):
    def test_authority_records_are_no_replace_and_exact_retry_is_idempotent(
        self,
    ) -> None:
        from kapisch_core.storage import store_authority_record

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.assertTrue(
                store_authority_record(repo, "scopes", "scope-1", b"canonical")
            )
            self.assertFalse(
                store_authority_record(repo, "scopes", "scope-1", b"canonical")
            )
            with self.assertRaises(FileExistsError):
                store_authority_record(repo, "scopes", "scope-1", b"different")
            self.assertEqual(
                (repo / ".kapisch/v3/authority/scopes/scope-1.json").read_bytes(),
                b"canonical",
            )

    def test_human_approval_artifact_is_content_addressed_and_idempotent(self) -> None:
        from kapisch_core.storage import (
            load_human_approval_artifact,
            retain_human_approval_artifact,
        )

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            data = b'{"protocol_version":3}\n'
            digest = hashlib.sha256(data).hexdigest()
            expected = {
                "path": f".kapisch/v3/authority/human-artifacts/{digest}.json",
                "sha256": digest,
            }
            self.assertEqual(retain_human_approval_artifact(repo, data), expected)
            self.assertEqual(retain_human_approval_artifact(repo, data), expected)
            self.assertEqual(
                load_human_approval_artifact(repo, expected["path"], digest), data
            )

    def test_human_approval_artifact_readback_rejects_tampering_and_noncanonical_path(
        self,
    ) -> None:
        from kapisch_core.storage import (
            load_human_approval_artifact,
            retain_human_approval_artifact,
        )

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            reference = retain_human_approval_artifact(repo, b"artifact")
            with self.assertRaises(ValueError):
                load_human_approval_artifact(
                    repo, "caller-selected.json", reference["sha256"]
                )
            artifact_path = repo / reference["path"]
            artifact_path.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                load_human_approval_artifact(
                    repo, reference["path"], reference["sha256"]
                )

    def test_human_approval_artifact_sync_failure_is_not_success(self) -> None:
        from kapisch_core.storage import (
            load_human_approval_artifact,
            retain_human_approval_artifact,
        )

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            data = b"canonical artifact bytes"
            with patch(
                "kapisch_core.storage._sync_hierarchy",
                side_effect=OSError("sync failed"),
            ):
                with self.assertRaisesRegex(OSError, "sync failed"):
                    retain_human_approval_artifact(repo, data)
            reference = retain_human_approval_artifact(repo, data)
            self.assertEqual(
                load_human_approval_artifact(
                    repo, reference["path"], reference["sha256"]
                ),
                data,
            )

    def test_human_approval_artifact_occupied_digest_path_fails_closed(self) -> None:
        from kapisch_core.storage import retain_human_approval_artifact

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            data = b"expected bytes"
            digest = hashlib.sha256(data).hexdigest()
            path = repo / ".kapisch/v3/authority/human-artifacts" / f"{digest}.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"different bytes")
            with self.assertRaises((OSError, ValueError)):
                retain_human_approval_artifact(repo, data)
            self.assertEqual(path.read_bytes(), b"different bytes")

    def test_load_authority_record_reads_exact_bytes(self) -> None:
        from kapisch_core.storage import load_authority_record, store_authority_record

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            record = b'{"protocol_version":3}\n'
            store_authority_record(repo, "scopes", "scope-1", record)
            self.assertEqual(load_authority_record(repo, "scopes", "scope-1"), record)
            with self.assertRaises(FileNotFoundError):
                load_authority_record(repo, "scopes", "missing")

    def test_authority_record_rejects_unsafe_leaf_types(self) -> None:
        from kapisch_core.storage import store_authority_record

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            leaf = repo / ".kapisch/v3/authority/human-actions/action-1.json"
            leaf.parent.mkdir(parents=True)
            target = repo / "external"
            target.write_bytes(b"outside")
            leaf.symlink_to(target)
            with self.assertRaises(OSError):
                store_authority_record(repo, "human-actions", "action-1", b"record")
            self.assertEqual(target.read_bytes(), b"outside")

    def test_authority_record_rejects_nonregular_occupied_identity(self) -> None:
        from kapisch_core.storage import store_authority_record

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            leaf = repo / ".kapisch/v3/authority/gate-approvals/approval-1.json"
            leaf.parent.mkdir(parents=True)
            leaf.mkdir()
            with self.assertRaises(ValueError):
                store_authority_record(repo, "gate-approvals", "approval-1", b"record")

    def test_retains_exact_bundle_after_distribution_upgrade(self) -> None:
        from kapisch_core.bundle import verify_bundle
        from kapisch_core.storage import load_bundle, store_bundle

        original, upgraded = _bundles()
        digest = hashlib.sha256(original).hexdigest()
        upgraded_digest = hashlib.sha256(upgraded).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.assertEqual(store_bundle(repo, original), digest)
            self.assertEqual(store_bundle(repo, upgraded), upgraded_digest)
            self.assertEqual(load_bundle(repo, digest), verify_bundle(original, digest))

            script = (
                "from pathlib import Path; from kapisch_core.storage import load_bundle; "
                "import sys; assert 'Distribution upgrade marker.' not in "
                "load_bundle(Path(sys.argv[1]), sys.argv[2]).payload['policies']['dispatch']['contract']"
            )
            run = subprocess.run(
                [sys.executable, "-c", script, str(repo), digest],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "core")},
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

            with self.assertRaises(FileNotFoundError):
                load_bundle(repo, "0" * 64)
            retained = repo / ".kapisch/v3/bundles" / f"{digest}.json"
            retained.unlink()
            with self.assertRaises(FileNotFoundError):
                load_bundle(repo, digest)
            self.assertEqual(
                load_bundle(repo, upgraded_digest),
                verify_bundle(upgraded, upgraded_digest),
            )
            store_bundle(repo, original)
            retained.write_bytes(upgraded)
            with self.assertRaises(ValueError):
                load_bundle(repo, digest)

    def test_store_rejects_symlinked_authority_components_without_external_writes(
        self,
    ) -> None:
        from kapisch_core.storage import store_bundle

        original, _ = _bundles()
        for component in (".kapisch", "v3", "bundles"):
            with (
                self.subTest(component=component),
                tempfile.TemporaryDirectory() as directory,
            ):
                repo = Path(directory) / "repo"
                repo.mkdir()
                external = Path(directory) / "external"
                external.mkdir()
                if component == ".kapisch":
                    (repo / component).symlink_to(external, target_is_directory=True)
                elif component == "v3":
                    (repo / ".kapisch").mkdir()
                    (repo / ".kapisch/v3").symlink_to(
                        external, target_is_directory=True
                    )
                else:
                    (repo / ".kapisch/v3").mkdir(parents=True)
                    (repo / ".kapisch/v3/bundles").symlink_to(
                        external, target_is_directory=True
                    )
                with self.assertRaises(OSError):
                    store_bundle(repo, original)
                self.assertEqual(list(external.iterdir()), [])

    def test_load_rejects_symlinked_authority_components(self) -> None:
        from kapisch_core.storage import load_bundle

        original, _ = _bundles()
        digest = hashlib.sha256(original).hexdigest()
        for component in (".kapisch", "v3", "bundles"):
            with (
                self.subTest(component=component),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory)
                repo = base / "repo"
                repo.mkdir()
                target = base / "target"
                bundle_dir = target / ".kapisch/v3/bundles"
                bundle_dir.mkdir(parents=True)
                (bundle_dir / f"{digest}.json").write_bytes(original)
                if component == ".kapisch":
                    (repo / component).symlink_to(
                        target / ".kapisch", target_is_directory=True
                    )
                elif component == "v3":
                    (repo / ".kapisch").mkdir()
                    (repo / ".kapisch/v3").symlink_to(
                        target / ".kapisch/v3", target_is_directory=True
                    )
                else:
                    (repo / ".kapisch/v3").mkdir(parents=True)
                    (repo / ".kapisch/v3/bundles").symlink_to(
                        bundle_dir, target_is_directory=True
                    )
                with self.assertRaises(OSError):
                    load_bundle(repo, digest)

    def test_load_and_store_reject_symlinked_digest_leaf(self) -> None:
        from kapisch_core.storage import load_bundle, store_bundle

        original, _ = _bundles()
        digest = hashlib.sha256(original).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            store_bundle(repo, original)
            leaf = repo / ".kapisch/v3/bundles" / f"{digest}.json"
            external = Path(directory) / "external.json"
            external.write_bytes(original)
            leaf.unlink()
            leaf.symlink_to(external)
            with self.assertRaises(OSError):
                load_bundle(repo, digest)
            with self.assertRaises(OSError):
                store_bundle(repo, original)
            self.assertEqual(external.read_bytes(), original)

    @unittest.skipUnless(
        hasattr(os, "mkfifo"), "FIFO creation is unsupported on this platform"
    )
    def test_load_and_store_reject_fifo_digest_leaf_without_blocking(self) -> None:
        from kapisch_core.storage import store_bundle

        original, _ = _bundles()
        digest = hashlib.sha256(original).hexdigest()
        script = """
import sys
from pathlib import Path
from kapisch_core.storage import load_bundle, store_bundle

repo = Path(sys.argv[1])
digest = sys.argv[2]
try:
    if sys.argv[3] == "load":
        load_bundle(repo, digest)
    else:
        store_bundle(repo, Path(sys.argv[4]).read_bytes())
except ValueError as error:
    assert str(error) == "retained bundle is not a regular file", str(error)
else:
    raise AssertionError("FIFO digest leaf was accepted")
"""
        for operation in ("load", "store"):
            with (
                self.subTest(operation=operation),
                tempfile.TemporaryDirectory() as directory,
            ):
                repo = Path(directory)
                store_bundle(repo, original)
                leaf = repo / ".kapisch/v3/bundles" / f"{digest}.json"
                leaf.unlink()
                os.mkfifo(leaf)
                try:
                    run = subprocess.run(
                        [
                            sys.executable,
                            "-c",
                            script,
                            str(repo),
                            digest,
                            operation,
                            str(ROOT / "core/dist/core-bundle.json"),
                        ],
                        cwd=ROOT,
                        env={**os.environ, "PYTHONPATH": str(ROOT / "core")},
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                finally:
                    self.assertTrue(stat.S_ISFIFO(leaf.lstat().st_mode))
                    self.assertEqual(list(leaf.parent.iterdir()), [leaf])

    def test_store_rejects_dangling_authority_symlinks(self) -> None:
        from kapisch_core.storage import load_bundle, store_bundle

        original, _ = _bundles()
        digest = hashlib.sha256(original).hexdigest()
        for component in (".kapisch", "v3", "bundles"):
            with (
                self.subTest(component=component),
                tempfile.TemporaryDirectory() as directory,
            ):
                repo = Path(directory) / "repo"
                repo.mkdir()
                if component == ".kapisch":
                    target = repo / component
                elif component == "v3":
                    (repo / ".kapisch").mkdir()
                    target = repo / ".kapisch/v3"
                else:
                    (repo / ".kapisch/v3").mkdir(parents=True)
                    target = repo / ".kapisch/v3/bundles"
                target.symlink_to(Path(directory) / "missing", target_is_directory=True)
                with self.assertRaises(OSError):
                    store_bundle(repo, original)
                with self.assertRaises(OSError):
                    load_bundle(repo, digest)

    def test_publication_fsyncs_file_and_directories_and_retry_is_safe(self) -> None:
        from kapisch_core import storage
        from kapisch_core.storage import load_bundle, store_bundle

        original, _ = _bundles()
        digest = hashlib.sha256(original).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            real_fsync = os.fsync
            calls = 0

            def fail_once(fd: int) -> None:
                nonlocal calls
                calls += 1
                if calls == 8:
                    raise OSError("injected directory fsync failure")
                real_fsync(fd)

            with (
                patch.object(storage.os, "fsync", side_effect=fail_once),
                self.assertRaises(OSError),
            ):
                store_bundle(repo, original)
            self.assertEqual(load_bundle(repo, digest).protocol_version, 3)
            self.assertEqual(store_bundle(repo, original), digest)

            calls = 0

            def count_fsync(fd: int) -> None:
                nonlocal calls
                calls += 1
                real_fsync(fd)

            with patch.object(storage.os, "fsync", side_effect=count_fsync):
                self.assertEqual(store_bundle(repo, original), digest)
            self.assertEqual(
                calls, 6
            )  # File, bundle directory, and all containing directories.


if __name__ == "__main__":
    unittest.main()
