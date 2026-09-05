# PR #26 Independent Review and Remediation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` for a separately authorized implementation. This review does not authorize implementation, commits, or pushes. Implementation steps below are intentionally unchecked.

**Goal:** Repair three verified P0–P2-scope defects in PR #26 without replacing its architecture.

**Architecture:** Keep canonical graph/state, immutable outcome records, the derived controller view, and portable Python command-line tools. Add the missing node/attempt invariant and correct two input-handling boundaries. No service, transaction framework, schema migration, or new dependency is needed.

**Tech Stack:** Python 3.11+, TOML (`tomllib`), JSON, `unittest`.

**Spec:** `docs/superpowers/specs/2026-08-31-parent-token-usage-design.md`, especially “Authoritative layers,” “Stage outcome contract,” “Resume and failure behavior,” and “Validator implications.”

## 1. Verdict and review scope

**Verdict: NOT-APPROVE.** Fix F1–F3 and run the verification checklist before requesting another review.

| Severity | Confirmed findings |
| --- | --- |
| P0 | None found |
| P1 | F1: a completed node/workflow can have only a failed implementation attempt |
| P2 | F2: non-regular existing controller views hang/crash the renderer |
| P2 | F3: malformed verification results crash validation and rendering |

This is an independent source review, not a restatement of prior PR comments. Three fresh-context, read-only reviewers inspected integrity, migration/rendering, and benchmark/contracts separately. The parent reproduced accepted findings and filtered speculative or overstated concerns.

- PR: <https://github.com/twKrash/kapisch/pull/26>
- Title: Add KAPISCH v4 controller view and outcomes
- Base: `ce352b4560587c92aff31ec434e186b27ee3bc56`
- Reviewed head: `9f5256b78e25aff4b55644b0c29fd4453ea96203`
- Scope: 210 changed files; Python implementation, tests, fixtures, portable contracts, packaging, and CI.
- Line references below refer to this head, not to future revisions.
- Runtime checks were performed locally on Linux. Windows behavior and actual provider benchmark runs were not independently executed.

### Completed review checklist

- [x] Confirm exact PR revisions and clean starting worktree.
- [x] Run existing portable-package and repository tests.
- [x] Obtain independent reviews of three distinct change areas.
- [x] Reproduce and deduplicate accepted findings.
- [x] Assign severities and a merge verdict.
- [x] Provide concrete, separately executable remediation tasks.

## 2. Global constraints

- Only this document is changed by the review; no implementation fixes are applied.
- No commits, pushes, remote review submissions, or KAPISCH skill invocation.
- Preserve v1–v3 readability; never silently migrate legacy runs.
- Preserve reviewer/final evidence requirements and immutable terminal evidence.
- Keep Python 3.11 compatibility and do not add dependencies.
- Do not “fix” invalid evidence by changing its status to success, regenerating source reports, or editing outcome history.
- Keep the controller view a replaceable projection, not a new source of authority.
- Release acceptance and measured token savings remain separate from PR merge readiness.

## 3. Verification evidence

These commands were run against the reviewed code, not against the proposed fixes:

| Command | Observed result |
| --- | --- |
| `cd plugins/kapisch && python scripts/test_portable_package.py` | Exit 0; 342 tests passed; `portable-package=passed` |
| `python -m unittest discover -s tests -v` from repository root | Exit 0; 16 tests passed |
| `python scripts/check_plugin_version.py --base ce352b4560587c92aff31ec434e186b27ee3bc56` from repository root | Exit 0; `1.1.0 -> 1.2.1`, `material=True` |
| F1 temporary-fixture reproduction | Renderer exit 0, validator exit 0, view `next_action = "complete"` despite failed implementation attempt/outcome |
| F2 temporary-fixture reproduction | FIFO: subprocess timed out after 3 seconds; directory: exit 1 with `IsADirectoryError` |
| F3 temporary-fixture reproduction | Validator and renderer both exit 1 with `TypeError`; JSON validator stdout is empty |
| Stale controller-view binding recovery | Replacing the state’s view digest with 64 zeroes, then rerunning the renderer, returns exit 0 |

Passing existing tests does not invalidate these findings: the reproduced cases are missing from current coverage. Proposed test/implementation snippets below are instructions for later work, not a claim that fixes have been executed or tested.

## 4. Findings

### F1 — P1: completed workflows can conceal a failed terminal attempt

**Location:** `plugins/kapisch/kapisch_validation/outcomes.py:214-215` and `:398-416`.

**Problem:** The validator checks that an outcome’s `lifecycle` equals its attempt’s `status`, but does not reconcile the latest attempt with the owning node’s terminal status. The controller chooses completion from node statuses, not attempt outcomes.

**Reproduction:** Copy `tests/kapisch_validation/fixtures/valid-v4-controller` to a temporary directory. Keep `T01`, `R01`, `F01`, and workflow state complete. Change only T01’s sole assignment attempt from `complete` to `failed`; change `stage-outcomes/AT-T01-1.toml` to `lifecycle="failed"`, `role_status="failed"`, and `next_action_reason="failed"`. Preserve existing report and invocation evidence. Run rendering, then validation. Both return 0, and the view still advertises `next_action="complete"` and validator success.

**Impact:** Resume/snapshot validation can certify mutually contradictory durable facts and present a completed workflow when its only implementation attempt records failure. This is a correctness failure at the new v4 integrity boundary, not merely malformed-input ergonomics. A previous-snapshot transition check is not a substitute: normal snapshot validation must reject this state on its own.

**Required correction:** For v4 nodes in `complete`, `blocked`, or `failed`, require their last persisted assignment attempt to have the same terminal status. Existing per-attempt outcome validation must continue to require a matching terminal outcome. Check the last attempt in persisted list order, not the lexically largest attempt ID. Do not reject historical failed attempts merely because a later legal attempt succeeded.

### F2 — P2: a non-regular existing view hangs or crashes recovery

**Location:** `plugins/kapisch/scripts/render_controller_view.py:35-36`.

**Problem:** After intentionally skipping view validation, the renderer backs up an existing view using `Path.read_bytes()` outside its error-handling block. A named pipe blocks on open; a directory raises an uncaught exception. This is exactly the recovery entry point for a missing or corrupt derived view.

**Reproduction:** In a temporary copy of `valid-v4-controller`, remove `04-controller-view.toml`, create a FIFO at that path, then invoke the renderer with a subprocess timeout. It does not return within 3 seconds. Replacing the file with a directory instead produces exit 1 and `IsADirectoryError`.

**Impact:** A corrupt or user-created run artifact can stall the controller indefinitely instead of producing a bounded failure. P2 is appropriate: the trigger is a non-regular local artifact, not a failure of ordinary valid runs.

**Required correction:** Read backup bytes through a nonblocking descriptor, require a regular file before reading, and return 2 for non-regular/unreadable inputs before any writes. A genuinely missing view must remain regenerable. Preserve the ability to replace corrupt regular-file bytes, including invalid UTF-8, because the view is derived and its old bytes are needed only for rollback.

### F3 — P2: malformed verification results escape the validation error protocol

**Location:** `plugins/kapisch/kapisch_validation/outcomes.py:143-153`.

**Problem:** `_collection_errors()` correctly identifies non-string fields, but `_schema_errors()` continues and tests an unhashable `result` against Python sets. For example, TOML `result=[]` raises `TypeError` instead of returning `ValidationError` records. A TOML inline table has the same problem.

**Reproduction:** Copy `valid-v4-controller`; in `stage-outcomes/AT-T01-1.toml`, replace the verification record’s `result = "pass"` with `result = []`. Run `validate_kapisch.py --format json` and `render_controller_view.py`. Both exit 1 with a traceback at line 147; the validator produces no JSON.

**Impact:** An agent-produced shape error breaks machine-readable validation and the controller’s normal invalid-artifact handling. The input is rejected only by crashing, rather than by the established exit-2/error-record contract.

**Required correction:** After collection shape validation, skip result-specific checks when `result` is not a string. Keep the existing wrong-shape error; do not coerce arrays/tables to strings or catch all exceptions around the entire validator.

## 5. Implementation plan

### Preparation: understand and establish the baseline

All paths below are relative to the repository root unless a command explicitly changes directory. Do not edit committed fixture evidence in place; tests must operate on temporary copies.

- [ ] Read `outcomes.py`, `controller_view.py`, `scripts/render_controller_view.py`, and the existing outcome/controller tool tests.
- [ ] Read the spec sections identified in the header. In particular, distinguish node lifecycle from attempt lifecycle and distinguish canonical evidence from a derived view.
- [ ] Record `git status --short` and `git rev-parse HEAD`. If HEAD differs from the reviewed head, check whether any finding has already been fixed before applying the snippets.
- [ ] Run the three baseline commands in section 3. Investigate unrelated failures separately rather than weakening assertions.

### Task 1: enforce terminal node/latest-attempt consistency (F1)

**Modify:** `plugins/kapisch/kapisch_validation/outcomes.py`.

**Tests:** `plugins/kapisch/tests/kapisch_validation/test_outcomes.py`.

**Interfaces:** Keep `validate_outcomes(manifest, state, task_dir) -> list[ValidationError]`. Add a v4-only invariant before its existing per-attempt loop. Introduce error code `TWV-OUTCOME-NODE-LIFECYCLE`; use the node ID in the reference so a controller can locate the contradiction.

- [ ] Add `tomllib` and `render_toml` imports to `test_outcomes.py`, then add this regression method to `OutcomeTests`:

```python
def test_complete_node_rejects_failed_latest_attempt(self):
    from kapisch_validation.cli import validate
    from kapisch_validation.outcomes import validate_outcomes

    with tempfile.TemporaryDirectory() as temporary:
        task = Path(temporary) / "task"
        shutil.copytree(FIXTURES / "valid-v4-controller", task)
        graph_path = task / "02-execution-graph.toml"
        graph = tomllib.loads(graph_path.read_text(encoding="utf-8"))
        node = next(node for node in graph["nodes"] if node["id"] == "T01")
        self.assertEqual(node["status"], "complete")
        node["assignment"]["attempts"][-1]["status"] = "failed"
        graph_path.write_bytes(render_toml(graph))

        outcome_path = task / "stage-outcomes/AT-T01-1.toml"
        outcome = tomllib.loads(outcome_path.read_text(encoding="utf-8"))
        outcome.update(
            lifecycle="failed", role_status="failed",
            next_action_reason="failed",
        )
        outcome_path.write_bytes(render_toml(outcome))

        manifest = parse_manifest(graph_path).manifest
        state, state_errors = parse_state(task / "03-state.toml")
        self.assertIsNotNone(manifest)
        self.assertIsNotNone(state)
        self.assertEqual(state_errors, [])
        self.assertIn(
            "TWV-OUTCOME-NODE-LIFECYCLE",
            {error.code for error in validate_outcomes(manifest, state, task)},
        )
        self.assertIn(
            "TWV-OUTCOME-NODE-LIFECYCLE",
            {error.code for error in validate(ROOT / "skills/kapisch", task)},
        )
        # Existing helper checks exit 2 and byte-for-byte non-mutation.
        self.assert_render_and_validate(task, "TWV-OUTCOME-NODE-LIFECYCLE")
```

Required imports at module scope:

```python
import tomllib
from kapisch_validation.canonical_toml import render_toml
```

- [ ] Run `cd plugins/kapisch && python -m unittest tests.kapisch_validation.test_outcomes.OutcomeTests.test_complete_node_rejects_failed_latest_attempt -v`. Before the fix, the new invariant assertion must fail because the error code is absent; a failure due only to stale view bytes is not sufficient evidence.
- [ ] Add the following check immediately after the v4 guard and `errors` initialization in `validate_outcomes`, before constructing/processing the attempt collection:

```python
for node in manifest.nodes:
    if node.status not in {"complete", "blocked", "failed"}:
        continue
    assignment = node.raw.get("assignment")
    history = assignment.get("attempts") if isinstance(assignment, dict) else None
    latest = history[-1] if isinstance(history, list) and history else None
    if not isinstance(latest, dict) or latest.get("status") != node.status:
        errors.append(_e(
            "TWV-OUTCOME-NODE-LIFECYCLE",
            task_dir / "02-execution-graph.toml",
            f"{node.id}.assignment.attempts",
            "latest attempt status must match terminal node status",
        ))
```

This is a focused proposed implementation. The rest of `validate_outcomes` still verifies required outcomes and their lifecycle/report/invocation bindings; do not remove those checks. A terminal node with a latest pending/running attempt must also fail. Cancelled nodes are deliberately excluded because this patch must not invent a cancellation-outcome schema.

- [ ] Add a table-driven unit test using the already imported `SimpleNamespace` and the existing fixture. For each terminal node status (`complete`, `blocked`, `failed`), try each latest attempt status (`pending`, `running`, `complete`, `blocked`, `failed`). Assert the new error is present exactly when statuses differ. Inspect only the new error code; other fixture bindings may intentionally mismatch in this isolated matrix. A concrete loop is:

```python
def test_terminal_node_attempt_status_matrix(self):
    task = FIXTURES / "valid-v4-controller"
    state, errors = parse_state(task / "03-state.toml")
    self.assertEqual(errors, [])
    for status in ("complete", "blocked", "failed"):
        for attempt_status in ("pending", "running", "complete", "blocked", "failed"):
            with self.subTest(status=status, attempt_status=attempt_status):
                node = SimpleNamespace(
                    id="T01", status=status,
                    raw={"assignment": {"attempts": [{"status": attempt_status}]}},
                )
                manifest = SimpleNamespace(version=4, nodes=[node])
                codes = {e.code for e in validate_outcomes(manifest, state, task)}
                self.assertEqual(
                    "TWV-OUTCOME-NODE-LIFECYCLE" in codes,
                    status != attempt_status,
                )
```

- [ ] Extend that isolated matrix with these explicit expectations: empty history on a complete node emits the new code; a complete node with `[failed, complete]` history does not emit it; `[complete, failed]` does emit it; the same isolated objects with manifest version 3 return no outcome errors. This tests ordering and legacy gating without pretending these minimal objects form a fully valid graph.
- [ ] Run `cd plugins/kapisch && python -m unittest tests.kapisch_validation.test_outcomes tests.kapisch_validation.test_controller_view tests.kapisch_validation.test_controller_tools -v`.

**Done when:** The original contradiction is rejected by snapshot validation and the renderer without rewriting artifacts, valid v4 fixtures still pass, and legacy versions remain unchanged.

### Task 2: make outcome verification shape errors non-throwing (F3)

**Modify:** `plugins/kapisch/kapisch_validation/outcomes.py`.

**Tests:** `plugins/kapisch/tests/kapisch_validation/test_outcomes.py`.

**Interfaces:** Preserve `parse_outcome(path) -> (raw_or_none, errors)`. Invalid scalar shapes should return `None` and `TWV-OUTCOME-WRONG-SHAPE`, not throw.

- [ ] Add this regression to `OutcomeTests`. It uses the `tomllib` and `render_toml` imports from Task 1:

```python
def test_verification_result_wrong_shapes_are_reported(self):
    for value in ([], {}, ["pass"], {"value": "pass"}, True, 1):
        with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary) / "task"
            shutil.copytree(FIXTURES / "valid-v4-controller", task)
            path = task / "stage-outcomes/AT-T01-1.toml"
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            raw["verification"][0]["result"] = value
            path.write_bytes(render_toml(raw))
            parsed, errors = parse_outcome(path)
            self.assertIsNone(parsed)
            self.assertIn("TWV-OUTCOME-WRONG-SHAPE", {e.code for e in errors})
            self.assert_render_and_validate(task, "TWV-OUTCOME-WRONG-SHAPE")
```

- [ ] Run the new method alone and confirm the pre-fix failure is the reproduced `TypeError` for the array/table cases.
- [ ] Immediately after `result = record.get("result")` in `_schema_errors`, add the guard below. `_collection_errors` has already reported missing or non-string values:

```python
if not isinstance(result, str):
    continue
```

- [ ] Keep the existing vocabulary and digest rules for actual strings. Do not replace set membership with coercion or silently accept bad values.
- [ ] Add a JSON CLI assertion for the `[]` case: invoke the validator with `--format json`; require exit 2, parse stdout with `json.loads`, assert an error’s `code` is `TWV-OUTCOME-WRONG-SHAPE`, and assert stderr contains no `Traceback`. Use a 10-second subprocess timeout.

```python
result = subprocess.run(
    [sys.executable, str(ROOT / "scripts/validate_kapisch.py"),
     "--task-dir", str(task), "--format", "json"],
    capture_output=True, text=True, timeout=10,
)
self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
self.assertIn(
    "TWV-OUTCOME-WRONG-SHAPE",
    {error["code"] for error in json.loads(result.stdout)},
)
self.assertNotIn("Traceback", result.stderr)
```

Add `import json` at module scope for this assertion. Place it inside a temporary-fixture test after mutating the verification result, not after the directory has been deleted.

- [ ] Run `cd plugins/kapisch && python -m unittest tests.kapisch_validation.test_outcomes -v`.

**Done when:** Invalid arrays/tables produce deterministic validation errors, neither entry point crashes, malformed inputs cause no writes, and valid result/digest cases still pass.

### Task 3: safely snapshot an existing derived view (F2)

**Modify:** `plugins/kapisch/scripts/render_controller_view.py`.

**Tests:** `plugins/kapisch/tests/kapisch_validation/test_controller_tools.py`.

**Interfaces:** Add a private helper returning `bytes | None` for a readable regular file or genuinely absent file. Other I/O cases must reach a bounded `return 2` before any atomic replacement.

- [ ] Add `os` and `stat` imports to the controller tool tests. Add the following methods to `ToolTests`:

```python
def test_existing_view_directory_is_rejected_without_writes(self):
    with tempfile.TemporaryDirectory() as directory:
        task = Path(directory) / "task"
        shutil.copytree(FIXTURES / "valid-v4-controller", task)
        view = task / "04-controller-view.toml"
        state = task / "03-state.toml"
        before = state.read_bytes()
        view.unlink()
        view.mkdir()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/render_controller_view.py"),
             "--task-dir", str(task)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(state.read_bytes(), before)
        self.assertTrue(view.is_dir())

@unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
def test_existing_view_fifo_is_rejected_without_blocking(self):
    with tempfile.TemporaryDirectory() as directory:
        task = Path(directory) / "task"
        shutil.copytree(FIXTURES / "valid-v4-controller", task)
        view = task / "04-controller-view.toml"
        state = task / "03-state.toml"
        before = state.read_bytes()
        view.unlink()
        os.mkfifo(view)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/render_controller_view.py"),
             "--task-dir", str(task)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(state.read_bytes(), before)
        self.assertTrue(stat.S_ISFIFO(view.stat().st_mode))
```

Do not read the FIFO to build a before/after snapshot; that would hang the test itself. The state-byte assertion and file-type assertion are intentional.

- [ ] Run the two new tests alone. Before the fix, the directory assertion sees exit 1 and the FIFO case raises `TimeoutExpired`. `subprocess.run` kills/reaps its child on timeout, so the regression must not leave a renderer running.
- [ ] Add `import stat` to the renderer, then add this small helper near `atomic`. It follows the existing nonblocking regular-file strategy in `kapisch_validation/artifact_io.py` but preserves arbitrary old bytes for rollback:

```python
def _existing_view_bytes(path: Path) -> bytes | None:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("existing controller view is not a regular file")
        chunks = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)
```

- [ ] Replace the existing one-line backup expression with an error-handled backup, before any writes:

```python
try:
    old_state = (d / "03-state.toml").read_bytes()
    old_view = _existing_view_bytes(d / "04-controller-view.toml")
except OSError:
    return 2
```

Do not merely call `is_file()` followed by `read_bytes()`: that recreates a check/open race and does not ensure the opened descriptor is regular. Do not use a UTF-8-only reader for old view backup unless it also exposes original bytes on decode failure.

- [ ] Add a positive regeneration test for each of these inputs: missing view; regular file containing `b"not TOML"`; regular file containing `b"\xff"`. For each temporary copy, run rendering with timeout 10, require exit 0, then require `validate_kapisch.py` exit 0. The existing canonical graph/state/outcomes must stay authoritative.
- [ ] Add a regression with a valid regular view and `controller_view_sha256` changed to 64 zeroes in state. Rendering must return 0 and full validation must then return 0. This preserves the existing interrupted-update repair path.
- [ ] Run `cd plugins/kapisch && python -m unittest tests.kapisch_validation.test_controller_tools tests.kapisch_validation.test_artifact_io -v`. The FIFO-specific test is skipped on systems without `os.mkfifo`; the directory and regular-file tests must run everywhere.

**Done when:** Non-regular inputs return promptly with exit 2 and no mutation; missing/stale/corrupt regular views still regenerate; no descriptor leaks or new transaction architecture are introduced.

## 6. Final implementation verification and handoff

Run these only after a later authorized implementation has completed the tasks:

- [ ] From `plugins/kapisch`: `python -m unittest tests.kapisch_validation.test_outcomes tests.kapisch_validation.test_controller_view tests.kapisch_validation.test_controller_tools tests.kapisch_validation.test_artifact_io -v`.
- [ ] From `plugins/kapisch`: `python scripts/test_portable_package.py`.
- [ ] From repository root: `python -m unittest discover -s tests -v`.
- [ ] From repository root: `python scripts/check_plugin_version.py --base ce352b4560587c92aff31ec434e186b27ee3bc56` while this is still the PR base. For a later PR, use its actual base. Do not blindly bump a version merely because these review fixes are applied before the existing candidate is released.
- [ ] Run `git diff --check` and inspect `git diff --stat` for accidental fixture regeneration or unrelated refactoring.
- [ ] Run the portable suite on Python 3.11/Linux and Windows CI. Confirm FIFO skip behavior and directory rejection on Windows.
- [ ] Request a fresh review of F1–F3 against the new head, including the negative tests and v1–v3 compatibility evidence.
- [ ] Keep the verdict NOT-APPROVE until those checks succeed. Do not claim release readiness without the separately required real benchmark and platform evidence.

## 7. Suggestions and rejected escalations

These are not additional confirmed P0–P2 findings and do not justify architectural expansion:

1. **Wire the version checker into CI if automatic enforcement is intended.** `quality.yml` tests the checker’s behavior but does not run it against the actual PR diff. Current PR versions already pass, and contribution guidance tells maintainers to run it; therefore this review does not label the missing automation a current P1 defect. A future CI addition should handle PR base SHA and push-event base semantics explicitly.
2. **Correct the release-document link.** `plugins/kapisch/README.md:126-130` still points at `acceptance-windows-v1.2.0.md`, although the 1.2.1 template exists. Update it to the 1.2.1 document when doing documentation cleanup. This is a minor release-navigation issue, not an additional P2 merge blocker here.
3. **Keep benchmark claims measurement-only.** The comparator accepts JSONL-reported review decisions; it is not a canonical reviewer-identity verifier. `docs/controller-benchmark.md` already reserves release acceptance for humans. Do not interpret `required_evidence_present` as cryptographic or independent proof of reviewer identity. Adding full invocation verification is not required by this review absent a new automated-acceptance contract.
4. **Do not redesign view updates as a transaction system for this patch.** Separate view/state replacements can leave a stale digest after interruption, but the renderer skips derived-view validation while rebuilding and repairs that state on rerun. The claimed “permanently invalid snapshot” was not reproduced; stale-binding recovery returned 0. Keep/add the recovery regression in Task 3 rather than introducing directory transactions or a durable journal.

## 8. Review deliverable boundary

This document records findings, evidence, and proposed future work only. No production/test code was changed to address them, no commits or pushes were made, and no remote approval or rejection was submitted. The verdict applies only to the exact reviewed head identified above.
