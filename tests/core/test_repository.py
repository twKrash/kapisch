import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[2] / "core"))

_repository = importlib.import_module("kapisch_core.repository")
RepositoryCaptureError = _repository.RepositoryCaptureError
capture_head = _repository.capture_head
capture_index = _repository.capture_index


class RepositoryGitCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "a@b")
        self.git("config", "user.name", "a")
        (self.root / "tracked").write_bytes(b"one")
        self.git("add", "tracked")
        self.git("commit", "-qm", "initial")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, **kwargs):
        return subprocess.run(
            ("git", "-C", str(self.root), *args),
            check=True,
            capture_output=True,
            **kwargs,
        )

    def test_capture_head_binds_storage_format_and_commit(self):
        observed = capture_head(self.root)
        expected_format = self.git(
            "rev-parse", "--show-object-format=storage"
        ).stdout.strip().decode("ascii")
        expected_commit = self.git("rev-parse", "--verify", "HEAD").stdout.strip().decode(
            "ascii"
        )
        self.assertEqual(observed.object_format, expected_format)
        self.assertEqual(observed.commit, expected_commit)

    def test_index_entry_digest_tracks_blob_stage_mode(self):
        before = capture_index(self.root)
        (self.root / "tracked").write_bytes(b"two")
        self.git("add", "tracked")
        self.git("update-index", "--chmod=+x", "--", "tracked")
        after = capture_index(self.root)
        self.assertNotEqual(before[0].object_id, after[0].object_id)
        self.assertEqual(after[0].mode, "100755")

    def test_capture_index_sorts_by_path_and_stage(self):
        (self.root / "z").write_bytes(b"z")
        (self.root / "a").write_bytes(b"a")
        self.git("add", "z", "a")
        entries = capture_index(self.root)
        self.assertEqual([entry.path for entry in entries], [b"a", b"tracked", b"z"])
        self.assertEqual([entry.stage for entry in entries], [0, 0, 0])

    def test_capture_index_preserves_raw_path_bytes(self):
        path = b"line\n\xff"
        fd = os.open(os.fsencode(self.root) + b"/" + path, os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            os.write(fd, b"raw")
        finally:
            os.close(fd)
        self.git("add", path)
        self.assertIn(path, [entry.path for entry in capture_index(self.root)])

    def test_capture_index_preserves_conflict_stages(self):
        self.git("checkout", "-qb", "side")
        (self.root / "tracked").write_bytes(b"side")
        self.git("commit", "-qam", "side")
        self.git("checkout", "-q", "-")
        (self.root / "tracked").write_bytes(b"main")
        self.git("commit", "-qam", "main")
        merge = subprocess.run(
            ("git", "-C", str(self.root), "merge", "side"),
            capture_output=True,
        )
        self.assertNotEqual(merge.returncode, 0)
        entries = capture_index(self.root)
        self.assertEqual([entry.stage for entry in entries], [1, 2, 3])

    def test_skip_worktree_and_gitlinks_are_rejected(self):
        self.git("update-index", "--skip-worktree", "--", "tracked")
        with self.assertRaises(RepositoryCaptureError):
            capture_index(self.root)
        self.git("update-index", "--no-skip-worktree", "--", "tracked")

        head = self.git("rev-parse", "HEAD").stdout.strip().decode("ascii")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},submodule")
        with self.assertRaises(RepositoryCaptureError):
            capture_index(self.root)

    def test_unborn_head_and_invalid_roots_are_rejected(self):
        unborn = Path(self.tmp.name) / "unborn"
        subprocess.run(("git", "init", "-q", str(unborn)), check=True)
        with self.assertRaises(RepositoryCaptureError):
            capture_head(unborn)

        with self.assertRaises(RepositoryCaptureError):
            capture_head(self.root / "nested")
        bare = Path(self.tmp.name) / "bare"
        subprocess.run(("git", "init", "--bare", "-q", str(bare)), check=True)
        with self.assertRaises(RepositoryCaptureError):
            capture_head(bare)

    def test_git_redirect_environment_is_ignored(self):
        with patch.dict(
            os.environ,
            {
                "GIT_DIR": str(self.root / "missing"),
                "GIT_INDEX_FILE": str(self.root / "missing-index"),
                "GIT_CONFIG_GLOBAL": str(self.root / "missing-global-config"),
                "GIT_CONFIG_NOSYSTEM": "1",
            },
        ):
            observed = capture_head(self.root)
        self.assertEqual(observed.commit, capture_head(self.root).commit)


if __name__ == "__main__":
    unittest.main()
