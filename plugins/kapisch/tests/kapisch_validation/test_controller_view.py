from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kapisch_validation.controller_view import render_controller_view, state_semantic_sha256

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[2]


class ControllerViewTests(unittest.TestCase):
    def test_state_binding_is_excluded_from_semantic_digest(self) -> None:
        state = {"task_id": "task", "controller_view_path": "04-controller-view.toml", "controller_view_sha256": "0" * 64}
        self.assertEqual(state_semantic_sha256(state), state_semantic_sha256(dict(state, controller_view_sha256="1" * 64)))

    def test_renderer_is_byte_deterministic(self) -> None:
        view = {"version": 1, "task_id": "task", "request": {"scope": "bounded"}, "predecessor_outcomes": []}
        self.assertEqual(render_controller_view(view), render_controller_view(view))

    def test_rebound_derived_mutations_fail(self) -> None:
        for needle, replacement in (
            ('source_plan = "01-plan.md"', 'source_plan = "wrong.md"'),
            ('risk = "unavailable"', 'risk = "high"'),
            ('assignment_id = "unavailable"', 'assignment_id = "wrong"'),
            ('predecessor_outcomes = []', 'predecessor_outcomes = [{lifecycle = "failed"}]'),
            ('next_action = "complete"', 'next_action = "block:wrong"'),
        ):
            with self.subTest(needle=needle), tempfile.TemporaryDirectory() as temp:
                task = Path(temp) / "task"; shutil.copytree(FIXTURES / "valid-v4-controller", task)
                view = task / "04-controller-view.toml"; data = view.read_text(); self.assertIn(needle, data)
                altered = data.replace(needle, replacement, 1); view.write_text(altered)
                digest = hashlib.sha256(view.read_bytes()).hexdigest(); state = task / "03-state.toml"
                state.write_text(state.read_text().replace('controller_view_sha256 = "' + hashlib.sha256(data.encode()).hexdigest() + '"', f'controller_view_sha256 = "{digest}"'))
                result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_kapisch.py"), "--task-dir", str(task), "--format", "json"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("TWV-VIEW-PROJECTION", result.stdout)


if __name__ == "__main__":
    unittest.main()
