import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))
_repository = importlib.import_module("kapisch_core.repository")
HeadIdentity = _repository.HeadIdentity
IndexEntry = _repository.IndexEntry
RepositoryStateFingerprint = _repository.RepositoryStateFingerprint
UntrackedEntry = _repository.UntrackedEntry
WorktreeEntry = _repository.WorktreeEntry
WorktreeFacts = _repository.WorktreeFacts
encode_fact = _repository.encode_fact
encode_git_path = _repository.encode_git_path


class RepositoryEncodingTests(unittest.TestCase):
    def test_git_paths_and_facts_are_canonical_bytes(self):
        self.assertEqual(encode_git_path(b"raw-\xff\n"), "7261772dff0a")
        head = HeadIdentity("sha1", "0" * 40)
        self.assertEqual(
            encode_fact(head),
            b'{"commit":"0000000000000000000000000000000000000000","object_format":"sha1"}\n',
        )
        index = IndexEntry(b"z\n", 0, "1" * 40, "100644")
        self.assertEqual(
            encode_fact(index),
            b'{"mode":"100644","object_id":"1111111111111111111111111111111111111111","path_hex":"7a0a","stage":0}\n',
        )

    def test_fingerprint_projection_is_sorted_and_schema_shaped(self):
        digest = "a" * 64
        state = RepositoryStateFingerprint(
            "sha1",
            "0" * 40,
            (IndexEntry(b"tracked", 0, "1" * 40, "100644"),),
            (WorktreeEntry(b"tracked", "file", "100644", digest),),
            (UntrackedEntry(b"extra", True, digest),),
        )
        self.assertEqual(
            state.canonical_bytes(),
            (
                b'{"head":"0000000000000000000000000000000000000000",'
                b'"index":[{"mode":"100644","object_id":"1111111111111111111111111111111111111111",'
                b'"path_hex":"747261636b6564","stage":0}],'
                b'"object_format":"sha1","untracked":[{"included":true,"path_hex":"6578747261",'
                b'"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],'
                b'"worktree":[{"kind":"file","mode":"100644","path_hex":"747261636b6564",'
                b'"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}\n'
            ),
        )
        facts = WorktreeFacts(
            (WorktreeEntry(b"tracked", "file", "100644", digest),),
            (UntrackedEntry(b"extra", True, digest),),
        )
        self.assertEqual(encode_fact(facts).count(b"\n"), 1)

    def test_closed_records_reject_unsafe_or_incomplete_values(self):
        with self.assertRaises((TypeError, ValueError)):
            encode_fact({"object_format": "sha1"})
        with self.assertRaises((TypeError, ValueError)):
            encode_git_path(bytearray(b"path"))
        with self.assertRaises(ValueError):
            encode_git_path(b"a/../b")
        with self.assertRaises(ValueError):
            WorktreeEntry(b"file", "file", "100644")
        with self.assertRaises(ValueError):
            UntrackedEntry(b"file", True)
        with self.assertRaises(ValueError):
            UntrackedEntry(b"file", False, "a" * 64)
        with self.assertRaises(ValueError):
            RepositoryStateFingerprint(
                "sha1",
                "0" * 40,
                (IndexEntry(b"index", 0, "2" * 64, "100644"),),
                (),
                (),
            )
        with self.assertRaises(ValueError):
            RepositoryStateFingerprint(
                "sha1",
                "0" * 40,
                (IndexEntry(b"z", 0, "1" * 40, "100644"), IndexEntry(b"a", 0, "2" * 40, "100644")),
                (),
                (),
            )


if __name__ == "__main__":
    unittest.main()
