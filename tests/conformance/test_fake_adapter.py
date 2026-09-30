from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from kapisch_core.bundle import verify_bundle
from kapisch_core.capabilities import CapabilityClaim, CapabilityClaims, CapabilityStatus
from kapisch_core.domain import (
    CapabilityEffect,
    ExecutionClass,
    Gate,
    LogicalTier,
    ProposedAction,
    ReviewScope,
    Role,
    Stage,
    Workflow,
)
from fake_adapter import FakeHarnessAdapter
from tooling.conformance.adapter import (
    HumanActionReceipt,
    HumanActionTarget,
    RuntimeProfile,
    human_receipt_matches,
)

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = ROOT / "core/dist/core-bundle.json"
BUNDLE_BYTES = BUNDLE_PATH.read_bytes()
BUNDLE_DIGEST = hashlib.sha256(BUNDLE_BYTES).hexdigest()


class FakeAdapterTests(unittest.TestCase):
    def test_compiles_exactly_six_roles_from_verified_bundle(self) -> None:
        bundle = verify_bundle(BUNDLE_BYTES, BUNDLE_DIGEST)
        assets, manifest = FakeHarnessAdapter().compile(
            BUNDLE_BYTES, BUNDLE_DIGEST, RuntimeProfile("test")
        )

        self.assertEqual(len(assets), 6)
        self.assertEqual(
            {asset.path for asset in assets},
            {f"agents/kapisch-{role}.md" for role in bundle.payload["roles"]},
        )
        for asset in assets:
            role = Path(asset.path).stem.removeprefix("kapisch-")
            self.assertEqual(asset.content, bundle.payload["roles"][role]["contract"].encode())
        self.assertEqual(json.loads(manifest)["bundle_digest"], BUNDLE_DIGEST)

    def test_manifest_declares_capability_statuses(self) -> None:
        statuses = tuple(CapabilityStatus)
        claims = CapabilityClaims(
            claims=tuple(
                CapabilityClaim(effect, statuses[index % len(statuses)])
                for index, effect in enumerate(CapabilityEffect)
            ),
            mutation_free_reviewer=CapabilityStatus.ADVISORY,
        )
        _, manifest = FakeHarnessAdapter(claims).compile(
            BUNDLE_BYTES, BUNDLE_DIGEST, RuntimeProfile("test")
        )
        declared = set(json.loads(manifest)["capabilities"]["effects"].values())
        self.assertEqual(declared, {status.value for status in statuses})
        self.assertEqual(
            json.loads(manifest)["capabilities"]["mutation_free_reviewer"],
            CapabilityStatus.ADVISORY.value,
        )

    def test_rejects_altered_bundle_digest(self) -> None:
        altered = BUNDLE_BYTES + b" "
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            FakeHarnessAdapter().compile(altered, BUNDLE_DIGEST, RuntimeProfile("test"))

    def test_compiler_never_reads_host_directories(self) -> None:
        adapter = FakeHarnessAdapter()
        with patch("builtins.open", side_effect=AssertionError("filesystem read")), patch(
            "pathlib.Path.open", side_effect=AssertionError("filesystem read")
        ):
            assets, _ = adapter.compile(BUNDLE_BYTES, BUNDLE_DIGEST, RuntimeProfile("test"))
        self.assertEqual(len(assets), 6)

    def test_manifest_and_assets_are_byte_stable(self) -> None:
        adapter = FakeHarnessAdapter()
        profile = RuntimeProfile("test")
        first = adapter.compile(BUNDLE_BYTES, BUNDLE_DIGEST, profile)
        second = adapter.compile(BUNDLE_BYTES, BUNDLE_DIGEST, profile)
        self.assertEqual(first, second)

    def test_profiles_do_not_change_role_contracts(self) -> None:
        adapter = FakeHarnessAdapter()
        assets_a, manifest_a = adapter.compile(BUNDLE_BYTES, BUNDLE_DIGEST, RuntimeProfile("alpha"))
        assets_b, manifest_b = adapter.compile(BUNDLE_BYTES, BUNDLE_DIGEST, RuntimeProfile("beta"))
        self.assertEqual(assets_a, assets_b)
        self.assertNotEqual(json.loads(manifest_a)["profile_id"], json.loads(manifest_b)["profile_id"])

    def test_descriptive_metadata_cannot_override_static_policy(self) -> None:
        adapter = FakeHarnessAdapter(
            CapabilityClaims(
                claims=(CapabilityClaim(CapabilityEffect.REPOSITORY_WRITE, CapabilityStatus.UNKNOWN),)
            )
        )
        action = ProposedAction(
            stage=Stage.IMPLEMENT,
            role=Role.IMPLEMENTER,
            execution_class=ExecutionClass.BOUNDED,
            tier=LogicalTier.STANDARD,
            effect=CapabilityEffect.REPOSITORY_WRITE,
        )
        metadata_cases = (
            None,
            {"new_field": "unknown"},
            {"stages": ["design"]},
            {"permission": "allow", "capabilities": ["enforced"]},
        )
        for metadata in metadata_cases:
            with self.subTest(metadata=metadata):
                result = adapter.evaluate_action(
                    BUNDLE_BYTES, BUNDLE_DIGEST, Workflow.TASK, action, workflow_metadata=metadata
                )
                self.assertFalse(result.admissible)
                self.assertIn("repository-write-capability-not-enforced", result.violations)

        allowed_action = ProposedAction(stage=Stage.RESEARCH, role=Role.RESEARCHER)
        for metadata in metadata_cases:
            with self.subTest(allowed_metadata=metadata):
                result = adapter.evaluate_action(
                    BUNDLE_BYTES, BUNDLE_DIGEST, Workflow.TASK, allowed_action,
                    workflow_metadata=metadata,
                )
                self.assertTrue(result.admissible, result.violations)

    def test_unsupported_effect_is_blocked(self) -> None:
        adapter = FakeHarnessAdapter(
            CapabilityClaims(
                claims=(CapabilityClaim(CapabilityEffect.REPOSITORY_READ, CapabilityStatus.UNSUPPORTED),)
            )
        )
        action = ProposedAction(stage=Stage.RESEARCH, role=Role.RESEARCHER)
        result = adapter.evaluate_action(BUNDLE_BYTES, BUNDLE_DIGEST, Workflow.TASK, action)
        self.assertFalse(result.admissible)
        self.assertIn("unsupported-capability-effect", result.violations)

    def test_missing_enforced_reviewer_blocks_approval(self) -> None:
        adapter = FakeHarnessAdapter()
        action = ProposedAction(
            stage=Stage.REVIEW,
            role=Role.REVIEWER,
            review_scope=ReviewScope.ITERATION,
            gate=Gate.APPROVAL,
        )
        result = adapter.evaluate_action(BUNDLE_BYTES, BUNDLE_DIGEST, Workflow.TASK, action)
        self.assertFalse(result.admissible)
        self.assertIn("reviewer-mutation-free-capability-not-enforced", result.violations)

    def test_unknown_capability_does_not_downgrade_policy(self) -> None:
        adapter = FakeHarnessAdapter()
        action = ProposedAction(
            stage=Stage.IMPLEMENT,
            role=Role.IMPLEMENTER,
            execution_class=ExecutionClass.BOUNDED,
            tier=LogicalTier.STANDARD,
            effect=CapabilityEffect.REPOSITORY_WRITE,
        )
        result = adapter.evaluate_action(BUNDLE_BYTES, BUNDLE_DIGEST, Workflow.TASK, action)
        self.assertFalse(result.admissible)
        self.assertIn("repository-write-capability-not-enforced", result.violations)

    def test_human_receipt_requires_observed_origin_and_exact_target_binding(self) -> None:
        target = HumanActionTarget("run-1", "human-decision", "decision-1", "plan.md", "a" * 64)
        valid = HumanActionReceipt(
            action_id="action-1",
            session_id="session-1",
            origin="inbound-human",
            run_id="run-1",
            gate="human-decision",
            decision_id="decision-1",
            target="plan.md",
            scope_digest="a" * 64,
            text_digest="b" * 64,
            observed_at="2026-09-30T00:00:00Z",
        )
        observed = FakeHarnessAdapter(human_action=valid).observe_human_action()
        self.assertIs(observed, valid)
        self.assertTrue(human_receipt_matches(observed, target))
        self.assertFalse(
            human_receipt_matches(
                FakeHarnessAdapter(human_action=replace(valid, origin="controller")).observe_human_action(),
                target,
            )
        )
        self.assertFalse(
            human_receipt_matches(
                FakeHarnessAdapter(human_action=replace(valid, target="other.md")).observe_human_action(),
                target,
            )
        )
        self.assertFalse(human_receipt_matches(FakeHarnessAdapter().observe_human_action(), target))
        for field in ("run_id", "gate", "decision_id", "target", "scope_digest"):
            with self.subTest(missing=field):
                self.assertFalse(human_receipt_matches(replace(valid, **{field: ""}), target))
                self.assertFalse(human_receipt_matches(valid, replace(target, **{field: ""})))
                self.assertFalse(
                    human_receipt_matches(
                        replace(valid, **{field: ""}), replace(target, **{field: ""})
                    )
                )
        for field in ("run_id", "gate", "decision_id", "target", "scope_digest"):
            with self.subTest(mismatch=field):
                value = "c" * 64 if field == "scope_digest" else "mismatch"
                self.assertFalse(human_receipt_matches(replace(valid, **{field: value}), target))
        self.assertFalse(human_receipt_matches(replace(valid, observed_at=""), target))
        self.assertFalse(human_receipt_matches(replace(valid, text_digest="not-a-digest"), target))
        self.assertFalse(human_receipt_matches(replace(valid, text_digest=None), target))
        self.assertFalse(human_receipt_matches(replace(valid, observed_at="not-a-date"), target))
        for timestamp in (
            "2026-09-30t00:00:00z",
            "2026-09-30T00:00:00.123+05:30",
            "2026-09-30T00:00:00-04:00",
            "2016-12-31T23:59:60Z",
            "2017-01-01T00:59:60+01:00",
        ):
            with self.subTest(timestamp=timestamp):
                self.assertTrue(human_receipt_matches(replace(valid, observed_at=timestamp), target))
        for timestamp in (
            "2026-09-30T00:00:00+00:60",
            "2026-09-30T00:00:00+01:99",
            "2026-09-30T00:00:60Z",
            "2016-12-31T12:34:60Z",
            "2016-12-30T23:59:60Z",
            "0001-01-01T00:00:60+00:01",
            "9999-12-31T23:59:60-00:01",
        ):
            with self.subTest(invalid_timestamp=timestamp):
                self.assertFalse(human_receipt_matches(replace(valid, observed_at=timestamp), target))




if __name__ == "__main__":
    unittest.main()
