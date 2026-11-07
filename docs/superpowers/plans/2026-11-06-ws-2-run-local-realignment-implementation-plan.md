# WS-2 Run-Local Realignment Implementation Plan (PR #86 correction)

> Executed with the superpowers subagent-driven-development workflow (TDD, independent per-task review, final
> cumulative review). Binding spec: [WS-2 design addendum, Revision 3](../specs/2026-11-05-ws-2-decision-applicability-design.md).
> This plan **supersedes** the cross-Run and global-graph parts of the
> [Revision 2 plan](2026-11-05-ws-2-decision-applicability-implementation-plan.md) (its Tasks 1, 4 and 5 where they
> require cross-Run reuse, project-wide `decision_id` uniqueness or a project-wide supersession scan, and its
> Global Constraints on those points). Everything else in that plan stays in force.

**Goal:** Independent Runs share durable project knowledge but never share execution authority, and canonical Run
history survives the lifecycle of temporary source worktrees.

## Global constraints

- Plan approval does not authorize commits, pushes or merges. Changes stay uncommitted on top of 13aa9df.
- Markdown-first, LLM-owned semantic judgment; small deterministic kernel; no Python duplication of LLM reasoning;
  no database, global authority service, distributed lock or separate agent runtime; no global decision index or
  project-wide authority graph; no unrelated refactoring; no new dependencies.
- Keep immutable decisions, digest bindings, reassessment, applicability results, explicit supersession,
  fail-closed dispatch eligibility and the prospective dispatch-only boundary.
- Fail closed with deterministic `ContractError` messages (exact strings below); no accidental exceptions.
- Do not use Kapisch to execute work on Kapisch. Follow `/home/dvory/code/kapisch/AGENTS.md` and the
  `code-standards` skill. Module >350 lines or function >60 lines needs a coherent split or justification.
- TDD: tests first, observe RED, implement, GREEN. Rewrite or delete tests that require cross-Run reuse or global
  supersession; do not weaken retained tests.

## Exact kernel contract

| Condition | `ContractError` message |
| --- | --- |
| Run id (path, `run.json.run_id`) not canonical lowercase UUIDv4 | `invalid Run identity` |
| `decision_ref` well-formed but in another Run | `decision reference is outside its Run` |
| `supersedes[*].decision_ref` in another Run than the superseder | `supersedes target is outside its Run` |
| decision record `run_id` missing, not a string, or not the owning Run | `decision run mismatch` |
| roots unusable (missing, not checkout roots, different repository, `state_root` not the primary working tree) | `invalid state_root/source_root mapping` |

Unchanged messages stay (`malformed decision reference`, `missing referenced decision`, `decision identity is not
unique or reference mismatches`, `supersedes target is missing`, `decision is superseded: <id>`, freshness
errors, ...). UUIDv4 regex: `[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`.
Check order inside `_validate_workorder` and error precedence from Revision 2 stay as they are; the new Run-local
checks are added where the corresponding decision reference is already validated.

## File map

| File | Change |
| --- | --- |
| `core/kapisch_core/_task_artifacts.py` | `_RUN_ID` pattern |
| `core/kapisch_core/_task_decisions.py` | Run-scoped path/uniqueness/ownership |
| `core/kapisch_core/_task_supersession.py` | Run-scoped scan/targets |
| `core/kapisch_core/_task_authority.py` | pass Run directory and `source_root` |
| `core/kapisch_core/_task_governing_inputs.py` | freshness against `source_root` (parameter rename only) |
| `core/kapisch_core/_task_roots.py` (new) | `_validated_roots` |
| `core/kapisch_core/task_contract.py` | UUIDv4 Run id; `state_root` + keyword `source_root` on all public entry points |
| `harnesses/pi/extensions/human-decisions.ts` | required Run id, record `run_id`, primary-checkout storage |
| `harnesses/pi/tests/*.test.ts`, `tests/core/test_task_contract.py`, `tests/core/test_package.py` | tests |
| `core/contracts/task-first.md`, `harnesses/pi/README.md`, `harnesses/pi/skills/kapisch/SKILL.md`, tracker, old plan banner | documentation |

## Task 1: Run identity and Run-local decision authority (Python core)

**Files:** modify `_task_artifacts.py`, `_task_decisions.py`, `_task_supersession.py`, `_task_authority.py`,
`task_contract.py`; tests in `tests/core/test_task_contract.py`.

Requirements
1. `_run_directory` (task_contract.py) requires the canonical UUIDv4 Run id in the path and in `run.json`
   (`invalid Run identity`); keep the existing portable-reference mismatch error for a valid-but-mismatching id.
2. `_validate_decision_path` takes the owning `run_directory`; after the existing shape/symlink checks, a
   well-formed ref not under `<run_directory>/decisions/` raises `decision reference is outside its Run`.
3. `_validate_unique_decision_reference` globs only `<run_directory>/decisions/*.json`.
4. `_read_decision_record` additionally requires decision `run_id` == owning Run id (`decision run mismatch`),
   checked after the filename/identity check. `run_id` is part of the decision record; no other record changes.
5. `_scan_decisions(root, run_directory)` enumerates only the owning Run; duplicate `decision_id` within the Run
   is an error; other Runs are never opened.
6. `supersedes` targets must be in the same Run directory (`supersedes target is outside its Run`), checked
   before target existence.
7. `validate_dispatch` scans only the target Run; `_validate_workorder` passes `run_directory` to every decision
   load. Acceptance/Outcome paths keep the Revision 2 behavior (no graph scan) and now scan nothing outside the Run.
8. Existing fixtures use non-UUID Run ids and decision records without `run_id`: update the shared test helpers
   once (UUIDv4 constants; `run_id` in decision builders); do not hand-edit each test.

Tests (names are required; all `test_ws2_rl_*`)
- `test_ws2_rl_two_runs_independent_decisions`: two Runs, distinct ids, each dispatch valid with its own decision.
- `test_ws2_rl_same_decision_id_allowed_in_different_runs`: same `decision_id` file name in two Runs validates in both.
- `test_ws2_rl_cross_run_decision_ref_rejected` (+ digest correct, other Run exists): exact error.
- `test_ws2_rl_cross_run_supersedes_target_rejected`.
- `test_ws2_rl_supersession_in_run_a_does_not_affect_run_b`: superseder in A for decision X; B referencing a
  same-id decision stays dispatchable; A's target is blocked.
- `test_ws2_rl_other_run_malformed_decision_ignored`: garbage file in Run B's `decisions/` does not fail Run A.
- `test_ws2_rl_decision_run_id_required_and_must_match` (missing, wrong string, non-string).
- `test_ws2_rl_run_id_must_be_uuid4` (path form, `run.json.run_id` form, uppercase, v1/v5-like, short).
- `test_ws2_rl_completed_outcome_unaffected_by_later_supersession` (kept semantics, Run-local).
- `test_ws2_rl_cold_process_reconstruction` (fresh subprocess with only persisted files validates).
- Delete/rewrite: `test_ws2_cross_run_reuse_has_one_original`, project-wide uniqueness and global-scan tests; keep
  and adapt the rest (attribution, applicability statuses, reassessment, empty-historical, one-read-per-call,
  retention failures, kernel never mutates decisions).

## Task 2: state_root / source_root split (Python core)

**Files:** create `_task_roots.py`; modify `task_contract.py`, `_task_authority.py`,
`_task_governing_inputs.py`; tests in `tests/core/test_task_contract.py` (use real `git init` + `git worktree add`).

Requirements
1. `_task_roots._validated_roots(state_root, source_root) -> tuple[Path, Path]` (resolved, strict) accepts only:
   existing directories that are Git checkout roots (`git rev-parse --show-toplevel` equals the path); same
   common Git directory; `state_root` is the primary working tree (`--git-dir` == `--git-common-dir` and that
   directory is `<state_root>/.git`). Else `invalid state_root/source_root mapping`. Git subprocess failures map
   to the same error. It may be the same directory for both. No discovery, no env lookup, no guessing.
2. Public API: `validate_run`, `validate_dispatch`, `claim_dispatch`, `validate_acceptance`,
   `validate_outcome` take `state_root` (first positional; replaces `root`) and a **required keyword-only**
   `source_root`. Each validates the pair once at entry. Private functions take the resolved `state`/`source`.
3. `source_root` is used only for governing-input freshness (`_task_governing_inputs`: `git -C`, working-tree
   read, `is_relative_to` confinement); everything under `.kapisch/` uses `state_root`. Update the escape error
   wording only if a test requires; otherwise keep messages.
4. No new persisted field; the Run records no machine path.

Tests (`test_ws2_rl_*`)
- `..._roots_same_directory_ok`.
- `..._state_in_primary_inputs_validated_against_feature_worktree`: inputs modified+committed in the worktree
  validate with `source_root=worktree` and fail with `requires reassessment` against the primary.
- `..._run_validates_after_worktree_removed` (`git worktree remove`; passes with `source_root=primary` when inputs
  match; Run files still present; with the removed path as `source_root` → mapping error).
- `..._mapping_fails_closed` parametrized: nonexistent root; plain non-git directory; subdirectory of a repo;
  `state_root` is a linked worktree; roots from two different repositories; bare repository as state; file instead
  of directory. Each for validate_run and one lifecycle entry point.
- `..._state_files_never_written_under_source_root` (claim_dispatch from a worktree writes only to the primary).
- `..._source_root_keyword_required` (TypeError is acceptable and documented: signature contract).
- Update every existing call site to pass `source_root=<same root>` through the shared test helper.

## Task 3: Pi producer and integration (TypeScript)

**Files:** `harnesses/pi/extensions/human-decisions.ts`, `harnesses/pi/tests/human-decisions.test.ts`,
`harnesses/pi/tests/task-first.integration.test.ts`. No other Pi changes.

Requirements
1. `run_id` becomes a required request field matching the UUIDv4 pattern; a request without it or with a
   malformed one is an invalid request (existing invalid-request handling, no recording).
2. Remove the Pi session-id identity fallback entirely; identity is the Run id. The decision record gains
   `run_id`. `decision_id` derivation is unchanged in form (hash of identity and `question_id`).
3. Storage root: derive the primary checkout from `context.cwd` with Git using the same acceptance rule as the
   kernel (`cwd` inside a repository; common dir is `<primary>/.git`; primary is its own working tree). Any
   failure (not a repository, bare/separate git dir, git unavailable) → existing "could not be read or safely
   written" path, nothing recorded. Keep the existing realpath/confinement checks, now against the primary
   checkout. A session in a linked worktree stores under the primary; nothing is created in the worktree.
4. Workers/reviewers/coordinator behavior unchanged: only the human-input boundary writes.
5. Integration test: update the Python subprocess calls to the new signatures; add a scenario with a linked
   worktree (decision stored in primary; `claim_dispatch` with `source_root=worktree`; remove the worktree;
   `validate_outcome` from a fresh process with `source_root=primary`).

Tests
- Required/malformed/missing `run_id` fail closed (no file written); legacy session-fallback test is replaced.
- Decision file lands in `<primary>/.kapisch/runs/<run_id>/decisions/` when `cwd` is a linked worktree, and not
  in the worktree; record contains `run_id`.
- Unresolvable root (non-git `cwd`) fails closed with no file written.
- Retained: source attribution, idempotence/EEXIST handling, symlink confinement, verbatim answer, workers cannot
  record.

## Task 4: Contracts, guidance, tracker

**Files:** `core/contracts/task-first.md`, `harnesses/pi/README.md`, `harnesses/pi/skills/kapisch/SKILL.md`,
`docs/superpowers/product-realignment-tracker.md`, banner in the Revision 2 plan, `tests/core/test_package.py`
(structural checks only), `harnesses/pi/tests/package.test.ts` if it asserts moved text.

Requirements: describe exactly Revision 3 (spec §2–§4, §2.6, §2.7): Run id minting and exclusive creation;
`state_root`/`source_root` and where each record is written; Run-local decisions and the project-knowledge
procedure (cite sources, obtain a Run-local decision; PR merge makes artifacts shared knowledge but does not
promote decisions); decision request now requires `run_id`; single-writer model and post-claim same-Run supersession re-read;
retention in `state_root`; stable errors and the labelled JSON block updated to the exact messages above. Remove
every statement of cross-Run reuse / global graph. Tracker: replace the cross-Run semantics, mark WS2-KR-002 resolved by the Run-local model and post-claim re-read, keep AC2 partial and WS-4 dependency, update evidence and
test counts only from real runs. Package checks assert labels/constants, never prose.

## Verification (controller, on the final tree)

`PYTHONPATH=core python -m unittest discover -s tests/core`; `-s tests/conformance`; `python
tooling/build/build_bundle.py --check`; `python3.11 -m unittest tests.core.test_task_contract`; `cd harnesses/pi
&& bun test tests/*.test.ts && bun scripts/generate-agents.ts --check`; ruff check/format on changed Python;
`code-gates run` on staged copies via temporary index (dryer, crapper with real coverage); mutator in a scratch
copy on changed production lines; final standalone `kapisch-reviewer` review.
