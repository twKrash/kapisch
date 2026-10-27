# Kapisch Product Realignment — Progress Tracker

**This is a human-visible SDLC progress record, not runtime authority.** It is not a
state machine, database, event ledger, or authority framework, and it does not replace
WorkOrder execution artifacts. Requirements live in the
[approved proposal](plans/2026-10-25-kapisch-product-realignment-proposal.md) and
[design specification](specs/2026-10-25-kapisch-product-realignment-design.md);
execution detail lives in per-run artifacts under `.kapisch/runs/<run-id>/` (local,
gitignored).

## Historical evidence and current status

The implementation and run evidence below records the earlier candidate at `8ed3f85`.
It is retained as historical evidence, but its decision-capture claims are superseded
for current Pi capability: the current Pi README, adapter skill, and
`extensions/human-decisions.ts` disable HumanDecision capture and direct-prompt
WorkOrder approval until immutable original-input provenance exists. The extension
only gates, repairs, or dismisses request blocks; it does not persist decisions or grant
authorization. Do not treat old
capture tests or run notes as proof of current capture support.

Last updated: 2026-10-27. Update this file when a slice changes state; never infer
state from it.

## At a glance

- **Finished (implemented):** advisory and standalone review remain graph-free; the
  one-task Pi-host slice, excluding decision capture.
- **Submitted:** Draft PR [#84](https://github.com/twKrash/kapisch/pull/84); not merged.
- **Historical verification:** one-task candidate path, local run, implementation-commit
  CI and test evidence at `8ed3f85`; superseded where it claimed Pi decision capture.
- **Current status:** no decision consumed end to end; Pi HumanDecision capture and
  direct-prompt WorkOrder approval are unavailable pending immutable original-input
  provenance or a separately verified adapter.
- **Remaining:** all 11 specification acceptance criteria are partial or unmet.
- **Review:** local advisory review completed findings-only; this is not GitHub approval.
- **Blocked:** formal GitHub review/approval remains pending for the unpushed local
  candidate; decision-required work remains blocked on Pi.
- **Next slice:** WS-1.2 harness work may proceed; WS-1.1 decision acceptance waits for a
  verified decision-capable adapter or immutable original-input provenance on Pi.
- **Overall realignment: NOT complete.**

## Status semantics

| Status | Meaning |
| --- | --- |
| `TODO` | Deliverable or criterion not met; no active work. |
| `IN PROGRESS` | Actively being worked in the current slice. |
| `BLOCKED` | Cannot proceed without a named external action or human decision. |
| `IMPLEMENTED / AWAITING REVIEW` | Written and locally checked; not accepted. |
| `DONE` | Merged, acceptance evidence verified, and any required review complete. |

Delivery is a separate axis: `local` → `draft PR` → `merged` → `verified`. A green
local run is not a merge; a merge is not acceptance. Cite a PR link for current
delivery state and keep SHAs only for historical implementation and verification
evidence. A WorkOrder `Outcome` marked complete covers its stated scope only.

## Workstreams

| ID | Objective | Depends on | Acceptance criteria | Status | Delivery | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| WS-0 | Advisory and standalone review stay first-class and graph-free | — | AC11: no WorkOrder, DAG, implementation authorization, or review gate; findings only | `IMPLEMENTED / AWAITING REVIEW` | Merged on `main`; preserved by PR #84 | `SKILL.md` advisory/review sections, `request-normalization.md`, `review.md`; no tracked test asserts the graph-free, no-gate property |
| WS-1 | One-task Pi-host slice (`WO-2026-10-26-PI-01/T01`): Context → WorkOrder → attempt → aggregation → advisory review → Outcome → handoff | — | Durable one-task records; retry uses fresh attempt IDs and preserves prior work; review is advisory findings-only; fresh-session reconstruction | `IMPLEMENTED / AWAITING REVIEW` (decision capability blocked on Pi) | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84), implementation commit `8ed3f85` (historical) | Historical: Pi package tests 22 pass; 9 decision-capture cases; local Outcome `complete` with attempts `A003` + `TEST-951202cef2e0`; `comparison.log` PASS. Current Pi README and adapter skill refuse capture and direct-prompt approval pending immutable original-input provenance. |
| WS-1.1 | Consume one real decision end to end, from any approved source | WS-1 | A decision is persisted and cited by aggregation and Outcome with its scope and attribution | `BLOCKED` on Pi pending immutable original-input provenance or a separately verified adapter | — | Run records `decision_refs: []`; prior capture unit tests are historical and superseded by the current Pi refusal. |
| WS-1.2 | Track the acceptance harness in Git | WS-1 | Aggregation/Outcome/comparison validation runs from tracked code in CI | `TODO` | `local` only | `compare.py`, `run.py`, `real_adapter.py`, `decision_records.py` and 16 comparator tests exist only under `.kapisch/runs/…` |
| WS-1.3 | Decision source kinds: direct, operator-reported external, external artifact | WS-1 | Each source is captured with scope and attribution; ambiguous text and agent/reviewer output are never inferred as decisions | `BLOCKED` on Pi pending immutable original-input provenance or a separately verified adapter | — | Historical `source_kind`, `source_ref`, `approving_party`, `operator_label` and capture tests at `8ed3f85` do not establish current capture. Current evidence is refusal/gating in the Pi README and adapter skill. |
| WS-2 | Decision applicability, duplicate-question prevention, scope coverage | WS-1.1, WS-1.2 | AC2, including not re-requesting a decision reported from an external record | `TODO` | — | Guidance only (`resume.md`, Pi `SKILL.md`); no applicability field or test |
| WS-3 | Optional review gate: immutable report, required-lens pass, permitted exception | WS-1.2, WS-2 | AC5, applied only where a WorkOrder explicitly requires lenses; no gate for advisory or standalone review | `TODO` | — | `reviews.md` is a local advisory record; no gate and no exception binding |
| WS-4 | Multi-task DAG: parallel dispatch and aggregation barrier | WS-1.2 | AC3, AC7; independent of WS-3 | `TODO` | — | One task only; no scheduler, no terminal/interrupted handling |
| WS-5 | Local retry and checkpoint discipline | WS-1 | AC4: fresh attempt IDs (met); stale/incompatible checkpoints rejected; failed work preserved; shared work never reset | `TODO` | `local` partial | Fresh-ID and prior-attempt preservation verified by regression test; no checkpoint compatibility logic |
| WS-6 | Ambiguous remote-effect gate | WS-2 | AC6: retry blocked until an authoritative outcome query or explicit scoped human authorization; local retries do not invoke it | `TODO` | Guidance only | Pi `SKILL.md` requires an exact `AUTHORIZE` answer; no enforcement or blocking test |
| WS-7 | Audience-neutral presentation invariance | — | AC9: an explicit style changes wording only; facts, evidence, decisions, authority identical | `TODO` | — | No style mechanism and no test |
| WS-8 | Packaging, install smoke test, validator retention, legacy cutover | WS-1.2, WS-4, WS-0 | AC10: reviewer install/invocation and new-format packaging verified before any legacy removal | `TODO` (removal correctly not started) | Pi package declares the extension | `package.json` `pi.extensions`; `core/schemas/v3` and migrators untouched |
| WS-9 | Test-harness health and regression watch | — | Supported suites run as CI runs them; non-source artifacts classified; no source-caused regression hidden | `IMPLEMENTED / AWAITING REVIEW` | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84) | CI-equivalent suites pass; root-level pytest and `.worktrees` artifacts explained below |

## Specification acceptance coverage

Coverage is independent of workstream status. Criteria are from specification §8.

| AC | Requirement (abbreviated) | Coverage | Evidence or gap |
| --- | --- | --- | --- |
| AC1 | Single-task SDLC flow reaches a durable Outcome, respecting human decisions and deployment authorization | partial | One-task Outcome exists locally; no decision consumed; no deployment boundary exercised; decision-required work blocks on Pi |
| AC2 | Decisions prevent duplicate questions; propagation preserves identity; substantive change reassesses; in-scope tasks need no per-task approval; out-of-scope blocks; external-record decisions are captured and not re-requested | partial | Decision applicability and duplicate-question behavior absent; current Pi does not capture decisions, so external-record decisions are not currently captured on Pi |
| AC3 | Aggregation barrier at completion or terminal condition; all required tasks accounted for; failure report is evidence but does not release dependents | partial | Single task, parent-LLM aggregation, no terminal/interrupted handling |
| AC4 | In-scope retries use fresh IDs, preserve failed work, reject stale checkpoints, never reset shared work | partial | Fresh IDs preserved; checkpoint rejection absent |
| AC5 | Immutable review report; remediation alone does not release; new pass or separate exception does; prohibited exceptions block; gate only where a WorkOrder requires lenses | none | Advisory wording and a local report only; no gate |
| AC6 | Ambiguous remote effects block until authoritative observation or explicit scoped authorization | none | Guidance only |
| AC7 | Same WorkOrder yields equivalent logical status, authority, decisions, evidence, reports, Outcome via real and test adapters; missing capabilities block | partial | One-task comparison PASS locally; harness untracked; historical capture evidence is superseded; current Pi capability refusal/gating is explicit |
| AC8 | Fresh-session reconstruction without conversational or mutable derived authority | partial | One-task state revalidated by a fresh process; not by an independent fresh agent session, and not for decisions or multi-task state |
| AC9 | Presentation styles preserve normalized facts, evidence, decisions, authority | none | No mechanism or test |
| AC10 | Reviewer installation/invocation and new-format packaging verified before legacy removal | none | Nothing removed (correct); no install smoke test; retention is a delegated decision |
| AC11 | Advisory and standalone review remain graph-free, need no DAG or implementation authorization, and do not depend on the optional review gate | partial | Contract text merged and preserved; no dedicated test of the graph-free/no-gate property |

## Repository test health

The repository's supported harness is the CI sequence in
`.github/workflows/quality.yml` — `unittest`, run from the directory each job selects.
Root-level `pytest` is not that harness.

CI-equivalent run in the clean feature worktree (2026-10-26):

| Suite | Result |
| --- | --- |
| Root `tests` (`unittest discover -s tests`) | pass |
| `tests/core`, `test_domain`, `test_bundle`, `tests/conformance` | pass |
| `plugins/kapisch` `tests/kapisch_validation` (490 tests) | pass |
| `scripts/test_portable_package.py`, validator `--help` | pass |
| `bun test harnesses/pi/tests/*.test.ts` (22) | pass |
| `bun run --cwd harnesses/pi check:generated` | current |

Two non-source artifacts were investigated; neither is a defect or a blocker:

- **Root-level pytest reports 21 failures** in `plugins/kapisch/tests/kapisch_validation/`.
  The same files pass 490/490 under the CI invocation (`cd plugins/kapisch && python -m
  unittest discover -s tests/kapisch_validation`) and under pytest run from
  `plugins/kapisch`. Those tests resolve fixture and reference paths relative to
  `plugins/kapisch`, so running pytest from the repository root is an unsupported
  invocation, not legacy breakage.
- **One marketplace failure appears only in the main checkout**, whose `.worktrees/`
  holds older worktrees; the test resolves a plugin manifest from
  `.worktrees/advisory-artifact-lifecycle/plugins/kapisch/…`. The clean worktree passes
  all marketplace tests, and CI has no such worktrees.

Source-caused regressions on the branch: none detected. Affected acceptance criteria:
none. The earlier "21 baseline failures" figure came from the unsupported root-level
pytest invocation, not from the legacy suites, so it is not a blocker for this
realignment.

## Blockers, limitations, and unknowns

**Blocker**

1. **Local advisory review completed.** K84-009 was reviewed findings-only; this is not
   GitHub approval. The local candidate is still unpushed, and formal PR review remains
   pending (`REVIEW_REQUIRED`).
2. **Decision-required work is blocked on Pi.** HumanDecision capture and direct-prompt
   WorkOrder approval remain unavailable until immutable original-input provenance
   exists or a separately verified adapter is available.

**Limitations (not blockers; block only the work that requires the guarantee)**

- Pi cannot enforce read-only review; the adapter declares it unsupported. Advisory
  research and standalone review remain available with the limitation disclosed. Only
  a WorkOrder that requires enforced read-only isolation blocks.
- No live HumanDecision has been consumed; the current extension only gates/repairs and
  does not persist decisions.
- The acceptance harness is untracked (WS-1.2).
- Root-level pytest is not the supported harness and reports 21 false failures because
  those tests resolve paths relative to `plugins/kapisch`; the supported suites pass,
  and no green full-suite claim is made.

**Unknowns**

- Canonical artifact schemas, field ownership, and publication order (§9) are still
  local conventions in an untracked run directory.
- Whether Pi can gain immutable original-input provenance or another adapter can be
  separately verified for decision capture.

## Escalations and delegated decisions

**Open owner escalations: none.** Escalate only if a choice changes product intent,
approved scope, human authority, security boundaries, external-effect permissions, or
introduces an unresolved material architectural trade-off. Merging and release remain
human actions; they are not escalation gates. Everything below is delegated engineering
work: decide it, record the choice and rationale, and report it.

| Delegated decision | Owner of the decision | Default direction |
| --- | --- | --- |
| Where the acceptance harness lives and when it lands | Implementation work | Next slice (WS-1.2) |
| Adapter used when lens gating is first required | Implementation work, after capability verification | Prefer a host whose enforcement is proven; Pi discloses its limitation |
| Validator/CLI retention or replacement | Implementation work | Keep a validator for the new format; remove legacy readers only after AC10 |
| Per-WorkOrder lens pass criteria and permitted exceptions | Implementation planning | Decide per WorkOrder; no new global exception layer |
| Artifact schema and producer ownership | Implementation planning | Smallest fields that satisfy the spec; no new subsystem |

Boundary: do not add new exceptions over V3 workflow rules. The existing one-task
host-native exception is already scoped and must not be widened.

## Next recommended vertical slice

**WS-1.2 harness work; WS-1.1 only after decision capability is verified.**

1. Move the artifact/aggregation/comparison harness from `.kapisch/runs/…` into
   tracked tests, keeping the same assertions.
2. Defer decision-backed aggregation and Outcome until immutable original-input
   provenance exists on Pi or a separately verified adapter can capture decisions.
3. Re-run the Pi and test-adapter comparison from tracked code once the required
   adapter capability is verified.

Rationale: harness work turns local-only claims into reviewable, CI-verifiable evidence;
it does not make decision capture available. WS-3 (optional review gate) follows; it is
not a prerequisite for WS-4.

## Evidence index

| Evidence | Identifier |
| --- | --- |
| Approved proposal / specification | PR #83 (merged); specification clarified 2026-10-26 |
| Plan assessment baseline | `fc31633` (per proposal §9) |
| Slice implementation (historical) | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84), commit `8ed3f85` |
| CI on the implementation commit (historical) | 4 check runs `SUCCESS`; `REVIEW_REQUIRED`; historical and superseded as evidence for current Pi decision capture |
| Focused verification (historical worktree) | `bun test` 22 pass; `check:generated` current; `pytest tests/core/test_review.py tests/core/test_package.py` 24 passed, 125 subtests; `git diff --check` clean; historical capture tests do not prove current capability |
| Test-harness triage | CI-equivalent suites pass on the branch; root-level pytest and `.worktrees` artifacts classified; failure-set diff shows no branch-only failures |
| Run evidence (historical, local, gitignored) | `.kapisch/runs/pi-task-first-2026-10-26-01/`: WorkOrder `WO-2026-10-26-PI-01`, attempt `A003`, test attempt `TEST-951202cef2e0`, `parent-generated-v2/{aggregation,outcome}.json`, `comparison.log` PASS, `cold-session-reconstruction.md`; no decision persisted |
| Current adapter capability evidence | Current Pi README, adapter `SKILL.md`, and `extensions/human-decisions.ts`: capture/direct-prompt approval unavailable; extension gates/repairs but does not persist decisions |
| Existing product roadmap (not this tracker) | `plugins/kapisch/docs/roadmap.md` |

## Update rules

- Update status only from repository evidence, a linked PR, CI, or a named run
  artifact. Do not mark `DONE` from a local run alone.
- Link the PR for current delivery state; use SHAs only for historical implementation
  or verification evidence. Do not require this file to name the commit that contains
  it.
- Keep failed, superseded, and blocked work visible. Do not delete rows; change status
  and add the reason.
- Do not expand the WorkOrder through this file. Scope changes need explicit human
  approval and a new WorkOrder.
