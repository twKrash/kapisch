# Thin KAPISCH Controller: Context and Handoff Design

**Status:** Approved design

## Goal

Reduce KAPISCH parent/controller context and turn overhead without weakening role separation, independent review, final-readiness, durable evidence, resume/recovery, validator semantics, truthful status reporting, or bounded retry policy.

The controller becomes a workflow decision-maker, not a second repository engineer. It normalizes the request, selects workflow/risk/gates and the next logical role, dispatches bounded work, consumes compact authoritative outcomes, performs allowed transition decisions, maintains minimum durable state, and reports status.

This design does not implement the change.

## Scope and non-goals

In scope: controller context boundaries, compact stage handoffs, deterministic projections/transitions, lazy artifact loading, adapter responsibilities, durable validation, observability, and benchmark acceptance.

Out of scope: issue #23 profile-setup locking; issue #25 containment/metadata/publication hardening; profile/model routing; provider pricing; Terra/Sol/Luna routing changes; TOON or another compact serialization format; new parallelism; general unrelated refactors; and a runtime service that replaces KAPISCH’s portable workflow semantics.

## Investigation findings

### Evidence examined

- Canonical KAPISCH public skill and normative references: request normalization, role resolution, handoffs, dispatch, durable execution, resume, and review.
- Current Python validator transition implementation, including deterministic `determine_next_action`.
- Existing v3 durable run artifacts for the 1.1.0 cost-efficiency work.
- Current Pi KAPISCH adapter skill and available Pi session/subagent artifacts.

### Source classification

| Possible source | Finding | Design response |
| --- | --- | --- |
| Canonical workflow instructions | Material. The public skill plus the five most relevant references are about 94k characters/~11k words. `handoffs.md`, `execution-graph.md`, and `review.md` contain necessary safety detail, but are too large to reread as ordinary transition context. | Preserve semantics; introduce compact, validator-bound projections and explicit loading rules. |
| Pi adapter/shim | Not the direct cause. It is a small instruction-only adapter that already requests fresh, bounded child contexts and does not itself scan run trees or ingest transcripts. Its canonical path is stale at v1.0.1. | Keep runtime mechanics in adapters; update the adapter to enforce bounded assignment/result behavior and current contract discovery. |
| Parent system/skill prompt | Material stable-prefix cost. Pi system/developer/skill text and canonical reference reads create a substantial base context. Caching may reduce billed uncached input but does not justify repeated mutable context. | Keep a stable compact controller contract and load detailed references only at initialization, explicit recovery, or exceptional policy questions. Benchmark cached and uncached input separately. |
| Repeated durable-state reads | Plausible and avoidable. Current artifacts require graph/state plus named reports and handoffs; the controller contract does not provide a compact current-state projection. | Add a derived controller view as the normal transition read. |
| Repeated repository reads | Plausible and avoidable for routine transitions. The controller can repeat specialist investigation when it rereads implementation details. | Controller reads Git identity/state required for freshness; specialists own repository substance. |
| Child-result ingestion | Avoidable. Existing detailed reports are useful evidence but too verbose for routine transition decisions. | Normalize each role return into a bounded stage outcome while retaining exact evidence. |
| Full child artifact/session ingestion | Avoidable. Pi persists transcripts separately; observed child outputs are compact, so transcript loading is controller behavior rather than a Pi-subagent requirement. | Treat transcripts/session/debug history as unloaded historical information by default. |
| Handoff verbosity | Material. Current handoff guidance requires broad fields and exact detailed evidence. | Preserve detailed evidence, but separate it from controller-facing compact outcomes. |
| Workflow ceremony | Partly avoidable. The validator already deterministically derives next action from manifest/state. | Move selection/reconciliation calculation and projection regeneration to deterministic helpers. |
| Repeated validation/readiness checks | Necessary at defined safety boundaries but repeated conversational inspection is avoidable. | Run structural validation at defined state-mutating boundaries and consume its compact result; preserve review/final semantic checks. |
| Redundant worker/reviewer iterations | Policy risk. Existing contracts constrain fixes, but runtime behavior needs a machine-checkable re-dispatch reason. | Require a persisted allowed re-dispatch reason, predecessor attempt, and budget consumption. |
| Context carried between stages | Material. Parent conversation can retain prior reports/tool outputs even where later roles do not need them. | Use stage-local contexts and a compact current view; never rely on historical chat as authority. |
| Adapter-specific behavior | Pi prompt/result transport and transcript storage are harness details. | Keep only portable schemas/rules in core; place transport, named-agent dispatch, and runtime metrics extraction in adapters. |

The exact reported 269k-input/54-turn KAPISCH trace was not present among available local session artifacts. That number remains a supplied baseline, not a reconstructed attribution. The benchmark in this design closes that measurement gap before release claims.

## Alternatives considered

1. **Minimal handoff/context trimming.** Preserve the current state machine and only shorten prompts/reports. Low complexity but controller compliance remains discretionary; it cannot prove that an outcome is authoritative or prevent repeated reconstruction. It has moderate expected savings and high drift risk.
2. **Thin-controller state model (selected).** Add compact stage outcomes and a derived controller view, retain detailed evidence by references/digests, and make every transition already determined by validated graph/state data deterministic. Moderate complexity and migration work; strong expected parent token/turn reduction while preserving portable semantics and debugging evidence.
3. **Runtime-managed orchestration service.** Place lifecycle mechanics in a runtime-specific scheduler. Highest potential turn reduction, but high complexity, larger migration risk, weaker Codex/Pi/OMP portability, and more opaque debugging. Rejected.

## Architecture

### Authoritative layers

1. **Existing canonical artifacts remain authoritative:** approved plan, `02-execution-graph.toml`, `03-state.toml`, task briefs/contexts/reports, review/final reports, and canonical reviewer invocation envelopes.
2. **Stage outcome is an immutable normalized index of one role attempt.** It is authoritative only for its normalized facts when its detailed evidence references validate; it never replaces raw/evidence artifacts.
3. **Controller view is a derived, replaceable projection.** It has no independent authority and must be reproducible from canonical artifacts and valid outcomes.

New durable runs add:

```text
.kapisch/runs/<task-id>/
  stage-outcomes/<attempt-id>.toml
  04-controller-view.toml
```

New durable manifests use `version = 4`. Version 4 binds every attempt ID to its immutable `stage-outcomes/<attempt-id>.toml` path and binds the current controller-view digest/path in state. These exact paths are normative; implementations must not substitute another layout.

### Stage outcome contract

One immutable outcome is written at `stage-outcomes/<attempt-id>.toml` for each terminal or safely resolved attempt. Its schema must include:

- schema version, task ID, node/stage ID, logical role, stable assignment and attempt IDs;
- outcome lifecycle (`complete`, `blocked`, or `failed`) and role disposition/status;
- base/head revision and applicable working-tree-state digest or `unavailable` only where the existing role contract permits it;
- a bounded list of finding/concern summaries, each with stable ID, severity/status, and reference to detailed evidence; the schema sets an explicit maximum count and maximum per-summary length;
- verification status with command/result artifact references and digests, not copied tool output;
- detailed report path, encoding, and SHA-256 digest; review/final invocation path/ID/digest when applicable;
- reviewer decision exactly as returned for review/final or `unavailable` for other roles;
- `redispatch_reason`, predecessor attempt ID, and retry/fix-budget effect; and
- an explicit `next_action_reason` chosen from a closed portable vocabulary.

It must not contain transcripts, raw child prompt/result text beyond already-required report binding, hidden reasoning, full tool output, model IDs, pricing, cache estimates, fabricated approvals, or unnamespaced runtime transport fields. Runtime-specific observable data belongs only in namespaced extensions.

### Controller view contract

`04-controller-view.toml` is atomically regenerated after every state-changing transition and contains only fields necessary for the next controller decision:

- normalized request summary, selected workflow/risk/review/final gates, authority constraints, and task ID;
- graph/state digest, current Git revision/state digest, validator result/digest, workflow status, active node, deterministic next action, and blocking reason;
- retry/fix budget and prior relevant re-dispatch reason;
- the current node’s role, assignment, brief/context/report paths, and allowed predecessor outcome references; and
- compact terminal predecessor outcome fields declared relevant to the current transition.

It stores references/digests rather than detailed evidence contents. It excludes completed-stage full contexts, raw reports, all transcripts, rendered state, metrics, generic history, and unrelated node records.

## Information ownership and loading classification

| Class | Meaning | Examples | Normal loader |
| --- | --- | --- | --- |
| A | Parent must understand content to decide the next workflow action. | normalized request/gates; active/next node; validator status; current revision; bounded outcome disposition/findings; retry reason/budget. | Controller view. |
| B | Parent needs validated existence/freshness, not substantive contents. | detailed role report, invocation envelope, verification command output, prior completed evidence. | Validator/projection via path+digest/status. |
| C | Only the next specialist needs content. | task context, approved technical plan detail, research report, detailed implementation report, review scope/evidence. | Adapter passes artifact references to the assigned specialist. |
| D | Historical/debug information normally unloaded. | child transcripts, session logs, old completed contexts, metrics, rendered state, superseded reports. | Explicit debug/recovery escalation only. |

The controller must not reread implementation files to reconstruct worker-reported facts, perform review work, inspect full child transcripts, scan the run tree per transition, or keep completed-stage context merely because it is in chat history.

## Lifecycle

1. **Initialize or resume.** Normalize request/gates. Read the controller view when valid. On missing/stale view, deterministically regenerate it from canonical artifacts; this is not evidence creation.
2. **Select/dispatch.** The adapter forms a bounded assignment from the controller view, the current node’s brief/context references, explicitly relevant predecessor outcomes, repository revision/state binding, constraints, and a role-specific compact return schema.
3. **Specialist work.** The specialist reads its own referenced artifacts and actual repository state. It returns the detailed evidence already required by canonical KAPISCH plus a bounded transport result. A reviewer independently inspects the actual Git range and never receives an implementation transcript as a substitute for inspection.
4. **Persist once.** Controller/adapter preserves detailed evidence exactly, writes/updates the required canonical artifact(s), writes the normalized stage outcome, updates graph/state, regenerates the controller view, and executes structural validation at this boundary.
5. **Transition or stop.** Parent reads the refreshed view and either performs a deterministic allowed next action, dispatches the selected role, or reports a durable block/failure/completion.

A normal transition must not read the entire run tree, prior completed reports, `03-state.md`, transcripts, metrics, or repository implementation content. A controller may enter explicit debug mode only with a recorded reason and bounded artifact list; that load is recorded in the next outcome.

## Determinism and parent-turn reduction

The deterministic helper, using the existing validator transition rules, performs next-action calculation, view regeneration, digest/reference checks, and structural validation. It does not choose risk, interpret ambiguous user scope, approve semantic review, or fabricate runtime identity.

Avoidable parent-turn classes are: repeated state-tree discovery; report rereading/re-summarization; read→summarize→dispatch cycles where a role can read the referenced artifact; conversational repetition of validator results; completed-stage context carriage; and confidence-only worker/reviewer redispatch.

The remaining LLM-controller decisions are normalization/risk/gate selection, material ambiguity, role selection where the existing contract requires judgment, authorized exception/retry decisions, semantic review/final status reporting, and final user communication.

## Retry and re-dispatch policy

No worker/reviewer re-dispatch is permitted without one of these persisted reasons:

- deterministic resolution of an interrupted active stage under existing resume rules;
- a concrete reviewer finding selected/authorized under the existing manual or bounded blocking fix policy;
- a failed/blocked attempt with an explicit retry-safe cause;
- stale revision/state requiring the canonical fresh review/final process;
- explicit user-approved plan/scope amendment; or
- a documented runtime dispatch failure where no work was performed and a fresh attempt is safe.

Each outcome records the reason, predecessor attempt, affected finding when applicable, authorization source, and consumed retry/fix budget. Re-dispatch for confidence, generic follow-up, or an unrecorded concern is forbidden. Existing maximum fix-round and reviewer-freshness rules remain unchanged.

## Resume and failure behavior

Resume continues to use canonical graph/state, Git reconciliation, evidence validation, and reviewer-envelope requirements. The controller view is a cacheable projection:

- valid/current view: load it and perform its indicated deterministic action;
- missing/stale/corrupt view: regenerate only from valid canonical artifacts and validate it;
- failed generation, missing canonical evidence, mismatched digest, invalid outcome, or ambiguous active state: persist/report the corresponding block and do not dispatch;
- existing legacy run: use current legacy resume behavior. Do not synthesize outcomes or views unless an explicit migration command creates validated new artifacts.

No projection, metric, chat claim, or compact outcome can approve a review/final, substitute a required invocation, or make a missing artifact valid.

## Validator implications

The validator gains schemas and checks for new-version outcomes/views: closed vocabularies; path containment; canonical report/invocation binding; digest and revision/state freshness; bounded summary fields; legal lifecycle relation to graph/state; re-dispatch authorization and budget; and deterministic controller-view derivation/currentness.

It retains its current boundary: structural validation does not establish semantic review scope, actual reviewer identity beyond existing evidence, full approval chain, or final readiness. Existing review/final validator behavior and canonical invocation envelopes remain unchanged.

## Adapter responsibilities

### Portable core

Own schemas, closed vocabularies, derivation rules, loader classification, retry reason rules, migration requirements, validator checks, and benchmark record format.

### Codex

Own named-agent profile dispatch and current reviewer invocation behavior. It writes core artifacts around actual Codex facts and never converts unavailable runtime evidence into a claim.

### Pi/OMP

Own bounded prompt construction, compact child-result extraction, transcript isolation, deterministic helper invocation, and collection of observable usage metrics. Pi/OMP must not put harness-specific transport details in portable fields; it may store observable values in namespaced extensions or `unavailable`.

The Pi adapter must use current contract discovery rather than a pinned v1.0.1 path.

## Backward compatibility and migration

Existing v1–v3 manifests and runs remain readable and resumable without rewriting. New durable runs use manifest version 4 for the explicitly added outcome/view bindings. The implementation supplies an explicit migration command for an eligible complete/inactive legacy run; it must derive records from existing canonical artifacts, validate before committing changes, and fail closed for missing/ambiguous/invalid evidence. Migration is never automatic during normal resume.

## Observability and metrics

When workflow metrics are requested, the controller records final-only, factual measurements:

- parent input/output, cache reads/hits when available, and turns;
- child input/output/cache/turns by role and invocation count;
- elapsed time; projection regeneration and debug-load counts; validator outcome; workflow outcome; review findings/decision; and correctness/test result.

Missing provider data is `unavailable`; metrics do not include prompts, secrets, hidden reasoning, raw transcripts, or estimates. Metrics do not establish approval.

## Benchmark and acceptance

Use equivalent clean commits/worktrees and fixed task definitions. Execute baseline current behavior and candidate behavior for:

1. a bounded behavioral task requiring implementation and independent review;
2. a high-risk durable task requiring research, implementation, independent whole-branch review, final readiness, and one controlled blocking-fix scenario; and
3. interrupted durable runs resumed at worker and reviewer boundaries.

For every run record parent and child input/output/turns; cache data; role invocation counts; elapsed time; projection/debug loads; workflow/validator outcome; review findings/decision; correctness/test results; durable artifact validation; and resume result.

Release acceptance requires materially lower parent uncached input and parent turns on representative runs, no material compensating increase in child input/turns or duplicate specialist invocation, preserved research/implementation/reviewer separation, valid durable artifacts, successful resume behavior, and equal-or-better correctness/review/final semantics. No percentage threshold is claimed before baseline measurement. A stretch target may be proposed only after measurements and must remain non-blocking unless separately approved.

## Testable invariants

- Normal controller transitions load only the controller view plus explicitly enumerated current artifacts.
- Every outcome binds to existing detailed evidence by exact path/digest and cannot outlive its graph/state/revision binding.
- A regenerated controller view is byte-deterministic for the same canonical inputs.
- Missing/stale/corrupt projection blocks or regenerates; it never invents evidence.
- Review/final approvals remain dependent on existing canonical invocation/report freshness requirements.
- Every re-dispatch has an allowed persisted reason and budget effect.
- Legacy runs do not change behavior without explicit migration.
- Runtime-specific data remains namespaced and unavailable values are not inferred.
