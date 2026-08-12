# Durable execution

This reference is the normative owner of the durable manifest/state schema and
the deterministic sequential controller transition table. Artifact placement
and invocation envelopes are owned by [handoffs.md](handoffs.md); recovery and
Git reconciliation are owned by [resume.md](resume.md). The validator mirrors
these contracts executablely but does not define additional policy.

Durable execution is optional. Activate it only when the user requests
end-to-end execution or resume, a plan has multiple independently reviewable
tasks, a task spans sessions, recovery is requested, or a roadmap milestone is
being executed. Simple isolated work keeps the existing graph-free flow.

## Supported execution surface

The current controller supports graph-free workflows and durable sequential
execution only. Every new durable manifest uses `parallelism: off` and
`max_parallel_agents: 1`, and the controller dispatches at most one
implementation executor at a time. It must not create, dispatch, resume,
cancel, integrate, or complete a wave. Manifest validation fails closed when
`policies.parallelism` is not `off`, `policies.max_parallel_agents` is not `1`,
or the root manifest contains a `waves` key or collection. Any root `waves`
collection is unsupported regardless of emptiness, member status, or whether it
contains only completed, cancelled, or otherwise terminal records. No automatic
wave recovery or sequential integration is permitted.

The retired parallel-wave protocol is preserved only as non-normative future
design material in
[`../../../docs/parallel-wave-design.md`](../../../docs/parallel-wave-design.md).

## Manifest and state

Create a versioned, readable manifest at
`.kapisch/runs/<task_id>/02-execution-graph.toml` and update
`03-state.toml` after every meaningful transition. Durable artifacts and Git
evidence are authoritative; conversation context is not. After the controller
receives verified evidence of one unambiguous approved plan, it initializes the
manifest from its stable task ID, approved plan path/roadmap reference, current
base revision, approved policies, and the plan's independently reviewable nodes.
It writes the initial state before dispatching a node. Missing approval,
ambiguity, or a plan that cannot be split without new design work blocks rather
than creating a graph.

`02-execution-graph.toml` and `03-state.toml` are authoritative for durable
graph state. `03-state.md`, when present, is an optional non-authoritative view.
Review/final and other referenced artifact locations are defined only in
[handoffs.md](handoffs.md).

```toml
version = 3
task_id = "example"
source_plan = "01-plan.md"
base_revision = "abc1234"

[policies]
execution = "sequential"
executor = "implementer"
dispatch = "auto"
model_tier = "standard"
batching = "auto"
parallelism = "off"
max_parallel_agents = 1
commit = "manual"
push = "manual"
fix_policy = "manual"
max_fix_rounds = 1
ecosystem_routing = "auto"

[[nodes]]
id = "T01"
sequence = 1
title = "Example deliverable"
kind = "behavioral"
risk = "high"
status = "pending"
depends_on = []
brief = "tasks/T01-brief.md"
context = "tasks/T01-context.md"
report = "tasks/T01-report.md"
reads = []
writes = []
shared_resources = []
verification = []
context_refs = []
executor_class = "implementer"
model_tier = "standard"
batching = "off"
verification_evidence = []
delegation_ids = []

[nodes.assignment]
id = "A-T01-1"
schema_version = 1
execution_class = "bounded"
reason_codes = []
source_revision = "abc1234"
context_refs = []
escalations = []

[[nodes.assignment.attempts]]
id = "AT-T01-1"
source_revision = "abc1234"
context_scope_ref = "A-T01-1"
status = "pending"
verification = []

[[nodes]]
id = "R01"
sequence = 2
title = "Integrated independent review"
kind = "review"
risk = "high"
status = "pending"
depends_on = ["T01"]
brief = "tasks/R01-brief.md"
context = "tasks/R01-context.md"
report = "reviews/round-0/03-review.md"
reviewer_invocation = "reviews/round-0/00-review-invocation.toml"
reads = []
writes = []
shared_resources = []
verification = ["independent-two-pass-review"]
context_refs = []
executor_class = "reviewer"
model_tier = "high"
batching = "off"
verification_evidence = []
delegation_ids = []

[nodes.review_scope]
terminal_node_ids = ["T01"]

[[nodes]]
id = "F01"
sequence = 3
title = "Final readiness"
kind = "final"
risk = "high"
status = "pending"
depends_on = ["R01"]
brief = "tasks/F01-brief.md"
context = "tasks/F01-context.md"
report = "reviews/final/05-final.md"
reviewer_invocation = "reviews/final/00-final-invocation.toml"
reads = []
writes = []
shared_resources = []
verification = ["revision-bound-final-readiness"]
context_refs = []
executor_class = "reviewer"
model_tier = "high"
batching = "off"
verification_evidence = []
delegation_ids = []
```

This version-3 template is for a newly initialized general graph. Its `auto`
policy values do not override a task's persisted policies. In particular, the
active Change 2 graph remains scoped to its recorded `dispatch=single` and
`batching=off` bootstrap, while the active Change 3 graph records
`execution=sequential`, `dispatch=auto`, `batching=auto`, `parallelism=off`, and
`max_parallel_agents=1`. A version-2 resume uses those exact recorded values; it
never applies Change 1 compatibility defaults or another task's bootstrap policy.
Version-2 manifests remain readable as compatibility input only (see
"Version-3 delegated-step references" below); newly initialized graphs are
version 3 and always record `ecosystem_routing` and `delegation_ids = []` on
every node.

### Closed persisted vocabularies

The validator and controller accept only the following durable string values.
They reject unknown values without case folding, aliases, or typo normalization.

| Persisted field | Accepted values |
| --- | --- |
| `policies.execution` | `sequential` |
| `policies.executor` | `implementer` |
| `policies.dispatch` | `auto`, `single` |
| `policies.model_tier` | `cheap`, `standard`, `high` |
| `policies.batching` | `auto`, `off` |
| `policies.parallelism` | `off` |
| `policies.commit` | `manual` |
| `policies.push` | `manual` |
| `policies.fix_policy` | `manual`, `blocking` |
| `policies.ecosystem_routing` | `auto`, `off` |
| `nodes[].executor_class` | `mechanic`, `implementer-lite`, `implementer`, `architect`, `researcher`, `reviewer` |
| `nodes[].model_tier` | `cheap`, `standard`, `high` |
| `nodes[].batching` | `auto`, `off` |
| `nodes[].assignment.execution_class` | `mechanical`, `prescriptive`, `bounded`, `design` |
| `workflow_status` | `running`, `complete` |

`max_parallel_agents` remains the integer sentinel `1`, and `max_fix_rounds`
remains a non-negative integer. `ecosystem_routing` remains version-3-only;
version-1 and version-2 manifests reject the field even when its scalar appears
in the table above. Version-1 omitted defaults are validated against the same
vocabulary after they are filled.

A persisted `workflow_status` is `complete` if and only if `next_action` is
`complete`. Every select, resolve, resume, or `block:*` action uses
`workflow_status = "running"`; a blocker does not invent another workflow
status. Across observed snapshots, the only legal workflow-status transitions
are `running -> running`, `running -> complete`, and `complete -> complete`.

### Previous-snapshot compatibility

When a previous persisted snapshot is supplied, compatibility validation runs
before lifecycle transition validation. Manifest `version`, `task_id`,
`source_plan`, `base_revision`, and normalized `policies` are immutable. Every
previously persisted node ID must remain present. For an existing node, `id`,
`sequence`, `title`, `kind`, `risk`, `depends_on`, `brief`, `context`, `report`,
`reviewer_invocation`, `reads`, `writes`, `shared_resources`, `verification`,
`context_refs`, `executor_class`, `model_tier`, `batching`, `review_scope`,
`delegation_ids`, and `extensions` are immutable. Dependency order is not
semantic, but adding, removing, or replacing a dependency is incompatible.

While an existing node is non-terminal, only its legal lifecycle `status` and
its runtime `revision`, `assignment`, `batch`, `verification_evidence`, and
`blocker` records may advance. A persisted assignment keeps its ID and stable
fields; attempts may advance their `status` and verification, while attempts,
escalations, and verification evidence retain every existing stable ID and may
only gain new records. After the node reaches `complete`, `blocked`,
`failed`, or `cancelled`, those runtime bindings are frozen too; they cannot be
removed, detached, replaced, or rebound. Once the workflow is `complete`, its
`current_revision`, latest approving review path and invocation ID, and fix-round
bounds are likewise frozen.

Graph growth is incompatible with an existing persisted snapshot. The current
schema has no graph-amendment protocol, so a new node, delegation step, or
artifact binding blocks resume rather than claiming append-only history.
Dynamic replanning requires a separate, versioned, evidence-bearing amendment
design that also establishes fresh review/final coverage; it must not be
inferred by weakening resume compatibility.

Each node has a stable ID; changing a title does not change identity. Its
non-negative integer `sequence` is the persisted approved-plan order; there is
no separate implicit plan-order input. Nodes also
record expected read/write scope, verification commands and expected results,
knowledge references, resulting revision/diff range, and a blocking or failure
reason when relevant. `03-state.toml` names the source plan, base/current
revision, workflow status, completed/running/ready/blocked/failed nodes, latest
approving review, fix-round count, next action, and files required to recover.

Before selecting a node, the controller creates its named brief, context, and
report. Every new durable graph must include at least one integrated
`kind: review` node and one subsequent `kind: final` node. Every review node has
a `review_scope` with a stable, sorted `terminal_node_ids` list, and its
`depends_on` must enumerate that exact set. Empty legacy
`integrated_wave_ids` and `wave_terminal_dependencies` fields remain readable;
new graphs omit them, and any non-empty value fails closed. Final depends on the
current approving review. A fix inserts an authorized implementation/fix node
after review, then a fresh review node before final; it must not back-edge to or
reuse the earlier approval. Review/final nodes have `executor_class: reviewer`,
`model_tier: high`, `batching: off`, and a named canonical invocation path.
They never enter a batch. A graph is incomplete until final is complete with
valid fresh reviewer evidence, even if all implementation nodes are complete.
Before a node advances or review/final returns, persist the required evidence
artifact and update graph/state references. Missing named durable evidence
blocks the transition; conversation results cannot fill it.

## Version-3 delegated-step references

Newly created durable graphs are version 3 after Change 7 lands. Version-1 and
version-2 parsing, defaults, fixtures, and migration behavior are preserved
without rewriting: a version-1 or version-2 manifest must reject
version-3-only fields rather than silently adopting new behavior, and reading an
old manifest must never create a route record or delegation fields.

A version-3 manifest adds:

- required policy `ecosystem_routing = "auto|off"`;
- `delegation_ids = []` on each node.

Each referenced ID resolves against `.kapisch/runs/<task_id>/delegations/00-route.toml`.
Every referenced step's `parent_node_id` must match the owning graph node, and
one step may be referenced by only one node. Every shipped route step must be
referenced by exactly one owning node. Review/final nodes may reference only
`repository-read` or `external-read` advisory steps, and a review/final node's
decision remains bound to its existing canonical reviewer invocation and result
artifact, never to delegated output. Delegated-step lifecycle/status gating is
deferred and does not alter graph-node transitions.

Version 3 changes no node-status transitions, deterministic node selection,
parallelism sentinels, assignment semantics, batches, or logical model tiers.
Graph-free delegation is deferred to a later change. The current version-3
delegation route is for durable graphs only, and every shipped delegated step
must name its owning graph node. The delegation record schema is owned by
[ecosystem-routing.md](ecosystem-routing.md).

## Dispatch-compatible graph fields

`dispatch`, `model_tier`, and `batching` are optional policy fields;
`executor_class`, `model_tier`, `batching`, `assignment`, `batch`, and
`verification_evidence` are optional node fields. They contain logical values
and durable evidence only; they never store a model identifier or hidden
reasoning.

An `assignment` has a stable `id`, schema version, execution class, concise
observable reason codes, source revision, and a `context_scope` with selected
context references plus context and scope fingerprints when available. Its
`attempts` use stable IDs and preserve their source revision, context/scope
reference, status, and exact verification evidence/results. Its `escalations`
use stable IDs and preserve the trigger, prior/new assignment and attempt IDs,
source/attempt revisions, and context/scope evidence.

An optional `batch` has a stable ID, ordered member IDs, member assignment IDs,
member outcomes, and composite outcome. `verification_evidence` and each
attempt/batch verification record use stable IDs and preserve the exact command
or check, result, evidence reference or output digest, and recorded revision.
Successful member evidence survives a partial batch, but does not unlock a
downstream node unless explicit member-level dependencies permit it.

Write or update assignment, attempt, escalation, batch, and verification
records before the lifecycle transition they justify. During resume, compare
their stable IDs, source/attempt revisions, context/scope evidence, batch
membership/results, and verification evidence with repository evidence before
choosing a permitted transition. Missing or conflicting evidence blocks rather
than infers an assignment, result, or escalation.

`dispatch=auto|single` and `batching=auto|off` are policy values; `single` is
the compatibility-safe implementation path using the standard `implementer`.
It blocks or rejects an implementation assignment unless it is exactly
`executor_class=implementer` and `model_tier=standard`; a running implementation
node is never silently rerouted to satisfy `single`. `kind: review` and
`kind: final` nodes retain their required independent `reviewer`/`high`
assignment under either policy and remain ineligible for batches.
Persist an approved assignment before dispatch. A completed node is never
reclassified. A running node retains its assignment unless a plan or repository
invalidation is explicitly recorded with a stable invalidation ID, version,
affected-node IDs, reason, evidence, and replacement assignment. Such a record
is the only basis for reclassification and is preserved in history; it does not
silently rewrite prior attempts or escalation evidence. A design assignment
remains blocked pending architect amendment and explicit plan approval.

For a Change 1 manifest that omits these fields, resolve deterministic defaults:
`executor_class=implementer`, `model_tier=standard`, and `batching=off`.
`dispatch` resolves to `single`, and no classification assignment is inferred or
written merely by reading an old graph. Parallel compatibility fields also
resolve to `parallelism=off` and `max_parallel_agents=1`; no unsupported
structure is inferred or written merely by reading an old graph. These defaults
preserve the existing sequential executor contract.

These compatibility defaults apply only to a version-1 manifest that omits the
fields. They do not rewrite a version-2 `auto` policy, and they do not make a
recorded Change 3 sequential bootstrap become Change 2 single-dispatch work.

The controller may optionally render the following non-authoritative human
summary from `03-state.toml`. Resume and validation must ignore this Markdown
file and use TOML state only.
```markdown
# Current Execution State

Task: example
Source plan: `01-plan.md`
Base revision: `abc1234`
Current revision: `def5678`
Workflow status: running

## Completed
- T01 — implementation verification passed
- R01 — independent review approved
## Running
- T02 — Add recovery protocol
## Ready / Blocked
- none / none
## Latest approving review
None.
## Current fix round
0 of 1
## Next action
Read `02-execution-graph.toml`, `tasks/T02-brief.md`,
`tasks/T02-context.md`, and `tasks/T02-report.md`; validate Git and continue.
```

## Deterministic sequential controller transitions

Allowed transitions are `pending -> ready -> running -> implemented -> reviewing
-> complete`; `running` or `reviewing` may become `blocked` or `failed`; a
pending/ready node may be `cancelled` only when remaining execution is cancelled.
No other transition is implied. A completed node never becomes ready/running:
invalid evidence requires an explicit recovery or fix event with its reason.

Before invoking the next-action calculation, schema validation rejects any
manifest whose `policies.parallelism != "off"`, whose
`policies.max_parallel_agents != 1`, or whose root contains `waves`. Root-key
presence alone is unsupported, including an empty collection or only completed,
cancelled, or terminal wave records. That unsupported-capability check is not a
next-action row and does not persist a substitute token.

Pending-to-ready promotion is a separate controller lifecycle transition. With
no active node, the controller may promote dependency-satisfied pending nodes
that meet every other readiness requirement, persist those transitions, and
then calculate from the resulting statuses. The validator does not perform or
infer that promotion. Explicit `cancel-remaining` is likewise a separate
authorized mutation: transition only pending/ready nodes to `cancelled`, resolve
any active node lawfully, persist, and calculate again.

After schema, reference, lifecycle, review/final, and invocation evidence have
been validated, apply the first matching row in this sole deterministic
next-action table:

| Priority | Persisted condition | Calculated result |
| --- | --- | --- |
| 1 | A version-1 compatibility manifest has no nodes | `complete`. This legacy exception does not waive gates for a non-empty graph. |
| 2 | More than one node is active (`running`, `implemented`, or `reviewing`) | `block:active-node-conflict`. |
| 3 | Exactly one node is active | `resolve:<id>`; reconcile that node through one allowed transition before considering ready work. |
| 4 | One or more dependency-valid nodes are already `ready` | `select:<id>` for the minimum `(sequence, id)`. |
| 5 | No node is selectable and no valid completed final gate depends on a preceding completed current approving review | `block:missing-review-final`. Missing, incomplete, stale, or invalid review/final evidence cannot complete the graph. |
| 6 | A valid completed review/final gate exists and every node is terminal for completion | `complete`. `complete` and `cancelled` are terminal for every kind; `blocked` and `failed` count as historical terminal states only for `review` and `final`. |
| 7 | No earlier row applies | `block:no-ready-node`. In particular, a blocked/failed behavioral or fix node prevents completion. |

The accepted persisted-input grammar is `select:<id>`, `resolve:<id>`, the
compatibility form `resume:<id>`, `block:active-node-conflict`,
`block:missing-review-final`, `block:no-ready-node`, or `complete`. This is only
the syntactic acceptance set: validation still compares the persisted value to
the calculated result. The emitted/calculated grammar excludes `resume:<id>`;
the table emits `resolve:<id>` for one active node. Selection is always the
minimum `(sequence, id)` because `sequence` already stores approved plan order;
completion timing, file order, and conversation order are irrelevant.

After `select:<id>`, the controller marks that node running, uses its persisted
assignment or compatibility defaults, and requires its report and verification
evidence before later transitions. Review/final nodes also require their matching
canonical invocation to be current and mapped exactly: completed review
`approve` and completed final `ready` map to node `complete`; completed
`do-not-approve` or `not-ready` maps to node `failed`; invocation `blocked` or
`failed` maps to the same graph status. Only review `approve` may populate the
latest-approving-review pointer. An eligible batch remains one
sequential composite unit. The active Change 2 graph retains its recorded
single/standard/off policy. Stop on any policy blocker, missing authority,
environment-stop condition, or ambiguity rather than inventing a transition.

The template uses `fix_policy: manual`. Set `blocking` only when the source
request explicitly authorizes the existing bounded blocking-fix policy.

## Archived parallel-wave design

The retired S4 protocol is preserved in
[`../../../docs/parallel-wave-design.md`](../../../docs/parallel-wave-design.md).
It is non-normative and cannot authorize operational routing or state changes.

## Node artifacts

`tasks/Tnn-brief.md` is self-contained: ID/title, goal and reason, acceptance
criteria, invariants, exact scope/files/symbols/interfaces, completed
dependencies, required tests/verification, forbidden changes, and report path.
`Tnn-context.md` contains only referenced durable records grouped as binding
decisions/invariants, informational facts, advisory hints, pitfalls, and
approved shortcuts. `Tnn-report.md` records status (`DONE`,
`DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`, or `FAILED`), summary,
files/symbols/behaviour/tests changed, exact commands and results, resulting
revision/diff, deviations, concerns, and candidate knowledge records.

`DONE` proceeds to evidence validation; `DONE_WITH_CONCERNS` pauses for concern
triage before review; `NEEDS_CONTEXT` remains non-complete until focused context
is supplied; `BLOCKED`/`FAILED` cause the controller to update graph/state and
stop dependent dispatch. The implementer returns only status, revision/diff,
one-line verification, and concerns; the controller persists the durable report.
