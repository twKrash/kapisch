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

    def test_implementer_lite_full_instructions_are_preserved(self) -> None:
        import tomllib
        from kapisch_core.bundle import compile_bundle

        bundle = json.loads(compile_bundle(ROOT / "core"))
        contract = bundle["roles"]["implementer-lite"]["contract"]
        full_instructions = contract.split("## Full role instructions", 1)[1].split(
            "## Supplemental role contract", 1
        )[0].strip()
        source = tomllib.loads(
            (ROOT / "plugins/kapisch/agents/kapisch-implementer-lite.toml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            " ".join(full_instructions.split()),
            " ".join(source["developer_instructions"].split()),
        )

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
        self.assertIn("human owns decision and approval input", instructions)
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


if __name__ == "__main__":
    unittest.main()
