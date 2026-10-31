# Kapisch Task-First Core and Acceptance Plan

**Status:** Planning artifact; no implementation is authorized by this document.
**Scope:** Next two-PR slice only: WS-1.2 tracked acceptance plus WS-1.1 persisted-decision consumer integration.
**Baseline:** `main` at `c259d28363d862976f9c980a71faaee8a14a3895`; PR #84 merged 2026-10-30.

## Recommendation and current state

Deliver the next slice in two dependent PRs. PR #84 already merged pending-request `HumanDecision` capture and authorization for one bounded direct-prompt WorkOrder. It did not deliver tracked end-to-end WorkOrder acceptance, Git-input freshness, portable fresh-process reconstruction, or same-WorkOrder real/test adapter equivalence. The tracker’s statements describing PR #84 as a draft are stale; use the GitHub PR record and current `main` as status evidence.

## Architecture boundaries

### Executable scope

The executable core handles exactly one Run containing one WorkOrder with one task. It validates authorization, evidence references, and permitted lifecycle transitions. It does not schedule tasks, run retries, create a generalized orchestration/recovery framework, or invoke an LLM runtime.

The deterministic test adapter supplies attempt results. In operation, the LLM aggregator produces the aggregation report; the core validates its coverage/references and applies transition policy. Tests may pass a fixed aggregation-report fixture to the validator, but must not call or emulate an LLM runtime.

### Portable artifacts and producers

Use ordinary per-run files with structured JSON for stable fields; no database or mutable global state. Candidate layout:

```text
.kapisch/runs/<run_id>/run.json
.kapisch/runs/<run_id>/workorder.json
.kapisch/runs/<run_id>/decisions/<decision_id>.json
.kapisch/runs/<run_id>/attempts/<attempt_id>.json
.kapisch/runs/<run_id>/aggregation.json
.kapisch/runs/<run_id>/outcome.json
```

Use opaque generic IDs and portable project-relative references with digests where needed. The coordinator publishes the Run record and canonical WorkOrder; the Run reference locates its WorkOrder, which references the HumanDecision. Workers write only unique attempt outputs; the coordinator owns canonical Attempt records and transitions. The LLM aggregator owns the report. The coordinator validates the report and publishes Outcome. The human-input boundary owns HumanDecision production: the Pi input extension handles explicit pending-request answers, while the coordinator handles direct-prompt decisions. Each path must produce one immutable decision record, not duplicate or recreate one.

- **Run:** stable `run_id` and WorkOrder reference; it locates durable work and is not itself authorization.
- **Context:** goals, constraints, evidence references, assumptions, and prior-decision references; not approval.
- **HumanDecision:** immutable `decision_id`, `question_id`, original question, governing-input references/digests, subject, scope, answer, decision type, source kind, and available attribution. Human decisions, agent evidence, and reviewer findings remain distinct.
- **Applicability:** recompute for the specific WorkOrder, scope, and current governing inputs. A persisted result may record the inputs, result, and reason for audit; it is never an independent authority source. Relevant input changes trigger reassessment.
- **WorkOrder:** authorized scope, one task, acceptance requirements, required capabilities, and decision references; no attempt forecast. Approval covers the stated scope; in-scope work needs no per-task approval.
- **Attempt:** unique attempt ID, task/WorkOrder references, status, output reference/digest, and evidence. This slice validates one attempt; it does not implement retries.
- **Aggregation report:** aggregator-produced coverage/result evidence with failures, conflicts, missing references, and unresolved issues preserved. Core validates it; it does not generate it.
- **Outcome:** coordinator-produced local completion evidence referring to the WorkOrder, decision, attempt, report, and checks; it does not grant external-effect permission.

### Portable identity and adapter boundary

Resolve a Run from the project root plus its portable `run_id` and file references. A fresh controller process must locate and validate the Run, WorkOrder, and HumanDecision without recovering the original Pi session, conversation history, or process memory. Keep Pi session IDs, host handles, transcripts, and host lookup metadata inside the adapter; never make them core identity.

Adapters report actual capabilities using `supported`, `unsupported`, or `unknown`, with a reason. Only supported and proven capabilities satisfy a WorkOrder requirement. An unsupported, unknown, or unproven required capability blocks dispatch/continuation until explicit human re-scope. The bounded interface is capability reporting plus start/collect; status/resume/stop remain optional and are not generalized into a workflow engine.

Persist and validate Run, HumanDecision, and WorkOrder references before dispatch; allocate the attempt ID/output location before start; persist the output before aggregation; validate the report before Outcome. After restart, revalidate source refs/digests and authorization. Never rely on process memory or silently recreate a missing record.

## Implementation steps

### PR 1 — Single-task portable contract and core validation

**Purpose:** Define the durable contract and track Kapisch-owned business acceptance before wiring the real adapter.

**Scope:** Add a task-first contract alongside `core/contracts` (candidate: `core/contracts/workflows/task-first.md`) and a narrow validator in `core/kapisch_core/task_contract.py`, isolated from V2/V3 protocol, state, schema, and lifecycle code. Add a deterministic test adapter under `tests/core` that supplies one task’s attempt result. Core checks authorization, governing-input evidence, and valid single-task transitions; tests pass report fixtures to validate report/result references and transition policy.

**Acceptance:** Required/malformed references fail closed; scope and decision authorization are checked; relevant input changes force reassessment; one failed/missing result cannot yield a complete Outcome; capability gaps block when required; portable file references support fresh-process reconstruction. Keep the test fixture limited to one Run, one WorkOrder, one task, one attempt, and a supplied report.

**Dependencies:** Merged PR #84 and approved design direction; no dependency on WS-3.

**Out of scope:** Multi-task scheduling or aggregation barriers, retries/checkpoints, LLM runtime integration, review gates, remote-effect reconciliation, a database, broad compatibility, and historical migration.

### PR 2 — Bounded Pi integration and same-WorkOrder acceptance

**Purpose:** Consume the new contract through the existing one-task Pi path and prove equivalence with the test adapter.

**Scope:** Depends on PR 1 and merged PR #84. Connect the portable Run/WorkOrder/decision references to the existing Pi path without changing its one-task bound. Reconcile the pending-request extension and direct-prompt coordinator producer paths so each yields one stable portable decision reference. Keep session metadata adapter-owned.

**Acceptance:** Tracked tests and the real-adapter smoke use the same logical WorkOrder. Compare normalized logical status, authority, decision identity/source/scope/applicability, evidence references, aggregation report, and Outcome; exclude host handles, session IDs, and timestamps without erasing logical identity. Verify the fresh-controller criterion above, current Git-bound input freshness, no duplicate approval, reference consistency across artifacts, and blocking for required unsupported/unknown/unproven capabilities. Test fallback eligibility only for the explicitly authorized bounded route when the canonical implementer is unavailable. Do not claim AC7 complete until the real-adapter smoke passes.

**Out of scope:** Multi-task orchestration, retry/checkpoint execution, general recovery, optional review gates, remote-effect gates, presentation invariance, packaging/cutover, and historical migration.

## Acceptance and test boundaries

Test Kapisch-owned business invariants and lifecycle behavior only—not third-party library behavior, Markdown wording, tracker contents, documentation snapshots, or generated prose.

**Fresh-process acceptance:** “A fresh controller process can locate and validate an existing Run, WorkOrder, and HumanDecision using portable references without recovering the original Pi session, conversation history, or process memory.”

The two-PR slice covers the bounded decision-to-Outcome path and focused portions of AC1, AC2, AC7, and AC8. It does not complete AC1–AC11. In particular, the broader LLM barrier and multi-task cases (AC3), retry/checkpoint behavior (AC4), review gates (AC5), remote effects (AC6), presentation invariance (AC9), and packaging/cutover (AC10) remain separate work. Preserve graph-free advisory and standalone review as findings-only capabilities (AC11); do not make the optional review gate a prerequisite for unrelated WorkOrders.

## Reuse, approval, and evidence

Reuse decision capture behavior from `harnesses/pi/extensions/human-decisions.ts`, resume requirements from `plugins/kapisch/skills/kapisch/references/resume.md`, and relevant policy from `core/contracts/policy/authority.md`, `review.md`, and `risk.md`. Reuse only targeted comparison/reference-validation ideas from the local, untracked `.kapisch/runs/pi-task-first-2026-10-26-01/test-adapter/` harness. Do not port its whole framework or import V2/V3 lifecycle semantics from `core/kapisch_core` or `core/schemas/v3`.

No owner escalation is needed for artifact fields, producer order, capability reporting, or the first adapter; these are delegated engineering choices. Escalate only if implementation changes approved scope, human authority, security boundaries, external-effect permissions, or requires a material architecture change. Implementation still needs a separately approved execution scope.

**Evidence references:**

- `docs/superpowers/plans/2026-10-25-kapisch-product-realignment-proposal.md` §§4–8, 11–13.
- `docs/superpowers/specs/2026-10-25-kapisch-product-realignment-design.md` §§4–10, especially §§5.6–5.7 and §8.
- `docs/superpowers/product-realignment-tracker.md` Workstreams, Acceptance coverage, blockers, and Next recommended vertical slice; progress evidence only.
- [GitHub PR #84](https://github.com/twKrash/kapisch/pull/84), merged 2026-10-30; current local main commit `c259d28363d862976f9c980a71faaee8a14a3895`.
