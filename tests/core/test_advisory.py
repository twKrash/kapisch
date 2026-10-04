from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kapisch_core.advisory import ProposedScopeRef, load_proposed_scope, propose_scope


class ProposedScopeTests(unittest.TestCase):
    def test_vectors_ordering_idempotence_and_cold_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            ref = propose_scope(repo, "run", "scope", "requirements", {"mode": "keys", "keys": ["a", "é"]})
            identity = "b61ebccd955f591b6391c2a7e467bee6be5db577d40d4b1c128e73da609d6fd3"
            data = b'{"applicability":{"keys":["a","\xc3\xa9"],"mode":"keys"},"origin_run_id":"run","protocol_version":3,"requirements":"requirements","scope_contract":"applicability-scope/1","scope_id":"scope"}\n'
            self.assertEqual(ref, ProposedScopeRef("run", "scope", "30060f54ad1cfbc7b1f1cdd465a43a9c14ab7cd8a7335e9f225a724d316a8ff7"))
            self.assertEqual((repo / ".kapisch/v3/authority/scopes" / f"{identity}.json").read_bytes(), data)
            self.assertEqual(propose_scope(repo, "run", "scope", "requirements", {"mode": "keys", "keys": ["a", "é"]}), ref)
            script = "from pathlib import Path; from kapisch_core.advisory import load_proposed_scope; import json; print(json.dumps(load_proposed_scope(Path(r'%s'), %s)))" % (repo, json.dumps(ref.__dict__))
            self.assertEqual(json.loads(subprocess.check_output([sys.executable, "-c", script], env={"PYTHONPATH": "core"}))["scope_id"], "scope")
            (repo / ".kapisch/v3/runs/run").mkdir(parents=True)
            import shutil
            shutil.rmtree(repo / ".kapisch/v3/runs/run")
            self.assertEqual(load_proposed_scope(repo, ref)["origin_run_id"], "run")

    def test_validation_collision_and_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            ref = propose_scope(repo, "run", "s", "r", {"mode": "all"})
            for applicability in ({"mode": "all", "keys": []}, {"mode": "keys", "keys": []}, {"mode": "keys", "keys": ["é", "a"]}, {"mode": "keys", "keys": ["a", "a"]}, {"mode": "other"}):
                with self.subTest(applicability=applicability), self.assertRaises(ValueError):
                    propose_scope(repo, "x", "s", "r", applicability)
            with self.assertRaises(ValueError):
                propose_scope(repo, "run", "s", "changed", {"mode": "all"})
            with self.assertRaises(ValueError):
                load_proposed_scope(repo, {"origin_run_id": "wrong", "scope_id": "s", "sha256": ref.sha256})
            path = next((repo / ".kapisch/v3/authority/scopes").glob("*.json"))
            path.write_bytes(path.read_bytes().replace(b'"requirements":"r"', b'"requirements":"x"'))
            with self.assertRaises(ValueError):
                load_proposed_scope(repo, ref)


if __name__ == "__main__":
    unittest.main()
