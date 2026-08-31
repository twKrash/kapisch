# Thin KAPISCH Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make KAPISCH’s parent a thin, validator-bound workflow controller using compact stage outcomes and a derived controller view, without weakening canonical evidence, review, final-readiness, or resume guarantees.

**Architecture:** Version-4 durable graphs add immutable per-attempt outcome artifacts and a derived `04-controller-view.toml`. The read-only validator validates these records; a separate explicit renderer writes the view atomically. Codex and Pi/OMP adapters consume the portable compact contracts but retain their own dispatch/transport details.

**Tech Stack:** Python 3.11 standard library, TOML, `unittest`, Markdown, existing `kapisch_validation` package and CLI.

**Spec:** `docs/superpowers/specs/2026-08-31-parent-token-usage-design.md`

## Global Constraints

- Do not implement issue #23, issue #25, profile/model routing, provider pricing, TOON, parallel execution, or unrelated refactors.
- Keep the six logical roles, sequential-only execution, risk/review/final policies, canonical reviewer invocation evidence, validator read-only behavior, and all current v1–v3 semantics intact.
- `kapisch-validate` remains read-only: it must never create, repair, migrate, or render artifacts.
- New durable graphs use manifest `version = 4`; v1–v3 stay readable/resumable without rewrite.
- Use only Python 3.11 standard library dependencies. Never infer unavailable runtime identity, approval, metrics, cache, cost, or test evidence.
- The controller normally reads only `04-controller-view.toml`; detailed artifacts are specialist-owned or debug-only as defined by the spec.
- No automatic worker/reviewer re-dispatch without a closed-vocabulary persisted reason, predecessor attempt, and budget effect.
- Do not commit, push, tag, publish, or make external changes unless separately authorized by the execution request.

---

## Locked v4 contract

Implement this exact contract; do not redesign it.

### Graph and state bindings

A v4 manifest adds root field `controller_view = "04-controller-view.toml"`. Every `nodes.assignment.attempts[]` record adds `outcome_path`, initially `"unavailable"`; a terminal attempt (`complete|blocked|failed`) requires `stage-outcomes/<attempt-id>.toml`, and a `pending|running` attempt requires `"unavailable"`.

A v4 state adds required fields:

```toml
controller_view_path = "04-controller-view.toml"
controller_view_sha256 = "<64 lowercase hex>"
```

Version 1–3 reject these v4-only fields. The state binding does not create a digest cycle: the rendered view’s `source_state_sha256` is SHA-256 of canonical JSON (`sort_keys=True`, separators `(',', ':')`, UTF-8) of parsed state after removing exactly `controller_view_path` and `controller_view_sha256`. Its `source_manifest_sha256` is SHA-256 of raw manifest bytes. `controller_view_sha256` is SHA-256 of the rendered view bytes.

### Outcome path and schema

Each terminal attempt has exactly one regular UTF-8 TOML file at `stage-outcomes/<attempt-id>.toml` with this closed top-level schema:

```toml
version = 1
task_id = "<task-id>"
node_id = "T01"
role = "implementer" # one of the six logical roles
assignment_id = "A-T01-1"
attempt_id = "AT-T01-1"
lifecycle = "complete" # complete|blocked|failed
role_status = "done" # done|done-with-concerns|needs-context|blocked|failed
base_revision = "<non-empty>"
head_revision = "<non-empty>"
working_tree_state_sha256 = "<64 lowercase hex>|unavailable"
report_path = "tasks/T01-report.md"
report_sha256 = "<64 lowercase hex>"
invocation_path = "unavailable" # required review/final path otherwise unavailable
invocation_id = "unavailable"
invocation_sha256 = "unavailable"
reviewer_decision = "unavailable" # unavailable|approve|do-not-approve|ready|not-ready
redispatch_reason = "none"
predecessor_attempt_id = "unavailable"
retry_budget_delta = 0
next_action_reason = "completed"
findings = []
verification = []
```

`findings` contains at most 20 inline tables, each with exactly `id`, `severity`, `summary`, and `evidence_ref`; `severity` is the existing KAPISCH severity vocabulary and `summary` is 1–280 Unicode code points. `verification` contains at most 20 inline tables, each with exactly `check`, `result`, `evidence_ref`, and `output_sha256`; `result` is `pass|fail|not-run|unavailable`, with a 64-character digest required only for `pass|fail`.

`redispatch_reason` is exactly one of `none`, `interrupted-active-stage`, `reviewer-finding`, `failed-attempt`, `stale-review-state`, `approved-amendment`, or `dispatch-no-work`. `retry_budget_delta` is `0` for `none`, `interrupted-active-stage`, `stale-review-state`, and `dispatch-no-work`; it is `1` for the other three. A non-`none` reason requires a non-`unavailable` predecessor attempt. `next_action_reason` is exactly one of `completed`, `blocked`, `failed`, `review-negative`, `review-stale`, `await-user`, `retry-authorized`, `retry-exhausted`, or `dispatch-failed`.

For `reviewer` outcomes, `invocation_*` fields must bind to the node’s existing canonical invocation artifact and `reviewer_decision` must match the existing review/final result. For non-reviewer outcomes, all invocation fields and `reviewer_decision` are `unavailable`.

### Controller view schema

`04-controller-view.toml` is canonical UTF-8 TOML, rendered in a fixed key/table order by one pure renderer. Its closed top-level schema is:

```toml
version = 1
task_id = "<task-id>"
source_manifest_sha256 = "<64 lowercase hex>"
source_state_sha256 = "<64 lowercase hex>"
workflow_status = "running|complete"
current_revision = "<non-empty>"
next_action = "select:T01|resolve:T01|block:*|complete"
validator_status = "pass|fail"
validator_error_count = 0
active_node_id = "T01|unavailable"
next_node_id = "T01|unavailable"
current_fix_round = 0
max_fix_rounds = 1
```

It then emits `[request]`, `[gates]`, `[active_assignment]` (all scalar/bounded fields only), plus zero or more `[[predecessor_outcomes]]` records. `predecessor_outcomes` are ordered by node sequence then attempt ID, contain only `node_id`, `attempt_id`, `lifecycle`, `role_status`, `reviewer_decision`, `redispatch_reason`, `next_action_reason`, and `outcome_path`, and include only completed dependencies of the active/next node. The renderer never includes raw reports, output, prompts, transcripts, metrics, extension data, or non-dependency history.

---

## File structure

| File | Responsibility |
| --- | --- |
| `plugins/kapisch/kapisch_validation/vocabulary.py` | v4 closed vocabularies and bounded-field constants. |
| `plugins/kapisch/kapisch_validation/models.py` | Typed parsed outcome/controller-view records. |
| `plugins/kapisch/kapisch_validation/outcomes.py` **new** | Read-only parse/validate outcome artifacts and their graph/report/invocation bindings. |
| `plugins/kapisch/kapisch_validation/controller_view.py` **new** | Pure deterministic view data construction, canonical TOML rendering, digest calculation, and validation. No writes. |
| `plugins/kapisch/kapisch_validation/manifest.py` | v4 graph/attempt schema and v1–v3 compatibility parsing. |
| `plugins/kapisch/kapisch_validation/references.py` | v4 state binding parsing and path/reference checks. |
| `plugins/kapisch/kapisch_validation/transitions.py` | v4 outcome immutability and lifecycle/re-dispatch checks across snapshots. |
| `plugins/kapisch/kapisch_validation/cli.py` | Call v4 read-only validators only. |
| `plugins/kapisch/scripts/render_controller_view.py` **new** | Explicit, atomic write-only renderer; validates before and after write. |
| `plugins/kapisch/scripts/migrate_controller_view_v4.py` **new** | Explicit, fail-closed eligible-v3 to v4 copy/migration tool; never invoked by resume. |
| `plugins/kapisch/skills/kapisch/references/{handoffs,execution-graph,resume,dispatch,review}.md` | Normative v4 semantics, load rules, retry rules, and unchanged review guarantees. |
| `plugins/kapisch/skills/kapisch/SKILL.md` | Compact normal controller procedure and exceptional detailed-reference loading. |
| `plugins/kapisch/tests/kapisch_validation/test_{manifest,vocabulary,transitions,cli}.py` | v4 parser, state-vocabulary, lifecycle, CLI, and legacy compatibility coverage. |
| `plugins/kapisch/tests/kapisch_validation/test_outcomes.py` **new** | Outcome schema/binding/limit coverage. |
| `plugins/kapisch/tests/kapisch_validation/test_controller_view.py` **new** | Pure renderer, deterministic ordering/digests, stale/missing/corrupt view coverage. |
| `plugins/kapisch/tests/kapisch_validation/test_controller_tools.py` **new** | Atomic renderer and explicit migration behavior. |
| `plugins/kapisch/tests/kapisch_validation/fixtures/valid-v4-controller/` **new** | Valid complete v4 graph/state/outcomes/view fixture. |
| `plugins/kapisch/tests/kapisch_validation/fixtures/invalid-v4-*/` **new** | One focused malformed/stale/binding/retry fixture per failure class. |
| `plugins/kapisch/docs/controller-benchmark.md` **new** | Reproducible baseline/candidate execution and measurement protocol. |
| `plugins/kapisch/scripts/compare_controller_benchmark.py` **new** | Read-only JSONL metric-record validator/comparator; no provider calls. |
| `/home/dvory/.pi/agent/skills/kapisch/SKILL.md` | Pi adapter contract update; treat as adapter-distribution work, not portable core source. |

---

### Task 1: Lock v4 vocabulary and parser shape

**Files:**

- Modify: `plugins/kapisch/kapisch_validation/vocabulary.py`
- Modify: `plugins/kapisch/kapisch_validation/models.py`
- Modify: `plugins/kapisch/kapisch_validation/manifest.py`
- Modify: `plugins/kapisch/kapisch_validation/references.py`
- Test: `plugins/kapisch/tests/kapisch_validation/test_manifest.py`
- Test: `plugins/kapisch/tests/kapisch_validation/test_vocabulary.py`

**Interfaces:**

- Consumes: existing `Manifest`, `State`, `parse_manifest`, and `parse_state` interfaces.
- Produces: parsed v4 `Manifest`/`State` preserving `raw`; v4-only `controller_view` root path, attempt `outcome_path`, and state view bindings; v1–v3 rejection of v4-only fields.

- [ ] **Step 1: Write failing manifest/state tests.** Add tests that construct a valid v4 copy of the v3 fixture and assert parsing succeeds, then assert exact error codes/references for: `version = 4` without `controller_view`; `controller_view` on v3; missing v4 attempt `outcome_path`; a terminal attempt with `outcome_path="unavailable"`; a running attempt with a real outcome path; missing state view binding; and a v3 state containing either view field.

```python
self.assertEqual(
    [(error.code, error.reference) for error in result.errors],
    [("TWV-SCHEMA-MISSING-FIELD", "controller_view")],
)
```

- [ ] **Step 2: Run the focused tests and confirm they fail because version 4 and the new fields are unsupported.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_manifest plugins.kapisch.tests.kapisch_validation.test_vocabulary`

Expected: FAIL with `TWV-SCHEMA-INVALID-VERSION` or missing parser support, not import/syntax errors.

- [ ] **Step 3: Add the minimal v4 parser support.** Add `4` to the accepted manifest versions; add `controller_view` only to v4 root vocabulary; extend the attempt vocabulary with `outcome_path`; extend state vocabulary with the two view-binding fields. Enforce the exact v4/legacy field-presence rules in the locked contract. Preserve existing parsed dataclass positional compatibility by adding new optional fields after current fields with defaults.

- [ ] **Step 4: Run focused tests to green.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_manifest plugins.kapisch.tests.kapisch_validation.test_vocabulary`

Expected: PASS.

- [ ] **Step 5: Commit the parser contract.**

```bash
git add plugins/kapisch/kapisch_validation/{vocabulary.py,models.py,manifest.py,references.py} \
  plugins/kapisch/tests/kapisch_validation/test_{manifest,vocabulary}.py
git commit -m "feat: parse KAPISCH v4 controller bindings"
```

### Task 2: Add immutable stage-outcome validation

**Files:**

- Create: `plugins/kapisch/kapisch_validation/outcomes.py`
- Modify: `plugins/kapisch/kapisch_validation/cli.py`
- Modify: `plugins/kapisch/kapisch_validation/transitions.py`
- Test: `plugins/kapisch/tests/kapisch_validation/test_outcomes.py`
- Test: `plugins/kapisch/tests/kapisch_validation/test_cli.py`

**Interfaces:**

- Consumes: `Manifest`, `State`, `read_utf8_artifact`, existing report/invocation paths, and locked v4 schema.
- Produces: `parse_outcome(path) -> tuple[dict[str, object] | None, list[ValidationError]]` and `validate_outcomes(manifest, state, task_dir) -> list[ValidationError]`; `validate_snapshot` invokes it for v4 only.

- [ ] **Step 1: Write failing outcome tests for the full happy path and closed schema.** Build an in-test v4 task directory with a terminal `AT-T01-1`, matching report bytes/digest, and matching outcome. Assert no errors. Add parameterized failure assertions for unknown key, non-regular/missing file, wrong task/node/role/assignment/attempt IDs, digest mismatch, invalid lifecycle/role status/re-dispatch reason, oversized finding list, 281-character summary, malformed verification record, and a non-reviewer carrying reviewer evidence.

```python
errors = validate_outcomes(manifest, state, task_dir)
self.assertIn("TWV-OUTCOME-REPORT-DIGEST", {error.code for error in errors})
```

- [ ] **Step 2: Add failing reviewer-binding tests.** Use the existing valid review fixture’s invocation/report evidence and assert an outcome fails for a missing invocation path, mismatched invocation digest, or decision that differs from the reviewer report/envelope.

- [ ] **Step 3: Run tests to verify missing module failures.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_outcomes`

Expected: FAIL with `ModuleNotFoundError: kapisch_validation.outcomes`.

- [ ] **Step 4: Implement `outcomes.py` minimally.** Use existing artifact I/O/error conventions. Enforce exact top-level/nested fields, count/length limits, digests, path containment, attempt lifecycle coupling, report binding, existing reviewer envelope coupling, and closed re-dispatch/budget rules. Return structured `ValidationError`s; do not write files or infer unavailable facts.

- [ ] **Step 5: Wire read-only validation and snapshot immutability.** Call `validate_outcomes` from `validate_snapshot` only for v4. In `validate_transition`, reject an outcome path/digest/content change for any prior terminal attempt, and reject a new non-`none` re-dispatch without the required predecessor/budget relation.

- [ ] **Step 6: Run focused tests to green.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_outcomes plugins.kapisch.tests.kapisch_validation.test_cli plugins.kapisch.tests.kapisch_validation.test_transitions`

Expected: PASS.

- [ ] **Step 7: Commit the outcome validator.**

```bash
git add plugins/kapisch/kapisch_validation/{outcomes.py,cli.py,transitions.py} \
  plugins/kapisch/tests/kapisch_validation/test_{outcomes,cli,transitions}.py
git commit -m "feat: validate immutable KAPISCH stage outcomes"
```

### Task 3: Build the pure controller-view renderer and validator

**Files:**

- Create: `plugins/kapisch/kapisch_validation/controller_view.py`
- Modify: `plugins/kapisch/kapisch_validation/cli.py`
- Test: `plugins/kapisch/tests/kapisch_validation/test_controller_view.py`

**Interfaces:**

- Consumes: parsed v4 manifest/state, validated outcomes, raw manifest bytes, and the canonical-state JSON digest rule.
- Produces: `state_semantic_sha256(state_raw) -> str`, `build_controller_view(manifest, state, outcomes, manifest_bytes) -> dict[str, object]`, `render_controller_view(view) -> bytes`, and `validate_controller_view(manifest, state, task_dir) -> list[ValidationError]`.

- [ ] **Step 1: Write failing deterministic-render tests.** Assert two semantically identical parsed states differing only in `controller_view_path`/`controller_view_sha256` produce the same state semantic digest; assert fixed view bytes/digest for the v4 fixture; assert predecessor outcomes include only completed dependencies ordered by node sequence then attempt ID; assert the rendered view omits `report_sha256`, raw report content, extensions, metrics, and non-dependency outcomes.

```python
self.assertEqual(
    state_semantic_sha256(with_binding),
    state_semantic_sha256(with_different_binding),
)
self.assertNotIn(b"report_sha256", rendered)
```

- [ ] **Step 2: Write failing stale-view tests.** Assert `validate_controller_view` returns dedicated errors for missing/non-regular/invalid UTF-8/malformed TOML view, unknown view field, source-manifest digest mismatch, source-state digest mismatch, state-bound view digest mismatch, and a view whose next/active node differs from deterministic graph/state action.

- [ ] **Step 3: Run tests and confirm missing-module failures.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_controller_view`

Expected: FAIL with `ModuleNotFoundError: kapisch_validation.controller_view`.

- [ ] **Step 4: Implement pure construction/rendering.** Use a hand-written canonical TOML renderer for the exact locked order; do not add a TOML dependency. Compute manifest raw-byte SHA-256 and canonical-state JSON SHA-256 as specified. Derive `active_node_id`, `next_node_id`, and predecessor outcomes from existing deterministic transition output. Set `validator_status="pass"`/`validator_error_count=0` only when called after successful snapshot validation; otherwise the writer must refuse to render rather than emit a failing view.

- [ ] **Step 5: Wire validation into `validate_snapshot` after reference/lifecycle/outcome checks.** Avoid recursive validation: `validate_controller_view` validates source/binding/projection, while `validate_snapshot` supplies already-validated outcome data. `kapisch-validate` remains read-only.

- [ ] **Step 6: Run focused tests to green.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_controller_view plugins.kapisch.tests.kapisch_validation.test_cli`

Expected: PASS.

- [ ] **Step 7: Commit the deterministic projection.**

```bash
git add plugins/kapisch/kapisch_validation/{controller_view.py,cli.py} \
  plugins/kapisch/tests/kapisch_validation/test_controller_view.py
git commit -m "feat: derive KAPISCH controller view"
```

### Task 4: Provide explicit atomic render and migration tools

**Files:**

- Create: `plugins/kapisch/scripts/render_controller_view.py`
- Create: `plugins/kapisch/scripts/migrate_controller_view_v4.py`
- Modify: `plugins/kapisch/scripts/test_portable_package.py`
- Test: `plugins/kapisch/tests/kapisch_validation/test_controller_tools.py`

**Interfaces:**

- Consumes: renderer `--task-dir PATH`; migration `--task-dir SOURCE --destination-task-dir DEST --approve`, where `DEST` must not exist.
- Produces: renderer exit 0 only after atomically replacing `04-controller-view.toml` and state bindings then revalidating; migration produces `DEST` as a copied v4 task directory and never mutates `SOURCE`.

- [ ] **Step 1: Write failing renderer tests.** In a temporary v4 fixture copy, assert render creates fixed view bytes, updates state’s view hash, and validates. Patch the atomic replacement seam to fail; assert original state/view bytes remain unchanged. Assert invalid source snapshots return 2 and create no view.

- [ ] **Step 2: Write failing migration tests.** Invoke migration with `--task-dir SOURCE --destination-task-dir DEST --approve`. Assert it rejects omitted `--approve`, omitted destination, an existing destination, active/ambiguous legacy runs, missing reports, or invalid legacy artifacts; assert an eligible complete v3 source produces v4 `DEST` with generated outcomes/view while source byte digests remain unchanged.

- [ ] **Step 3: Run focused tests to confirm scripts are absent.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_controller_tools`

Expected: FAIL with import/file-not-found failures for the two scripts.

- [ ] **Step 4: Implement the renderer.** Follow `migrate_legacy_run.py` safety style: parse and validate before writes; create a same-directory temporary file; `os.replace` view first; atomically replace state second; if state replacement fails, restore the old view bytes; run read-only validation after both replacements; on post-write validation failure restore both old bytes and return 2. Do not add this behavior to `kapisch-validate`.

- [ ] **Step 5: Implement migration as copy-then-validate.** Parse `SOURCE` and `DEST` from the required arguments, reject an existing `DEST`, and create the staging directory under `DEST.parent`. Require a complete, inactive v3 graph with persisted terminal assignment/attempt records and valid current evidence; add version-4 fields, derive an outcome for each terminal attempt from canonical report/invocation facts only, render view, validate, then atomically rename the staged directory to `DEST`. Fail closed when a required outcome fact cannot be derived; never synthesize reviewer provenance or decisions.

- [ ] **Step 6: Add portable-package assertions.** Require both scripts and their imported package modules in the copied bundle; run `--help` for both scripts in the package smoke test.

- [ ] **Step 7: Run focused tests to green.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_controller_tools plugins.kapisch.tests.kapisch_validation.test_extraction_acceptance`

Expected: PASS.

- [ ] **Step 8: Commit the explicit write tools.**

```bash
git add plugins/kapisch/scripts/{render_controller_view.py,migrate_controller_view_v4.py,test_portable_package.py} \
  plugins/kapisch/tests/kapisch_validation/test_controller_tools.py
git commit -m "feat: add explicit KAPISCH controller view tools"
```

### Task 5: Add v4 fixtures and full validator compatibility matrix

**Files:**

- Create: `plugins/kapisch/tests/kapisch_validation/fixtures/valid-v4-controller/` complete artifact tree
- Create: `plugins/kapisch/tests/kapisch_validation/fixtures/invalid-v4-*` focused artifact trees
- Modify: `plugins/kapisch/tests/kapisch_validation/test_cli.py`
- Modify: `plugins/kapisch/tests/kapisch_validation/test_transitions.py`

**Interfaces:**

- Consumes: Tasks 1–4 contracts.
- Produces: fixture-backed behavior proof for v4 validity, legacy non-regression, stale/corrupt view blocking, terminal outcome immutability, and authorized retry behavior.

- [ ] **Step 1: Add valid fixture first.** Create a complete v4 T01/R01/F01 sequential tree with report/invocation bytes and computed SHA-256 fields. Add it to the existing CLI fixture matrix with expected exit 0.

- [ ] **Step 2: Add one failure fixture per invariant.** Include: missing view, stale view digest, view source mismatch, report digest mismatch, reviewer invocation mismatch, terminal outcome rewritten versus previous snapshot, unknown outcome field, over-limit finding, forbidden re-dispatch, and a legacy v3 fixture carrying v4 fields.

- [ ] **Step 3: Run fixture matrix and confirm each initially fails for its intended primary code.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_cli plugins.kapisch.tests.kapisch_validation.test_transitions`

Expected: each invalid fixture exits 2 with its named `TWV-*` code; valid v1, v2, v3, and v4 fixtures exit 0.

- [ ] **Step 4: Correct fixture bytes/digests and error assertions until the matrix is stable.** Do not loosen parser/validator code to accommodate malformed fixtures.

- [ ] **Step 5: Run the complete validator suite.**

Run: `python -m unittest discover -s plugins/kapisch/tests/kapisch_validation`

Expected: PASS.

- [ ] **Step 6: Commit fixture coverage.**

```bash
git add plugins/kapisch/tests/kapisch_validation
git commit -m "test: cover KAPISCH v4 controller artifacts"
```

### Task 6: Document the portable thin-controller procedure

**Files:**

- Modify: `plugins/kapisch/skills/kapisch/SKILL.md`
- Modify: `plugins/kapisch/skills/kapisch/references/handoffs.md`
- Modify: `plugins/kapisch/skills/kapisch/references/execution-graph.md`
- Modify: `plugins/kapisch/skills/kapisch/references/resume.md`
- Modify: `plugins/kapisch/skills/kapisch/references/dispatch.md`
- Modify: `plugins/kapisch/skills/kapisch/references/review.md`
- Modify: `plugins/kapisch/README.md`
- Modify: `plugins/kapisch/CHANGELOG.md`
- Test: `plugins/kapisch/tests/kapisch_validation/test_extraction_acceptance.py`

**Interfaces:**

- Consumes: locked v4 contract and unchanged existing reviewer/final rules.
- Produces: one portable controller procedure and explicit A/B/C/D loading rules used by Codex, Pi, and OMP adapters.

- [ ] **Step 1: Write documentation-contract tests.** Assert the public skill says normal transitions read the controller view, prohibits transcript/full-run-tree reads and confidence re-dispatch, and sends specialists artifact references. Assert handoffs/execution/resume specify v4 outcome/view paths, explicit regeneration/block behavior, and v1–v3 compatibility. Assert review documentation retains fresh independent actual-diff inspection and canonical invocation requirements.

- [ ] **Step 2: Run the extraction tests to verify assertions fail before docs change.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_extraction_acceptance`

Expected: FAIL only on the newly asserted contract text.

- [ ] **Step 3: Update normative owners without duplicating semantic authority.** `handoffs.md` owns outcome storage/fields; `execution-graph.md` owns v4 bindings/deterministic view inputs; `resume.md` owns stale/missing view regeneration/blocking; `dispatch.md` owns bounded assignments/re-dispatch reasons; `review.md` explicitly states outcomes/views never replace reviewer evidence; `SKILL.md` gives the compact normal procedure and names exceptional detailed loads.

- [ ] **Step 4: Update public README/changelog.** Describe v4 controller projections, explicit renderer/migration commands, no change to core role/review/final guarantees, and no performance claim pending benchmark data.

- [ ] **Step 5: Run documentation tests to green.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_extraction_acceptance`

Expected: PASS.

- [ ] **Step 6: Commit portable contract docs.**

```bash
git add plugins/kapisch/{skills/kapisch,README.md,CHANGELOG.md} \
  plugins/kapisch/tests/kapisch_validation/test_extraction_acceptance.py
git commit -m "docs: define thin KAPISCH controller contract"
```

### Task 7: Update Codex and Pi/OMP adapter contracts

**Files:**

- Modify: `plugins/kapisch/agents/kapisch-{researcher,implementer,implementer-lite,mechanic,architect,reviewer}.toml`
- Modify: `plugins/kapisch/roles/{researcher,implementer,implementer-lite,mechanic,architect,reviewer}.md`
- Modify: `/home/dvory/.pi/agent/skills/kapisch/SKILL.md` (or the adapter distribution source that installs this exact file)
- Test: `plugins/kapisch/tests/kapisch_validation/test_extraction_acceptance.py`

**Interfaces:**

- Consumes: current role identities and portable v4 assignment/result rules.
- Produces: role prompts requiring compact transport returns plus detailed evidence, and Pi adapter instructions using current contract discovery, fresh contexts, artifact references, transcript isolation, and renderer/validator boundaries.

- [ ] **Step 1: Write failing role/adapter contract tests.** Assert each portable role contract retains its permissions and does not contain Pi/Codex paths; assert each role returns a bounded outcome payload with report reference/digest rather than transcript contents; assert reviewer instructions still require actual Git inspection and no implementation changes. Add a filesystem test only if the Pi adapter is version-controlled in the executing checkout; otherwise record this as an external adapter acceptance command.

- [ ] **Step 2: Run the focused test and confirm new assertions fail.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_extraction_acceptance`

Expected: FAIL on compact-return/current-discovery assertions, not on existing identity or permission assertions.

- [ ] **Step 3: Update portable role/profile text.** Add one concise shared return contract: report status/reference/digest; outcome lifecycle; bounded findings/verification; and no transcript/raw tool output. Keep role-specific responsibility, write boundary, and reviewer independence wording unchanged. Do not place harness-specific fields in portable role files.

- [ ] **Step 4: Update the Pi adapter.** Replace its v1.0.1 fixed contract location with discovery of the installed/current canonical contract. Require it to: pass artifact references not contents; request the compact result schema; keep child transcripts external; render/validate view after persisted transitions; and load detailed artifacts only for the documented debug/recovery exception. It must state Pi provenance remains advisory where canonical Codex evidence is unavailable.

- [ ] **Step 5: Run tests to green and manually inspect adapter diff.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_extraction_acceptance && git diff --check`

Expected: PASS and no whitespace errors.

- [ ] **Step 6: Commit repository-owned files; commit the adapter in its own distribution repository if applicable.**

```bash
git add plugins/kapisch/{agents,roles} plugins/kapisch/tests/kapisch_validation/test_extraction_acceptance.py
git commit -m "docs: bound KAPISCH role handoffs"
```

### Task 8: Add factual benchmark record validation and runbook

**Files:**

- Create: `plugins/kapisch/scripts/compare_controller_benchmark.py`
- Create: `plugins/kapisch/docs/controller-benchmark.md`
- Create: `plugins/kapisch/tests/kapisch_validation/fixtures/controller-benchmark/{baseline,candidate}.jsonl`
- Test: `plugins/kapisch/tests/kapisch_validation/test_controller_benchmark.py`

**Interfaces:**

- Consumes: JSONL records with `run_id`, `variant`, `role`, `invocation`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `turns`, `elapsed_ms`, `workflow_outcome`, `validator_exit`, `review_decision`, `review_findings`, `test_result`, and `resume_result`; unavailable numerics are literal `null`.
- Produces: read-only JSON summary comparing parent/children/total, invocation counts by role, unavailable fields, and acceptance-gate booleans without percentages or provider calls.

- [ ] **Step 1: Write failing parser/aggregation tests.** Assert the tool rejects duplicate `(run_id, role, invocation)`, negative numeric values, unsupported roles, incomplete terminal records, candidate missing a baseline task, and fabricated numeric zero in place of `null`. Assert it aggregates parent and child inputs/outputs/turns separately and preserves cache-read data as optional.

- [ ] **Step 2: Run test to verify script is missing.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_controller_benchmark`

Expected: FAIL with missing module/script import.

- [ ] **Step 3: Implement the read-only comparator.** Use `argparse`, `json`, and the standard library only. It accepts `--baseline FILE --candidate FILE --format json`, validates records, reports absolute values/deltas, and outputs `unavailable` rather than estimates. It must not declare release acceptance automatically; it reports whether required evidence fields are present and whether child work materially rose for a human decision.

- [ ] **Step 4: Write the benchmark runbook.** Define clean-worktree setup, the three exact task classes from the spec, baseline/candidate execution controls, required collection points, resume interruption points, raw JSONL retention location outside committed run evidence, and review of cache versus uncached input. State that numeric release thresholds are not set before baseline measurement.

- [ ] **Step 5: Run focused tests to green.**

Run: `python -m unittest plugins.kapisch.tests.kapisch_validation.test_controller_benchmark`

Expected: PASS.

- [ ] **Step 6: Commit benchmark tooling.**

```bash
git add plugins/kapisch/{scripts/compare_controller_benchmark.py,docs/controller-benchmark.md,tests/kapisch_validation}
git commit -m "test: add controller context benchmark tooling"
```

### Task 9: Run release-quality verification and benchmark acceptance

**Files:**

- Modify only if results reveal a defect in prior tasks; otherwise no source change.
- Create locally, untracked: benchmark raw JSONL and environment notes as directed by `plugins/kapisch/docs/controller-benchmark.md`.

**Interfaces:**

- Consumes: complete v4 implementation, installed/package copy, current adapters, and equivalent clean worktrees.
- Produces: factual before/after evidence; no speculative savings claim.

- [ ] **Step 1: Run all static/package gates.**

Run:

```bash
cd plugins/kapisch
python -m unittest discover -s tests/kapisch_validation
python scripts/test_portable_package.py
python scripts/validate_kapisch.py --help
python scripts/render_controller_view.py --help
python scripts/migrate_controller_view_v4.py --help
cd ../..
python -m unittest discover -s tests
git diff --check
```

Expected: every test suite and help command exits 0; `git diff --check` is empty.

- [ ] **Step 2: Validate all representative durable trees.**

Run:

```bash
cd plugins/kapisch
python scripts/validate_kapisch.py --task-dir tests/kapisch_validation/fixtures/valid-v4-controller --format json
```

Expected: `[]` and exit 0. Then run each invalid-v4 fixture and confirm exit 2 with the fixture’s documented primary error code.

- [ ] **Step 3: Execute benchmark baseline and candidate in equivalent clean worktrees.** Follow the runbook for behavioral, high-risk durable-with-fix, and worker/reviewer-resume scenarios. Record parent/child input/output/turns, cache reads, elapsed time, invocation counts, validator, review, correctness, and resume evidence exactly as observed.

- [ ] **Step 4: Compare factual records.**

Run:

```bash
cd plugins/kapisch
python scripts/compare_controller_benchmark.py \
  --baseline <baseline.jsonl> --candidate <candidate.jsonl> --format json
```

Expected: valid JSON with per-role and total absolute/delta measurements and no estimated values.

- [ ] **Step 5: Make the acceptance decision.** Accept only when parent uncached input and parent turns are materially lower across representative tasks; child input/turns have no material compensating increase; role separation, reviewer/final semantics, validator, durable artifacts, and both resume scenarios pass; and correctness is equal or better. If any condition is unavailable or fails, record it as a blocker and do not claim the optimization complete.

- [ ] **Step 6: Commit only source/doc/test corrections discovered by verified failures.** Keep benchmark raw records uncommitted unless a separately approved sanitized acceptance record is requested.

---

## Dependency order and review boundaries

1. Task 1 establishes v4 parsing and is required by every later task.
2. Task 2 adds authoritative attempt outcomes and must precede views.
3. Task 3 derives/validates views from Tasks 1–2.
4. Task 4 adds explicit writers/migration only after the pure validators exist.
5. Task 5 locks fixture-level compatibility after all validation paths exist.
6. Tasks 6 and 7 document/adapt the completed portable contract; neither may change validator semantics.
7. Task 8 supplies benchmark tooling; Task 9 is the final evidence gate.

Each numbered task is an independent review/commit boundary. Do not combine tasks, skip failing-test confirmation, or redesign the v4 contract during execution.
