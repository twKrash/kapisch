# Kapisch Execution-Order Amendment

**Status:** Approved roadmap sequencing decision (owner, 2026-11-05). Planning artifact; no implementation is authorized by this document.
**Scope:** Implementation order only. The approved [proposal](2026-10-25-kapisch-product-realignment-proposal.md) and [design specification](../specs/2026-10-25-kapisch-product-realignment-design.md) remain authoritative for product requirements, acceptance criteria AC1–AC11, the security model, and human authority. Nothing here changes them.
**Supersedes (order only):** the implicit order in proposal §11 (real-plus-test adapter validation interleaved with the core slice) and the "next item" in the [2026-10-30 plan](2026-10-30-kapisch-task-first-core-acceptance-plan.md) execution record (Pi integration first). Those documents stay as historical records.
**Progress and status:** the [tracker](../product-realignment-tracker.md) holds workstream status and dependencies. This file defines the phases, deliverables, and acceptance boundaries.

## Decision

Complete the harness-agnostic orchestration core first, then portable reviewer contracts and document-review lenses, then harness-neutral conformance, and only afterward implement production Pi and Claude harness adapters. The next priority is the harness-neutral core and reusable reviewer semantics, not Pi- or Claude-specific execution.

The spec already allows this order: the aggregation barrier and parallel dispatch are independent of the optional review gate (spec §5.2.8, AC11), and the first real adapter is chosen after capabilities are verified (spec §7). The spec's real-adapter requirement (§5.6.3, AC7) is unchanged; it is demonstrated in Phase 4, not earlier.

## Evidence classes

| Class | Produced by | Proves | Does not prove |
| --- | --- | --- | --- |
| Portable-core | Core validators with deterministic/test adapters | Record, authority, and transition semantics | Any real host behavior |
| Harness-neutral conformance | The shared Phase 3 suite with deterministic and fake adapters | The adapter protocol and orchestration invariants hold for any conforming adapter | Actual host invocation, capability enforcement, isolation, or runtime compatibility |
| Real-adapter | A production adapter on its real host, tracked in CI where the host allows | Actual invocation, enforced capabilities, isolation, runtime compatibility | — |

Fake-adapter or deterministic evidence never marks a real-adapter criterion complete. Local manual smokes are supporting evidence only, in every phase.

## Phase sequence

| Phase | Name | Workstreams | Starts after |
| --- | --- | --- | --- |
| 0 | Bounded single-task foundation (baseline) | WS-1, WS-1.1–WS-1.3, WS-1.2, WS-9 (PR #85) | — |
| 1 | Harness-agnostic orchestration core | WS-2, WS-4, WS-5, WS-6 | PR #85 merged (human action) |
| 2 | Portable reviewer contracts and document lenses | WS-3.1, WS-3 | Phase 1 exit |
| 3 | Harness-neutral conformance | WS-10 | Phases 1 and 2 exit |
| 4 | Real harness integration, then packaging and cutover | WS-11 (Pi), WS-12 (Claude), then WS-8 | Phase 3 exit |

"Starts after" for Phases 2–4 is an owner-directed sequencing dependency, not a technical coupling, and changes only by owner decision. Within a phase, only the dependencies listed in the tracker are hard. WS-7 (presentation invariance) has no Pi or Claude dependency and is not sequenced by this amendment.

### Phase 0 — baseline (PR #85)

PR #85 is a bounded, portable single-task foundation: one Run, one WorkOrder, one task, one Attempt, a supplied aggregation report, and an Outcome, with fresh-process reconstruction. It does not complete the core, the reviewer contracts, conformance, or real-harness integration. Recorded dispositions stay as recorded: PR85-008 fixed; PR85-009 accepted as a local filesystem-integrity limitation; Finding 003 deferred (now to Phase 4); AC7 partial. The documented power-loss/storage-rollback and standalone-packaging limitations remain.

### Phase 1 — harness-agnostic orchestration core

Complete the portable domain model and orchestration semantics against deterministic/test adapters only:

- **WS-2:** HumanDecision applicability, scope coverage, reuse without re-asking, and reassessment on substantive governing change (AC2).
- **WS-4:** WorkOrder DAG, task dependencies, parallel-ready scheduling, task and attempt identity, and the aggregation barrier including terminal/interrupted conditions (AC3).
- **WS-5:** local retries with fresh attempt IDs, checkpoint compatibility, interrupted attempts, and durable recovery (AC4).
- **WS-6:** ambiguous external-effect handling and explicit authorization boundaries (AC6).
- Existing authority, persistence, provenance, and fresh-process reconstruction guarantees stay in force (AC8).

**Next slice: WS-2**, the first unfinished Phase 1 requirement, after PR #85 is merged. Recommended order is WS-2, WS-4, WS-5, WS-6; this is a recommendation, and only the dependencies in the tracker are hard. WS-2's scope-coverage and applicability checks are consumed by in-scope additions (WS-4), in-scope retries (WS-5), and scoped authorization (WS-6).

Constraints: core authority records carry no Pi-, Claude-, Codex-, or session-specific identifiers; host handles and session metadata stay adapter-owned. The legacy V3 `session_namespace`/`session_id` provenance fields (proposal §9) are outside the task-first contract and are handled at cutover. No database, generalized event sourcing, transaction coordinator, or recovery framework. Exit: AC2–AC4 and AC6 portable-core criteria demonstrated by tracked tests with deterministic adapters.

### Phase 2 — portable reviewer contracts and document lenses

Planned deliverables (none is created by this amendment; file locations are an implementation-planning choice):

- A portable `kapisch-reviewer` role contract that preserves the existing reviewer and its advisory authority.
- Portable ReviewReport semantics: immutable report with findings, original verdict, evidence, confidence, unresolved issues, recommendation, escalation, and reviewer provenance. A later review is a new report; a human exception never rewrites a verdict.
- Eight reusable lenses, each with required target and context, evaluation criteria, expected evidence, report semantics, and escalation conditions: requirements and intent completeness; research and documentation quality; architecture, ADRs, API/event contracts, and NFRs; decision readiness before human approval; code quality and maintainability; security, permissions, privacy, and isolation; test strategy, coverage, and verification; operations, audit, recovery, and deployment readiness.
- Optional WorkOrder review-gate semantics (WS-3), applied only where a WorkOrder requires lenses: a required non-pass blocks dependent tasks; a human fix direction authorizes remediation only; pending, interrupted, or still-failing remediation stays blocked; release needs a new passing report or a separately authorized, permitted HumanDecision exception that references the verdict; normative and security restrictions cannot be excepted; no autonomous review/fix loop and no separate review-approval subsystem.
- Reconcile `core/contracts/policy/review.md` ("authoritative approval or readiness") with the target semantics. Reviewer findings and passes are evidence, never human approval.
- Standalone graph-free `workflow=advisory` and `workflow=review` stay first-class and gate-free (AC11).

Exit: AC5 and AC11 portable-core criteria demonstrated with a deterministic reviewer fake. Real reviewer invocation on a host is Phase 4.

### Phase 3 — harness-neutral conformance

Define one reusable conformance suite over the minimal adapter interface, run by deterministic and configurable fake adapters (for example: unsupported or unknown capabilities, failed, interrupted, and late results). It covers:

- orchestration invariants: single producer per record, immutability, derived-state reconstruction;
- unsupported, unknown, or unproven capabilities block dispatch until explicit human re-scope;
- incomplete and failed attempts, aggregation accounting, and dependency barriers;
- retry, stale-checkpoint rejection, interrupted-attempt recovery;
- approval scope: in-scope proceeds, out-of-scope blocks, carried-forward answers are not approval;
- reviewer outcomes and gate release rules;
- ambiguous external effects;
- fresh-process reconstruction without conversational or process memory;
- same-WorkOrder parity between two adapters on normalized logical status, authority, decisions, evidence references, reports, and Outcome (host handles, session IDs, and timestamps excluded).

Deterministic adapters validate core semantics and protocol behavior only. Passing this suite does not complete AC7 and does not substitute for any real-adapter acceptance. The suite becomes the conformance gate each Phase 4 adapter must also pass.

### Phase 4 — real harness integration

Only after Phases 1–3 exit. Pi and Claude are separate adapters implementing the same portable contract. Host execution, permissions, sessions, handles, and capability reporting stay outside core. The intended interface stays minimal: capability reporting, start, collect, and optional capability-gated status/resume/stop.

- **WS-11 (Pi):** the deferred PR85 Finding 003 lives here: tracked real Pi capability probing and `start/collect`, same-WorkOrder parity against the deterministic adapter, and blocking on unsupported, unknown, or unproven required capabilities at the real boundary. Also: tracked direct-prompt and pending-request producer coverage, and real-host interruption recovery. Pi keeps read-only review unsupported unless enforcement is proven.
- **WS-12 (Claude):** not implemented and no capability evidence exists. Capabilities are verified, not assumed.
- Each adapter passes the Phase 3 suite and then demonstrates real-adapter acceptance. AC7 stays partial until at least one real adapter shows same-WorkOrder parity with the deterministic adapter; claims about a specific host apply only to that host.
- **WS-8** (packaging, installation verification, validator retention, legacy cutover) follows the corresponding real-adapter acceptance. Removing legacy paths still needs separate authorization.

## Non-goals of this amendment

- No product requirement, acceptance criterion, security model, or human-authority change.
- No implementation, adapter code, reviewer or lens files, tests, or schema changes.
- No new infrastructure: database, event sourcing, distributed transactions, or a generic recovery framework.
- No claim that PR #85 or any fake-adapter evidence satisfies Phase 2, 3, or 4 criteria.

## Items reported for owner attention (not changed here)

- Proposal §8 names Codex as a candidate first adapter. This amendment schedules Pi and Claude only; Codex is neither added nor removed, and first-adapter selection remains a delegated engineering decision.
- AC7 and the spec §5.6.3 wording require a real adapter. Deferring that proof to Phase 4 is sequencing, not a requirement change.
