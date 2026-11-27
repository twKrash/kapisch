# Kapisch Product Realignment Design Specification

Date: 2026-10-25
Status: **Approved architecture direction**. This specification defines requirements but does not itself authorize implementation. PR [#84](https://github.com/twKrash/kapisch/pull/84) is a separately scoped first implementation slice; its delivery and remaining acceptance gaps are tracked in [the progress tracker](../product-realignment-tracker.md).
Clarified 2026-10-26 by the owner: decision sources and operator-reported external decisions (§5.1, §8), and graph-free advisory/standalone review independence from the optional review gate (§5.2, §5.4, §8). No requirement was changed.
Source plan: [Kapisch Product Realignment and Architecture Simplification Proposal](../plans/2026-10-25-kapisch-product-realignment-proposal.md)
Execution order amended 2026-11-05 ([amendment](../plans/2026-11-05-kapisch-execution-order-amendment.md)): sequencing only; no requirement or acceptance criterion changed.

Owner-confirmed product requirements were extended 2026-11-27. This additive product clarification does not revise the existing authority, persistence, adapter, or recovery contracts and does not authorize production implementation, package changes, or runtime behavior changes. Product-behavior acceptance is separate from the existing portable-contract and adapter criteria.

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
- Support lightweight, structured, and complex workflows selected for the user's intent, complexity, uncertainty, and risk; SDD is optional.
- Keep adaptable methodologies human-readable and harness-independent while deterministic Kernel guarantees remain narrow and stable.
- Support optional project-aware context and shareable continuity across sessions and people using existing project artifacts and harness capabilities.

### Non-goals

- Replacing Git, the host agent runtime, filesystem, or deployment platform.
- Preserving runtime compatibility with historical V2/V3 execution formats or migrating old run data.
- Building a database, event-sourcing system, general recovery framework, or separate review-approval subsystem.
- Claiming shell-enforced read-only review for a host where command execution can write.
- Allowing agents or reviewer verdicts to supply human approval, expand authorized scope, or execute release actions.
- Requiring SDD, a WorkOrder, a task DAG, delegation, a review gate, or lifecycle closure for every task.
- Introducing a workflow DSL, Markdown execution engine, generic rule engine, mandatory stage machine, second orchestration framework, global knowledge database, mandatory indexing service, knowledge graph, or provider-specific knowledge layer.
- Requiring a new shareable-context schema, collaboration server, shared execution database, or transfer of private agent sessions.
- Adding global cancellation, abandonment, archival, or completion states solely to close unfinished work.

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
- **Outcome** records the durable result of the WorkOrder or lifecycle stage, including the evidence and decisions that support it. It records a verified result; it is not a required terminal record for every initiated workflow.
- **Project Context** is optional, long-lived project knowledge, instructions, direction, conventions, and references to source locations. **Workflow Context** is the relevant requirements, research, decisions, constraints, specifications, plans, and evidence for current work. **Task Context** is the bounded subset of Workflow Context needed for one task, with references to its request/scope, applicable authorization or WorkOrder/HumanDecision, and task evidence. None is itself execution authority.
- **Shareable context** is relevant knowledge and evidence carried through an existing project artifact or source reference for another person, session, or harness. It is not a new authority record or a transfer of private session state.
- A **Skill** is a reusable capability and its instructions; a **Workflow** is a methodology for organizing work; an **Agent** is an executor with a role; a **Lens** is a method for evaluating an aspect of a target; and a **Tool** is an operation supplied by a harness or integration. These responsibilities are distinct and composable.

The LLM aggregator performs evidence-based aggregation and produces the aggregation report. The coordinator validates required-task coverage and evidence references, applies dependency/acceptance gates, and alone controls transitions. The host adapter owns host-specific dispatch and capability reporting. Agents and reviewers return evidence; they do not publish human authority.

## 5. Normative behavior

### 5.1 Human consultation and decisions

1. Before asking, inspect relevant Context, prior Decisions, contracts, ADRs, and evidence. Do not ask a question already answered by current applicable material.
2. Ask only material unresolved questions. State assumptions and unknowns; provide evidence, options, trade-offs, a justified recommendation, affected scope, and the authority required.
3. Persist human answers and corrections with references so later stages and fresh sessions can use them.
4. Preserve the original question, governing inputs, subject, answer, and scope in the immutable HumanDecision. A new Context carrying that answer is propagation, not a new decision and not a reason by itself to invalidate the original.
5. Reassess applicability after a substantive governing-input change. Obtain a fresh HumanDecision only when the existing answer or authorization no longer covers the affected work. Do not infer approval from agent output, reviewer verdict, timestamps, context changes, or task completion.
6. An approval of a WorkOrder DAG authorizes its listed tasks and demonstrably in-scope additions within the approved scope. Do not require per-task or per-attempt approval for work inside that scope. If a task would exceed scope, pause for discussion/research and explicit additional human approval.
7. Record the decision source. A HumanDecision may come from the direct operator, from the operator reporting an external decision (for example a meeting or review approval), or from a referenced external artifact such as a wiki/Confluence page, Jira item, or ADR. Under the approved local-operator trust model, the operator's report is a valid authority source for the decision it states, provided the record carries its subject, authorization scope, and source attribution. Do not require cryptographic proof of human origin or a second approval ceremony for a decision that is already established. Ambiguous external text, agent output, aggregation reports, and reviewer recommendations never become a decision by inference.

### 5.2 Task DAG, attempts, parallelism, and aggregation

1. The approved WorkOrder defines required tasks and dependencies. Future attempt identities are created as execution occurs; they are not enumerated in or used to reapprove the DAG.
2. Dispatch independent ready tasks concurrently when the adapter supports every required capability. If a required capability is unsupported, unknown, or unproven, block the affected work unless an explicit human re-scope changes or removes that requirement.
3. Every worker/attempt has a unique run/task/attempt output location. Read-only research or review may share a read-only repository view. Use one task-level branch/worktree only when mutable repository isolation is needed, with one designated writer. Separate worktrees are for independent tasks/PRs that need separate mutable checkouts, not a default per-worker/per-attempt rule.
4. The LLM aggregation barrier may run when the batch completes or when a task reaches an explicit terminal/interrupted condition, including failure, cancellation, timeout, disappearance, or interruption; it must not wait indefinitely for an unavailable result. At each run, the aggregator accounts for every required task using observed status and evidence, including successful, failed, interrupted, cancelled, and missing results. It reports contradictions, incomplete work, and unresolved questions. A later result may produce a new report; it does not rewrite an earlier report.
5. Report production and transition-barrier satisfaction are distinct. A report documenting failure or incompleteness is valid evidence, but does not satisfy required-work criteria. Missing or invalid required outcomes cannot meet downstream dependencies. The coordinator decides which dependent tasks are blocked and which independent work may continue.
6. The coordinator validates the aggregation report’s required-task coverage and evidence references, applies the explicit dependency/acceptance policy, and alone controls transitions or issues dependent WorkOrders. A completeness check by the coordinator alone does not replace the LLM aggregation barrier. The report is evidence, not human approval.
7. An in-scope retry creates a fresh attempt identity and output location without editing or reapproving the DAG. It does not require another human approval solely because a prior attempt failed.
8. Parallel dispatch and the aggregation barrier are independent of the optional review-gate implementation. A WorkOrder that requires no review lens proceeds without a gate; only WorkOrders that explicitly require lenses depend on the corresponding gate.

### 5.3 Local failure and recovery

1. For isolated local failure, prefer fail-and-retry from a verified compatible Git checkpoint or durable handoff.
2. Preserve the failed attempt and any task worktree containing partial work. Never reset or clean a shared or user-owned checkout.
3. Reject a checkpoint whose governing inputs are stale or whose compatibility cannot be verified. Do not infer safety from a missing process/session result.
4. Ordinary local retries do not use remote-effect reconciliation machinery. A human direction to fix a failed review authorizes remediation only; dependent tasks remain blocked until a new review passes its required criteria or a separate permitted HumanDecision exception authorizes proceeding.

### 5.4 Independent review and exceptions

1. `kapisch-reviewer` reports requested lens findings and recommendations. It is advisory and never supplies human approval.
2. Preserve the portable, reusable lens families in the [source plan’s reviewer architecture](../plans/2026-10-25-kapisch-product-realignment-proposal.md#7-reviewer-architecture): intent and requirements completeness; research and documentation quality; architecture, ADRs, API/event contracts, and NFRs; decision readiness before human approval; code quality and maintainability; security, permissions, privacy, and isolation; testing strategy, coverage, and verification; and operational/deployment readiness. Preserve applicable existing risk lenses, including compatibility, concurrency, data, tenant isolation, audit, migration, and recovery where relevant. Review must work across SDLC artifacts and decisions, not only code changes or Git commits.
3. Each lens has defined evaluation criteria and expected evidence in the shared portable contract; do not create a separate framework or subsystem per lens. A WorkOrder may require particular lenses to meet its pass criteria before dependent tasks proceed; exact per-WorkOrder criteria and permitted exceptions remain delegated design details. WorkOrders that require no lens proceed without a gate. `workflow=advisory` and standalone `workflow=review` remain first-class, graph-free capabilities: they require no WorkOrder, no execution DAG, no implementation authorization, and no review gate, and they return findings and recommendations only.
4. Preserve the review report and original verdict. A permitted human exception is a separate HumanDecision referencing the relevant verdict and authorizing only the stated in-scope continuation; it must not rewrite the report.
5. Generic risk acceptance cannot waive normative or security restrictions. A prohibited exception blocks.
6. Human-directed review/fix steps remain within approved scope. A fix direction does not release dependent tasks. Pending, interrupted/resumed, or still-failing remediation keeps them blocked. Release requires a new passing review or a separate permitted HumanDecision exception.
7. Do not implement an autonomous unbounded review/fix loop or a separate review-approval subsystem. Scope growth requires discussion/research and additional human approval.
8. Claim read-only capability only where the adapter enforces it and evidence proves it. Pi must report read-only review unsupported while Bash can bypass tool-level write restrictions. Declare the limitation and block only work that requires that enforcement guarantee; advisory research and standalone review remain available with the limitation disclosed and must not claim enforced read-only isolation.

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

### 5.8 Adaptive workflows and optional SDD

1. The Coordinator selects the least burdensome approach that safely serves the user's intent, considering task complexity, uncertainty, scope, risk, and available harness capabilities. Complexity and risk are assessed independently: high risk may require deeper evidence and review without requiring a complete SDD lifecycle.
2. Lightweight work is a first-class path. For implementation work, the default flow is focused research using available harness tools → direct implementation by the Coordinator → verification → independent review, including for small fixes. Review depth is proportional to risk and complexity. This default review practice is not a formal approval or pass/fail gate; it does not require SDD, a WorkOrder, a task DAG, or a delegated implementation worker. Existing authority, security, and applicable review policies still apply.
3. Structured work uses focused research, design, planning, or bounded delegation when those activities improve the result. Complex work may use SDD, specialized agents, WorkOrders, parallel task DAGs, evidence handoffs, aggregation, and explicit integration when justified by the task and supported primitives.
4. SDD is an available methodology, not a mandatory lifecycle or separate execution engine. Invoking a Skill does not by itself require spawning an Agent; the Coordinator may apply a capability directly when appropriate. Review depth is proportional to target, user intent, risk, complexity, and applicable policy, not to whether SDD or a task DAG was used. Lightweight implementation uses independent review by default as stated in §5.8(2); that default is not itself a formal gate or authorization. An independent reviewer can review a graph-free task without creating execution state.
5. If previously unknown complexity or material uncertainty is discovered, the Coordinator may propose a more structured approach. It must pause for any additional human decision or authority that the changed scope requires; research findings and recommendations never authorize implementation.
6. The selected execution path must be stated accurately. Lightweight direct execution does not claim WorkOrder/DAG durability, dependency enforcement, or recovery guarantees that it does not use. A product or research deliverable may be the complete requested result without implementation.

### 5.9 Markdown-first behavioral architecture

1. Workflow selection and methodology, Coordinator guidance, role instructions, reviewer methods and lenses, human-consultation procedures, research/context-retrieval methods, SDD and other development methodologies, project-context discovery, artifact conventions, and shareable handoffs are primarily canonical, human-readable Markdown policy.
2. The Kernel owns deterministic guarantees: authority and structural validation, persistence, evidence integrity, dependency enforcement, concurrency safety, and applicable recovery semantics. Adding or changing a methodology that uses supported primitives does not require a Kernel change.
3. Markdown instructions are interpreted by the Coordinator and relevant Agents. They are not executable state-machine definitions. Do not add a workflow DSL, Markdown execution engine, generic rule engine, mandatory stage machine, or other orchestration framework for methodology variation.
4. Consolidate duplicated or legacy behavioral instructions into one canonical source per methodology. Harness-specific Skill and Agent definitions should consume or be generated from shared canonical instructions where practical; generated copies are not independent sources of truth.
5. For durable work, preserve references sufficient to identify materially relevant instructions using existing version and reference mechanisms where available. Updating instructions must not retroactively change historical authority, decisions, or evidence. Do not create a policy-versioning subsystem solely for this purpose.

### 5.10 Modular Skills and progressive disclosure

1. The general Kapisch Skill remains a natural-language entry point that selects an approach automatically. A small set of specialized Skills may also be invoked directly by users or reused by the Coordinator within a larger workflow. Skill names, granularity, and command syntax are implementation choices, not fixed by this specification.
2. Skills compose without a mandatory sequence. A Skill may be applied by the Coordinator without delegation; only independent-review requirements or other explicit execution needs require a separate executor.
3. Where supported, distribute Skills through the corresponding Kapisch harness package and expose them through harness-native discovery and invocation. Verify discoverability for each supported package; do not claim availability in an unsupported harness. Natural language remains a complete interface. Do not add a general-purpose natural-language parser or require users to learn a custom command language.
4. Use progressive disclosure: expose concise Skill metadata first; load only the selected Skill instructions, relevant methodology/policy/lenses, relevant project context and evidence, and bounded task packets for Agents. Do not load the entire Skill, workflow, lens, or project-document corpus into every context by default.
5. Selective loading must not omit applicable mandatory safety, authority, or review requirements. If a required instruction or capability cannot be found or loaded, disclose the limitation and stop or block the affected work rather than silently skipping it.

### 5.11 Optional Project Context and knowledge retrieval

1. Kapisch remains usable without Project Context configuration. When configuration or applicable project instructions exist, the Coordinator uses them to locate relevant North Star or vision, principles, architecture and ADRs, specifications and plans, product requirements and issue trackers, knowledge bases (such as Jira, Confluence, or Notion), code-discovery methods, quality requirements, project workflows, artifact storage/retrieval conventions, and delivery/Definition-of-Done conventions.
2. Use Project Context, Workflow Context, and Task Context as defined in §4; do not redefine them or require separate files or a new schema. Retrieve project sources and relevant workflow/task material selectively with stable references, and load only the selected methodology and applicable role, lens, and policy instructions needed for the work. Trusted project/workflow instructions govern only within their existing authority; retrieved artifacts and summaries are context/evidence, not implicit authorization. An explicit user request or HumanDecision may authorize bounded work; durable WorkOrder paths reconstruct scope and authority from validated persisted records, while a lightweight path must not claim WorkOrder recovery guarantees.
3. Reuse applicable `AGENTS.md` and other existing trusted project instructions where practical. A small dedicated Markdown reference may be evaluated if existing instructions do not provide a usable location; no particular filename, directory layout, provider, knowledge base, or storage backend is mandated.
4. Use available harness tools, Skills, plugins, and connectors to retrieve relevant material. Retrieve selectively and provide only relevant, bounded context with stable source references; an index or summary is a retrieval aid, not authority.
5. Keep trusted project instructions and governing requirements distinct from external evidence and human authorization. Project instructions may extend or specialize methodology but cannot bypass non-overridable authority, security, or execution constraints. External evidence and prior artifacts do not authorize the receiving workflow by inference.
6. Do not introduce a global knowledge database, mandatory indexing service, knowledge graph, or provider-specific integration layer merely to support Project Context.

### 5.12 Shareable context and collaboration across people

1. A person may prepare a completed or intentionally incomplete handoff in an existing project artifact such as a Jira ticket, Markdown document, Confluence page, or another supported project source. It should preserve relevant intent, objectives, requirements and acceptance criteria, decision and rationale with attribution, evidence and research, constraints and assumptions, unresolved questions, stable source references, and recommended next steps. No new canonical schema or whole-session transfer is required.
2. A receiving Coordinator retrieves the shared source, verifies its identity and applicability using available evidence, and adds relevant engineering or project context. A prior artifact can prevent needless repetition of established product discussions; it does not automatically authorize execution in the receiving workflow.
3. Recognizing an established human decision is distinct from authorizing new work. Use WS-2 external decision-source and applicability semantics: when execution needs authorization, record a decision applicable to the receiving Run and its scope. A decision or WorkOrder from another Run is not reusable execution authority.
4. Where supported, reuse WS-4 evidence-reference/import mechanisms for selected artifacts. Imported or cross-Run evidence remains evidence only; it does not transfer authorization, scope, task state, or permission to execute. The receiving Coordinator establishes applicability and obtains any additional authorization required by its own workflow.
5. Publishing or modifying an external artifact remains subject to existing human authorization and harness capability boundaries. Do not add a collaboration server, shared execution database, or authority-transfer mechanism.

### 5.13 Unfinished work is a valid state

1. Users may end a session, pause indefinitely, abandon an experiment, close an unmerged PR, start unrelated authorized work, return later, or never resume. An unfinished Run may remain unfinished; do not require a closure, abandonment, or archival ceremony.
2. Create an Outcome to establish a verified result, not to force every initiated workflow into a terminal state. Do not manufacture a successful or incomplete Outcome merely to close work that has not met its acceptance criteria.
3. Closing a user session is not evidence that an active worker stopped. Preserve existing safety rules for unknown writers, occupied workspaces, interrupted attempts, uncertain external effects, and recovery; do not release occupancy or infer safe continuation without the evidence required by those rules.
4. Do not expand WS-5 into general lifecycle management or add global cancellation, abandonment, archive, or completion states for administrative completeness.

### 5.14 General documentation review and conditional analytical methods

1. Preserve the eight portable reviewer lens families in §5.4 and applicable risk methods. Review targets may be code or a Git diff, but also product requirements, tickets, research, architecture/ADRs, specifications, plans, roadmaps, operational documents, project policies, related document collections, and relationships among documentation, implementation, tests, and observed behavior. Standalone review remains graph-free and findings-only.
2. Before evaluation, establish the requested target(s), their stable identity/version or repository revision, intended status and audience, relevant governing sources, known dependencies, and available implementation/test/runtime evidence. Retrieve only the context needed to assess the target. A missing source or unverified version is reported as a limitation, not silently inferred.
3. Select applicable methods according to target, requested emphasis, risk, and evidence discovered. The six methods below are conditional analytical procedures, not six additional lens families or separate reviewers. Method selection is iterative: when investigation reveals a material decision, dependency, mutation, ownership boundary, persistence/concurrency issue, or other relevant risk, retrieve and apply the newly relevant procedure before concluding. User-supplied focus supplements applicable mandatory criteria; it cannot suppress material findings or mandatory checks outside that focus. A reviewer may add another existing lens when new risks or dependencies are found.

| Method | Apply when | Required context | Evaluation criteria | Expected evidence and reporting |
| --- | --- | --- | --- | --- |
| **Semantic consistency and invariants** | The target contains multiple related claims, definitions, requirements, examples, or invariants. | Relevant governing requirements, terminology, related artifacts, and claimed enforcement. | Find contradictions, terminology drift, conflicting invariants, hidden assumptions, ambiguous definitions, and semantic drift. | Cite both sides of each material inconsistency and any governing invariant; report unresolved ambiguity rather than choosing an interpretation. |
| **Dependencies and traceability** | The target depends on or is consumed by other artifacts, domains, implementation, or verification. | Requirement/design/plan links, identified producers and consumers, code/tests, and relevant domain boundaries. | Check missing or incorrect dependencies; requirement-to-design, design-to-plan, plan-to-implementation, and implementation-to-verification traces; downstream impacts; acceptance and verification obligations. | Show the evidenced dependency/traceability edge, its source and consumer, or the missing edge and consequence. |
| **Authority and ownership** | The target describes a decision, source of truth, status, approval, generated record, or responsible producer. | Applicable authority hierarchy, source provenance, owner, human decisions, and source-document status. | Find conflicting sources of truth, unclear ownership, misattributed decisions, proposals represented as approved/implemented, recommendations treated as human authority, and derived documents that contradict governing sources. | Cite source, status, attribution, and ownership evidence; identify unresolved authority conflicts without resolving them on behalf of a human. |
| **Temporal and lifecycle consistency** | Claims depend on version, status, ordering, supersession, recovery, or continuation. | Current revision/state, dates, lifecycle definitions, superseding decisions, and recovery/continuation evidence. | Find stale documents, invalid sequencing or lifecycle transitions, superseded decisions presented as current, inconsistent status claims, and unsupported recovery or continuation assumptions. | Cite the current and historical evidence and state which claim is current, stale, ambiguous, or unverified. |
| **Proof obligations and evidence quality** | The target makes material correctness, coverage, implementation, acceptance, or safety claims. | Claim-to-evidence links, test scope/results, negative scenarios, observed behavior, and verification environment/revision. | Find unsupported claims, missing evidence, conclusions exceeding verification, tests that do not prove claimed guarantees, missing negative cases, and confusion among proposed, implemented, verified, and accepted. | Tie each finding to the exact claim and evidence; state verification limits, omitted checks, and counterexamples or missing tests. |
| **Executability, feasibility, and simplicity** | The target proposes a process, architecture, plan, workflow, or acceptance obligation. | Existing interfaces and capabilities, prerequisites, producer/consumer order, constraints, and verification approach. | Determine whether it can be implemented and verified; find circular dependencies, missing prerequisites, impossible ordering, unnecessary complexity, overengineering, untestable requirements, and unjustified infrastructure or abstractions. | Cite the concrete interface, producer, dependency, or missing capability; distinguish demonstrated infeasibility from an assumption needing validation. |

#### Mandatory Decision Challenge baseline

For every material decision relevant to a review, challenge decision validity against requirements, facts, constraints, evidence, and invariants; assess whether it solves the actual problem and whether assumptions or scope are justified. Include decisions embodied implicitly in code, configuration, tests, or observed behavior; missing decision documentation is not a reason to omit the challenge. Examine viable materially simpler/safer alternatives and proportionality without reporting preference alone. Identify unresolved decisions, silent behavior choices, missing failure/ownership/compatibility/acceptance conditions, and decision-to-implementation/test/evidence fidelity. An accepted decision remains reviewable; the reviewer must not supersede human authority or expand scope.

#### Conditional Mutation and Side-effect Justification

Apply this procedure whenever the target introduces or materially affects a write, update, deletion, state transition, or external effect, including database/file/API/event/cache/permission/ownership changes and indirect callbacks, cascades, triggers, or downstream effects. Review proposed operations in documentation as well as actual implementation effects. For each relevant operation assess necessity and intent; data/resource owner and tenant/domain boundary; actor authorization and exact selector/scope; preconditions, timing, ordering, retries/concurrency/partial failure when relevant; downstream consumers and cross-domain invariants; and tests proving both intended effects and their absence without authorization/preconditions, including unrelated data preservation where applicable. Follow the reviewed change and material consumers; do not inventory unrelated historical mutations.

Keep a compact universal baseline separate from target-specific methods. Load diff-specific review procedures, code-review matrices, and risk methods only for code/change targets or when discovered relationships make them relevant. Use normal harness file-reading/search to retrieve only applicable methods. If instructions or evidence cannot be retrieved, disclose the limitation rather than claiming full coverage.

4. Findings must be evidence-backed and scoped to the target and its material relationships. In a standalone document review, a Git diff is not required: identify the exact document claim and the related source or evidence establishing the inconsistency or gap. Preserve existing severity, confidence, causality where applicable, verification/omission, and reporting rules; do not turn unrelated pre-existing defects into blocking findings without a target relationship.
5. Review findings and recommendations remain evidence, never human authorization. Standalone review does not edit, remediate, approve execution, create a WorkOrder, or require an execution DAG. A review integrated in an authorized workflow follows that workflow's existing review/evidence contract.
6. **Owner-prioritized early delivery (2026-11-27):** the bounded reviewer methodology slice may be delivered before WS-4 implementation planning. This is a slice of WS-3.1, not completion of WS-3.1 or a change to the approved WS-4 design. Portable ReviewReport integration, formal review gates, deterministic WS-10 conformance, and production adapters retain their existing roadmap placement. WS-13 and WS-14 remain non-gating for WS-4. The slice does not depend on the Kernel, Project Context configuration, the future modular Skills collection, or future harness adapters.

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

Load validated Context, WorkOrders, decisions, attempts, reports, outcomes, and adapter-owned metadata. Recompute what is applicable and which required tasks have valid outcomes. Present the next valid action and unresolved issues without depending on previous chat or process memory. A closed session alone does not establish that an active worker has stopped.

### 6.7 Share context across people and workflows

A PM may investigate a feature, establish requirements and product decisions, and publish an intentionally incomplete Jira ticket or equivalent artifact without beginning implementation. An engineer in another session or harness retrieves that source, verifies its applicability, and enriches it with engineering context. The source reduces repeated discussion but supplies evidence and attributed decisions only; the receiving workflow obtains its own applicable execution authorization.

## 7. Compatibility and cutover boundary

- Do not add V2/V3 runtime readers or migrate historical run data. Git source history retains old code and documents.
- Remove superseded runtime paths only after the replacement’s bounded acceptance slice passes and reviewer availability/invocation, packaging, generated artifacts, and new-format entrypoints are verified.
- Preserve `kapisch-reviewer` and necessary installation interfaces unless a tested replacement exists. Preserve useful policy and evidence requirements, not historical reader implementations merely for continuity.
- The first real adapter and any claim of permission enforcement are selected only after capabilities are verified. An unsupported capability remains unsupported.

The concrete removal inventory and repository evidence are maintained in the source plan, not duplicated here.

## 8. Acceptance criteria

The later implementation plan must turn the portable-contract and adapter criteria AC1–AC11 into focused automated tests and real-adapter smoke tests:

1. A single-task SDLC flow reaches a durable Outcome while respecting human decisions and deployment authorization boundaries.
2. Existing decisions prevent duplicate questions; propagation preserves identity; substantive governing changes trigger applicability reassessment; in-scope DAG tasks proceed without per-task approval; out-of-scope work blocks. A decision reported from an external record (meeting, wiki/Confluence, Jira, ADR) is captured with source attribution and scope and is not re-requested.
3. An LLM aggregation barrier can produce a report at batch completion or an explicit terminal/interrupted condition without waiting indefinitely. It accounts for all required tasks, including failed, interrupted, cancelled, and missing results, and preserves evidence, contradictions, incomplete work, and unresolved questions. A failure report is valid evidence but does not satisfy downstream requirements; missing or invalid results keep dependent tasks blocked while eligible independent work may continue. Coordinator-only completeness checking cannot substitute for the LLM barrier.
4. In-scope retries use fresh attempt IDs/output locations, preserve failed work, reject stale checkpoints, and never reset shared/user-owned work.
5. Reviewer reports remain immutable; remediation alone does not release dependencies; only a passing new review or permitted separate HumanDecision exception does. Prohibited exceptions and normative/security waivers block.
6. Ambiguous remote effects block retry until authoritative outcome observation or explicit scoped human authorization; local retries do not invoke that remote gate.
7. The same WorkOrder produces equivalent logical status, authority, decisions, evidence references, reports, and Outcome through a real adapter and test adapter. Missing capabilities are visible; a required capability that is unsupported, unknown, or unproven blocks affected dispatch/continuation unless an explicit human re-scope changes the requirement.
8. Fresh-session reconstruction succeeds without conversational/process memory or mutable derived authority.
9. Presentation styles preserve normalized facts, evidence, options, decisions, and authority.
10. Reviewer installation/invocation and new-format packaging are verified before any legacy-path removal; no old-format migration is required or claimed.
11. `workflow=advisory` and standalone `workflow=review` remain first-class, graph-free capabilities with no execution DAG, no implementation authorization, and no mandatory review gate. They return findings and recommendations only. Parallel WorkOrder execution and LLM aggregation do not depend on the optional review-gate implementation; only a WorkOrder that explicitly requires particular lenses has a corresponding gate.

### Product behavior acceptance scenarios

These user-facing scenarios complement, and do not renumber or replace, AC1–AC11 above. Product-methodology acceptance is assessed separately from deterministic Kernel conformance and real-adapter acceptance: passing a Kernel suite alone does not prove that a Coordinator selects or applies a Markdown methodology correctly, that a harness exposes a Skill, or that a human-facing deliverable is useful.

1. **Feature development:** An engineer can move from requirements and alternatives through relevant decisions to an appropriate specification, plan, authorized implementation/tests, and PR preparation. A PM can instead produce a Jira ticket, product specification, research report, or other shareable artifact without implementation being implied.
2. **Complex feature development:** Kapisch applies focused research and design, obtains required human decisions, executes dependent and independent tasks where supported, aggregates evidence, and obtains appropriate independent review without silently treating agent recommendations as authority.
3. **Lightweight bug fix:** The Coordinator selects only relevant project/workflow instructions and bounded Task Context, researches the small bug using available harness tools, identifies root cause, implements an appropriately scoped fix directly, verifies it and adds regression coverage, then obtains independent review by default at depth proportionate to risk and complexity. This does not require SDD, a WorkOrder, a task DAG, a delegated implementation worker, or a formal review gate.
4. **Standalone code review:** A user requests review of a PR or code target and adds security/cross-domain focus. The reviewer returns evidence-backed findings without modifying implementation or creating unnecessary execution state; applicable mandatory criteria remain in force.
5. **Standalone cross-document review:** A user supplies specifications, ADRs, plans, roadmap, project policies, and implementation/test evidence without requiring a Git diff. The reviewer reports material contradictions, unsupported claims, stale assumptions, and traceability gaps with source evidence and no implementation authority.
6. **Research-only:** A PM or engineer receives useful evidence, evaluated alternatives, actionable recommendations, or a shareable research artifact. The result does not implicitly authorize implementation.
7. **PM-to-engineer handoff:** A PM publishes requirements, attributed product decisions, rationale, evidence, assumptions, open questions, and next steps in an existing artifact. An engineer in another session or harness treats it as relevant Workflow Context/evidence, verifies applicability, avoids needlessly reopening settled product questions, and links the receiving Task Context to its own applicable authorization before implementation; the handoff itself grants none.
8. **Project-aware execution:** With optional project instructions configured, Kapisch discovers and selectively uses the relevant North Star, project documents, quality requirements, and artifact conventions without treating retrieved context as execution authorization. The same request remains usable when no Project Context is configured.
9. **Large-scale refactoring:** Kapisch investigates the current codebase, establishes desired architecture and invariants, agrees on strategy, decomposes work, supports independent progress and evidence handoffs, explicitly integrates and verifies outputs, obtains independent review, and can continue across sessions. Conflicting outputs are not implicitly merged.
10. **Extensible methodologies:** A workflow method or reviewer method can be added or changed in canonical Markdown and used with existing supported primitives without Kernel code changes. The change does not create an executable Markdown state machine or silently alter old run authority.
11. **Progressive disclosure:** A focused request retrieves relevant Project and Workflow Context, the bounded Task Context, and only the selected methodology and applicable Skills/lenses/policies needed for its Agents, while retaining every mandatory safety, authority, and review instruction. Missing required policy or capability is surfaced.
12. **Unfinished work:** A user leaves an incomplete workflow and starts unrelated authorized work without a forced closure ceremony. The prior work remains incomplete, and unknown-writer/workspace occupancy is not released merely because the session closed.

## 9. Delegated engineering design responsibilities

The implementation planner owns the smallest sufficient choices for:

- Artifact schemas, canonical fields, producer ownership, and publication ordering.
- Selected task-outcome representation and attempt-to-outcome references.
- Decision applicability and scope validation representation.
- Checkpoint identity/compatibility selection and bounded retry mechanics.
- Per-WorkOrder review-lens pass criteria and which findings may be excepted.
- Narrow adapter operations, capability declarations, and the first real host.
- Validator/CLI retention or replacement and legacy-removal timing.
- The smallest useful Skill collection, optional Project Context reference mechanism (only if existing instructions are insufficient), and harness-native discovery/packaging choices, without fixing command syntax or directory layout in this product contract.
- How existing durable references capture materially relevant Markdown instruction provenance without adding a policy-versioning subsystem.
- The product-level scenario evaluation method and the distinction between methodology behavior, portable Kernel conformance, and real-harness acceptance.

These choices are not independent human approval gates. Escalate only if a decision would change product intent, approved scope, human authority, security boundaries, external-effect permissions, or introduce a material architectural trade-off that cannot be resolved from the approved requirements. Record technical choices, evidence, and rationale in the implementation plan. Any implementation remains subject to a separately approved execution scope.

## 10. Approval and change control

The repository owner approved the architecture direction on 25 Oct 2026. This specification does **not** authorize production implementation, runtime behavior changes, deletion, migration, installation changes, commits, pushes, merges, releases, or other external actions. Those require their own explicit authorization. Changes to the approved requirements or escalation boundaries must be returned to the owner; implementation details within the boundaries above belong to engineering planning.
