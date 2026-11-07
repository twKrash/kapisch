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

Last updated: 2026-11-06; local state checked point-in-time. GitHub state last checked
2026-11-06 via PR list: PR #85 merged at 2026-11-05T07:57:33Z (merge commit
`93bc222`, "feat(core): task-first portable acceptance contract and bounded Pi integration
(#85)"). Its last formal review was `APPROVED` on implementation head `2885a1e`; four
CI checks succeeded. Execution order was amended on 2026-11-05: see the
[execution-order amendment](plans/2026-11-05-kapisch-execution-order-amendment.md) and
[Execution order](#execution-order) below. The review reassessment is recorded in [PR
comment #6590462154](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590462154);
Finding 3's deferral is recorded in [PR comment
#6590593116](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590593116).
Findings 1 and 2 are superseded by current code, subject to the documented power-loss/
storage-rollback limitation for finding 1. P2-008 is fixed in commit `2885a1e`; P2-009
is an operator-accepted filesystem-integrity limitation. See [PR comment
#6643639447](https://github.com/twKrash/kapisch/pull/85#issuecomment-6643639447).
Finding 3 remains open and is deferred to a dedicated Pi harness-integration follow-up;
AC7 remains partial. An aligned local Pi worker smoke at
`.kapisch/runs/task-first-real-worker-smoke-2026-11-02-workorder-1/` used the tracked
integration fixture's exact WorkOrder and decision identity and matched all nine
persisted artifacts byte-for-byte with the deterministic adapter, including fresh-process
reconstruction. A separate synthetic direct-prompt coordinator preflight is recorded
below; neither local smoke is CI or real-user approval. Update this file when a slice
changes state; never infer state from it.

## At a glance

- **Finished (implemented):** advisory and standalone review remain graph-free; the
  bounded one-task Pi-host execution contract and validation are locally implemented.
- **Current slice:** WS-2 (Run-local decision applicability, reassessment, and
  supersession) is implemented locally and uncommitted on
  `feat/ws-2-decision-applicability`, based on `13aa9df`. Revision 3 removes
  cross-Run authority reuse; decisions, uniqueness checks, and supersession are
  confined to one Run. AC2 remains partial because WS-4 owns task-level scope
  coverage and per-task authorization bindings. Local verification (2026-11-06,
  not CI) passed; see the WS-2 row.
- **Submitted:** PR [#85](https://github.com/twKrash/kapisch/pull/85) is merged
  (`93bc222`); its last formal review was `APPROVED` and four CI checks succeeded.
  PR #84 is merged.
- **Historical verification:** one-task candidate path, local run, implementation-commit
  CI and test evidence at `8ed3f85`; superseded where it claimed Pi decision capture.
- **Current status:** PR #85 is merged. WS-2 Revision 3 implementation and
  contract alignment remain local and uncommitted, awaiting owner review and merge.
  Local suites pass (not CI); broader scope and multi-task behavior remain
  unverified. Overall realignment is not complete.
- **Review history:** the earlier K84-010 WorkOrder-binding finding was fixed with a
  regression assertion. The requested bounded standalone review of this seven-file
docs/test delta found one confirmed P3 (K84-WT-001): assertions rejected equivalent
  Markdown line wrapping. The tests now normalize whitespace and test wrapped prose while
  retaining decision-binding and before-dispatch checks. The reviewer found no other
diff-causal findings; this earlier review was not rerun after the fix and was not formal
GitHub review approval.
- **Latest formal review:** The older P1 persisted-answer-consumption finding and
  K84-IND-001 (P2), raised against `1cbc5ac`, are fixed; both GitHub review threads are
  resolved. K84-IND-001 was fixed in PR head `c5c1457`, and the standalone reviewer
  re-reviewed that change with no new findings.
- **Blocked:** interrupted resume and full product acceptance remain open. Finding 3 is
  intentionally deferred to Phase 4 real-harness integration (WS-11); the tracked test
  is synthetic, so AC7 remains partial. The earlier `CHANGES_REQUESTED` review on
  `816abdb` is superseded by the later `APPROVED` formal review. The local real-worker
  smoke is not a CI check.
- **Next slice:** Complete and verify the WS-2 Run-local contract, then WS-4
  (DAG, dependencies, task scope coverage, and per-task authorization) is next.
  WS-5 and WS-6 follow in Phase 1, then portable reviewer contracts (Phase 2),
  harness-neutral conformance (Phase 3), and real Pi/Claude adapters (Phase 4).
  See [Next recommended vertical slice](#next-recommended-vertical-slice).
- **Overall realignment: NOT complete.**

## Execution order

The owner-approved order (2026-11-05, [amendment](plans/2026-11-05-kapisch-execution-order-amendment.md)) is: harness-agnostic core, then portable reviewer contracts and lenses, then harness-neutral conformance, then real harness adapters. It changes sequencing only; requirements and AC1–AC11 are unchanged. Phase details, deliverables, and acceptance boundaries live in the amendment; this tracker records status and dependencies.

| Phase | Name | Workstreams |
| --- | --- | --- |
| 0 | Bounded single-task foundation (PR #85) | WS-1, WS-1.1, WS-1.2, WS-1.3, WS-9 |
| 1 | Harness-agnostic orchestration core | WS-2, WS-4, WS-5, WS-6 |
| 2 | Portable reviewer contracts and document lenses | WS-3.1, WS-3 |
| 3 | Harness-neutral conformance | WS-10 |
| 4 | Real harness integration, then packaging and cutover | WS-11 (Pi), WS-12 (Claude), then WS-8 |

WS-0 (graph-free advisory/review) is preserved throughout. WS-7 (presentation invariance) has no host dependency and is not sequenced by the amendment.

**Dependencies.** A workstream's *Depends on* lists hard dependencies. Phase order adds an owner-directed *sequencing dependency* between phases (Phase 2 after Phase 1, Phase 3 after Phases 1 and 2, Phase 4 after Phase 3); it is not a technical coupling and changes only by owner decision. Phase 0–3 workstreams do not depend on Pi or Claude integration. Evidence class matters: deterministic or fake-adapter evidence (Phases 1–3) never completes a real-adapter criterion (Phase 4), and local manual smokes are supporting evidence only.

## Status semantics

| Status | Meaning |
| --- | --- |
| `TODO` | Deliverable or criterion not met; no active work. |
| `IN PROGRESS` | Actively being worked in the current slice. |
| `BLOCKED` | Cannot proceed without a named external action or human decision. |
| `IMPLEMENTED / AWAITING REVIEW` | The bounded deliverable is implemented and checked; acceptance or required review is still outstanding. |
| `IMPLEMENTED / AWAITING MERGE` | The bounded deliverable is implemented, checked, and its required review is approved; only the merge (a human action) is outstanding. |
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
| WS-1 | First bounded one-task Pi-host slice (`WO-2026-10-26-PI-01/T01`): direct decision → WorkOrder → attempt → aggregation → Outcome → handoff | — | Durable one-task records; retry uses fresh attempt IDs and preserves prior work; review is advisory findings-only; fresh-session reconstruction | `PARTIAL / IN PROGRESS` | Merged via PR #85 | Tracked tests cover one-task authorization and Attempt/report/Outcome reconstruction. A local real Pi worker smoke used Git-bound inputs and the same WorkOrder/decision identity as the test fixture, matched the deterministic adapter Outcome, and validated it from a fresh process. Retry and interrupted resume remain outside this slice. PR #85 had four successful checks and an `APPROVED` formal review as of 2026-11-05 (see above). Finding 3 is deferred to Phase 4 real-harness integration (WS-11), so AC7 remains partial. The manual smoke itself is not CI evidence. K84-IND-001 was fixed in `c5c1457` and re-reviewed with no new findings. |
| WS-1.1 | Consume one real decision end to end, from any approved source | WS-1 | A decision is persisted and cited by aggregation and Outcome with its scope and attribution | `IN PROGRESS` (one direct path smoke-tested; broader source coverage remains) | PR #84 merged; continuation in [#85](https://github.com/twKrash/kapisch/pull/85) | The tracked integration test exercises pending-request capture and a same-WorkOrder test adapter. A separate local direct-operator worker smoke cited one decision through WorkOrder, Attempt, aggregation, and Outcome; broader source/applicability coverage remains. Remaining work splits by owner: portable source/applicability coverage is WS-1.3 and WS-2; Pi producer-path coverage (pending-request extension, direct-prompt coordinator) is WS-11. |
| WS-1.2 | Track the acceptance harness in Git | WS-1 | Aggregation/Outcome/comparison validation runs from tracked code in CI | `DONE` | merged (PR #85, `93bc222`) | Tracked `tests/core/test_task_contract.py` and `harnesses/pi/tests/task-first.integration.test.ts` cover validation and same-WorkOrder comparison; PR #85 had four successful checks and an approved review as of 2026-11-05. The tracked Pi integration test remains synthetic; Finding 3 is deferred to WS-11 (Phase 4) and is not a prerequisite for Phase 1. The old `.kapisch/runs/…` harness is historical, not the source of test authority. |
| WS-1.3 | Decision source kinds: direct, operator-reported external, external artifact | WS-1 | Each source is captured with scope and attribution; ambiguous text and agent/reviewer output are never inferred as decisions | `IMPLEMENTED / AWAITING REVIEW` | Merged via #85 | Tracked tests cover pending-request source-kind fields; the earlier RPC smoke persisted an external-artifact decision with stable `source_ref`; a local task-first worker smoke used a synthetic `direct_operator` fixture. This verifies only those exercised paths, not all external-source applicability. Records omit host identity fields; no cryptographic or original-keystroke provenance is claimed or required. |
| WS-2 | Phase 1. Run-local decision applicability, provenance, reassessment, and explicit supersession | WS-1.2 | AC2 decision-level clauses: identity propagation, applicability/reassessment, and external-source provenance. Task-level in-scope/out-of-scope rules and per-task bindings remain WS-4; AC2 stays partial | `IMPLEMENTED / AWAITING PR REVIEW` | local on `feat/ws-2-decision-applicability` (base `13aa9df`) | Revision 3 kernel, Pi adapter, tests, and aligned contract are implemented. No cross-Run decision reuse or global authority graph. WS2-KR-002 is closed: the Run-local architecture removes the cross-Run race, and `claim_dispatch` re-reads the Run's decisions after claiming, so a same-Run superseder published before the claim still stops the host start. Post-review guardrails (owner-approved 2026-11-06): the coordinator creates each Run with `create_run(state_root)` (UUIDv4 plus exclusive Run directory; the LLM never types an id; ids are recovered from disk after compaction), and the Pi producer writes only into an existing Run folder without `dispatch-claim.json`, otherwise it blocks and warns about a possibly wrong Run id. Local verification on 2026-11-06 (not CI): core unittest 738 OK; conformance 18 OK; Python 3.11 task contract 297 OK; Pi `bun test` 56 pass; bundle and generated-agent checks current; Ruff check and format clean; `code-gates` dryer and crapper exit 0 with real coverage (new or changed core functions CRAP ≤ 7.1; pre-existing `_validate_attempt_report` 28.2 and `_validate_workorder` 25.8 stay above threshold). Focused mutation testing of the new Run-creation and Pi Run-folder guard lines was run in scratch; survivors and limitations are recorded in Current local verification below. TypeScript coverage was not measured. Earlier standalone review issues were fixed. Follow-up found P2 WS2-FU-001 (repair rejected valid requests for missing/closed Runs); code and regression tests now address it, and an independent re-review found no new P0–P2 findings. PR review then raised two findings, both fixed: a symlinked Run path could redirect a decision into another Run (P3, reclassified by the owner; the Pi producer now rejects a symlinked `.kapisch`, `runs` or Run folder before `realpath()`), and the direct-prompt recipe omitted the owning `run_id` (P2; recipe corrected, with a core regression test on the documented record shape). These two fixes have not been re-reviewed. Three P3 issues were fixed: Git calls ignore inherited `GIT_*` overrides, with regression tests in core and Pi; package checks use kernel message constants; Pi package checks assert paths and labels. A fourth P3, that `validate_dispatch` now loads the Run before the Run-local scan, is accepted as required by the design; `_validate_workorder` precedence is unchanged. The reviewer did not re-review the guardrails added afterwards. |
| WS-3.1 | Phase 2. Portable reviewer contracts: `kapisch-reviewer` role, ReviewReport semantics, and the eight reusable lenses (target/context, criteria, evidence, report semantics, escalation) | WS-0; Phase 1 exit (sequencing) | Planned deliverables and boundaries in the [amendment](plans/2026-11-05-kapisch-execution-order-amendment.md); reviewer remains advisory; findings never become human approval; standalone graph-free review preserved (AC11) | `TODO` | — | Not started. Existing `kapisch-reviewer` and `core/contracts/policy/review.md` are unchanged; reconciling `review.md`'s "authoritative approval" wording is part of this workstream. |
| WS-3 | Phase 2. Optional review gate: immutable report, required-lens pass, permitted exception | WS-3.1, WS-2, WS-4 | AC5, applied only where a WorkOrder explicitly requires lenses; no gate for advisory or standalone review | `TODO` | — | `reviews.md` is a local advisory record; no gate and no exception binding |
| WS-4 | Phase 1. Multi-task DAG: dependencies, parallel-ready scheduling, task/attempt identity, and aggregation barrier | WS-1.2, WS-2 | AC3 on the portable core with deterministic adapters; AC2 task-level authorization bindings: in-scope DAG tasks proceed without per-task approval and out-of-scope work blocks. AC7 parity parts are tracked in WS-10 and WS-11 | `TODO` | — | One task only; no scheduler, no terminal/interrupted handling. Depends on WS-2's decision-level records, implemented locally and unmerged. |
| WS-5 | Phase 1. Local retry, checkpoint compatibility, interrupted attempts, and durable recovery | WS-1 | AC4: fresh attempt IDs; stale/incompatible checkpoints rejected; failed work preserved; shared work never reset | `TODO` | — | Retry/checkpoint execution remains outside the current one-task slice. The one-shot claim blocks replay, but retry and checkpoint compatibility are not implemented. Real-host interruption recovery is proven in WS-11, not here. |
| WS-6 | Phase 1. Ambiguous external-effect handling and explicit authorization boundaries | WS-2 | AC6: retry blocked until an authoritative outcome query or explicit scoped human authorization; local retries do not invoke it | `TODO` | — | Guidance only |
| WS-7 | Audience-neutral presentation invariance | — | AC9: an explicit style changes wording only; facts, evidence, decisions, authority identical | `TODO` | — | No style mechanism and no test. Not sequenced by the 2026-11-05 amendment; no Pi or Claude dependency. |
| WS-8 | Phase 4 (after real-adapter acceptance). Packaging, install smoke test, validator retention, legacy cutover | WS-0, WS-3.1, WS-11 (and WS-12 for any Claude package claim) | AC10: reviewer install/invocation and new-format packaging verified before any legacy removal | `TODO` (removal correctly not started) | Pi package declares the extension | A fresh local Pi package install and one worker invocation succeeded in the smoke workspace. Reviewer installation/invocation, validator retention, and cutover acceptance remain unverified; `core/schemas/v3` and migrators are untouched. Starts only after the corresponding real-adapter acceptance; legacy removal still needs separate authorization. |
| WS-9 | Test-harness health and regression watch | — | Supported suites run as CI runs them; non-source artifacts classified; no source-caused regression hidden | `DONE` | merged (PR #85, `93bc222`) | Local supported suites pass; PR #85 had four successful checks and an approved review as of 2026-11-05. Root-level pytest and `.worktrees` artifacts are explained below. |
| WS-10 | Phase 3. Harness-neutral conformance: one reusable suite over the adapter protocol, run by deterministic and fake adapters | WS-2, WS-3, WS-3.1, WS-4, WS-5, WS-6 | Portable-core halves of AC1–AC6, AC8, and AC11, plus deterministic same-WorkOrder parity: orchestration invariants, unsupported/unknown capability blocking, failed/incomplete attempts, recovery, approval scope, dependency barriers, reviewer outcomes, fresh-process reconstruction. Does not complete AC7 or any real-host criterion | `TODO` | — | No suite exists. PR #85 tests are a single-task subset. |
| WS-11 | Phase 4. Real Pi adapter and real-adapter acceptance, including deferred PR #85 Finding 3 | WS-10 | AC7 for Pi: the same WorkOrder through real capability probing and start/collect, compared with the deterministic adapter in tracked tests; unsupported/unknown/unproven capabilities block start; the Phase 3 suite passes against the adapter; tracked direct-prompt and pending-request producer coverage; real-host interruption recovery. Pi read-only review stays unsupported unless enforcement is proven | `TODO` | — | Existing local Pi smokes are manual, not CI. The tracked Pi integration test is synthetic and hard-codes capabilities. |
| WS-12 | Phase 4. Real Claude adapter and real-adapter acceptance | WS-10 | The same portable contract and real-adapter requirements as WS-11 on a separate adapter; host capabilities verified, not assumed | `TODO` | — | Not implemented; no capability evidence. |

## Specification acceptance coverage

Coverage is independent of workstream status. Criteria are from specification §8. A criterion that requires a real adapter (AC7, and the real-host parts of AC1, AC8, and AC10) cannot be completed with deterministic or fake-adapter evidence; the amendment plans that proof in Phase 4.

| AC | Requirement (abbreviated) | Coverage | Evidence or gap |
| --- | --- | --- | --- |
| AC1 | Single-task SDLC flow reaches a durable Outcome, respecting human decisions and deployment authorization | partial | Tracked tests cover one-task authorization through durable Outcome; a local real Pi worker smoke used Git-bound inputs and a fresh-process validator. Deployment authorization, interruption/resume, review, and broader lifecycle behavior remain outside this slice. |
| AC2 | Within a Run, decisions preserve identity, are reassessed for changed applicability, and avoid repeated prompts for covered external facts; task-level scope and per-task authorization | partial | WS-2 now uses Run-local decisions with required identity, provenance, reassessment, and supersession; no decision is reused as permission across Runs. WS-4 owns DAG task coverage and in-scope/out-of-scope bindings and remains unimplemented, so AC2 stays partial. |
| AC3 | Aggregation barrier at completion or terminal condition; all required tasks accounted for; failure report is evidence but does not release dependents | partial | Single task, parent-LLM aggregation, no terminal/interrupted handling |
| AC4 | In-scope retries use fresh IDs, preserve failed work, reject stale checkpoints, never reset shared work | partial | Retry and checkpoint execution are explicitly outside this two-PR slice. The one-task core prevents replay of a claimed attempt; it does not implement retry or checkpoint compatibility. |
| AC5 | Immutable review report; remediation alone does not release; new pass or separate exception does; prohibited exceptions block; gate only where a WorkOrder requires lenses | none | Advisory wording and a local report only; no gate |
| AC6 | Ambiguous remote effects block until authoritative observation or explicit scoped authorization | none | Guidance only |
| AC7 | Same WorkOrder yields equivalent logical status, authority, decisions, evidence, reports, Outcome via real and test adapters; missing capabilities block | partial | The aligned local worker smoke used the exact tracked WorkOrder/decision identity and matched all nine artifacts, but is local/manual. The tracked integration test still synthesizes output and hard-codes supported capability; it does not exercise actual Pi start/collect or capability probes at that boundary. Finding 3 is deferred to Phase 4 (WS-11); do not mark AC7 complete until tracked same-WorkOrder adapter and capability-boundary coverage exists against a real adapter. Deterministic-adapter parity (WS-10) does not complete it. |
| AC8 | Fresh-session reconstruction without conversational or mutable derived authority | partial | A fresh Python controller process validated persisted WorkOrder, Decision, Attempt, report, and Outcome for both adapter roots. Reconstructing the next action after interruption and multi-task recovery remain untested. |
| AC9 | Presentation styles preserve normalized facts, evidence, decisions, authority | none | No style mechanism or test |
| AC10 | Reviewer installation/invocation and new-format packaging verified before legacy removal | partial | Local Pi package install and one task-worker invocation succeeded in the smoke workspace. Reviewer installation/invocation, validator retention, and cutover acceptance remain unverified; nothing was removed. |
| AC11 | Advisory and standalone review remain graph-free, need no DAG or implementation authorization, and do not depend on the optional review gate | partial | Contract text merged and preserved; no dedicated test of the graph-free/no-gate property |

## Repository test health

The repository's supported harness is the CI sequence in
`.github/workflows/quality.yml` — `unittest`, run from the directory each job selects.
Root-level `pytest` is not that harness.

Current local verification for WS-2 (2026-11-06; local only, not CI): core unittest 738 OK;
conformance 18 OK; bundle check OK; Python 3.11 task-contract suite 297 OK; Pi Bun tests
Pi human-decision test file 39 pass; full Pi suite 56 pass; generated Pi agents current; Ruff check/format and `git diff --check` clean.
`code-gates` dryer and crapper passed with real Python coverage; changed/new core functions
scored CRAP ≤ 7.1. Pre-existing `_validate_attempt_report` (28.2) and `_validate_workorder`
(25.8) remain above 10. Focused mutation testing ran in a disposable scratch copy against
Run-creation and Pi Run-folder guard source lines (not the entire Revision 3): core killed 5
mutants, 2 survived on `create_run` path hardening (`or`→`and`, and `strict=True`→`False`);
the current tests did not distinguish these variants; they remain unresolved until reviewed. Pi
killed 10 and had 3 surviving error-classification mutants at `human-decisions.ts:216`,
`:225`, and `:230`, involving error codes/shapes other than the normal ENOENT/EEXIST paths;
the mutation run did not establish their equivalence or prove fail-closed behavior for those
errors. Git environment-filter mutation selection yielded no mutant sites. This is focused test
evidence, not a full mutation score; TypeScript coverage was not measured.
The standalone follow-up review found one P2: the wrong-Run warning recommended a repair command that rejected structurally valid requests. Fixed by making repair re-check persisted Run existence/claim state at invocation and regenerate a non-authorizing request only for invalid or unavailable Runs; regression tests cover missing, dispatched, and valid/open Runs, including one-message/no-decision and hidden-triggered send options. Focused mutation testing of the repair handler killed all 6 selected mutants. A fresh read-only follow-up review found no new P0–P2 findings. PR review findings fixed afterwards: the Pi producer now `lstat`-checks `.kapisch`, `.kapisch/runs` and the Run folder and blocks on a symlink (three alias regression tests failed first), and the direct-prompt recipe lists the owning `run_id` (the validator already required it, so its regression test passed on first run and was shown to fail with the check disabled). Focused mutation testing of the new `lstat` loop: 2 killed, 3 survived. One survivor (`&&`→`||` in the `lstat` error handler) would report a non-ENOENT filesystem error as a wrong Run id instead of a storage failure; input is blocked either way. The other two are in the older `realpath` ENOENT branch, which the `lstat` loop now makes unreachable. Not CI:
no Windows, live-producer or PR/CI run.

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
   Outcome to the deterministic adapter and passed fresh-process validation. The
   `490cc99` check state and the `816abdb` change request cited in earlier updates are
   historical; see the PR state above. Broader decision-source coverage, interruption
   recovery, multi-task work, and product acceptance remain open (core work in Phase 1;
   real-host proof in Phase 4).

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

- **WS-2 limitations and follow-ups:** acceptance/Outcome validation continues to
  re-check current Git inputs against `source_root`. Run history and supersession
  chains must be retained under `state_root`; retention/GC remains owner-decided.
  Older validators ignore `supersedes`, and Pi producers do not emit it until WS-11.
  Incomplete local directory enumeration remains outside the guarantee (PR85-009).
  WS2-KR-002 is closed: independent Runs share no authority graph, and
  `claim_dispatch` re-reads the Run's decisions after claiming, so a same-Run
  superseder published before the claim stops the host start (the Run stays
  claimed for operator reconciliation). A wrong but existing, undispatched Run id
  in a decision request is still not detected by the producer; the consuming Run
  rejects the decision.
**Unknowns**

- The bounded one-task schemas, validation, and producer order are tracked in
  `core/contracts/task-first.md` and `core/kapisch_core/task_contract.py`. Extending
  those records to multi-task execution or interruption recovery remains a separate
  design and implementation decision.
- A synthetic direct-prompt coordinator preflight exercises persisted decision
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

**After this WS-2 Revision 3 slice is reviewed and merged, WS-4 (DAG, dependencies, and per-task authorization) is the next recommended item.**

1. Phase 1 recommendation: WS-4, then WS-5 (retry, checkpoints, interrupted attempts,
   recovery), and WS-6 (ambiguous external effects, authorization boundaries). Use
   deterministic/test adapters only; put no Pi-, Claude-, Codex-, or session-specific
   identifiers in core authority records. WS-4 depends on WS-1.2 and WS-2's Run-local
   decision-level records; only dependencies in the workstream table are hard.
2. Then Phase 2 (WS-3.1 reviewer contracts and lenses, WS-3 review gate), Phase 3 (WS-10
   harness-neutral conformance), and Phase 4 (WS-11 Pi including deferred Finding 3,
   WS-12 Claude, then WS-8 packaging and cutover).
3. Keep AC7 partial until a real adapter demonstrates same-WorkOrder parity in tracked
   tests. Keep local worker smokes as manual evidence, not CI.

Rationale: WS-2 supplies Run-local decision-level records needed by WS-4 to WS-6. WS-3
(optional review gate) is not a prerequisite for WS-4. This is a sequencing recommendation,
not an owner decision.

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
| PR #85 state (GitHub read, 2026-11-06; point-in-time) | Merged 2026-11-05T07:57:33Z as `93bc222` ("feat(core): task-first portable acceptance contract and bounded Pi integration (#85)"); last formal review `APPROVED` on implementation head `2885a1e`; four CI checks succeeded. |
| Finding 3 deferral (operator decision, 2026-11-02) | Deferred to a dedicated Pi harness-integration follow-up; AC7 remains partial. [PR comment #6590593116](https://github.com/twKrash/kapisch/pull/85#issuecomment-6590593116). The 2026-11-05 amendment schedules that follow-up as WS-11 in Phase 4. |
| Execution-order amendment (owner decision, 2026-11-05) | Core, then reviewer contracts/lenses, then harness-neutral conformance, then real Pi and Claude adapters; sequencing only. [Amendment](plans/2026-11-05-kapisch-execution-order-amendment.md). |
| PR85 review dispositions (operator decision, 2026-11-04) | P2-008 fixed in commit `2885a1e`; P2-009 accepted as a local filesystem-integrity limitation; [PR comment #6643639447](https://github.com/twKrash/kapisch/pull/85#issuecomment-6643639447) and `core/contracts/task-first.md`. |
| WS-2 design addendum (approved 2026-11-06) | [Design addendum](specs/2026-11-05-ws-2-decision-applicability-design.md); owner-authorized implementation remains local and uncommitted. |
| WS-2 implementation plan (approved 2026-11-06) | [Implementation plan](plans/2026-11-05-ws-2-decision-applicability-implementation-plan.md); uncommitted working-tree implementation evidence is recorded in WS-2 above. |
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
