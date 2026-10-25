# Kapisch Product Realignment Design Specification

Date: 2026-10-25
Status: **Approved architecture direction** (owner approval; implementation is not authorized)
Source plan: [Kapisch Product Realignment and Architecture Simplification Proposal](../plans/2026-10-25-kapisch-product-realignment-proposal.md)

## 1. Intent

Kapisch coordinates human-governed AI-assisted software lifecycle work. It carries context, scopes work, dispatches bounded attempts, coordinates dependencies, aggregates evidence, supports independent review, records human decisions, and preserves durable outcomes across sessions.

This specification records the approved product and architecture contract. It is the source for later implementation planning, not authorization to change production code or runtime behavior. The source plan contains the repository assessment, removal candidates, evidence, and roadmap; this document states the target behavior and its boundaries.

## 2. Goals and non-goals

### Goals

- Make one logical task/work-order model usable across agent harnesses.
- Support independent parallel tasks when the selected host can do so.
- Preserve explicit human authority and consultation through the SDLC.
- Make task outcomes, review, decisions, and unresolved issues inspectable and shareable.
- Reconstruct the current workflow after a fresh controller session from validated persisted authority.
- Prefer readable files, Git, and existing host persistence over new infrastructure.
- Preserve the actively used `kapisch-reviewer` as an advisory capability with reusable SDLC lenses.

### Non-goals

- Replacing Git, the host agent runtime, filesystem, or deployment platform.
- Preserving runtime compatibility with historical V2/V3 execution formats or migrating old run data.
- Building a database, event-sourcing system, general recovery framework, or separate review-approval subsystem.
- Claiming shell-enforced read-only review for a host where command execution can write.
- Allowing agents or reviewer verdicts to supply human approval, expand authorized scope, or execute release actions.

### Anti-goals

Do not preserve an abstraction solely because it exists in V2/V3; reintroduce old lifecycle machinery under new names; silently emulate an unsupported host capability; treat a missing result as proof that an action did not happen; reset or clean shared/user-owned work; or let presentation style change facts, evidence, decisions, or authority.

## 3. Approaches considered

1. **Preserve the V2/V3 staged execution model.** This offers continuity and historical-format compatibility, but retains complexity the owner does not require and conflicts with the product's task-first parallel workflow. Not selected.
2. **Incrementally simplify V3.** This can reuse modules, but risks carrying old authority and lifecycle assumptions into the replacement. With no old-format compatibility requirement, it makes the clean boundary harder to maintain. Not selected as the target.
3. **Use a task-first, harness-neutral contract.** Model Context, approved WorkOrders/DAGs, execution-time attempts, aggregation/review, HumanDecisions, and Outcomes using readable files, Git, and existing host facilities. This is the approved direction. Preserve useful policy, reviewer, installation, and adapter capabilities where they fit; do not preserve old execution semantics as runtime authority.

These alternatives were assessed in the source plan (§10). The selected approach is approved; the detailed schemas, adapter operations, and implementation sequence remain delegated engineering design work.

## 4. Conceptual responsibilities

These terms define semantic responsibilities, not a frozen file layout or schema. Exact artifact boundaries, fields, canonicalization, and producers are implementation-planning decisions subject to §10.

- **Context** carries relevant project material, source references, existing decisions, and verified outcomes into a later stage or session. It is not itself an approval.
- **WorkOrder** states authorized scope and the required task DAG, including dependencies and any task-specific policy. Human approval of a WorkOrder authorizes its listed tasks within that explicit scope.
- **Task** is a required unit of work in the approved DAG. The DAG defines tasks and dependencies, not future execution attempt IDs.
- **Attempt** is one bounded execution of a task. Create its identity when execution occurs. Each worker/attempt has a distinct output location; a retry creates a new attempt and preserves earlier evidence.
- **HumanDecision** is immutable evidence of a human answer or authorization. It is bound to its original question, relevant governing inputs, explicit subject, and authorization scope. Applicability to later work is assessed separately; ordinary answer propagation does not mutate the original decision.
- **Review report** records advisory lens findings and the reviewer’s original verdict. It does not grant human authority and is not rewritten when a human records an exception.
- **Aggregation report** is produced by the LLM aggregator and makes required-task coverage, selected outcomes, evidence references, failed/superseded/late/conflicting attempts, missing work, and unresolved issues visible before dependent work proceeds.
- **Outcome** records the durable result of the WorkOrder or lifecycle stage, including the evidence and decisions that support it.

The LLM aggregator performs evidence-based aggregation and produces the aggregation report. The coordinator validates required-task coverage and evidence references, applies dependency/acceptance gates, and alone controls transitions. The host adapter owns host-specific dispatch and capability reporting. Agents and reviewers return evidence; they do not publish human authority.

## 5. Normative behavior

### 5.1 Human consultation and decisions

1. Before asking, inspect relevant Context, prior Decisions, contracts, ADRs, and evidence. Do not ask a question already answered by current applicable material.
2. Ask only material unresolved questions. State assumptions and unknowns; provide evidence, options, trade-offs, a justified recommendation, affected scope, and the authority required.
3. Persist human answers and corrections with references so later stages and fresh sessions can use them.
4. Preserve the original question, governing inputs, subject, answer, and scope in the immutable HumanDecision. A new Context carrying that answer is propagation, not a new decision and not a reason by itself to invalidate the original.
5. Reassess applicability after a substantive governing-input change. Obtain a fresh HumanDecision only when the existing answer or authorization no longer covers the affected work. Do not infer approval from agent output, reviewer verdict, timestamps, context changes, or task completion.
6. An approval of a WorkOrder DAG authorizes its listed tasks and demonstrably in-scope additions within the approved scope. Do not require per-task or per-attempt approval for work inside that scope. If a task would exceed scope, pause for discussion/research and explicit additional human approval.

### 5.2 Task DAG, attempts, parallelism, and aggregation

1. The approved WorkOrder defines required tasks and dependencies. Future attempt identities are created as execution occurs; they are not enumerated in or used to reapprove the DAG.
2. Dispatch independent ready tasks concurrently when the adapter supports every required capability. If a required capability is unsupported, unknown, or unproven, block the affected work unless an explicit human re-scope changes or removes that requirement.
3. Every worker/attempt has a unique run/task/attempt output location. Read-only research or review may share a read-only repository view. Use one task-level branch/worktree only when mutable repository isolation is needed, with one designated writer. Separate worktrees are for independent tasks/PRs that need separate mutable checkouts, not a default per-worker/per-attempt rule.
4. The LLM aggregation barrier may run when the batch completes or when a task reaches an explicit terminal/interrupted condition, including failure, cancellation, timeout, disappearance, or interruption; it must not wait indefinitely for an unavailable result. At each run, the aggregator accounts for every required task using observed status and evidence, including successful, failed, interrupted, cancelled, and missing results. It reports contradictions, incomplete work, and unresolved questions. A later result may produce a new report; it does not rewrite an earlier report.
5. Report production and transition-barrier satisfaction are distinct. A report documenting failure or incompleteness is valid evidence, but does not satisfy required-work criteria. Missing or invalid required outcomes cannot meet downstream dependencies. The coordinator decides which dependent tasks are blocked and which independent work may continue.
6. The coordinator validates the aggregation report’s required-task coverage and evidence references, applies the explicit dependency/acceptance policy, and alone controls transitions or issues dependent WorkOrders. A completeness check by the coordinator alone does not replace the LLM aggregation barrier. The report is evidence, not human approval.
7. An in-scope retry creates a fresh attempt identity and output location without editing or reapproving the DAG. It does not require another human approval solely because a prior attempt failed.

### 5.3 Local failure and recovery

1. For isolated local failure, prefer fail-and-retry from a verified compatible Git checkpoint or durable handoff.
2. Preserve the failed attempt and any task worktree containing partial work. Never reset or clean a shared or user-owned checkout.
3. Reject a checkpoint whose governing inputs are stale or whose compatibility cannot be verified. Do not infer safety from a missing process/session result.
4. Ordinary local retries do not use remote-effect reconciliation machinery. A human direction to fix a failed review authorizes remediation only; dependent tasks remain blocked until a new review passes its required criteria or a separate permitted HumanDecision exception authorizes proceeding.

### 5.4 Independent review and exceptions

1. `kapisch-reviewer` reports requested lens findings and recommendations. It is advisory and never supplies human approval.
2. Preserve the portable, reusable lens families in the [source plan’s reviewer architecture](../plans/2026-10-25-kapisch-product-realignment-proposal.md#7-reviewer-architecture): intent and requirements completeness; research and documentation quality; architecture, ADRs, API/event contracts, and NFRs; decision readiness before human approval; code quality and maintainability; security, permissions, privacy, and isolation; testing strategy, coverage, and verification; and operational/deployment readiness. Preserve applicable existing risk lenses, including compatibility, concurrency, data, tenant isolation, audit, migration, and recovery where relevant. Review must work across SDLC artifacts and decisions, not only code changes or Git commits.
3. Each lens has defined evaluation criteria and expected evidence in the shared portable contract; do not create a separate framework or subsystem per lens. A WorkOrder may require particular lenses to meet its pass criteria before dependent tasks proceed; exact per-WorkOrder criteria and permitted exceptions remain delegated design details.
4. Preserve the review report and original verdict. A permitted human exception is a separate HumanDecision referencing the relevant verdict and authorizing only the stated in-scope continuation; it must not rewrite the report.
5. Generic risk acceptance cannot waive normative or security restrictions. A prohibited exception blocks.
6. Human-directed review/fix steps remain within approved scope. A fix direction does not release dependent tasks. Pending, interrupted/resumed, or still-failing remediation keeps them blocked. Release requires a new passing review or a separate permitted HumanDecision exception.
7. Do not implement an autonomous unbounded review/fix loop or a separate review-approval subsystem. Scope growth requires discussion/research and additional human approval.
8. Claim read-only capability only where the adapter enforces it and evidence proves it. Pi must report read-only review unsupported while Bash can bypass tool-level write restrictions.

### 5.5 External effects

For an ambiguous remote side effect (for example, a push, merge, deployment, or non-idempotent API write), keep retry blocked until an authoritative query establishes the exact outcome or the human records explicit scoped authorization to proceed. A missing agent result is not proof that the effect did not occur. Do not burden ordinary local retry with this remote-only safeguard.

### 5.6 Harness portability and presentation

1. The core WorkOrder, task, decision, review, evidence, and outcome semantics must not depend on a particular agent host.
2. Adapters report actual capabilities; unsupported operations must be surfaced, not silently emulated. If a WorkOrder requires a capability the selected adapter reports unsupported, unknown, or cannot prove enforced, block the affected dispatch or continuation. Proceed only after an explicit human re-scope changes or removes that requirement; disclosure alone is insufficient. Host-specific dispatch, permissions, session identifiers, and installation remain adapter concerns.
3. Acceptance must run the same logical WorkOrder through one real adapter and a lightweight test adapter, comparing logical status, authority, decisions, evidence references, reports, and Outcome.
4. Default output is audience-neutral plain language. A user-selected presentation style may change wording only; normalized facts, evidence, options, recommendations, decisions, and authority must remain identical.

### 5.7 Persistence, provenance, and cold restart

1. Prefer readable files, Git artifacts, and existing host-native session/run persistence. No database or custom recovery framework is required by this design. Reconsider storage only if a verified scenario cannot be safely served by files and host APIs.
2. Reconstruct current work, decisions, open questions, required-task coverage, evidence references, and the next valid action after controller restart from validated persisted authority alone. Do not rely on conversational state, process memory, caller honesty, or mutable derived views.
3. Kapisch-authored canonical records must have clear ownership and source provenance. Authority-bearing fields within those records have one clear owner; retain only the references needed to explain decisions and transitions.
4. External documents, Git artifacts, ADRs, issue-tracker records, and agent-runtime results may be referenced as evidence by their original author/issuer/source and stable identifier or location; they do not need Kapisch-specific producers or copied Kapisch records. Preserve the distinction between HumanDecision authority, agent observations, and reviewer findings.
5. Keep provenance lightweight and proportional to orchestration needs. Do not add producer registries or chains, extra authority protocols, or schema frameworks solely to establish provenance.
6. Validate canonical authority and evidence at persistence/protocol boundaries; fail closed on malformed, stale, missing, or conflicting authoritative data. Derived views and presentation copies are never authority.

## 6. Lifecycle flows

### 6.1 Consult, scope, and approve

Start from existing Context and source material; identify a material unresolved question; present evidence/options/trade-offs and the required authority; persist the human answer as an immutable HumanDecision; then create or update a WorkOrder DAG with explicit scope, tasks, dependencies, and applicable policy. Work inside that approved scope proceeds without per-task approval. Pause and consult before scope expansion.

### 6.2 Execute a DAG and aggregate

Dispatch ready independent tasks through the selected adapter, each with a unique output location, only when required capabilities are supported or explicitly re-scoped. Record each returned attempt and its evidence. Run the LLM aggregator when the batch completes or a task reaches an explicit terminal/interrupted condition (failure, cancellation, timeout, disappearance, or interruption); do not wait indefinitely for an unavailable result. The aggregator accounts for every required task, including successful, failed, interrupted, cancelled, and missing results, and produces a report preserving evidence, contradictions, incomplete work, and unresolved questions. A failure/incompleteness report is valid evidence but does not satisfy required-work criteria; missing or invalid outcomes cannot release dependent tasks. The coordinator decides which dependencies remain blocked and which independent work may continue, and alone controls transitions. Later results may produce a new report. Do not add a generalized recovery engine, transaction coordinator, or sophisticated timeout-management subsystem.

### 6.3 Retry a failed local task

Preserve the failed attempt and partial work. Verify checkpoint compatibility against the task’s governing inputs, then create a fresh in-scope attempt with a new identity and output location. Keep the original DAG and its approval unchanged. Never clean shared/user-owned work to make the retry convenient.

### 6.4 Review, remediate, and continue

Run the requested `kapisch-reviewer` lenses and persist the original report/verdict. If a required lens fails, the human may direct an in-scope fix; that authorizes the fix only, so dependent work remains blocked. A new passing report releases the gate. Where WorkOrder policy permits, a separate scoped HumanDecision may authorize an exception without changing the report. Normative/security prohibitions cannot be excepted.

### 6.5 Handle an uncertain remote effect

When a remote operation may have happened but its result is uncertain, query the authoritative operation/target. Retry only after its exact state is known or the human records explicit scoped authorization. Do not infer non-occurrence from agent silence.

### 6.6 Resume after a fresh session

Load validated Context, WorkOrders, decisions, attempts, reports, outcomes, and adapter-owned metadata. Recompute what is applicable and which required tasks have valid outcomes. Present the next valid action and unresolved issues without depending on previous chat or process memory.

## 7. Compatibility and cutover boundary

- Do not add V2/V3 runtime readers or migrate historical run data. Git source history retains old code and documents.
- Remove superseded runtime paths only after the replacement’s bounded acceptance slice passes and reviewer availability/invocation, packaging, generated artifacts, and new-format entrypoints are verified.
- Preserve `kapisch-reviewer` and necessary installation interfaces unless a tested replacement exists. Preserve useful policy and evidence requirements, not historical reader implementations merely for continuity.
- The first real adapter and any claim of permission enforcement are selected only after capabilities are verified. An unsupported capability remains unsupported.

The concrete removal inventory and repository evidence are maintained in the source plan, not duplicated here.

## 8. Acceptance criteria

The later implementation plan must turn these criteria into focused automated tests and real-adapter smoke tests:

1. A single-task SDLC flow reaches a durable Outcome while respecting human decisions and deployment authorization boundaries.
2. Existing decisions prevent duplicate questions; propagation preserves identity; substantive governing changes trigger applicability reassessment; in-scope DAG tasks proceed without per-task approval; out-of-scope work blocks.
3. An LLM aggregation barrier can produce a report at batch completion or an explicit terminal/interrupted condition without waiting indefinitely. It accounts for all required tasks, including failed, interrupted, cancelled, and missing results, and preserves evidence, contradictions, incomplete work, and unresolved questions. A failure report is valid evidence but does not satisfy downstream requirements; missing or invalid results keep dependent tasks blocked while eligible independent work may continue. Coordinator-only completeness checking cannot substitute for the LLM barrier.
4. In-scope retries use fresh attempt IDs/output locations, preserve failed work, reject stale checkpoints, and never reset shared/user-owned work.
5. Reviewer reports remain immutable; remediation alone does not release dependencies; only a passing new review or permitted separate HumanDecision exception does. Prohibited exceptions and normative/security waivers block.
6. Ambiguous remote effects block retry until authoritative outcome observation or explicit scoped human authorization; local retries do not invoke that remote gate.
7. The same WorkOrder produces equivalent logical status, authority, decisions, evidence references, reports, and Outcome through a real adapter and test adapter. Missing capabilities are visible; a required capability that is unsupported, unknown, or unproven blocks affected dispatch/continuation unless an explicit human re-scope changes the requirement.
8. Fresh-session reconstruction succeeds without conversational/process memory or mutable derived authority.
9. Presentation styles preserve normalized facts, evidence, options, decisions, and authority.
10. Reviewer installation/invocation and new-format packaging are verified before any legacy-path removal; no old-format migration is required or claimed.

## 9. Delegated engineering design responsibilities

The implementation planner owns the smallest sufficient choices for:

- Artifact schemas, canonical fields, producer ownership, and publication ordering.
- Selected task-outcome representation and attempt-to-outcome references.
- Decision applicability and scope validation representation.
- Checkpoint identity/compatibility selection and bounded retry mechanics.
- Per-WorkOrder review-lens pass criteria and which findings may be excepted.
- Narrow adapter operations, capability declarations, and the first real host.
- Validator/CLI retention or replacement and legacy-removal timing.

These choices are not independent human approval gates. Escalate only if a decision would change product intent, approved scope, human authority, security boundaries, external-effect permissions, or introduce a material architectural trade-off that cannot be resolved from the approved requirements. Record technical choices, evidence, and rationale in the implementation plan. Any implementation remains subject to a separately approved execution scope.

## 10. Approval and change control

The repository owner approved the architecture direction on 25 Oct 2026. This specification does **not** authorize production implementation, runtime behavior changes, deletion, migration, installation changes, commits, pushes, merges, releases, or other external actions. Those require their own explicit authorization. Changes to the approved requirements or escalation boundaries must be returned to the owner; implementation details within the boundaries above belong to engineering planning.
