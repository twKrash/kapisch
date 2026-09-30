from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))


class BundleTests(unittest.TestCase):
    def test_bundle_is_canonical_and_verified_by_whole_byte_digest(self) -> None:
        from kapisch_core.bundle import compile_bundle, verify_bundle

        data = compile_bundle(ROOT / "core")
        digest = hashlib.sha256(data).hexdigest()
        canonical = json.dumps(
            json.loads(data), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8") + b"\n"
        self.assertEqual(data, canonical)
        self.assertEqual(verify_bundle(data, digest).protocol_version, 3)
        with self.assertRaises(ValueError):
            verify_bundle(data, "0" * 64)
        with self.assertRaises(ValueError):
            verify_bundle(data + b" ", hashlib.sha256(data + b" ").hexdigest())

    def test_bundle_contains_all_six_full_role_contracts_and_controller_policy(self) -> None:
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        self.assertEqual(
            set(bundle["roles"]),
            {"architect", "researcher", "implementer", "implementer-lite", "mechanic", "reviewer"},
        )
        for role, contract in bundle["roles"].items():
            source = (ROOT / "core/contracts/roles" / f"{role}.md").read_text(encoding="utf-8")
            self.assertEqual(contract["contract"], source)
            self.assertTrue(contract["contract"].strip())
        self.assertEqual(set(bundle["workflows"]), {"advisory", "review", "task", "milestone"})
        for workflow, contract in bundle["workflows"].items():
            source = (ROOT / "core/contracts/workflows" / f"{workflow}.md").read_text(encoding="utf-8")
            header, body = source.split("\n", 1)
            metadata = json.loads(header.removeprefix("<!-- kapisch-workflow: ").removesuffix(" -->"))
            self.assertEqual(contract["contract"], body)
            self.assertEqual(contract["stages"], metadata["stages"])
            self.assertEqual(contract["gates"], metadata["gates"])
        for policy, contract in bundle["policies"].items():
            source = (ROOT / "core/contracts/policy" / f"{policy}.md").read_text(encoding="utf-8")
            self.assertEqual(contract["contract"], source)
        self.assertEqual(
            bundle["controller_instructions"],
            (ROOT / "core/contracts/controller.md").read_text(encoding="utf-8"),
        )
        self.assertTrue(bundle["policies"])

    def test_role_contracts_preserve_semantics_without_v4_transport(self) -> None:
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        required = {
            "architect": ("work read-only", "a recommendation is advice, not acceptance", "never approve implementation"),
            "researcher": ("work read-only", "no design", "observed evidence"),
            "implementer": ("change the root cause", "focused regression coverage", "self-review"),
            "implementer-lite": ("completely specified, prescriptive behavioral change", "stop and return the precise blocker", "verify yourself"),
            "mechanic": ("non-behavioral maintenance", "stop before editing", "verify fresh"),
            "reviewer": ("independent kapisch reviewer", "findings only", "behavioral branch matrix", "invariant evidence matrix", "the review policy owns matrix scope"),
        }
        for role, phrases in required.items():
            contract = bundle["roles"][role]["contract"].lower()
            with self.subTest(role=role):
                self.assertIn("## full role instructions", contract)
                self.assertIn("the shared `authority`, `dispatch`, `risk`, `review`, `handoff`, `normalization`, and `resume` policies", contract)
                self.assertIn("never replace or weaken them", contract)
                for phrase in phrases:
                    self.assertIn(phrase, contract)
                for transport in ("version-4 transport", "bounded v4 transport payload", "model_reasoning_effort", ".codex/"):
                    self.assertNotIn(transport, contract)

    def test_authority_schema_references_use_registered_absolute_ids(self) -> None:
        from kapisch_core.bundle import compile_bundle

        schemas = json.loads(compile_bundle(ROOT / "core"))["schemas"]
        by_id = {schema["$id"]: schema for schema in schemas.values()}

        def check_references(value: object, root: object) -> None:
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str):
                    schema_id, separator, fragment = reference.partition("#")
                    target = root if not schema_id else by_id.get(schema_id)
                    if not isinstance(target, dict):
                        self.fail(f"unresolved schema reference: {reference}")
                    if separator:
                        current: object = target
                        for segment in fragment.lstrip("/").split("/") if fragment else []:
                            segment = segment.replace("~1", "/").replace("~0", "~")
                            if not isinstance(current, dict):
                                self.fail(f"unresolved schema pointer: {reference}")
                            self.assertIn(segment, current, reference)
                            current = current[segment]
                for child in value.values():
                    check_references(child, root)
            elif isinstance(value, list):
                for child in value:
                    check_references(child, root)

        for schema in schemas.values():
            check_references(schema, schema)

    def test_schema_compiler_and_verifier_reject_invalid_schema_structure(self) -> None:
        from kapisch_core.bundle import canonical_json, compile_bundle, verify_bundle

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "core"
            shutil.copytree(ROOT / "core", source)
            schema_path = source / "schemas/v3/run.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["required"] = 42
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            with self.assertRaises(ValueError):
                compile_bundle(source)

        payload = json.loads((ROOT / "core/dist/core-bundle.json").read_bytes())
        payload["schemas"]["run"]["required"] = 42
        malformed = canonical_json(payload)
        with self.assertRaises(ValueError):
            verify_bundle(malformed, hashlib.sha256(malformed).hexdigest())

    def test_compiler_and_verifier_reject_invalid_schema_type_and_ref_targets(self) -> None:
        from kapisch_core.bundle import canonical_json, compile_bundle, verify_bundle

        def corrupt(schema: dict[str, Any], case: str) -> None:
            if case == "duplicate type array":
                schema["properties"]["run_id"]["type"] = ["string", "string"]
            elif case == "reference to array":
                schema["properties"]["bundle_digest"]["$ref"] = "#/required"
            else:
                schema["properties"]["bundle_digest"]["$ref"] = "#/properties"

        for case in ("duplicate type array", "reference to array", "reference to object map"):
            with self.subTest(case=case, entrypoint="compile"), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "core"
                shutil.copytree(ROOT / "core", source)
                schema_path = source / "schemas/v3/run.json"
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                corrupt(schema, case)
                schema_path.write_text(json.dumps(schema), encoding="utf-8")
                with self.assertRaises(ValueError, msg=case):
                    compile_bundle(source)

            with self.subTest(case=case, entrypoint="verify"):
                payload = json.loads((ROOT / "core/dist/core-bundle.json").read_bytes())
                corrupt(payload["schemas"]["run"], case)
                malformed = canonical_json(payload)
                with self.assertRaises(ValueError, msg=case):
                    verify_bundle(malformed, hashlib.sha256(malformed).hexdigest())

    def test_snapshot_dependency_ids_and_mutable_relationship_refs_are_declared(self) -> None:
        from kapisch_core.bundle import compile_bundle

        schemas = json.loads(compile_bundle(ROOT / "core"))["schemas"]
        dependency = schemas["snapshot"]["$defs"]["source"]
        self.assertEqual(
            set(dependency["properties"]),
            {"kind", "path", "sha256", "decision_id", "snapshot_id"},
        )
        self.assertIn("allOf", dependency)
        identity_rules = {
            rule["if"]["properties"]["kind"]["const"]: set(rule["then"]["required"])
            for rule in dependency["allOf"]
        }
        self.assertEqual(
            identity_rules,
            {"decision": {"decision_id"}, "snapshot": {"snapshot_id"}},
        )
        run_schema = schemas["run"]
        self.assertEqual(
            set(schemas["run"]["properties"]),
            {
                "protocol_version", "run_id", "bundle_digest", "workflow", "revision",
                "history", "accepted_snapshot", "approved_plan", "amends", "supersedes",
            },
        )
        relationship_rules = [
            rule
            for rule in run_schema["allOf"]
            if rule["if"].get("required") == ["accepted_snapshot"]
        ]
        self.assertEqual(len(relationship_rules), 1)
        self.assertEqual(
            set(relationship_rules[0]["then"]["required"]), {"amends", "supersedes"}
        )

    def test_bundle_schema_closes_canonical_member_maps(self) -> None:
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        schema = bundle["schemas"]["bundle"]
        for group in ("roles", "workflows", "policies", "schemas"):
            group_schema = schema["properties"][group]
            self.assertEqual(set(group_schema["properties"]), set(bundle[group]))
            self.assertEqual(set(group_schema["required"]), set(bundle[group]))
            self.assertIs(group_schema["additionalProperties"], False)
        vocabulary = schema["properties"]["vocabulary"]
        self.assertEqual(set(vocabulary["properties"]), set(bundle["vocabulary"]))
        self.assertEqual(set(vocabulary["required"]), set(bundle["vocabulary"]))
        self.assertIs(vocabulary["additionalProperties"], False)

    def test_only_v3_authority_schemas_enter_bundle(self) -> None:
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        self.assertEqual(
            set(bundle["schemas"]),
            {"approval", "bundle", "invocation", "repository-state", "run", "snapshot", "stage"},
        )
        self.assertNotIn("telemetry", bundle["schemas"])
        bundle_text = json.dumps(bundle).lower()
        self.assertTrue(set(re.findall("[a-z]+", bundle_text)).isdisjoint({"codex", "pi"}))
        self.assertNotIn(".codex", bundle_text)
        self.assertNotIn(".pi", bundle_text)
        self.assertNotIn("openai-codex", bundle_text)

    def test_contract_or_authority_schema_changes_change_digest_but_telemetry_does_not(self) -> None:
        from kapisch_core.bundle import compile_bundle

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "core"
            shutil.copytree(ROOT / "core", source)
            before = compile_bundle(source)
            role = source / "contracts/roles/architect.md"
            role.write_text(role.read_text() + "\nChanged contract.\n", encoding="utf-8")
            self.assertNotEqual(
                hashlib.sha256(before).digest(), hashlib.sha256(compile_bundle(source)).digest()
            )
            schema = source / "schemas/v3/run.json"
            value = json.loads(schema.read_text())
            value["description"] = "Changed authority schema."
            schema.write_text(json.dumps(value), encoding="utf-8")
            after_schema = compile_bundle(source)
            self.assertNotEqual(hashlib.sha256(before).digest(), hashlib.sha256(after_schema).digest())
            telemetry = source / "schemas/telemetry"
            telemetry.mkdir(parents=True)
            (telemetry / "telemetry.json").write_text('{"changed":true}', encoding="utf-8")
            self.assertEqual(after_schema, compile_bundle(source))

    def test_state_schema_references_immutable_snapshot_and_plan_artifacts(self) -> None:
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        run_schema = bundle["schemas"]["run"]
        self.assertEqual(run_schema["properties"]["accepted_snapshot"]["$ref"], "#/$defs/snapshot_ref")
        self.assertEqual(run_schema["properties"]["approved_plan"]["$ref"], "#/$defs/plan_ref")
        self.assertEqual(
            set(run_schema["$defs"]["snapshot_ref"]["required"]), {"snapshot_id", "path", "sha256"}
        )
        repository_schema = bundle["schemas"]["repository-state"]["$defs"]
        self.assertNotIn("sha256", repository_schema["worktree_entry"]["required"])
        self.assertNotIn("sha256", repository_schema["untracked_entry"]["required"])
        instructions = bundle["controller_instructions"].lower()
        self.assertIn("cold restart", instructions)
        self.assertIn("earlier explicit producer", instructions)
        self.assertIn("the human owns explicit decision input and side-effect permission, separately from independent reviewer judgment", instructions)
        self.assertIn("immutable snapshot serialization after explicit human choice", instructions)

    def test_verify_rejects_unknown_fields_and_changed_contract_hash(self) -> None:
        from kapisch_core.bundle import canonical_json, verify_bundle

        payload = json.loads((ROOT / "core/dist/core-bundle.json").read_bytes())
        payload["adapter_runtime"] = {"model": "example"}
        malformed = canonical_json(payload)
        with self.assertRaises(ValueError):
            verify_bundle(malformed, hashlib.sha256(malformed).hexdigest())
        payload.pop("adapter_runtime")
        payload["roles"]["architect"]["sha256"] = "0" * 64
        malformed = canonical_json(payload)
        with self.assertRaises(ValueError):
            verify_bundle(malformed, hashlib.sha256(malformed).hexdigest())
        payload = json.loads((ROOT / "core/dist/core-bundle.json").read_bytes())
        payload["schemas"]["run"]["$id"] = "kapisch://schemas/v2/run"
        malformed = canonical_json(payload)
        with self.assertRaises(ValueError):
            verify_bundle(malformed, hashlib.sha256(malformed).hexdigest())

    def test_compiler_rejects_unregistered_v3_schema(self) -> None:
        from kapisch_core.bundle import compile_bundle

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "core"
            shutil.copytree(ROOT / "core", source)
            extra = source / "schemas/v3/telemetry.json"
            extra.write_text('{"type":"object"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                compile_bundle(source)

    def test_build_is_hash_seed_independent_and_checked_artifacts_match(self) -> None:
        script = ROOT / "tooling/build/build_bundle.py"
        outputs = []
        for seed in ("1", "8675309"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            result = subprocess.run(
                [sys.executable, str(script), "--check"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            outputs.append((ROOT / "core/dist/core-bundle.json").read_bytes())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], (ROOT / "core/kapisch_core/resources/core-bundle.json").read_bytes())
        self.assertEqual(outputs[0], (ROOT / "tests/conformance/fixtures/v3/bundle.json").read_bytes())

    def test_check_rejects_changed_contract_or_authority_schema(self) -> None:
        script = ROOT / "tooling/build/build_bundle.py"
        for relative in ("contracts/roles/architect.md", "schemas/v3/run.json"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                source_root = Path(directory)
                core = source_root / "core"
                shutil.copytree(
                    ROOT / "core", core,
                    ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "build"),
                )
                fixture = source_root / "tests/conformance/fixtures/v3"
                fixture.mkdir(parents=True)
                shutil.copy2(ROOT / "tests/conformance/fixtures/v3/bundle.json", fixture / "bundle.json")
                contract = core / relative
                if relative.endswith(".json"):
                    schema = json.loads(contract.read_text(encoding="utf-8"))
                    schema["description"] = "Changed authority schema."
                    contract.write_text(json.dumps(schema), encoding="utf-8")
                else:
                    contract.write_text(
                        contract.read_text(encoding="utf-8") + "\nChanged.\n",
                        encoding="utf-8",
                    )
                result = subprocess.run(
                    [sys.executable, str(script), "--check", "--root", str(source_root)],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("core/dist/core-bundle.json", result.stderr)

    def test_installed_wheel_contains_exact_bundle_resource(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "core"
            shutil.copytree(
                ROOT / "core", source,
                ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "build"),
            )
            wheelhouse = Path(directory) / "wheelhouse"
            target = Path(directory) / "installed"
            wheelhouse.mkdir()
            built = subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--disable-pip-version-check", "--wheel-dir", str(wheelhouse), str(source)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            wheel = next(wheelhouse.glob("*.whl"))
            installed = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-deps", "--no-index", "--disable-pip-version-check", "--target", str(target), str(wheel)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            self.assertEqual(
                (target / "kapisch_core/resources/core-bundle.json").read_bytes(),
                (ROOT / "core/dist/core-bundle.json").read_bytes(),
            )


    def test_human_receipt_binds_exact_gate_target_and_input(self) -> None:
        approval = json.loads((ROOT / "core/schemas/v3/approval.json").read_text(encoding="utf-8"))
        outer = approval["properties"]
        receipt = approval["$defs"]["receipt"]
        bound_fields = {"run_id", "gate", "decision_id", "target", "scope_digest"}

        self.assertTrue(bound_fields <= set(outer))
        self.assertTrue(bound_fields <= set(approval["required"]))
        self.assertTrue(bound_fields | {"text_digest", "origin", "session_id", "action_id", "observed_at"} <= set(receipt["required"]))
        self.assertNotIn("approval", outer["gate"]["enum"])
        self.assertNotIn("approval", receipt["properties"]["gate"]["enum"])
        self.assertEqual(receipt["properties"]["origin"]["const"], "inbound-human")
        artifact = approval["$defs"]["artifact"]
        self.assertIn("sha256", artifact["required"])
        self.assertEqual(artifact["properties"]["source"]["const"], "externally-supplied")
        self.assertEqual(receipt["additionalProperties"], False)

        authority = (ROOT / "core/contracts/policy/authority.md").read_text(encoding="utf-8")
        self.assertIn("Gate.APPROVAL", authority)
        self.assertIn("human approval of a plan", authority)

    def test_review_policy_owns_behavioral_and_invariant_evidence_matrices(self) -> None:
        review = (ROOT / "core/contracts/policy/review.md").read_text(encoding="utf-8").lower()
        behavioral_columns = (
            "entry point", "trigger", "state before the transition", "pending or persisted state",
            "reconstructed state after resume", "authorization and policy context",
            "side effect or persistence result", "final public result/status",
            "regression coverage", "status",
        )
        invariant_rows = (
            "source claim", "schema or example", "normal transition", "failure or cancellation",
            "resume", "consumers or policy", "negative scenario", "fallback or bootstrap",
            "evidence", "status",
        )
        for column in behavioral_columns:
            with self.subTest(column=column):
                self.assertIn(column, review)
        for row in invariant_rows:
            with self.subTest(row=row):
                self.assertIn(row, review)
        self.assertIn("every observable branch", review)
        self.assertIn("invalid-input", review)
        self.assertIn("pause/resume", review)
        self.assertIn("every applicable high-risk", review)
        self.assertIn("every `n/a` must include its reason", review)
        for severity in ("p0", "p1", "p2", "p3"):
            self.assertIn(f"**{severity}**", review)
        for field in ("stable id", "causal relationship", "regression coverage", "confirmed", "likely", "question"):
            self.assertIn(field, review)

    def test_handoff_policy_defines_decision_packet_structure(self) -> None:
        handoff = (ROOT / "core/contracts/policy/handoff.md").read_text(encoding="utf-8").lower()
        for field in ("id", "kind", "problem", "why", "decision_required", "options", "recommendation"):
            with self.subTest(field=field):
                self.assertIn(field, handoff)
        for option_field in ("description", "consequences"):
            self.assertIn(option_field, handoff)
        self.assertIn("up to three materially different options", handoff)
        self.assertIn("recommendation", handoff)
        self.assertIn("unavailable", handoff)
        self.assertIn("never record an agent recommendation as a human decision", handoff)

    def test_role_assignment_and_risk_semantics_are_canonical_in_v3_policies(self) -> None:
        dispatch = (ROOT / "core/contracts/policy/dispatch.md").read_text(encoding="utf-8").lower()
        risk = (ROOT / "core/contracts/policy/risk.md").read_text(encoding="utf-8").lower()
        assignment_rules = (
            ("mechanical", "mechanic", "cheap"),
            ("non-high-risk prescriptive", "implementer-lite", "cheap"),
            ("high-risk prescriptive", "implementer", "standard"),
            ("bounded", "implementer", "standard"),
            ("design", "architect", "high"),
            ("research", "researcher", "standard"),
            ("review", "reviewer", "high"),
        )
        for rule in assignment_rules:
            with self.subTest(rule=rule):
                for term in rule:
                    self.assertIn(term, dispatch)
        for trigger in ("authentication", "authorization", "privacy", "concurrency", "migration", "recovery", "external side effects"):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, risk)
        self.assertIn("risk is independent of implementation complexity", risk)
        self.assertIn("high-risk work requires", risk)
        self.assertIn("low → quick", risk)
        self.assertIn("medium → standard", risk)
        self.assertIn("high → deep", risk)
        for lens in (
            "behavior", "security", "permissions", "privacy", "tenant-isolation", "concurrency",
            "data", "migration", "api", "compatibility", "tests", "operations", "audit", "recovery",
        ):
            with self.subTest(lens=lens):
                self.assertIn(lens, risk)

    def test_workflow_metadata_is_scoped_and_admissible_under_stage1_policy(self) -> None:
        from kapisch_core.bundle import compile_bundle
        from kapisch_core.capabilities import CapabilityClaim, CapabilityClaims, CapabilityStatus
        from kapisch_core.domain import (
            CapabilityEffect, ExecutionClass, Gate, LogicalTier, ProposedAction,
            ReviewDepth, ReviewScope, Role, Stage, Workflow,
        )
        from kapisch_core.policy import evaluate_action_policy

        bundle = json.loads(compile_bundle(ROOT / "core"))
        workflows = bundle["workflows"]
        workflow_schema = bundle["schemas"]["bundle"]["$defs"]["workflow"]
        self.assertEqual(set(workflow_schema["required"]), {"metadata_scope", "stages", "gates", "review_scopes", "contract", "sha256"})
        self.assertEqual(workflow_schema["properties"]["metadata_scope"]["const"], "workflow-specific")
        expected_metadata = {
            "advisory": ({"research", "design", "gate"}, {"human-decision"}, set()),
            "review": ({"review"}, set(), {"standalone"}),
            "task": ({"implement", "review", "gate"}, {"human-decision", "approval", "side-effect"}, {"iteration", "whole-branch"}),
            "milestone": ({"research", "design", "gate", "implement", "review", "final"}, {"human-decision", "approval", "side-effect"}, {"iteration", "whole-branch"}),
        }
        self.assertEqual(set(workflows), {item.value for item in Workflow})
        implementation = {
            Stage.RESEARCH: (Role.RESEARCHER, LogicalTier.STANDARD, ExecutionClass.PRESCRIPTIVE),
            Stage.DESIGN: (Role.ARCHITECT, LogicalTier.HIGH, ExecutionClass.DESIGN),
            Stage.IMPLEMENT: (Role.IMPLEMENTER, LogicalTier.STANDARD, ExecutionClass.BOUNDED),
            Stage.GATE: (Role.IMPLEMENTER, LogicalTier.STANDARD, ExecutionClass.BOUNDED),
            Stage.BOUNDED_DELEGATE: (Role.IMPLEMENTER, LogicalTier.STANDARD, ExecutionClass.BOUNDED),
        }
        for name, metadata in workflows.items():
            with self.subTest(workflow=name):
                self.assertEqual(metadata["metadata_scope"], "workflow-specific")
                stages, gates, scopes = expected_metadata[name]
                self.assertEqual(set(metadata["stages"]), stages)
                self.assertEqual(set(metadata["gates"]), gates)
                self.assertEqual(set(metadata["review_scopes"]), scopes)
                self.assertEqual(len(metadata["review_scopes"]), len(set(metadata["review_scopes"])))
                workflow = Workflow(name)
                for stage_name in metadata["stages"]:
                    stage = Stage(stage_name)
                    if stage in implementation:
                        role, tier, execution_class = implementation[stage]
                        scope = ReviewScope.ITERATION
                        depth = ReviewDepth.STANDARD
                        claims = CapabilityClaims()
                    else:
                        role, tier, execution_class = Role.REVIEWER, LogicalTier.HIGH, ExecutionClass.PRESCRIPTIVE
                        scope = ReviewScope.STANDALONE if workflow is Workflow.REVIEW else ReviewScope.ITERATION
                        depth = ReviewDepth.DEEP if stage is Stage.FINAL else ReviewDepth.STANDARD
                        claims = CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED)
                        if stage is Stage.FINAL:
                            scope = ReviewScope.WHOLE_BRANCH
                    result = evaluate_action_policy(
                        workflow,
                        ProposedAction(stage, role, tier=tier, execution_class=execution_class,
                                       review_depth=depth, review_scope=scope),
                        claims,
                    )
                    self.assertTrue(result.admissible, (name, stage_name, result.violations))

                for scope_name in metadata["review_scopes"]:
                    result = evaluate_action_policy(
                        workflow,
                        ProposedAction(Stage.REVIEW, Role.REVIEWER, tier=LogicalTier.HIGH,
                                       review_scope=ReviewScope(scope_name)),
                        CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED),
                    )
                    self.assertTrue(result.admissible, (name, scope_name, result.violations))

                for gate_name in metadata["gates"]:
                    gate = Gate(gate_name)
                    effect = CapabilityEffect.REPOSITORY_READ
                    role, tier = Role.IMPLEMENTER, LogicalTier.STANDARD
                    claims = CapabilityClaims()
                    if gate is Gate.APPROVAL:
                        role, tier = Role.REVIEWER, LogicalTier.HIGH
                        claims = CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED)
                        claims = CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED)
                    elif gate is Gate.SIDE_EFFECT:
                        effect = CapabilityEffect.REPOSITORY_WRITE
                        claims = CapabilityClaims((CapabilityClaim(effect, CapabilityStatus.ENFORCED),))
                    result = evaluate_action_policy(
                        workflow,
                        ProposedAction(Stage.GATE, role, tier=tier, gate=gate, effect=effect,
                                       review_scope=ReviewScope.ITERATION),
                        claims,
                    )
                    self.assertTrue(result.admissible, (name, gate_name, result.violations))

        self.assertNotIn("approval", workflows["advisory"]["gates"])
        rejected_advisory_approval = evaluate_action_policy(
            Workflow.ADVISORY,
            ProposedAction(Stage.GATE, Role.IMPLEMENTER, gate=Gate.APPROVAL),
            CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED),
        )
        self.assertFalse(rejected_advisory_approval.admissible)
        rejected_task_standalone = evaluate_action_policy(
            Workflow.TASK,
            ProposedAction(Stage.REVIEW, Role.REVIEWER, tier=LogicalTier.HIGH,
                           review_scope=ReviewScope.STANDALONE),
            CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED),
        )
        self.assertFalse(rejected_task_standalone.admissible)
        rejected_final_iteration = evaluate_action_policy(
            Workflow.MILESTONE,
            ProposedAction(Stage.FINAL, Role.REVIEWER, tier=LogicalTier.HIGH,
                           review_scope=ReviewScope.ITERATION),
            CapabilityClaims(mutation_free_reviewer=CapabilityStatus.ENFORCED),
        )
        self.assertFalse(rejected_final_iteration.admissible)

    def test_stage_schema_separates_stage_kind_from_attempt_identity(self) -> None:
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        stage = json.loads((ROOT / "core/schemas/v3/stage.json").read_text(encoding="utf-8"))
        run = json.loads((ROOT / "core/schemas/v3/run.json").read_text(encoding="utf-8"))
        self.assertIn("stage_id", stage["required"])
        self.assertIn("stage_kind", stage["required"])
        self.assertEqual(stage["properties"]["stage_kind"]["type"], "string")
        self.assertEqual(set(stage["properties"]["stage_kind"]["enum"]), set(bundle["vocabulary"]["stages"]))
        self.assertIn("review", stage["properties"]["stage_kind"]["enum"])
        self.assertIn("final", stage["properties"]["stage_kind"]["enum"])
        self.assertNotEqual(stage["properties"]["stage_id"], stage["properties"]["stage_kind"])
        self.assertEqual(run["properties"]["history"]["items"]["$ref"], "kapisch://schemas/v3/stage")
        self.assertIn("task", run["properties"]["workflow"]["enum"])

if __name__ == "__main__":
    unittest.main()
    unittest.main()
    unittest.main()
