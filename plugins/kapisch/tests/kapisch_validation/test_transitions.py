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


def state(action: str, workflow_status: str = "running") -> State:
    return State(
        "x",
        "head",
        workflow_status,
        (),
        (),
        ("T01",),
        (),
        (),
        action,
        {},
    )


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

    def test_workflow_status_and_terminal_action_must_agree(self) -> None:
        cases = (
            ("running", "complete"),
            ("complete", "select:T01"),
        )
        for workflow_status, action in cases:
            with self.subTest(workflow_status=workflow_status, action=action):
                errors = validate_lifecycle(
                    manifest("ready"), state(action, workflow_status)
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-WORKFLOW-STATUS"
                        for error in errors
                    ),
                    errors,
                )

    def test_valid_running_and_complete_pairs_have_no_status_finding(self) -> None:
        running_errors = validate_lifecycle(
            manifest("ready"), state("select:T01", "running")
        )
        empty_v1 = Manifest(1, "x", "base", {}, (), "graph.toml")
        complete_state = State(
            "x", "head", "complete", (), (), (), (), (), "complete", {}
        )
        complete_errors = validate_lifecycle(empty_v1, complete_state)
        for errors in (running_errors, complete_errors):
            self.assertFalse(
                any(
                    error.code == "TWV-LIFECYCLE-WORKFLOW-STATUS"
                    for error in errors
                ),
                errors,
            )

    def test_complete_workflow_cannot_transition_back_to_running(self) -> None:
        errors = validate_lifecycle(
            manifest("ready"),
            state("select:T01", "running"),
            previous_state=state("complete", "complete"),
        )
        self.assertTrue(
            any(
                error.code == "TWV-LIFECYCLE-ILLEGAL-WORKFLOW-TRANSITION"
                for error in errors
            ),
            errors,
        )

    def test_running_workflow_may_transition_to_complete(self) -> None:
        empty_v1 = Manifest(1, "x", "base", {}, (), "graph.toml")
        complete_state = State(
            "x", "head", "complete", (), (), (), (), (), "complete", {}
        )
        errors = validate_lifecycle(
            empty_v1,
            complete_state,
            previous_state=state("block:no-ready-node", "running"),
        )
        self.assertFalse(
            any(
                error.code == "TWV-LIFECYCLE-ILLEGAL-WORKFLOW-TRANSITION"
                for error in errors
            ),
            errors,
        )

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
