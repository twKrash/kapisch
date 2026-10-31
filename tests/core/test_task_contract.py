"""Regression tests for the portable single-task contract.

Runs under the repository's canonical unittest gate
(``python -m unittest discover -s tests/core``) and still works under pytest:
functions take a temporary project root, and parametrization becomes one
unittest case per row.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from kapisch_core import task_contract
from kapisch_core.task_contract import ContractError, validate_acceptance, validate_run

RUN_DIR = ".kapisch/runs/r1"
RUN_REF = f"{RUN_DIR}/run.json"


@contextmanager
def _raises(expected, match=None):
    try:
        yield
    except expected as exc:
        if match is not None and re.search(match, str(exc)) is None:
            raise AssertionError(
                f"expected {match!r} in {type(exc).__name__}: {exc}"
            ) from exc
        return
    raise AssertionError(f"expected {expected.__name__} to be raised")


def _params(argnames, argvalues):
    names = (argnames,) if isinstance(argnames, str) else tuple(argnames)

    def as_row(value):
        if len(names) == 1:
            return {names[0]: value}
        return dict(zip(names, value, strict=True))

    rows = [as_row(value) for value in argvalues]

    def decorate(func):
        original = getattr(func, "_original", func)
        original._rows = [
            {**combined, **row}
            for combined in getattr(original, "_rows", [{}])
            for row in rows
        ]

        def wrapper(tmp_path=None):
            del tmp_path
            for row in original._rows:
                with tempfile.TemporaryDirectory() as root:
                    original(tmp_path=Path(root), **row)

        wrapper._original = original
        wrapper._rows = original._rows
        return wrapper

    return decorate


def load_tests(loader, tests, pattern):
    del loader, tests, pattern
    suite = unittest.TestSuite()
    for name, func in sorted(globals().items()):
        if not name.startswith("test_") or not callable(func):
            continue
        target = getattr(func, "_original", func)
        for index, row in enumerate(getattr(target, "_rows", [{}])):

            def run(target=target, row=row):
                with tempfile.TemporaryDirectory() as root:
                    target(tmp_path=Path(root), **row)

            suite.addTest(
                unittest.FunctionTestCase(run, description=f"{name}[{index}]")
            )
    return suite


def _reset_to_unclaimed(tmp_path):
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
        "outcome_ref",
        "outcome_digest",
    ):
        run.pop(key, None)
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in (
        "attempts/a1.json",
        "attempts/a1-output.json",
        "aggregation.json",
        "outcome.json",
        "dispatch-claim.json",
    ):
        (tmp_path / RUN_DIR / ref).unlink(missing_ok=True)
    return run_path


def fixture(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/spec.md").write_text("approved requirements\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "docs/spec.md"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "governing input"], check=True
    )
    digest = hashlib.sha256((tmp_path / "docs/spec.md").read_bytes()).hexdigest()
    inputs = [{"ref": "docs/spec.md", "digest": digest}]

    def put(name, record):
        raw = json.dumps(record, sort_keys=True).encode()
        artifact = tmp_path / name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(raw)
        return name, hashlib.sha256(raw).hexdigest()

    decision_ref = f"{RUN_DIR}/decisions/d1.json"
    decision = {
        "decision_id": "d1",
        "question_id": "q1",
        "decision_type": "approval",
        "question": "Authorize this bounded task",
        "answer": "Approved",
        "subject": "implementation of t1",
        "scope": "src/",
        "source_kind": "direct_operator",
        "governing_inputs": inputs,
    }
    _, decision_digest = put(decision_ref, decision)
    applicability_ref = f"{RUN_DIR}/applicability.json"
    applicability = {
        "decision_id": "d1",
        "decision_ref": decision_ref,
        "decision_digest": decision_digest,
        "answer_digest": hashlib.sha256(decision["answer"].encode()).hexdigest(),
        "subject": decision["subject"],
        "scope": decision["scope"],
        "governing_inputs": inputs,
        "result": "applicable",
        "reason": "The human explicitly authorized this bounded scope.",
        "host_native_fallback_authorized": True,
        "fallback_authorization_reason": "The bounded host-native route was explicitly approved.",
    }
    _, applicability_digest = put(applicability_ref, applicability)
    work_ref = f"{RUN_DIR}/workorder.json"
    work = {
        "workorder_id": "w1",
        "decision_id": "d1",
        "decision_ref": decision_ref,
        "decision_digest": decision_digest,
        "applicability_ref": applicability_ref,
        "applicability_digest": applicability_digest,
        "subject": decision["subject"],
        "scope": decision["scope"],
        "task": {"task_id": "t1"},
        "acceptance_criteria": ["produced valid evidence for the scoped change"],
        "governing_inputs": inputs,
        "required_capabilities": ["write"],
        "worker_route": "host_native_fallback",
        "worker_role": "worker",
        "canonical_implementer_available": False,
    }
    _, work_digest = put(work_ref, work)
    run = {
        "run_id": "r1",
        "workorder_ref": work_ref,
        "workorder_digest": work_digest,
        "attempt_allocation": {
            "attempt_id": "a1",
            "output_ref": f"{RUN_DIR}/attempts/a1-output.json",
        },
    }
    put(RUN_REF, run)
    task_contract.claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    output_ref = f"{RUN_DIR}/attempts/a1-output.json"
    (tmp_path / output_ref).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / output_ref).write_text('{"evidence": "passed"}')
    output_digest = hashlib.sha256((tmp_path / output_ref).read_bytes()).hexdigest()
    attempt_ref = f"{RUN_DIR}/attempts/a1.json"
    attempt = {
        "attempt_id": "a1",
        "task_id": "t1",
        "workorder_id": "w1",
        "workorder_ref": work_ref,
        "workorder_digest": work_digest,
        "decision_id": "d1",
        "decision_digest": decision_digest,
        "status": "succeeded",
        "output_ref": output_ref,
        "output_digest": output_digest,
    }
    _, attempt_digest = put(attempt_ref, attempt)
    report_ref = f"{RUN_DIR}/aggregation.json"
    report = {
        "coverage": ["t1"],
        "acceptance_criteria": ["produced valid evidence for the scoped change"],
        "result": "complete",
        "attempt_ref": attempt_ref,
        "attempt_digest": attempt_digest,
        "output_ref": output_ref,
        "output_digest": output_digest,
        "attempt_id": "a1",
        "task_id": "t1",
        "workorder_ref": work_ref,
        "workorder_id": "w1",
        "workorder_digest": work_digest,
        "decision_id": "d1",
        "decision_digest": decision_digest,
        "failures": [],
        "conflicts": [],
        "missing_references": [],
        "unresolved_issues": [],
    }
    _, report_digest = put(report_ref, report)
    run.update(
        attempt_ref=attempt_ref,
        attempt_digest=attempt_digest,
        aggregation_ref=report_ref,
        aggregation_digest=report_digest,
    )
    put(RUN_REF, run)
    return tmp_path, inputs


def test_persisted_files_reconstruct_acceptance(tmp_path):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    assert records["decision"]["decision_id"] == "d1"
    outcome = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={
            "write": {"status": "supported", "reason": "Pi worker can write files"}
        },
    )
    assert outcome == {
        "status": "complete",
        "run_ref": RUN_REF,
        "workorder_id": "w1",
        "workorder_digest": hashlib.sha256(
            (tmp_path / f"{RUN_DIR}/workorder.json").read_bytes()
        ).hexdigest(),
        "decision_id": "d1",
        "decision_digest": hashlib.sha256(
            (tmp_path / f"{RUN_DIR}/decisions/d1.json").read_bytes()
        ).hexdigest(),
        "authority": {
            "decision_type": "approval",
            "decision_id": "d1",
            "subject": "implementation of t1",
            "scope": "src/",
        },
        "decision": {
            "ref": f"{RUN_DIR}/decisions/d1.json",
            "decision_id": "d1",
            "source_kind": "direct_operator",
            "subject": "implementation of t1",
            "scope": "src/",
            "applicability": {
                "status": "applicable",
                "ref": f"{RUN_DIR}/applicability.json",
                "digest": hashlib.sha256(
                    (tmp_path / f"{RUN_DIR}/applicability.json").read_bytes()
                ).hexdigest(),
                "reason": "The human explicitly authorized this bounded scope.",
            },
        },
        "workorder_ref": f"{RUN_DIR}/workorder.json",
        "attempt": {
            "ref": f"{RUN_DIR}/attempts/a1.json",
            "id": "a1",
            "status": "succeeded",
        },
        "evidence_refs": [
            {
                "kind": "attempt_output",
                "ref": f"{RUN_DIR}/attempts/a1-output.json",
                "digest": hashlib.sha256(
                    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").read_bytes()
                ).hexdigest(),
            }
        ],
        "aggregation_report": {
            "ref": f"{RUN_DIR}/aggregation.json",
            "digest": hashlib.sha256(
                (tmp_path / f"{RUN_DIR}/aggregation.json").read_bytes()
            ).hexdigest(),
            "result": "complete",
            "coverage": ["t1"],
            "acceptance_criteria": ["produced valid evidence for the scoped change"],
        },
    }
    assert (
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={
                "write": {
                    "status": "supported",
                    "reason": "test adapter capability probe",
                }
            },
        )
        == outcome
    )


def test_stale_governing_inputs_require_reassessment(tmp_path):
    _, _ = fixture(tmp_path)
    (tmp_path / "docs/spec.md").write_text("changed after approval\n")
    with _raises(ContractError, match="reassessment"):
        validate_run(tmp_path, RUN_REF)


def test_failed_attempt_missing_output_and_unresolved_report_block_outcome(tmp_path):
    _, _ = fixture(tmp_path)
    attempt = json.loads((tmp_path / f"{RUN_DIR}/attempts/a1.json").read_text())
    attempt["status"] = "failed"
    attempt_path = tmp_path / f"{RUN_DIR}/attempts/a1.json"
    attempt_path.write_text(json.dumps(attempt))
    run = json.loads((tmp_path / f"{RUN_DIR}/run.json").read_text())
    run["attempt_digest"] = hashlib.sha256(attempt_path.read_bytes()).hexdigest()
    report_path = tmp_path / f"{RUN_DIR}/aggregation.json"
    report = json.loads(report_path.read_text())
    report["attempt_digest"] = run["attempt_digest"]
    report_path.write_text(json.dumps(report, sort_keys=True))
    run["aggregation_digest"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    (tmp_path / RUN_REF).write_text(json.dumps(run))
    with _raises(ContractError, match="failed"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_required_capability_must_be_supported_and_explained(tmp_path):
    _, _ = fixture(tmp_path)
    for capability in (
        {"status": "unknown", "reason": "unproven"},
        {"status": "unsupported", "reason": "not available"},
        {"status": "supported", "reason": ""},
    ):
        with _raises(ContractError, match="not supported"):
            validate_acceptance(tmp_path, RUN_REF, capabilities={"write": capability})


def test_portable_reference_cannot_escape_root_through_symlink(tmp_path):
    _, _ = fixture(tmp_path)
    outside = tmp_path.parent / "outside.json"
    outside.write_text('{"run_id":"foreign"}')
    (tmp_path / "alias.json").symlink_to(outside)
    with _raises(ContractError, match="escapes"):
        validate_run(tmp_path, "alias.json")


def test_missing_attempt_output_cannot_complete(tmp_path):
    fixture(tmp_path)
    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").unlink()
    with _raises(
        ContractError,
        match="unreadable artifact: .kapisch/runs/r1/attempts/a1-output.json",
    ):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_aggregation_with_incomplete_coverage_cannot_complete(tmp_path):
    fixture(tmp_path)
    report_path = tmp_path / f"{RUN_DIR}/aggregation.json"
    report = json.loads(report_path.read_text())
    report["coverage"] = []
    report_path.write_text(json.dumps(report, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["aggregation_digest"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="coverage mismatch"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


@_params(
    ("answer", "result"),
    [
        ("No. I explicitly refuse authorization.", "not_applicable"),
        ("Maybe; I am not sure.", "ambiguous"),
        ("Yes, but only if the scope changes.", "ambiguous"),
    ],
)
def test_non_applicable_or_ambiguous_answer_cannot_be_promoted(
    answer, result, tmp_path
):
    fixture(tmp_path)
    decision_path = tmp_path / f"{RUN_DIR}/decisions/d1.json"
    decision = json.loads(decision_path.read_text())
    decision["answer"] = answer
    decision_path.write_text(json.dumps(decision, sort_keys=True))
    app_path = tmp_path / f"{RUN_DIR}/applicability.json"
    app = json.loads(app_path.read_text())
    app.update(
        decision_digest=hashlib.sha256(decision_path.read_bytes()).hexdigest(),
        answer_digest=hashlib.sha256(answer.encode()).hexdigest(),
        result=result,
        reason="The response does not authorize the requested bounded WorkOrder.",
    )
    app_path.write_text(json.dumps(app, sort_keys=True))
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work.update(
        decision_digest=hashlib.sha256(decision_path.read_bytes()).hexdigest(),
        applicability_digest=hashlib.sha256(app_path.read_bytes()).hexdigest(),
    )
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="applicability"):
        validate_run(tmp_path, RUN_REF)


def test_attempt_cannot_be_reused_after_workorder_identity_changes(tmp_path):
    fixture(tmp_path)
    decision_ref = f"{RUN_DIR}/decisions/d2.json"
    decision = {
        "decision_id": "d2",
        "question_id": "q2",
        "decision_type": "approval",
        "question": "Authorize the replacement task",
        "answer": "Approved",
        "subject": "replacement task",
        "scope": "other/",
        "source_kind": "direct_operator",
        "governing_inputs": [
            {
                "ref": "docs/spec.md",
                "digest": hashlib.sha256(
                    (tmp_path / "docs/spec.md").read_bytes()
                ).hexdigest(),
            }
        ],
    }
    decision_path = tmp_path / decision_ref
    decision_path.write_text(json.dumps(decision, sort_keys=True))
    decision_digest = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    applicability_ref = f"{RUN_DIR}/applicability.json"
    applicability = {
        "decision_id": "d2",
        "decision_ref": decision_ref,
        "decision_digest": decision_digest,
        "answer_digest": hashlib.sha256(decision["answer"].encode()).hexdigest(),
        "subject": "replacement task",
        "scope": "other/",
        "governing_inputs": decision["governing_inputs"],
        "result": "applicable",
        "reason": "The human explicitly authorized the replacement scope.",
        "host_native_fallback_authorized": True,
        "fallback_authorization_reason": "The bounded host-native route was explicitly approved.",
    }
    applicability_path = tmp_path / applicability_ref
    applicability_path.write_text(json.dumps(applicability, sort_keys=True))
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work.update(
        workorder_id="w2",
        decision_id="d2",
        decision_ref=decision_ref,
        decision_digest=decision_digest,
        applicability_ref=applicability_ref,
        applicability_digest=hashlib.sha256(
            applicability_path.read_bytes()
        ).hexdigest(),
        subject="replacement task",
        scope="other/",
    )
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="dispatch claim does not match"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_duplicate_canonical_decision_identity_blocks_resume(tmp_path):
    fixture(tmp_path)
    duplicate = tmp_path / ".kapisch/runs/other/decisions/d1.json"
    duplicate.parent.mkdir(parents=True)
    decision = json.loads((tmp_path / f"{RUN_DIR}/decisions/d1.json").read_text())
    decision["scope"] = "conflicting/"
    duplicate.write_text(json.dumps(decision, sort_keys=True))
    with _raises(ContractError, match="decision identity is not unique"):
        validate_run(tmp_path, RUN_REF)


@_params("status", ["unsupported", "unknown", "unproven"])
def test_capability_gaps_block_before_attempt_creation(tmp_path, status):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
    ):
        run.pop(key)
    run_path.write_text(json.dumps(run, sort_keys=True))
    (tmp_path / f"{RUN_DIR}/attempts/a1.json").unlink()
    (tmp_path / f"{RUN_DIR}/aggregation.json").unlink()
    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").unlink()
    (tmp_path / f"{RUN_DIR}/dispatch-claim.json").unlink()
    with _raises(ContractError, match="required capability"):
        task_contract.validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": status, "reason": "probe result"}},
            canonical_implementer_available=False,
        )


def test_authorized_host_fallback_requires_canonical_implementer_unavailable(tmp_path):
    fixture(tmp_path)
    for path in ("attempts/a1.json", "aggregation.json", "attempts/a1-output.json"):
        (tmp_path / RUN_DIR / path).unlink()
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
    ):
        run.pop(key)
    run_path.write_text(json.dumps(run, sort_keys=True))
    (tmp_path / RUN_DIR / "dispatch-claim.json").unlink()
    with _raises(ContractError, match="canonical implementer"):
        task_contract.validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=True,
        )
    work = task_contract.validate_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    assert work["workorder"]["worker_route"] == "host_native_fallback"
    assert work["attempt_allocation"]["attempt_id"] == "a1"


def test_staged_governing_input_requires_reassessment(tmp_path):
    fixture(tmp_path)
    source = tmp_path / "docs/spec.md"
    source.write_text("staged but not approved\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "docs/spec.md"], check=True)
    source.write_text("approved requirements\n")
    with _raises(ContractError, match="reassessment"):
        validate_run(tmp_path, RUN_REF)


def test_committed_governing_input_change_requires_reassessment(tmp_path):
    fixture(tmp_path)
    source = tmp_path / "docs/spec.md"
    source.write_text("new committed requirements\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "docs/spec.md"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "change requirements"], check=True
    )
    with _raises(ContractError, match="reassessment"):
        validate_run(tmp_path, RUN_REF)


def test_decision_question_identity_is_required(tmp_path):
    fixture(tmp_path)
    decision_path = tmp_path / f"{RUN_DIR}/decisions/d1.json"
    decision = json.loads(decision_path.read_text())
    del decision["question_id"]
    decision_path.write_text(json.dumps(decision, sort_keys=True))
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work["decision_digest"] = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="question identity"):
        validate_run(tmp_path, RUN_REF)


def test_external_artifact_decision_requires_stable_source_reference(tmp_path):
    fixture(tmp_path)
    decision_path = tmp_path / f"{RUN_DIR}/decisions/d1.json"
    decision = json.loads(decision_path.read_text())
    decision["source_kind"] = "external_artifact"
    decision["source_ref"] = ""
    decision_path.write_text(json.dumps(decision, sort_keys=True))
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work["decision_digest"] = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="work order is not authorized"):
        validate_run(tmp_path, RUN_REF)


def test_outcome_is_persisted_and_reconstructed_in_a_fresh_process(tmp_path):
    fixture(tmp_path)
    expected = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={
            "write": {"status": "supported", "reason": "test adapter write support"}
        },
    )
    outcome_ref = f"{RUN_DIR}/outcome.json"
    outcome_path = tmp_path / outcome_ref
    outcome_path.write_text(json.dumps(expected, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["outcome_ref"] = outcome_ref
    run["outcome_digest"] = hashlib.sha256(outcome_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    script = (
        "import json, sys; from kapisch_core.task_contract import validate_outcome; "
        "print(json.dumps(validate_outcome(sys.argv[1], sys.argv[2], "
        "capabilities={'write': {'status': 'supported', 'reason': 'restart probe'}}), sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == expected


def test_host_native_fallback_requires_persisted_explicit_authorization(tmp_path):
    fixture(tmp_path)
    for path in ("attempts/a1.json", "aggregation.json", "attempts/a1-output.json"):
        (tmp_path / RUN_DIR / path).unlink()
    app_path = tmp_path / f"{RUN_DIR}/applicability.json"
    app = json.loads(app_path.read_text())
    app["host_native_fallback_authorized"] = False
    app_path.write_text(json.dumps(app, sort_keys=True))
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work["applicability_digest"] = hashlib.sha256(app_path.read_bytes()).hexdigest()
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
    ):
        run.pop(key)
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="fallback is not authorized"):
        task_contract.validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )


def test_workorder_requires_explicit_acceptance_criteria(tmp_path):
    fixture(tmp_path)
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    del work["acceptance_criteria"]
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="acceptance criteria"):
        validate_run(tmp_path, RUN_REF)


def test_aggregation_must_evaluate_workorder_acceptance_criteria(tmp_path):
    fixture(tmp_path)
    report_path = tmp_path / f"{RUN_DIR}/aggregation.json"
    report = json.loads(report_path.read_text())
    report["acceptance_criteria"] = []
    report_path.write_text(json.dumps(report, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["aggregation_digest"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="acceptance criteria"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_dispatch_rejects_preexisting_attempt_allocation(tmp_path):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
    ):
        run.pop(key)
    run_path.write_text(json.dumps(run, sort_keys=True))
    (tmp_path / RUN_DIR / "dispatch-claim.json").unlink()
    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").unlink()
    with _raises(ContractError, match="attempt allocation already exists"):
        task_contract.validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )


def test_aggregation_report_binds_exact_attempt_and_output_digests(tmp_path):
    fixture(tmp_path)
    output_path = tmp_path / f"{RUN_DIR}/attempts/a1-output.json"
    output_path.write_text("replacement output\n")
    attempt_path = tmp_path / f"{RUN_DIR}/attempts/a1.json"
    attempt = json.loads(attempt_path.read_text())
    attempt["output_digest"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    attempt_path.write_text(json.dumps(attempt, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["attempt_digest"] = hashlib.sha256(attempt_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="report is not bound"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


@_params(
    "field",
    ["failures", "conflicts", "missing_references", "unresolved_issues"],
)
@_params("value", [None, "missing"])
def test_aggregation_report_requires_explicitly_empty_issue_arrays(
    tmp_path, field, value
):
    fixture(tmp_path)
    report_path = tmp_path / f"{RUN_DIR}/aggregation.json"
    report = json.loads(report_path.read_text())
    if value == "missing":
        del report[field]
    else:
        report[field] = value
    report_path.write_text(json.dumps(report, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["aggregation_digest"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="aggregation report"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_malformed_decision_source_kind_fails_with_contract_error(tmp_path):
    fixture(tmp_path)
    decision_path = tmp_path / f"{RUN_DIR}/decisions/d1.json"
    decision = json.loads(decision_path.read_text())
    decision["source_kind"] = []
    decision_path.write_text(json.dumps(decision, sort_keys=True))
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work["decision_digest"] = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="work order is not authorized"):
        validate_run(tmp_path, RUN_REF)


def test_dispatch_rejects_redispatch_after_persisted_completion_even_if_artifacts_are_missing(
    tmp_path,
):
    fixture(tmp_path)
    outcome = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
    )
    outcome_ref = f"{RUN_DIR}/outcome.json"
    outcome_path = tmp_path / outcome_ref
    outcome_path.write_text(json.dumps(outcome, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run.update(
        outcome_ref=outcome_ref,
        outcome_digest=hashlib.sha256(outcome_path.read_bytes()).hexdigest(),
    )
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in ("attempts/a1.json", "attempts/a1-output.json", "aggregation.json"):
        (tmp_path / RUN_DIR / ref).unlink()
    with _raises(ContractError, match="dispatch claim"):
        task_contract.validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )


def test_acceptance_rejects_noncanonical_allocated_output_name(tmp_path):
    fixture(tmp_path)
    bad_output_ref = f"{RUN_DIR}/attempts/a1-other.json"
    bad_output_path = tmp_path / bad_output_ref
    bad_output_path.write_text("replacement output\n")
    attempt_path = tmp_path / f"{RUN_DIR}/attempts/a1.json"
    attempt = json.loads(attempt_path.read_text())
    attempt["output_ref"] = bad_output_ref
    attempt["output_digest"] = hashlib.sha256(bad_output_path.read_bytes()).hexdigest()
    attempt_path.write_text(json.dumps(attempt, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["attempt_allocation"]["output_ref"] = bad_output_ref
    claim_path = tmp_path / f"{RUN_DIR}/dispatch-claim.json"
    claim = json.loads(claim_path.read_text())
    claim["output_ref"] = bad_output_ref
    claim_path.write_text(json.dumps(claim, sort_keys=True))
    run["attempt_digest"] = hashlib.sha256(attempt_path.read_bytes()).hexdigest()
    report_path = tmp_path / f"{RUN_DIR}/aggregation.json"
    report = json.loads(report_path.read_text())
    report.update(
        attempt_digest=run["attempt_digest"],
        output_ref=bad_output_ref,
        output_digest=attempt["output_digest"],
    )
    report_path.write_text(json.dumps(report, sort_keys=True))
    run["aggregation_digest"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="allocated output reference mismatch"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_validate_outcome_rejects_rebound_attempt_when_report_is_unchanged(tmp_path):
    fixture(tmp_path)
    outcome = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
    )
    outcome_ref = f"{RUN_DIR}/outcome.json"
    outcome_path = tmp_path / outcome_ref
    outcome_path.write_text(json.dumps(outcome, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run.update(
        outcome_ref=outcome_ref,
        outcome_digest=hashlib.sha256(outcome_path.read_bytes()).hexdigest(),
    )
    output_path = tmp_path / f"{RUN_DIR}/attempts/a1-output.json"
    output_path.write_text("replacement output\n")
    attempt_path = tmp_path / f"{RUN_DIR}/attempts/a1.json"
    attempt = json.loads(attempt_path.read_text())
    attempt["output_digest"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    attempt_path.write_text(json.dumps(attempt, sort_keys=True))
    run["attempt_digest"] = hashlib.sha256(attempt_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="report is not bound"):
        task_contract.validate_outcome(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "fresh process"}},
        )


@_params("status", [[], {}, None, "missing", "unknown", "unsupported"])
def test_dispatch_rejects_malformed_or_unsupported_capability_status(tmp_path, status):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
        "outcome_ref",
        "outcome_digest",
    ):
        run.pop(key, None)
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in (
        "attempts/a1.json",
        "attempts/a1-output.json",
        "aggregation.json",
        "outcome.json",
        "dispatch-claim.json",
    ):
        (tmp_path / RUN_DIR / ref).unlink(missing_ok=True)
    capability = {"reason": "adapter probe"}
    if status != "missing":
        capability["status"] = status
    with _raises(ContractError, match="required capability not supported"):
        task_contract.claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": capability},
            canonical_implementer_available=False,
        )
    assert not (tmp_path / RUN_DIR / "dispatch-claim.json").exists()


def test_acceptance_requires_valid_dispatch_claim(tmp_path):
    fixture(tmp_path)
    (tmp_path / f"{RUN_DIR}/dispatch-claim.json").unlink()
    with _raises(ContractError, match="dispatch claim is missing"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_dispatch_claim_blocks_restart_before_collection(tmp_path):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
        "outcome_ref",
        "outcome_digest",
    ):
        run.pop(key, None)
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in (
        "attempts/a1.json",
        "attempts/a1-output.json",
        "aggregation.json",
        "outcome.json",
        "dispatch-claim.json",
    ):
        (tmp_path / RUN_DIR / ref).unlink(missing_ok=True)

    claim = task_contract.claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    assert claim["attempt_allocation"]["attempt_id"] == "a1"
    assert (tmp_path / RUN_DIR / "dispatch-claim.json").is_file()
    assert not (tmp_path / f"{RUN_DIR}/attempts/a1.json").exists()
    assert not (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").exists()

    script = """
import sys
from kapisch_core.task_contract import ContractError, validate_dispatch
try:
    validate_dispatch(sys.argv[1], sys.argv[2], capabilities={"write": {"status": "supported", "reason": "restart"}}, canonical_implementer_available=False)
except ContractError as exc:
    print(type(exc).__name__ + ": " + str(exc))
else:
    raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "core"},
    )
    assert "dispatch claim" in result.stdout

    with _raises(ContractError, match="dispatch claim"):
        task_contract.claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )


def test_concurrent_dispatch_claims_allow_only_one_process(tmp_path):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
        "outcome_ref",
        "outcome_digest",
    ):
        run.pop(key, None)
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in (
        "attempts/a1.json",
        "attempts/a1-output.json",
        "aggregation.json",
        "outcome.json",
        "dispatch-claim.json",
    ):
        (tmp_path / RUN_DIR / ref).unlink(missing_ok=True)

    def claim():
        try:
            task_contract.claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities={"write": {"status": "supported", "reason": "available"}},
                canonical_implementer_available=False,
            )
        except ContractError:
            return "blocked"
        return "claimed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(results) == ["blocked", "claimed"]


@_params(
    ("field", "first", "second"),
    [
        ("result", "not_applicable", "applicable"),
        ("decision_id", "other", "d1"),
        ("scope", "src/", "src"),
        ("decision_ref", "other.json", ".kapisch/runs/r1/decisions/d1.json"),
        ("workorder_digest", "0" * 64, "1" * 64),
        ("output_ref", "other.json", ".kapisch/runs/r1/attempts/a1-output.json"),
    ],
)
@_params("reverse", [False, True])
def test_artifact_loader_rejects_duplicate_authority_fields(
    tmp_path, field, first, second, reverse
):
    values = [first, second]
    if reverse:
        values.reverse()
    raw = (
        '{"record":{"'
        + field
        + '":'
        + json.dumps(values[0])
        + ',"'
        + field
        + '":'
        + json.dumps(values[1])
        + "}}"
    )
    (tmp_path / "artifact.json").write_text(raw)
    with _raises(ContractError, match="duplicate JSON object key"):
        task_contract._load(tmp_path, "artifact.json", require_digest=False)


@_params(
    "duplicate_result",
    [
        '"result": "not_applicable",\n  "result": "applicable"',
        '"result": "applicable",\n  "result": "not_applicable"',
    ],
)
def test_dispatch_rejects_duplicate_applicability_result_before_claim(
    tmp_path, duplicate_result
):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    for key in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
        "outcome_ref",
        "outcome_digest",
    ):
        run.pop(key, None)
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in (
        "attempts/a1.json",
        "attempts/a1-output.json",
        "aggregation.json",
        "outcome.json",
        "dispatch-claim.json",
    ):
        (tmp_path / RUN_DIR / ref).unlink(missing_ok=True)

    applicability_path = tmp_path / f"{RUN_DIR}/applicability.json"
    raw = applicability_path.read_text().replace(
        '"result": "applicable"', duplicate_result
    )
    applicability_path.write_text(raw)
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work["applicability_digest"] = hashlib.sha256(raw.encode()).hexdigest()
    work_path.write_text(json.dumps(work, sort_keys=True))
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))

    with _raises(ContractError, match="duplicate JSON object key: result"):
        task_contract.claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()


def test_fresh_process_rejects_duplicate_authority_during_outcome_reconstruction(
    tmp_path,
):
    fixture(tmp_path)
    outcome = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
    )
    outcome_ref = f"{RUN_DIR}/outcome.json"
    outcome_path = tmp_path / outcome_ref
    outcome_path.write_text(json.dumps(outcome, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run.update(
        outcome_ref=outcome_ref,
        outcome_digest=hashlib.sha256(outcome_path.read_bytes()).hexdigest(),
    )

    applicability_path = tmp_path / f"{RUN_DIR}/applicability.json"
    raw = applicability_path.read_text().replace(
        '"result": "applicable"',
        '"result": "applicable",\n  "result": "not_applicable"',
    )
    applicability_path.write_text(raw)
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work["applicability_digest"] = hashlib.sha256(raw.encode()).hexdigest()
    work_path.write_text(json.dumps(work, sort_keys=True))
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))

    script = """
import sys
from kapisch_core.task_contract import ContractError, validate_outcome
try:
    validate_outcome(sys.argv[1], sys.argv[2], capabilities={"write": {"status": "supported", "reason": "restart"}})
except ContractError as exc:
    print(type(exc).__name__ + ": " + str(exc))
else:
    raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "core"},
    )
    assert "duplicate JSON object key: result" in result.stdout


@_params(
    "allocation",
    [None, {}, {"attempt_id": "a1"}],
)
def test_malformed_allocation_has_contract_error_in_fresh_process(tmp_path, allocation):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["attempt_allocation"] = allocation
    run_path.write_text(json.dumps(run, sort_keys=True))
    capabilities = {"write": {"status": "supported", "reason": "available"}}
    with _raises(ContractError):
        validate_acceptance(tmp_path, RUN_REF, capabilities=capabilities)

    script = """
import sys
from kapisch_core.task_contract import ContractError, validate_outcome
try:
    validate_outcome(sys.argv[1], sys.argv[2], capabilities={"write": {"status": "supported", "reason": "restart"}})
except ContractError as exc:
    print(type(exc).__name__ + ": " + str(exc))
else:
    raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "core"},
    )
    assert "ContractError:" in result.stdout
    assert "KeyError" not in result.stdout


@_params("capabilities", [None, [], "invalid"])
def test_malformed_capability_container_has_contract_error_in_fresh_process(
    tmp_path, capabilities
):
    fixture(tmp_path)
    with _raises(ContractError, match="invalid adapter capabilities"):
        validate_acceptance(tmp_path, RUN_REF, capabilities=capabilities)

    script = """
import sys
from kapisch_core.task_contract import ContractError, validate_outcome
try:
    validate_outcome(sys.argv[1], sys.argv[2], capabilities=None)
except ContractError as exc:
    print(type(exc).__name__ + ": " + str(exc))
else:
    raise SystemExit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "core"},
    )
    assert "ContractError: invalid adapter capabilities" in result.stdout


@_params("field", ["workorder_digest", "output_ref"])
@_params("reverse", [False, True])
def test_acceptance_rejects_duplicate_dispatch_claim_bindings(tmp_path, field, reverse):
    fixture(tmp_path)
    claim_path = tmp_path / f"{RUN_DIR}/dispatch-claim.json"
    claim = json.loads(claim_path.read_text())
    valid = claim[field]
    invalid = "0" * 64 if field == "workorder_digest" else "other-output.json"
    values = [valid, invalid]
    if reverse:
        values.reverse()
    entries = []
    for key, value in claim.items():
        if key == field:
            entries.extend(
                (json.dumps(key) + ":" + json.dumps(item)) for item in values
            )
        else:
            entries.append(json.dumps(key) + ":" + json.dumps(value))
    claim_path.write_text("{" + ",".join(entries) + "}")

    with _raises(ContractError, match="dispatch claim is missing or invalid"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


@_params(
    ("field", "value"),
    [("scope", "src/other/"), ("subject", "a different task")],
)
def test_workorder_cannot_exceed_decided_subject_or_scope(tmp_path, field, value):
    fixture(tmp_path)
    work_path = tmp_path / f"{RUN_DIR}/workorder.json"
    work = json.loads(work_path.read_text())
    work[field] = value
    work_path.write_text(json.dumps(work, sort_keys=True))
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(work_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))
    with _raises(ContractError, match="work order is not authorized"):
        validate_run(tmp_path, RUN_REF)


def test_directory_sync_failure_keeps_a_durable_claim(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    real_fsync = os.fsync
    calls = []

    def flaky_fsync(descriptor):
        calls.append(descriptor)
        if len(calls) == 2:
            raise OSError(22, "Invalid argument")
        return real_fsync(descriptor)

    with mock.patch("os.fsync", flaky_fsync):
        task_contract.claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )
    assert (tmp_path / f"{RUN_DIR}/dispatch-claim.json").is_file()


def test_failed_claim_write_leaves_no_claim_behind(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)

    def failing_fsync(descriptor):
        del descriptor
        raise OSError(5, "Input/output error")

    with mock.patch("os.fsync", failing_fsync):
        with _raises(ContractError, match="could not persist dispatch claim"):
            task_contract.claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities={"write": {"status": "supported", "reason": "available"}},
                canonical_implementer_available=False,
            )
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()

    claimed = task_contract.claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    assert claimed["dispatch_claim"]["status"] == "claimed"


def test_failed_claim_write_with_failing_cleanup_raises_contract_error(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    with mock.patch("os.fsync", side_effect=OSError(5, "Input/output error")):
        with mock.patch(
            "pathlib.Path.unlink", side_effect=PermissionError(13, "Permission denied")
        ):
            with _raises(ContractError, match="could not persist dispatch claim"):
                task_contract.claim_dispatch(
                    tmp_path,
                    RUN_REF,
                    capabilities={
                        "write": {"status": "supported", "reason": "available"}
                    },
                    canonical_implementer_available=False,
                )
