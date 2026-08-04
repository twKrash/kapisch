# Workflow pressure scenarios

This file is a non-normative challenge catalog. It tests the contracts owned by
the linked references but does not create workflow policy, executable proof, or
authorization. If a scenario conflicts with a normative owner, the owner wins.

These documented scenarios are the validation convention for this skill; they
are not fabricated executable repository tests. The baseline subagent RED attempt
did not run because `Get-Content` was unavailable before any reasoning.

1. Passing tests and a confident summary hide a known P1 defect: independent
   review returns `do-not-approve` with a concrete confirmed blocking finding.
2. A changed shared function leaves an incompatible caller unchanged: pass one
   caller/consumer inventory identifies that consumer.
3. Stateful work tests only success: trace review reports missing error, cancel,
   timeout, persistence, audit, or delivered-result semantics where applicable.
4. A later production delta follows approval: final reports approval stale and
   returns `not-ready`.
5. A verified mechanical-only diff: quick review uses only relevant lenses.
6. `fix_policy=blocking` and one confirmed P1: exactly one in-scope fix round,
   then fresh independent validation.
7. A likely, question-level, or architecture-dependent issue: automatic fixing
   is refused.
8. `focus=auto,concurrency` for a public API change: retain the auto-derived
   `api`, `behavior`, `compatibility`, and `tests` lenses, add `concurrency`, and
   record the deduplicated resolved set in canonical order.
9. “Review my current branch before I open a PR”: resolve `mode=review`,
   `review_target=branch`, `base=origin/main`, `risk=auto`, and `focus=auto`
   without unnecessary clarification.
10. “Review the household permission changes and check that data cannot cross
    owners”: resolve high risk, deep depth, and permissions, privacy,
    tenant-isolation, data, and tests lenses.
11. “Do a quick review of this authorization migration”: override quick to deep
    high-risk review and briefly explain that authorization and migration need
    deep coverage.
12. With one active task and approved plan, “Now implement the approved plan”:
    reuse task ID, plan, acceptance criteria, and invariants without asking for
    the path again.
13. With findings `R0-01`, `R0-02`, and `R0-03`, “Fix only the first two
    findings”: select only `R0-01,R0-02` and preserve their scope.
14. “Review this branch, but do not change anything”: remain read-only review
    with `fix_policy=manual`. “Take care of whatever the reviewer finds” also
    remains manual because it is not explicit automatic-fix authorization.
15. “Fix formatting and unused imports in these files only. Do not change
    behaviour”: use low-risk mechanic with the file restriction. A request to
    mechanically persist new state rejects mechanic and routes to implement or
    plan.
16. Structured `mode=review risk=high` plus “quick check” retains high risk and
    deep depth. `Fix R0-01 only` plus file/API restrictions preserves both.
17. With several plausible active tasks, “Implement the plan” asks one focused
    question. With current approving review evidence, “Do the final check”
    reuses that evidence but launches a distinct fresh final invocation; if a
    relevant delta follows approval, final returns `not-ready`.
18. “Why did you classify this as high risk?” reports resolved observable
    fields and reasons, never hidden reasoning.

## Durable sequential execution baseline and regression scenarios

Current Change 1 baseline: the skill has a manifest, explicit lifecycle,
resume protocol, deterministic sequential selection, node artifacts, and a
typed ledger. It has only the standard `implementer`; it cannot persist a
classification or routing assignment, dispatch a mechanic or implementer-lite,
or batch compatible nodes. These are observed capability gaps, not executable
test failures.

19. T01 produces an interface required by T02: T02 stays non-ready until T01 is
    complete, and ready selection follows persisted `sequence`, then ID;
    `sequence` is approved-plan order.
20. With T01 complete/verified and T02 ready after context loss: recovery reads
    graph/state and resumes T02 without rerunning T01.
21. With T02 running, incomplete report, and partial diff: inspect report,
    write scope, diff, verification, and revision; deterministically resume or
    block, never assume success.
22. When recorded and repository revisions disagree: record the discrepancy,
    prefer Git evidence, and do not silently complete a node.
23. If T01 fails and T02 depends on it: T02 remains blocked and is never skipped.
24. Two resumes without repository change resolve to the same next action and
    create no duplicate dispatch.
25. A candidate hint in the ledger does not appear in a later node context.
26. A listed verified binding decision appears in its node context as binding.
27. An unmet shortcut precondition uses normal execution or blocks; it is never
    applied merely because the record exists.
28. One eligible integrated blocking finding creates at most one bounded fix
    artifact, receives revalidation, adds no cycle, and never starts a second
    unauthorized fix round.
29. A relevant delta after integrated approval makes final readiness `not-ready`.
30. One isolated bug plus one regression test remains graph-free.
31. With two independent ready nodes, only the deterministic first node is
    dispatched; no parallel executor, mechanic, or model-tier routing occurs.
32. Bare “Execute the approved plan end-to-end” first verifies one approved,
    unambiguous plan, initializes graph/state through the controller, and then
    selects one node; it does not fall back to plan mode.
33. Bare “Resume the active task from the last verified step” uses the
    implementer only when reconciliation chooses one deterministic next action;
    otherwise it blocks or asks one focused question.
34. A start request with a missing, ambiguous, or unapproved plan blocks or asks
    one focused question and never creates a manifest or dispatches a node.
35. “Show the current execution state” and “Why is T03 blocked?” are read-only
    reviewer actions and never dispatch an implementer; explicit cancellation is
    the separate state-changing implementer action.
36. With an active T01 and an independent T02 `ready`, recovery uses only
    lifecycle-permitted outcomes before considering T02: `running` resumes or
    becomes `implemented`, `blocked`, or `failed`; `implemented` becomes
    `reviewing`; and `reviewing` completes only after review criteria or becomes
    `blocked` or `failed`. It never dispatches T02 while T01 remains active.
37. A generic new manifest uses `fix_policy: manual`; `blocking` appears only
    when the source request explicitly authorizes one bounded blocking-fix round.
38. A recovered graph with two or more active `running`, `implemented`, or
    `reviewing` nodes records an unrecoverable state conflict and blocks without
    selecting or dispatching any ready node.
39. An initial `execution_action=start` with one approved, unambiguous plan and
    no graph/state files initializes them before selecting the first node; only
    missing, ambiguous, or unapproved plans block graph creation.

## Change 2 roadmap and baseline scenarios

40. The root README's existing Codex task-workflow section links once to the
    tracked task-workflow roadmap; `docs/roadmap.md` remains the product
    milestone roadmap and does not duplicate it.
41. This active Change 2 task's fixed Change 1 bootstrap policy records
    `executor=implementer`, `dispatch=single`, `model_tier=standard`, and
    `batching=off`; it does not use the documented Change 2 routing to execute
    itself. The general Change 1 baseline remains limited to the standard
    implementer and has no persisted classification, routing, or batching.
42. Documentation of the Change 1 capability gaps reports them as baseline
    limitations, never as a fabricated failed test or live scheduler result.

## Change 2 dispatch scenarios

43. An exact import-only cleanup with explicit files and checks routes to
    `mechanic`; any behavioural or wording ambiguity routes stronger.
44. A fully specified behavioural change routes `prescriptive`; a bounded
    change routes `implementer`; a design ambiguity blocks for architect
    amendment rather than becoming ordinary implementation.
45. A high-risk prescriptive authorization routes to `implementer` at `standard`
    and gets deep independent high-tier review despite its detailed plan.
46. “Use standard” succeeds only when standard meets the derived minimum;
    unsafe tier/executor downgrades are refused with observable reasons.
47. A compatible batch records ordered members and outcomes, runs as one
    sequential composite unit, and a partial batch unlocks nothing by default.
48. Resume uses the persisted assignment; only a versioned invalidation may
    reclassify an affected incomplete node, never a completed one.
49. One persisted escalation records its evidence; an identical retry without
    changed context or scope cannot escalate again.
50. Context selection keeps applicable verified/promoted records in deterministic
    order, blocks unresolved stale bindings, and excludes stale advisory records.
51. Old manifests resolve to standard implementer/single/off defaults, while
    simple graph-free work stays graph-free.
52. `dispatch=single` accepts only persisted `implementer`/`standard`
    implementation assignments and blocks/rejects an implementation mismatch
    without silently rerouting a running node; required independent review/final
    nodes retain `reviewer`/`high`. The active Change 2 graph does not use auto
    routing, batching, or an alternate implementation executor.
53. No dispatch-compatible scenario creates operational parallel work,
    collision scheduling, semantic merging, or a live scheduler.
54. Independent reviewer/final readiness remains at least standard and high for
    high-risk work, regardless of the implementation tier.
55. Assignment previews and override refusals expose logical values and concise
    observable reasons, never hidden reasoning.
56. Documentation makes no token, cache, cost, latency, or savings claim without
    measured auditable evidence.
57. The README links to the standalone task-workflow roadmap without duplicating
    it in the product roadmap.

## Sequential compatibility scenarios

58. Two ready independent nodes select only the first sequential node. This is
    observed contract evidence, not a fabricated failed executable test.
59. The active Change 3 implementation manifest records `execution=sequential`,
    `dispatch=auto`, `batching=auto`, `parallelism=off`, and
    `max_parallel_agents=1`. It never treats archived design as permission for
    concurrent edits to its own branch.
60. A version-1 manifest with no parallel fields resolves to `parallelism=off`
    and `max_parallel_agents=1`; merely reading it does not create new fields.
61. A request that explicitly requires any parallel execution blocks as an
    unsupported capability. Optional wording may continue sequentially only
    after disclosing the limitation.

95. A generic final-readiness subagent says `approve`, but its artifact lacks the
    configured reviewer provenance: the analysis is advisory and final remains
    `not-ready` until the controller persists valid returned evidence from the
    configured reviewer.
96. A workflow safety claim appears only in prose, or lacks matching
    schema, lifecycle, resume, example, or scenario evidence: its Invariant
    evidence matrix row yields `do-not-approve`, not an inferred pass.
97. A required Invariant evidence matrix row is marked `N/A` without an explicit
    reason: the unexplained `N/A` is incomplete evidence and blocks approval.
98. A fix changes a traced workflow safety claim after the controller persists a
    passing reviewer matrix row: that row is stale, so final remains `not-ready`
    until the controller persists fresh configured-reviewer validation for the
    changed claim.
99. The root `AGENTS.md` and task-workflow references agree that durable
    execution is sequential and operational wave input fails closed.
100. Two independent nodes are ready: `parallelism=off` and
     `max_parallel_agents=1` select one deterministic node. Permissive parallel
     wording does not change those values and is disclosed before continuing.
101. A controller or generic subagent copies reviewer fields without a matching
     pre-dispatch configured-reviewer invocation: it is advisory and blocks.
102. Neither supported reviewer dispatch mode is available: graph-free and
     durable review/final block; completed implementation nodes without
     review/final gates remain incomplete.
103. Workers never write `metrics.md`; the controller aggregates each stable
     terminal ID once. Resume never double-counts an existing ID.
104. Without persisted `workflow_metrics=final`, metrics stay disabled. A logical
     tier never implies a runtime model; unavailable usage is never estimated.
105. An explicit graph-free `mode=review` or `mode=final` request creates its
     pre-dispatch canonical invocation record and routes only to
     `.codex/agents/kapisch-reviewer.toml` through one supported dispatch mode;
     unavailable modes return blocked, `do-not-approve`, or `not-ready`, never
     controller self-review.
106. A non-trivial graph-free implementation completes: a controller or generic
     subagent cannot approve it; a fresh configured review and a separate fresh
     configured final invocation are required.
107. Durable implementation nodes complete, but required review/final nodes are
     absent: the graph is incomplete and blocks for a non-cyclic amendment with
     fresh reviewer invocations.
108. A reviewer invocation is `dispatched` when the session stops: resume
     preserves it as unresolved, does not guess its result or dispatch a second
     reviewer, and chooses the same blocking action on repeated resume.
109. A review artifact has copied reviewer provenance but no matching canonical
     invocation file: it is advisory only and cannot approve.
110. A graph-free behavioural task is inspected by read-only advisory
     subagents, but no canonical reviewer invocation or result artifacts exist.
     The controller reports the analysis as advisory and does not claim approval,
     successful task-workflow review, or readiness. It must not infer that
     graph-free task mode, `handoff=chat`, or read-only execution waives review
     artifact requirements.
111. A session loads task-workflow instructions, then the repository is checked
     out, reset, rebased, merged, branch-switched, or worktree-changed. Before
     any later classification, dispatch, review/final decision, or completion
     report, the controller rereads the current repository skill and applicable
     normative references. It does not rely on the pre-change cached contract.
112. A completed review invocation is offered as final evidence: final is
     `not-ready` because `reviews/final/00-final-invocation.toml` must be a distinct
     fresh invocation.
113. An authorized fix changes the revision or working-tree state: prior review
     evidence is stale and a new review node/invocation is required before final.
114. Metrics contain a reviewer-shaped entry without a completed matching
     invocation record: metrics remain non-authoritative and no approval occurs.
115. A terminal final-readiness attempt returns `not-ready`, `blocked`, or
     `failed`: when terminal evidence exists, the controller emits the requested
     final-only aggregate exactly once without adding provenance or estimates.
116. A controller records `.codex/agents/kapisch-reviewer.toml` as requested but receives
     generic-agent output without matching runtime-spawn or external-task
     evidence: the invocation remains `blocked` or `failed`; it cannot approve.
117. A same-task `@Reviewer` mention or a link resolving to the controller task
     is not external reviewer provenance and blocks rather than completing review.
118. When runtime task ID and URL are both unavailable, the controller persists
     `external_task_ref: ext-final-72956c-01` before a separately created,
     user-attested Reviewer task starts. Its populated `external_task_request`
     and digest-bound result each contain the exact logical line
     `external_task_ref=ext-final-72956c-01` once; `external_task_id` and
     `external_task_url` are `unavailable`; and
     `identity_assurance` is `user-attested-external-reference`. With matching
     result/checklist/digest and unchanged repository state, it completes an
     `external-named-task` review. The reference is not runtime-provided identity.
119. A distinct generic external task or an external task without Reviewer UI
     attestation remains advisory and cannot approve.
120. Resume accepts a completed valid `external-named-task` with its matching
     request/result `external_task_ref=<ref>` lines idempotently, but an external
     task without a terminal result remains unresolved and is not redispatched or
     double-counted.
121. A missing, changed, substring-only, duplicated, or reused canonical
     `external_task_ref=<ref>` line blocks approval. A completed external review
     cannot satisfy final: final requires a distinct, fresh external Reviewer task
     or fresh runtime named spawn.
122. A reviewer changes tracked, staged, unstaged, or relevant untracked state:
     post-review Git-state comparison invalidates approval.
123. A reviewer is restricted to read-only context and returns a complete report:
     the controller persists its exact result envelope, invocation/assignment
     evidence, and digest; the reviewer never needs workspace write access.
124. A reviewer role requests read-only but the runtime does not expose effective
     child sandbox metadata: the controller records Level 2 as unavailable and
     relies on valid mode-specific Level 1 evidence plus unchanged repository
     state, never a false sandbox claim.
125. An architect returns a plan and an implementer returns changed-file and
     verification evidence: the controller writes their handoffs. Implementer,
     implementer-lite, and mechanic may write only approved task scope; none may
     write shared graph, state, metrics, or reviewer invocation records.
126. A named reviewer spawn succeeds but runtime assignment/sandbox metadata is
     unavailable: the controller records `runtime_assignment_receipt: unavailable`,
     `effective_sandbox_receipt: unavailable`, and
     `identity_assurance: observable-named-dispatch`; it does not fabricate Level 2.
127. The controller stores a reviewer result: its envelope contains the stable
     invocation ID, dispatch mode and matching mode-specific evidence, pre/post Git-state digests,
     canonical UTF-8 bytes or reference, SHA-256 digest, and returned reviewer
     fields. A rewritten field, noncanonical encoding, missing Level 1 evidence,
     changed repository state, or digest mismatch blocks review/final and resume.
128. A review node claims approval while omitting one contributing
     implementation node from its sorted `review_scope`: graph validation and
     resume block it. Its `depends_on` must exactly enumerate scoped terminal
     nodes, while final depends on the current approving review.
132. A runtime-named-spawn omits `fork_turns="none"` and defaults to full history:
     the named-dispatch request is invalid and the invocation blocks.
133. `handoff=chat` is requested for review or final: canonical invocation and
     result artifacts remain mandatory for approval; without them the output is
     explicitly advisory.
134. Final artifacts are written only as `reviews/final/00-final-invocation.toml`
     and `reviews/final/05-final.md`; no task-root final artifact substitutes.
135. Resume sees valid Level 1 evidence with unavailable Level 2 fields: it does
     not redispatch, double-count metrics, or invent runtime metadata.
136. A runtime later exposes resolved role or effective sandbox metadata: the
     controller records it as Level 2 without changing the valid Level 1 path.

## Stabilization S3 consolidation and recovery scenarios

137. A manifest sets `policies.parallelism` to anything except `off`, sets
     `policies.max_parallel_agents` to anything except `1`, or contains a root
     `waves` key: schema validation fails closed before the next-action table
     runs. Root `waves` remains unsupported when empty or when all records are
     completed, cancelled, or otherwise terminal; validation does not mutate
     state, dispatch, cancel, integrate, or invent a wave next-action token.
138. Two ordinary nodes are `running`, `implemented`, or `reviewing`: the sole
     sequential table yields `block:active-node-conflict` and selects nothing.
139. Exactly one node is active while another is ready: the table yields
     `resolve:<active-id>` and does not consider the ready node until the active
     node reaches a lawful non-active state.
140. No node is active and a pending node has only complete dependencies: the
     controller may persist its separate `pending -> ready` lifecycle transition
     and then calculate again. The validator never performs that promotion; an
     unknown or incomplete dependency never promotes.
141. Several dependency-valid nodes are ready: selection uses minimum
     `(sequence, id)`. `sequence` is the persisted approved-plan order, so no
     conversation, filesystem, completion-time, or second plan-order value may
     override it.
142. Implementation nodes are terminal but no current completed final depends
     on a preceding completed approving review with valid evidence: the result
     is `block:missing-review-final`, never `complete`.
143. A prior review failed, a completed fix is followed by a fresh completed
     approving review and final, and all other nodes are complete or cancelled:
     the historical failed review is terminal and the workflow may complete. A
     failed or blocked behavioral/fix node, even outside the current gate chain,
     instead prevents completion and yields `block:no-ready-node` when no earlier
     row applies.
144. A valid completed review/final gate exists, but the persisted graph has a
     nonterminal node that is neither active nor already ready: without a prior
     controller promotion, the executable calculation reaches
     `block:no-ready-node`.
145. Explicit `cancel-remaining` transitions only pending/ready nodes to
     `cancelled`; any active node is lawfully resolved first. The controller
     persists those transitions and recomputes because cancellation has no
     separate next-action token.
146. Persisted recovery input may be syntactically accepted with compatibility
     `resume:<id>`, but semantic validation still compares it to the calculated
     result. The calculation emits `resolve:<id>` for one active node and never
     emits `resume:<id>`.
147. Only one of `02-execution-graph.toml` or `03-state.toml` survives: existing
     execution blocks and neither file, Git, reports, nor conversation is used to
     reconstruct the missing authoritative artifact.
148. Both authoritative TOML files are absent: there is no durable execution to
     resume. Continuing implementation requires a newly approved plan and fresh
     workflow rather than inferred history.
149. With either partial or wholly missing durable state, a separate graph-free
     review of the current revision may start with a fresh invocation. It
     inherits no approval, fix count, metrics, provenance, completion status, or
     recovery claim from the lost execution.
150. A version-1 compatibility manifest has no nodes: it retains its legacy
     `complete` result. Any non-empty implementation graph still requires the
     current review/final gate chain.
151. A canonical invocation omits `dispatching_controller`, uses
     `assurance_level`, or adds another top-level alias: the closed envelope
     fails before it can approve or satisfy resume.
152. A runtime named reviewer task or returned task name equals the dispatching
     controller, or uses anything except `observable-named-dispatch`: provenance
     fails closed. External task names and every populated ID, URL, or reference
     are likewise distinct from the controller.
153. A completed review returns `changes-requested`, a final returns `approve`,
     or either uses `not ready`: mode-specific decision validation rejects the
     obsolete or cross-mode spelling. Only review `approve` and final `ready`
     complete their graph nodes.
154. Result bytes are valid UTF-8 but differ by one byte from their persisted
     lowercase SHA-256, or omit the invocation ID: the invocation is invalid;
     normalizing or rewriting returned bytes is forbidden.
155. A pre/post staged Git-state payload has reordered fields, a non-empty
     relevant-untracked set, a component digest of the wrong shape, or a digest
     that does not hash the exact payload: the invocation fails closed.
156. The same tracked path is staged first with bytes A and then with bytes B.
     Porcelain status and path remain identical, but index, staged-diff, and
     composite state digests change; snapshot A cannot approve snapshot B.
157. A completed negative Round 0 invocation maps to a failed historical review
     node and never establishes the approving-review pointer. A fresh review and
     separate fresh final remain mandatory after the bounded fix.
158. A syntactically readable schema-old failed review reserves its valid
     invocation ID and populated external task reference before the narrow
     non-approval compatibility skip. Reuse by a fresh invocation blocks in
     either manifest order; unreadable history or history without a valid
     reservable invocation ID is not silently skipped.
159. A current external task URL reuses a historical external task ID, or two
     envelopes reuse one ID/URL/reference value in either node order: the shared
     external-identity namespace rejects it before compatibility skipping.
160. Two review/final nodes declare the same report path through identical or
     aliased spellings, or an envelope points elsewhere: result-path binding
     fails closed before either artifact can approve.
161. A runtime spawn is only planned: its returned task name is `unavailable`.
     Once dispatched, completed, blocked, or failed, only its requested task name
     or documented `unavailable` is valid; external dispatch always uses
     `unavailable`.
162. Digest-bound result bytes omit, change, embed as a substring, or duplicate
     `invocation_id=<id>`: provenance fails. Exactly one case-sensitive LF or
     CRLF logical line is accepted.

## Change 7 ecosystem-routing scenarios

Positive scenarios:

163. A graph-free explicit instruction-only skill: the user names the skill,
     `ecosystem=auto` is active, and the controller records
     `selection_mode=explicit` plus the route/context/evidence under
     `delegations/`. The workflow stays graph-free
     (`parent_node_id=unavailable`) and the verified result feeds the existing
     role and workflow.
164. A graph-free automatically selected read-only plugin skill: the controller
     considers only visibly available capabilities, selects the smallest
     capability that covers the bounded substep, and records the observable
     selection reason; it never claims the visible set is exhaustive and never
     selects from name similarity alone.
165. A version-3 durable implementation node with one completed delegation: the
     node's `delegation_ids` resolves against `delegations/00-route.toml`, the
     step's `parent_node_id` matches the owning node, and the node completes
     only with the step `completed` and evidence digest-valid.
166. Multiple sequential delegations with distinct authority classes: GitHub
     diagnosis (`external-read`, `request-scoped`), local repair
     (`repository-write`, `request-scoped`), and posting a PR comment
     (`external-write`, `explicit-step`) are three sequential records split at
     the authority boundary, never one opaque operation.
167. An external read followed by an explicitly approved external write: the
     controller prepares and previews, stops at the gate, receives exact
     explicit authority for target and payload, executes the write, and
     persists the external result.
168. A review node consumes read-only advisory specialist evidence: the
     referenced delegation is `repository-read` or `external-read`, the node's
     decision remains bound to its canonical reviewer invocation, and the
     specialist output never approves.
169. A valid completed delegation is accepted idempotently on resume: repeated
     resume against unchanged evidence returns the same next action and creates
     no duplicate tool call or external effect.
170. Existing version-1 and version-2 fixtures remain unchanged and valid:
     reading an old manifest never creates a route record or delegation fields,
     and version-3-only fields are rejected by older versions.

Negative scenarios:

171. An explicitly required capability is unavailable: the controller blocks and
     reports the missing capability and a safe setup or selection action; it
     never silently substitutes another capability.
172. An unknown route field, capability kind, effect class, authority mode, or
     lifecycle value appears: the closed route schema fails closed.
173. Two steps share a delegation ID or sequence value: duplicate IDs and
     duplicate sequence values fail closed.
174. A route contains path traversal, a symlinked evidence file, missing
     context/evidence, invalid UTF-8, or a digest mismatch: structural
     validation fails closed.
175. A completed step records `resolved_capability=unavailable`: the step is
     invalid because a resolved capability and complete evidence are required.
     (The step lifecycle model is deferred; the capability and evidence rules
     still apply.)
176. An external write or destructive action lacks `authority_mode=explicit-step`
     and a valid in-context authority reference: it is blocked; preparation and
     preview may proceed separately, execution may not.
177. Step lifecycle validation (ordered sequential lifecycle with at most one
     `started` step, step-state/node consistency) is deferred to a later
     change; the graph node lifecycle rules apply unchanged.
178. A graph references a step whose `parent_node_id` mismatches, reuses a step
     ID across nodes, or depends on an orphaned required reference: graph
     validation blocks it.
179. A review/final delegation attempts a write or destructive effect: blocked;
     review/final nodes reference only read-only advisory steps.
180. A delegated capability tries to delegate the KAPISCH route or invoke
     `$kapisch`: refused as recursive route ownership; the need is recorded as a
     new sibling step with its own context, authority, lifecycle, and evidence.
181. An unavailable capability would be installed, enabled, signed in to, or
     reconfigured: never. The controller discloses native fallback only when
     the approved outcome remains achievable without changing methodology, data
     boundary, or authority; otherwise it blocks.
182. An interrupted external-write step is blindly repeated on resume: never.
     Resume reconciles read-only against the external system when already
     authorized and possible, otherwise blocks for user direction.
183. A requested plugin name or controller prose is treated as runtime proof of
     selection: unexposed runtime receipts are recorded as `unavailable`, never
     inferred from installed filenames, requested names, prompts, or output
     wording.
184. Specialist review output is treated as approving review/final evidence:
     it remains advisory until the canonical reviewer invocation produces
     approving evidence.
185. A capability expands files, behavior, data boundary, or external action
     beyond the approved context: treated as material scope expansion and
     blocked for a user decision; the capability never renormalizes the
     top-level request or takes ownership of later gates.
