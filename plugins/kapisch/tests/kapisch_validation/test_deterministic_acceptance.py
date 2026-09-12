from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from copy import deepcopy
from pathlib import Path

from kapisch_validation.canonical_bytes import (
    canonical_json_line,
    normalize_utf8_text,
    sha256_hex,
)
from kapisch_validation.canonical_toml import render_toml
from kapisch_validation.delegations import render_route
from kapisch_validation.knowledge import render_knowledge_records
from kapisch_validation.manifest import render_manifest
from kapisch_validation.outcomes import render_outcome
from kapisch_validation.path_atoms import canonical_relative_path, validate_relative_posix_path
from kapisch_validation.presentations import render_metrics, render_state_markdown
from kapisch_validation.references import render_state
from kapisch_validation.review_evidence import render_reviewer_invocation


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_VECTOR = FIXTURES / "deterministic-generated-artifacts" / "expected-sha256.json"
TASK_FIXTURE = FIXTURES / "valid-v4-controller"


def _benchmark_rows(variant: str) -> list[dict[str, object]]:
    def row(
        scenario: str,
        role: str,
        invocation: int,
        *,
        decision: str = "approve",
        findings: int = 0,
        resume: str = "not-applicable",
    ) -> dict[str, object]:
        return {
            "run_id": "tâche",
            "scenario": scenario,
            "variant": variant,
            "role": role,
            "invocation": invocation,
            "input_tokens": 10,
            "output_tokens": 2,
            "cache_read_tokens": None,
            "turns": 1,
            "elapsed_ms": 5,
            "workflow_outcome": "complete",
            "validator_exit": 0,
            "review_decision": decision,
            "review_findings": findings,
            "test_result": "pass",
            "resume_result": resume,
        }

    return [
        row("behavioral", "parent", 1),
        row("behavioral", "implementer", 1),
        row("behavioral", "reviewer", 1),
        row("durable-fix", "parent", 1),
        row("durable-fix", "researcher", 1),
        row("durable-fix", "implementer", 1),
        row("durable-fix", "reviewer", 2, decision="do-not-approve", findings=1),
        row("durable-fix", "implementer", 3),
        row("durable-fix", "reviewer", 4),
        row("durable-fix", "reviewer", 5, decision="ready"),
        row("worker-reviewer-resume", "parent", 1),
        row("worker-reviewer-resume", "implementer", 1, resume="pass"),
        row("worker-reviewer-resume", "reviewer", 1, resume="pass"),
    ]


def _eligible_v3_source(root: Path) -> Path:
    source = root / "source"
    shutil.copytree(FIXTURES / "valid-v3-durable", source)
    graph_path = source / "02-execution-graph.toml"
    graph = tomllib.loads(graph_path.read_text(encoding="utf-8"))
    v4 = tomllib.loads(
        (TASK_FIXTURE / "02-execution-graph.toml").read_text(encoding="utf-8")
    )
    for node, v4_node in zip(graph["nodes"], v4["nodes"], strict=True):
        node["assignment"] = deepcopy(v4_node["assignment"])
        node["assignment"]["attempts"][0].pop("outcome_path")
    graph_path.write_bytes(render_toml(graph))
    return source


def _tree_digest(root: Path) -> str:
    records = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        records.append(relative + b"\0" + sha256_hex(path.read_bytes()).encode("ascii") + b"\n")
    return sha256_hex(b"".join(records))


def _with_order(value: object, *, reverse: bool) -> object:
    """Reconstruct mappings in a deliberately opposite insertion order."""
    if isinstance(value, dict):
        items = list(value.items())
        if reverse:
            items.reverse()
        return {key: _with_order(item, reverse=reverse) for key, item in items}
    return deepcopy(value)


def _portable(task_dir: Path, value: str) -> str:
    return canonical_relative_path(task_dir / value, root=task_dir)


def _rebind_paths(task_dir: Path, manifest: dict[str, object], state: dict[str, object], route: dict[str, object]) -> None:
    for field in ("source_plan", "controller_view"):
        if field in manifest:
            manifest[field] = _portable(task_dir, str(manifest[field]))
    for node in manifest["nodes"]:  # type: ignore[index]
        assert isinstance(node, dict)
        for field in ("brief", "context", "report", "reviewer_invocation"):
            if field in node:
                node[field] = _portable(task_dir, str(node[field]))
        for field in ("reads", "writes", "shared_resources"):
            if field in node:
                node[field] = [_portable(task_dir, str(path)) for path in node[field]]
        for item in node.get("verification_evidence", []):
            assert isinstance(item, dict)
            item["evidence_ref"] = _portable(task_dir, str(item["evidence_ref"]))
        assignment = node.get("assignment")
        if isinstance(assignment, dict):
            for attempt in assignment.get("attempts", []):
                assert isinstance(attempt, dict)
                if attempt.get("outcome_path") != "unavailable":
                    attempt["outcome_path"] = _portable(
                        task_dir, str(attempt["outcome_path"])
                    )
    for field in ("source_plan", "latest_approving_review_path", "controller_view_path"):
        if state.get(field) != "unavailable":
            state[field] = _portable(task_dir, str(state[field]))
    for step in route["steps"]:  # type: ignore[index]
        assert isinstance(step, dict)
        for field in ("context_path", "evidence_path"):
            step[field] = _portable(task_dir, str(step[field]))


def _assert_portable_paths(manifest: dict[str, object], state: dict[str, object], route: dict[str, object]) -> None:
    paths: list[str] = []
    for field in ("source_plan", "controller_view"):
        if field in manifest:
            paths.append(str(manifest[field]))
    for node in manifest["nodes"]:  # type: ignore[index]
        assert isinstance(node, dict)
        paths.extend(str(node[field]) for field in ("brief", "context", "report", "reviewer_invocation") if field in node)
        for field in ("reads", "writes", "shared_resources"):
            paths.extend(str(path) for path in node.get(field, []))
        paths.extend(str(item["evidence_ref"]) for item in node.get("verification_evidence", []))
        assignment = node.get("assignment")
        if isinstance(assignment, dict):
            for attempt in assignment.get("attempts", []):
                assert isinstance(attempt, dict)
                if attempt.get("outcome_path") != "unavailable":
                    paths.append(str(attempt["outcome_path"]))
    paths.extend(str(state[field]) for field in ("source_plan", "latest_approving_review_path", "controller_view_path") if state.get(field) != "unavailable")
    for step in route["steps"]:  # type: ignore[index]
        assert isinstance(step, dict)
        paths.extend((str(step["context_path"]), str(step["evidence_path"])))
    single_component_paths = {"01-plan.md", "04-controller-view.toml"}
    for value in paths:
        portable = validate_relative_posix_path(value)
        assert ("/" in portable) == (portable not in single_component_paths)


def _generate(root: Path, reverse_inputs: bool) -> dict[str, str]:
    repository = root / "répo with spaces"
    task_dir = repository / "run"
    shutil.copytree(TASK_FIXTURE, task_dir)

    invocation_paths = (
        "reviews/round-0/00-review-invocation.toml",
        "reviews/final/00-final-invocation.toml",
    )
    invocation_digests: dict[str, str] = {}
    for relative in invocation_paths:
        path = task_dir / relative
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        rendered = render_reviewer_invocation(_with_order(raw, reverse=reverse_inputs))
        path.write_bytes(rendered)
        invocation_digests[relative] = sha256_hex(rendered)

    outcome_digests: dict[str, str] = {}
    for path in sorted((task_dir / "stage-outcomes").glob("*.toml"), reverse=reverse_inputs):
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        invocation_path = raw["invocation_path"]
        if invocation_path != "unavailable":
            raw["invocation_sha256"] = invocation_digests[str(invocation_path)]
        rendered = render_outcome(_with_order(raw, reverse=reverse_inputs))
        path.write_bytes(rendered)
        outcome_digests[path.stem] = sha256_hex(rendered)

    graph_path = task_dir / "02-execution-graph.toml"
    state_path = task_dir / "03-state.toml"
    route_path = task_dir / "delegations/00-route.toml"
    manifest = tomllib.loads(graph_path.read_text(encoding="utf-8"))
    state = tomllib.loads(state_path.read_text(encoding="utf-8"))
    route = tomllib.loads(route_path.read_text(encoding="utf-8"))
    if reverse_inputs:
        manifest["nodes"] = list(reversed(manifest["nodes"]))
        route["steps"] = list(reversed(route["steps"]))
        for field in ("completed_node_ids", "running_node_ids", "ready_node_ids", "blocked_node_ids", "failed_node_ids"):
            state[field] = list(reversed(state[field]))
    _rebind_paths(task_dir, manifest, state, route)
    route_bytes = render_route(_with_order(route, reverse=reverse_inputs))
    manifest_bytes = render_manifest(_with_order(manifest, reverse=reverse_inputs), initial=False)
    state_bytes = render_state(_with_order(state, reverse=reverse_inputs))
    route_path.write_bytes(route_bytes)
    graph_path.write_bytes(manifest_bytes)
    state_path.write_bytes(state_bytes)
    _assert_portable_paths(manifest, state, route)

    rendered_view = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts/render_controller_view.py"), "--task-dir", str(task_dir)],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if rendered_view.returncode:
        raise AssertionError(rendered_view.stdout + rendered_view.stderr)
    before_noop = (
        state_path.read_bytes(),
        (task_dir / "04-controller-view.toml").read_bytes(),
        state_path.stat().st_mtime_ns,
        (task_dir / "04-controller-view.toml").stat().st_mtime_ns,
    )
    rendered_view_again = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts/render_controller_view.py"), "--task-dir", str(task_dir)],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    after_noop = (
        state_path.read_bytes(),
        (task_dir / "04-controller-view.toml").read_bytes(),
        state_path.stat().st_mtime_ns,
        (task_dir / "04-controller-view.toml").stat().st_mtime_ns,
    )
    if rendered_view_again.returncode or before_noop != after_noop:
        raise AssertionError("controller-view regeneration was not a true no-op")
    validated = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts/validate_kapisch.py"), "--task-dir", str(task_dir)],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if validated.returncode:
        raise AssertionError(validated.stdout + validated.stderr)

    invalid_task = repository / "répertoire-invalid"
    shutil.copytree(FIXTURES / "dependency-cycle", invalid_task)
    diagnostic = subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts/validate_kapisch.py"),
            "--task-dir",
            str(invalid_task),
            "--format",
            "json",
        ],
        cwd=root.parent,
        capture_output=True,
        check=False,
    )
    if (
        diagnostic.returncode != 2
        or "répertoire-invalid".encode("utf-8") not in diagnostic.stdout
        or b"\\u00e9" in diagnostic.stdout
        or not diagnostic.stdout.endswith(b"\n")
        or b"\r\n" in diagnostic.stdout
    ):
        raise AssertionError("validator diagnostic bytes are not canonical")

    benchmark_dir = repository / "benchmark"
    benchmark_dir.mkdir()
    benchmark_paths = []
    for variant in ("baseline", "candidate"):
        rows = _benchmark_rows(variant)
        if reverse_inputs:
            rows.reverse()
        path = benchmark_dir / f"{variant}.jsonl"
        path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in rows
            ),
            encoding="utf-8",
            newline="\n",
        )
        benchmark_paths.append(path)
    benchmark = subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts/compare_controller_benchmark.py"),
            "--baseline",
            str(benchmark_paths[0]),
            "--candidate",
            str(benchmark_paths[1]),
        ],
        cwd=root.parent,
        capture_output=True,
        check=False,
    )
    benchmark_summary = json.loads(benchmark.stdout)
    if (
        benchmark.returncode
        or not benchmark_summary["required_evidence_present"]
        or not benchmark.stdout.endswith(b"\n")
        or b"\r\n" in benchmark.stdout
    ):
        raise AssertionError("benchmark output bytes are not canonical")

    migration_root = repository / "migration"
    migration_root.mkdir()
    migration_source = _eligible_v3_source(migration_root)
    migration_destination = migration_root / "destination"
    migrated = subprocess.run(
        [
            sys.executable,
            str(PLUGIN_ROOT / "scripts/migrate_controller_view_v4.py"),
            "--task-dir",
            str(migration_source),
            "--destination-task-dir",
            str(migration_destination),
            "--approve",
        ],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if migrated.returncode:
        raise AssertionError(migrated.stdout + migrated.stderr)
    migration_digest = _tree_digest(migration_destination)

    agents = repository / ".codex/agents"
    agents.mkdir(parents=True, exist_ok=True)
    profiles = (("alpha.toml", "kapisch-implementer.toml"), ("omega.toml", "kapisch-researcher.toml"))
    if reverse_inputs:
        profiles = tuple(reversed(profiles))
    for destination, source in profiles:
        shutil.copyfile(PLUGIN_ROOT / "agents" / source, agents / destination)
    installed = subprocess.run(
        [
            sys.executable, str(PLUGIN_ROOT / "scripts/setup_profile.py"), "--role", "reviewer",
            "--profile-set", "balanced", "--project-dir", str(repository), "--install",
        ],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if installed.returncode:
        raise AssertionError(installed.stdout + installed.stderr)

    installed_profile = agents / "kapisch-reviewer.toml"
    profile_state = tomllib.loads(
        (repository / ".kapisch/local-state/profiles/reviewer.toml").read_text(
            encoding="utf-8"
        )
    )
    expected_profile_state = {
        "profile_state_version": 1,
        "template": "kapisch-reviewer.toml",
        "template_sha256": sha256_hex(
            normalize_utf8_text(
                (PLUGIN_ROOT / "agents/kapisch-reviewer.toml").read_bytes()
            )
        ),
        "installed_profile": str(installed_profile),
        "scope": "project",
        "profile_set": "balanced",
        "profile_identity": "kapisch-reviewer",
        "installed_model": "gpt-5.6-terra",
        "installed_model_reasoning_effort": "high",
        "installed_sha256": sha256_hex(installed_profile.read_bytes()),
    }
    if profile_state != expected_profile_state:
        raise AssertionError("installed profile ownership state is not truthful")

    applies_when = ["zeta", "zeta", "alpha"]
    if reverse_inputs:
        applies_when.reverse()
    knowledge_input = {
        "version": 1,
        "records": [
            {"id": "D-001", "kind": "decision", "scope": "task:vector", "authority": "binding", "status": "verified", "statement": "Bytes stay exact.", "source": "01-plan.md", "verified_at_revision": "abc1234", "applies_when": applies_when},
            {"id": "P-002", "kind": "pitfall", "scope": "repository", "authority": "advisory", "status": "candidate", "statement": "Do not normalize evidence.", "source": "03-review.md", "applies_when": []},
        ],
    }
    knowledge = render_knowledge_records(
        _with_order(knowledge_input, reverse=reverse_inputs)
    )
    current_state = tomllib.loads(state_path.read_text(encoding="utf-8"))
    state_projection = _with_order(current_state, reverse=reverse_inputs)
    for field in (
        "completed_node_ids", "running_node_ids", "ready_node_ids",
        "blocked_node_ids", "failed_node_ids",
    ):
        if reverse_inputs:
            state_projection[field] = list(reversed(state_projection[field]))
    state_markdown = render_state_markdown(state_projection)
    metric_records = [
        {"terminal_id": "AT-T01-1", "role": "implementer", "elapsed_ms": 12},
        {"terminal_id": "AT-F01-1", "role": "reviewer", "elapsed_ms": "unavailable"},
    ]
    if reverse_inputs:
        metric_records.reverse()
    metrics = render_metrics(
        metric_records,
        _with_order({"terminal_count": 2}, reverse=reverse_inputs),
    )
    canonical_json = canonical_json_line(
        _with_order({"é": "é", "z": 1}, reverse=reverse_inputs)
    )
    finding_outcome = tomllib.loads(
        (task_dir / "stage-outcomes/AT-T01-1.toml").read_text(encoding="utf-8")
    )
    finding_outcome["findings"] = [
        {"id": "F-2", "severity": "P2", "summary": "later", "evidence_ref": "tasks/T01-report.md"},
        {"id": "F-1", "severity": "P0", "summary": "first", "evidence_ref": "tasks/T01-report.md"},
    ]
    if reverse_inputs:
        finding_outcome["findings"].reverse()
    outcome_findings = render_outcome(
        _with_order(finding_outcome, reverse=reverse_inputs)
    )
    invocation_outputs = tuple(
        (task_dir / relative).read_bytes() for relative in invocation_paths
    )
    outcome_outputs = tuple(
        (task_dir / "stage-outcomes" / f"{attempt_id}.toml").read_bytes()
        for attempt_id in ("AT-T01-1", "AT-R01-1", "AT-F01-1")
    )
    portable_outputs = (
        route_bytes, manifest_bytes, state_path.read_bytes(),
        (task_dir / "04-controller-view.toml").read_bytes(), knowledge,
        state_markdown, metrics, canonical_json, outcome_findings,
        benchmark.stdout,
        *invocation_outputs, *outcome_outputs,
        *(path.read_bytes() for path in migration_destination.rglob("*") if path.is_file()),
    )
    local_path_needles = {
        spelling.encode("utf-8")
        for local_path in (root, root.parent)
        for spelling in (
            str(local_path),
            local_path.as_posix(),
            str(local_path).replace("\\", "\\\\"),
        )
    }
    for output in portable_outputs:
        if (
            any(needle in output for needle in local_path_needles)
            or b"kapisch-switch-" in output
            or b'"pid"' in output
            or b"pid=" in output
        ):
            raise AssertionError("portable canonical output contains local process data")

    return {
        "benchmark-json": sha256_hex(benchmark.stdout),
        "canonical-json": sha256_hex(canonical_json),
        "controller-view": sha256_hex((task_dir / "04-controller-view.toml").read_bytes()),
        "exact-evidence-crlf": sha256_hex(b"status: DONE\r\n"),
        "exact-evidence-lf": sha256_hex(b"status: DONE\n"),
        "knowledge": sha256_hex(knowledge),
        "manifest": sha256_hex(manifest_bytes),
        "migration-tree": migration_digest,
        "metrics": sha256_hex(metrics),
        "outcome-at-f01-1": outcome_digests["AT-F01-1"],
        "outcome-at-r01-1": outcome_digests["AT-R01-1"],
        "outcome-at-t01-1": outcome_digests["AT-T01-1"],
        "outcome-findings": sha256_hex(outcome_findings),
        "profile": sha256_hex(installed_profile.read_bytes()),
        "review-invocation-final": invocation_digests["reviews/final/00-final-invocation.toml"],
        "review-invocation-round-0": invocation_digests["reviews/round-0/00-review-invocation.toml"],
        "route": sha256_hex(route_bytes),
        "state": sha256_hex(state_path.read_bytes()),
        "state-markdown": sha256_hex(state_markdown),
    }


def _available_locales() -> tuple[str, ...]:
    original = locale.setlocale(locale.LC_ALL)
    available = ["C"]
    try:
        for candidate in ("C.UTF-8", "en_US.UTF-8", "en-US"):
            if candidate == "C":
                continue
            try:
                locale.setlocale(locale.LC_ALL, candidate)
            except locale.Error:
                continue
            available.append(candidate)
            break
    finally:
        locale.setlocale(locale.LC_ALL, original)
    return tuple(available)


def _generate_subprocess(*, cwd: Path, seed: str, timezone: str, locale_name: str, unrelated_value: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as temporary:
        environment = dict(os.environ)
        environment.update({
            "PYTHONPATH": str(PLUGIN_ROOT),
            "PYTHONHASHSEED": seed,
            "TZ": timezone,
            "LC_ALL": locale_name,
            "KAPISCH_TEST_UNRELATED": unrelated_value,
        })
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--emit-digest", str(Path(temporary) / "generated")],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


class DeterministicAcceptanceTests(unittest.TestCase):
    def test_committed_cross_platform_digest_vector(self) -> None:
        expected = json.loads(EXPECTED_VECTOR.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(_generate(Path(temporary) / "one", reverse_inputs=False), expected)

    def test_relocation_and_input_order_do_not_change_portable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(
                _generate(root / "first location", reverse_inputs=False),
                _generate(root / "second location", reverse_inputs=True),
            )

    def test_environment_and_cwd_perturbations_match_vector(self) -> None:
        expected = json.loads(EXPECTED_VECTOR.read_text(encoding="utf-8"))
        locales = _available_locales()
        if len(locales) == 1:
            print("coverage_note=non-C locale unavailable; C-locale perturbation coverage remains active")
        with tempfile.TemporaryDirectory() as unrelated:
            for cwd in (REPOSITORY_ROOT, PLUGIN_ROOT, Path(unrelated)):
                for seed, timezone in (("1", "UTC"), ("8675309", "America/New_York")):
                    for locale_name in locales:
                        with self.subTest(cwd=cwd, seed=seed, timezone=timezone, locale=locale_name):
                            self.assertEqual(_generate_subprocess(cwd=cwd, seed=seed, timezone=timezone, locale_name=locale_name, unrelated_value="irrelevant"), expected)

    def test_exact_evidence_newlines_remain_distinct(self) -> None:
        self.assertEqual(sha256_hex(b"status: DONE\n"), "804aaae7bd1b6d3585d7f60cd58893771aa9439bbbfc76f62293ef7acb6898b4")
        self.assertEqual(sha256_hex(b"status: DONE\r\n"), "801e597fbfe90fa4d5c41d36640ac24b97a19ad8e7b20daec399d9988c2ff1be")

    def test_persisted_evidence_newline_change_invalidates_exact_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            shutil.copytree(TASK_FIXTURE, task_dir)
            evidence = task_dir / "delegations/D01/01-evidence.md"
            original = evidence.read_bytes()
            changed = original.replace(b"\n", b"\r\n")
            self.assertNotEqual(changed, original)
            evidence.write_bytes(changed)
            result = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts/validate_kapisch.py"),
                    "--task-dir",
                    str(task_dir),
                    "--format",
                    "json",
                ],
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            findings = json.loads(result.stdout)
            self.assertTrue(
                any(
                    finding["code"] == "TWV-DELEG-STALE-EVIDENCE"
                    for finding in findings
                ),
                findings,
            )

            route_path = task_dir / "delegations/00-route.toml"
            route = tomllib.loads(route_path.read_text(encoding="utf-8"))
            route["steps"][0]["evidence_sha256"] = sha256_hex(changed)
            route_path.write_bytes(render_route(route))
            rebound = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts/validate_kapisch.py"),
                    "--task-dir",
                    str(task_dir),
                    "--format",
                    "json",
                ],
                capture_output=True,
                check=False,
            )
            self.assertEqual(rebound.returncode, 0, rebound.stdout + rebound.stderr)

    def test_persisted_review_newline_change_requires_complete_rebinding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            shutil.copytree(TASK_FIXTURE, task_dir)
            report_path = task_dir / "reviews/round-0/03-review.md"
            original = report_path.read_bytes()
            changed = original.replace(b"\n", b"\r\n")
            self.assertNotEqual(changed, original)
            report_path.write_bytes(changed)

            stale = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts/validate_kapisch.py"),
                    "--task-dir",
                    str(task_dir),
                    "--format",
                    "json",
                ],
                capture_output=True,
                check=False,
            )
            self.assertEqual(stale.returncode, 2)
            findings = json.loads(stale.stdout)
            self.assertTrue(
                any(
                    finding["code"] == "TWV-REVIEW-STALE-EVIDENCE"
                    for finding in findings
                ),
                findings,
            )

            report_digest = sha256_hex(changed)
            invocation_path = task_dir / "reviews/round-0/00-review-invocation.toml"
            invocation = tomllib.loads(invocation_path.read_text(encoding="utf-8"))
            invocation["result_sha256"] = report_digest
            invocation_bytes = render_reviewer_invocation(invocation)
            invocation_path.write_bytes(invocation_bytes)

            outcome_path = task_dir / "stage-outcomes/AT-R01-1.toml"
            outcome = tomllib.loads(outcome_path.read_text(encoding="utf-8"))
            outcome["invocation_sha256"] = sha256_hex(invocation_bytes)
            outcome["report_sha256"] = report_digest
            for verification in outcome["verification"]:
                if verification["evidence_ref"] == "reviews/round-0/03-review.md":
                    verification["output_sha256"] = report_digest
            outcome_path.write_bytes(render_outcome(outcome))

            graph_path = task_dir / "02-execution-graph.toml"
            manifest = tomllib.loads(graph_path.read_text(encoding="utf-8"))
            for node in manifest["nodes"]:
                if node["id"] == "R01":
                    for evidence in node["verification_evidence"]:
                        if evidence["evidence_ref"] == "reviews/round-0/03-review.md":
                            evidence["output_sha256"] = report_digest
            graph_path.write_bytes(render_manifest(manifest, initial=False))

            rendered_view = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts/render_controller_view.py"),
                    "--task-dir",
                    str(task_dir),
                ],
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                rendered_view.returncode,
                0,
                rendered_view.stdout + rendered_view.stderr,
            )
            rebound = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_ROOT / "scripts/validate_kapisch.py"),
                    "--task-dir",
                    str(task_dir),
                    "--format",
                    "json",
                ],
                capture_output=True,
                check=False,
            )
            self.assertEqual(rebound.returncode, 0, rebound.stdout + rebound.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--emit-digest":
        sys.stdout.buffer.write(canonical_json_line(_generate(Path(sys.argv[2]), reverse_inputs=False)))
    else:
        unittest.main()
