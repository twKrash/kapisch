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

Last updated: GitHub state checked 2026-11-02. PR #85 is open and non-draft at head `1d86f83ef305f6cd4a16d7fb77d6838467ed28b7`, with four successful check runs; the latest formal review remains `CHANGES_REQUESTED` on `816abdb2827b166e609a03d9ed3a5a5b683a19fd`. The review reassessment is recorded in [PR comment #6590462154](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590462154); Finding 3's deferral is recorded in [PR comment #6590593116](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590593116). Findings 1 and 2 are superseded by current code, subject to the documented power-loss/storage-rollback limitation for finding 1. Finding 3 remains open and is deferred to a dedicated Pi harness-integration follow-up; AC7 remains partial. An aligned local Pi worker smoke at `.kapisch/runs/task-first-real-worker-smoke-2026-11-02-workorder-1/` used the tracked integration fixture's exact WorkOrder and decision identity and matched all nine persisted artifacts byte-for-byte with the deterministic adapter, including fresh-process reconstruction. A separate synthetic direct-prompt coordinator preflight is recorded below; neither local smoke is CI or real-user approval. Update this file when a slice changes state; never infer state from it.

## At a glance

- **Finished (implemented):** advisory and standalone review remain graph-free; the
  bounded one-task Pi-host execution contract and validation are locally implemented.
- **Current slice:** Pi pending-request HumanDecision capture and one-task WorkOrder acceptance have tracked tests. The aligned local real-Pi worker smoke at `.kapisch/runs/task-first-real-worker-smoke-2026-11-02-workorder-1/` used the tracked fixture's exact `workorder-1` and decision identity, validated the Git-bound input and persisted claim, matched all nine persisted artifacts byte-for-byte with the deterministic adapter, and passed fresh-process reconstruction. A separate synthetic direct-prompt coordinator smoke persisted one exact-prompt `direct_operator` decision and bound WorkOrder, then passed fresh-process dispatch validation without starting a worker. Both are local manual evidence, not CI or real-user approval; broader source/applicability coverage, interrupted resume, and multi-task acceptance remain unverified. The extension remains the producer for pending-request answers, while the coordinator owns direct-prompt records.
- **Submitted:** PR [#85](https://github.com/twKrash/kapisch/pull/85) is open, not draft, at head `1d86f83`; all four check runs pass. The latest formal review remains `CHANGES_REQUESTED` on `816abdb`; the current reassessment is in [PR comment #6590462154](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590462154). PR #84 is merged.
- **Historical verification:** one-task candidate path, local run, implementation-commit
  CI and test evidence at `8ed3f85`; superseded where it claimed Pi decision capture.
- **Current status:** tracked one-task contract tests and the aligned local real-worker smoke exist. Oracle assessment finds review findings 1 and 2 superseded by current code, with the known storage-rollback qualification for finding 1. Finding 3 remains valid for tracked acceptance and is deferred to a dedicated Pi harness-integration follow-up; AC7 remains partial. PR #85 is at `1d86f83` with four successful checks; formal review status remains `CHANGES_REQUESTED` on `816abdb`. The direct-prompt synthetic preflight is manual evidence only. Interrupted resume, scope-change reassessment, broader source coverage, and multi-task behavior remain unverified.
- **Remaining:** all 11 specification acceptance criteria are partial or unmet.
- **Review history:** the earlier K84-010 WorkOrder-binding finding was fixed with a regression assertion. The requested bounded standalone review of this seven-file docs/test delta found one confirmed P3 (K84-WT-001): assertions rejected equivalent Markdown line wrapping. The tests now normalize whitespace and test wrapped prose while retaining decision-binding and before-dispatch checks. The reviewer found no other diff-causal findings; this earlier review was not rerun after the fix and was not formal GitHub review approval.
- **Latest formal review:** The older P1 persisted-answer-consumption finding and K84-IND-001 (P2), raised against `1cbc5ac`, are fixed; both GitHub review threads are resolved. K84-IND-001 was fixed in PR head `c5c1457`, and the standalone reviewer re-reviewed that change with no new findings.
- **Blocked:** interrupted resume and full product acceptance remain open. Finding 3 is intentionally deferred to dedicated Pi harness integration; the tracked test is synthetic, so AC7 remains partial. The latest formal review still requests changes on `816abdb`; the reassessment comment asks the reviewer to reevaluate findings 1 and 2 against current code. The local real-worker smoke is not a CI check.
- **Next slice:** dedicated Pi harness integration for deferred Finding 3: exercise the
  same WorkOrder through real capability probing and start/collect, compare normalized
  results with the deterministic adapter, and verify unsupported/unknown/unproven
  capabilities block start. Keep AC7 partial until that tracked acceptance passes; then
  expand direct-path source/applicability coverage and interrupted resume. Keep multi-task
  scheduling, review gates, and remote-effect reconciliation in separate workstreams.
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
| WS-1 | First bounded one-task Pi-host slice (`WO-2026-10-26-PI-01/T01`): direct decision → WorkOrder → attempt → aggregation → Outcome → handoff | — | Durable one-task records; retry uses fresh attempt IDs and preserves prior work; review is advisory findings-only; fresh-session reconstruction | `PARTIAL / IN PROGRESS` | PR [#85](https://github.com/twKrash/kapisch/pull/85) open | Tracked tests cover one-task authorization and Attempt/report/Outcome reconstruction. A local real Pi worker smoke used Git-bound inputs and the same WorkOrder/decision identity as the test fixture, matched the deterministic adapter Outcome, and validated it from a fresh process. Retry and interrupted resume remain outside this slice. The current PR head `1d86f83` has four successful checks; the formal review still requests changes on `816abdb`. Finding 3 is deferred to harness integration, so AC7 remains partial. The manual smoke itself is not CI evidence. K84-IND-001 was fixed in `c5c1457` and re-reviewed with no new findings. |
| WS-1.1 | Consume one real decision end to end, from any approved source | WS-1 | A decision is persisted and cited by aggregation and Outcome with its scope and attribution | `IN PROGRESS` (one direct path smoke-tested; broader source coverage remains) | PR #84 merged; continuation in [#85](https://github.com/twKrash/kapisch/pull/85) | The tracked integration test exercises pending-request capture and a same-WorkOrder test adapter. A separate local direct-operator worker smoke cited one decision through WorkOrder, Attempt, aggregation, and Outcome; broader source/applicability coverage remains. |
| WS-1.2 | Track the acceptance harness in Git | WS-1 | Aggregation/Outcome/comparison validation runs from tracked code in CI | `IMPLEMENTED / AWAITING REVIEW` | PR [#85](https://github.com/twKrash/kapisch/pull/85) open | Tracked `tests/core/test_task_contract.py` and `harnesses/pi/tests/task-first.integration.test.ts` cover validation and same-WorkOrder comparison; local suites pass; current PR head `1d86f83` has four successful checks. The tracked integration test remains synthetic, and Finding 3 is deferred. The old `.kapisch/runs/…` harness is historical, not the source of test authority. |
| WS-1.3 | Decision source kinds: direct, operator-reported external, external artifact | WS-1 | Each source is captured with scope and attribution; ambiguous text and agent/reviewer output are never inferred as decisions | `IMPLEMENTED / AWAITING REVIEW` | PR #84 merged; current task-first continuation in [#85](https://github.com/twKrash/kapisch/pull/85) | Tracked tests cover pending-request source-kind fields; the earlier RPC smoke persisted an external-artifact decision with stable `source_ref`; a local task-first worker smoke used a synthetic `direct_operator` fixture. This verifies only those exercised paths, not all external-source applicability. Records omit host identity fields; no cryptographic or original-keystroke provenance is claimed or required. |
| WS-2 | Decision applicability, duplicate-question prevention, scope coverage | WS-1.1, WS-1.2 | AC2, including not re-requesting a decision reported from an external record | `TODO` | — | Guidance only (`resume.md`, Pi `SKILL.md`); no applicability field or test |
| WS-3 | Optional review gate: immutable report, required-lens pass, permitted exception | WS-1.2, WS-2 | AC5, applied only where a WorkOrder explicitly requires lenses; no gate for advisory or standalone review | `TODO` | — | `reviews.md` is a local advisory record; no gate and no exception binding |
| WS-4 | Multi-task DAG: parallel dispatch and aggregation barrier | WS-1.2 | AC3, AC7; independent of WS-3 | `TODO` | — | One task only; no scheduler, no terminal/interrupted handling |
| WS-5 | Local retry and checkpoint discipline | WS-1 | AC4: fresh attempt IDs; stale/incompatible checkpoints rejected; failed work preserved; shared work never reset | `TODO` | — | Retry/checkpoint execution remains outside the current one-task slice. The one-shot claim blocks replay, but retry and checkpoint compatibility are not implemented. |
| WS-6 | Ambiguous remote-effect gate | WS-2 | AC6: retry blocked until an authoritative outcome query or explicit scoped human authorization; local retries do not invoke it | `TODO` | Guidance only | Pi `SKILL.md` requires an exact `AUTHORIZE` answer; no enforcement or blocking test |
| WS-7 | Audience-neutral presentation invariance | — | AC9: an explicit style changes wording only; facts, evidence, decisions, authority identical | `TODO` | — | No style mechanism and no test |
| WS-8 | Packaging, install smoke test, validator retention, legacy cutover | WS-1.2, WS-4, WS-0 | AC10: reviewer install/invocation and new-format packaging verified before any legacy removal | `TODO` (removal correctly not started) | Pi package declares the extension | A fresh local Pi package install and one worker invocation succeeded in the smoke workspace. Reviewer installation/invocation, validator retention, and cutover acceptance remain unverified; `core/schemas/v3` and migrators are untouched. |
| WS-9 | Test-harness health and regression watch | — | Supported suites run as CI runs them; non-source artifacts classified; no source-caused regression hidden | `IMPLEMENTED / AWAITING REVIEW` | PR [#85](https://github.com/twKrash/kapisch/pull/85) open | Local supported suites pass; current PR head `1d86f83` has four successful checks, while the formal review still requests changes on `816abdb`. Root-level pytest and `.worktrees` artifacts are explained below. |

## Specification acceptance coverage

Coverage is independent of workstream status. Criteria are from specification §8.

| AC | Requirement (abbreviated) | Coverage | Evidence or gap |
| --- | --- | --- | --- |
| AC1 | Single-task SDLC flow reaches a durable Outcome, respecting human decisions and deployment authorization | partial | Tracked tests cover one-task authorization through durable Outcome; a local real Pi worker smoke used Git-bound inputs and a fresh-process validator. Deployment authorization, interruption/resume, review, and broader lifecycle behavior remain outside this slice. |
| AC2 | Decisions prevent duplicate questions; propagation preserves identity; substantive change reassesses; in-scope tasks need no per-task approval; out-of-scope blocks; external-record decisions are captured and not re-requested | partial | The package tests assert no redundant direct approval; a synthetic direct-prompt coordinator preflight persisted one exact-prompt decision and bound it to a WorkOrder, while the tracked extension tests cover pending-request capture. Propagation, scope-change reassessment, out-of-scope blocking, and external-record no-reprompt behavior remain unverified. |
| AC3 | Aggregation barrier at completion or terminal condition; all required tasks accounted for; failure report is evidence but does not release dependents | partial | Single task, parent-LLM aggregation, no terminal/interrupted handling |
| AC4 | In-scope retries use fresh IDs, preserve failed work, reject stale checkpoints, never reset shared work | partial | Retry and checkpoint execution are explicitly outside this two-PR slice. The one-task core prevents replay of a claimed attempt; it does not implement retry or checkpoint compatibility. |
| AC5 | Immutable review report; remediation alone does not release; new pass or separate exception does; prohibited exceptions block; gate only where a WorkOrder requires lenses | none | Advisory wording and a local report only; no gate |
| AC6 | Ambiguous remote effects block until authoritative observation or explicit scoped authorization | none | Guidance only |
| AC7 | Same WorkOrder yields equivalent logical status, authority, decisions, evidence, reports, Outcome via real and test adapters; missing capabilities block | partial | The aligned local worker smoke used the exact tracked WorkOrder/decision identity and matched all nine artifacts, but is local/manual. The tracked integration test still synthesizes output and hard-codes supported capability; it does not exercise actual Pi start/collect or capability probes at that boundary. Finding 3 is deferred to a dedicated Pi harness-integration follow-up; do not mark AC7 complete until tracked same-WorkOrder adapter and capability-boundary coverage exists. |
| AC8 | Fresh-session reconstruction without conversational or mutable derived authority | partial | A fresh Python controller process validated persisted WorkOrder, Decision, Attempt, report, and Outcome for both adapter roots. Reconstructing the next action after interruption and multi-task recovery remain untested. |
| AC9 | Presentation styles preserve normalized facts, evidence, decisions, authority | none | No mechanism or test |
| AC10 | Reviewer installation/invocation and new-format packaging verified before legacy removal | partial | Local Pi package install and one task-worker invocation succeeded in the smoke workspace. Reviewer installation/invocation, validator retention, and cutover acceptance remain unverified; nothing was removed. |
| AC11 | Advisory and standalone review remain graph-free, need no DAG or implementation authorization, and do not depend on the optional review gate | partial | Contract text merged and preserved; no dedicated test of the graph-free/no-gate property |

## Repository test health

The repository's supported harness is the CI sequence in
`.github/workflows/quality.yml` — `unittest`, run from the directory each job selects.
Root-level `pytest` is not that harness.

Current local verification for the task-first delta (2026-11-02):
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=core python3 -B -m unittest discover -s tests/core -q`
— 535 tests passed; `cd harnesses/pi && bun test tests/*.test.ts` — 47 passed;
`ruff check` and `ruff format --check` on the changed Python files — passed; `git diff
--check` — clean. These local checks are not CI. The current PR #85 head `1d86f83` has
four successful check runs. The formal review still requests changes on older head
`816abdb`; the current finding disposition is recorded in the PR reassessment comment.

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

1. **Interrupted resume and broader acceptance remain incomplete.** Tracked one-task
   acceptance tests cover WorkOrder, Attempt, report, Outcome, Git-bound input checks,
   and deterministic same-WorkOrder comparison. The retained local smoke at
   `.kapisch/runs/task-first-real-worker-smoke-2026-11-02/` also matched a real Pi worker
   Outcome to the deterministic adapter and passed fresh-process validation. PR #85
   check runs were in progress on pushed head `490cc99`; the latest review decision
    requests changes on `816abdb`;
   broader decision-source coverage, interruption recovery, multi-task work, and product
   acceptance remain open.

**Limitations (not blockers; block only the work that requires the guarantee)**

- Pi cannot enforce read-only review; the adapter declares it unsupported. Advisory
  research and standalone review remain available with the limitation disclosed. Only
  a WorkOrder that requires enforced read-only isolation blocks.
- **Historical smoke (2026-10-28):** the fresh Pi run consumed one direct HumanDecision
  through a simple WorkOrder, Attempt, aggregation, and Outcome in a non-Git workspace;
  it did not validate Git source freshness, resume, or cross-adapter equivalence. The
  earlier external-artifact RPC smoke used a synthetic reference and did not authenticate
  identity or validate the referenced artifact.
- Current tracked tests cover one-task acceptance and deterministic same-WorkOrder
  comparison. The actual Pi worker smoke is a separate local manual run retained under
  `.kapisch/runs/task-first-real-worker-smoke-2026-11-02/`; it is not a reusable harness or
  CI evidence. Direct-prompt record creation/consumption is still not a tracked runtime
  path; a synthetic coordinator preflight validated one persisted record and WorkOrder
  from a fresh process, but did not dispatch a worker. The extension test covers
  pending-request capture.
- Root-level pytest is not the supported harness and reports 21 false failures because
  those tests resolve paths relative to `plugins/kapisch`; the supported suites pass,
  and no green full-suite claim is made.

**Unknowns**

- The bounded one-task schemas, validation, and producer order are tracked in
  `core/contracts/task-first.md` and `core/kapisch_core/task_contract.py`. Extending
  those records to multi-task execution or interruption recovery remains a separate
  design and implementation decision.
- A synthetic direct-prompt coordinator preflight now exercises persisted decision
  creation, WorkOrder binding, and fresh-process validation. It is local/manual, not a
  real-user approval or worker run; no automated runtime fixture covers this path or its
  post-restart lookup. This remains a test-coverage gap, not an input-authenticity
  requirement.

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

**Keep the deferred Pi integration gap explicit, then expand beyond the bounded one-task slice.**

1. Findings 1 and 2 are superseded by current code and regression tests; preserve the
   explicit limitation that power-loss/storage rollback can still erase best-effort state.
2. Defer Finding 3 to a dedicated Pi harness-integration follow-up. Keep AC7 partial and
   do not claim completion until tracked tests use the same WorkOrder through actual Pi
   capability probing and start/collect, then compare it with the deterministic adapter.
3. Keep `.kapisch/runs/task-first-real-worker-smoke-2026-11-02/` as manual evidence, not CI.
   Add tracked direct-prompt producer coverage, interruption recovery, and broader adapter
   cases before claiming full AC7/AC8.

Rationale: the current tracked test exercises decision capture and portable validation,
not actual worker invocation. The aligned local smoke is useful but untracked. PR #85 head
`1d86f83` has four successful checks; the formal review still requests changes on
`816abdb`. The reassessment and deferral are documented in the PR comments. WS-3 (optional
review gate) follows; it is not a prerequisite for WS-4.

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
| Historical direct-prompt Pi smoke (local, non-Git, 2026-10-28) | One direct_operator decision cited through WorkOrder → Attempt → aggregation → Outcome; exact output bytes and ID references independently checked. No Git-bound inputs, resume, implementer-unavailable fallback verification, review, or cross-adapter comparison; not tracked or CI evidence. |
| Historical task-first real-worker smoke (`task-first-real-worker-smoke-2026-10-30`; artifact not present in this checkout) | The prior tracker described WorkOrder `workorder-1`, Decision `0e87d9f3-3df2-5466-b5bb-fe9e3c477658`, and Attempt `attempt-1`, but the referenced directory is absent from the current worktree. Do not rely on this row as current acceptance evidence; the aligned 2026-11-02 smoke below is verified in this checkout. | |
| Earlier task-first real-worker smoke (`task-first-real-worker-smoke-2026-11-02`; retained, local, gitignored; different WorkOrder from the tracked fixture) | WorkOrder `w1`, Decision `d1`, Attempt `a1`; real and deterministic adapter artifacts matched within that run. This evidence used a different logical WorkOrder from the tracked integration test, so it does not establish the same-WorkOrder criterion. Full artifact chains remain under `.kapisch/runs/task-first-real-worker-smoke-2026-11-02/`. | |
| Aligned task-first real-worker smoke (`task-first-real-worker-smoke-2026-11-02-workorder-1`; local, gitignored) | Actual Pi worker run `c4f57106-a9d5-4809-b8d5-2d8370647e1e` used the tracked fixture's `workorder-1` and decision `0e87d9f3-3df2-5466-b5bb-fe9e3c477658`. The worker wrote only the allocated output; all nine persisted artifacts matched the deterministic adapter byte-for-byte, and both Outcomes reconstructed in fresh Python processes. Aggregation was a fixed fixture; no LLM runtime was invoked. Output SHA-256: `c9f4f3308798ce36576aa54bac2d152e08ff38f70b43fbc4d07a24e1c4c80d41`. Local manual evidence, not CI; full evidence is under `.kapisch/runs/task-first-real-worker-smoke-2026-11-02-workorder-1/`. |
| Synthetic direct-prompt coordinator preflight (2026-11-02; local, gitignored) | In the dummy project `.kapisch/runs/task-first-real-worker-smoke-2026-11-02-workorder-1/real-worker/`, Run `.kapisch/runs/direct-prompt-coordinator-smoke/run.json` bound WorkOrder `workorder-ab493f6f6ae3413b839bafedc73b152f` to one `direct_operator` decision `decision-37e7fd9dd22345a8ba0fb72f40791d0d`. Fresh-process `validate_dispatch` passed; exact synthetic prompt in question/answer; one decision JSON; decision digest `040c6a66bb4bed98de68c1a8993cfd1d1b60efc9078e50db047bbe3d1bd5e768`; current Git input digest `d94fd107d92d87184ed0f5dcb9d659711e5b94ab5eaaef77b3173f2dfe399375`; source tree clean. Run stayed ready; no claim or worker output. Synthetic/manual evidence, not user approval or CI. |
| PR #85 state (GitHub read, 2026-11-02) | Open, non-draft, remote head `1d86f83ef305f6cd4a16d7fb77d6838467ed28b7`; four check runs successful; latest formal review remains `CHANGES_REQUESTED` on `816abdb2827b166e609a03d9ed3a5a5b683a19fd`; recorded base `c259d28363d862976f9c980a71faaee8a14a3895`. |
| Finding 3 deferral (operator decision, 2026-11-02) | Deferred to a dedicated Pi harness-integration follow-up; AC7 remains partial. [PR comment #6590593116](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590593116). |
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
