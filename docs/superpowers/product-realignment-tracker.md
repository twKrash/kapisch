# Kapisch Product Realignment — Progress Tracker

**This is a human-visible SDLC progress record, not runtime authority.** It is not a
state machine, database, event ledger, or authority framework, and it does not replace
WorkOrder execution artifacts. Requirements live in the
[approved proposal](plans/2026-10-25-kapisch-product-realignment-proposal.md) and
[design specification](specs/2026-10-25-kapisch-product-realignment-design.md);
execution detail lives in per-run artifacts under `.kapisch/runs/<run-id>/` (local,
gitignored).

## Historical evidence and current status

The implementation and run evidence below records earlier candidates, including
`8ed3f85`; those claims remain historical. At PR head `1cbc5ac`, the branch includes
pending-request HumanDecision capture and direct authorization for one bounded
WorkOrder. The coordinator persists one existing-format `direct_operator`
HumanDecision before dispatch, without a second approval question or input-provenance
requirement. Tracked Pi tests cover pending-request capture and direct-path contract
assertions; the full direct WorkOrder lifecycle is evidenced by one manual smoke, not a
tracked acceptance test. A fresh
Pi-Bolt smoke on 2026-10-28 exercised one direct prompt through a decision, WorkOrder,
one Pi-native worker attempt, aggregation, Outcome, and handoff in a disposable
non-Git workspace; the exact output bytes and artifact references were independently
checked. This was one instruction-driven run, not a tracked acceptance harness. It did
not establish the canonical-implementer-unavailable condition for native-worker
fallback, exercise Git-bound governing-input refs, resume from persisted state, or
compare equivalent WorkOrders across adapters. Do not treat it as full acceptance.

Last updated: 2026-10-30 (PR head `f8e9485`). Update this file when a slice changes state; never infer
state from it.

## At a glance

- **Finished (implemented):** advisory and standalone review remain graph-free; the
  bounded one-task Pi-host execution contract is locally documented.
- **Current slice:** Pi pending-request HumanDecision capture is covered by tracked
  tests and the earlier RPC smoke. A fresh real-Pi smoke also exercised one explicitly
  authorized direct prompt through a single coordinator-owned decision, WorkOrder,
  worker attempt, aggregation, Outcome, and handoff; output bytes and references
  matched. The extension remains the sole producer for pending-request answers, while
  the coordinator owns direct-prompt records. This single disposable non-Git run is
  not a tracked acceptance harness, did not establish the implementer-unavailable
  fallback condition, and did not test Git-bound input freshness, resume, or
  cross-adapter WorkOrder equivalence. The test-only external-source fixture still
  compares HumanDecision facts only.
- **Submitted:** Draft PR [#84](https://github.com/twKrash/kapisch/pull/84); not merged.
- **Historical verification:** one-task candidate path, local run, implementation-commit
  CI and test evidence at `8ed3f85`; superseded where it claimed Pi decision capture.
- **Current status:** the smoke produced one real direct-prompt decision → WorkOrder
  → attempt → aggregation → Outcome chain, but no reusable tracked WorkOrder acceptance
  harness or cross-adapter comparison exists. It used no Git-bound governing inputs
  and did not exercise resume or scope-change reassessment. Those broader behaviors
  remain unverified.
- **Remaining:** all 11 specification acceptance criteria are partial or unmet.
- **Review history:** the earlier K84-010 WorkOrder-binding finding was fixed with a regression assertion. The requested bounded standalone review of this seven-file docs/test delta found one confirmed P3 (K84-WT-001): assertions rejected equivalent Markdown line wrapping. The tests now normalize whitespace and test wrapped prose while retaining decision-binding and before-dispatch checks. The reviewer found no other diff-causal findings; this earlier review was not rerun after the fix and was not formal GitHub review approval.
- **Latest formal review:** the review of `1cbc5ac` requested changes for unresolved P2 K84-IND-001; see the blocker below.
- **Blocked:** formal review on head `1cbc5ac` requested changes for open finding
  K84-IND-001 (P2): a complete decision fence inside an HTML comment or `<pre>`
  example is recognized as a live request; malformed HTML examples can also alter
  capture behavior. The review requests parser exclusions and regression tests; this
  is not fixed by the documentation update. All four GitHub checks for `1cbc5ac`
  completed successfully, but green checks do not resolve the review finding. Tracked
  WorkOrder acceptance, cross-adapter comparison, Git-bound input freshness, and
  resume behavior also remain open.
- **Next slice:** add the tracked full WorkOrder-to-Outcome comparison and broader
  direct-path coverage, including implementer-unavailable routing, Git-bound inputs,
  applicability, and fresh-session resume.
- **Overall realignment: NOT complete.**

## Status semantics

| Status | Meaning |
| --- | --- |
| `TODO` | Deliverable or criterion not met; no active work. |
| `IN PROGRESS` | Actively being worked in the current slice. |
| `BLOCKED` | Cannot proceed without a named external action or human decision. |
| `IMPLEMENTED / AWAITING REVIEW` | The bounded deliverable is implemented and checked; acceptance or required review is still outstanding. |
| `PARTIAL / IN PROGRESS` | A bounded slice is delivered, but the workstream's stated acceptance criteria are not met. |
| `DONE` | Merged, acceptance evidence verified, and any required review complete. |

Delivery is a separate axis: `local` → `draft PR` → `merged` → `verified`. A green
local run is not a merge; a merge is not acceptance. Cite a PR link for current
delivery state and keep SHAs only for historical implementation and verification
evidence. A WorkOrder `Outcome` marked complete covers its stated scope only.

## Workstreams

| ID | Objective | Depends on | Acceptance criteria | Status | Delivery | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| WS-0 | Advisory and standalone review stay first-class and graph-free | — | AC11: no WorkOrder, DAG, implementation authorization, or review gate; findings only | `IMPLEMENTED / AWAITING REVIEW` | Merged on `main`; preserved by PR #84 | `SKILL.md` advisory/review sections, `request-normalization.md`, `review.md`; no tracked test asserts the graph-free, no-gate property |
| WS-1 | First bounded one-task Pi-host slice (`WO-2026-10-26-PI-01/T01`): direct decision → WorkOrder → attempt → aggregation → Outcome → handoff | — | Durable one-task records; retry uses fresh attempt IDs and preserves prior work; review is advisory findings-only; fresh-session reconstruction | `PARTIAL / IN PROGRESS` | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84); all four CI checks passed on reviewed head `1cbc5ac` | Tracked code captures pending-request decisions and implements coordinator-owned direct-prompt authorization/binding. One manual real-Pi smoke exercised a direct decision through WorkOrder, attempt, aggregation, Outcome, and handoff. The smoke was disposable and non-Git; it did not verify implementer-unavailable routing, Git-bound inputs, restart/resume, retries, review, or cross-adapter equivalence. Open review finding K84-IND-001 remains. |
| WS-1.1 | Consume one real decision end to end, from any approved source | WS-1 | A decision is persisted and cited by aggregation and Outcome with its scope and attribution | `IN PROGRESS` (one direct path smoke-tested; reusable acceptance remains) | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84) | A fresh direct-prompt Pi run persisted one decision and cited its ID through a WorkOrder, attempt, aggregation, and Outcome. This establishes one manual scenario, not a tracked/reusable consumer test or broader source/applicability coverage. |
| WS-1.2 | Track the acceptance harness in Git | WS-1 | Aggregation/Outcome/comparison validation runs from tracked code in CI | `TODO` | `local` only | `compare.py`, `run.py`, `real_adapter.py`, `decision_records.py` and 16 comparator tests exist only under `.kapisch/runs/…` |
| WS-1.3 | Decision source kinds: direct, operator-reported external, external artifact | WS-1 | Each source is captured with scope and attribution; ambiguous text and agent/reviewer output are never inferred as decisions | `IMPLEMENTED / AWAITING REVIEW` | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84) | Tracked tests cover pending-request source-kind fields; the earlier RPC smoke persisted an external-artifact decision with stable `source_ref`; the new direct-prompt smoke persisted a `direct_operator` decision. This verifies only those exercised paths, not all external-source applicability. Records omit host identity fields; no cryptographic or original-keystroke provenance is claimed or required. |
| WS-2 | Decision applicability, duplicate-question prevention, scope coverage | WS-1.1, WS-1.2 | AC2, including not re-requesting a decision reported from an external record | `TODO` | — | Guidance only (`resume.md`, Pi `SKILL.md`); no applicability field or test |
| WS-3 | Optional review gate: immutable report, required-lens pass, permitted exception | WS-1.2, WS-2 | AC5, applied only where a WorkOrder explicitly requires lenses; no gate for advisory or standalone review | `TODO` | — | `reviews.md` is a local advisory record; no gate and no exception binding |
| WS-4 | Multi-task DAG: parallel dispatch and aggregation barrier | WS-1.2 | AC3, AC7; independent of WS-3 | `TODO` | — | One task only; no scheduler, no terminal/interrupted handling |
| WS-5 | Local retry and checkpoint discipline | WS-1 | AC4: fresh attempt IDs (met); stale/incompatible checkpoints rejected; failed work preserved; shared work never reset | `TODO` | `local` partial | Fresh-ID and prior-attempt preservation verified by regression test; no checkpoint compatibility logic |
| WS-6 | Ambiguous remote-effect gate | WS-2 | AC6: retry blocked until an authoritative outcome query or explicit scoped human authorization; local retries do not invoke it | `TODO` | Guidance only | Pi `SKILL.md` requires an exact `AUTHORIZE` answer; no enforcement or blocking test |
| WS-7 | Audience-neutral presentation invariance | — | AC9: an explicit style changes wording only; facts, evidence, decisions, authority identical | `TODO` | — | No style mechanism and no test |
| WS-8 | Packaging, install smoke test, validator retention, legacy cutover | WS-1.2, WS-4, WS-0 | AC10: reviewer install/invocation and new-format packaging verified before any legacy removal | `TODO` (removal correctly not started) | Pi package declares the extension | A fresh local Pi package install and one worker invocation succeeded in the smoke workspace. Reviewer installation/invocation, validator retention, and cutover acceptance remain unverified; `core/schemas/v3` and migrators are untouched. |
| WS-9 | Test-harness health and regression watch | — | Supported suites run as CI runs them; non-source artifacts classified; no source-caused regression hidden | `IMPLEMENTED / AWAITING REVIEW` | Draft PR [#84](https://github.com/twKrash/kapisch/pull/84) | CI-equivalent suites pass; root-level pytest and `.worktrees` artifacts explained below |

## Specification acceptance coverage

Coverage is independent of workstream status. Criteria are from specification §8.

| AC | Requirement (abbreviated) | Coverage | Evidence or gap |
| --- | --- | --- | --- |
| AC1 | Single-task SDLC flow reaches a durable Outcome, respecting human decisions and deployment authorization | partial | One manual smoke completed the direct-authorized path through a durable Outcome, but no tracked acceptance test covers the lifecycle. It used no Git-bound inputs and did not exercise deployment authorization, retries, review, or resume. |
| AC2 | Decisions prevent duplicate questions; propagation preserves identity; substantive change reassesses; in-scope tasks need no per-task approval; out-of-scope blocks; external-record decisions are captured and not re-requested | partial | The package tests assert no redundant direct approval; one fresh Pi smoke persisted the original prompt as one direct decision and completed a matching WorkOrder without another question. Propagation, scope-change reassessment, out-of-scope blocking, and external-record no-reprompt behavior remain unverified. |
| AC3 | Aggregation barrier at completion or terminal condition; all required tasks accounted for; failure report is evidence but does not release dependents | partial | Single task, parent-LLM aggregation, no terminal/interrupted handling |
| AC4 | In-scope retries use fresh IDs, preserve failed work, reject stale checkpoints, never reset shared work | partial | Fresh IDs preserved; checkpoint rejection absent |
| AC5 | Immutable review report; remediation alone does not release; new pass or separate exception does; prohibited exceptions block; gate only where a WorkOrder requires lenses | none | Advisory wording and a local report only; no gate |
| AC6 | Ambiguous remote effects block until authoritative observation or explicit scoped authorization | none | Guidance only |
| AC7 | Same WorkOrder yields equivalent logical status, authority, decisions, evidence, reports, Outcome via real and test adapters; missing capabilities block | partial | Tracked tests compare Pi-persisted and external-test-adapter HumanDecision facts only. A fresh Pi smoke exercised one real WorkOrder-to-Outcome path, but no same-WorkOrder cross-adapter comparison, report equivalence, or capability-failure equivalence is claimed; the old minimal decision-application fixture remains excluded because it was not production integration. |
| AC8 | Fresh-session reconstruction without conversational or mutable derived authority | partial | Smoke artifacts were created in a fresh Pi session, but the run did not restart from pre-existing WorkOrder/decision files or reconstruct the next action after interruption; multi-task reconstruction is also untested. |
| AC9 | Presentation styles preserve normalized facts, evidence, decisions, authority | none | No mechanism or test |
| AC10 | Reviewer installation/invocation and new-format packaging verified before legacy removal | partial | Local Pi package install and one task-worker invocation succeeded in the smoke workspace. Reviewer installation/invocation, validator retention, and cutover acceptance remain unverified; nothing was removed. |
| AC11 | Advisory and standalone review remain graph-free, need no DAG or implementation authorization, and do not depend on the optional review gate | partial | Contract text merged and preserved; no dedicated test of the graph-free/no-gate property |

## Repository test health

The repository's supported harness is the CI sequence in
`.github/workflows/quality.yml` — `unittest`, run from the directory each job selects.
Root-level `pytest` is not that harness.

Current local verification for this follow-up (2026-10-28): `bun test
harnesses/pi/tests/*.test.ts` — 37 passed; `bun run --cwd harnesses/pi
check:generated` — passed; `git diff --check` — clean. These are local checks, not
GitHub CI. All four GitHub check runs passed on the last pushed head `796479b` (two
`ci`, two `windows-profile-setup`); this documentation/test follow-up was not part of
that run and needs separate CI evidence.

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

The 2026-10-26 CI-equivalent run found no source-caused regressions in that tested
range; it does not cover this current delta. The earlier "21 baseline failures" figure
came from the unsupported root-level pytest invocation, not from the legacy suites, so
it is not a blocker for this realignment.

## Blockers, limitations, and unknowns

**Blockers**

1. **Open review finding K84-IND-001 (P2).** The formal standalone review of head
   `1cbc5ac` found that a complete `kapisch-decision` fence inside an HTML comment or
   `<pre>` example is treated as a live request; malformed HTML examples can change
   capture behavior. The reviewer requested excluding raw HTML/comment contents from
   active fence discovery and adding regressions for examples, genuine requests, and
   malformed HTML. This remains unresolved; see
   [review thread](https://github.com/twKrash/kapisch/pull/84#discussion_r4416399995).
2. **Tracked end-to-end acceptance remains incomplete.** One real-Pi smoke consumed a
   direct decision in a simple WorkOrder and wrote an Outcome, but there is no tracked
   reusable WorkOrder consumer/comparison harness. Direct-path applicability, Git-bound
   input freshness, and resume/restart behavior remain unverified. CI success on
   `1cbc5ac` does not close either gap.

**Limitations (not blockers; block only the work that requires the guarantee)**

- Pi cannot enforce read-only review; the adapter declares it unsupported. Advisory
  research and standalone review remain available with the limitation disclosed. Only
  a WorkOrder that requires enforced read-only isolation blocks.
- The fresh Pi smoke consumed one direct HumanDecision through a simple WorkOrder,
  attempt, aggregation, and Outcome. It ran in a disposable non-Git workspace with no
  governing-input references; it did not validate Git source freshness, resume, or a
  general tracked acceptance consumer. The earlier external-artifact RPC smoke used a
  synthetic reference and did not authenticate identity or validate the referenced
  artifact. Decision cold-restart consumption remains unverified.
- The acceptance harness is untracked (WS-1.2).
- Root-level pytest is not the supported harness and reports 21 false failures because
  those tests resolve paths relative to `plugins/kapisch`; the supported suites pass,
  and no green full-suite claim is made.

**Unknowns**

- Canonical artifact schemas, field ownership, and publication order (§9) are still
  local conventions in an untracked run directory.
- The direct-prompt record now has one real-Pi smoke run, but no automated runtime
  fixture exercises its creation/consumption or post-restart lookup. This is an
  implementation/test-coverage gap, not an input-authenticity requirement.

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

**WS-1.2 tracked harness and WS-1.1 consumer integration.**

1. Keep the minimal external-source test adapter and comparison in tracked tests; do not
   reconstruct the old local harness framework.
2. Consume the persisted `HumanDecision` in the actual WorkOrder aggregation/Outcome path
   and verify applicability after a fresh restart.
3. Extend the same-WorkOrder comparison to reports, Outcome, and capability-failure
   behavior before claiming full AC7 acceptance.

Rationale: current evidence establishes pending-request capture, decision-level
portable-field comparison, and one real direct-prompt WorkOrder-to-Outcome smoke. The
smoke is not a tracked acceptance harness, cross-adapter comparison, or cold-restart
check. Full decision-to-Outcome acceptance remains incomplete. WS-3 (optional review
gate) follows; it is not a prerequisite for WS-4.

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
| Fresh direct-prompt Pi smoke (local, non-Git) | One direct_operator decision cited through WorkOrder → attempt → aggregation → Outcome; exact 15-byte output and ID references independently checked. No Git-bound inputs, resume, implementer-unavailable fallback verification, review, or cross-adapter comparison; not tracked or CI evidence. |
| Current adapter capability evidence | The Pi extension persists valid answers to explicit pending requests; tracked tests and an earlier `pi-bolt --mode rpc` smoke cover that capture path. A fresh `pi-bolt` smoke installed the local package and executed one explicitly authorized direct prompt through a single existing-format HumanDecision, WorkOrder, worker attempt, aggregation, Outcome, and handoff; the parent checked exact output bytes and matching references. Limitations: disposable non-Git workspace, no governing-input refs, no restart/resume, no test of the implementer-unavailable precondition for native-worker fallback, and no tracked cross-adapter comparison. This is one local scenario, not full acceptance or CI evidence. |
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
