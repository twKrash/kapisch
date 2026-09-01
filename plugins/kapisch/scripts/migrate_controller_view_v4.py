#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kapisch_validation.canonical_toml import render_toml
from kapisch_validation.cli import validate
from kapisch_validation.manifest import parse_manifest
from kapisch_validation.references import parse_state
from render_controller_view import main as render_view


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--destination-task-dir", required=True, type=Path)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve:
        parser.error("migration requires explicit --approve")
    source, destination = args.task_dir.resolve(), args.destination_task_dir.resolve()
    if not source.is_dir() or destination.exists() or source == destination or destination.is_relative_to(source):
        return 2
    if any(path.is_symlink() for path in source.rglob("*")):
        return 2
    manifest_result = parse_manifest(source / "02-execution-graph.toml")
    state, _ = parse_state(source / "03-state.toml")
    if manifest_result.manifest is None or state is None or manifest_result.manifest.version != 3 or state.workflow_status != "complete" or validate(ROOT / "skills" / "kapisch", source):
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kapisch-v4-", dir=destination.parent) as temporary:
        staged = Path(temporary) / destination.name
        shutil.copytree(source, staged, copy_function=shutil.copy2)
        graph = tomllib.loads((staged / "02-execution-graph.toml").read_text(encoding="utf-8"))
        graph["version"] = 4
        graph["controller_view"] = "04-controller-view.toml"
        outcomes = staged / "stage-outcomes"
        outcomes.mkdir()
        for node in graph["nodes"]:
            assignment = node.get("assignment")
            attempts = assignment.get("attempts") if isinstance(assignment, dict) else None
            if not isinstance(attempts, list) or len(attempts) != 1:
                return 2
            for attempt in attempts:
                if not isinstance(attempt, dict) or attempt.get("status") != "complete":
                    return 2
                attempt_id = attempt.get("id")
                if not isinstance(attempt_id, str):
                    return 2
                outcome_path = f"stage-outcomes/{attempt_id}.toml"
                attempt["outcome_path"] = outcome_path
                role, invocation = node["executor_class"], node.get("reviewer_invocation")
                invocation_raw: dict[str, object] = {}
                if role == "reviewer":
                    if not isinstance(invocation, str) or not (staged / invocation).is_file():
                        return 2
                    invocation_raw = tomllib.loads((staged / invocation).read_text(encoding="utf-8"))
                    if invocation_raw.get("returned_decision") not in {"approve", "ready"}:
                        return 2
                report = staged / node["report"]
                if not report.is_file():
                    return 2
                outcome = {"version": 1, "task_id": graph["task_id"], "node_id": node["id"], "role": role, "assignment_id": assignment["id"], "attempt_id": attempt_id, "lifecycle": attempt["status"], "role_status": "done" if attempt["status"] == "complete" else attempt["status"], "base_revision": node["revision"]["base"], "head_revision": node["revision"]["head"], "working_tree_state_sha256": "unavailable", "report_path": node["report"], "report_sha256": digest(report), "invocation_path": invocation if role == "reviewer" else "unavailable", "invocation_id": invocation_raw.get("invocation_id", "unavailable") if role == "reviewer" else "unavailable", "invocation_sha256": digest(staged / invocation) if role == "reviewer" else "unavailable", "reviewer_decision": invocation_raw.get("returned_decision", "unavailable") if role == "reviewer" else "unavailable", "redispatch_reason": "none", "predecessor_attempt_id": "unavailable", "retry_budget_delta": 0, "next_action_reason": "completed", "findings": [], "verification": []}
                evidence = node.get("verification_evidence")
                if not isinstance(evidence, list) or any(
                    not isinstance(record, dict)
                    or set(record) != {"id", "check", "result", "evidence_ref", "output_sha256", "revision"}
                    or record["result"] not in {"pass", "fail", "not-run", "unavailable"}
                    for record in evidence
                ):
                    return 2
                outcome["verification"] = [
                    {key: record[key] for key in ("check", "result", "evidence_ref", "output_sha256")}
                    for record in evidence
                ]
                (staged / outcome_path).write_bytes(render_toml(outcome))
        (staged / "02-execution-graph.toml").write_bytes(render_toml(graph))
        state_raw = dict(state.raw)
        state_raw["controller_view_path"] = "04-controller-view.toml"
        state_raw["controller_view_sha256"] = "0" * 64
        (staged / "03-state.toml").write_bytes(render_toml(state_raw))
        if render_view(["--task-dir", str(staged)]) or validate(ROOT / "skills" / "kapisch", staged):
            return 2
        os.replace(staged, destination)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
