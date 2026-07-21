from __future__ import annotations

import unittest

from kapisch_validation.models import Manifest, Node, State
from kapisch_validation.transitions import (
    determine_next_action,
    validate_lifecycle,
)


def manifest(status: str) -> Manifest:
    node = Node("T01", 1, "behavioral", status, (), (), None, {})
    return Manifest(2, "x", "base", {}, (node,), "graph.toml")


def state(action: str) -> State:
    return State("x", "head", "running", (), (), ("T01",), (), (), action, {})


class TransitionTests(unittest.TestCase):
    def test_selects_smallest_ready_node(self) -> None:
        self.assertEqual(
            determine_next_action(manifest("ready"), state("")), "select:T01"
        )

    def test_rejects_illegal_observed_transition(self) -> None:
        errors = validate_lifecycle(
            manifest("running"), state("resolve:T01"), manifest("complete")
        )
        self.assertEqual(errors[0].code, "TWV-LIFECYCLE-ILLEGAL-TRANSITION")

    def test_rejects_invalid_next_action_grammar(self) -> None:
        errors = validate_lifecycle(manifest("ready"), state("launch:T01"))
        self.assertEqual(errors[0].code, "TWV-LIFECYCLE-INVALID-NEXT-ACTION")

    def test_failed_behavioral_node_prevents_completion(self) -> None:
        failed = Node("T00", 1, "behavioral", "failed", (), (), None, {})
        implemented = Node("T01", 2, "behavioral", "complete", (), (), None, {})
        review = Node("R01", 3, "review", "complete", ("T01",), (), None, {})
        final = Node("F01", 4, "final", "complete", ("R01",), (), None, {})
        graph = Manifest(
            2,
            "x",
            "base",
            {},
            (failed, implemented, review, final),
            "graph.toml",
        )

        self.assertEqual(
            determine_next_action(graph, state("block:no-ready-node")),
            "block:no-ready-node",
        )


if __name__ == "__main__":
    unittest.main()
