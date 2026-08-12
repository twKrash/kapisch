from __future__ import annotations

import unittest

from kapisch_validation.models import Manifest, Node, State
from kapisch_validation.transitions import (
    determine_next_action,
    validate_lifecycle,
    validate_transition,
)


def snapshot_node(
    node_id: str = "T01",
    *,
    sequence: int = 1,
    kind: str = "behavioral",
    status: str = "pending",
    depends_on: tuple[str, ...] = (),
    **raw_overrides: object,
) -> Node:
    raw: dict[str, object] = {
        "id": node_id,
        "sequence": sequence,
        "title": f"{node_id} title",
        "kind": kind,
        "risk": "low",
        "status": status,
        "depends_on": list(depends_on),
        "brief": f"tasks/{node_id}-brief.md",
        "context": f"tasks/{node_id}-context.md",
        "report": f"tasks/{node_id}-report.md",
        "reads": [],
        "writes": [],
        "shared_resources": [],
        "verification": [],
        "context_refs": [],
        "executor_class": "implementer",
        "model_tier": "standard",
        "batching": "off",
        "delegation_ids": [],
    }
    raw.update(raw_overrides)
    paths = tuple(
        str(raw.get(field, ""))
        for field in ("brief", "context", "report", "reviewer_invocation")
    )
    review_scope = raw.get("review_scope")
    return Node(
        str(raw["id"]),
        int(raw["sequence"]),
        str(raw["kind"]),
        str(raw["status"]),
        tuple(raw["depends_on"]),
        paths,
        review_scope if isinstance(review_scope, dict) else None,
        raw,
    )


def snapshot_manifest(
    *nodes: Node,
    version: int = 3,
    task_id: str = "x",
    base_revision: str = "base",
    source_plan: str = "01-plan.md",
    policies: dict[str, object] | None = None,
) -> Manifest:
    return Manifest(
        version,
        task_id,
        base_revision,
        {"execution": "sequential"} if policies is None else policies,
        tuple(nodes),
        "graph.toml",
        source_plan,
    )


def manifest(status: str) -> Manifest:
    return snapshot_manifest(snapshot_node(status=status), version=2, policies={})


def state(
    action: str,
    workflow_status: str = "running",
    **raw_overrides: object,
) -> State:
    raw: dict[str, object] = {
        "task_id": "x",
        "source_plan": "01-plan.md",
        "base_revision": "base",
        "current_revision": "head",
        "workflow_status": workflow_status,
        "completed_node_ids": [],
        "running_node_ids": [],
        "ready_node_ids": ["T01"],
        "blocked_node_ids": [],
        "failed_node_ids": [],
        "latest_approving_review_path": "unavailable",
        "latest_approving_invocation_id": "unavailable",
        "current_fix_round": 0,
        "max_fix_rounds": 1,
        "next_action": action,
    }
    raw.update(raw_overrides)
    return State(
        str(raw["task_id"]),
        str(raw["current_revision"]),
        str(raw["workflow_status"]),
        tuple(raw["completed_node_ids"]),
        tuple(raw["running_node_ids"]),
        tuple(raw["ready_node_ids"]),
        tuple(raw["blocked_node_ids"]),
        tuple(raw["failed_node_ids"]),
        str(raw["next_action"]),
        raw,
    )


class TransitionTests(unittest.TestCase):
    def test_selects_smallest_ready_node(self) -> None:
        self.assertEqual(
            determine_next_action(manifest("ready"), state("")), "select:T01"
        )

    def test_rejects_illegal_observed_transition(self) -> None:
        errors = validate_transition(
            manifest("running"), state("resolve:T01"), manifest("complete"), state("complete")
        )
        self.assertEqual(errors[0].code, "TWV-LIFECYCLE-ILLEGAL-TRANSITION")

    def test_rejects_manifest_contract_changes(self) -> None:
        previous = snapshot_manifest(snapshot_node())
        cases = (
            ("version", snapshot_manifest(snapshot_node(), version=2)),
            ("task_id", snapshot_manifest(snapshot_node(), task_id="other")),
            (
                "base_revision",
                snapshot_manifest(snapshot_node(), base_revision="other"),
            ),
            (
                "source_plan",
                snapshot_manifest(snapshot_node(), source_plan="other-plan.md"),
            ),
            (
                "policies",
                snapshot_manifest(
                    snapshot_node(), policies={"execution": "sequential", "dispatch": "auto"}
                ),
            ),
        )
        for reference, current in cases:
            with self.subTest(reference=reference):
                errors = validate_transition(
                    current,
                    state("select:T01"),
                    previous,
                    state("select:T01"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == reference
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_removed_previous_node(self) -> None:
        errors = validate_transition(
            snapshot_manifest(),
            state("block:no-ready-node"),
            snapshot_manifest(snapshot_node()),
            state("select:T01"),
        )
        self.assertEqual(
            [
                (error.code, error.reference)
                for error in errors
                if error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
            ],
            [("TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT", "nodes[T01]")],
        )

    def test_rejects_renamed_completed_node(self) -> None:
        errors = validate_transition(
            snapshot_manifest(snapshot_node("T02", status="pending")),
            state("select:T02"),
            snapshot_manifest(snapshot_node("T01", status="complete")),
            state("complete", "complete"),
        )
        self.assertTrue(
            any(
                error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and error.reference == "nodes[T01]"
                for error in errors
            ),
            errors,
        )

    def test_rejects_graph_field_changes_with_node_and_field_reference(self) -> None:
        previous = snapshot_manifest(snapshot_node(depends_on=("T00",)))
        cases = (
            ("sequence", snapshot_node(sequence=2, depends_on=("T00",))),
            ("kind", snapshot_node(kind="fix", depends_on=("T00",))),
            ("depends_on", snapshot_node(depends_on=("T00", "T99"))),
        )
        for field, changed_node in cases:
            with self.subTest(field=field):
                errors = validate_transition(
                    snapshot_manifest(changed_node),
                    state("select:T01"),
                    previous,
                    state("select:T01"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == f"nodes[T01].{field}"
                        for error in errors
                    ),
                    errors,
                )

    def test_dependency_order_is_not_a_semantic_change(self) -> None:
        previous = snapshot_manifest(snapshot_node(depends_on=("T00", "T99")))
        current = snapshot_manifest(snapshot_node(depends_on=("T99", "T00")))
        self.assertEqual(
            validate_transition(
                current,
                state("select:T01"),
                previous,
                state("select:T01"),
            ),
            [],
        )

    def test_rejects_completed_node_artifact_and_reviewer_rebinding(self) -> None:
        previous_node = snapshot_node(
            "R01",
            kind="review",
            status="complete",
            report="reviews/round-0/03-review.md",
            reviewer_invocation="reviews/round-0/00-review-invocation.toml",
        )
        cases = (
            (
                "report",
                snapshot_node(
                    "R01",
                    kind="review",
                    status="complete",
                    report="reviews/round-1/03-review.md",
                    reviewer_invocation="reviews/round-0/00-review-invocation.toml",
                ),
            ),
            (
                "reviewer_invocation",
                snapshot_node(
                    "R01",
                    kind="review",
                    status="complete",
                    report="reviews/round-0/03-review.md",
                    reviewer_invocation="reviews/round-1/00-review-invocation.toml",
                ),
            ),
        )
        for field, current_node in cases:
            with self.subTest(field=field):
                errors = validate_transition(
                    snapshot_manifest(current_node),
                    state("complete", "complete"),
                    snapshot_manifest(previous_node),
                    state("complete", "complete"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == f"nodes[R01].{field}"
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_terminal_node_evidence_replacement_or_detachment(self) -> None:
        evidence = [
            {
                "id": "V01",
                "check": "tests",
                "result": "pass",
                "evidence_ref": "tasks/T01-report.md",
                "output_sha256": "abc",
                "revision": "head",
            }
        ]
        previous_node = snapshot_node(
            status="complete",
            revision={"base": "base", "head": "head"},
            assignment={"id": "A-T01-1", "schema_version": 1},
            verification_evidence=evidence,
        )
        cases = (
            (
                "assignment",
                snapshot_node(
                    status="complete",
                    revision={"base": "base", "head": "head"},
                    assignment={"id": "A-T01-2", "schema_version": 1},
                    verification_evidence=evidence,
                ),
            ),
            (
                "verification_evidence",
                snapshot_node(
                    status="complete",
                    revision={"base": "base", "head": "head"},
                    assignment={"id": "A-T01-1", "schema_version": 1},
                    verification_evidence=[],
                ),
            ),
        )
        for field, current_node in cases:
            with self.subTest(field=field):
                errors = validate_transition(
                    snapshot_manifest(current_node),
                    state("complete", "complete"),
                    snapshot_manifest(previous_node),
                    state("complete", "complete"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == f"nodes[T01].{field}"
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_rebinding_completed_workflow_state(self) -> None:
        graph = snapshot_manifest(snapshot_node(status="complete"))
        previous_state = state(
            "complete",
            "complete",
            latest_approving_review_path="reviews/round-0/03-review.md",
            latest_approving_invocation_id="I-REVIEW-1",
        )
        cases = (
            ("current_revision", {"current_revision": "other-head"}),
            (
                "latest_approving_review_path",
                {"latest_approving_review_path": "reviews/round-1/03-review.md"},
            ),
            (
                "latest_approving_invocation_id",
                {"latest_approving_invocation_id": "I-REVIEW-2"},
            ),
            ("current_fix_round", {"current_fix_round": 1}),
        )
        for reference, changed in cases:
            with self.subTest(reference=reference):
                state_values = {
                    "latest_approving_review_path": "reviews/round-0/03-review.md",
                    "latest_approving_invocation_id": "I-REVIEW-1",
                }
                state_values.update(changed)
                current_state = state(
                    "complete",
                    "complete",
                    **state_values,
                )
                errors = validate_transition(
                    graph, current_state, graph, previous_state
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == reference
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_new_node_without_a_graph_amendment_protocol(self) -> None:
        previous_node = snapshot_node("T01", sequence=1, status="ready")
        forbidden_statuses = (
            "running",
            "implemented",
            "reviewing",
            "complete",
            "blocked",
            "failed",
            "cancelled",
        )
        for forbidden_status in forbidden_statuses:
            with self.subTest(status=forbidden_status):
                current = snapshot_manifest(
                    previous_node,
                    snapshot_node("T02", sequence=2, status=forbidden_status),
                )
                errors = validate_transition(
                    current,
                    state("select:T01"),
                    snapshot_manifest(previous_node),
                    state("select:T01"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == "nodes[T02]"
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_backdated_new_node_without_a_graph_amendment_protocol(self) -> None:
        previous_node = snapshot_node("T01", sequence=2, status="ready")
        current = snapshot_manifest(
            snapshot_node("T02", sequence=1, status="pending"),
            previous_node,
        )
        errors = validate_transition(
            current,
            state("select:T01"),
            snapshot_manifest(previous_node),
            state("select:T01"),
        )
        self.assertTrue(
            any(
                error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and error.reference == "nodes[T02]"
                for error in errors
            ),
            errors,
        )

    def test_rejects_append_only_graph_growth_without_an_amendment_protocol(self) -> None:
        previous_node = snapshot_node("T01", sequence=1, status="ready")
        for initial_status in ("pending", "ready"):
            with self.subTest(status=initial_status):
                current = snapshot_manifest(
                    previous_node,
                    snapshot_node("T02", sequence=2, status=initial_status),
                )
                errors = validate_transition(
                    current,
                    state("select:T01"),
                    snapshot_manifest(previous_node),
                    state("select:T01"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        and error.reference == "nodes[T02]"
                        for error in errors
                    ),
                    errors,
                )

    def test_unchanged_completed_snapshot_is_idempotent(self) -> None:
        graph = snapshot_manifest(
            snapshot_node(
                status="complete",
                revision={"base": "base", "head": "head"},
                verification_evidence=[{"id": "V01", "result": "pass"}],
            )
        )
        completed_state = state(
            "complete",
            "complete",
            latest_approving_review_path="reviews/round-0/03-review.md",
            latest_approving_invocation_id="I-REVIEW-1",
        )
        self.assertEqual(
            validate_transition(graph, completed_state, graph, completed_state), []
        )

    def test_allows_legal_status_progression_with_structure_preserved(self) -> None:
        previous = snapshot_manifest(snapshot_node(status="ready"))
        current = snapshot_manifest(
            snapshot_node(
                status="running",
                assignment={"id": "A-T01-1", "schema_version": 1},
                verification_evidence=[],
            )
        )
        self.assertEqual(
            validate_transition(
                current,
                state("resolve:T01", current_revision="work-head"),
                previous,
                state("select:T01"),
            ),
            [],
        )

    def test_rejects_runtime_binding_replacement_before_terminal_status(self) -> None:
        previous = snapshot_manifest(
            snapshot_node(
                status="running",
                assignment={"id": "A-T01-1", "schema_version": 1},
                verification_evidence=[{"id": "V01", "result": "pass"}],
            )
        )
        current = snapshot_manifest(
            snapshot_node(
                status="implemented",
                assignment={"id": "A-T01-2", "schema_version": 1},
                verification_evidence=[],
            )
        )
        errors = validate_transition(
            current,
            state("resolve:T01"),
            previous,
            state("resolve:T01"),
        )
        self.assertTrue(
            any(
                error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and error.reference == "nodes[T01].assignment"
                for error in errors
            ),
            errors,
        )

    def test_allows_runtime_evidence_and_attempt_advancement_before_transition(self) -> None:
        assignment = {
            "id": "A-T01-1",
            "schema_version": 1,
            "execution_class": "bounded",
            "attempts": [
                {
                    "id": "AT-T01-1",
                    "source_revision": "base",
                    "context_scope_ref": "A-T01-1",
                    "status": "running",
                    "verification": [],
                }
            ],
            "escalations": [],
        }
        previous = snapshot_manifest(
            snapshot_node(status="running", assignment=assignment, verification_evidence=[])
        )
        current_assignment = {
            **assignment,
            "attempts": [
                {
                    **assignment["attempts"][0],
                    "status": "complete",
                    "verification": ["tests"],
                }
            ],
        }
        current = snapshot_manifest(
            snapshot_node(
                status="implemented",
                assignment=current_assignment,
                verification_evidence=[{"id": "V01", "result": "pass"}],
            )
        )
        self.assertEqual(
            validate_transition(
                current,
                state("resolve:T01"),
                previous,
                state("resolve:T01"),
            ),
            [],
        )

    def test_rejects_removal_of_persisted_runtime_records(self) -> None:
        assignment = {
            "id": "A-T01-1",
            "schema_version": 1,
            "attempts": [
                {
                    "id": "AT-T01-1",
                    "source_revision": "base",
                    "context_scope_ref": "A-T01-1",
                    "status": "running",
                    "verification": [],
                }
            ],
            "escalations": [],
        }
        previous = snapshot_manifest(
            snapshot_node(
                status="running",
                assignment=assignment,
                verification_evidence=[{"id": "V01", "result": "pass"}],
            )
        )
        current = snapshot_manifest(
            snapshot_node(
                status="implemented",
                assignment={**assignment, "attempts": []},
                verification_evidence=[],
            )
        )
        errors = validate_transition(
            current,
            state("resolve:T01"),
            previous,
            state("resolve:T01"),
        )
        self.assertEqual(
            {
                error.reference
                for error in errors
                if error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
            },
            {"nodes[T01].assignment.attempts", "nodes[T01].verification_evidence"},
        )

    def test_rejects_attempt_rollback_and_duplicate_runtime_id(self) -> None:
        attempt = {
            "id": "AT-T01-1",
            "source_revision": "base",
            "context_scope_ref": "A-T01-1",
            "status": "complete",
            "verification": ["tests"],
        }
        assignment = {
            "id": "A-T01-1",
            "schema_version": 1,
            "attempts": [attempt],
            "escalations": [],
        }
        previous = snapshot_manifest(
            snapshot_node(
                status="running",
                assignment=assignment,
                verification_evidence=[{"id": "V01", "result": "pass"}],
            )
        )
        rollback = snapshot_manifest(
            snapshot_node(
                status="implemented",
                assignment={
                    **assignment,
                    "attempts": [{**attempt, "status": "running", "verification": []}],
                },
                verification_evidence=[{"id": "V01", "result": "pass"}],
            )
        )
        duplicate = snapshot_manifest(
            snapshot_node(
                status="implemented",
                assignment=assignment,
                verification_evidence=[
                    {"id": "V01", "result": "fail"},
                    {"id": "V01", "result": "pass"},
                ],
            )
        )
        for current in (rollback, duplicate):
            with self.subTest(current=current):
                errors = validate_transition(
                    current,
                    state("resolve:T01"),
                    previous,
                    state("resolve:T01"),
                )
                self.assertTrue(
                    any(
                        error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                        for error in errors
                    ),
                    errors,
                )

    def test_allows_monotonic_batch_outcome_advancement(self) -> None:
        batch = {
            "id": "B-T01-1",
            "member_node_ids": ["T01"],
            "member_assignment_ids": ["A-T01-1"],
            "member_outcomes": ["pending"],
            "outcome": "pending",
        }
        previous = snapshot_manifest(snapshot_node(status="running", batch=batch))
        current = snapshot_manifest(
            snapshot_node(
                status="implemented",
                batch={**batch, "member_outcomes": ["complete"], "outcome": "complete"},
            )
        )
        self.assertEqual(
            validate_transition(
                current,
                state("resolve:T01"),
                previous,
                state("resolve:T01"),
            ),
            [],
        )

    def test_rejects_fix_round_rollback_while_running(self) -> None:
        graph = snapshot_manifest(snapshot_node(status="ready"))
        errors = validate_transition(
            graph,
            state("select:T01", current_fix_round=0),
            graph,
            state("select:T01", current_fix_round=1),
        )
        self.assertTrue(
            any(
                error.code == "TWV-LIFECYCLE-INCOMPATIBLE-SNAPSHOT"
                and error.reference == "current_fix_round"
                for error in errors
            ),
            errors,
        )

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
        errors = validate_transition(
            manifest("ready"),
            state("select:T01", "running"),
            manifest("ready"),
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
        errors = validate_transition(
            empty_v1,
            complete_state,
            empty_v1,
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
