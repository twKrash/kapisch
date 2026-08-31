from __future__ import annotations

import unittest

from kapisch_validation.controller_view import state_semantic_sha256


class ControllerViewTests(unittest.TestCase):
    def test_state_binding_is_excluded_from_semantic_digest(self) -> None:
        state = {
            "task_id": "task",
            "controller_view_path": "04-controller-view.toml",
            "controller_view_sha256": "0" * 64,
        }
        changed = dict(state, controller_view_sha256="1" * 64)
        self.assertEqual(state_semantic_sha256(state), state_semantic_sha256(changed))


if __name__ == "__main__":
    unittest.main()
