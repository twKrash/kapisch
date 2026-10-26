# Kapisch Product Realignment — Progress Tracker

**This is a human-visible SDLC progress record, not runtime authority.** It is not a
state machine, database, event ledger, or authority framework, and it does not replace
WorkOrder execution artifacts. Requirements live in the
[approved proposal](plans/2026-10-25-kapisch-product-realignment-proposal.md) and
[design specification](specs/2026-10-25-kapisch-product-realignment-design.md);
execution detail lives in per-run artifacts under `.kapisch/runs/<run-id>/` (local,
gitignored).

Last updated: 2026-10-26. Update this file when a slice changes state; never infer
state from it.

## At a glance

- **Finished (implemented):** the one-task Pi-host slice — HumanDecision capture
  extension, one-task file-flow guidance, advisory review wording.
- **Submitted:** Draft PR [#84](https://github.com/twKrash/kapisch/pull/84) at
  `8ed3f85`, CI green, `REVIEW_REQUIRED`; not merged.
- **Verified:** the slice's own one-task path, locally, against
  `.kapisch/runs/pi-task-first-2026-10-26-01/`.
- **Not verified:** anything through independent review or merge; no live operator
  decision was consumed; the acceptance harness is untracked.
- **Remaining:** all 10 specification acceptance criteria are unmet or partial; none is met.
- **Blocked:** independent review of #84 (`pi-subagents` disabled in the authoring
  session); full-suite green (pre-existing failures, out of authorized scope).
- **Next slice:** WS-1.2 + WS-1.1 — version the one-task acceptance harness and
  consume one real TUI decision.
- **Overall realignment: NOT complete.**

## Status semantics

| Status | Meaning |
| --- | --- |
| `TODO` | Deliverable or criterion not met; no active work. |
| `IN PROGRESS` | Actively being worked in the current slice. |
| `BLOCKED` | Cannot proceed without a named external action or human decision. |
| `IMPLEMENTED / AWAITING REVIEW` | Code/docs written and locally checked; not accepted. |
| `DONE` | Merged, acceptance evidence verified, and any required review complete. |

Delivery is a separate axis and must not be collapsed into status:
`local` → `draft PR` → `merged` → `verified`. A green local run is not a merge; a
merge is not acceptance. A WorkOrder `Outcome` marked complete covers its stated
scope only.

## Workstreams

| ID | Objective | Depends on | Acceptance criteria | Status | Delivery | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | One-task Pi-host slice (`WO-2026-10-26-PI-01/T01`): Context → WorkOrder → attempt → aggregation → advisory review → Outcome → handoff | — | Durable one-task records; validated TUI-only decision capture; retry uses fresh attempt IDs and preserves prior work; review is advisory findings-only; fresh-session reconstruction | `IMPLEMENTED / AWAITING REVIEW` | Draft PR #84 `8ed3f85`; CI 4/4 success; `REVIEW_REQUIRED` | Pi package tests 22 pass; 9 decision-capture cases; local Outcome `complete` with attempts `A003` + `TEST-951202cef2e0`; `comparison.log` PASS |
| WS-1.1 | Consume one real operator decision end to end (TUI answer → aggregated report → Outcome) | WS-1 | A real decision is persisted and referenced by aggregation and Outcome (AC2 prerequisite) | `TODO` | `local` | Run records `decision_refs: []`; capture proven by unit tests only |
| WS-1.2 | Put the acceptance harness in Git so evidence is reproducible | WS-1 | Aggregation/Outcome/comparison validation runs from tracked code in CI, not a gitignored run directory (AC3, AC7, AC8) | `TODO` | `local` only | `compare.py`, `run.py`, `real_adapter.py`, `decision_records.py` and 16 comparator tests exist only under `.kapisch/runs/…` |
| WS-2 | HumanDecision applicability, duplicate-question prevention, scope coverage | WS-1.1, WS-1.2 | AC2: no repeated question; propagation preserves identity; substantive change triggers reassessment; in-scope DAG tasks need no per-task approval; out-of-scope work blocks | `TODO` | — | Guidance only (`resume.md`, Pi `SKILL.md`); no applicability field, no test |
| WS-3 | Review gate: immutable advisory report, required lens pass, permitted exception | WS-1, WS-2, WS-1.1 | AC5: report/verdict immutable; remediation alone does not release dependents; only a new pass or a separate permitted HumanDecision does; prohibited exception blocks | `TODO` | — | `reviews.md` is a local advisory record; no gate, no exception binding; Pi declares `read_only_review: unsupported` |
| WS-4 | Multi-task DAG: parallel dispatch and aggregation barrier | WS-1.2, WS-3 | AC3, AC7: barrier at batch completion or terminal/interrupted condition; accounts for failed, interrupted, cancelled, missing results; never waits indefinitely; coordinator validates coverage | `TODO` | — | One task only; no scheduler, no terminal-condition handling |
| WS-5 | Local retry and checkpoint discipline | WS-1 | AC4: fresh attempt IDs (met); stale/incompatible checkpoints rejected; failed work preserved; shared/user-owned work never reset | `TODO` | `local` partial | Fresh-ID and prior-attempt preservation verified by regression test; no checkpoint compatibility logic |
| WS-6 | Ambiguous remote-effect gate | WS-2 | AC6: retry blocked until an authoritative outcome query or explicit scoped human authorization; local retries do not invoke it | `TODO` | Guidance only | Pi `SKILL.md` requires an exact `AUTHORIZE` answer; no enforcement or blocking test |
| WS-7 | Audience-neutral presentation invariance | — | AC9: an explicit style changes wording only; normalized facts, options, evidence, decisions, authority identical | `TODO` | — | No style mechanism and no test |
| WS-8 | Packaging, install smoke test, validator retention, legacy cutover | WS-1 … WS-7 | AC10: reviewer install/invocation and new-format packaging verified before any legacy removal; no old-format migration | `TODO` (removal correctly not started) | Pi package declares the extension | `package.json` `pi.extensions`; `core/schemas/v3` and migrators untouched; no install smoke test |
| WS-9 | Repository suite health | — | Relevant suites green for changed areas; unrelated pre-existing failures triaged, not silently fixed | `BLOCKED` | — | Recorded baseline `fc31633`: 21 failures; dirty tree: 22 incl. an environmental marketplace failure from ignored `.worktrees/`; CI scoped jobs pass |

## Specification acceptance coverage

Coverage is independent of workstream status: a submitted slice can leave the criteria
it cites unmet. Criteria are from specification §8.

| AC | Requirement (abbreviated) | Coverage | Evidence or gap |
| --- | --- | --- | --- |
| AC1 | Single-task SDLC flow reaches a durable Outcome, respecting human decisions and deployment authorization | partial | One-task Outcome exists locally; no decision consumed; no deployment boundary exercised |
| AC2 | Decisions prevent duplicate questions; propagation preserves identity; substantive change reassesses; in-scope tasks need no per-task approval; out-of-scope blocks | none | Guidance only |
| AC3 | Aggregation barrier at completion or terminal condition; all required tasks accounted for; failure report is evidence but does not release dependents | partial | Single task, parent-LLM aggregation, no terminal/interrupted handling |
| AC4 | In-scope retries use fresh IDs, preserve failed work, reject stale checkpoints, never reset shared work | partial | Fresh IDs preserved; checkpoint rejection absent |
| AC5 | Immutable review report; remediation alone does not release; new pass or separate exception does; prohibited exceptions block | none | Advisory wording and a local report only |
| AC6 | Ambiguous remote effects block until authoritative observation or explicit scoped authorization | none | Guidance only |
| AC7 | Same WorkOrder yields equivalent logical status, authority, decisions, evidence, reports, Outcome via real and test adapters; missing capabilities block | partial | One-task comparison PASS locally; harness untracked; no capability-block path in tracked code |
| AC8 | Fresh-session reconstruction without conversational or mutable derived authority | partial | One-task state revalidated by a fresh process; not yet by an independent fresh agent session, and not for decisions or multi-task state |
| AC9 | Presentation styles preserve normalized facts, evidence, decisions, authority | none | No mechanism or test |
| AC10 | Reviewer installation/invocation and new-format packaging verified before legacy removal | none | Nothing removed (correct); no install smoke test |

## Blockers and unknowns

**Blockers**

1. **Independent review of PR #84 is outstanding.** `pi-subagents` was disabled in the
   authoring session, so no post-change reviewer ran. GitHub reports
   `REVIEW_REQUIRED`. Unblocks with a reviewer session or human review.
2. **Full repository suite is not green.** Recorded baseline at `fc31633` had 21
   failures; the dirty tree had 22, including an environmental marketplace failure
   caused by ignored `.worktrees/` manifests. Fixing unrelated legacy failures is
   outside the authorized scope. CI's scoped jobs pass.
3. **No live HumanDecision has been consumed.** The extension is unit-tested; the run
   records zero decisions, so applicability and citation behavior are unproven.
4. **Pi cannot enforce read-only review.** The adapter declares
   `read_only_review: unsupported`, so AC5 cannot be fully exercised on Pi alone.

**Unknowns**

- Canonical artifact schemas, field ownership, and publication order (§9) are still
  local conventions in an untracked run directory.
- Whether the validator/CLI is retained for the new format (§9).
- Whether Pi remains the first real adapter for review-lens acceptance, or Codex
  enforcement is verified instead.

## Decisions requiring human input

1. **Land WS-1.2 before the next slice?** Recommended: yes. Without tracked harness
   code, every later acceptance claim is local-only and unreviewable.
2. **Merge PR #84 as submitted, or extend it with the tracked harness first?**
   Either is defensible; extending keeps one reviewable acceptance story.
3. **First adapter for review-gate acceptance:** keep Pi with a documented
   read-only-review limitation, or verify Codex enforcement before AC5 work.
4. **Validator/CLI retention** for the new format (affects AC10 and later removal).
5. **Per-WorkOrder review-lens pass criteria and exception policy** (§9) must be
   chosen before WS-3 can be specified.

## Next recommended vertical slice

**WS-1.2 + WS-1.1 — make the one-task acceptance reproducible and decision-backed.**

1. Move the artifact/aggregation/comparison harness from `.kapisch/runs/…` into
   tracked tests and CI, keeping the same assertions.
2. Capture one real TUI operator decision, then have aggregation and Outcome cite it.
3. Re-run the Pi and test-adapter comparison from tracked code.

Rationale: it is the smallest slice that converts local-only claims into reviewable,
CI-verifiable evidence and exercises the immutable-decision invariant end to end.
It adds no product semantics. WS-3 (review gate) follows, because a gate without a
consumed decision has nothing to bind an exception to.

## Evidence index

| Evidence | Identifier |
| --- | --- |
| Approved proposal / specification | PR #83, merge `a65adc6` |
| Plan assessment baseline | `fc31633` (per proposal §9) |
| Slice implementation | Draft PR #84, commit `8ed3f85`, branch `feat/pi-task-first-slice` |
| CI on `8ed3f85` | 4 check runs `SUCCESS` (runs 40416527985, 40416556156); `REVIEW_REQUIRED` |
| Focused verification (worktree) | `bun test` 22 pass; `check:generated` current; `pytest tests/core/test_review.py tests/core/test_package.py` 24 passed, 125 subtests; `git diff --check` clean |
| Run evidence (local, gitignored) | `.kapisch/runs/pi-task-first-2026-10-26-01/`: WorkOrder `WO-2026-10-26-PI-01`, attempt `A003`, test attempt `TEST-951202cef2e0`, `parent-generated-v2/{aggregation,outcome}.json`, `comparison.log` PASS, `cold-session-reconstruction.md` |
| Adapter capability declaration | `.kapisch/runs/…/adapter/pi.json`: `read_only_review: unsupported`, `direct_user_decision: unproven` |
| Existing product roadmap (not this tracker) | `plugins/kapisch/docs/roadmap.md` |

## Update rules

- Update status only from evidence in this repository, a linked PR, CI, or a named
  run artifact. Do not mark `DONE` from a local run alone.
- Record the PR/commit and the verification command with its result; never cite a
  check that was not run.
- Keep failed, superseded, and blocked work visible. Do not delete rows; change status
  and add the reason.
- Do not expand the WorkOrder through this file. Scope changes need explicit human
  approval and a new WorkOrder.
