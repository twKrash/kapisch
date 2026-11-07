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
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event, current_thread
from unittest import mock

from kapisch_core import task_contract
from kapisch_core.task_contract import ContractError

_public_validate_run = task_contract.validate_run
_public_validate_dispatch = task_contract.validate_dispatch
_public_claim_dispatch = task_contract.claim_dispatch
_public_validate_acceptance = task_contract.validate_acceptance
_public_validate_outcome = task_contract.validate_outcome


def validate_run(state_root, *args, source_root=None, **kwargs):
    return _public_validate_run(
        state_root, *args, source_root=source_root or state_root, **kwargs
    )


def validate_acceptance(state_root, *args, source_root=None, **kwargs):
    return _public_validate_acceptance(
        state_root, *args, source_root=source_root or state_root, **kwargs
    )


def _validate_dispatch(state_root, *args, source_root=None, **kwargs):
    return _public_validate_dispatch(
        state_root, *args, source_root=source_root or state_root, **kwargs
    )


def _claim_dispatch(state_root, *args, source_root=None, **kwargs):
    return _public_claim_dispatch(
        state_root, *args, source_root=source_root or state_root, **kwargs
    )


def _validate_outcome(state_root, *args, source_root=None, **kwargs):
    return _public_validate_outcome(
        state_root, *args, source_root=source_root or state_root, **kwargs
    )


RUN_ID = "a0000000-0000-4000-8000-000000000001"
OTHER_RUN_ID = "b0000000-0000-4000-8000-000000000002"
RUN_DIR = f".kapisch/runs/{RUN_ID}"
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
    run["dispatch_state"] = "ready"
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


def fixture(
    tmp_path, *, decision_run=RUN_ID, source_kind="direct_operator", source_ref=None
):
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

    decision_ref = f".kapisch/runs/{decision_run}/decisions/d1.json"
    decision = {
        "decision_id": "d1",
        "question_id": "q1",
        "decision_type": "approval",
        "question": "Authorize this bounded task",
        "answer": "Approved",
        "subject": "implementation of t1",
        "scope": "src/",
        "source_kind": source_kind,
        "run_id": decision_run,
        "governing_inputs": inputs,
    }
    if source_ref is not None:
        decision["source_ref"] = source_ref
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
        "run_id": RUN_ID,
        "workorder_ref": work_ref,
        "workorder_digest": work_digest,
        "dispatch_state": "ready",
        "advisory_review": {"status": "not_run"},
        "attempt_allocation": {
            "attempt_id": "a1",
            "output_ref": f"{RUN_DIR}/attempts/a1-output.json",
        },
    }
    put(RUN_REF, run)
    _claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "claimed"
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


def _add_linked_worktree(primary, path):
    subprocess.run(
        ["git", "-C", str(primary), "worktree", "add", "--detach", str(path), "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return path


def test_ws2_rl_roots_same_directory_ok(tmp_path):
    fixture(tmp_path)
    records = task_contract.validate_run(tmp_path, RUN_REF, source_root=tmp_path)
    assert records["run"]["run_id"] == RUN_ID


def test_ws2_rl_state_in_primary_inputs_validated_against_feature_worktree(tmp_path):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF, source_root=tmp_path)
    worktree = _add_linked_worktree(tmp_path, tmp_path / "feature-worktree")
    changed = worktree / "docs/spec.md"
    changed.write_text("feature-specific approved requirements\n")
    subprocess.run(["git", "-C", str(worktree), "add", "docs/spec.md"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree), "commit", "-qm", "feature governing input"],
        check=True,
    )
    old_inputs = records["decision"]["governing_inputs"]
    new_inputs = [
        {
            "ref": "docs/spec.md",
            "digest": hashlib.sha256(changed.read_bytes()).hexdigest(),
        }
    ]
    applicability, work = records["applicability"], records["workorder"]
    applicability.update(
        original_governing_inputs=old_inputs, governing_inputs=new_inputs
    )
    work["governing_inputs"] = new_inputs
    _ws2_rebind(tmp_path, applicability=applicability, work=work)
    assert (
        validate_run(tmp_path, RUN_REF, source_root=worktree)["workorder"][
            "governing_inputs"
        ]
        == new_inputs
    )
    with _raises(
        ContractError, match="^current governing inputs require reassessment$"
    ):
        validate_run(tmp_path, RUN_REF, source_root=tmp_path)


def test_ws2_rl_run_validates_after_worktree_removed(tmp_path):
    fixture(tmp_path)
    worktree = _add_linked_worktree(tmp_path, tmp_path / "removed-worktree")
    run_path = tmp_path / RUN_REF
    state_before = run_path.read_bytes()
    subprocess.run(
        ["git", "-C", str(tmp_path), "worktree", "remove", "--force", str(worktree)],
        check=True,
    )
    assert (
        validate_run(tmp_path, RUN_REF, source_root=tmp_path)["run"]["run_id"] == RUN_ID
    )
    assert run_path.read_bytes() == state_before
    with _raises(ContractError, match="^invalid state_root/source_root mapping$"):
        validate_run(tmp_path, RUN_REF, source_root=worktree)


def test_ws2_rl_mapping_fails_closed(tmp_path):
    fixture(tmp_path)
    worktree = _add_linked_worktree(tmp_path, tmp_path / "linked-worktree")
    other_repo = tmp_path.parent / f"{tmp_path.name}-other-repo"
    other_repo.mkdir()
    subprocess.run(["git", "init", "-q", str(other_repo)], check=True)
    plain = tmp_path.parent / f"{tmp_path.name}-plain"
    plain.mkdir()
    bare = tmp_path.parent / f"{tmp_path.name}-bare.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    missing = tmp_path.parent / f"{tmp_path.name}-missing"
    cases = (
        (missing, tmp_path),
        (tmp_path, missing),
        (tmp_path, tmp_path / "docs"),
        (tmp_path, plain),
        (tmp_path, other_repo),
        (worktree, tmp_path),
        (bare, bare),
        (tmp_path / "docs/spec.md", tmp_path),
    )
    with (
        mock.patch.dict(os.environ, {"GIT_DIR": str(tmp_path / ".git")}),
        _raises(ContractError, match="^invalid state_root/source_root mapping$"),
    ):
        task_contract.validate_run(tmp_path, RUN_REF, source_root=plain)
    for state_root, source_root in cases:
        with _raises(ContractError, match="^invalid state_root/source_root mapping$"):
            task_contract.validate_run(state_root, RUN_REF, source_root=source_root)
        with _raises(ContractError, match="^invalid state_root/source_root mapping$"):
            task_contract.claim_dispatch(
                state_root,
                RUN_REF,
                source_root=source_root,
                capabilities={"write": {"status": "supported", "reason": "available"}},
                canonical_implementer_available=False,
            )


def test_ws2_rl_state_files_never_written_under_source_root(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    worktree = _add_linked_worktree(tmp_path, tmp_path / "claim-worktree")
    claim_ref = f"{RUN_DIR}/dispatch-claim.json"
    assert not (worktree / claim_ref).exists()
    claim = task_contract.claim_dispatch(
        tmp_path,
        RUN_REF,
        source_root=worktree,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    assert claim["dispatch_claim"]["run_id"] == RUN_ID
    assert (tmp_path / claim_ref).is_file()
    assert not (worktree / claim_ref).exists()
    assert (tmp_path / ".kapisch").is_dir()
    assert not (worktree / ".kapisch").exists()


def test_ws2_rl_source_root_keyword_required(tmp_path):
    fixture(tmp_path)
    with _raises(TypeError):
        task_contract.validate_run(tmp_path, RUN_REF)


def _rewrite_decision_answer(tmp_path, answer, *, valid_utf8, ensure_ascii=True):
    def write_record(ref, record):
        raw = json.dumps(record, ensure_ascii=ensure_ascii, sort_keys=True).encode(
            "utf-8"
        )
        (tmp_path / ref).write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    decision_ref = f"{RUN_DIR}/decisions/d1.json"
    decision_path = tmp_path / decision_ref
    decision = json.loads(decision_path.read_text())
    decision["answer"] = answer
    decision_digest = write_record(decision_ref, decision)

    applicability_ref = f"{RUN_DIR}/applicability.json"
    applicability_path = tmp_path / applicability_ref
    applicability = json.loads(applicability_path.read_text())
    applicability["decision_digest"] = decision_digest
    applicability["answer_digest"] = (
        hashlib.sha256(answer.encode("utf-8")).hexdigest() if valid_utf8 else "0" * 64
    )
    applicability_digest = write_record(applicability_ref, applicability)

    workorder_ref = f"{RUN_DIR}/workorder.json"
    workorder_path = tmp_path / workorder_ref
    workorder = json.loads(workorder_path.read_text())
    workorder["decision_digest"] = decision_digest
    workorder["applicability_digest"] = applicability_digest
    workorder_digest = write_record(workorder_ref, workorder)

    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = workorder_digest
    write_record(RUN_REF, run)


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
        "advisory_review": {"status": "not_run"},
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
        match=re.escape(f"unreadable artifact: {RUN_DIR}/attempts/a1-output.json"),
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


@_params("answer", ["\ud800", "\udc00", "prefix\ud800suffix"])
def test_non_utf8_decision_answer_is_a_contract_error(tmp_path, answer):
    fixture(tmp_path)
    _rewrite_decision_answer(tmp_path, answer, valid_utf8=False)
    capabilities = {"write": {"status": "supported", "reason": "available"}}
    validators = (
        lambda: validate_run(tmp_path, RUN_REF),
        lambda: _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=capabilities,
            canonical_implementer_available=False,
        ),
        lambda: validate_acceptance(tmp_path, RUN_REF, capabilities=capabilities),
        lambda: _validate_outcome(tmp_path, RUN_REF, capabilities=capabilities),
    )
    for validate in validators:
        with _raises(ContractError, match="decision answer is not valid UTF-8"):
            validate()

    _reset_to_unclaimed(tmp_path)
    run_path = tmp_path / RUN_REF
    run_before = run_path.read_bytes()
    with _raises(ContractError, match="decision answer is not valid UTF-8"):
        _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=capabilities,
            canonical_implementer_available=False,
        )
    assert run_path.read_bytes() == run_before
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()
    assert not (tmp_path / f"{RUN_DIR}/attempts/a1.json").exists()
    assert not (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").exists()

    script = """
import sys
from kapisch_core.task_contract import ContractError, validate_run
try:
    validate_run(sys.argv[1], sys.argv[2], source_root=sys.argv[1])
except ContractError as exc:
    print(type(exc).__name__ + ": " + str(exc))
except Exception as exc:
    print(type(exc).__name__)
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
    assert result.stdout.strip() == (
        "ContractError: decision answer is not valid UTF-8"
    )


@_params(
    ("answer", "ensure_ascii"),
    [
        ("café 東京", True),
        ("😀", True),
        ("Café 東京 😀", False),
        ("  Café😀  ", True),
    ],
)
def test_valid_unicode_decision_answer_uses_exact_utf8_digest(
    tmp_path, answer, ensure_ascii
):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    _rewrite_decision_answer(
        tmp_path, answer, valid_utf8=True, ensure_ascii=ensure_ascii
    )

    records = validate_run(tmp_path, RUN_REF)
    expected_digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    assert records["decision"]["answer"] == answer
    assert records["applicability"]["answer_digest"] == expected_digest
    claim = _claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    assert claim["decision"]["answer"] == answer


@_params("reason", [None, "", " \t"])
def test_applicability_requires_nonempty_text_reason(tmp_path, reason):
    fixture(tmp_path)
    applicability_path = tmp_path / f"{RUN_DIR}/applicability.json"
    applicability = json.loads(applicability_path.read_text())
    applicability["reason"] = reason
    applicability_path.write_text(json.dumps(applicability, sort_keys=True))

    workorder_path = tmp_path / f"{RUN_DIR}/workorder.json"
    workorder = json.loads(workorder_path.read_text())
    workorder["applicability_digest"] = hashlib.sha256(
        applicability_path.read_bytes()
    ).hexdigest()
    workorder_path.write_text(json.dumps(workorder, sort_keys=True))

    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["workorder_digest"] = hashlib.sha256(workorder_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))

    with _raises(ContractError, match="decision applicability"):
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
        "run_id": RUN_ID,
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
    duplicate = tmp_path / f".kapisch/runs/{OTHER_RUN_ID}/decisions/d1.json"
    duplicate.parent.mkdir(parents=True)
    decision = json.loads((tmp_path / f"{RUN_DIR}/decisions/d1.json").read_text())
    decision["run_id"] = OTHER_RUN_ID
    decision["scope"] = "conflicting/"
    duplicate.write_text(json.dumps(decision, sort_keys=True))
    assert validate_run(tmp_path, RUN_REF)["decision"]["decision_id"] == "d1"


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
    run["dispatch_state"] = "ready"
    run_path.write_text(json.dumps(run, sort_keys=True))
    (tmp_path / f"{RUN_DIR}/attempts/a1.json").unlink()
    (tmp_path / f"{RUN_DIR}/aggregation.json").unlink()
    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").unlink()
    (tmp_path / f"{RUN_DIR}/dispatch-claim.json").unlink()
    with _raises(ContractError, match="required capability"):
        _validate_dispatch(
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
    run["dispatch_state"] = "ready"
    run_path.write_text(json.dumps(run, sort_keys=True))
    (tmp_path / RUN_DIR / "dispatch-claim.json").unlink()
    with _raises(ContractError, match="canonical implementer"):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=True,
        )
    work = _validate_dispatch(
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
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    del run["advisory_review"]
    run_path.write_text(json.dumps(run, sort_keys=True))
    expected = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={
            "write": {"status": "supported", "reason": "test adapter write support"}
        },
    )
    assert expected["advisory_review"] == {"status": "not_run"}
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
        "print(json.dumps(validate_outcome(sys.argv[1], sys.argv[2], source_root=sys.argv[1], "
        "capabilities={'write': {'status': 'supported', 'reason': 'restart probe'}}), sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == expected


def test_performed_advisory_review_is_persisted_and_reconstructed(tmp_path):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    attempt = json.loads((tmp_path / run["attempt_ref"]).read_text())
    run["advisory_review"] = {
        "status": "performed",
        "workorder_ref": run["workorder_ref"],
        "workorder_digest": run["workorder_digest"],
        "attempt_ref": run["attempt_ref"],
        "attempt_id": attempt["attempt_id"],
        "attempt_digest": run["attempt_digest"],
    }
    run_path.write_text(json.dumps(run, sort_keys=True))

    expected = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
    )
    assert expected["advisory_review"] == run["advisory_review"]
    outcome_ref = f"{RUN_DIR}/outcome.json"
    outcome_path = tmp_path / outcome_ref
    outcome_path.write_text(json.dumps(expected, sort_keys=True))
    run["outcome_ref"] = outcome_ref
    run["outcome_digest"] = hashlib.sha256(outcome_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))

    script = (
        "import json, sys; from kapisch_core.task_contract import validate_outcome; "
        "print(json.dumps(validate_outcome(sys.argv[1], sys.argv[2], source_root=sys.argv[1], "
        "capabilities={'write': {'status': 'supported', 'reason': 'restart'}}), sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == expected


@_params(
    "advisory_review",
    [
        None,
        [],
        {"status": "unknown"},
        {"status": "not_run", "attempt_id": "a1"},
        {"status": "performed"},
        {
            "status": "performed",
            "workorder_ref": "other/workorder.json",
            "workorder_digest": "0" * 64,
            "attempt_ref": "other/attempt.json",
            "attempt_id": "other",
            "attempt_digest": "0" * 64,
        },
    ],
)
def test_advisory_review_metadata_must_be_valid_and_bound(tmp_path, advisory_review):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["advisory_review"] = advisory_review
    run_path.write_text(json.dumps(run, sort_keys=True))

    with _raises(ContractError, match="advisory review"):
        validate_acceptance(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
        )


def test_persisted_outcome_rejects_rebound_advisory_review(tmp_path):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    attempt = json.loads((tmp_path / run["attempt_ref"]).read_text())
    run["advisory_review"] = {
        "status": "performed",
        "workorder_ref": run["workorder_ref"],
        "workorder_digest": run["workorder_digest"],
        "attempt_ref": run["attempt_ref"],
        "attempt_id": attempt["attempt_id"],
        "attempt_digest": run["attempt_digest"],
    }
    run_path.write_text(json.dumps(run, sort_keys=True))
    outcome = validate_acceptance(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
    )
    outcome["advisory_review"]["attempt_id"] = "rebound"
    outcome_ref = f"{RUN_DIR}/outcome.json"
    outcome_path = tmp_path / outcome_ref
    outcome_path.write_text(json.dumps(outcome, sort_keys=True))
    run["outcome_ref"] = outcome_ref
    run["outcome_digest"] = hashlib.sha256(outcome_path.read_bytes()).hexdigest()
    run_path.write_text(json.dumps(run, sort_keys=True))

    with _raises(ContractError, match="persisted Outcome does not match"):
        _validate_outcome(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "fresh process"}},
        )


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
        _validate_dispatch(
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
    run["dispatch_state"] = "ready"
    run_path.write_text(json.dumps(run, sort_keys=True))
    (tmp_path / RUN_DIR / "dispatch-claim.json").unlink()
    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").unlink()
    with _raises(ContractError, match="attempt allocation already exists"):
        _validate_dispatch(
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
        _validate_dispatch(
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
        _validate_outcome(
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
    run["dispatch_state"] = "ready"
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
        _claim_dispatch(
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
    run["dispatch_state"] = "ready"
    run_path.write_text(json.dumps(run, sort_keys=True))
    for ref in (
        "attempts/a1.json",
        "attempts/a1-output.json",
        "aggregation.json",
        "outcome.json",
        "dispatch-claim.json",
    ):
        (tmp_path / RUN_DIR / ref).unlink(missing_ok=True)

    claim = _claim_dispatch(
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
    validate_dispatch(sys.argv[1], sys.argv[2], source_root=sys.argv[1], capabilities={"write": {"status": "supported", "reason": "restart"}}, canonical_implementer_available=False)
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
        _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )


def test_lost_dispatch_claim_does_not_reenable_allocation_after_restart(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    _claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    assert run["dispatch_state"] == "claimed"
    (tmp_path / RUN_DIR / "dispatch-claim.json").unlink()
    assert not (tmp_path / f"{RUN_DIR}/attempts/a1.json").exists()
    assert not (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").exists()

    script = """
import sys
from kapisch_core.task_contract import ContractError, validate_dispatch
try:
    validate_dispatch(sys.argv[1], sys.argv[2], source_root=sys.argv[1], capabilities={"write":{"status":"supported","reason":"restart"}}, canonical_implementer_available=False)
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
    assert "consumed" in result.stdout


def test_dispatch_state_write_failure_keeps_claim_and_blocks_restart(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    with mock.patch(
        "kapisch_core._task_artifacts.os.replace",
        side_effect=OSError("injected Run replacement failure"),
    ):
        with _raises(ContractError, match="could not persist dispatch boundary"):
            _claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities={"write": {"status": "supported", "reason": "available"}},
                canonical_implementer_available=False,
            )

    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "ready"
    assert (tmp_path / RUN_DIR / "dispatch-claim.json").is_file()
    with _raises(ContractError, match="dispatch claim already exists"):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "restart"}},
            canonical_implementer_available=False,
        )


@_params("dispatch_state", [None, True, False, 0, [], {}, "unknown"])
def test_malformed_dispatch_state_fails_closed(tmp_path, dispatch_state):
    fixture(tmp_path)
    run_path = tmp_path / RUN_REF
    run = json.loads(run_path.read_text())
    run["dispatch_state"] = dispatch_state
    run_path.write_text(json.dumps(run, sort_keys=True))

    with _raises(ContractError, match="invalid persisted dispatch state"):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "restart"}},
            canonical_implementer_available=False,
        )


def test_missing_dispatch_state_fails_closed(tmp_path):
    fixture(tmp_path)
    run_path = _reset_to_unclaimed(tmp_path)
    run = json.loads(run_path.read_text())
    del run["dispatch_state"]
    run_path.write_text(json.dumps(run, sort_keys=True))

    with _raises(ContractError, match="invalid persisted dispatch state"):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "restart"}},
            canonical_implementer_available=False,
        )


def test_claim_creation_failure_does_not_consume_allocation(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    with mock.patch(
        "kapisch_core.task_contract._create_exclusive",
        side_effect=ContractError("injected claim write failure"),
    ):
        with _raises(ContractError, match="injected claim write failure"):
            _claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities={"write": {"status": "supported", "reason": "available"}},
                canonical_implementer_available=False,
            )

    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "ready"
    assert not (tmp_path / RUN_DIR / "dispatch-claim.json").exists()
    claim = _claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "available"}},
        canonical_implementer_available=False,
    )
    assert claim["dispatch_claim"]["status"] == "claimed"


def test_losing_claimant_cannot_overwrite_published_outcome(tmp_path):
    fixture(tmp_path)
    artifact_refs = (
        "attempts/a1-output.json",
        "attempts/a1.json",
        "aggregation.json",
    )
    artifacts = {ref: (tmp_path / RUN_DIR / ref).read_bytes() for ref in artifact_refs}
    run_path = _reset_to_unclaimed(tmp_path)
    preflight_complete = Event()
    release_loser = Event()
    original_validate_dispatch = task_contract.validate_dispatch

    def delayed_preflight(*args, **kwargs):
        records = original_validate_dispatch(*args, **kwargs)
        if current_thread().name.startswith("stale-claim"):
            preflight_complete.set()
            if not release_loser.wait(timeout=5):
                raise AssertionError("timed out waiting to release stale claimant")
        return records

    with mock.patch.object(task_contract, "validate_dispatch", delayed_preflight):
        with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="stale-claim"
        ) as pool:
            loser = pool.submit(
                task_contract.claim_dispatch,
                tmp_path,
                RUN_REF,
                source_root=tmp_path,
                capabilities={"write": {"status": "supported", "reason": "available"}},
                canonical_implementer_available=False,
            )
            try:
                assert preflight_complete.wait(timeout=5)
                _claim_dispatch(
                    tmp_path,
                    RUN_REF,
                    capabilities={
                        "write": {"status": "supported", "reason": "available"}
                    },
                    canonical_implementer_available=False,
                )
                run = json.loads(run_path.read_text())
                for ref, content in artifacts.items():
                    (tmp_path / RUN_DIR / ref).write_bytes(content)
                attempt_ref = f"{RUN_DIR}/attempts/a1.json"
                aggregation_ref = f"{RUN_DIR}/aggregation.json"
                run.update(
                    attempt_ref=attempt_ref,
                    attempt_digest=hashlib.sha256(
                        (tmp_path / attempt_ref).read_bytes()
                    ).hexdigest(),
                    aggregation_ref=aggregation_ref,
                    aggregation_digest=hashlib.sha256(
                        (tmp_path / aggregation_ref).read_bytes()
                    ).hexdigest(),
                )
                run_path.write_text(json.dumps(run, sort_keys=True))
                outcome = validate_acceptance(
                    tmp_path,
                    RUN_REF,
                    capabilities={
                        "write": {"status": "supported", "reason": "available"}
                    },
                )
                outcome_ref = f"{RUN_DIR}/outcome.json"
                outcome_path = tmp_path / outcome_ref
                outcome_path.write_text(json.dumps(outcome, sort_keys=True))
                run["outcome_ref"] = outcome_ref
                run["outcome_digest"] = hashlib.sha256(
                    outcome_path.read_bytes()
                ).hexdigest()
                run_path.write_text(json.dumps(run, sort_keys=True))
                published_run = run_path.read_bytes()
            finally:
                release_loser.set()

            with _raises(ContractError, match="dispatch claim already exists"):
                loser.result(timeout=5)

    assert run_path.read_bytes() == published_run
    script = (
        "import json, sys; from kapisch_core.task_contract import validate_outcome; "
        "print(json.dumps(validate_outcome(sys.argv[1], sys.argv[2], source_root=sys.argv[1], "
        "capabilities={'write': {'status': 'supported', 'reason': 'restart'}}), sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == outcome


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
    run["dispatch_state"] = "ready"
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
            _claim_dispatch(
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


def test_artifact_loader_rejects_nonstandard_or_excessive_json(tmp_path):
    run_path = tmp_path / RUN_REF
    run_path.parent.mkdir(parents=True)
    for payload in (
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":1e999}',
        b'{"x":' + b"9" * 5000 + b"}",
    ):
        run_path.write_bytes(payload)
        with _raises(ContractError):
            validate_run(tmp_path, RUN_REF)


def test_json_loader_does_not_impose_a_nesting_limit(tmp_path):
    artifact = tmp_path / "artifact.json"
    payload = b'{"x":' + b"[" * 300 + b"0" + b"]" * 300 + b"}"
    artifact.write_bytes(payload)

    loaded = task_contract._load(tmp_path, "artifact.json", require_digest=False)
    value = loaded["x"]
    for _ in range(300):
        value = value[0]
    assert value == 0


def test_json_loader_normalizes_parser_recursion_errors(tmp_path):
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"{}")
    with mock.patch(
        "kapisch_core._task_artifacts.json.loads",
        side_effect=RecursionError("parser depth limit"),
    ):
        with _raises(ContractError):
            task_contract._load(tmp_path, "artifact.json", require_digest=False)


def test_path_resolution_failures_are_contract_errors(tmp_path):
    artifact = tmp_path / "loop.json"
    artifact.symlink_to(artifact)
    with _raises(ContractError):
        task_contract._load(tmp_path, "loop.json", require_digest=False)

    root_loop = tmp_path / "root-loop"
    root_loop.symlink_to(root_loop, target_is_directory=True)
    with _raises(ContractError):
        validate_run(root_loop, RUN_REF)

    writer_loop = tmp_path / "writer-loop"
    writer_loop.symlink_to(writer_loop, target_is_directory=True)
    with _raises(ContractError):
        task_contract._create_exclusive(tmp_path, "writer-loop/claim.json", {})
    with _raises(ContractError):
        task_contract._replace_json_atomically(tmp_path, "writer-loop/run.json", {})


def test_decision_identity_scan_resolution_failures_are_contract_errors(tmp_path):
    fixture(tmp_path)
    duplicate = tmp_path / f".kapisch/runs/{OTHER_RUN_ID}/decisions/d1.json"
    duplicate.parent.mkdir(parents=True)
    duplicate.symlink_to(duplicate)
    assert validate_run(tmp_path, RUN_REF)["decision"]["decision_id"] == "d1"


def test_governing_input_resolution_failures_are_contract_errors(tmp_path):
    fixture(tmp_path)
    source = tmp_path / "docs/spec.md"
    source.unlink()
    source.symlink_to(source)

    with _raises(ContractError):
        validate_run(tmp_path, RUN_REF)


def _assert_dispatch_alias_rejected(tmp_path, foreign_target):
    capabilities = {"write": {"status": "supported", "reason": "available"}}
    with _raises(ContractError):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=capabilities,
            canonical_implementer_available=False,
        )
    with _raises(ContractError):
        _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=capabilities,
            canonical_implementer_available=False,
        )

    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "ready"
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()
    assert not foreign_target.exists()


def test_dispatch_rejects_dangling_output_alias(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    foreign_target = tmp_path / ".kapisch/runs/r2/attempts/a2-output.json"
    foreign_target.parent.mkdir(parents=True)
    (tmp_path / f"{RUN_DIR}/attempts/a1-output.json").symlink_to(foreign_target)

    _assert_dispatch_alias_rejected(tmp_path, foreign_target)


def test_dispatch_rejects_dangling_attempt_alias(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    foreign_target = tmp_path / ".kapisch/runs/r2/attempts/a2.json"
    foreign_target.parent.mkdir(parents=True)
    (tmp_path / f"{RUN_DIR}/attempts/a1.json").symlink_to(foreign_target)

    _assert_dispatch_alias_rejected(tmp_path, foreign_target)


def test_dispatch_rejects_parent_directory_alias(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    attempts = tmp_path / f"{RUN_DIR}/attempts"
    attempts.rmdir()
    foreign_attempts = tmp_path / ".kapisch/runs/r2/attempts"
    foreign_attempts.mkdir(parents=True)
    foreign_target = foreign_attempts / "a1-output.json"
    attempts.symlink_to(foreign_attempts, target_is_directory=True)

    _assert_dispatch_alias_rejected(tmp_path, foreign_target)


def test_dispatch_rejects_non_directory_attempts_parent(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    attempts = tmp_path / f"{RUN_DIR}/attempts"
    attempts.rmdir()
    attempts.write_text("not a directory")
    capabilities = {"write": {"status": "supported", "reason": "available"}}

    with _raises(ContractError):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=capabilities,
            canonical_implementer_available=False,
        )
    with _raises(ContractError):
        _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=capabilities,
            canonical_implementer_available=False,
        )

    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "ready"
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()
    assert attempts.is_file()


def test_dispatch_allows_missing_attempts_parent(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    attempts = tmp_path / f"{RUN_DIR}/attempts"
    attempts.rmdir()
    capabilities = {"write": {"status": "supported", "reason": "available"}}

    validated = _validate_dispatch(
        tmp_path,
        RUN_REF,
        capabilities=capabilities,
        canonical_implementer_available=False,
    )
    assert validated["attempt_allocation"]["attempt_id"] == "a1"

    claimed = _claim_dispatch(
        tmp_path,
        RUN_REF,
        capabilities=capabilities,
        canonical_implementer_available=False,
    )
    assert claimed["run"]["dispatch_state"] == "claimed"
    assert not attempts.exists()


def test_dispatch_rejects_uninspectable_allocation_parent(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    attempts = tmp_path / f"{RUN_DIR}/attempts"
    original_stat = Path.stat

    def denied_stat(path, *args, **kwargs):
        if path == attempts:
            raise PermissionError("allocation parent is unreadable")
        return original_stat(path, *args, **kwargs)

    capabilities = {"write": {"status": "supported", "reason": "available"}}
    with mock.patch.object(Path, "stat", denied_stat):
        with _raises(ContractError):
            _validate_dispatch(
                tmp_path,
                RUN_REF,
                capabilities=capabilities,
                canonical_implementer_available=False,
            )
        with _raises(ContractError):
            _claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities=capabilities,
                canonical_implementer_available=False,
            )

    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "ready"
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()


def test_dispatch_rejects_uninspectable_existing_output(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    output = tmp_path / f"{RUN_DIR}/attempts/a1-output.json"
    output.write_text("existing output")
    original_exists = Path.exists
    original_stat = Path.stat

    def denied_stat(path, *args, **kwargs):
        if path == output:
            raise PermissionError("cannot inspect allocated output")
        return original_stat(path, *args, **kwargs)

    def hidden_exists(path, *args, **kwargs):
        if path == output:
            return False
        return original_exists(path, *args, **kwargs)

    capabilities = {"write": {"status": "supported", "reason": "available"}}
    with (
        mock.patch.object(Path, "stat", denied_stat),
        mock.patch.object(Path, "exists", hidden_exists),
    ):
        with _raises(ContractError):
            _validate_dispatch(
                tmp_path,
                RUN_REF,
                capabilities=capabilities,
                canonical_implementer_available=False,
            )
        with _raises(ContractError):
            _claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities=capabilities,
                canonical_implementer_available=False,
            )

    run = json.loads((tmp_path / RUN_REF).read_text())
    assert run["dispatch_state"] == "ready"
    assert not (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()
    assert output.read_text() == "existing output"


def test_claim_keeps_blocking_claim_on_run_stat_error(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    run_path = tmp_path / RUN_REF
    original_run = run_path.read_bytes()
    original_lstat = Path.lstat

    def denied_lstat(path, *args, **kwargs):
        if path == run_path:
            raise PermissionError("cannot inspect Run before replacement")
        return original_lstat(path, *args, **kwargs)

    capabilities = {"write": {"status": "supported", "reason": "available"}}
    with mock.patch.object(Path, "lstat", denied_lstat):
        with _raises(ContractError):
            _claim_dispatch(
                tmp_path,
                RUN_REF,
                capabilities=capabilities,
                canonical_implementer_available=False,
            )

    assert run_path.read_bytes() == original_run
    assert json.loads(original_run)["dispatch_state"] == "ready"
    assert (tmp_path / f"{RUN_DIR}/dispatch-claim.json").exists()


def test_artifact_serialization_rejects_nonfinite_values(tmp_path):
    invalid_record = {"value": float("nan")}
    with _raises(ContractError):
        task_contract._create_exclusive(tmp_path, "claim.json", invalid_record)
    assert not (tmp_path / "claim.json").exists()

    target = tmp_path / "run.json"
    target.write_text("{}")
    with _raises(ContractError):
        task_contract._replace_json_atomically(tmp_path, "run.json", invalid_record)
    assert target.read_text() == "{}"


@_params(
    ("field", "first", "second"),
    [
        ("result", "not_applicable", "applicable"),
        ("decision_id", "other", "d1"),
        ("scope", "src/", "src"),
        ("decision_ref", "other.json", f"{RUN_DIR}/decisions/d1.json"),
        ("workorder_digest", "0" * 64, "1" * 64),
        ("output_ref", "other.json", f"{RUN_DIR}/attempts/a1-output.json"),
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
        _claim_dispatch(
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
    validate_outcome(sys.argv[1], sys.argv[2], source_root=sys.argv[1], capabilities={"write": {"status": "supported", "reason": "restart"}})
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
    validate_outcome(sys.argv[1], sys.argv[2], source_root=sys.argv[1], capabilities={"write": {"status": "supported", "reason": "restart"}})
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
    validate_outcome(sys.argv[1], sys.argv[2], source_root=sys.argv[1], capabilities=None)
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


def test_dispatch_boundary_does_not_require_filesystem_sync(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    with mock.patch("os.fsync", side_effect=OSError(22, "Invalid argument")) as fsync:
        claim = _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "available"}},
            canonical_implementer_available=False,
        )
    assert claim["dispatch_claim"]["status"] == "claimed"
    assert (tmp_path / f"{RUN_DIR}/dispatch-claim.json").is_file()
    assert not fsync.called


def _ws2_put(root, ref, record):
    raw = json.dumps(record, sort_keys=True).encode()
    path = root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _ws2_rebind(root, *, decision=None, applicability=None, work=None):
    run = json.loads((root / RUN_REF).read_text())
    if work is None:
        work = json.loads((root / run["workorder_ref"]).read_text())
    if decision is not None:
        work["decision_digest"] = _ws2_put(root, work["decision_ref"], decision)
    if applicability is None:
        applicability = json.loads((root / work["applicability_ref"]).read_text())
    applicability.update(
        decision_ref=work["decision_ref"],
        decision_id=work["decision_id"],
        decision_digest=work["decision_digest"],
    )
    work["applicability_digest"] = _ws2_put(
        root, work["applicability_ref"], applicability
    )
    run["workorder_digest"] = _ws2_put(root, run["workorder_ref"], work)
    _ws2_put(root, RUN_REF, run)


def _ws2_reassess(root):
    records = validate_run(root, RUN_REF)
    original = records["decision"]["governing_inputs"]
    (root / "docs/spec.md").write_text("approved requirements, clarified\n")
    subprocess.run(["git", "-C", str(root), "add", "docs/spec.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "clarify governing input"],
        check=True,
    )
    assessed = [
        {
            "ref": "docs/spec.md",
            "digest": hashlib.sha256((root / "docs/spec.md").read_bytes()).hexdigest(),
        }
    ]
    app, work = records["applicability"], records["workorder"]
    app.update(original_governing_inputs=original, governing_inputs=assessed)
    work["governing_inputs"] = assessed
    _ws2_rebind(root, applicability=app, work=work)
    return original, assessed


def test_ws2_reassessment_preserves_immutable_original(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    path = tmp_path / f"{RUN_DIR}/decisions/d1.json"
    before = path.read_bytes()
    original, assessed = _ws2_reassess(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    assert original != assessed
    assert records["decision"]["governing_inputs"] == original
    assert records["applicability"]["original_governing_inputs"] == original
    assert records["applicability"]["governing_inputs"] == assessed
    assert records["workorder"]["governing_inputs"] == assessed
    assert (
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities={"write": {"status": "supported", "reason": "reassessment"}},
            canonical_implementer_available=False,
        )["decision"]["governing_inputs"]
        == original
    )
    assert path.read_bytes() == before


@_params("variant", ["absent", "mismatch", "assessed_mismatch"])
def test_ws2_reassessment_binding_failures(tmp_path, variant):
    fixture(tmp_path)
    _ws2_reassess(tmp_path)
    work = json.loads((tmp_path / RUN_DIR / "workorder.json").read_text())
    app = json.loads((tmp_path / work["applicability_ref"]).read_text())
    if variant == "absent":
        app.pop("original_governing_inputs")
        message = "governing inputs require reassessment"
    elif variant == "mismatch":
        app["original_governing_inputs"] = app["governing_inputs"]
        message = "original governing inputs mismatch"
    else:
        app["governing_inputs"] = app["original_governing_inputs"]
        message = "decision applicability is missing, stale, or not applicable"
    _ws2_rebind(tmp_path, applicability=app, work=work)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        validate_run(tmp_path, RUN_REF)


@_params(
    ("snapshot", "message"),
    [
        (None, "invalid historical governing inputs"),
        ([], "work order requires governing Git inputs"),
        ({}, "invalid historical governing inputs"),
        ([None], "malformed governing Git input"),
        ([{"ref": "docs/spec.md"}], "malformed governing Git input"),
        ([{"ref": "../spec.md", "digest": "0" * 64}], "malformed governing Git input"),
        ([{"ref": "docs/spec.md", "digest": None}], "malformed governing Git input"),
        (
            [{"ref": "docs/spec.md", "digest": "A" * 64}],
            "malformed governing Git input",
        ),
        (
            [{"ref": "docs/spec.md", "digest": "0" * 64, "extra": 1}],
            "malformed governing Git input",
        ),
        (
            [{"ref": "docs/spec.md", "digest": "0" * 64}] * 2,
            "duplicate governing Git input",
        ),
        ("__omit__", "invalid historical governing inputs"),
    ],
)
def test_ws2_equal_malformed_historical_snapshots_rejected(tmp_path, snapshot, message):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    decision, app = records["decision"], records["applicability"]
    app["original_governing_inputs"] = snapshot
    if snapshot == "__omit__":
        decision.pop("governing_inputs")
    else:
        decision["governing_inputs"] = snapshot
    _ws2_rebind(tmp_path, decision=decision, applicability=app)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        validate_run(tmp_path, RUN_REF)


@_params("snapshot", [None, {}, [None]])
def test_ws2_present_invalid_original_is_not_absent(tmp_path, snapshot):
    fixture(tmp_path)
    app = validate_run(tmp_path, RUN_REF)["applicability"]
    app["original_governing_inputs"] = snapshot
    _ws2_rebind(tmp_path, applicability=app)
    message = (
        "malformed governing Git input"
        if snapshot == [None]
        else "invalid historical governing inputs"
    )
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        validate_run(tmp_path, RUN_REF)


@_params("field", ["subject", "scope"])
def test_ws2_reassessment_cannot_change_authority(tmp_path, field):
    fixture(tmp_path)
    _ws2_reassess(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    app, work = records["applicability"], records["workorder"]
    app[field] = work[field] = "wider authority"
    _ws2_rebind(tmp_path, applicability=app, work=work)
    with _raises(ContractError, match="^work order is not authorized$"):
        validate_run(tmp_path, RUN_REF)


@_params("original_present", [False, True])
def test_ws2_empty_original_snapshot_presence_semantics(tmp_path, original_present):
    from kapisch_core._task_authority import _validate_governing_binding

    fixture(tmp_path)
    work = validate_run(tmp_path, RUN_REF)["workorder"]
    decision = {"governing_inputs": []}
    app = {"original_governing_inputs": []} if original_present else {}
    if original_present:
        _validate_governing_binding(tmp_path, work, decision, app)
    else:
        with _raises(ContractError, match="^governing inputs require reassessment$"):
            _validate_governing_binding(tmp_path, work, decision, app)


def test_ws2_present_empty_original_mismatches_nonempty_snapshot(tmp_path):
    fixture(tmp_path)
    app = validate_run(tmp_path, RUN_REF)["applicability"]
    app["original_governing_inputs"] = []
    _ws2_rebind(tmp_path, applicability=app)
    with _raises(ContractError, match="^original governing inputs mismatch$"):
        validate_run(tmp_path, RUN_REF)


def test_ws2_drift_without_reassessment_is_rejected(tmp_path):
    fixture(tmp_path)
    (tmp_path / "docs/spec.md").write_text("changed governing input\n")
    with _raises(
        ContractError,
        match="^current governing inputs require reassessment$",
    ):
        validate_run(tmp_path, RUN_REF)


def test_ws2_85_compatibility_without_original_snapshot(tmp_path):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    assert "original_governing_inputs" not in records["applicability"]
    assert (
        records["workorder"]["governing_inputs"]
        == records["decision"]["governing_inputs"]
    )


def test_ws2_rl_run_id_must_be_uuid4(tmp_path):
    from kapisch_core.task_contract import _run_directory

    fixture(tmp_path)
    valid = {"run_id": RUN_ID}
    assert _run_directory(valid, RUN_REF) == RUN_DIR
    invalid_ids = (
        RUN_ID.upper(),
        "00000000-0000-1000-8000-000000000001",
        "00000000-0000-4000-7000-000000000001",
        "short",
    )
    for invalid in invalid_ids:
        with _raises(ContractError, match="^invalid Run identity$"):
            _run_directory({"run_id": invalid}, f".kapisch/runs/{invalid}/run.json")
    with _raises(ContractError, match="^invalid Run identity$"):
        _run_directory({}, RUN_REF)
    for malformed_ref in (
        ".kapisch/runs/not-a-uuid/run.json",
        f".kapisch/runs/{RUN_ID.upper()}/run.json",
    ):
        with _raises(ContractError, match="^invalid Run identity$"):
            _run_directory(valid, malformed_ref)
    with _raises(ContractError, match="^Run identity and portable reference mismatch$"):
        _run_directory(valid, f".kapisch/runs/{OTHER_RUN_ID}/run.json")


def test_ws2_rl_decision_run_id_required_and_must_match(tmp_path):
    fixture(tmp_path)
    record = validate_run(tmp_path, RUN_REF)["decision"]
    for value in (None, OTHER_RUN_ID, 7):
        changed = dict(record)
        if value is None:
            changed.pop("run_id")
        else:
            changed["run_id"] = value
        _ws2_rebind(tmp_path, decision=changed)
        with _raises(ContractError, match="^decision run mismatch$"):
            validate_run(tmp_path, RUN_REF)
        _ws2_rebind(tmp_path, decision=record)


# The fields the canonical skill tells the coordinator to write for a direct-prompt approval.
DIRECT_PROMPT_DECISION_FIELDS = (
    "decision_id",
    "run_id",
    "question_id",
    "question",
    "answer",
    "governing_inputs",
    "subject",
    "scope",
    "decision_type",
    "source_kind",
)


def test_ws2_direct_prompt_decision_record_is_valid_only_with_owning_run_id(tmp_path):
    fixture(tmp_path)
    full = validate_run(tmp_path, RUN_REF)["decision"]
    record = {key: full[key] for key in DIRECT_PROMPT_DECISION_FIELDS}
    record.update(decision_type="approval", source_kind="direct_operator")
    _ws2_rebind(tmp_path, decision=record)
    assert validate_run(tmp_path, RUN_REF)["decision"] == record
    del record["run_id"]
    _ws2_rebind(tmp_path, decision=record)
    with _raises(ContractError, match="^decision run mismatch$"):
        validate_run(tmp_path, RUN_REF)


def test_ws2_rl_cross_run_decision_ref_rejected(tmp_path):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    foreign = f".kapisch/runs/{OTHER_RUN_ID}/decisions/d1.json"
    digest = _ws2_put(tmp_path, foreign, records["decision"])
    work = records["workorder"]
    work.update(decision_ref=foreign, decision_digest=digest)
    _ws2_rebind(tmp_path, work=work)
    with _raises(ContractError, match="^decision reference is outside its Run$"):
        validate_run(tmp_path, RUN_REF)


def test_ws2_rl_other_run_malformed_decision_ignored(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    foreign = tmp_path / f".kapisch/runs/{OTHER_RUN_ID}/decisions/bad.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("not json")
    assert (
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )["decision"]["run_id"]
        == RUN_ID
    )


def test_ws2_rl_two_runs_independent_decisions(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    run_b = _ws2_new_ready_run(tmp_path)
    result_a = _validate_dispatch(
        tmp_path,
        RUN_REF,
        capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )
    result_b = _validate_dispatch(
        tmp_path,
        run_b,
        capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )
    assert result_a["decision"]["run_id"] == RUN_ID
    assert result_b["decision"]["run_id"] == OTHER_RUN_ID
    assert result_a["decision"]["decision_id"] == result_b["decision"]["decision_id"]


def test_ws2_rl_same_decision_id_allowed_in_different_runs(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    run_b = _ws2_new_ready_run(tmp_path)
    assert validate_run(tmp_path, RUN_REF)["decision"]["decision_id"] == "d1"
    assert validate_run(tmp_path, run_b)["decision"]["decision_id"] == "d1"


def test_ws2_rl_cross_run_supersedes_target_rejected(tmp_path):
    from kapisch_core._task_supersession import _validate_supersession_graph

    fixture(tmp_path)
    _ws2_new_ready_run(tmp_path)
    foreign_ref = f".kapisch/runs/{OTHER_RUN_ID}/decisions/d1.json"
    entry = {
        "decision_id": "d1",
        "decision_ref": foreign_ref,
        "decision_digest": hashlib.sha256(
            (tmp_path / foreign_ref).read_bytes()
        ).hexdigest(),
    }
    _ws2_add_decision(tmp_path, "d2", supersedes=[entry])
    with _raises(ContractError, match="^supersedes target is outside its Run$"):
        _validate_supersession_graph(tmp_path, RUN_DIR)


def test_ws2_rl_supersession_in_run_a_does_not_affect_run_b(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    run_b = _ws2_new_ready_run(tmp_path)
    _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    with _raises(ContractError, match="^decision is superseded: d1$"):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )
    result_b = _validate_dispatch(
        tmp_path,
        run_b,
        capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )
    assert result_b["decision"]["run_id"] == OTHER_RUN_ID


def test_ws2_rl_completed_outcome_unaffected_by_later_supersession(tmp_path):
    fixture(tmp_path)
    expected = _ws2_persist_outcome(tmp_path)
    _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    assert (
        _validate_outcome(tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES) == expected
    )
    assert _ws2_restart(tmp_path, "validate_outcome") == expected


def test_ws2_rl_cold_process_reconstruction(tmp_path):
    fixture(tmp_path)
    script = "from kapisch_core.task_contract import validate_run; import sys; validate_run(sys.argv[1], sys.argv[2], source_root=sys.argv[1])"
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "core"),
    }
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), RUN_REF],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@_params(
    "ref",
    [
        "docs/d1.json",
        f"{RUN_DIR}/decisions/other.json",
        f"{RUN_DIR}/decisions/../decisions/d1.json",
        f"{RUN_DIR}/decisions/nested/d1.json",
    ],
)
@_params(
    "ref",
    [
        "docs/d1.json",
        f"{RUN_DIR}/decisions/other.json",
        f"{RUN_DIR}/decisions/../decisions/d1.json",
        f"{RUN_DIR}/decisions/nested/d1.json",
    ],
)
def test_ws2_decision_layout_rejected(tmp_path, ref):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    work = records["workorder"]
    work["decision_ref"] = ref
    _ws2_put(tmp_path, ref, records["decision"])
    _ws2_rebind(tmp_path, work=work)
    expected = (
        "decision identity is not unique or reference mismatches"
        if ref.endswith("/other.json")
        else "malformed decision reference"
    )
    with _raises(ContractError, match="^" + re.escape(expected) + "$"):
        validate_run(tmp_path, RUN_REF)


def test_ws2_duplicate_decision_identity(tmp_path):
    fixture(tmp_path)
    record = validate_run(tmp_path, RUN_REF)["decision"]
    _ws2_put(
        tmp_path,
        f".kapisch/runs/{OTHER_RUN_ID}/decisions/d1.json",
        {**record, "run_id": OTHER_RUN_ID},
    )
    assert validate_run(tmp_path, RUN_REF)["decision"]["decision_id"] == "d1"


@_params("target_kind", ["internal", "escaping", "loop"])
@_params("component", ["file", "decisions", "run"])
def test_ws2_decision_symlink_components(tmp_path, target_kind, component):
    from kapisch_core._task_decisions import _load_decision

    fixture(tmp_path)
    # A decision reference within this Run traverses the symlinked component.
    if component == "file":
        link_path = tmp_path / RUN_DIR / "decisions" / "d1.json"
        outside_target = tmp_path / "docs" / "target.json"
    elif component == "decisions":
        decisions = tmp_path / RUN_DIR / "decisions"
        moved = tmp_path / RUN_DIR / "saved-decisions"
        decisions.rename(moved)
        link_path = decisions
        outside_target = moved
    else:
        run_path = tmp_path / RUN_DIR
        moved = tmp_path / ".kapisch" / "saved-run"
        run_path.rename(moved)
        link_path = run_path
        outside_target = moved
    if component == "file":
        link_path.unlink()
    if target_kind == "internal":
        target = outside_target
    elif target_kind == "escaping":
        target = tmp_path.parent / "outside-ws2-artifact"
    else:
        target = link_path
    link_path.symlink_to(target, target_is_directory=component != "file")
    with _raises(ContractError, match="^decision reference contains a symlink$"):
        _load_decision(
            tmp_path, RUN_DIR, f"{RUN_DIR}/decisions/d1.json", require_digest=False
        )


def test_ws2_decision_digest_binding(tmp_path):
    fixture(tmp_path)
    path = tmp_path / f"{RUN_DIR}/decisions/d1.json"
    path.write_bytes(path.read_bytes() + b" ")
    with _raises(
        ContractError,
        match=(
            "^"
            + re.escape(f"artifact digest mismatch: {RUN_DIR}/decisions/d1.json")
            + "$"
        ),
    ):
        validate_run(tmp_path, RUN_REF)


@_params(
    ("where", "value", "message"),
    [
        ("decision", "bad.id", "invalid decision identity"),
        ("decision", "d2", "decision identity is not unique or reference mismatches"),
        ("workorder", "d2", "decision reference mismatch"),
    ],
)
def test_ws2_decision_identity_bindings(tmp_path, where, value, message):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    if where == "decision":
        decision = records["decision"]
        decision["decision_id"] = value
        _ws2_rebind(tmp_path, decision=decision)
    else:
        work = records["workorder"]
        work["decision_id"] = value
        _ws2_rebind(tmp_path, work=work)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        validate_run(tmp_path, RUN_REF)


@_params(
    "decision_type",
    ["answer", "correction", "risk_acceptance", "external_effect_authorization"],
)
def test_ws2_selected_nonapproval_cannot_authorize(tmp_path, decision_type):
    fixture(tmp_path)
    decision = validate_run(tmp_path, RUN_REF)["decision"]
    decision["decision_type"] = decision_type
    _ws2_rebind(tmp_path, decision=decision)
    with _raises(ContractError, match="^work order is not authorized$"):
        validate_run(tmp_path, RUN_REF)


@_params(
    ("result", "message"),
    [
        ("not_applicable", "decision applicability result is not_applicable"),
        ("ambiguous", "decision applicability result is ambiguous"),
        (
            "reassessment_required",
            "decision applicability result is reassessment_required",
        ),
        ("superseded", "invalid decision applicability result"),
        ("unknown", "invalid decision applicability result"),
        ("", "invalid decision applicability result"),
        (None, "invalid decision applicability result"),
        (1, "invalid decision applicability result"),
        (True, "invalid decision applicability result"),
        ([], "invalid decision applicability result"),
        ({}, "invalid decision applicability result"),
        ("__omit__", "invalid decision applicability result"),
    ],
)
def test_ws2_result_diagnostics(tmp_path, result, message):
    fixture(tmp_path)
    app = validate_run(tmp_path, RUN_REF)["applicability"]
    if result == "__omit__":
        app.pop("result")
    else:
        app["result"] = result
    _ws2_rebind(tmp_path, applicability=app)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        validate_run(tmp_path, RUN_REF)


@_params("reason", [None, "", "  ", 0, [], {}, "__omit__"])
def test_ws2_invalid_reason_keeps_existing_diagnostic(tmp_path, reason):
    fixture(tmp_path)
    app = validate_run(tmp_path, RUN_REF)["applicability"]
    if reason == "__omit__":
        app.pop("reason")
    else:
        app["reason"] = reason
    _ws2_rebind(tmp_path, applicability=app)
    with _raises(
        ContractError,
        match=("^decision applicability is missing, stale, or not applicable$"),
    ):
        validate_run(tmp_path, RUN_REF)


@_params("snapshot", [[], [{"ref": "external:opaque ref", "digest": "0" * 64}] * 2])
def test_ws2_historical_reader_matches_producer_snapshot(tmp_path, snapshot):
    from kapisch_core._task_decisions import _load_decision

    fixture(tmp_path)
    record = validate_run(tmp_path, RUN_REF)["decision"]
    record["governing_inputs"] = snapshot
    record["approving_party"] = "operator"
    ref = f"{RUN_DIR}/decisions/d1.json"
    # Use one original: put the fixture's identity under a distinct identity instead.
    record["decision_id"] = "history"
    ref = f"{RUN_DIR}/decisions/history.json"
    digest = _ws2_put(tmp_path, ref, record)
    assert _load_decision(tmp_path, RUN_DIR, ref, digest) == record


@_params("original_present", [False, True])
def test_ws2_empty_selected_inputs_cannot_authorize(tmp_path, original_present):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    decision, app, work = (
        records[key] for key in ("decision", "applicability", "workorder")
    )
    decision["governing_inputs"] = []
    if original_present:
        app["original_governing_inputs"] = []
    _ws2_rebind(tmp_path, decision=decision, applicability=app, work=work)
    with _raises(ContractError, match="^work order requires governing Git inputs$"):
        validate_run(tmp_path, RUN_REF)


def _ws2_edge(root, decision_id):
    run = RUN_ID
    ref = f".kapisch/runs/{run}/decisions/{decision_id}.json"
    return {
        "decision_id": decision_id,
        "decision_ref": ref,
        "decision_digest": hashlib.sha256((root / ref).read_bytes()).hexdigest(),
    }


def _ws2_add_decision(root, decision_id, *, supersedes=None):
    work = json.loads((root / RUN_DIR / "workorder.json").read_text())
    record = json.loads((root / work["decision_ref"]).read_text())
    record.pop("supersedes", None)
    record.update(decision_id=decision_id, question_id="different-" + decision_id)
    if supersedes is not None:
        record["supersedes"] = supersedes
    ref = f"{RUN_DIR}/decisions/{decision_id}.json"
    _ws2_put(root, ref, record)
    return ref


def _ws2_graph(root):
    from kapisch_core._task_supersession import _validate_supersession_graph

    return _validate_supersession_graph(root, RUN_DIR)


def test_ws2_graph_transitive_different_question_non_revival(tmp_path):
    fixture(tmp_path)
    assert _ws2_graph(tmp_path) == frozenset()
    _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    assert _ws2_graph(tmp_path) == frozenset({"d1"})
    _ws2_add_decision(tmp_path, "d3", supersedes=[_ws2_edge(tmp_path, "d2")])
    assert _ws2_graph(tmp_path) == frozenset({"d1", "d2"})


@_params(
    ("value", "message"),
    [
        (None, "invalid decision supersedes"),
        ([], "invalid decision supersedes"),
        ({}, "invalid decision supersedes"),
        ([None], "invalid supersedes entry"),
        ([{}], "invalid supersedes entry"),
        (
            [
                {
                    "decision_id": "d1",
                    "decision_ref": "docs/d1.json",
                    "decision_digest": "0" * 64,
                }
            ],
            "malformed decision reference",
        ),
        (
            [
                {
                    "decision_id": [],
                    "decision_ref": f"{RUN_DIR}/decisions/d1.json",
                    "decision_digest": "0" * 64,
                }
            ],
            "invalid supersedes decision identity",
        ),
        (
            [
                {
                    "decision_id": "d1",
                    "decision_ref": f"{RUN_DIR}/decisions/d1.json",
                    "decision_digest": [],
                }
            ],
            "invalid supersedes decision digest",
        ),
    ],
)
def test_ws2_graph_edge_schema(tmp_path, value, message):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record["supersedes"] = value
    _ws2_put(tmp_path, ref, record)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        _ws2_graph(tmp_path)


@_params(
    ("variant", "message"),
    [
        ("extra", "invalid supersedes entry"),
        ("duplicate", "duplicate supersedes target"),
        ("missing", "supersedes target is missing"),
        ("identity", "supersedes target identity mismatch"),
        ("digest", f"artifact digest mismatch: {RUN_DIR}/decisions/d1.json"),
    ],
)
def test_ws2_graph_invalid_target_binding(tmp_path, variant, message):
    fixture(tmp_path)
    edge = _ws2_edge(tmp_path, "d1")
    edges = [edge]
    if variant == "extra":
        edge["extra"] = True
    elif variant == "duplicate":
        edges.append(dict(edge))
    elif variant == "missing":
        edge["decision_ref"] = f"{RUN_DIR}/decisions/absent.json"
    elif variant == "identity":
        edge["decision_id"] = "other"
    else:
        edge["decision_digest"] = "0" * 64
    _ws2_add_decision(tmp_path, "d2", supersedes=edges)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        _ws2_graph(tmp_path)


@_params("variant", ["self", "cycle"])
def test_ws2_graph_cycles_before_digest_validation(tmp_path, variant):
    fixture(tmp_path)
    ref = f"{RUN_DIR}/decisions/d1.json"
    record = json.loads((tmp_path / ref).read_text())
    self_edge = {**_ws2_edge(tmp_path, "d1"), "decision_digest": "0" * 64}
    if variant == "self":
        record["supersedes"] = [self_edge]
        message = "decision cannot supersede itself"
    else:
        _ws2_add_decision(tmp_path, "d2", supersedes=[self_edge])
        record["supersedes"] = [
            {**_ws2_edge(tmp_path, "d2"), "decision_digest": "0" * 64}
        ]
        message = "decision supersession cycle"
    _ws2_put(tmp_path, ref, record)
    with _raises(ContractError, match="^" + message + "$"):
        _ws2_graph(tmp_path)


@_params(
    ("field", "value", "message"),
    [
        ("question", None, "invalid decision question"),
        ("question_id", None, "invalid decision question identity"),
        ("subject", [], "invalid decision subject"),
        ("scope", "", "invalid decision scope"),
        ("answer", "", "invalid decision answer"),
        ("answer", "\ud800", "decision answer is not valid UTF-8"),
        ("source_kind", [], "work order is not authorized"),
        ("source_kind", "external_artifact", "work order is not authorized"),
        ("decision_type", "other", "work order is not authorized"),
        ("governing_inputs", None, "invalid historical governing inputs"),
    ],
)
def test_ws2_graph_validates_unconnected_decision(tmp_path, field, value, message):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record[field] = value
    _ws2_put(tmp_path, ref, record)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        _ws2_graph(tmp_path)


@_params(
    ("raw", "message"),
    [
        (b"{", f"invalid JSON artifact: {RUN_DIR}/decisions/d2.json"),
        (
            b'{"decision_id":"d2","decision_id":"d2"}',
            "duplicate JSON object key: decision_id",
        ),
        (b"[]", f"artifact must be an object: {RUN_DIR}/decisions/d2.json"),
    ],
)
def test_ws2_graph_uses_strict_loader(tmp_path, raw, message):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    (tmp_path / ref).write_bytes(raw)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        _ws2_graph(tmp_path)


@_params("target_kind", ["internal", "escaping", "loop"])
def test_ws2_graph_rejects_symlink_file(tmp_path, target_kind):
    fixture(tmp_path)
    path = tmp_path / RUN_DIR / "decisions/d2.json"
    target = {
        "internal": tmp_path / RUN_DIR / "decisions/d1.json",
        "escaping": tmp_path.parent / "outside-ws2-artifact",
        "loop": path,
    }[target_kind]
    path.symlink_to(target)
    with _raises(ContractError, match="^decision reference contains a symlink$"):
        _ws2_graph(tmp_path)


def test_ws2_graph_rejects_duplicate_identity(tmp_path):
    fixture(tmp_path)
    record = json.loads((tmp_path / RUN_DIR / "decisions/d1.json").read_text())
    _ws2_put(tmp_path, f"{RUN_DIR}/decisions/d1-copy.json", record)
    with _raises(
        ContractError,
        match=("^decision identity is not unique or reference mismatches$"),
    ):
        _ws2_graph(tmp_path)


@_params(
    "decision_type",
    ["answer", "correction", "risk_acceptance", "external_effect_authorization"],
)
def test_ws2_graph_accepts_nonapproval_human_decisions(tmp_path, decision_type):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record["decision_type"] = decision_type
    _ws2_put(tmp_path, ref, record)
    assert _ws2_graph(tmp_path) == frozenset()


@_params("snapshot", [[], [{"ref": "external:opaque ref", "digest": "0" * 64}] * 2])
def test_ws2_graph_accepts_producer_snapshot_and_empty_chain(tmp_path, snapshot):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record["governing_inputs"] = snapshot
    _ws2_put(tmp_path, ref, record)
    _ws2_add_decision(tmp_path, "d3", supersedes=[_ws2_edge(tmp_path, "d2")])
    ref3 = f"{RUN_DIR}/decisions/d3.json"
    record3 = json.loads((tmp_path / ref3).read_text())
    record3["governing_inputs"] = []
    _ws2_put(tmp_path, ref3, record3)
    assert _ws2_graph(tmp_path) == frozenset({"d2"})


def test_ws2_graph_reads_each_file_once(tmp_path):
    from collections import Counter
    from pathlib import Path

    fixture(tmp_path)
    previous = "d1"
    for number in range(2, 14):
        identity = f"d{number}"
        _ws2_add_decision(
            tmp_path, identity, supersedes=[_ws2_edge(tmp_path, previous)]
        )
        previous = identity
    expected = set((tmp_path / RUN_DIR / "decisions").glob("*.json"))
    reads, globs = Counter(), []
    read_bytes, glob = Path.read_bytes, Path.glob

    def counted_read(path):
        if path in expected:
            reads[path] += 1
        return read_bytes(path)

    def counted_glob(path, pattern):
        if path == tmp_path / RUN_DIR / "decisions" and pattern == "*.json":
            globs.append(pattern)
        return glob(path, pattern)

    with (
        mock.patch.object(Path, "read_bytes", counted_read),
        mock.patch.object(Path, "glob", counted_glob),
    ):
        assert _ws2_graph(tmp_path) == frozenset(f"d{i}" for i in range(1, 13))
    assert reads == Counter({path: 1 for path in expected})
    assert len(globs) == 1


_WS2_CAPABILITIES = {"write": {"status": "supported", "reason": "test adapter"}}


def _ws2_restart(root, operation, run_ref=RUN_REF):
    script = """
import json, sys
from kapisch_core import task_contract
kwargs = {"source_root": sys.argv[1], "capabilities": {"write": {"status": "supported", "reason": "restart"}}}
if sys.argv[3] in {"validate_dispatch", "claim_dispatch"}:
    kwargs["canonical_implementer_available"] = False
try:
    result = getattr(task_contract, sys.argv[3])(sys.argv[1], sys.argv[2], **kwargs)
except task_contract.ContractError as exc:
    result = {"error": str(exc)}
print(json.dumps(result, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(root), run_ref, operation],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _ws2_snapshot(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in (root / ".kapisch").rglob("*")
        if path.is_file()
    }


def _ws2_persist_outcome(root):
    outcome = validate_acceptance(root, RUN_REF, capabilities=_WS2_CAPABILITIES)
    outcome_ref = f"{RUN_DIR}/outcome.json"
    digest = _ws2_put(root, outcome_ref, outcome)
    run = json.loads((root / RUN_REF).read_text())
    run.update(outcome_ref=outcome_ref, outcome_digest=digest)
    _ws2_put(root, RUN_REF, run)
    return outcome


def _ws2_new_ready_run(root, run_id=OTHER_RUN_ID, decision_id="d1"):
    source_records = validate_run(root, RUN_REF)
    directory = f".kapisch/runs/{run_id}"
    decision_ref = f"{directory}/decisions/{decision_id}.json"
    decision = {
        **source_records["decision"],
        "run_id": run_id,
        "decision_id": decision_id,
    }
    decision_digest = _ws2_put(root, decision_ref, decision)

    applicability = {
        **source_records["applicability"],
        "decision_id": decision_id,
        "decision_ref": decision_ref,
        "decision_digest": decision_digest,
    }
    applicability_ref = f"{directory}/applicability.json"
    applicability_digest = _ws2_put(root, applicability_ref, applicability)

    work = {
        **source_records["workorder"],
        "workorder_id": f"w-{run_id[-4:]}",
        "decision_id": decision_id,
        "decision_ref": decision_ref,
        "decision_digest": decision_digest,
        "applicability_ref": applicability_ref,
        "applicability_digest": applicability_digest,
    }
    work_ref = f"{directory}/workorder.json"
    work_digest = _ws2_put(root, work_ref, work)

    run = {
        **source_records["run"],
        "run_id": run_id,
        "dispatch_state": "ready",
        "workorder_ref": work_ref,
        "workorder_digest": work_digest,
        "attempt_allocation": {
            "attempt_id": f"a-{run_id[-4:]}",
            "output_ref": f"{directory}/attempts/a-{run_id[-4:]}-output.json",
        },
    }
    for field in (
        "attempt_ref",
        "attempt_digest",
        "aggregation_ref",
        "aggregation_digest",
        "outcome_ref",
        "outcome_digest",
    ):
        run.pop(field, None)
    run_ref = f"{directory}/run.json"
    _ws2_put(root, run_ref, run)
    return run_ref


@_params("operation", ["validate_dispatch", "claim_dispatch"])
@_params("transitive", [False, True])
def test_ws2_dispatch_blocks_superseded_without_mutation(
    tmp_path, operation, transitive
):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    if transitive:
        _ws2_add_decision(tmp_path, "d3", supersedes=[_ws2_edge(tmp_path, "d2")])
    before = _ws2_snapshot(tmp_path)
    with _raises(ContractError, match="^decision is superseded: d1$"):
        getattr(task_contract, operation)(
            tmp_path,
            RUN_REF,
            source_root=tmp_path,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )
    assert _ws2_restart(tmp_path, operation) == {"error": "decision is superseded: d1"}
    assert _ws2_snapshot(tmp_path) == before
    assert not (tmp_path / RUN_DIR / "dispatch-claim.json").exists()


def test_ws2_dispatch_still_allows_original_and_new_superseder(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    result = _validate_dispatch(
        tmp_path,
        RUN_REF,
        capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )
    assert result["decision"]["decision_id"] == "d1"
    ref = _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    decision = json.loads((tmp_path / ref).read_text())
    work = validate_run(tmp_path, RUN_REF)["workorder"]
    work.update(
        decision_id="d2",
        decision_ref=ref,
        decision_digest=hashlib.sha256((tmp_path / ref).read_bytes()).hexdigest(),
    )
    _ws2_rebind(tmp_path, work=work)
    assert (
        _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )["decision"]
        == decision
    )


@_params(
    ("later", "message"),
    [
        ("valid", "decision is superseded: d1"),
        (
            "invalid_json",
            f"invalid JSON artifact: {RUN_DIR}/decisions/d2.json",
        ),
        ("duplicate_keys", "duplicate JSON object key: decision_id"),
        ("invalid_record", "invalid decision question identity"),
        ("invalid_edges", "invalid decision supersedes"),
    ],
)
def test_ws2_rl_completed_outcome_ignores_later_graph_but_dispatch_fails_closed(
    tmp_path, later, message
):
    fixture(tmp_path)
    expected = _ws2_persist_outcome(tmp_path)
    run_b = _ws2_new_ready_run(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    if later == "invalid_json":
        (tmp_path / ref).write_bytes(b"{")
    elif later == "duplicate_keys":
        (tmp_path / ref).write_bytes(b'{"decision_id":"d2","decision_id":"d2"}')
    elif later == "invalid_record":
        _ws2_put(tmp_path, ref, {"decision_id": "d2"})
    elif later == "invalid_edges":
        record = json.loads((tmp_path / ref).read_text())
        record["supersedes"] = []
        _ws2_put(tmp_path, ref, record)
    assert (
        validate_acceptance(tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES)
        == expected
    )
    assert (
        _validate_outcome(tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES) == expected
    )
    assert _ws2_restart(tmp_path, "validate_outcome") == expected
    # Run B is isolated: later invalid authority in Run A cannot poison its dispatch.
    assert (
        _validate_dispatch(
            tmp_path,
            run_b,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )["decision"]["run_id"]
        == OTHER_RUN_ID
    )


@_params("source_kind", ["external_artifact", "operator_reported_external"])
def test_ws2_external_run_local_source_attribution(tmp_path, source_kind):
    source = "records/operator-approval.md"
    fixture(tmp_path, source_kind=source_kind, source_ref=source)
    original_ref = f"{RUN_DIR}/decisions/d1.json"
    original = (tmp_path / original_ref).read_bytes()
    expected = _ws2_persist_outcome(tmp_path)
    assert expected["decision"]["ref"] == original_ref
    assert expected["decision"]["decision_id"] == "d1"
    assert expected["decision"]["source_kind"] == source_kind
    assert "source_ref" not in expected["decision"]  # No Outcome schema expansion.
    records = validate_run(tmp_path, RUN_REF)
    assert records["decision"]["source_ref"] == source
    assert (
        json.loads((tmp_path / expected["decision"]["ref"]).read_text())["source_ref"]
        == source
    )
    assert _ws2_restart(tmp_path, "validate_outcome") == expected
    assert (tmp_path / original_ref).read_bytes() == original
    assert (tmp_path / RUN_DIR / "decisions/d1.json").exists()


def test_ws2_dispatch_accepts_unrelated_empty_historical_inputs(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record["governing_inputs"] = []
    _ws2_put(tmp_path, ref, record)
    assert (
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )["decision"]["decision_id"]
        == "d1"
    )


def test_ws2_dispatch_reads_each_decision_once_per_call(tmp_path):
    from collections import Counter
    from pathlib import Path

    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    for number in range(2, 10):
        _ws2_add_decision(tmp_path, f"d{number}")
    expected = set((tmp_path / RUN_DIR / "decisions").glob("*.json"))
    reads, globs = Counter(), []
    read_bytes, glob = Path.read_bytes, Path.glob

    def counted_read(path):
        if path in expected:
            reads[path] += 1
        return read_bytes(path)

    def counted_glob(path, pattern):
        if path == tmp_path / RUN_DIR / "decisions" and pattern == "*.json":
            globs.append(pattern)
        return glob(path, pattern)

    with (
        mock.patch.object(Path, "read_bytes", counted_read),
        mock.patch.object(Path, "glob", counted_glob),
    ):
        for invocation in (1, 2):
            _validate_dispatch(
                tmp_path,
                RUN_REF,
                capabilities=_WS2_CAPABILITIES,
                canonical_implementer_available=False,
            )
            assert reads == Counter({path: invocation for path in expected})
            assert (
                len(globs) == invocation
            )  # No cross-call cache, including selected d1.


@_params("supersedes", [False, True])
def test_ws2_missing_retained_reference_fails_closed_after_restart(
    tmp_path, supersedes
):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    ref = records["workorder"]["decision_ref"]
    if supersedes:
        edge = {
            "decision_id": "d1",
            "decision_ref": ref,
            "decision_digest": records["workorder"]["decision_digest"],
        }
        _ws2_add_decision(tmp_path, "d2", supersedes=[edge])
        # Reference d2 as the selected authority, retaining its edge to d1.
        d2_ref = f"{RUN_DIR}/decisions/d2.json"
        work, app = records["workorder"], records["applicability"]
        digest = hashlib.sha256((tmp_path / d2_ref).read_bytes()).hexdigest()
        for record in (work, app):
            record.update(decision_id="d2", decision_ref=d2_ref, decision_digest=digest)
        _ws2_rebind(tmp_path, work=work, applicability=app)
    # Archive, never delete, the original file; consumers still reference its old path.
    archive = tmp_path / "archived-decisions"
    archive.mkdir()
    (tmp_path / ref).rename(archive / "d1.json")
    expected = (
        "supersedes target is missing" if supersedes else "missing referenced decision"
    )
    assert _ws2_restart(tmp_path, "validate_dispatch")["error"] == expected


@_params("case", ["first", "second", "zero", "mismatch"])
def test_ws2_mut_unique_decision_reference_rejects_invalid_match_count(tmp_path, case):
    from kapisch_core._task_decisions import _validate_unique_decision_reference

    local = f"{RUN_DIR}/decisions/d1.json"
    foreign = f".kapisch/runs/{OTHER_RUN_ID}/decisions/d1.json"
    if case != "zero":
        path = tmp_path / local
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    if case == "second":
        path = tmp_path / foreign
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    if case in {"first", "second"}:
        _validate_unique_decision_reference(tmp_path, RUN_DIR, "d1", local)
    else:
        mismatched_ref = local if case == "zero" else f"{RUN_DIR}/decisions/other.json"
        with _raises(
            ContractError,
            match="^decision identity is not unique or reference mismatches$",
        ):
            _validate_unique_decision_reference(tmp_path, RUN_DIR, "d1", mismatched_ref)


def test_ws2_mut_historical_nonstring_ref_rejected(tmp_path):
    from kapisch_core._task_decisions import _validated_historical_inputs

    with _raises(ContractError, match="^malformed governing Git input$"):
        _validated_historical_inputs([{"ref": 1, "digest": "0" * 64}])


def test_ws2_mut_historical_whitespace_ref_rejected(tmp_path):
    from kapisch_core._task_decisions import _validated_historical_inputs

    with _raises(ContractError, match="^malformed governing Git input$"):
        _validated_historical_inputs([{"ref": "  ", "digest": "0" * 64}])


def test_ws2_mut_supersedes_duplicate_id_only_rejected(tmp_path):
    from kapisch_core._task_supersession import _supersedes_entries

    fixture(tmp_path)
    with _raises(ContractError, match="^duplicate supersedes target$"):
        _supersedes_entries(
            tmp_path,
            RUN_DIR,
            {
                "supersedes": [
                    {
                        "decision_id": "d1",
                        "decision_ref": f"{RUN_DIR}/decisions/a.json",
                        "decision_digest": "0" * 64,
                    },
                    {
                        "decision_id": "d1",
                        "decision_ref": f"{RUN_DIR}/decisions/b.json",
                        "decision_digest": "1" * 64,
                    },
                ]
            },
        )


def test_ws2_mut_supersedes_duplicate_ref_only_rejected(tmp_path):
    from kapisch_core._task_supersession import _supersedes_entries

    fixture(tmp_path)
    with _raises(ContractError, match="^duplicate supersedes target$"):
        _supersedes_entries(
            tmp_path,
            RUN_DIR,
            {
                "supersedes": [
                    {
                        "decision_id": "d1",
                        "decision_ref": f"{RUN_DIR}/decisions/a.json",
                        "decision_digest": "0" * 64,
                    },
                    {
                        "decision_id": "d2",
                        "decision_ref": f"{RUN_DIR}/decisions/a.json",
                        "decision_digest": "1" * 64,
                    },
                ]
            },
        )


def test_ws2_mut_decision_digest_defaults_fail_closed(tmp_path):
    from kapisch_core._task_artifacts import _load_with_digest
    from kapisch_core._task_decisions import _load_decision, _read_decision_record

    fixture(tmp_path)
    ref = f"{RUN_DIR}/decisions/d1.json"
    for operation in (
        lambda: _load_with_digest(tmp_path, ref),
        lambda: _read_decision_record(tmp_path, RUN_DIR, ref),
        lambda: _load_decision(tmp_path, RUN_DIR, ref),
    ):
        with _raises(
            ContractError,
            match="^missing artifact digest: "
            + re.escape(f"{RUN_DIR}/decisions/d1.json")
            + "$",
        ):
            operation()


def test_ws2_kernel_never_mutates_any_decision_file(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    before = {
        p: p.read_bytes() for p in tmp_path.glob(".kapisch/runs/*/decisions/*.json")
    }
    _validate_dispatch(
        tmp_path,
        RUN_REF,
        capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )
    assert {p: p.read_bytes() for p in before} == before
    record = json.loads((tmp_path / ref).read_text())
    record["supersedes"] = [_ws2_edge(tmp_path, "d1")]
    _ws2_put(tmp_path, ref, record)  # Human-boundary fixture, not a kernel mutation.
    before = {p: p.read_bytes() for p in before}
    with _raises(ContractError, match="^decision is superseded: d1$"):
        _validate_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )
    assert {p: p.read_bytes() for p in before} == before


@_params("entry", ["validate_run", "validate_dispatch"])
def test_ws2_fix_decision_inspection_oserror_is_contract_error(tmp_path, entry):
    import errno

    fixture(tmp_path)
    if entry == "validate_dispatch":
        _reset_to_unclaimed(tmp_path)
    original_exists = Path.exists
    decision_path = tmp_path / f"{RUN_DIR}/decisions/d1.json"

    def failing_exists(path):
        if path == decision_path:
            raise OSError(errno.EIO, "injected I/O error")
        return original_exists(path)

    with mock.patch.object(Path, "exists", failing_exists):
        with _raises(ContractError, match="^cannot inspect decision reference$"):
            if entry == "validate_run":
                validate_run(tmp_path, RUN_REF)
            else:
                _validate_dispatch(
                    tmp_path,
                    RUN_REF,
                    capabilities=_WS2_CAPABILITIES,
                    canonical_implementer_available=False,
                )


def test_ws2_fix_missing_decision_retains_diagnostic(tmp_path):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    (tmp_path / records["workorder"]["decision_ref"]).unlink()
    with _raises(ContractError, match="^missing referenced decision$"):
        validate_run(tmp_path, RUN_REF)


@_params("invalidity", ["acceptance", "applicability_digest"])
def test_ws2_fix_stale_governing_input_precedes_other_invalidity(tmp_path, invalidity):
    fixture(tmp_path)
    work_path = tmp_path / RUN_DIR / "workorder.json"
    work = json.loads(work_path.read_text())
    if invalidity == "acceptance":
        work["acceptance_criteria"] = []
        _ws2_rebind(tmp_path, work=work)
    else:
        work["applicability_digest"] = "0" * 64
        run = json.loads((tmp_path / RUN_REF).read_text())
        run["workorder_digest"] = _ws2_put(tmp_path, run["workorder_ref"], work)
        _ws2_put(tmp_path, RUN_REF, run)
    (tmp_path / "docs/spec.md").write_text("stale governing input\\n")
    with _raises(
        ContractError,
        match="^current governing inputs require reassessment$",
    ):
        validate_run(tmp_path, RUN_REF)


@_params(
    ("invalidity", "message"),
    [
        ("extra_tasks", "work order must contain exactly one task"),
        ("missing_task", "work order must contain one task"),
        ("invalid_task_id", "invalid task identity"),
        ("invalid_workorder_id", "invalid work order identity"),
    ],
)
def test_ws2_fix_stale_input_follows_workorder_identity_checks(
    tmp_path, invalidity, message
):
    fixture(tmp_path)
    work = json.loads((tmp_path / RUN_DIR / "workorder.json").read_text())
    if invalidity == "extra_tasks":
        work["tasks"] = []
    elif invalidity == "missing_task":
        work["task"] = None
    elif invalidity == "invalid_task_id":
        work["task"]["task_id"] = "bad id"
    else:
        work["workorder_id"] = "bad id"
    _ws2_rebind(tmp_path, work=work)
    (tmp_path / "docs/spec.md").write_text("stale governing input\\n")
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        validate_run(tmp_path, RUN_REF)


def test_ws2_rl_create_run_mints_exclusive_run_directory(tmp_path):
    fixture(tmp_path)
    run_ids = [task_contract.create_run(tmp_path) for _ in range(2)]
    assert run_ids[0] != run_ids[1]
    for run_id in run_ids:
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            run_id,
        )
        assert list((tmp_path / ".kapisch/runs" / run_id).iterdir()) == []
    with (
        mock.patch.object(uuid, "uuid4", return_value=uuid.UUID(run_ids[0])),
        _raises(ContractError, match="^cannot create Run directory$"),
    ):
        task_contract.create_run(tmp_path)


def test_ws2_rl_create_run_fails_closed(tmp_path):
    fixture(tmp_path)
    worktree = _add_linked_worktree(tmp_path, tmp_path / "create-run-worktree")
    with _raises(ContractError, match="^invalid state_root/source_root mapping$"):
        task_contract.create_run(worktree)
    repo = tmp_path.parent / f"{tmp_path.name}-symlinked-state"
    outside = tmp_path.parent / f"{tmp_path.name}-outside-state"
    outside.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".kapisch").symlink_to(outside, target_is_directory=True)
    with _raises(ContractError, match="^Run directory escapes project root$"):
        task_contract.create_run(repo)
    assert list(outside.iterdir()) == []


def test_ws2_rl_claim_rechecks_supersession_after_claim(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    create_exclusive = task_contract._create_exclusive

    def publish_superseder_first(*args, **kwargs):
        _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
        return create_exclusive(*args, **kwargs)

    with (
        mock.patch.object(task_contract, "_create_exclusive", publish_superseder_first),
        _raises(ContractError, match="^decision is superseded: d1$"),
    ):
        _claim_dispatch(
            tmp_path,
            RUN_REF,
            capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )
    assert (tmp_path / RUN_DIR / "dispatch-claim.json").is_file()
    assert json.loads((tmp_path / RUN_REF).read_text())["dispatch_state"] == "claimed"
