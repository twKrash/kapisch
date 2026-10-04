import hashlib
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[2] / "core"))

_repository = importlib.import_module("kapisch_core.repository")
_repository_git = importlib.import_module("kapisch_core._repository_git")
_repository_worktree = importlib.import_module("kapisch_core._repository_worktree")
_repository_fingerprint = importlib.import_module(
    "kapisch_core._repository_fingerprint"
)
RepositoryCaptureError = _repository.RepositoryCaptureError
capture_head = _repository.capture_head
capture_index = _repository.capture_index
capture_worktree = _repository.capture_worktree
capture_repository_state = _repository.capture_repository_state


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
        return self.git_at(self.root, *args, **kwargs)

    def git_at(self, root, *args, **kwargs):
        return subprocess.run(
            ("git", "-C", str(root), *args),
            check=True,
            capture_output=True,
            **kwargs,
        )

    def _mutating_stat_before_final_path_stat(self, path, data):
        original_stat = _repository_worktree.os.stat
        calls = 0

        def mutate(name, *args, **kwargs):
            nonlocal calls
            if name == path:
                calls += 1
                if calls == 2:
                    (self.root / os.fsdecode(path)).write_bytes(data)
            return original_stat(name, *args, **kwargs)

        return patch.object(_repository_worktree.os, "stat", side_effect=mutate)

    def test_capture_head_binds_storage_format_and_commit(self):
        observed = capture_head(self.root)
        expected_format = (
            self.git("rev-parse", "--show-object-format=storage")
            .stdout.strip()
            .decode("ascii")
        )
        expected_commit = (
            self.git("rev-parse", "--verify", "HEAD").stdout.strip().decode("ascii")
        )
        self.assertEqual(observed.object_format, expected_format)
        self.assertEqual(observed.commit, expected_commit)

    def test_replacement_ref_cannot_mask_noncommit_head(self):
        blob = self.git("hash-object", "tracked").stdout.strip().decode("ascii")
        commit = self.git("rev-parse", "HEAD").stdout.strip().decode("ascii")
        self.git("update-ref", f"refs/replace/{blob}", commit)
        self.git("update-ref", "HEAD", blob)
        for capture in (capture_head, capture_index):
            with self.assertRaises(RepositoryCaptureError):
                capture(self.root)

    def test_lazy_fetch_and_transport_are_disabled(self):
        for caller_value in (None, "0"):
            with self.subTest(caller_value=caller_value):
                root = Path(self.tmp.name) / (f"missing-{caller_value or 'unset'}")
                root.mkdir()
                self.git_at(root, "init", "-q")
                self.git_at(root, "config", "user.email", "a@b")
                self.git_at(root, "config", "user.name", "a")
                (root / "tracked").write_bytes(b"one")
                self.git_at(root, "add", "tracked")
                self.git_at(root, "commit", "-qm", "initial")
                marker = root / "transport-marker"
                script = root / "ssh-marker.sh"
                script.write_text('#!/bin/sh\nprintf x >> "$KAPISCH_SSH_MARKER"\n')
                script.chmod(0o755)
                self.git_at(
                    root,
                    "remote",
                    "add",
                    "origin",
                    "ssh://example.invalid/repo",
                )
                self.git_at(root, "config", "remote.origin.promisor", "true")
                self.git_at(root, "config", "extensions.partialClone", "origin")
                self.git_at(root, "config", "core.sshCommand", str(script))
                missing = "f" * 40
                (root / ".git" / "HEAD").write_text(missing + "\n")
                env = {"KAPISCH_SSH_MARKER": str(marker)}
                if caller_value is not None:
                    env["GIT_NO_LAZY_FETCH"] = caller_value
                with patch.dict(os.environ, env):
                    if caller_value is None:
                        os.environ.pop("GIT_NO_LAZY_FETCH", None)
                    for capture in (capture_head, capture_index):
                        with self.assertRaises(RepositoryCaptureError):
                            capture(root)
                    self.assertFalse(marker.exists())
                    probe_env = os.environ.copy()
                    probe_env["GIT_NO_LAZY_FETCH"] = "1"
                    probe = subprocess.run(
                        ("git", "-C", str(root), "cat-file", "-e", missing),
                        env=probe_env,
                        capture_output=True,
                        check=False,
                    )
                    self.assertNotEqual(probe.returncode, 0)

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
        fd = os.open(
            os.fsencode(self.root) + b"/" + path,
            os.O_WRONLY | os.O_CREAT,
            0o644,
        )
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
            check=False,
        )
        self.assertNotEqual(merge.returncode, 0)
        entries = capture_index(self.root)
        self.assertEqual([entry.stage for entry in entries], [1, 2, 3])
        state = capture_worktree(self.root, entries)
        self.assertEqual([entry.path for entry in state.worktree], [b"tracked"])

    def test_skip_intent_and_gitlinks_are_rejected(self):
        self.git("update-index", "--skip-worktree", "--", "tracked")
        with self.assertRaises(RepositoryCaptureError):
            capture_index(self.root)
        self.git("update-index", "--no-skip-worktree", "--", "tracked")

        (self.root / "intent").touch()
        self.git("add", "-N", "intent")
        with self.assertRaises(RepositoryCaptureError):
            capture_index(self.root)
        self.git("reset", "-q", "--", "intent")

        head = self.git("rev-parse", "HEAD").stdout.strip().decode("ascii")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},submodule")
        with self.assertRaises(RepositoryCaptureError):
            capture_index(self.root)

    def test_untracked_scan_ignores_git_trace_environment(self):
        (self.root / "extra").write_bytes(b"extra")
        with patch.dict(os.environ, {"GIT_TRACE": "1"}):
            state = capture_worktree(self.root, capture_index(self.root))
        self.assertEqual([entry.path for entry in state.untracked], [b"extra"])

    def test_untracked_scan_rejects_stderr_warnings(self):
        (self.root / "extra").write_bytes(b"extra")
        original_run = _repository_git.subprocess.run

        def warn_on_untracked(command, *args, **kwargs):
            result = original_run(command, *args, **kwargs)
            if "ls-files" in command and "--others" in command:
                return subprocess.CompletedProcess(
                    result.args, result.returncode, result.stdout, b"warning"
                )
            return result

        with (
            patch.object(
                _repository_git.subprocess,
                "run",
                side_effect=warn_on_untracked,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, capture_index(self.root))

    def test_untracked_scan_uses_the_opened_worktree(self):
        (self.root / "extra").write_bytes(b"extra")
        self.git("config", "core.worktree", str(self.root))
        original_run = _repository_git.subprocess.run
        original_root = self.root.with_name(self.root.name + "-original")
        swapped = False

        def swap_worktree_for_scan(command, *args, **kwargs):
            nonlocal swapped
            if "ls-files" not in command or "--others" not in command:
                return original_run(command, *args, **kwargs)
            swapped = True
            self.root.rename(original_root)
            self.root.mkdir()
            try:
                original_run(
                    ("git", "-C", str(self.root), "init", "-q"),
                    check=True,
                    capture_output=True,
                )
                return original_run(command, *args, **kwargs)
            finally:
                shutil.rmtree(self.root)
                original_root.rename(self.root)

        with patch.object(
            _repository_git.subprocess, "run", side_effect=swap_worktree_for_scan
        ):
            state = capture_worktree(self.root, capture_index(self.root))
        self.assertTrue(swapped)
        self.assertEqual([entry.path for entry in state.untracked], [b"extra"])

    def test_leaf_observation_returns_explicit_kinds(self):
        (self.root / "directory").mkdir()
        os.mkfifo(self.root / "special")
        os.symlink("tracked", self.root / "link")
        rootfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            self.assertEqual(
                _repository_worktree._observe_leaf(rootfd, b"tracked").kind,
                "regular",
            )
            self.assertEqual(
                _repository_worktree._observe_leaf(rootfd, b"directory").kind,
                "directory",
            )
            self.assertEqual(
                _repository_worktree._observe_leaf(rootfd, b"link").kind,
                "symlink",
            )
            self.assertEqual(
                _repository_worktree._observe_leaf(rootfd, b"special").kind,
                "special",
            )
            self.assertEqual(
                _repository_worktree._observe_leaf(rootfd, b"missing").kind,
                "missing",
            )
        finally:
            os.close(rootfd)

    def test_worktree_digests_tracked_untracked_and_symlink_bytes(self):
        link = self.root / "link"
        os.symlink("tracked", link)
        self.git("add", "-A")
        self.git("commit", "-qm", "symlink")
        (self.root / "new").write_bytes(b"new")
        state = capture_worktree(self.root, capture_index(self.root), (b"new",))
        entries = {entry.path: entry for entry in state.worktree}
        self.assertEqual(entries[b"tracked"].kind, "file")
        self.assertEqual(
            entries[b"tracked"].sha256,
            hashlib.sha256(b"one").hexdigest(),
        )
        self.assertEqual(entries[b"link"].kind, "symlink")
        self.assertEqual(entries[b"link"].mode, "120000")
        self.assertEqual(
            entries[b"link"].sha256,
            hashlib.sha256(b"tracked").hexdigest(),
        )
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertTrue(untracked[b"new"].included)
        self.assertEqual(
            untracked[b"new"].sha256,
            hashlib.sha256(b"new").hexdigest(),
        )

    def test_worktree_chain_validation_does_not_rewalk_prefixes(self):
        current = self.root
        parts = []
        depth = 24
        for index in range(depth):
            current /= f"d{index}"
            current.mkdir()
            parts.append(f"d{index}".encode())
        (current / "file").write_bytes(b"payload")
        self.git("add", "d0")
        self.git("commit", "-qm", "deep")
        index = capture_index(self.root)
        original_stat = _repository_worktree.os.stat
        prefix_stats = 0

        def count_prefix_stats(name, *args, **kwargs):
            nonlocal prefix_stats
            if (
                kwargs.get("dir_fd") is not None
                and isinstance(name, bytes)
                and b"/" in name
            ):
                prefix_stats += 1
            return original_stat(name, *args, **kwargs)

        with patch.object(
            _repository_worktree.os, "stat", side_effect=count_prefix_stats
        ):
            state = capture_worktree(self.root, index)
        path = b"/".join(parts + [b"file"])
        self.assertEqual(state.worktree[0].path, path)
        self.assertLess(prefix_stats, depth)

    def test_worktree_rejects_ancestor_replacement_during_chain_validation(self):
        parent = self.root / "a"
        leaf = parent / "b" / "c" / "file"
        leaf.parent.mkdir(parents=True)
        leaf.write_bytes(b"old")
        self.git("add", "a")
        self.git("commit", "-qm", "chain")
        index = capture_index(self.root)
        original_open = _repository_worktree.os.open
        calls = 0

        def replace_before_later_component(name, flags, *args, **kwargs):
            nonlocal calls
            if name == b"b":
                calls += 1
                if calls == 3:
                    parent.rename(self.root / "old-a")
                    parent.mkdir()
                    (parent / "b" / "c").mkdir(parents=True)
                    (parent / "b" / "c" / "file").write_bytes(b"current")
            return original_open(name, flags, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "open",
                side_effect=replace_before_later_component,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_ancestor_replacement_on_final_chain_validation(
        self,
    ):
        parent = self.root / "a"
        leaf = parent / "b" / "c" / "file"
        leaf.parent.mkdir(parents=True)
        leaf.write_bytes(b"old")
        self.git("add", "a")
        self.git("commit", "-qm", "chain")
        index = capture_index(self.root)
        original_open = _repository_worktree.os.open
        calls = 0

        def replace_during_final_chain(name, flags, *args, **kwargs):
            nonlocal calls
            if name == b"b":
                calls += 1
                if calls == 5:
                    parent.rename(self.root / "old-a")
                    parent.mkdir()
                    (parent / "b" / "c").mkdir(parents=True)
                    (parent / "b" / "c" / "file").write_bytes(b"current")
            return original_open(name, flags, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "open",
                side_effect=replace_during_final_chain,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_ancestor_replacement_during_final_attachment(
        self,
    ):
        parent = self.root / "a"
        leaf = parent / "b" / "c" / "file"
        leaf.parent.mkdir(parents=True)
        leaf.write_bytes(b"old")
        self.git("add", "a")
        self.git("commit", "-qm", "chain")
        index = capture_index(self.root)
        original_stat = _repository_worktree.os.stat
        calls = 0

        def replace_during_attachment(name, *args, **kwargs):
            nonlocal calls
            if name == b"b" and kwargs.get("dir_fd") is not None:
                calls += 1
                if calls == 4:
                    parent.rename(self.root / "old-a")
                    parent.mkdir()
                    (parent / "b" / "c").mkdir(parents=True)
                    (parent / "b" / "c" / "file").write_bytes(b"current")
            return original_stat(name, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "stat",
                side_effect=replace_during_attachment,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_descendant_replacement_during_final_attachment(
        self,
    ):
        parent = self.root / "a"
        blocker = parent / "b"
        leaf = blocker / "c" / "file"
        leaf.parent.mkdir(parents=True)
        leaf.write_bytes(b"old")
        self.git("add", "a")
        self.git("commit", "-qm", "chain")
        index = capture_index(self.root)
        original_stat = _repository_worktree.os.stat
        calls = 0

        def replace_before_final_root_stat(name, *args, **kwargs):
            nonlocal calls
            if name == b"a" and kwargs.get("dir_fd") is not None:
                calls += 1
                if calls == 4:
                    blocker.rename(parent / "old-b")
                    blocker.mkdir()
                    (blocker / "c").mkdir(parents=True)
                    (blocker / "c" / "file").write_bytes(b"current")
            return original_stat(name, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "stat",
                side_effect=replace_before_final_root_stat,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_ancestor_replacement_during_final_metadata(
        self,
    ):
        parent = self.root / "a"
        leaf = parent / "b" / "c" / "file"
        leaf.parent.mkdir(parents=True)
        leaf.write_bytes(b"old")
        self.git("add", "a")
        self.git("commit", "-qm", "chain")
        index = capture_index(self.root)
        original_fstat = _repository_worktree.os.fstat
        calls = 0

        def replace_during_metadata(fd):
            nonlocal calls
            calls += 1
            if calls == 35:
                parent.rename(self.root / "old-a")
                parent.mkdir()
                (parent / "b" / "c").mkdir(parents=True)
                (parent / "b" / "c" / "file").write_bytes(b"current")
            return original_fstat(fd)

        with (
            patch.object(
                _repository_worktree.os,
                "fstat",
                side_effect=replace_during_metadata,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_binds_symlink_read_to_observed_inode(self):
        link = self.root / "link"
        os.symlink("initial", link)
        self.git("add", "link")
        self.git("commit", "-qm", "symlink-race")
        index = capture_index(self.root)
        original_readlink = _repository_worktree.os.readlink

        def read_transient_target(name, *args, **kwargs):
            if name != b"link":
                return original_readlink(name, *args, **kwargs)
            saved = self.root / "link-saved"
            link.rename(saved)
            os.symlink("transient", link)
            try:
                return original_readlink(name, *args, **kwargs)
            finally:
                link.unlink()
                saved.rename(link)

        with patch.object(
            _repository_worktree.os,
            "readlink",
            side_effect=read_transient_target,
        ):
            state = capture_worktree(self.root, index)
        entry = {item.path: item for item in state.worktree}[b"link"]
        self.assertEqual(
            entry.sha256,
            hashlib.sha256(b"initial").hexdigest(),
        )

    def test_worktree_rejects_endpoint_disappearance_during_observation(self):
        link = self.root / "link"
        os.symlink("tracked", link)
        self.git("add", "link")
        self.git("commit", "-qm", "endpoint")
        index = capture_index(self.root)
        original_stat = _repository_worktree.os.stat
        calls = 0

        def remove_before_final_stat(name, *args, **kwargs):
            nonlocal calls
            if name == b"link":
                calls += 1
                if calls == 2:
                    link.unlink()
            return original_stat(name, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os, "stat", side_effect=remove_before_final_stat
            ),
            self.assertRaisesRegex(RepositoryCaptureError, "replacement race"),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_tracked_same_inode_mutation_before_final_stat(self):
        with (
            self._mutating_stat_before_final_path_stat(b"tracked", b"two"),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, capture_index(self.root))

    def test_worktree_rejects_included_same_inode_mutation_before_final_stat(self):
        (self.root / "included").write_bytes(b"one")
        with (
            self._mutating_stat_before_final_path_stat(b"included", b"two"),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, capture_index(self.root), (b"included",))

    def test_worktree_treats_symlink_parent_as_tracked_deletion(self):
        nested = self.root / "dir"
        nested.mkdir()
        (nested / "child").write_bytes(b"child")
        self.git("add", "dir")
        self.git("commit", "-qm", "nested")
        (nested / "child").unlink()
        nested.rmdir()
        os.symlink("nowhere", nested)

        state = capture_worktree(self.root, capture_index(self.root))
        tracked = {entry.path: entry for entry in state.worktree}
        self.assertEqual(tracked[b"dir/child"].kind, "deletion")
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertFalse(untracked[b"dir"].included)

    def test_worktree_modes_deletions_and_unincluded_inventory(self):
        self.git("update-index", "--chmod=+x", "--", "tracked")
        os.chmod(self.root / "tracked", 0o755)
        (self.root / "extra").write_bytes(b"extra")
        state = capture_worktree(self.root, capture_index(self.root))
        tracked = {entry.path: entry for entry in state.worktree}
        self.assertEqual(tracked[b"tracked"].mode, "100755")
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertFalse(untracked[b"extra"].included)
        self.assertNotIn("sha256", untracked[b"extra"])

        (self.root / "tracked").unlink()
        deleted = capture_worktree(self.root, capture_index(self.root))
        entry = {item.path: item for item in deleted.worktree}[b"tracked"]
        self.assertEqual(entry.kind, "deletion")
        self.assertEqual(entry.mode, "000000")
        self.assertNotIn("sha256", entry.to_dict())

    def test_worktree_treats_directory_at_tracked_leaf_as_deletion(self):
        tracked = self.root / "tracked"
        tracked.unlink()
        tracked.mkdir()
        (tracked / "new").write_bytes(b"new")

        state = capture_worktree(self.root, capture_index(self.root))
        entries = {entry.path: entry for entry in state.worktree}
        self.assertEqual(entries[b"tracked"].kind, "deletion")
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertFalse(untracked[b"tracked/new"].included)

    def test_worktree_treats_non_directory_parent_as_tracked_deletion(self):
        nested = self.root / "dir"
        nested.mkdir()
        (nested / "child").write_bytes(b"child")
        self.git("add", "dir")
        self.git("commit", "-qm", "nested")
        (nested / "child").unlink()
        nested.rmdir()
        nested.write_bytes(b"replacement")

        state = capture_worktree(self.root, capture_index(self.root))
        tracked = {entry.path: entry for entry in state.worktree}
        self.assertEqual(tracked[b"dir/child"].kind, "deletion")
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertFalse(untracked[b"dir"].included)

    def test_unincluded_paths_are_inventory_only(self):
        (self.root / "extra").write_bytes(b"extra")
        original_observe = _repository_worktree._observe_leaf

        def reject_extra(rootfd, path):
            if path == b"extra":
                raise AssertionError("unincluded path was read")
            return original_observe(rootfd, path)

        with patch.object(
            _repository_worktree, "_observe_leaf", side_effect=reject_extra
        ):
            state = capture_worktree(self.root, capture_index(self.root))
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertFalse(untracked[b"extra"].included)

    def test_included_untracked_paths_require_regular_files(self):
        os.symlink("tracked", self.root / "link")
        with self.assertRaises(RepositoryCaptureError):
            capture_worktree(self.root, capture_index(self.root), (b"link",))

    def test_untracked_embedded_repository_directory_marker_is_normalized(self):
        nested = self.root / "nested"
        nested.mkdir()
        self.git_at(nested, "init", "-q")
        state = capture_worktree(self.root, capture_index(self.root))
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertIn(b"nested", untracked)
        self.assertFalse(untracked[b"nested"].included)

    def test_untracked_inventory_preserves_raw_paths_and_ignores_files(self):
        raw_path = b"raw-\n\xff"
        fd = os.open(
            os.fsencode(self.root) + b"/" + raw_path,
            os.O_WRONLY | os.O_CREAT,
            0o644,
        )
        try:
            os.write(fd, b"raw")
        finally:
            os.close(fd)
        (self.root / ".gitignore").write_text("ignored\n")
        (self.root / "ignored").write_bytes(b"ignored")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "ignore")
        state = capture_worktree(self.root, capture_index(self.root), (raw_path,))
        paths = {entry.path: entry for entry in state.untracked}
        self.assertTrue(paths[raw_path].included)
        self.assertNotIn(b"ignored", paths)

    def test_worktree_rejects_malformed_index(self):
        with self.assertRaises(RepositoryCaptureError):
            capture_worktree(self.root, (object(),))

    def test_worktree_rejects_replaced_enotdir_parent_during_observation(self):
        parent = self.root / "a"
        parent.mkdir()
        (parent / "b").write_bytes(b"blocker")
        rootfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        original_verify = _repository_worktree._verify_non_directory
        replaced = False

        def replace_after_verify(parentfd, name):
            nonlocal replaced
            result = original_verify(parentfd, name)
            if not replaced:
                replaced = True
                parent.rename(self.root / "old-a")
                parent.mkdir()
                (parent / "b").write_bytes(b"replacement")
            return result

        try:
            with (
                patch.object(
                    _repository_worktree,
                    "_verify_non_directory",
                    side_effect=replace_after_verify,
                ),
                self.assertRaises(RepositoryCaptureError),
            ):
                _repository_worktree._observe_leaf(rootfd, b"a/b/file")
        finally:
            os.close(rootfd)
        self.assertTrue(parent.is_dir())
        self.assertTrue((self.root / "old-a").is_dir())

    def test_worktree_rejects_blocker_parent_replacement_during_capture(self):
        cases = ((b"regular", False), (b"symlink", True))
        for parent_name, _ in cases:
            parent = self.root / os.fsdecode(parent_name)
            leaf = parent / "b" / "file"
            leaf.parent.mkdir(parents=True)
            leaf.write_bytes(b"tracked")
        self.git("add", "regular", "symlink")
        self.git("commit", "-qm", "blockers")

        def assert_rejected(parent_name, symlink_blocker):
            parent = self.root / os.fsdecode(parent_name)
            leaf = parent / "b" / "file"
            leaf.unlink()
            leaf.parent.rmdir()
            if symlink_blocker:
                os.symlink("missing", parent / "b")
            else:
                (parent / "b").write_bytes(b"old")
            index = tuple(
                entry
                for entry in capture_index(self.root)
                if entry.path == parent_name + b"/b/file"
            )
            original_verify = _repository_worktree._verify_non_directory
            original_stat = _repository_worktree.os.stat
            verify_calls = 0
            stat_calls = 0

            def replace_during_final_check(
                parentfd,
                name,
                *,
                original_verify=original_verify,
                original_stat=original_stat,
            ):
                nonlocal verify_calls, stat_calls
                verify_calls += 1
                if verify_calls != 2:
                    return original_verify(parentfd, name)

                def mutate(
                    name_arg,
                    *args,
                    parent=parent,
                    parent_name=parent_name,
                    original_stat=original_stat,
                    **kwargs,
                ):
                    nonlocal stat_calls
                    if name_arg == b"b":
                        stat_calls += 1
                        if stat_calls == 2:
                            parent.rename(
                                self.root / (os.fsdecode(parent_name) + "-old")
                            )
                            parent.mkdir()
                            (parent / "b").mkdir()
                            (parent / "b" / "file").write_bytes(b"current")
                    return original_stat(name_arg, *args, **kwargs)

                with patch.object(_repository_worktree.os, "stat", side_effect=mutate):
                    return original_verify(parentfd, name)

            with (
                patch.object(
                    _repository_worktree,
                    "_verify_non_directory",
                    side_effect=replace_during_final_check,
                ),
                self.assertRaises(RepositoryCaptureError),
            ):
                capture_worktree(self.root, index)
            self.assertEqual((parent / "b" / "file").read_bytes(), b"current")

        for parent_name, symlink_blocker in cases:
            with self.subTest(parent_name=parent_name):
                assert_rejected(parent_name, symlink_blocker)

    def test_worktree_rejects_missing_parent_replacement_during_capture(self):
        parent = self.root / "a"
        leaf = parent / "b" / "file"
        leaf.parent.mkdir(parents=True)
        leaf.write_bytes(b"tracked")
        self.git("add", "a")
        self.git("commit", "-qm", "nested")
        leaf.unlink()
        leaf.parent.rmdir()
        index = capture_index(self.root)
        original_open = _repository_worktree.os.open
        calls = 0

        def replace_before_final_missing(name, flags, *args, **kwargs):
            nonlocal calls
            if name == b"b":
                calls += 1
                if calls == 2:
                    parent.rename(self.root / "old-a")
                    parent.mkdir()
                    (parent / "b").mkdir()
                    (parent / "b" / "file").write_bytes(b"replacement")
            return original_open(name, flags, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "open",
                side_effect=replace_before_final_missing,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_directory_parent_replacement_during_capture(self):
        parent = self.root / "a"
        leaf = parent / "child"
        leaf.parent.mkdir()
        leaf.write_bytes(b"tracked")
        self.git("add", "a")
        self.git("commit", "-qm", "directory")
        leaf.unlink()
        leaf.mkdir()
        index = capture_index(self.root)
        original_stat = _repository_worktree.os.stat
        calls = 0

        def replace_before_final_directory_stat(name, *args, **kwargs):
            nonlocal calls
            if name == b"child":
                calls += 1
                if calls == 2:
                    parent.rename(self.root / "old-a")
                    parent.mkdir()
                    (parent / "child").mkdir()
            return original_stat(name, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "stat",
                side_effect=replace_before_final_directory_stat,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_symlink_parent_replacement_during_capture(self):
        parent = self.root / "a"
        leaf = parent / "link"
        leaf.parent.mkdir()
        leaf.write_bytes(b"tracked")
        self.git("add", "a")
        self.git("commit", "-qm", "symlink")
        leaf.unlink()
        os.symlink("target", leaf)
        index = capture_index(self.root)
        original_stat = _repository_worktree.os.stat
        calls = 0

        def replace_before_final_symlink_stat(name, *args, **kwargs):
            nonlocal calls
            if name == b"link":
                calls += 1
                if calls == 2:
                    parent.rename(self.root / "old-a")
                    parent.mkdir()
                    os.symlink("target", parent / "link")
            return original_stat(name, *args, **kwargs)

        with (
            patch.object(
                _repository_worktree.os,
                "stat",
                side_effect=replace_before_final_symlink_stat,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_worktree(self.root, index)

    def test_worktree_rejects_replaced_parent_during_observation(self):
        parent = self.root / "a"
        parent.mkdir()
        (parent / "old-child").write_bytes(b"old")
        rootfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        original_open = _repository_worktree.os.open
        replaced = False

        def replace_parent(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == b"b" and not replaced:
                replaced = True
                parent.rename(self.root / "old-a")
                parent.mkdir()
            return original_open(name, flags, *args, **kwargs)

        try:
            with (
                patch.object(
                    _repository_worktree.os, "open", side_effect=replace_parent
                ),
                self.assertRaises(RepositoryCaptureError),
            ):
                _repository_worktree._observe_leaf(rootfd, b"a/b/file")
        finally:
            os.close(rootfd)
        self.assertTrue(parent.is_dir())
        self.assertTrue((self.root / "old-a").is_dir())

    def test_unborn_head_and_invalid_roots_are_rejected(self):
        unborn = Path(self.tmp.name) / "unborn"
        subprocess.run(("git", "init", "-q", str(unborn)), check=True)
        with self.assertRaises(RepositoryCaptureError):
            capture_head(unborn)

        for capture in (capture_head, capture_index):
            with self.assertRaises(RepositoryCaptureError):
                capture(self.root / "nested")
        bare = Path(self.tmp.name) / "bare"
        subprocess.run(("git", "init", "--bare", "-q", str(bare)), check=True)
        for capture in (capture_head, capture_index):
            with self.assertRaises(RepositoryCaptureError):
                capture(bare)

    def test_newline_and_non_utf8_root_paths_are_supported(self):
        raw_root = os.fsencode(self.tmp.name) + b"/root-\n-\xff"
        os.mkdir(raw_root)
        root = Path(os.fsdecode(raw_root))
        self.git_at(root, "init", "-q")
        self.git_at(root, "config", "user.email", "a@b")
        self.git_at(root, "config", "user.name", "a")
        (root / "tracked").write_bytes(b"one")
        self.git_at(root, "add", "tracked")
        self.git_at(root, "commit", "-qm", "initial")

        self.assertEqual(capture_head(root).object_format, "sha1")
        index = capture_index(root)
        self.assertEqual(len(index), 1)
        self.assertEqual(len(capture_worktree(root, index).worktree), 1)

    def test_capture_index_disables_local_and_global_fsmonitor_hooks(self):
        marker = Path(self.tmp.name) / "fsmonitor-marker"
        script = Path(self.tmp.name) / "fsmonitor.sh"
        script.write_text('#!/bin/sh\nprintf x >> "$KAPISCH_FSMONITOR_MARKER"\n')
        script.chmod(0o755)
        with patch.dict(os.environ, {"KAPISCH_FSMONITOR_MARKER": str(marker)}):
            self.git("config", "core.fsmonitor", str(script))
            self.git("update-index", "--fsmonitor")
            marker.unlink(missing_ok=True)
            capture_index(self.root)
            self.assertFalse(marker.exists())

            home = Path(self.tmp.name) / "home"
            home.mkdir()
            (home / ".gitconfig").write_text(f"[core]\n\tfsmonitor = {script}\n")
            global_root = Path(self.tmp.name) / "global-repo"
            global_root.mkdir()
            self.git_at(global_root, "init", "-q")
            self.git_at(global_root, "config", "user.email", "a@b")
            self.git_at(global_root, "config", "user.name", "a")
            (global_root / "tracked").write_bytes(b"one")
            self.git_at(global_root, "add", "tracked")
            self.git_at(global_root, "commit", "-qm", "initial")
            subprocess.run(
                (
                    "git",
                    "-c",
                    "core.fsmonitor=false",
                    "-C",
                    str(global_root),
                    "update-index",
                    "--fsmonitor",
                ),
                check=True,
                capture_output=True,
            )
            marker.unlink(missing_ok=True)
            with patch.dict(os.environ, {"HOME": str(home)}):
                capture_index(global_root)
            self.assertFalse(marker.exists())

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
            observed_head = capture_head(self.root)
            observed_index = capture_index(self.root)
        self.assertEqual(observed_head.commit, capture_head(self.root).commit)
        self.assertEqual(len(observed_index), 1)


class RepositoryFingerprintTests(unittest.TestCase):
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

    def test_public_capture_returns_closed_fingerprint(self):
        state = capture_repository_state(self.root)
        self.assertIsInstance(state, _repository.RepositoryStateFingerprint)
        self.assertEqual(state.object_format, "sha1")
        self.assertEqual(state.worktree[0].path, b"tracked")
        self.assertEqual(state.as_dict(), state.as_dict())
        self.assertEqual(state.canonical_bytes(), state.canonical_bytes())

    def test_staged_blob_change_changes_fingerprint(self):
        before = capture_repository_state(self.root)
        (self.root / "tracked").write_bytes(b"two")
        self.git("add", "tracked")
        after = capture_repository_state(self.root)
        self.assertNotEqual(before.canonical_bytes(), after.canonical_bytes())
        self.assertNotEqual(before.index[0].object_id, after.index[0].object_id)

    def test_worktree_and_included_untracked_bytes_are_bound(self):
        os.symlink("tracked", self.root / "link")
        self.git("add", "link")
        self.git("commit", "-qm", "symlink")
        (self.root / "new").write_bytes(b"new")
        state = capture_repository_state(self.root, (b"new",))
        entries = {entry.path: entry for entry in state.worktree}
        self.assertEqual(entries[b"link"].kind, "symlink")
        untracked = {entry.path: entry for entry in state.untracked}
        self.assertTrue(untracked[b"new"].included)
        self.assertEqual(
            untracked[b"new"].sha256,
            hashlib.sha256(b"new").hexdigest(),
        )

    def test_capture_rejects_head_change_before_second_index(self):
        original = _repository_fingerprint.capture_head
        calls = 0

        def change_head_after_observation(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 3:
                self.git("commit", "--allow-empty", "-qm", "late")
            return result

        with (
            patch.object(
                _repository_fingerprint,
                "capture_head",
                side_effect=change_head_after_observation,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_repository_state(self.root)
        self.assertEqual(calls, 4)

    def test_capture_rejects_index_change_before_second_worktree(self):
        original = _repository_fingerprint.capture_worktree
        calls = 0

        def change_index_before_observation(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.git("update-index", "--chmod=+x", "--", "tracked")
            return original(*args, **kwargs)

        with (
            patch.object(
                _repository_fingerprint,
                "capture_worktree",
                side_effect=change_index_before_observation,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_repository_state(self.root)
        self.assertEqual(calls, 2)

    def test_capture_rejects_skip_worktree_change_before_second_worktree(self):
        original = _repository_fingerprint.capture_worktree
        calls = 0

        def change_flags_before_observation(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.git("update-index", "--skip-worktree", "--", "tracked")
            return original(*args, **kwargs)

        with (
            patch.object(
                _repository_fingerprint,
                "capture_worktree",
                side_effect=change_flags_before_observation,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_repository_state(self.root)
        self.assertEqual(calls, 2)

    def test_unincluded_untracked_paths_are_inventory_only(self):
        (self.root / "build.log").write_bytes(b"changing")
        state = capture_repository_state(self.root)
        entry = next(x for x in state.untracked if x.path == b"build.log")
        self.assertFalse(entry.included)
        self.assertIsNone(entry.sha256)

    def test_capture_rejects_unmerged_index(self):
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
        with self.assertRaises(RepositoryCaptureError):
            capture_repository_state(self.root)

    def test_capture_rejects_unborn_and_bare_repositories(self):
        unborn = Path(self.tmp.name) / "unborn"
        subprocess.run(("git", "init", "-q", str(unborn)), check=True)
        with self.assertRaises(RepositoryCaptureError):
            capture_repository_state(unborn)
        bare = Path(self.tmp.name) / "bare"
        subprocess.run(("git", "init", "--bare", "-q", str(bare)), check=True)
        with self.assertRaises(RepositoryCaptureError):
            capture_repository_state(bare)

    def test_capture_ignores_inherited_git_redirects(self):
        old = os.environ.copy()
        os.environ.update(
            {
                "GIT_DIR": str(self.root / "missing"),
                "GIT_INDEX_FILE": str(self.root / "missing-index"),
                "GIT_WORK_TREE": str(self.root / "elsewhere"),
            }
        )
        try:
            captured = capture_repository_state(self.root)
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertEqual(captured.head, capture_repository_state(self.root).head)

    def test_capture_rejects_changes_between_passes(self):
        original = _repository_fingerprint.capture_worktree
        calls = 0

        def mutate_after_first(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                (self.root / "tracked").write_bytes(b"changed")
            return result

        with (
            patch.object(
                _repository_fingerprint,
                "capture_worktree",
                side_effect=mutate_after_first,
            ),
            self.assertRaises(RepositoryCaptureError),
        ):
            capture_repository_state(self.root)
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
