from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from kapisch_validation.manifest import parse_manifest
from kapisch_validation.models import Manifest, Node, State
from kapisch_validation.references import parse_state
from kapisch_validation.review_evidence import (
    CANONICAL_REVIEWER_PROFILE,
    LEGACY_REVIEWER_PROFILE,
    validate_review_evidence,
)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
FIXTURES = Path(__file__).parent / "fixtures"


def state_payload(head: str, marker: str = EMPTY_SHA256) -> str:
    return (
        f"head={head};index_sha256={marker};staged_diff_sha256={marker};"
        f"unstaged_diff_sha256={EMPTY_SHA256};status_sha256={EMPTY_SHA256};"
        f"relevant_untracked_count=0;relevant_untracked_sha256={EMPTY_SHA256}"
    )


class ReviewEvidenceTests(unittest.TestCase):
    def write_invocation(
        self,
        root: Path,
        *,
        overrides: dict[str, str | bool] | None = None,
        node_status: str = "complete",
        result_text: str | None = None,
    ) -> tuple[Manifest, State, Path]:
        invocation_id = "I1"
        overrides = overrides or {}
        fallback_ref = overrides.get("external_task_ref")
        if result_text is None:
            result_text = f"invocation_id={invocation_id}\nreview result\n"
            if (
                isinstance(fallback_ref, str)
                and fallback_ref != "unavailable"
                and overrides.get("identity_assurance")
                == "user-attested-external-reference"
            ):
                result_text += f"external_task_ref={fallback_ref}\n"
        result = root / "result.md"
        result.write_bytes(result_text.encode())
        working_state = state_payload("head")
        fields: dict[str, str | bool] = {
            "invocation_id": invocation_id,
            "mode": "review",
            "dispatch_mode": "runtime-named-spawn",
            "requested_role": "reviewer",
            "requested_profile": CANONICAL_REVIEWER_PROFILE,
            "task_name": "review-task",
            "dispatching_controller": "controller-task",
            "target": "staged",
            "base_revision": "base",
            "reviewed_revision": "head",
            "working_tree_state": working_state,
            "post_review_working_tree_state": working_state,
            "pre_dispatch_state_digest": hashlib.sha256(
                working_state.encode()
            ).hexdigest(),
            "post_review_state_digest": hashlib.sha256(
                working_state.encode()
            ).hexdigest(),
            "lifecycle_status": "completed",
            "expected_result_path": "result.md",
            "produced_result_path": "result.md",
            "result_encoding": "utf-8",
            "result_sha256": hashlib.sha256(result.read_bytes()).hexdigest(),
            "returned_role": "reviewer",
            "returned_profile": CANONICAL_REVIEWER_PROFILE,
            "returned_target": "staged",
            "returned_revision": "head",
            "returned_working_tree_state": working_state,
            "returned_decision": (
                "approve" if node_status == "complete" else "do-not-approve"
            ),
            "external_task_id": "unavailable",
            "external_task_url": "unavailable",
            "external_task_ref": "unavailable",
            "external_task_request": "unavailable",
            "identity_assurance": "observable-named-dispatch",
            "reviewer_selection_attested": False,
            "spawn_agent_type": "reviewer",
            "spawn_fork_turns": "none",
            "spawn_result_task_name": "review-task",
        }
        fields.update(overrides)
        invocation = root / "review.toml"
        lines = []
        for key, value in fields.items():
            if isinstance(value, bool):
                lines.append(f"{key}={'true' if value else 'false'}")
            else:
                lines.append(f"{key}={json.dumps(value)}")
        invocation.write_text("\n".join(lines) + "\n")
        implementation = Node("T01", 1, "behavioral", "complete", (), (), None, {})
        review = Node(
            "R01",
            2,
            "review",
            node_status,
            ("T01",),
            ("", "", "result.md", "review.toml"),
            {"terminal_node_ids": ["T01"]},
            {"executor_class": "reviewer", "model_tier": "high", "batching": "off"},
        )
        final = Node(
            "F01",
            3,
            "final",
            "pending",
            ("R01",),
            ("", "", "final.md", ""),
            None,
            {},
        )
        manifest = Manifest(
            2, "x", "base", {}, (implementation, review, final), "graph.toml"
        )
        completed = ("T01", "R01") if node_status == "complete" else ("T01",)
        failed = ("R01",) if node_status == "failed" else ()
        state = State(
            "x",
            "head",
            "running",
            completed,
            (),
            (),
            (),
            failed,
            "block:no-ready-node",
            {
                "latest_approving_review_path": "unavailable",
                "latest_approving_invocation_id": "unavailable",
            },
        )
        return manifest, state, invocation

    def validate_one(
        self,
        root: Path,
        *,
        overrides: dict[str, str | bool] | None = None,
        node_status: str = "complete",
        result_text: str | None = None,
    ) -> tuple[list, Path]:
        manifest, state, invocation = self.write_invocation(
            root,
            overrides=overrides,
            node_status=node_status,
            result_text=result_text,
        )
        return validate_review_evidence(manifest, state, root), invocation

    def assert_code(self, findings: list, code: str) -> None:
        self.assertTrue(
            any(error.code == code for error in findings),
            [error.code for error in findings],
        )

    def test_missing_dispatching_controller_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, state, invocation = self.write_invocation(root)
            invocation.write_text(
                invocation.read_text().replace(
                    'dispatching_controller="controller-task"\n', ""
                )
            )
            findings = validate_review_evidence(manifest, state, root)
        self.assert_code(findings, "TWV-SCHEMA-MISSING-FIELD")

    def test_missing_external_task_request_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, state, invocation = self.write_invocation(root)
            invocation.write_text(
                invocation.read_text().replace(
                    'external_task_request="unavailable"\n', ""
                )
            )
            findings = validate_review_evidence(manifest, state, root)
        self.assert_code(findings, "TWV-SCHEMA-MISSING-FIELD")

    def test_valid_runtime_named_invocation_passes(self) -> None:
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(Path(temporary))
        self.assertEqual(findings, [])

    def test_completed_legacy_reviewer_profile_evidence_remains_valid(self) -> None:
        for node_status in ("complete", "failed"):
            with (
                self.subTest(node_status=node_status),
                TemporaryDirectory() as temporary,
            ):
                findings, _ = self.validate_one(
                    Path(temporary),
                    node_status=node_status,
                    overrides={
                        "requested_profile": LEGACY_REVIEWER_PROFILE,
                        "returned_profile": LEGACY_REVIEWER_PROFILE,
                    },
                )
                self.assertEqual(findings, [])

    def test_legacy_reviewer_profile_is_rejected_for_noncompleted_evidence(self) -> None:
        for lifecycle in ("planned", "dispatched", "blocked", "failed"):
            with (
                self.subTest(lifecycle=lifecycle),
                TemporaryDirectory() as temporary,
            ):
                overrides = self.noncompleted_overrides(lifecycle, "unavailable")
                overrides["requested_profile"] = LEGACY_REVIEWER_PROFILE
                findings, _ = self.validate_one(
                    Path(temporary),
                    node_status="reviewing",
                    overrides=overrides,
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_completed_reviewer_profile_pair_must_match_a_supported_identity(self) -> None:
        for requested, returned in (
            (LEGACY_REVIEWER_PROFILE, CANONICAL_REVIEWER_PROFILE),
            (CANONICAL_REVIEWER_PROFILE, LEGACY_REVIEWER_PROFILE),
            (".codex/agents/other.toml", ".codex/agents/other.toml"),
        ):
            with (
                self.subTest(requested=requested, returned=returned),
                TemporaryDirectory() as temporary,
            ):
                findings, _ = self.validate_one(
                    Path(temporary),
                    overrides={
                        "requested_profile": requested,
                        "returned_profile": returned,
                    },
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_runtime_spawn_result_follows_lifecycle(self) -> None:
        valid = (
            ("planned", "unavailable"),
            ("dispatched", "unavailable"),
            ("dispatched", "review-task"),
        )
        for lifecycle, returned_name in valid:
            with (
                self.subTest(lifecycle=lifecycle, returned_name=returned_name),
                TemporaryDirectory() as temporary,
            ):
                findings, _ = self.validate_one(
                    Path(temporary),
                    node_status="reviewing",
                    overrides=self.noncompleted_overrides(lifecycle, returned_name),
                )
                self.assertFalse(
                    any(
                        error.code == "TWV-REVIEW-MALFORMED-ENVELOPE"
                        for error in findings
                    ),
                    findings,
                )
                if lifecycle == "dispatched":
                    self.assert_code(findings, "TWV-REVIEW-UNRESOLVED-DISPATCH")
                else:
                    self.assertEqual(findings, [])

    def test_noncompleted_invocation_rejects_populated_post_review_fields(self) -> None:
        for lifecycle in ("planned", "dispatched"):
            for field, value in (
                ("post_review_working_tree_state", state_payload("head")),
                (
                    "post_review_state_digest",
                    hashlib.sha256(state_payload("head").encode()).hexdigest(),
                ),
            ):
                with (
                    self.subTest(lifecycle=lifecycle, field=field),
                    TemporaryDirectory() as temporary,
                ):
                    overrides = self.noncompleted_overrides(
                        lifecycle, "unavailable"
                    )
                    overrides[field] = value
                    findings, _ = self.validate_one(
                        Path(temporary),
                        node_status="reviewing",
                        overrides=overrides,
                    )
                    self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

        invalid = (("planned", "review-task"), ("dispatched", "other-task"))
        for lifecycle, returned_name in invalid:
            with (
                self.subTest(lifecycle=lifecycle, returned_name=returned_name),
                TemporaryDirectory() as temporary,
            ):
                findings, _ = self.validate_one(
                    Path(temporary),
                    node_status="reviewing",
                    overrides=self.noncompleted_overrides(lifecycle, returned_name),
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_obsolete_assurance_fields_are_rejected(self) -> None:
        for alias in ("assurance_level", "assurance"):
            with self.subTest(alias=alias), TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest, state, invocation = self.write_invocation(root)
                invocation.write_text(
                    invocation.read_text() + f'{alias}="observable-named-dispatch"\n'
                )
                findings = validate_review_evidence(manifest, state, root)
                self.assert_code(findings, "TWV-SCHEMA-UNKNOWN-FIELD")

    def test_external_task_matching_dispatching_controller_is_rejected(self) -> None:
        cases = (
            self.external_overrides(external_task_id="controller-task"),
            self.external_overrides(external_task_url="controller-task"),
            self.external_overrides(external_task_ref="controller-task"),
            {**self.external_overrides(), "task_name": "controller-task"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(Path(temporary), overrides=overrides)
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def external_overrides(
        self,
        *,
        external_task_id: str = "external-123",
        external_task_url: str = "unavailable",
        external_task_ref: str = "unavailable",
        assurance: str = "external-named-task",
        external_task_request: str | None = None,
    ) -> dict[str, str | bool]:
        if external_task_request is None:
            external_task_request = "Review the staged target."
            if assurance == "user-attested-external-reference":
                external_task_request += f"\nexternal_task_ref={external_task_ref}\n"
        return {
            "dispatch_mode": "external-named-task",
            "external_task_id": external_task_id,
            "external_task_url": external_task_url,
            "external_task_ref": external_task_ref,
            "external_task_request": external_task_request,
            "identity_assurance": assurance,
            "reviewer_selection_attested": True,
            "spawn_agent_type": "unavailable",
            "spawn_fork_turns": "unavailable",
            "spawn_result_task_name": "unavailable",
        }

    def noncompleted_overrides(
        self, lifecycle: str, spawn_result_task_name: str
    ) -> dict[str, str]:
        return {
            "lifecycle_status": lifecycle,
            "post_review_working_tree_state": "unavailable",
            "post_review_state_digest": "unavailable",
            "produced_result_path": "unavailable",
            "result_sha256": "unavailable",
            "returned_role": "unavailable",
            "returned_profile": "unavailable",
            "returned_target": "unavailable",
            "returned_revision": "unavailable",
            "returned_working_tree_state": "unavailable",
            "returned_decision": "unavailable",
            "spawn_result_task_name": spawn_result_task_name,
        }

    def test_valid_external_runtime_identity_cases_pass(self) -> None:
        for overrides in (
            self.external_overrides(),
            self.external_overrides(
                external_task_id="unavailable",
                external_task_url="https://tasks.example/reviewer-123",
            ),
        ):
            with self.subTest(overrides=overrides), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(Path(temporary), overrides=overrides)
                self.assertEqual(findings, [])

    def test_valid_user_attested_external_fallback_passes(self) -> None:
        overrides = self.external_overrides(
            external_task_id="unavailable",
            external_task_ref="ext-review-123",
            assurance="user-attested-external-reference",
        )
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(Path(temporary), overrides=overrides)
        self.assertEqual(findings, [])

    def test_fallback_request_reference_must_be_one_exact_logical_line(self) -> None:
        reference = "ext-review-123"
        invalid_requests = (
            "Review the staged target.",
            "Review the staged target.\nexternal_task_ref=ext-review-124\n",
            "Review the staged target.\nexternal_task_ref=ext-review-1234\n",
            "Review the staged target.\nexternal_task_ref=ext-review-12\n",
            "Review the staged target.\nExternal_task_ref=ext-review-123\n",
            "Review the staged target.\nuse external_task_ref=ext-review-123\n",
            "Review the staged target.\n external_task_ref=ext-review-123\n",
            "Review the staged target.\nexternal_task_ref=ext-review-123\n"
            "external_task_ref=ext-review-123\n",
        )
        for request in invalid_requests:
            with self.subTest(request=request), TemporaryDirectory() as temporary:
                overrides = self.external_overrides(
                    external_task_id="unavailable",
                    external_task_ref=reference,
                    assurance="user-attested-external-reference",
                    external_task_request=request,
                )
                findings, _ = self.validate_one(Path(temporary), overrides=overrides)
                self.assert_code(findings, "TWV-REVIEW-REFERENCE-MISMATCH")

    def test_fallback_result_reference_must_be_one_exact_logical_line(self) -> None:
        reference = "ext-review-123"
        overrides = self.external_overrides(
            external_task_id="unavailable",
            external_task_ref=reference,
            assurance="user-attested-external-reference",
        )
        invalid_results = (
            "invocation_id=I1\nreview result\n",
            "invocation_id=I1\nexternal_task_ref=ext-review-124\n",
            "invocation_id=I1\nexternal_task_ref=ext-review-1234\n",
            "invocation_id=I1\nexternal_task_ref=ext-review-12\n",
            "invocation_id=I1\nExternal_task_ref=ext-review-123\n",
            "invocation_id=I1\nuse external_task_ref=ext-review-123\n",
            "invocation_id=I1\n external_task_ref=ext-review-123\n",
            "invocation_id=I1\nexternal_task_ref=ext-review-123\n"
            "external_task_ref=ext-review-123\n",
        )
        for result_text in invalid_results:
            with self.subTest(result=result_text), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary),
                    overrides=overrides,
                    result_text=result_text,
                )
                self.assert_code(findings, "TWV-REVIEW-REFERENCE-MISMATCH")
                self.assertFalse(
                    any(error.code == "TWV-REVIEW-STALE-EVIDENCE" for error in findings)
                )

    def test_fallback_reference_accepts_exact_crlf_lines(self) -> None:
        reference = "ext-review-123"
        request = f"Review the staged target.\r\nexternal_task_ref={reference}\r\n"
        result = f"invocation_id=I1\r\nexternal_task_ref={reference}\r\n"
        overrides = self.external_overrides(
            external_task_id="unavailable",
            external_task_ref=reference,
            assurance="user-attested-external-reference",
            external_task_request=request,
        )
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary), overrides=overrides, result_text=result
            )
        self.assertEqual(findings, [])

    def test_invalid_fallback_reference_grammar_is_rejected(self) -> None:
        for reference in (
            "ext-ab",
            "ext-Review-123",
            "ext_review_123",
            "ext-" + "a" * 81,
        ):
            with self.subTest(reference=reference), TemporaryDirectory() as temporary:
                overrides = self.external_overrides(
                    external_task_id="unavailable",
                    external_task_ref=reference,
                    assurance="user-attested-external-reference",
                )
                findings, _ = self.validate_one(Path(temporary), overrides=overrides)
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_runtime_reviewer_equal_to_controller_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary), overrides={"task_name": "controller-task"}
            )
        self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_assurance_and_dispatch_must_be_compatible(self) -> None:
        cases = (
            {"identity_assurance": "external-named-task"},
            self.external_overrides(assurance="observable-named-dispatch"),
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(Path(temporary), overrides=overrides)
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_lifecycle_status_uses_exact_enum(self) -> None:
        for lifecycle in ("complete", "in-progress", "reviewed"):
            with self.subTest(lifecycle=lifecycle), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary), overrides={"lifecycle_status": lifecycle}
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_mode_specific_decision_vocabulary(self) -> None:
        for decision in ("ready", "not-ready"):
            with self.subTest(decision=decision), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary), overrides={"returned_decision": decision}
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-sequential-v2", root)
            invocation = root / "reviews/final/00-final-invocation.toml"
            invocation.write_text(
                invocation.read_text().replace(
                    'returned_decision="ready"', 'returned_decision="approve"'
                )
            )
            manifest = parse_manifest(root / "02-execution-graph.toml").manifest
            state, state_errors = parse_state(root / "03-state.toml")
            self.assertEqual(state_errors, [])
            self.assertIsNotNone(manifest)
            self.assertIsNotNone(state)
            findings = validate_review_evidence(manifest, state, root)
        self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_completed_final_not_ready_maps_to_failed_node(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-sequential-v2", root)
            manifest_path = root / "02-execution-graph.toml"
            manifest_text = manifest_path.read_text()
            final_start = manifest_text.index('[[nodes]]\nid="F01"')
            prefix = manifest_text[:final_start]
            final = manifest_text[final_start:].replace(
                'status="complete"', 'status="failed"', 1
            )
            manifest_path.write_text(prefix + final)
            invocation = root / "reviews/final/00-final-invocation.toml"
            invocation.write_text(
                invocation.read_text().replace(
                    'returned_decision="ready"', 'returned_decision="not-ready"'
                )
            )
            state_path = root / "03-state.toml"
            state_text = state_path.read_text().replace(
                'workflow_status="complete"', 'workflow_status="running"'
            )
            state_text = state_text.replace(
                'completed_node_ids=["F01","R01","T01"]',
                'completed_node_ids=["R01","T01"]',
            ).replace("failed_node_ids=[]", 'failed_node_ids=["F01"]')
            state_path.write_text(state_text)
            manifest = parse_manifest(manifest_path).manifest
            state, state_errors = parse_state(state_path)
            self.assertEqual(state_errors, [])
            self.assertIsNotNone(manifest)
            self.assertIsNotNone(state)
            findings = validate_review_evidence(manifest, state, root)
        self.assertEqual(findings, [])

    def test_obsolete_decision_spelling_is_rejected(self) -> None:
        for decision in ("changes-requested", "not ready"):
            with self.subTest(decision=decision), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary), overrides={"returned_decision": decision}
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_result_digest_format_and_exact_bytes_are_validated(self) -> None:
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary), overrides={"result_sha256": "ABC"}
            )
        self.assert_code(findings, "TWV-REVIEW-INVALID-DIGEST")

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, state, _ = self.write_invocation(root)
            with (root / "result.md").open("ab") as result:
                result.write(b"changed")
            findings = validate_review_evidence(manifest, state, root)
        self.assert_code(findings, "TWV-REVIEW-STALE-EVIDENCE")

    def test_result_invocation_id_requires_one_exact_logical_line(self) -> None:
        invalid_results = (
            "review result\n",
            "invocation_id=I2\nreview result\n",
            "prefix invocation_id=I1\nreview result\n",
            "invocation_id=I1-suffix\nreview result\n",
            "invocation_id=I1\ninvocation_id=I1\nreview result\n",
        )
        for result_text in invalid_results:
            with self.subTest(result=result_text), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary), result_text=result_text
                )
                self.assert_code(findings, "TWV-REVIEW-MALFORMED-ENVELOPE")

    def test_result_invocation_id_accepts_lf_and_crlf(self) -> None:
        for result_text in (
            "invocation_id=I1\nreview result\n",
            "invocation_id=I1\r\nreview result\r\n",
        ):
            with self.subTest(result=result_text), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary), result_text=result_text
                )
                self.assertEqual(findings, [])

    def test_review_result_path_must_match_node_report(self) -> None:
        for field in ("expected_result_path", "produced_result_path"):
            with self.subTest(field=field), TemporaryDirectory() as temporary:
                findings, _ = self.validate_one(
                    Path(temporary), overrides={field: "other.md"}
                )
                self.assert_code(findings, "TWV-REVIEW-RESULT-PATH-MISMATCH")

    def test_planned_expected_result_path_must_match_node_report(self) -> None:
        overrides = self.noncompleted_overrides("planned", "unavailable")
        overrides["expected_result_path"] = "other.md"
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary), node_status="reviewing", overrides=overrides
            )
        self.assert_code(findings, "TWV-REVIEW-RESULT-PATH-MISMATCH")

    def test_final_result_path_must_match_node_report(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-sequential-v2", root)
            invocation = root / "reviews/final/00-final-invocation.toml"
            invocation.write_text(
                invocation.read_text().replace(
                    'expected_result_path="reviews/final/05-final.md"',
                    'expected_result_path="reviews/final/other.md"',
                )
            )
            manifest = parse_manifest(root / "02-execution-graph.toml").manifest
            state, state_errors = parse_state(root / "03-state.toml")
            self.assertEqual(state_errors, [])
            self.assertIsNotNone(manifest)
            self.assertIsNotNone(state)
            findings = validate_review_evidence(manifest, state, root)
        self.assert_code(findings, "TWV-REVIEW-RESULT-PATH-MISMATCH")

    def test_review_and_final_cannot_share_resolved_report_path(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-sequential-v2", root)
            manifest_path = root / "02-execution-graph.toml"
            manifest_path.write_text(
                manifest_path.read_text().replace(
                    'report="reviews/final/05-final.md"',
                    'report="reviews/final/../round-0/03-review.md"',
                )
            )
            manifest = parse_manifest(manifest_path).manifest
            state, state_errors = parse_state(root / "03-state.toml")
            self.assertEqual(state_errors, [])
            self.assertIsNotNone(manifest)
            self.assertIsNotNone(state)
            findings = validate_review_evidence(manifest, state, root)
        self.assert_code(findings, "TWV-REVIEW-RESULT-PATH-MISMATCH")

    def test_pre_and_post_state_payload_hashes_are_validated(self) -> None:
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary), overrides={"pre_dispatch_state_digest": "0" * 64}
            )
        self.assert_code(findings, "TWV-REVIEW-INVALID-DIGEST")

        malformed = state_payload("head").replace("index_sha256", "index")
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary), overrides={"post_review_working_tree_state": malformed}
            )
        self.assert_code(findings, "TWV-REVIEW-INVALID-GIT-STATE")

    def test_unequal_pre_and_post_state_is_stale(self) -> None:
        changed = state_payload("head", "1" * 64)
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(
                Path(temporary),
                overrides={
                    "post_review_working_tree_state": changed,
                    "post_review_state_digest": hashlib.sha256(
                        changed.encode()
                    ).hexdigest(),
                },
            )
        self.assert_code(findings, "TWV-REVIEW-STALE-EVIDENCE")

    def git_output(self, root: Path, *args: str) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, stdout=subprocess.PIPE
        ).stdout

    def git_snapshot(self, root: Path) -> tuple[str, bytes]:
        head = self.git_output(root, "rev-parse", "HEAD").decode().strip()
        index = self.git_output(root, "ls-files", "--stage", "-z")
        staged = self.git_output(
            root, "diff", "--cached", "--binary", "--full-index", "--no-ext-diff"
        )
        unstaged = self.git_output(
            root, "diff", "--binary", "--full-index", "--no-ext-diff"
        )
        status = self.git_output(
            root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        untracked = self.git_output(
            root, "ls-files", "--others", "--exclude-standard", "-z"
        )
        self.assertEqual(untracked, b"")
        payload = (
            f"head={head};index_sha256={hashlib.sha256(index).hexdigest()};"
            f"staged_diff_sha256={hashlib.sha256(staged).hexdigest()};"
            f"unstaged_diff_sha256={hashlib.sha256(unstaged).hexdigest()};"
            f"status_sha256={hashlib.sha256(status).hexdigest()};"
            "relevant_untracked_count=0;"
            f"relevant_untracked_sha256={hashlib.sha256(untracked).hexdigest()}"
        )
        return payload, status

    def test_same_path_staged_content_mutation_invalidates_freshness(self) -> None:
        with TemporaryDirectory() as temporary:
            git_root = Path(temporary) / "repo"
            git_root.mkdir()
            self.git_output(git_root, "init", "-q")
            self.git_output(git_root, "config", "user.email", "test@example.invalid")
            self.git_output(git_root, "config", "user.name", "Test")
            target = git_root / "tracked.txt"
            target.write_bytes(b"baseline\n")
            self.git_output(git_root, "add", "tracked.txt")
            self.git_output(git_root, "commit", "-q", "-m", "baseline")

            target.write_bytes(b"bytes A\n")
            self.git_output(git_root, "add", "tracked.txt")
            snapshot_a, status_a = self.git_snapshot(git_root)
            target.write_bytes(b"bytes B\n")
            self.git_output(git_root, "add", "tracked.txt")
            snapshot_b, status_b = self.git_snapshot(git_root)

            self.assertEqual(status_a, status_b)
            self.assertNotEqual(snapshot_a, snapshot_b)
            parts_a = dict(item.split("=", 1) for item in snapshot_a.split(";"))
            parts_b = dict(item.split("=", 1) for item in snapshot_b.split(";"))
            self.assertNotEqual(parts_a["index_sha256"], parts_b["index_sha256"])
            self.assertNotEqual(
                parts_a["staged_diff_sha256"], parts_b["staged_diff_sha256"]
            )
            self.assertNotEqual(
                hashlib.sha256(snapshot_a.encode()).hexdigest(),
                hashlib.sha256(snapshot_b.encode()).hexdigest(),
            )

            evidence_root = Path(temporary) / "evidence"
            evidence_root.mkdir()
            head = parts_a["head"]
            findings, _ = self.validate_one(
                evidence_root,
                overrides={
                    "reviewed_revision": head,
                    "returned_revision": head,
                    "working_tree_state": snapshot_a,
                    "returned_working_tree_state": snapshot_a,
                    "post_review_working_tree_state": snapshot_b,
                    "pre_dispatch_state_digest": hashlib.sha256(
                        snapshot_a.encode()
                    ).hexdigest(),
                    "post_review_state_digest": hashlib.sha256(
                        snapshot_b.encode()
                    ).hexdigest(),
                },
            )
        self.assert_code(findings, "TWV-REVIEW-STALE-EVIDENCE")

    def test_completed_final_requires_state_bound_approval(self) -> None:
        fixture = FIXTURES / "valid-sequential-v2"
        manifest = parse_manifest(fixture / "02-execution-graph.toml").manifest
        state, errors = parse_state(fixture / "03-state.toml")
        self.assertEqual(errors, [])
        self.assertIsNotNone(manifest)
        self.assertIsNotNone(state)
        mismatched_state = State(
            state.task_id,
            state.current_revision,
            state.workflow_status,
            state.completed,
            state.running,
            state.ready,
            state.blocked,
            state.failed,
            state.next_action,
            {**state.raw, "latest_approving_invocation_id": "I-OLD"},
        )
        findings = validate_review_evidence(manifest, mismatched_state, fixture)
        self.assert_code(findings, "TWV-REVIEW-FINAL-APPROVAL-MISMATCH")

    def test_completed_review_requires_approving_decision(self) -> None:
        with TemporaryDirectory() as temporary:
            findings, _ = self.validate_one(Path(temporary), node_status="failed")
        self.assertFalse(
            any(error.code == "TWV-REVIEW-LIFECYCLE-MISMATCH" for error in findings)
        )

    def test_missing_review_scope_is_rejected(self) -> None:
        node = Node(
            "R01",
            1,
            "review",
            "pending",
            (),
            ("", "", "review.md", ""),
            None,
            {},
        )
        manifest = Manifest(2, "x", "base", {}, (node,), "graph.toml")
        state = State(
            "x", "head", "running", (), (), (), (), (), "block:no-ready-node", {}
        )
        with TemporaryDirectory() as temporary:
            errors = validate_review_evidence(manifest, state, Path(temporary))
        self.assertEqual(errors[0].code, "TWV-REVIEW-MISSING-SCOPE")

    def test_malformed_invocation_envelope_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "review.toml").write_text('invocation_id = "I1"\n')
            node = Node(
                "R01",
                1,
                "review",
                "reviewing",
                (),
                ("", "", "review.md", "review.toml"),
                {"terminal_node_ids": []},
                {},
            )
            manifest = Manifest(2, "x", "base", {}, (node,), "graph.toml")
            state = State(
                "x", "head", "running", (), (), (), (), (), "block:no-ready-node", {}
            )
            errors = validate_review_evidence(manifest, state, root)
        self.assert_code(errors, "TWV-SCHEMA-MISSING-FIELD")

    def test_invocation_path_escape_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            node = Node(
                "R01",
                1,
                "review",
                "reviewing",
                (),
                ("", "", "review.md", "../x.toml"),
                {"terminal_node_ids": []},
                {},
            )
            manifest = Manifest(2, "x", "base", {}, (node,), "graph.toml")
            state = State(
                "x", "head", "running", (), (), (), (), (), "block:no-ready-node", {}
            )
            errors = validate_review_evidence(manifest, state, root)
        self.assert_code(errors, "TWV-REF-ARTIFACT")


if __name__ == "__main__":
    unittest.main()
