# WS-2 Decision Applicability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse immutable HumanDecisions across Runs, reassess current Git inputs without rewriting historical authority, and reject explicitly superseded decisions only before new dispatch.

**Architecture:** Separate local decision reading, WorkOrder authorization, Git snapshot validation, and dispatch-only global supersession. Extract one shared decision reader and one small graph validator; reuse the existing strict JSON loader and governing-input primitives. Only `validate_dispatch` calls graph policy; `claim_dispatch` delegates before creating a claim. Persist no derived supersession result or index.

**Tech Stack:** Existing Python standard library, Git, pytest for focused development, and canonical unittest discovery. No new runtime dependencies or persistence layer.

**Spec:** `docs/superpowers/specs/2026-11-05-ws-2-decision-applicability-design.md` (binding; read with this plan).

## Global Constraints

Plan approval does not authorize commits, pushes or merges. The executor leaves changes uncommitted; the owner decides whether and when to publish. SDD review packages must use the stash-free working-tree checkpoint alternative in Step 6, not BASE..HEAD. Fixture commits run only in temporary test repositories.

- “Decisions are never copied or re-created.” Positive reuse references one original immutable decision, even across Runs. Only rejection tests deliberately duplicate authority.
- “The decision and its `governing_inputs` snapshot stay immutable.” Original snapshots are historical; assessed snapshots still match HEAD, index and working-tree bytes.
- “`subject` and `scope` in applicability and WorkOrder must still equal the decision's, byte for byte.” No action field or task-level matcher is added; semantic action coverage stays with the coordinator.
- “`superseded` is **not** a persisted result.” Only `applicable` with a non-empty reason authorizes work. Absent `original_governing_inputs` retains #85 meaning.
- “Consequence is **prospective and dispatch-only**.” Both global graph integrity and eligibility run only in `validate_dispatch` and delegated `claim_dispatch`, never in `validate_run`, `_validate_workorder`, acceptance or Outcome reconstruction. Local loading does not inspect `supersedes`.
- “No global question identity.” Opaque non-empty `question_id`; no semantic matcher, question index, database, event log, new orchestration subsystem, Pi changes, or task-level authorization (WS-4).
- “Produced by the human-input boundary together with the new decision; the coordinator never adds it.” Recording a direct human prompt is that boundary, not permission to infer supersession. Producer implementations remain WS-11/WS-12.
- “Cold restart: all state reconstructs from the decision files, applicability, WorkOrder and Run.” No controller memory, caller honesty, conversational state or mutable derived view supplies authority.
- Enumerate exactly `.kapisch/runs/*/decisions/*.json`; every enumerated record validates, including disconnected records. PR85-009 incomplete-enumeration limitations under arbitrary filesystem corruption are unchanged.
- Preserve the existing current-Git freshness checks, including their pre-existing acceptance/Outcome consequences. See the open follow-up below.
- Do not use Kapisch to execute work on Kapisch. This plan is external work; execute through the named superpowers skill, not Kapisch workflows.
- Keep actual implementation to the listed files. During this revision no worktree production/tests were edited, and no destructive shell or file-deletion operations were performed. Prototype changes live only in scratch.

## Review Focus

1. Internal, escaping/dangling and looped symlink components: `test_ws2_decision_symlink_components` (Task 1), `test_ws2_graph_rejects_symlink_file` (Task 4). Reject before resolution; unrelated artifact semantics stay unchanged.
2. Equal malformed historical snapshots with valid current inputs: `test_ws2_equal_malformed_historical_snapshots_rejected` and `test_ws2_present_invalid_original_is_not_absent` (Task 3).
3. Later unrelated malformed decisions cannot poison a completed Outcome: `test_ws2_completed_outcome_ignores_later_graph_but_dispatch_fails_closed` (Task 5).
4. Digest-bound cycles cannot require impossible hash fixed points to exercise cycle detection: `test_ws2_graph_cycles_before_digest_validation` (Task 4) asserts exact structural errors before digest checks.
5. A legitimate non-approval HumanDecision is not an approval, and an already-claimed fixture must not masquerade as a supersession rejection: `test_ws2_selected_nonapproval_cannot_authorize` (Task 1), `test_ws2_graph_accepts_nonapproval_human_decisions` (Task 4), and explicit resets plus exact errors in Task 5.

## File Structure and Ownership

Line references are **verified baseline worktree references**, not speculative post-insertion locations. New files have no invented line numbers.

| File | Responsibility/change | Baseline → tested final lines |
| --- | --- | --- |
| `core/kapisch_core/_task_artifacts.py` | One strict parser returning parsed object and same-read digest; legacy _load facade. | 210 → 217 |
| `core/kapisch_core/_task_decisions.py` | Canonical reference, immutable read snapshot and producer-shaped historical validation; no graph policy. | new → 139 |
| `core/kapisch_core/_task_authority.py` | Selected approval/non-empty original authority, kernel-owned applicability constants, binding and existing route authorization. | 154 → 161 |
| `core/kapisch_core/_task_governing_inputs.py` | Strict selected/current snapshot shape and unchanged current-Git checks. | 81 → 89 |
| `core/kapisch_core/_task_supersession.py` | Single enumeration/parse; identity/path/digest and forward-edge maps; dispatch-only cycle/hash/eligibility. | new → 115 |
| `core/kapisch_core/task_contract.py` | Private Run helper receives call-local snapshot only from dispatch; public local validation is unchanged. | 456 → 471 |
| `tests/core/test_task_contract.py` | Default-compatible fixture; focused table-driven and read-count/retention/immutability regressions under existing unittest loader. | 2151 → 2973 |
| `tests/core/test_package.py` | One structural/constant-driven metadata method; installed-console test unchanged. | 127 → 166 |
| `core/contracts/task-first.md` | Full semantic guidance, producer/history distinction, retention and minimal stable JSON contract block. | 80 → 156 |
| Binding spec and this plan | Listed clarifications and approved executable instructions. | documents |

One-way imports are fixed, not deferred:

```text
task_contract -> _task_authority -> _task_decisions -> _task_artifacts
_task_authority -> _task_governing_inputs -> _task_artifacts
task_contract -> _task_supersession -> _task_decisions
_task_supersession -> _task_artifacts
_task_authority -> _task_governing_inputs, _task_artifacts
```

No lower-level module imports the lifecycle facade, authority validator or graph module. Only the facade imports graph policy, and only dispatch invokes it. All new functions remain private.

Structural ruling: retain the existing lifecycle facade deliberately (471 lines, below 500); the new private Run helper only threads a dispatch-owned byte snapshot and preserves the public API. Do not split unrelated claim/acceptance/Outcome code. `_validate_workorder` is 69 lines, a cohesive local-authorization/route boundary; historical shape, freshness and graph policy remain delegated. This crosses the ~60-line review trigger, but no changed production module exceeds 500 lines and no production function exceeds 100. Keep the existing regression module and unittest loader rather than inventing a new test system. The artifact helper is a focused same-parser refactor, not a new storage model.

## Execution Dependencies and Real Commands

Strict order: **1 → 2 → 3 → 4 → 5 → 6**. Fixtures precede consumers; historical validation precedes graph fixtures; the graph interface precedes dispatch wiring; prose follows final diagnostics. Fresh implementers need only this plan, its spec, and the checkout; scratch scripts are not dependencies.

The canonical core command is `.github/workflows/quality.yml:21`: `PYTHONPATH=core python -m unittest discover -s tests/core -v`. Focused pytest uses the same `PYTHONPATH=core`. `_params` functions count once under pytest but expand per row under unittest. Run the **whole task-contract unittest suite after each Task 1–5**, not only selected new tests.

Existing tests whose names/assertions stay **unchanged**:

| Test | Verified baseline location | Compatibility pinned |
| --- | --- | --- |
| `test_persisted_files_reconstruct_acceptance` | `tests/core/test_task_contract.py:297–378` | Exact baseline Outcome |
| `test_stale_governing_inputs_require_reassessment` | `tests/core/test_task_contract.py:381–385` | Working-tree freshness |
| `test_staged_governing_input_requires_reassessment` | `tests/core/test_task_contract.py:758–765` | Index freshness |
| `test_committed_governing_input_change_requires_reassessment` | `tests/core/test_task_contract.py:768–777` | HEAD freshness |
| `test_non_applicable_or_ambiguous_answer_cannot_be_promoted` | `tests/core/test_task_contract.py:470–499` | Error retains `applicability` |
| `test_applicability_requires_nonempty_text_reason` | `tests/core/test_task_contract.py:597–617` | Error retains **`decision applicability`** |
| `test_workorder_cannot_exceed_decided_subject_or_scope` | `tests/core/test_task_contract.py:2125–2136` | Authority ceiling |
| `test_outcome_is_persisted_and_reconstructed_in_a_fresh_process` | `tests/core/test_task_contract.py:817–850` | Real Outcome persistence/restart recipe |
| `PackageTests.test_installed_console_matches_module_cli` | `tests/core/test_package.py:15–123` | Installed-package CLI |

Intentionally updated existing assertions: **none**. Only the common fixture gains default-preserving optional parameters. New tests pin changed diagnostics without weakening existing assertions. `_reset_to_unclaimed` already exists at `tests/core/test_task_contract.py:93–115` and must run before new dispatch tests, never on a completed historical Run.

## Exact Validation Contract

- Literal decision-ref fullmatch: `r"\.kapisch/runs/[A-Za-z0-9][A-Za-z0-9._-]*/decisions/[A-Za-z0-9][A-Za-z0-9_-]*\.json"`. No leading slash, dot/dot-dot components, backslash, nested directory or alternate extension. The run-directory component uses existing portable-component characters; decision IDs keep `_required_id`'s no-dot grammar.
- Inspect every path component from the resolved project root to the decision file before `_load` resolves it. Reject internal, escaping, dangling and looped links alike. The caller's project-root argument retains its existing resolution semantics; this is not a global artifact policy change.
- `_load` delegates to `_load_with_digest`, which owns confinement, exact-byte digest checks, strict JSON and duplicate-key handling in one parse. Local non-dispatch paths retain the existing selected-ID uniqueness scan; dispatch instead uses one complete invocation-local identity/ref/digest snapshot with no duplicate identities. Loading an original decision never requires its original Run metadata.
- `_validated_historical_inputs` owns the producer snapshot shape: list, including empty; exact `{ref, digest}` objects; non-empty string refs and lowercase 64-hex digests. It permits duplicates and opaque/non-Git refs exactly as the producer does. No current-byte check applies to historical snapshots. Optional emitted attribution is absent or a non-empty string; null request attribution is omitted on emission. `external_artifact` requires `source_ref`.
- `_validated_governing_inputs` separately owns selected authority/current WorkOrder shape: non-empty, unique, portable refs; then `_validate_governing_inputs` checks current HEAD/index/worktree bytes. A selected empty-input decision always raises `work order requires governing Git inputs`, even if assessed inputs are non-empty and `original_governing_inputs=[]` matches. Applicability assessed inputs equal WorkOrder assessed inputs exactly.
- `original_governing_inputs=[]` is present, valid historical shape, and equals only an empty decision snapshot. Absence instead requires assessed inputs to equal the decision snapshot (#85). A direct historical comparison can match empty originals, but that fact never authorizes an empty-input decision. Null/malformed originals fail closed; [] against a non-empty snapshot is `original governing inputs mismatch`.
- The shared reader recognizes the existing five HumanDecision types. Only a selected authorizing decision must be `approval`; do not infer approval from answer text.
- Graph absence means no edges; present empty/null/non-list is invalid. Each edge has exactly three keys and no repeated target ID or reference. Validate all local records first; then edge structure, target identity and self-reference; then cycles; then edge digests; finally selected-decision eligibility. Sorted enumeration and heap traversal make failures deterministic. Cycle errors intentionally precede their inconsistent hashes.
- Eligibility is the union of **all** validated targets, not only leaf superseders. Thus d3→d2→d1 still blocks d1 and d2: transitive and no revival. No durable `superseded` field or graph cache.
- Dispatch performs one glob and one read/parse per decision, including selected authority and all edge targets. Temporary identity→record/path/digest and reference lookups plus forward edges resolve all targets and hashes. Complexity: O(N log N + E) time plus total input-byte reading/parsing, O(N + E) auxiliary graph space plus parsed data. Sorting and the deterministic heap account for N log N; no N per-node enumeration. Every subsequent validation call starts from disk.
- Cross-Run authority is a retention obligation: retain every referenced decision and its supersedes chain unmodified while any Run or WorkOrder references it. Archiving/removing a containing Run directory breaks cold-restart validation. Missing selected authority raises `missing referenced decision`; missing chain targets raise `supersedes target is missing`. Retention policy/GC is out of scope and owner-decided; the kernel never mutates decision files.

| Condition | Exact error | Owning proof |
| --- | --- | --- |
| Invalid path | `malformed decision reference` | Tasks 1,4 layout/schema |
| Any path symlink | `decision reference contains a symlink` | Tasks 1,4 aliases/loops |
| Inspection OSError | `cannot inspect decision reference` | Explicit implementation error boundary |
| Invalid local ID | `invalid decision identity` | Task 1 identity |
| Duplicate ID or wrong filename | `decision identity is not unique or reference mismatches` | Tasks 1,4 |
| WorkOrder ID mismatch | `decision reference mismatch` | Task 1 identity |
| Invalid type/source or selected nonapproval/subject/scope | `work order is not authorized` | Tasks 1,3,4 |
| Blocked result | `decision applicability result is not_applicable`, `decision applicability result is ambiguous`, `decision applicability result is reassessment_required` | Task 2 result table |
| Unknown/missing/non-string/container result, including `superseded` | `invalid decision applicability result` | Task 2 result table |
| Invalid reason or other applicability binding | `decision applicability is missing, stale, or not applicable` | Tasks 2,3 |
| Legacy absent-original mismatch | `governing inputs require reassessment` | Task 3 binding |
| Present original differs from decision | `original governing inputs mismatch` | Task 3 binding |
| Missing/null/empty/non-list snapshot | `work order requires governing Git inputs` | Task 3 shape table; existing diagnostic retained |
| Malformed snapshot record | `malformed governing Git input` | Task 3 shape table |
| Duplicate snapshot ref | `duplicate governing Git input` | Task 3 shape table |
| Current bytes drift | `current governing inputs require reassessment` | Unchanged freshness tests |
| Invalid present supersedes | `invalid decision supersedes` | Tasks 4,5 |
| Invalid entry shape | `invalid supersedes entry` | Task 4 tables |
| Bad edge ID/digest | `invalid supersedes decision identity`, `invalid supersedes decision digest` | Task 4 schema |
| Duplicate edge target | `duplicate supersedes target` | Task 4 targets |
| Missing/wrong-ID target | `supersedes target is missing`, `supersedes target identity mismatch` | Task 4 targets |
| Self/cycle | `decision cannot supersede itself`, `decision supersession cycle` | Task 4 exact error assertions |
| Target digest mismatch (example literal) | `artifact digest mismatch: .kapisch/runs/r1/decisions/d1.json` | Task 4 target table |
| Selected decision superseded | `decision is superseded: d1` | Task 5 direct/fresh-process APIs |
| Bad later JSON | `invalid JSON artifact: .kapisch/runs/graph/decisions/d2.json` | Tasks 4,5 |
| Duplicate keys | `duplicate JSON object key: decision_id` | Tasks 4,5 |
| Non-object JSON | `artifact must be an object: .kapisch/runs/graph/decisions/d2.json` | Task 4 strict loader |

Other primitive errors remain the unchanged loader and `_required_text`/`_required_id` errors. Every literal used by a new assertion appears in its complete table below.

### Task 1: Shared canonical decision reader and cross-Run reuse

**Files:** Create `core/kapisch_core/_task_decisions.py`; modify `core/kapisch_core/_task_artifacts.py` (`_load` only, adding `_load_with_digest`), `core/kapisch_core/_task_governing_inputs.py`, and `core/kapisch_core/_task_authority.py:20–34,69–99`; replace fixture at `tests/core/test_task_contract.py:118–258`; append tests to that test module.

**Interfaces:** Consume the existing strict artifact parser, ID/text primitives and current-Git checks. Produce `_load_with_digest(...) -> tuple[dict[str, Any], str]`, `_validated_governing_inputs(inputs)`, `_validated_historical_inputs(inputs)`, `_DecisionRecord(ref, digest, decision)`, `_read_decision_record(...)`, `_load_decision(..., records=None)`, and `_validate_decision_path(...)`. The reader's optional mapping is supplied only by Task 5 dispatch; it never survives the call. `_ws2_put` and `_ws2_rebind` are complete module-level test helpers.

- [ ] **Step 1: Write the fixtures and complete failing tests.** Replace the entire existing fixture with this default-compatible version. It writes one original decision before the consuming WorkOrder/Run and constructs external attribution before any downstream digest/claim bindings.

```python
def fixture(
    tmp_path, *, decision_run="r1", source_kind="direct_operator", source_ref=None
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
        "run_id": "r1",
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
    task_contract.claim_dispatch(
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
```

Append these complete helpers/tests to `tests/core/test_task_contract.py`; its imports and `load_tests` already support them. Only intentional negative layout/identity tests copy invalid authority.

```python

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


def test_ws2_cross_run_reuse_has_one_original(tmp_path):
    fixture(tmp_path, decision_run="original")
    original = tmp_path / ".kapisch/runs/original/decisions/d1.json"
    before = original.read_bytes()
    records = validate_run(tmp_path, RUN_REF)
    assert records["workorder"]["decision_ref"] == (
        ".kapisch/runs/original/decisions/d1.json"
    )
    assert list(tmp_path.glob(".kapisch/runs/*/decisions/*.json")) == [original]
    assert original.read_bytes() == before


@_params("ref", [
    "docs/d1.json", ".kapisch/runs/r1/decisions/other.json",
    ".kapisch/runs/r1/decisions/../decisions/d1.json",
    ".kapisch/runs/r1/decisions/nested/d1.json",
])
def test_ws2_decision_layout_rejected(tmp_path, ref):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    work = records["workorder"]
    work["decision_ref"] = ref
    _ws2_put(tmp_path, ref, records["decision"])
    _ws2_rebind(tmp_path, work=work)
    expected = (
        "decision identity is not unique or reference mismatches"
        if ref.endswith("/other.json") else "malformed decision reference"
    )
    with _raises(ContractError, match="^" + re.escape(expected) + "$"):
        validate_run(tmp_path, RUN_REF)


def test_ws2_duplicate_decision_identity(tmp_path):
    fixture(tmp_path)
    record = validate_run(tmp_path, RUN_REF)["decision"]
    _ws2_put(tmp_path, ".kapisch/runs/other/decisions/d1.json", record)
    with _raises(ContractError, match=(
        "^decision identity is not unique or reference mismatches$"
    )):
        validate_run(tmp_path, RUN_REF)


@_params("target_kind", ["internal", "escaping", "loop"])
@_params("component", ["file", "decisions", "run"])
def test_ws2_decision_symlink_components(tmp_path, target_kind, component):
    from kapisch_core._task_decisions import _load_decision

    fixture(tmp_path)
    record = validate_run(tmp_path, RUN_REF)["decision"]
    target_ref = ".kapisch/runs/original/decisions/d1.json"
    _ws2_put(tmp_path, target_ref, {**record, "decision_id": "d1"})
    alias_ref = ".kapisch/runs/alias/decisions/d1.json"
    suffix = {"file": "decisions/d1.json", "decisions": "decisions", "run": ""}
    alias = tmp_path / ".kapisch/runs/alias" / suffix[component]
    internal = tmp_path / ".kapisch/runs/original" / suffix[component]
    alias.parent.mkdir(parents=True, exist_ok=True)
    if target_kind == "internal":
        target = internal
    elif target_kind == "escaping":
        target = tmp_path.parent / "outside-ws2-artifact"
    else:
        target = alias
    alias.symlink_to(target, target_is_directory=component != "file")
    with _raises(ContractError, match="^decision reference contains a symlink$"):
        _load_decision(tmp_path, alias_ref, require_digest=False)


def test_ws2_decision_digest_binding(tmp_path):
    fixture(tmp_path, decision_run="original")
    path = tmp_path / ".kapisch/runs/original/decisions/d1.json"
    path.write_bytes(path.read_bytes() + b" ")
    with _raises(ContractError, match=(
        r"^artifact digest mismatch: \.kapisch/runs/original/decisions/d1\.json$"
    )):
        validate_run(tmp_path, RUN_REF)

@_params(("where", "value", "message"), [
    ("decision", "bad.id", "invalid decision identity"),
    ("decision", "d2", "decision identity is not unique or reference mismatches"),
    ("workorder", "d2", "decision reference mismatch"),
])
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


@_params("decision_type", [
    "answer", "correction", "risk_acceptance", "external_effect_authorization"
])
def test_ws2_selected_nonapproval_cannot_authorize(tmp_path, decision_type):
    fixture(tmp_path)
    decision = validate_run(tmp_path, RUN_REF)["decision"]
    decision["decision_type"] = decision_type
    _ws2_rebind(tmp_path, decision=decision)
    with _raises(ContractError, match="^work order is not authorized$"):
        validate_run(tmp_path, RUN_REF)


@_params("snapshot", [[], [{"ref": "external:opaque ref", "digest": "0" * 64}] * 2])
def test_ws2_historical_reader_matches_producer_snapshot(tmp_path, snapshot):
    from kapisch_core._task_decisions import _load_decision

    fixture(tmp_path)
    record = validate_run(tmp_path, RUN_REF)["decision"]
    record["governing_inputs"] = snapshot
    record["approving_party"] = "operator"
    ref = ".kapisch/runs/history/decisions/d1.json"
    # Use one original: put the fixture's identity under a distinct identity instead.
    record["decision_id"] = "history"
    ref = ".kapisch/runs/history/decisions/history.json"
    digest = _ws2_put(tmp_path, ref, record)
    assert _load_decision(tmp_path, ref, digest) == record


@_params("original_present", [False, True])
def test_ws2_empty_selected_inputs_cannot_authorize(tmp_path, original_present):
    fixture(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    decision, app, work = (records[key] for key in ("decision", "applicability", "workorder"))
    decision["governing_inputs"] = []
    if original_present:
        app["original_governing_inputs"] = []
    _ws2_rebind(tmp_path, decision=decision, applicability=app, work=work)
    with _raises(ContractError, match="^work order requires governing Git inputs$"):
        validate_run(tmp_path, RUN_REF)
```

- [ ] **Step 2: Prove red.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k ws2 -q`

Expected: cross-Run cases fail the old outside-Run rule; symlink-reader imports fail before the module exists. Retained negative/approval tests may already pass. **Actual revision-2 run:** exit 1, **6 failed, 3 passed, 66 deselected**.

- [ ] **Step 3: Implement the shared loader, distinct historical/current shapes, and reader.** In `core/kapisch_core/_task_artifacts.py`, replace `_load` with these two functions; leave every other helper unchanged. `_load_with_digest` returns the exact-byte digest from the same read/parse, so graph edges never reread target files. `_load` remains backward-compatible and uses that single strict parser.

```python
def _load(
    root: Path, ref: Any, digest: Any = None, *, require_digest: bool = True
) -> dict[str, Any]:
    value, _ = _load_with_digest(root, ref, digest, require_digest=require_digest)
    return value


def _load_with_digest(
    root: Path, ref: Any, digest: Any = None, *, require_digest: bool = True
) -> tuple[dict[str, Any], str]:
    if require_digest and digest is None:
        raise ContractError(f"missing artifact digest: {ref}")
    try:
        raw = (
            _read_bytes(root, ref, digest)
            if digest is not None
            else _read_bytes_without_digest(root, ref)
        )
        value = json.loads(
            raw,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
            parse_float=_finite_float,
        )
    except ContractError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ) as exc:
        raise ContractError(f"invalid JSON artifact: {ref}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"artifact must be an object: {ref}")
    return value, hashlib.sha256(raw).hexdigest()
```

Replace `core/kapisch_core/_task_governing_inputs.py` with this complete version. This extracts strict non-empty/unique/portable shape validation for **selected WorkOrder authority**, not historical records; existing HEAD/index/worktree checks are unchanged.

```python
"""Freshness validation for tracked Git inputs to task WorkOrders."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from ._task_artifacts import _DIGEST, _REF, ContractError, _resolve


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError("cannot validate current Git inputs") from exc
    return result.stdout.strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError("cannot validate current Git inputs") from exc
    return result.stdout


def _validated_input_record(item: Any) -> tuple[str, str]:
    if not isinstance(item, dict) or set(item) != {"ref", "digest"}:
        raise ContractError("malformed governing Git input")
    ref, digest = item["ref"], item["digest"]
    if (
        not isinstance(ref, str)
        or not _REF.fullmatch(ref)
        or ".." in ref.split("/")
        or not isinstance(digest, str)
        or not _DIGEST.fullmatch(digest)
    ):
        raise ContractError("malformed governing Git input")
    return ref, digest


def _validate_current_input(root: Path, ref: str, digest: str) -> None:
    path = _resolve(root / ref, "governing input")
    if not path.is_relative_to(root):
        raise ContractError("governing Git input escapes project root")
    _git(root, "ls-files", "--error-unmatch", "--", ref)
    try:
        current = path.read_bytes()
        committed = _git_bytes(root, "show", f"HEAD:{ref}")
        staged = _git_bytes(root, "show", f":{ref}")
    except OSError as exc:
        raise ContractError("current governing inputs require reassessment") from exc
    if (
        hashlib.sha256(committed).hexdigest() != digest
        or hashlib.sha256(staged).hexdigest() != digest
        or hashlib.sha256(current).hexdigest() != digest
    ):
        raise ContractError("current governing inputs require reassessment")


def _validated_governing_inputs(inputs: Any) -> tuple[tuple[str, str], ...]:
    """Validate snapshot shape without consulting current Git or file bytes."""
    if not isinstance(inputs, list) or not inputs:
        raise ContractError("work order requires governing Git inputs")
    seen_refs = set()
    records = []
    for item in inputs:
        ref, digest = _validated_input_record(item)
        if ref in seen_refs:
            raise ContractError("duplicate governing Git input")
        seen_refs.add(ref)
        records.append((ref, digest))
    return tuple(records)


def _validate_governing_inputs(root: Path, inputs: Any) -> None:
    for ref, digest in _validated_governing_inputs(inputs):
        _validate_current_input(root, ref, digest)
```

Create the entire `core/kapisch_core/_task_decisions.py`. `_validated_historical_inputs` matches the actual producer's broader snapshot shape; `_read_decision_record` returns record/path/exact-byte digest without global enumeration. `_load_decision` preserves local selected-ID uniqueness on non-dispatch paths and can consume an explicitly passed dispatch snapshot without re-reading or re-globbing. This parameter is call-local data, not a cache.


```python
"""Canonical immutable HumanDecision reading and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._task_artifacts import (
    ContractError, _DIGEST, _load_with_digest, _required_id, _required_text,
)

_MISSING_DECISION = "missing referenced decision"


@dataclass(frozen=True)
class _DecisionRecord:
    ref: str
    digest: str
    decision: dict[str, Any]


_DECISION_REF = re.compile(
    r"\.kapisch/runs/[A-Za-z0-9][A-Za-z0-9._-]*/decisions/"
    r"[A-Za-z0-9][A-Za-z0-9_-]*\.json"
)


def _validate_decision_path(root: Path, ref: Any) -> None:
    if not isinstance(ref, str) or not _DECISION_REF.fullmatch(ref):
        raise ContractError("malformed decision reference")
    current = root
    for part in ref.split("/"):
        current = current / part
        try:
            linked = current.is_symlink()
        except OSError as exc:
            raise ContractError("cannot inspect decision reference") from exc
        if linked:
            raise ContractError("decision reference contains a symlink")


def _validate_unique_decision_reference(
    root: Path, decision_id: str, decision_ref: str
) -> None:
    matches = []
    for candidate in sorted(root.glob(".kapisch/runs/*/decisions/*.json")):
        if candidate.name != f"{decision_id}.json":
            continue
        ref = candidate.relative_to(root).as_posix()
        _validate_decision_path(root, ref)
        matches.append(ref)
    if len(matches) != 1 or matches[0] != decision_ref:
        raise ContractError("decision identity is not unique or reference mismatches")


def _validated_historical_inputs(inputs: Any) -> None:
    """Match the producer request snapshot shape; no freshness, path or uniqueness policy."""
    if not isinstance(inputs, list):
        raise ContractError("invalid historical governing inputs")
    for item in inputs:
        if (
            not isinstance(item, dict)
            or set(item) != {"ref", "digest"}
            or not isinstance(item["ref"], str)
            or not item["ref"].strip()
            or not isinstance(item["digest"], str)
            or not _DIGEST.fullmatch(item["digest"])
        ):
            raise ContractError("malformed governing Git input")


def _read_decision_record(
    root: Path, ref: str, digest: str | None = None, *, require_digest: bool = True
) -> _DecisionRecord:
    _validate_decision_path(root, ref)
    if not (root / ref).exists():
        raise ContractError(_MISSING_DECISION)
    decision, actual_digest = _load_with_digest(
        root, ref, digest, require_digest=require_digest
    )
    decision_id = _required_id(decision, "decision_id", "decision identity")
    if Path(ref).name != f"{decision_id}.json":
        raise ContractError("decision identity is not unique or reference mismatches")
    _required_text(decision, "question_id", "decision question identity")
    _required_text(decision, "question", "decision question")
    answer = _required_text(decision, "answer", "decision answer")
    try:
        answer.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    _required_text(decision, "subject", "decision subject")
    _required_text(decision, "scope", "decision scope")
    source = decision.get("source_kind")
    decision_type = decision.get("decision_type")
    if (
        not isinstance(decision_type, str)
        or decision_type not in {
            "answer", "correction", "approval", "risk_acceptance",
            "external_effect_authorization",
        }
        or not isinstance(source, str)
        or source not in {
            "direct_operator", "operator_reported_external", "external_artifact"
        }
        or (
            source == "external_artifact"
            and (
                not isinstance(decision.get("source_ref"), str)
                or not decision["source_ref"].strip()
            )
        )
    ):
        raise ContractError("work order is not authorized")
    for field in ("source_ref", "approving_party"):
        if field in decision:
            _required_text(decision, field, "decision " + field)
    _validated_historical_inputs(decision.get("governing_inputs"))
    return _DecisionRecord(ref, actual_digest, decision)


def _load_decision(
    root: Path, ref: str, digest: str | None = None, *, require_digest: bool = True,
    records: dict[str, _DecisionRecord] | None = None,
) -> dict[str, Any]:
    _validate_decision_path(root, ref)
    if records is None:
        record = _read_decision_record(root, ref, digest, require_digest=require_digest)
        _validate_unique_decision_reference(root, record.decision["decision_id"], ref)
    else:
        if require_digest and digest is None:
            raise ContractError(f"missing artifact digest: {ref}")
        record = records.get(ref)
        if record is None:
            raise ContractError(_MISSING_DECISION)
        if digest is not None and digest != record.digest:
            raise ContractError(f"artifact digest mismatch: {ref}")
    return record.decision
```

Replace `core/kapisch_core/_task_authority.py` with this complete intermediate version. Local loading is shared, selected authorization still requires approval, and applicability stays in the consuming Run. No graph imports.

```python
"""Validate persisted task authority and WorkOrder applicability."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ._task_artifacts import (
    ContractError,
    _load,
    _required_id,
    _required_text,
)
from ._task_decisions import _load_decision
from ._task_governing_inputs import _validate_governing_inputs, _validated_governing_inputs


def _validate_applicability(
    applicability: dict[str, Any],
    work: dict[str, Any],
    decision: dict[str, Any],
    decision_digest: str,
) -> None:
    try:
        answer_bytes = decision["answer"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    answer_digest = hashlib.sha256(answer_bytes).hexdigest()
    expected_values = (
        ("result", "applicable"),
        ("decision_id", decision["decision_id"]),
        ("decision_ref", work["decision_ref"]),
        ("decision_digest", decision_digest),
        ("answer_digest", answer_digest),
        ("subject", work["subject"]),
        ("scope", work["scope"]),
        ("governing_inputs", work["governing_inputs"]),
    )
    if any(applicability.get(key) != value for key, value in expected_values):
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )
    reason = applicability.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )


def _validate_workorder(
    base: Path, run_directory: str, work: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_ref = _required_text(work, "decision_ref", "decision reference")
    decision_digest = _required_text(work, "decision_digest", "decision digest")
    decision = _load_decision(base, decision_ref, decision_digest)
    _validated_governing_inputs(decision["governing_inputs"])
    decision_id = decision["decision_id"]
    if work.get("decision_id") != decision_id:
        raise ContractError("decision reference mismatch")
    if (
        decision["decision_type"] != "approval"
        or decision["subject"] != work.get("subject")
        or decision["scope"] != work.get("scope")
    ):
        raise ContractError("work order is not authorized")
    if "tasks" in work:
        raise ContractError("work order must contain exactly one task")
    task = work.get("task")
    if not isinstance(task, dict):
        raise ContractError("work order must contain one task")
    _required_id(task, "task_id", "task identity")
    _required_id(work, "workorder_id", "work order identity")
    governing = work.get("governing_inputs")
    if decision.get("governing_inputs") != governing:
        raise ContractError("governing inputs require reassessment")
    _validate_governing_inputs(base, governing)
    acceptance = work.get("acceptance_criteria")
    if (
        not isinstance(acceptance, list)
        or not acceptance
        or not all(isinstance(item, str) and item.strip() for item in acceptance)
    ):
        raise ContractError("invalid WorkOrder acceptance criteria")
    if not isinstance(work.get("required_capabilities"), list) or not all(
        isinstance(item, str) and item for item in work["required_capabilities"]
    ):
        raise ContractError("invalid required capabilities")
    applicability_ref = _required_text(
        work, "applicability_ref", "applicability reference"
    )
    applicability_digest = _required_text(
        work, "applicability_digest", "applicability digest"
    )
    if applicability_ref != run_directory + "/applicability.json":
        raise ContractError("Applicability reference is outside its Run")
    applicability = _load(base, applicability_ref, applicability_digest)
    _validate_applicability(applicability, work, decision, decision_digest)
    route = _required_text(work, "worker_route", "worker route")
    role = _required_text(work, "worker_role", "worker role")
    if route == "host_native_fallback":
        fallback_reason = applicability.get("fallback_authorization_reason")
        if (
            role != "worker"
            or work.get("canonical_implementer_available") is not False
            or applicability.get("host_native_fallback_authorized") is not True
            or not isinstance(fallback_reason, str)
            or not fallback_reason.strip()
        ):
            raise ContractError(
                "host-native fallback is not authorized or canonical implementer is available"
            )
    elif route == "canonical_implementer":
        if (
            role != "implementer"
            or work.get("canonical_implementer_available") is not True
        ):
            raise ContractError("canonical implementer route is not available")
    else:
        raise ContractError("unsupported worker route")
    return decision, applicability
```

- [ ] **Step 4: Verify focused green.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k ws2 -q`

Actual revision-2 focused green: exit 0, **9 passed, 66 deselected**.

- [ ] **Step 5: Verify the full task-contract compatibility gate.**

Run: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_task_contract.py`

Actual revision-2 task-contract unittest: exit 0, **147 tests, OK**.

- [ ] **Step 6: Review the uncommitted working-tree checkpoint.** Save a stash-free per-task evidence file outside the repository, for example `$EVIDENCE/task1-working-tree.patch`, using `git diff --binary -- <this task's tracked paths>`. Append every new file in this task with `git diff --no-index --binary -- /dev/null <new-file>` (exit 1 means differences, not failure). These are working-tree checkpoint patches, not BASE..HEAD packages or instructions to change HEAD. Have the task reviewer inspect the patch plus full new-file content and test logs. Leave all changes uncommitted. The final reviewer reviews the cumulative working-tree diff, including every untracked file in scope; do not rely on per-task history.

### Task 2: Applicability result and reason contract

**Files:** Modify `_validate_applicability` in `core/kapisch_core/_task_authority.py` (baseline **37–66**, not 33–65); append tests to `tests/core/test_task_contract.py`.

**Interfaces:** Consumes Task 1 fixtures and `_ws2_rebind`. Preserves `_validate_applicability(applicability, work, decision, decision_digest) -> None`. Known blocked results are distinguished before ordinary binding/reason validation; type-guard malformed values before membership checks.

- [ ] **Step 1: Append the complete failing tables.**

```python

@_params(("result", "message"), [
    ("not_applicable", "decision applicability result is not_applicable"),
    ("ambiguous", "decision applicability result is ambiguous"),
    ("reassessment_required", "decision applicability result is reassessment_required"),
    ("superseded", "invalid decision applicability result"),
    ("unknown", "invalid decision applicability result"),
    ("", "invalid decision applicability result"),
    (None, "invalid decision applicability result"),
    (1, "invalid decision applicability result"),
    (True, "invalid decision applicability result"),
    ([], "invalid decision applicability result"),
    ({}, "invalid decision applicability result"),
    ("__omit__", "invalid decision applicability result"),
])
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
    with _raises(ContractError, match=(
        "^decision applicability is missing, stale, or not applicable$"
    )):
        validate_run(tmp_path, RUN_REF)
```

- [ ] **Step 2: Prove red.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k 'ws2_result or ws2_invalid_reason' -q`

Actual revision-2 focused red: exit 1, **1 failed, 1 passed, 75 deselected**.

- [ ] **Step 3: Add the kernel-owned constants and replace only `_validate_applicability` with this complete function.** Existing imports suffice.

```python
_ORIGINAL_GOVERNING_INPUTS = "original_governing_inputs"
_APPLICABILITY_CONTROL_FIELDS = ("result", "reason")
_APPLICABILITY_RESULTS = frozenset({
    "applicable", "not_applicable", "ambiguous", "reassessment_required",
})
_APPLICABILITY_BINDING_FIELDS = (
    "decision_id", "decision_ref", "decision_digest", "answer_digest",
    "subject", "scope", "governing_inputs",
)
_APPLICABILITY_DIAGNOSTICS = {
    "invalid_result": "invalid decision applicability result",
    **{result: f"decision applicability result is {result}"
       for result in _APPLICABILITY_RESULTS if result != "applicable"},
}


def _validate_applicability(
    applicability: dict[str, Any],
    work: dict[str, Any],
    decision: dict[str, Any],
    decision_digest: str,
) -> None:
    result_field, reason_field = _APPLICABILITY_CONTROL_FIELDS
    result = applicability.get(result_field)
    if not isinstance(result, str) or result not in _APPLICABILITY_RESULTS:
        raise ContractError(_APPLICABILITY_DIAGNOSTICS["invalid_result"])
    if result != "applicable":
        raise ContractError(_APPLICABILITY_DIAGNOSTICS[result])
    try:
        answer_bytes = decision["answer"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    answer_digest = hashlib.sha256(answer_bytes).hexdigest()
    expected_values = (
        ("decision_id", decision["decision_id"]),
        ("decision_ref", work["decision_ref"]),
        ("decision_digest", decision_digest),
        ("answer_digest", answer_digest),
        ("subject", work["subject"]),
        ("scope", work["scope"]),
        ("governing_inputs", work["governing_inputs"]),
    )
    expected = dict(expected_values)
    if any(applicability.get(key) != expected[key] for key in _APPLICABILITY_BINDING_FIELDS):
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )
    reason = applicability.get(reason_field)
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )
```

- [ ] **Step 4: Verify focused green.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k 'ws2_result or ws2_invalid_reason' -q`

Actual revision-2 focused green: exit 0, **2 passed, 75 deselected**.

- [ ] **Step 5: Verify compatibility.**

Run: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_task_contract.py`

Actual revision-2 task-contract unittest: exit 0, **166 tests, OK**.

- [ ] **Step 6: Review the uncommitted working-tree checkpoint.** Save a stash-free per-task evidence file outside the repository, for example `$EVIDENCE/task2-working-tree.patch`, using `git diff --binary -- <this task's tracked paths>`. Append every new file in this task with `git diff --no-index --binary -- /dev/null <new-file>` (exit 1 means differences, not failure). These are working-tree checkpoint patches, not BASE..HEAD packages or instructions to change HEAD. Have the task reviewer inspect the patch plus full new-file content and test logs. Leave all changes uncommitted. The final reviewer reviews the cumulative working-tree diff, including every untracked file in scope; do not rely on per-task history.

### Task 3: Historical snapshot presence semantics and current-input reassessment

**Files:** Modify `core/kapisch_core/_task_authority.py` (baseline governing equality/freshness is 107–110); append tests to `tests/core/test_task_contract.py`. The distinct historical and strict current-input shape validators already come from Task 1.

**Interfaces:** Consume Tasks 1–2. `_validate_governing_binding(base, work, decision, applicability)` owns historical equality and present-vs-absent semantics; `_validated_historical_inputs` checks originals, and `_validate_governing_inputs` checks assessed freshness. The selected decision's strict non-empty shape check remains before binding. No graph imports.

- [ ] **Step 1: Append the complete tests and Git/rebinding helper.** Snapshot decision bytes before temporary-test-repository fixture commits that change assessed inputs. Regenerate applicability→WorkOrder→Run digests. Reset claimed artifacts only for the successful new dispatch, never to rewrite a historical Outcome.

```python

def _ws2_reassess(root):
    records = validate_run(root, RUN_REF)
    original = records["decision"]["governing_inputs"]
    (root / "docs/spec.md").write_text("approved requirements, clarified\n")
    subprocess.run(["git", "-C", str(root), "add", "docs/spec.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "clarify governing input"],
        check=True,
    )
    assessed = [{
        "ref": "docs/spec.md",
        "digest": hashlib.sha256((root / "docs/spec.md").read_bytes()).hexdigest(),
    }]
    app, work = records["applicability"], records["workorder"]
    app.update(original_governing_inputs=original, governing_inputs=assessed)
    work["governing_inputs"] = assessed
    _ws2_rebind(root, applicability=app, work=work)
    return original, assessed


def test_ws2_reassessment_preserves_immutable_original(tmp_path):
    fixture(tmp_path, decision_run="original")
    _reset_to_unclaimed(tmp_path)
    path = tmp_path / ".kapisch/runs/original/decisions/d1.json"
    before = path.read_bytes()
    original, assessed = _ws2_reassess(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    assert original != assessed
    assert records["decision"]["governing_inputs"] == original
    assert records["applicability"]["original_governing_inputs"] == original
    assert records["applicability"]["governing_inputs"] == assessed
    assert records["workorder"]["governing_inputs"] == assessed
    assert task_contract.validate_dispatch(
        tmp_path, RUN_REF,
        capabilities={"write": {"status": "supported", "reason": "reassessment"}},
        canonical_implementer_available=False,
    )["decision"]["governing_inputs"] == original
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


@_params(("snapshot", "message"), [
    (None, "invalid historical governing inputs"),
    ([], "work order requires governing Git inputs"),
    ({}, "invalid historical governing inputs"),
    ([None], "malformed governing Git input"),
    ([{"ref": "docs/spec.md"}], "malformed governing Git input"),
    ([{"ref": "../spec.md", "digest": "0" * 64}], "malformed governing Git input"),
    ([{"ref": "docs/spec.md", "digest": None}], "malformed governing Git input"),
    ([{"ref": "docs/spec.md", "digest": "A" * 64}], "malformed governing Git input"),
    ([{"ref": "docs/spec.md", "digest": "0" * 64, "extra": 1}],
     "malformed governing Git input"),
    ([{"ref": "docs/spec.md", "digest": "0" * 64}] * 2,
     "duplicate governing Git input"),
    ("__omit__", "invalid historical governing inputs"),
])
def test_ws2_equal_malformed_historical_snapshots_rejected(
    tmp_path, snapshot, message
):
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
        "malformed governing Git input" if snapshot == [None]
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
        # A historical comparison may match []; this does not authorize a WorkOrder.
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
```

- [ ] **Step 2: Prove red.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k 'ws2_reassessment or ws2_equal_malformed or ws2_present_invalid or ws2_empty_original or ws2_present_empty' -q`

Actual revision-2 focused red: exit 1, **6 failed, 1 passed, 77 deselected**.

- [ ] **Step 3: Implement historical/assessed binding.** Task 1 already installed both shape validators; do not rewrite them or tighten historical data to current WorkOrder policy. Replace only `core/kapisch_core/_task_authority.py` with this complete version. Present-empty originals are compared exactly; absence still binds assessed inputs directly to the original. Selected empty-input decisions remain ineligible before this helper runs.

```python
"""Validate persisted task authority and WorkOrder applicability."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ._task_artifacts import (
    ContractError,
    _load,
    _required_id,
    _required_text,
)
from ._task_decisions import _load_decision, _validated_historical_inputs
from ._task_governing_inputs import (
    _validate_governing_inputs,
    _validated_governing_inputs,
)


_ORIGINAL_GOVERNING_INPUTS = "original_governing_inputs"
_APPLICABILITY_CONTROL_FIELDS = ("result", "reason")
_APPLICABILITY_RESULTS = frozenset({
    "applicable", "not_applicable", "ambiguous", "reassessment_required",
})
_APPLICABILITY_BINDING_FIELDS = (
    "decision_id", "decision_ref", "decision_digest", "answer_digest",
    "subject", "scope", "governing_inputs",
)
_APPLICABILITY_DIAGNOSTICS = {
    "invalid_result": "invalid decision applicability result",
    **{result: f"decision applicability result is {result}"
       for result in _APPLICABILITY_RESULTS if result != "applicable"},
}


def _validate_applicability(
    applicability: dict[str, Any],
    work: dict[str, Any],
    decision: dict[str, Any],
    decision_digest: str,
) -> None:
    result_field, reason_field = _APPLICABILITY_CONTROL_FIELDS
    result = applicability.get(result_field)
    if not isinstance(result, str) or result not in _APPLICABILITY_RESULTS:
        raise ContractError(_APPLICABILITY_DIAGNOSTICS["invalid_result"])
    if result != "applicable":
        raise ContractError(_APPLICABILITY_DIAGNOSTICS[result])
    try:
        answer_bytes = decision["answer"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    answer_digest = hashlib.sha256(answer_bytes).hexdigest()
    expected_values = (
        ("decision_id", decision["decision_id"]),
        ("decision_ref", work["decision_ref"]),
        ("decision_digest", decision_digest),
        ("answer_digest", answer_digest),
        ("subject", work["subject"]),
        ("scope", work["scope"]),
        ("governing_inputs", work["governing_inputs"]),
    )
    expected = dict(expected_values)
    if any(applicability.get(key) != expected[key] for key in _APPLICABILITY_BINDING_FIELDS):
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )
    reason = applicability.get(reason_field)
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )


def _validate_governing_binding(
    base: Path,
    work: dict[str, Any],
    decision: dict[str, Any],
    applicability: dict[str, Any],
) -> None:
    historical = decision["governing_inputs"]
    if _ORIGINAL_GOVERNING_INPUTS in applicability:
        original = applicability[_ORIGINAL_GOVERNING_INPUTS]
        _validated_historical_inputs(original)
        if original != historical:
            raise ContractError("original governing inputs mismatch")
    elif work.get("governing_inputs") != historical:
        raise ContractError("governing inputs require reassessment")
    _validate_governing_inputs(base, work.get("governing_inputs"))


def _validate_workorder(
    base: Path, run_directory: str, work: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_ref = _required_text(work, "decision_ref", "decision reference")
    decision_digest = _required_text(work, "decision_digest", "decision digest")
    decision = _load_decision(base, decision_ref, decision_digest)
    _validated_governing_inputs(decision["governing_inputs"])
    decision_id = decision["decision_id"]
    if work.get("decision_id") != decision_id:
        raise ContractError("decision reference mismatch")
    if (
        decision["decision_type"] != "approval"
        or decision["subject"] != work.get("subject")
        or decision["scope"] != work.get("scope")
    ):
        raise ContractError("work order is not authorized")
    if "tasks" in work:
        raise ContractError("work order must contain exactly one task")
    task = work.get("task")
    if not isinstance(task, dict):
        raise ContractError("work order must contain one task")
    _required_id(task, "task_id", "task identity")
    _required_id(work, "workorder_id", "work order identity")
    acceptance = work.get("acceptance_criteria")
    if (
        not isinstance(acceptance, list)
        or not acceptance
        or not all(isinstance(item, str) and item.strip() for item in acceptance)
    ):
        raise ContractError("invalid WorkOrder acceptance criteria")
    if not isinstance(work.get("required_capabilities"), list) or not all(
        isinstance(item, str) and item for item in work["required_capabilities"]
    ):
        raise ContractError("invalid required capabilities")
    applicability_ref = _required_text(
        work, "applicability_ref", "applicability reference"
    )
    applicability_digest = _required_text(
        work, "applicability_digest", "applicability digest"
    )
    if applicability_ref != run_directory + "/applicability.json":
        raise ContractError("Applicability reference is outside its Run")
    applicability = _load(base, applicability_ref, applicability_digest)
    _validate_governing_binding(base, work, decision, applicability)
    _validate_applicability(applicability, work, decision, decision_digest)
    route = _required_text(work, "worker_route", "worker route")
    role = _required_text(work, "worker_role", "worker role")
    if route == "host_native_fallback":
        fallback_reason = applicability.get("fallback_authorization_reason")
        if (
            role != "worker"
            or work.get("canonical_implementer_available") is not False
            or applicability.get("host_native_fallback_authorized") is not True
            or not isinstance(fallback_reason, str)
            or not fallback_reason.strip()
        ):
            raise ContractError(
                "host-native fallback is not authorized or canonical implementer is available"
            )
    elif route == "canonical_implementer":
        if (
            role != "implementer"
            or work.get("canonical_implementer_available") is not True
        ):
            raise ContractError("canonical implementer route is not available")
    else:
        raise ContractError("unsupported worker route")
    return decision, applicability
```

- [ ] **Step 4: Verify focused green.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k 'ws2_reassessment or ws2_equal_malformed or ws2_present_invalid or ws2_empty_original or ws2_present_empty' -q`

Actual revision-2 focused green: exit 0, **7 passed, 77 deselected**.

- [ ] **Step 5: Keep all current freshness and authority tests green.**

Run: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_task_contract.py`

Actual revision-2 task-contract unittest: exit 0, **189 tests, OK**.

- [ ] **Step 6: Review the uncommitted working-tree checkpoint.** Save a stash-free per-task evidence file outside the repository, for example `$EVIDENCE/task3-working-tree.patch`, using `git diff --binary -- <this task's tracked paths>`. Append every new file in this task with `git diff --no-index --binary -- /dev/null <new-file>` (exit 1 means differences, not failure). These are working-tree checkpoint patches, not BASE..HEAD packages or instructions to change HEAD. Have the task reviewer inspect the patch plus full new-file content and test logs. Leave all changes uncommitted. The final reviewer reviews the cumulative working-tree diff, including every untracked file in scope; do not rely on per-task history.

### Task 4: Validated persisted supersession graph

**Files:** Create `core/kapisch_core/_task_supersession.py`; append tests to `tests/core/test_task_contract.py`. Do not make decision loading or `_validate_workorder` call graph validation.

**Interfaces:** Consume `_read_decision_record`, `_DecisionRecord`, `_validate_decision_path` and the strict shared parser. Produce `_scan_decisions(root) -> dict[str, _DecisionRecord]`, `_validate_supersession_graph(root, records=None) -> frozenset[str]` and `_validate_decision_eligibility(root, decision_id, records=None)`. The optional mapping is invocation-local; omitted means one fresh scan. `_validate_acyclic` is iterative integrity validation, not an execution graph subsystem. One identity lookup, one reference lookup and forward-edge adjacency replace per-node enumeration/reads; cycle policy precedes edge hash comparisons.

- [ ] **Step 1: Append complete graph fixtures/tests.** d2/d3 have distinct IDs and question IDs; duplicate identity is deliberate only in its rejection test. Self/cycle records use syntactically valid zero hashes and assert exact structural diagnostics, avoiding impossible mutually consistent hashes. Existing non-approval types are well-formed graph records but cannot authorize a selected WorkOrder (Task 1).

```python

def _ws2_edge(root, decision_id):
    run = "r1" if decision_id == "d1" else "graph"
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
    ref = f".kapisch/runs/graph/decisions/{decision_id}.json"
    _ws2_put(root, ref, record)
    return ref


def _ws2_graph(root):
    from kapisch_core._task_supersession import _validate_supersession_graph

    return _validate_supersession_graph(root)


def test_ws2_graph_transitive_different_question_non_revival(tmp_path):
    fixture(tmp_path)
    assert _ws2_graph(tmp_path) == frozenset()
    _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    assert _ws2_graph(tmp_path) == frozenset({"d1"})
    _ws2_add_decision(tmp_path, "d3", supersedes=[_ws2_edge(tmp_path, "d2")])
    assert _ws2_graph(tmp_path) == frozenset({"d1", "d2"})


@_params(("value", "message"), [
    (None, "invalid decision supersedes"),
    ([], "invalid decision supersedes"),
    ({}, "invalid decision supersedes"),
    ([None], "invalid supersedes entry"),
    ([{}], "invalid supersedes entry"),
    ([{"decision_id": "d1", "decision_ref": "docs/d1.json",
       "decision_digest": "0" * 64}], "malformed decision reference"),
    ([{"decision_id": [], "decision_ref": ".kapisch/runs/r1/decisions/d1.json",
       "decision_digest": "0" * 64}], "invalid supersedes decision identity"),
    ([{"decision_id": "d1", "decision_ref": ".kapisch/runs/r1/decisions/d1.json",
       "decision_digest": []}], "invalid supersedes decision digest"),
])
def test_ws2_graph_edge_schema(tmp_path, value, message):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record["supersedes"] = value
    _ws2_put(tmp_path, ref, record)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        _ws2_graph(tmp_path)


@_params(("variant", "message"), [
    ("extra", "invalid supersedes entry"),
    ("duplicate", "duplicate supersedes target"),
    ("missing", "supersedes target is missing"),
    ("identity", "supersedes target identity mismatch"),
    ("digest", "artifact digest mismatch: .kapisch/runs/r1/decisions/d1.json"),
])
def test_ws2_graph_invalid_target_binding(tmp_path, variant, message):
    fixture(tmp_path)
    edge = _ws2_edge(tmp_path, "d1")
    edges = [edge]
    if variant == "extra":
        edge["extra"] = True
    elif variant == "duplicate":
        edges.append(dict(edge))
    elif variant == "missing":
        edge["decision_ref"] = ".kapisch/runs/absent/decisions/d1.json"
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
        record["supersedes"] = [{
            **_ws2_edge(tmp_path, "d2"), "decision_digest": "0" * 64
        }]
        message = "decision supersession cycle"
    _ws2_put(tmp_path, ref, record)
    with _raises(ContractError, match="^" + message + "$"):
        _ws2_graph(tmp_path)


@_params(("field", "value", "message"), [
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
])
def test_ws2_graph_validates_unconnected_decision(tmp_path, field, value, message):
    fixture(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record[field] = value
    _ws2_put(tmp_path, ref, record)
    with _raises(ContractError, match="^" + re.escape(message) + "$"):
        _ws2_graph(tmp_path)


@_params(("raw", "message"), [
    (b"{", "invalid JSON artifact: .kapisch/runs/graph/decisions/d2.json"),
    (b'{"decision_id":"d2","decision_id":"d2"}',
     "duplicate JSON object key: decision_id"),
    (b"[]", "artifact must be an object: .kapisch/runs/graph/decisions/d2.json"),
])
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
    _ws2_put(tmp_path, ".kapisch/runs/graph/decisions/d1.json", record)
    with _raises(ContractError, match=(
        "^decision identity is not unique or reference mismatches$"
    )):
        _ws2_graph(tmp_path)


@_params("decision_type", [
    "answer", "correction", "risk_acceptance", "external_effect_authorization"
])
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
    ref3 = ".kapisch/runs/graph/decisions/d3.json"
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
        _ws2_add_decision(tmp_path, identity, supersedes=[_ws2_edge(tmp_path, previous)])
        previous = identity
    expected = set(tmp_path.glob(".kapisch/runs/*/decisions/*.json"))
    reads, globs = Counter(), []
    read_bytes, glob = Path.read_bytes, Path.glob

    def counted_read(path):
        if path in expected:
            reads[path] += 1
        return read_bytes(path)

    def counted_glob(path, pattern):
        if pattern == ".kapisch/runs/*/decisions/*.json":
            globs.append(pattern)
        return glob(path, pattern)

    with mock.patch.object(Path, "read_bytes", counted_read), mock.patch.object(Path, "glob", counted_glob):
        assert _ws2_graph(tmp_path) == frozenset(f"d{i}" for i in range(1, 13))
    assert reads == Counter({path: 1 for path in expected})
    assert len(globs) == 1
```

- [ ] **Step 2: Prove red.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k ws2_graph -q`

Actual revision-2 focused red: exit 1, **11 failed, 84 deselected**.

- [ ] **Step 3: Create the complete graph validator.** Every enumerated HumanDecision validates, even without edges. Shared local loading never imports this module. Edge hashes are verified with the existing primitive after structural integrity succeeds.

```python
"""Dispatch-only validation of explicit persisted decision supersession."""

from __future__ import annotations

import heapq
from pathlib import Path
from typing import Any

from ._task_artifacts import ContractError, _DIGEST, _required_id
from ._task_decisions import (
    _DecisionRecord, _read_decision_record, _validate_decision_path,
)


_SUPERSEDES_FIELDS = frozenset({"decision_id", "decision_ref", "decision_digest"})


def _supersedes_entries(root: Path, decision: dict[str, Any]) -> list[dict[str, str]]:
    if "supersedes" not in decision:
        return []
    entries = decision["supersedes"]
    if not isinstance(entries, list) or not entries:
        raise ContractError("invalid decision supersedes")
    ids, refs = set(), set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _SUPERSEDES_FIELDS:
            raise ContractError("invalid supersedes entry")
        identity = _required_id(entry, "decision_id", "supersedes decision identity")
        ref = entry["decision_ref"]
        _validate_decision_path(root, ref)
        digest = entry["decision_digest"]
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ContractError("invalid supersedes decision digest")
        if identity in ids or ref in refs:
            raise ContractError("duplicate supersedes target")
        ids.add(identity)
        refs.add(ref)
    return entries


def _validate_acyclic(edges: dict[str, list[str]]) -> None:
    incoming = dict.fromkeys(edges, 0)
    for targets in edges.values():
        for target in targets:
            incoming[target] += 1
    ready = [identity for identity, count in incoming.items() if count == 0]
    heapq.heapify(ready)
    visited = 0
    while ready:
        identity = heapq.heappop(ready)
        visited += 1
        for target in edges[identity]:
            incoming[target] -= 1
            if incoming[target] == 0:
                heapq.heappush(ready, target)
    if visited != len(edges):
        raise ContractError("decision supersession cycle")


_SUPERSESSION_DIAGNOSTICS = {
    "missing_target": "supersedes target is missing",
    "superseded": "decision is superseded",
}


def _scan_decisions(root: Path) -> dict[str, _DecisionRecord]:
    """One invocation-local byte/parse snapshot, never persisted or cached."""
    records = {}
    identities = {}
    for path in sorted(root.glob(".kapisch/runs/*/decisions/*.json")):
        ref = path.relative_to(root).as_posix()
        record = _read_decision_record(root, ref, require_digest=False)
        identity = record.decision["decision_id"]
        if identity in identities:
            raise ContractError("decision identity is not unique or reference mismatches")
        identities[identity] = record
        records[ref] = record
    return records


def _validate_supersession_graph(
    root: Path, records: dict[str, _DecisionRecord] | None = None,
) -> frozenset[str]:
    """Validate structure and cycles before exact-byte edge digests."""
    if records is None:
        records = _scan_decisions(root)
    identities = {r.decision["decision_id"]: r for r in records.values()}
    edges = {identity: [] for identity in identities}
    bindings = []
    for identity, record in identities.items():
        for entry in _supersedes_entries(root, record.decision):
            target_id = entry["decision_id"]
            target_ref = entry["decision_ref"]
            if target_id == identity or target_ref == record.ref:
                raise ContractError("decision cannot supersede itself")
            target = identities.get(target_id)
            if target_ref not in records:
                raise ContractError(_SUPERSESSION_DIAGNOSTICS["missing_target"])
            if target is None or target.ref != target_ref:
                raise ContractError("supersedes target identity mismatch")
            edges[identity].append(target_id)
            bindings.append((entry, target))
    _validate_acyclic(edges)
    for entry, target in bindings:
        if entry["decision_digest"] != target.digest:
            raise ContractError(f"artifact digest mismatch: {target.ref}")
    return frozenset(target for targets in edges.values() for target in targets)


def _validate_decision_eligibility(
    root: Path, decision_id: str,
    records: dict[str, _DecisionRecord] | None = None,
) -> None:
    if decision_id in _validate_supersession_graph(root, records):
        raise ContractError(f"{_SUPERSESSION_DIAGNOSTICS['superseded']}: {decision_id}")
```

- [ ] **Step 4: Verify focused green.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k ws2_graph -q`

Actual revision-2 focused green: exit 0, **11 passed, 84 deselected**.

- [ ] **Step 5: Run the whole task-contract suite.**

Run: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_task_contract.py`

Actual revision-2 task-contract unittest: exit 0, **229 tests, OK**.

- [ ] **Step 6: Review the uncommitted working-tree checkpoint.** Save a stash-free per-task evidence file outside the repository, for example `$EVIDENCE/task4-working-tree.patch`, using `git diff --binary -- <this task's tracked paths>`. Append every new file in this task with `git diff --no-index --binary -- /dev/null <new-file>` (exit 1 means differences, not failure). These are working-tree checkpoint patches, not BASE..HEAD packages or instructions to change HEAD. Have the task reviewer inspect the patch plus full new-file content and test logs. Leave all changes uncommitted. The final reviewer reviews the cumulative working-tree diff, including every untracked file in scope; do not rely on per-task history.

### Task 5: Dispatch-only eligibility, historical Outcomes and source attribution

**Files:** Modify `core/kapisch_core/task_contract.py` and private `_validate_workorder` in `core/kapisch_core/_task_authority.py`; append tests to `tests/core/test_task_contract.py`. Retain claim_dispatch delegation before mutation and all acceptance/Outcome logic.

**Interfaces:** Consume Task 4's invocation-local snapshot and eligibility APIs. Private `_validate_run` and `_validate_workorder` explicitly receive the snapshot; public `validate_run` retains its API/local-only behavior and acceptance/Outcome callers are unchanged. No public bypass parameter, Outcome fields, durable index or ambient cache is introduced. `_ws2_persist_outcome` uses the real existing persistence recipe.

- [ ] **Step 1: Append complete lifecycle/restart/attribution tests.** Reset dispatch fixtures before adding superseders. Never reset completed historical Runs: create a separate ready r2 consumer referencing the same original decision, proving dispatch failure without mutating history. Assert exact errors, both entry points, fresh interpreters and prior artifact bytes.

```python

_WS2_CAPABILITIES = {"write": {"status": "supported", "reason": "test adapter"}}


def _ws2_restart(root, operation, run_ref=RUN_REF):
    script = '''
import json, sys
from kapisch_core import task_contract
kwargs = {"capabilities": {"write": {"status": "supported", "reason": "restart"}}}
if sys.argv[3] in {"validate_dispatch", "claim_dispatch"}:
    kwargs["canonical_implementer_available"] = False
try:
    result = getattr(task_contract, sys.argv[3])(sys.argv[1], sys.argv[2], **kwargs)
except task_contract.ContractError as exc:
    result = {"error": str(exc)}
print(json.dumps(result, sort_keys=True))
'''
    result = subprocess.run(
        [sys.executable, "-c", script, str(root), run_ref, operation],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def _ws2_snapshot(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in (root / ".kapisch").rglob("*") if path.is_file()
    }


def _ws2_persist_outcome(root):
    outcome = validate_acceptance(root, RUN_REF, capabilities=_WS2_CAPABILITIES)
    outcome_ref = f"{RUN_DIR}/outcome.json"
    digest = _ws2_put(root, outcome_ref, outcome)
    run = json.loads((root / RUN_REF).read_text())
    run.update(outcome_ref=outcome_ref, outcome_digest=digest)
    _ws2_put(root, RUN_REF, run)
    return outcome


def _ws2_new_ready_consumer(root):
    source_run = json.loads((root / RUN_REF).read_text())
    work = json.loads((root / source_run["workorder_ref"]).read_text())
    app = json.loads((root / work["applicability_ref"]).read_text())
    directory = ".kapisch/runs/r2"
    work.update(workorder_id="w2", applicability_ref=directory + "/applicability.json")
    work["applicability_digest"] = _ws2_put(root, work["applicability_ref"], app)
    work_ref = directory + "/workorder.json"
    work_digest = _ws2_put(root, work_ref, work)
    run_ref = directory + "/run.json"
    _ws2_put(root, run_ref, {
        "run_id": "r2", "dispatch_state": "ready",
        "workorder_ref": work_ref, "workorder_digest": work_digest,
        "attempt_allocation": {
            "attempt_id": "a2", "output_ref": directory + "/attempts/a2-output.json"
        },
    })
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
            tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
            canonical_implementer_available=False,
        )
    assert _ws2_restart(tmp_path, operation) == {"error": "decision is superseded: d1"}
    assert _ws2_snapshot(tmp_path) == before
    assert not (tmp_path / RUN_DIR / "dispatch-claim.json").exists()


def test_ws2_dispatch_still_allows_original_and_new_superseder(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    result = task_contract.validate_dispatch(
        tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )
    assert result["decision"]["decision_id"] == "d1"
    ref = _ws2_add_decision(tmp_path, "d2", supersedes=[_ws2_edge(tmp_path, "d1")])
    decision = json.loads((tmp_path / ref).read_text())
    work = validate_run(tmp_path, RUN_REF)["workorder"]
    work.update(decision_id="d2", decision_ref=ref,
                decision_digest=hashlib.sha256((tmp_path / ref).read_bytes()).hexdigest())
    _ws2_rebind(tmp_path, work=work)
    assert task_contract.claim_dispatch(
        tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )["decision"] == decision


@_params(("later", "message"), [
    ("valid", "decision is superseded: d1"),
    ("invalid_json", "invalid JSON artifact: .kapisch/runs/graph/decisions/d2.json"),
    ("duplicate_keys", "duplicate JSON object key: decision_id"),
    ("invalid_record", "invalid decision question identity"),
    ("invalid_edges", "invalid decision supersedes"),
])
def test_ws2_completed_outcome_ignores_later_graph_but_dispatch_fails_closed(
    tmp_path, later, message
):
    fixture(tmp_path)
    expected = _ws2_persist_outcome(tmp_path)
    consumer = _ws2_new_ready_consumer(tmp_path)
    before = _ws2_snapshot(tmp_path)
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
    assert validate_acceptance(
        tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES
    ) == expected
    assert task_contract.validate_outcome(
        tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES
    ) == expected
    assert _ws2_restart(tmp_path, "validate_outcome") == expected
    for operation in ("validate_dispatch", "claim_dispatch"):
        with _raises(ContractError, match="^" + re.escape(message) + "$"):
            getattr(task_contract, operation)(
                tmp_path, consumer, capabilities=_WS2_CAPABILITIES,
                canonical_implementer_available=False,
            )
        assert _ws2_restart(tmp_path, operation, consumer) == {"error": message}
    for ref, raw in before.items():
        assert (tmp_path / ref).read_bytes() == raw


@_params("source_kind", ["external_artifact", "operator_reported_external"])
def test_ws2_external_cross_run_source_attribution(tmp_path, source_kind):
    source = "records/operator-approval.md"
    fixture(tmp_path, decision_run="original", source_kind=source_kind, source_ref=source)
    original_ref = ".kapisch/runs/original/decisions/d1.json"
    original = (tmp_path / original_ref).read_bytes()
    expected = _ws2_persist_outcome(tmp_path)
    assert expected["decision"]["ref"] == original_ref
    assert expected["decision"]["decision_id"] == "d1"
    assert expected["decision"]["source_kind"] == source_kind
    assert "source_ref" not in expected["decision"]  # No Outcome schema expansion.
    records = validate_run(tmp_path, RUN_REF)
    assert records["decision"]["source_ref"] == source
    assert json.loads((tmp_path / expected["decision"]["ref"]).read_text())["source_ref"] == source
    assert _ws2_restart(tmp_path, "validate_outcome") == expected
    assert (tmp_path / original_ref).read_bytes() == original
    assert not (tmp_path / RUN_DIR / "decisions/d1.json").exists()



def test_ws2_dispatch_accepts_unrelated_empty_historical_inputs(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    record = json.loads((tmp_path / ref).read_text())
    record["governing_inputs"] = []
    _ws2_put(tmp_path, ref, record)
    assert task_contract.validate_dispatch(
        tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
        canonical_implementer_available=False,
    )["decision"]["decision_id"] == "d1"


def test_ws2_dispatch_reads_each_decision_once_per_call(tmp_path):
    from collections import Counter
    from pathlib import Path

    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    for number in range(2, 10):
        _ws2_add_decision(tmp_path, f"d{number}")
    expected = set(tmp_path.glob(".kapisch/runs/*/decisions/*.json"))
    reads, globs = Counter(), []
    read_bytes, glob = Path.read_bytes, Path.glob

    def counted_read(path):
        if path in expected:
            reads[path] += 1
        return read_bytes(path)

    def counted_glob(path, pattern):
        if pattern == ".kapisch/runs/*/decisions/*.json":
            globs.append(pattern)
        return glob(path, pattern)

    with mock.patch.object(Path, "read_bytes", counted_read), mock.patch.object(Path, "glob", counted_glob):
        for invocation in (1, 2):
            task_contract.validate_dispatch(tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
                              canonical_implementer_available=False)
            assert reads == Counter({path: invocation for path in expected})
            assert len(globs) == invocation  # No cross-call cache, including selected d1.


@_params("supersedes", [False, True])
def test_ws2_missing_retained_reference_fails_closed_after_restart(tmp_path, supersedes):
    fixture(tmp_path, decision_run="origin")
    _reset_to_unclaimed(tmp_path)
    records = validate_run(tmp_path, RUN_REF)
    ref = records["workorder"]["decision_ref"]
    if supersedes:
        edge = {"decision_id": "d1", "decision_ref": ref,
                "decision_digest": records["workorder"]["decision_digest"]}
        _ws2_add_decision(tmp_path, "d2", supersedes=[edge])
        # Reference d2 as the selected authority, retaining its edge to d1.
        d2_ref = ".kapisch/runs/graph/decisions/d2.json"
        decision = json.loads((tmp_path / d2_ref).read_text())
        work, app = records["workorder"], records["applicability"]
        digest = hashlib.sha256((tmp_path / d2_ref).read_bytes()).hexdigest()
        for record in (work, app):
            record.update(decision_id="d2", decision_ref=d2_ref, decision_digest=digest)
        _ws2_rebind(tmp_path, work=work, applicability=app)
    # Archive, never delete, the original file; consumers still reference its old path.
    archive = tmp_path / "archived-decisions"
    archive.mkdir()
    (tmp_path / ref).rename(archive / "d1.json")
    expected = "supersedes target is missing" if supersedes else "missing referenced decision"
    assert _ws2_restart(tmp_path, "validate_dispatch")["error"] == expected


def test_ws2_kernel_never_mutates_any_decision_file(tmp_path):
    fixture(tmp_path)
    _reset_to_unclaimed(tmp_path)
    ref = _ws2_add_decision(tmp_path, "d2")
    before = {p: p.read_bytes() for p in tmp_path.glob(".kapisch/runs/*/decisions/*.json")}
    task_contract.validate_dispatch(tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
                      canonical_implementer_available=False)
    assert {p: p.read_bytes() for p in before} == before
    record = json.loads((tmp_path / ref).read_text())
    record["supersedes"] = [_ws2_edge(tmp_path, "d1")]
    _ws2_put(tmp_path, ref, record)  # Human-boundary fixture, not a kernel mutation.
    before = {p: p.read_bytes() for p in before}
    with _raises(ContractError, match="^decision is superseded: d1$"):
        task_contract.validate_dispatch(tmp_path, RUN_REF, capabilities=_WS2_CAPABILITIES,
                          canonical_implementer_available=False)
    assert {p: p.read_bytes() for p in before} == before
```

- [ ] **Step 2: Prove red.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k 'ws2_dispatch or ws2_completed or ws2_external or ws2_missing_retained or ws2_kernel_never' -q`

Actual revision-2 focused red: exit 1, **5 failed, 3 passed, 95 deselected**.

- [ ] **Step 3: Thread the invocation-local snapshot through private helpers.** Replace `core/kapisch_core/_task_authority.py` with this complete version (only `_DecisionRecord` import, private parameter and forwarding change since Task 3):

```python
"""Validate persisted task authority and WorkOrder applicability."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ._task_artifacts import (
    ContractError,
    _load,
    _required_id,
    _required_text,
)
from ._task_decisions import _DecisionRecord, _load_decision, _validated_historical_inputs
from ._task_governing_inputs import (
    _validate_governing_inputs,
    _validated_governing_inputs,
)


_ORIGINAL_GOVERNING_INPUTS = "original_governing_inputs"
_APPLICABILITY_CONTROL_FIELDS = ("result", "reason")
_APPLICABILITY_RESULTS = frozenset({
    "applicable", "not_applicable", "ambiguous", "reassessment_required",
})
_APPLICABILITY_BINDING_FIELDS = (
    "decision_id", "decision_ref", "decision_digest", "answer_digest",
    "subject", "scope", "governing_inputs",
)
_APPLICABILITY_DIAGNOSTICS = {
    "invalid_result": "invalid decision applicability result",
    **{result: f"decision applicability result is {result}"
       for result in _APPLICABILITY_RESULTS if result != "applicable"},
}


def _validate_applicability(
    applicability: dict[str, Any],
    work: dict[str, Any],
    decision: dict[str, Any],
    decision_digest: str,
) -> None:
    result_field, reason_field = _APPLICABILITY_CONTROL_FIELDS
    result = applicability.get(result_field)
    if not isinstance(result, str) or result not in _APPLICABILITY_RESULTS:
        raise ContractError(_APPLICABILITY_DIAGNOSTICS["invalid_result"])
    if result != "applicable":
        raise ContractError(_APPLICABILITY_DIAGNOSTICS[result])
    try:
        answer_bytes = decision["answer"].encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractError("decision answer is not valid UTF-8") from exc
    answer_digest = hashlib.sha256(answer_bytes).hexdigest()
    expected_values = (
        ("decision_id", decision["decision_id"]),
        ("decision_ref", work["decision_ref"]),
        ("decision_digest", decision_digest),
        ("answer_digest", answer_digest),
        ("subject", work["subject"]),
        ("scope", work["scope"]),
        ("governing_inputs", work["governing_inputs"]),
    )
    expected = dict(expected_values)
    if any(applicability.get(key) != expected[key] for key in _APPLICABILITY_BINDING_FIELDS):
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )
    reason = applicability.get(reason_field)
    if not isinstance(reason, str) or not reason.strip():
        raise ContractError(
            "decision applicability is missing, stale, or not applicable"
        )


def _validate_governing_binding(
    base: Path,
    work: dict[str, Any],
    decision: dict[str, Any],
    applicability: dict[str, Any],
) -> None:
    historical = decision["governing_inputs"]
    if _ORIGINAL_GOVERNING_INPUTS in applicability:
        original = applicability[_ORIGINAL_GOVERNING_INPUTS]
        _validated_historical_inputs(original)
        if original != historical:
            raise ContractError("original governing inputs mismatch")
    elif work.get("governing_inputs") != historical:
        raise ContractError("governing inputs require reassessment")
    _validate_governing_inputs(base, work.get("governing_inputs"))


def _validate_workorder(
    base: Path, run_directory: str, work: dict[str, Any],
    decision_records: dict[str, _DecisionRecord] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_ref = _required_text(work, "decision_ref", "decision reference")
    decision_digest = _required_text(work, "decision_digest", "decision digest")
    decision = _load_decision(base, decision_ref, decision_digest, records=decision_records)
    _validated_governing_inputs(decision["governing_inputs"])
    decision_id = decision["decision_id"]
    if work.get("decision_id") != decision_id:
        raise ContractError("decision reference mismatch")
    if (
        decision["decision_type"] != "approval"
        or decision["subject"] != work.get("subject")
        or decision["scope"] != work.get("scope")
    ):
        raise ContractError("work order is not authorized")
    if "tasks" in work:
        raise ContractError("work order must contain exactly one task")
    task = work.get("task")
    if not isinstance(task, dict):
        raise ContractError("work order must contain one task")
    _required_id(task, "task_id", "task identity")
    _required_id(work, "workorder_id", "work order identity")
    acceptance = work.get("acceptance_criteria")
    if (
        not isinstance(acceptance, list)
        or not acceptance
        or not all(isinstance(item, str) and item.strip() for item in acceptance)
    ):
        raise ContractError("invalid WorkOrder acceptance criteria")
    if not isinstance(work.get("required_capabilities"), list) or not all(
        isinstance(item, str) and item for item in work["required_capabilities"]
    ):
        raise ContractError("invalid required capabilities")
    applicability_ref = _required_text(
        work, "applicability_ref", "applicability reference"
    )
    applicability_digest = _required_text(
        work, "applicability_digest", "applicability digest"
    )
    if applicability_ref != run_directory + "/applicability.json":
        raise ContractError("Applicability reference is outside its Run")
    applicability = _load(base, applicability_ref, applicability_digest)
    _validate_governing_binding(base, work, decision, applicability)
    _validate_applicability(applicability, work, decision, decision_digest)
    route = _required_text(work, "worker_route", "worker route")
    role = _required_text(work, "worker_role", "worker role")
    if route == "host_native_fallback":
        fallback_reason = applicability.get("fallback_authorization_reason")
        if (
            role != "worker"
            or work.get("canonical_implementer_available") is not False
            or applicability.get("host_native_fallback_authorized") is not True
            or not isinstance(fallback_reason, str)
            or not fallback_reason.strip()
        ):
            raise ContractError(
                "host-native fallback is not authorized or canonical implementer is available"
            )
    elif route == "canonical_implementer":
        if (
            role != "implementer"
            or work.get("canonical_implementer_available") is not True
        ):
            raise ContractError("canonical implementer route is not available")
    else:
        raise ContractError("unsupported worker route")
    return decision, applicability
```

In `core/kapisch_core/task_contract.py`, add these imports beside the authority import:

```python
from ._task_decisions import _DecisionRecord
from ._task_supersession import _scan_decisions, _validate_decision_eligibility
```

Replace `validate_run` with this public wrapper and private helper. Public `validate_run` still performs local validation only; acceptance and Outcome callers never receive a global snapshot or graph check. Do not introduce module-level context, a persisted index, or an optional public validation bypass.

```python
def validate_run(
    root: str | Path, run_ref: str, run_digest: str | None = None
) -> dict[str, Any]:
    """Validate local persisted authority without a global dispatch scan."""
    return _validate_run(root, run_ref, run_digest)


def _validate_run(
    root: str | Path, run_ref: str, run_digest: str | None = None, *,
    decision_records: dict[str, _DecisionRecord] | None = None,
) -> dict[str, Any]:
    """Load persisted Run, WorkOrder, and authority evidence from disk."""
    base = _resolve(Path(root), "project root")
    run = _load(base, run_ref, run_digest, require_digest=False)
    dispatch_state = run.get("dispatch_state")
    if not isinstance(dispatch_state, str) or dispatch_state not in (
        "ready",
        "claimed",
    ):
        raise ContractError("invalid persisted dispatch state")
    run_directory = _run_directory(run, run_ref)
    workorder_ref = _required_text(run, "workorder_ref", "WorkOrder reference")
    if workorder_ref != run_directory + "/workorder.json":
        raise ContractError("WorkOrder reference is outside its canonical Run path")
    work = _load(base, workorder_ref, run.get("workorder_digest"))
    decision, applicability = _validate_workorder(base, run_directory, work, decision_records)
    return {
        "run": run,
        "workorder": work,
        "decision": decision,
        "applicability": applicability,
    }
```

Replace `validate_dispatch` with the following function. It enumerates/parses once, passes the same snapshot to the selected-decision loader, then applies graph integrity/eligibility only here. Parsing all historical records now precedes local authorization; edge structure/cycle/hash policy still runs after capabilities/readiness/allocation checks and before publication. The selected file and edge targets are never read again during the call.

```python
def validate_dispatch(
    root: str | Path,
    run_ref: str,
    *,
    capabilities: dict[str, dict[str, str]],
    canonical_implementer_available: bool,
) -> dict[str, Any]:
    """Validate durable authorization and actual adapter capabilities before start."""
    base = _resolve(Path(root), "project root")
    decision_records = _scan_decisions(base)
    records = _validate_run(base, run_ref, decision_records=decision_records)
    work = records["workorder"]
    _validate_capabilities(work, capabilities)
    if (
        type(canonical_implementer_available) is not bool
        or canonical_implementer_available
        is not work["canonical_implementer_available"]
    ):
        raise ContractError(
            "canonical implementer availability changed; reauthorize dispatch"
        )
    run = records["run"]
    base = _validate_dispatch_readiness(root, run_ref, run)
    allocation = _validate_dispatch_allocation_paths(base, run_ref, run)
    _validate_decision_eligibility(
        base, records["decision"]["decision_id"], decision_records
    )
    return {**records, "attempt_allocation": allocation}
```

- [ ] **Step 4: Verify focused green.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_task_contract.py -k 'ws2_dispatch or ws2_completed or ws2_external or ws2_missing_retained or ws2_kernel_never' -q`

Actual revision-2 focused green: exit 0, **8 passed, 95 deselected**.

- [ ] **Step 5: Verify the entire task-contract gate.**

Run: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_task_contract.py`

Actual revision-2 task-contract unittest: exit 0, **246 tests, OK**.

- [ ] **Step 6: Review the uncommitted working-tree checkpoint.** Save a stash-free per-task evidence file outside the repository, for example `$EVIDENCE/task5-working-tree.patch`, using `git diff --binary -- <this task's tracked paths>`. Append every new file in this task with `git diff --no-index --binary -- /dev/null <new-file>` (exit 1 means differences, not failure). These are working-tree checkpoint patches, not BASE..HEAD packages or instructions to change HEAD. Have the task reviewer inspect the patch plus full new-file content and test logs. Leave all changes uncommitted. The final reviewer reviews the cumulative working-tree diff, including every untracked file in scope; do not rely on per-task history.

### Task 6: Full task-first guidance, structural contract checks, and final gates

**Files:** Modify `core/contracts/task-first.md:22,39–46`; add a method to `PackageTests` in `tests/core/test_package.py:14–123`. General v3 policy files remain unchanged. Include the approved spec and plan in the final cumulative working-tree review package; do not stage them.

**Interfaces:** Consumes Tasks 1–5 diagnostics. Produces full coordinator prose and one small deterministic structural/constant-based metadata regression (no sentence assertions). No bundle input or host dependency is added.

- [ ] **Step 1: Add this complete method inside `class PackageTests(unittest.TestCase)`.** Preserve the installed-console test unchanged.

```python
    def test_task_first_decision_guidance(self) -> None:
        import json
        import re

        from kapisch_core._task_artifacts import ContractError
        from kapisch_core._task_authority import (
            _APPLICABILITY_BINDING_FIELDS, _APPLICABILITY_CONTROL_FIELDS,
            _APPLICABILITY_DIAGNOSTICS,
            _APPLICABILITY_RESULTS, _ORIGINAL_GOVERNING_INPUTS,
        )
        from kapisch_core._task_decisions import _MISSING_DECISION
        from kapisch_core._task_supersession import (
            _SUPERSEDES_FIELDS, _SUPERSESSION_DIAGNOSTICS,
        )

        text = (ROOT / "core/contracts/task-first.md").read_text()
        headings = set(re.findall(r"^#{2,3} (.+)$", text, re.MULTILINE))
        self.assertTrue({
            "Decision reuse, reassessment, and supersession",
            "Retention of cross-Run authority", "Machine-checkable decision contract",
        } <= headings)
        blocks = re.findall(
            r"<!-- ws2-decision-contract -->\s*```json\n(.*?)\n```\s*"
            r"<!-- /ws2-decision-contract -->", text, re.DOTALL,
        )
        self.assertEqual(len(blocks), 1)
        contract = json.loads(blocks[0])
        self.assertEqual(contract["applicability"], {
            "results": sorted(_APPLICABILITY_RESULTS),
            "binding_fields": list(_APPLICABILITY_BINDING_FIELDS),
            "optional_fields": [_ORIGINAL_GOVERNING_INPUTS],
            "required_fields": list(_APPLICABILITY_CONTROL_FIELDS),
        })
        self.assertEqual(contract["supersedes"]["entry_fields"], sorted(_SUPERSEDES_FIELDS))
        self.assertEqual(contract["error_classes"], [ContractError.__name__])
        self.assertEqual(contract["diagnostics"], {
            **_APPLICABILITY_DIAGNOSTICS, **_SUPERSESSION_DIAGNOSTICS,
            "missing_decision": _MISSING_DECISION,
        })
```

- [ ] **Step 2: Prove red.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_package.py::PackageTests::test_task_first_decision_guidance -q`

Actual revision-2 focused red: exit 1, **1 failed**.

- [ ] **Step 3: Replace the entire `core/contracts/task-first.md` with this exact Markdown.** Core stays host-neutral (`Harness producers`); this spec/plan owns the explicit Pi deferral.

````markdown
# Task-first single-task contract

This contract covers one persisted Run, one authorized WorkOrder containing exactly one task, one Attempt, one aggregation report, and a coordinator-produced Outcome. It does not schedule tasks, retry work, or invoke an LLM. Files are project-relative JSON references with SHA-256 digests over exact bytes.

## Portable records and authority

The canonical layout is:

```
.kapisch/runs/<run_id>/run.json
.kapisch/runs/<run_id>/workorder.json
.kapisch/runs/<run_id>/decisions/<decision_id>.json
.kapisch/runs/<run_id>/applicability.json
.kapisch/runs/<run_id>/dispatch-claim.json
.kapisch/runs/<run_id>/attempts/<attempt_id>.json
.kapisch/runs/<run_id>/aggregation.json
.kapisch/runs/<run_id>/outcome.json
```

The coordinator creates Run and WorkOrder; a new Run starts with `dispatch_state=ready`. Before start, Run records an `attempt_allocation` containing a unique attempt ID and output path. `validate_dispatch` is a read-only preflight; `claim_dispatch` revalidates, exclusively creates the fixed `dispatch-claim.json`, then atomically replaces Run with `dispatch_state=claimed` before the host adapter is invoked. The claim records `status=claimed` and binds the Run, WorkOrder reference/digest, Decision ID/digest, attempt ID, and output reference. The claimed Run state blocks redispatch if the best-effort claim is lost during an ordinary controller restart; exclusive creation also prevents concurrent claims. Neither Run replacement nor claim creation is explicitly synced to storage, so this does not guarantee survival of power loss or storage rollback. Any incomplete `claimed` Run is uncertain whether its claim or output is present or missing; absence does not prove that dispatch did not occur. Do not automatically redispatch an incomplete Run. A missing or unknown dispatch state is invalid and requires operator reconciliation. Inspect portable artifacts and actual work products; any available harness history may help a human investigate, but is optional evidence and never authority. If completion cannot be established, ask the operator to reconcile. An explicitly authorized retry uses a new Run, and uncertain external effects still require reconciliation or scoped human authorization. This slice does not automate recovery or retry. After collection, Run records the Attempt, report, and Outcome references/digests; it is not authorization. WorkOrder references one HumanDecision and exactly one task. HumanDecision is immutable and includes `decision_id`, `question_id`, original question, answer, subject, scope, decision type, source kind, optional attribution, and the governing-input ref/digest snapshot. Adapter session identifiers and host handles are adapter metadata, never portable identity. An adapter that captures a pending-request answer writes a supplied `run_id` under the portable run path; legacy requests without one stay in the adapter's session-local path.

## Decision reuse, reassessment, and supersession

Before asking the human, inspect existing HumanDecision records under `.kapisch/runs/*/decisions/`, including decisions reported from external records. The LLM coordinator decides whether subject, scope, action and the proposed work are already covered, and whether input changes are substantive. There is no kernel semantic matcher, global question index, or same-question ambiguity rule; `question_id` is an opaque non-empty string. If authorization does not cover the work or coverage is ambiguous, persist `not_applicable` or `ambiguous` and obtain a fresh HumanDecision. Never infer approval from `decision_type=approval` or agent advice.

The shared HumanDecision reader accepts `answer`, `correction`, `approval`, `risk_acceptance`, and `external_effect_authorization`; a selected WorkOrder authorizing decision must still have `decision_type=approval` and non-empty governing Git inputs. Unrelated valid decisions with empty snapshots do not block dispatch and can be supersession targets or superseders. The producer accepts optional request attribution as absent or null (omitted in emitted decisions), or a non-empty string; emitted `source_ref` and `approving_party`, when present, are non-empty strings. `external_artifact` requires `source_ref`; the producer emits no `run_id` field in the decision. A WorkOrder can reuse one original immutable decision from any Run at `.kapisch/runs/<run>/decisions/<decision_id>.json`. Never copy or re-create a decision in a consuming Run. Canonical layout, project-root confinement, exact filename and decision identity, project-wide uniqueness, exact-byte digests, and rejection of symlinked files or path components still apply. Applicability stays inside the consuming Run. External-record reuse preserves source attribution through the original decision reference and `source_kind`; `external_artifact` requires a non-empty `source_ref` in that original record. Outcome does not gain a `source_ref` field.

The coordinator persists applicability bindings to the exact decision ID/reference/digest, answer digest, WorkOrder subject/scope, and assessed `governing_inputs`, plus `result` and a non-empty `reason`. Only `applicable` authorizes work; `not_applicable`, `ambiguous`, and `reassessment_required` block with distinct errors, and unknown or malformed results are invalid. `superseded` is never a persisted applicability result: it is derived from explicit human authority by the dispatch validator.

For reassessment, keep the decision and its snapshot byte-for-byte unchanged. Persist the decision's exact original snapshot as `original_governing_inputs` in applicability and the reassessed current snapshot as `governing_inputs` in both applicability and WorkOrder; refresh applicability and WorkOrder digests in their consumers. `original_governing_inputs` is historical: both historical snapshots use the producer shape: a list (possibly empty) of exact `{ref, digest}` records, non-empty string refs and lowercase SHA-256 digests; repeated or non-Git refs are allowed historically. They must match exactly, in order; do not compare historical bytes with current Git. A present empty original snapshot is valid only when the decision snapshot is also empty. A present null, malformed, or mismatching snapshot is invalid. An empty original is not absence: presence compares the original snapshot, while absence requires assessed inputs to equal that snapshot. Selected WorkOrder authority still requires a non-empty, portable, unique governing-input snapshot in the decision and non-empty fresh Git inputs in the WorkOrder, so an empty-input decision never authorizes dispatch, even with an explicit empty original snapshot. Absence retains the #85 meaning: assessed inputs must equal the decision snapshot. Assessed inputs must still match HEAD, index and working-tree bytes. Reassessment cannot change subject, scope, or action authority. Per-task authorization and narrowing remain WS-4.

Only the human-input boundary produces `supersedes` together with a new immutable HumanDecision: the host input adapter for a pending request, or the coordinator recording a direct human prompt. A coordinator must never add inferred supersession to an existing decision. Absence means no edges; if present, `supersedes` must be a non-empty list of exact `{decision_id, decision_ref, decision_digest}` objects, with no repeated target ID or reference. Targets must exist with the stated ID and exact digest. Question IDs need not match. Self-reference and cycles are invalid; structure, target identities, self-reference and cycles are checked before target digests so cyclic invalid records need no digest fixed point to be rejected.

Supersession is prospective, transitive, and never revives an earlier target when its superseder is superseded. The global graph integrity and eligibility checks run only in `validate_dispatch` (and `claim_dispatch` through delegation), never in `validate_run`, `_validate_workorder`, acceptance, or Outcome validation. Dispatch reads every enumerated `*.json` under `.kapisch/runs/*/decisions/`, parses each HumanDecision including unconnected records exactly once per dispatch call, builds temporary identity/path/digest and forward-edge lookups, then validates the graph. The selected decision uses that same call-local byte snapshot. No persisted index or cross-call/module-level cache is used. Sorted enumeration and heap-based cycle validation cost O(N log N + E) time plus input-byte parsing, and O(N + E) auxiliary space; each file is read once. A later malformed decision file blocks dispatch but does not trigger new graph checks on an already claimed Run or completed Outcome. Graph validation and rejected dispatch are read-only; historical artifacts are not mutated or re-judged for supersession. Incomplete enumeration under arbitrary local filesystem corruption remains outside PR85-009. Existing current-input freshness checks still run at acceptance and Outcome validation; this pre-existing behavior is unchanged.

Older validators ignore `supersedes` and can still honor a superseded target: use a WS-2-capable validator before relying on this authority-bearing field. Harness producers must not emit this field until WS-11. No database, durable question index, event log, additional orchestration subsystem, or host identifier is introduced.

On task-first resume or handoff, reconstruct the original decision, current applicability, WorkOrder, Run and their exact bindings from persisted files; do not rely on conversation or copied authority. Reuse the original decision and reassess current inputs before new dispatch. A handoff or worker recommendation grants no human authority. Preserve claimed Runs and completed Outcomes; do not use supersession to authorize redispatch or to infer retry safety. The general v3 resume/handoff policies govern their separate stage-attempt lifecycle and are unchanged by this task-first addendum.

WorkOrder records one task, non-empty acceptance criteria, required capabilities, worker route/role, canonical-implementer availability, and decision/applicability refs and digests. An ordinary route requires the canonical implementer. The one-task host-native fallback is eligible only when the canonical implementer is unavailable and the persisted applicability evidence explicitly authorizes this bounded route. Do not mislabel a host-native worker as an implementer. Capability probes use `supported`, `unsupported`, or `unknown` plus a reason. Required capabilities block dispatch unless actually supported and explained; no capability is inferred or silently emulated. Call `claim_dispatch` before host start with current adapter capabilities and canonical-implementer availability; it performs the read-only `validate_dispatch` checks, then persists the one-shot claim. A `claimed` Run state, an existing claim, or any Run already carrying Attempt/report/Outcome references blocks dispatch, as do pre-existing Attempt/output files and unknown/unsupported/unproven required capabilities.

The human-input boundary is the sole HumanDecision producer: the host input adapter captures one explicit pending-request answer, while the coordinator produces one direct-prompt record. Neither path creates duplicate approval. Coordinator owns the single Attempt record and lifecycle references; worker writes only its unique output. The aggregator owns the report and binds it to the exact Attempt digest, output reference/digest, WorkOrder, Decision, task coverage, and acceptance criteria. It records `failures`, `conflicts`, `missing_references`, and `unresolved_issues` as explicit empty arrays for a successful result; omitted arrays do not count as empty. Coordinator validates all records and publishes Outcome only for one successful attempt and a complete valid report. Optional advisory review is findings-only: its coordinator-owned status is carried into Outcome but never gates acceptance or grants authority. Outcome grants no external-effect permission.

### Retention of cross-Run authority

A referenced HumanDecision and every decision in its `supersedes` chain must remain retained and byte-for-byte unmodified for as long as any Run or WorkOrder references it. Moving or archiving a Run directory that contains a still-referenced decision breaks cold-restart validation: missing selected decisions fail closed with `missing referenced decision`; missing chain targets fail closed with `supersedes target is missing`. The kernel never rewrites, archives or deletes decision files. Superseding decisions must also be retained. Supersession is derived at dispatch from the persisted superseder; deleting a superseder can make an older superseded decision eligible again, even when nothing references the superseder. Until a future retention/GC policy is approved, do not delete any HumanDecision record, including an apparently unreferenced superseder. Retention policy and garbage collection are out of scope and owner-decided; do not assume that a completed Run makes its decision safe to remove.

### Machine-checkable decision contract

The stable block label and field names below are contract metadata, not prose assertions. Diagnostics list kernel-owned stable errors; the `superseded` diagnostic is the prefix before the decision ID. `ContractError` is the existing public error class, not a new exception type.

<!-- ws2-decision-contract -->
```json
{
  "applicability": {
    "results": [
      "ambiguous",
      "applicable",
      "not_applicable",
      "reassessment_required"
    ],
    "binding_fields": [
      "decision_id",
      "decision_ref",
      "decision_digest",
      "answer_digest",
      "subject",
      "scope",
      "governing_inputs"
    ],
    "optional_fields": [
      "original_governing_inputs"
    ],
    "required_fields": [
      "result",
      "reason"
    ]
  },
  "supersedes": {
    "entry_fields": [
      "decision_digest",
      "decision_id",
      "decision_ref"
    ]
  },
  "error_classes": [
    "ContractError"
  ],
  "diagnostics": {
    "invalid_result": "invalid decision applicability result",
    "ambiguous": "decision applicability result is ambiguous",
    "not_applicable": "decision applicability result is not_applicable",
    "reassessment_required": "decision applicability result is reassessment_required",
    "missing_target": "supersedes target is missing",
    "superseded": "decision is superseded",
    "missing_decision": "missing referenced decision"
  }
}
```
<!-- /ws2-decision-contract -->

## Required record fields

Keys are literal. Missing, mistyped, or contradictory keys fail closed, and
unknown extra keys are ignored except where noted. The dispatch claim and the
Outcome are compared for exact equality, so they must contain exactly the
listed keys.

- **Run:** `run_id`, `workorder_ref`, `workorder_digest`, `dispatch_state`
  (`ready` before dispatch, `claimed` once consumed), `attempt_allocation`
  (`attempt_id`, `output_ref`); optional `advisory_review`; after collection `attempt_ref`,
  `attempt_digest`, `aggregation_ref`, `aggregation_digest`; after publication
  `outcome_ref`, `outcome_digest`.
- **HumanDecision:** `decision_id`, `question_id`, `question`, `answer`,
  `subject`, `scope`, `decision_type`, `source_kind`, `governing_inputs`;
  `source_ref` is required for `external_artifact`; optional `supersedes` follows
  the exact edge schema above.
- **Applicability:** `decision_id`, `decision_ref`, `decision_digest`,
  `answer_digest`, `subject`, `scope`, `governing_inputs`, `result`, `reason`;
  optional `original_governing_inputs` carries the historical snapshot,
  plus `host_native_fallback_authorized` and `fallback_authorization_reason`
  for the host-native fallback. `answer_digest` is SHA-256 over the UTF-8 bytes
  of the `answer` string itself, not over a file.
- **WorkOrder:** `workorder_id`, `decision_id`, `decision_ref`,
  `decision_digest`, `applicability_ref`, `applicability_digest`, `subject`,
  `scope`, `task` (`task_id`), `acceptance_criteria`, `governing_inputs`,
  `required_capabilities`, `worker_route`, `worker_role`,
  `canonical_implementer_available`. An extra `tasks` key is rejected
  outright; the one task lives under `task`.
- **Dispatch claim:** `status`, `run_id`, `run_ref`, `workorder_ref`,
  `workorder_digest`, `decision_id`, `decision_digest`, `attempt_id`,
  `output_ref`.
- **Attempt:** `attempt_id`, `task_id`, `workorder_id`, `workorder_ref`,
  `workorder_digest`, `decision_id`, `decision_digest`, `status`,
  `output_ref`, `output_digest`.
- **Aggregation report:** `coverage`, `acceptance_criteria`, `result`,
  `attempt_ref`, `attempt_digest`, `attempt_id`, `task_id`, `workorder_ref`,
  `workorder_id`, `workorder_digest`, `decision_id`, `decision_digest`,
  `output_ref`, `output_digest`, `failures`, `conflicts`,
  `missing_references`, `unresolved_issues`.
- **Advisory review status:** an optional coordinator-owned Run field. Omission
  means `{"status":"not_run"}`. A performed review records exactly
  `status=performed`, `workorder_ref`, `workorder_digest`, `attempt_ref`,
  `attempt_id`, and `attempt_digest`, each matching the accepted WorkOrder and
  Attempt. Malformed or rebound metadata fails closed. This records status, not
  approval, reviewer authority, or a prerequisite.
- **Outcome:** the coordinator persists exactly the object returned by
  `validate_acceptance`, including normalized `advisory_review` status, so
  hand-authored or partial Outcomes never match; a worker or aggregator never
  writes one.

## Validation and restart

The core validates exact bytes/digests, project-root confinement, same-Run references, decision identity uniqueness across enumerated canonical Decision artifacts, required `question_id`, authorization scope, applicability, one-task shape, Attempt/WorkOrder/Decision bindings, dispatch-claim/Run/WorkOrder/Decision bindings, report/Attempt digest and output-reference/digest bindings, output evidence, and complete coverage. Governing Git inputs must be tracked and match the stored digest in HEAD, the index, and the working tree; any change requires reassessment. Missing, malformed, duplicate, failed, stale, unsupported, or mismatched artifacts fail closed. The uniqueness check assumes complete enumeration of intact local artifact directories; it is not a security boundary against arbitrary local filesystem corruption or a subject able to modify authoritative artifacts. An unreadable directory omitted by a filesystem API can hide a duplicate Decision ID, so uniqueness is guaranteed only over artifacts visible to the validator.

After writing `outcome.json`, record its reference and digest in Run. A fresh process calls `validate_outcome`, which reloads Run, WorkOrder, HumanDecision, Applicability, Attempt, report, and evidence from portable refs, recomputes acceptance, and compares it with the persisted Outcome. Do not recover authority from process memory, conversation history, or a host session, and never recreate missing records silently. Harness-specific session history may help locate work product for human-assisted recovery, but must not be required, parsed by the portable core, or treated as proof that an unrecorded effect did not occur.
````

Resume/handoff search, from repo root:

```bash
rg -n -i 'decision|applicab' core/contracts/policy/resume.md core/contracts/policy/handoff.md
```

Actual inspection: `resume.md` has **0** matches; `handoff.md` has **10** matching lines about general delegation and the human-decision packet, not task-first persisted applicability. These separate v3 stage-attempt policies are bundle inputs: leave them unchanged. The new task-first resume/handoff paragraph supplies this slice's complete guidance. No other resume/handoff-named Markdown files exist under `core/contracts` or `docs`. Task-first text is not a bundle input; do not broaden scope to v3 authority or generated outputs.

- [ ] **Step 4: Verify the structural contract test green.**

Run: `PYTHONPATH=core python -m pytest tests/core/test_package.py::PackageTests::test_task_first_decision_guidance -q`

Actual revision-2 focused green: exit 0, **1 passed**.

- [ ] **Step 5: Run each final integration gate.**

```bash
PYTHONPATH=core python -m unittest discover -s tests/core -v
PYTHONPATH=core python -m unittest discover -s tests/conformance -v
PYTHONPATH=core python tooling/build/build_bundle.py --check
```

Actual revision-2 integration gates: all exit 0; **687 core tests OK**, **18 conformance tests OK**, bundle check reports `CoreBundle copies match canonical sources`.

- [ ] **Step 6: Review the uncommitted working-tree checkpoint.** Save a stash-free per-task evidence file outside the repository, for example `$EVIDENCE/task6-working-tree.patch`, using `git diff --binary -- <this task's tracked paths>`. Append every new file in this task with `git diff --no-index --binary -- /dev/null <new-file>` (exit 1 means differences, not failure). These are working-tree checkpoint patches, not BASE..HEAD packages or instructions to change HEAD. Have the task reviewer inspect the patch plus full new-file content and test logs. Leave all changes uncommitted. The final reviewer reviews the cumulative working-tree diff, including every untracked file in scope; do not rely on per-task history.

## Spec Coverage Matrix

| Spec §2 decision/bullet | Tasks | Named proof or artifact |
| --- | --- | --- |
| 1 Cross-Run single-original reuse, canonical refs/digest/confinement/symlinks/unique ID; local applicability | 1 | `test_ws2_cross_run_reuse_has_one_original`, `test_ws2_decision_layout_rejected`, `test_ws2_decision_identity_bindings`, `test_ws2_duplicate_decision_identity`, `test_ws2_decision_symlink_components`, `test_ws2_decision_digest_binding`; retained local applicability check |
| 2 Immutable original and assessed bindings | 3 | `test_ws2_reassessment_preserves_immutable_original`, `test_ws2_reassessment_binding_failures`, `test_ws2_equal_malformed_historical_snapshots_rejected`, `test_ws2_present_invalid_original_is_not_absent` |
| 2 Historical producer shape vs selected/current strict shape, freshness, legacy absence | 1,3 | Distinct historical/selected tables, empty-original presence/mismatch proofs; three unchanged freshness tests; baseline exact Outcome |
| 2 Subject/scope/action authority unchanged | 1,3,6 | `test_ws2_reassessment_cannot_change_authority`, unchanged authority-ceiling test, coordinator action-coverage prose; no new action field |
| 2 Result vocabulary, reason, distinct blocked/malformed diagnostics, no persisted superseded | 2,6 | `test_ws2_result_diagnostics`, `test_ws2_invalid_reason_keeps_existing_diagnostic`, structural metadata test |
| 2 Uncovered/ambiguous work needs fresh decision | 6 | Full lookup/assessment/fresh-decision prose (reviewer inspection, not sentence assertions) |
| 3 Non-empty exact edge schema, target ID/ref/digest | 4 | `test_ws2_graph_edge_schema`, `test_ws2_graph_invalid_target_binding` |
| 3 Human-boundary producer ownership | 6 | Full immutable human-input-boundary prose (reviewer inspection); no producer changes |
| 3 Self/cycle, different question IDs | 4 | `test_ws2_graph_cycles_before_digest_validation`, `test_ws2_graph_transitive_different_question_non_revival` |
| 3 Transitive/no revival, dispatch-only, historical isolation | 4,5 | All-target union; `test_ws2_dispatch_blocks_superseded_without_mutation`, `test_ws2_completed_outcome_ignores_later_graph_but_dispatch_fails_closed` |
| 3 Every enumerated file validates; PR85-009 | 4,5,6 | `test_ws2_graph_validates_unconnected_decision`, `test_ws2_graph_uses_strict_loader`, `test_ws2_graph_rejects_duplicate_identity`, `test_ws2_graph_rejects_symlink_file`; later-invalid-file integration rows; prose limitation |
| 3 Existing five types vs selected approval (clarification) | 1,4,6 | `test_ws2_selected_nonapproval_cannot_authorize`, `test_ws2_graph_accepts_nonapproval_human_decisions`; spec/contract ruling |
| 3 Authority-bearing version boundary; WS-11 deferral | 6 | Old-validator and deferred-producer clauses; mandatory text test |
| 4 No global question identity | 4,6 | Different questions accepted; opaque-ID and no-index prose |
| 5 Semantic scope, WS-4, partial AC2 | 6 | No matcher; per-task authorization/narrowing deferred; spec retains partial AC2 |

| Spec §5 test category | Task and named proof |
| --- | --- |
| Cross-Run reuse | 1: single-original test |
| Immutable original and mismatch rejection | 3: immutable-original test, binding/shape tables |
| Successful reassessment after drift | 3: isolated temporary-repository fixture commit and successful ready-Run dispatch |
| Drift without reassessment blocked | 3: unchanged working-tree/index/HEAD tests; absent-original variant |
| Subject/scope rejected | 3: reassessment authority test and unchanged authority-ceiling test |
| Each blocked and unknown result | 2: complete `_params` result/reason tables |
| Different question_id supersession | 4: transitive/different-question/non-revival test |
| Invalid refs, hashes, self/cycles | 1,4: layout/digest/schema/target tests, exact structural diagnostics |
| Superseded blocks dispatch/claim, not completed Outcome | 5: both APIs directly and in fresh processes; valid/malformed later files |
| Both external source kinds and attribution | 5: original ref/ID/source_kind in Outcome; source_ref in original record; unchanged schema |
| Fresh-process reconstruction | 5: `_ws2_restart` dispatch/claim failures and persisted Outcome successes; existing restart test unchanged |
| #85 records and HEAD/index/worktree checks remain green | 1–5 full task-contract gate after every task; 6 full 687-test core suite; no old assertion rewrites |

### Revision-2 contract proofs

| Requirement | Named proof / task |
| --- | --- |
| Empty historical snapshots accepted; no unrelated dispatch veto | 1 `test_ws2_historical_reader_matches_producer_snapshot`; 4 `test_ws2_graph_accepts_producer_snapshot_and_empty_chain`; 5 `test_ws2_dispatch_accepts_unrelated_empty_historical_inputs` |
| Empty-input targets and superseders remain valid; selected empty cannot authorize | 4 `test_ws2_graph_accepts_producer_snapshot_and_empty_chain`; 1 `test_ws2_empty_selected_inputs_cannot_authorize` (absent/present original) |
| Explicit original=[] vs absent and mismatch | 3 `test_ws2_empty_original_snapshot_presence_semantics`; `test_ws2_present_empty_original_mismatches_nonempty_snapshot` |
| One glob/read per file; no across-call cache | 4 `test_ws2_graph_reads_each_file_once`; 5 `test_ws2_dispatch_reads_each_decision_once_per_call` (two invocations) |
| Retained selected/chain references missing after archival | 5 `test_ws2_missing_retained_reference_fails_closed_after_restart` (two stable errors) |
| Kernel never mutates selected, unrelated or superseding decisions | 5 `test_ws2_kernel_never_mutates_any_decision_file`; existing dispatch/lifecycle snapshots |
| Structural metadata, closed vocabulary/fields, real diagnostics | 6 `PackageTests.test_task_first_decision_guidance`; no phrase assertions |

## Verification Evidence and Limitations

All final executable snippets were replayed sequentially, red then green, in `/home/dvory/.pi/tmp/ws2-revision2-verified`. Evidence, extracted snippets and scripts are in `/home/dvory/.pi/tmp/ws2-revision2-snippets`; these are evidence paths, not execution dependencies. Earlier attempts are retained in `/home/dvory/.pi/tmp/ws2-revision2-replay`, `/home/dvory/.pi/tmp/ws2-revision2-replay-final` and `/home/dvory/.pi/tmp/ws2-revision2-clean-replay`; nothing was deleted. Plan-only extraction reconstruction is `/home/dvory/.pi/tmp/ws2-revision2-plan-extraction`.

| Task | Actual focused red (exit 1) | Actual focused green (exit 0) | Whole task-contract unittest |
| --- | --- | --- | --- |
| 1 | 6 failed, 3 passed, 66 deselected | 9 passed, 66 deselected | 147 OK |
| 2 | 1 failed, 1 passed, 75 deselected | 2 passed, 75 deselected | 166 OK |
| 3 | 6 failed, 1 passed, 77 deselected | 7 passed, 77 deselected | 189 OK |
| 4 | 11 failed, 84 deselected | 11 passed, 84 deselected | 229 OK |
| 5 | 5 failed, 3 passed, 95 deselected | 8 passed, 95 deselected | 246 OK |
| 6 | 1 failed | 1 passed | final full core below |

Final gates (actual): `PYTHONPATH=core python -m unittest discover -s tests/core`: **687 tests, OK**; `PYTHONPATH=core python -m unittest discover -s tests/conformance`: **18 tests, OK**; `python tooling/build/build_bundle.py --check`: **exit 0**, `CoreBundle copies match canonical sources`. Logs: `revision2-taskN-{red,green,unittest}.log`, `revision2-full-core.log`, `revision2-conformance.log`, `revision2-bundle-check.log`.

Extraction audit: every Python fence compiles (the indented PackageTests method compiles under its class), 14 full/test snippets match their staged prototype files exactly, partial replacements match the corresponding AST symbols/constants, and the installed Markdown equals its snippet exactly. All 9 changed implementation/test/contract files in plan-only sequential reconstruction match the final prototype (Python AST equivalence; Markdown exact bytes); all 18 Python fences compile. The audit and measured sizes are in `revision2-plan-audit.json`.

Corrections caught in scratch, not hidden: moving strict selected-input shape extraction into Task 1 required importing it in both early authority stages; missing helper names and ready-state setup in first-draft regressions were fixed before the clean replay. Historical malformed-input errors now reflect the historical reader, not current WorkOrder policy. A host name in an implementation docstring initially tripped host-neutral conformance; it was replaced with producer-neutral wording. The first bundle probe used the wrong script path and was rerun with the real `tooling/build/build_bundle.py`. These failed preliminary probes are not claimed as passes; final clean task replay and all final gates passed.

Scratch copies exclude `.git`, caches, virtual environments and `node_modules`, initialize independent Git, and import read-only local source history for fixed historical-bundle fixtures. No worktree production/test writes, staging, publication, destructive shell commands or explicit file deletions occurred. Test-fixture Git commits occur only in their temporary repositories. The existing unittest loader's temporary-directory cleanup is unchanged.

Not run: `code-gates run` (crapper/dryer/mutator), root/plugin/Bun/harness CI, alternate Python versions/Windows, live human-producer integrations, or an execution through the subagent skill. No bundle inputs or generated outputs changed. These limitations do not replace later owner-authorized CI. Plan approval grants no publication authority.

## Plan Notes / Rulings / Open Questions

1. **Publication boundary:** approval authorizes no commits, pushes or merges. Keep work uncommitted; the owner decides. SDD checkpoint review uses saved working-tree patches including untracked files, and final review uses the cumulative working-tree diff. Supervisor explicitly allowed only isolated fixture commits in temporary Git repositories.
2. **Historical producer shape:** verified `harnesses/pi/extensions/human-decisions.ts` `parseRequest` (61–85), `recordDecision` (216–231), and non-empty input guard (269–273). Governing snapshots may be empty, duplicate or non-Git; each entry has exactly a non-empty string ref and lowercase 64-hex digest. Decision types are the five producer values. Required question/subject/scope/answer strings remain non-empty. Optional request `source_ref`/`approving_party` may be absent or null (emitted absent), or non-empty strings (emitted present); `external_artifact` requires source_ref. `run_id` selects storage but is not emitted in the decision. No stricter historical portability/uniqueness/current-Git policy is invented.
3. **Empty-original ruling (§2.2):** present `original_governing_inputs=[]` is valid historical shape and matches only an empty decision snapshot. It is distinct from absence, which requires assessed==historical. Null/malformed originals fail; [] vs a non-empty decision fails mismatch. Empty historical decisions may appear anywhere in a valid supersession graph, but cannot authorize a WorkOrder, even with fresh assessed inputs and explicit original=[]; the selected path preserves `work order requires governing Git inputs`.
4. **One-call snapshot:** dispatch scans/parses every decision once, then uses identity→record/path/digest and forward edges for uniqueness, target resolution, self/cycles/hashes and eligibility. Explicit private parameter threading reuses selected bytes. No persisted index, new runtime infrastructure, module cache or cross-call memory. O(N log N + E) time plus input-byte parsing; O(N + E) auxiliary graph space. Tests count all file reads and globs across two calls.
5. **Retention:** referenced decisions and their supersedes chain remain retained/unmodified while any Run or WorkOrder references them. Missing selected authority and missing chain targets have distinct stable errors. Archiving a referenced Run breaks cold restart. Retention policy/GC remains owner-decided and out of scope; the kernel never mutates decisions.
6. **Deterministic documentation checks:** replace all 16 literal phrase checks with one small method checking headings/label, minimal JSON metadata, closed results/fields imported from actual used kernel constants, and declared diagnostics/error class. Markdown still carries full LLM semantic guidance. No CI assertion on sentence wording or implementation syntax.
7. **Dispatch-only policy retained:** graph integrity and supersession eligibility are never applied by public validate_run, acceptance or Outcome. Structure/identity/self/cycles precede edge hashes, with no digest fixed point for invalid cycles. Rejected dispatch is read-only and transitive supersession never revives targets. Current-input freshness on acceptance/Outcome remains the pre-existing non-blocking follow-up, not changed here.
8. **Boundaries retained:** LLM owns reuse, substantive-change and scope/action judgments; decisions stay immutable; no global question identity. Real producer work is WS-11/WS-12, task-level enforcement/narrowing is WS-4, AC2 remains partial. General v3 resume/handoff and bundle-authority files remain unchanged. Tracker updates remain the separate spec §7.2 change.
9. **No implementation-blocking ambiguity remains.** Retention policy/GC and the pre-existing freshness follow-up require owner decisions only if separately taken up; no new ruling expands this implementation's scope.

### Small Clarifying Spec Edits Made

- §2.1 retains cross-Run reference-only reuse, confinement, identity, uniqueness and digest checks.
- §2.2 separates producer-shaped historical snapshots from strict selected/current WorkOrder inputs; explicitly defines present-empty vs absent originals and preserves the selected empty-input diagnostic.
- §2.3 requires one call-local enumeration/parse and identity/edge lookup (no persisted index or cross-call cache); graph validation remains dispatch-only and cycle-before-hash ordering is retained.
- New §2.6 states cross-Run retention, transitive chain obligations, stable missing-reference diagnostics, immutable kernel behavior and owner-decided out-of-scope GC.
- §4 requires full retention/reassessment guidance plus minimal machine-checkable contract metadata and structural/constant-based package checks, not literal prose assertions.
- §5 adds empty historical scan/chain/authorization cases, original=[] semantics, bounded reads/globs, missing retained references after restart and decision immutability; the coverage matrix above ties them to named tests.
- §3 producer ownership remains unchanged: human-input boundary owns `supersedes`; coordinator owns applicability; no generated durable index or snapshot artifact is added.

## Task-Count / Size Summary

Six sequential tasks, 36 checkbox steps. Checkpoint reviews replace all executor publication steps. Complete code/test/Markdown snippets remain in this plan; no scratch file is an executor dependency. Measured module sizes and review-trigger justifications are listed above. Ten new test functions cover 15 parameterized cases; one obsolete planned present-empty-is-invalid case is replaced by the explicit valid-empty/mismatch/selected-ineligible rulings (net +14 core unittest cases, 673→687). No pre-existing production test assertion is weakened. The package test remains one method and no longer asserts prose wording.
