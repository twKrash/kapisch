# Durable-execution resume and reconciliation

This reference is the normative owner of durable recovery, reconciliation,
idempotent resume, and missing-artifact behavior. The manifest/state schema and
next-action table are owned by [execution-graph.md](execution-graph.md); artifact
paths and invocation envelope fields are owned by [handoffs.md](handoffs.md).

For an initial `execution_action=start`, first validate one unambiguous approved
plan. If no execution manifest/state exists, initialize them as described in
[execution graph](execution-graph.md) before selecting or dispatching a node.
Missing, ambiguous, or unapproved plans block or ask one focused question; they
do not create a graph.

For `resume`, both `02-execution-graph.toml` and `03-state.toml` must already
exist. If either file is missing, the existing execution cannot resume and the
controller must not reconstruct, infer, or partially regenerate it from task
reports, conversation history, Git state, or the surviving file. If both are
absent, there is no durable execution to resume. Continuing implementation then
requires a newly approved plan and a fresh workflow (graph-free when the task is
simple, or a new durable start when activation conditions apply).

Missing durable state does not prohibit a separate fresh graph-free review of
the current repository revision. Such a review must establish its own
revision-bound invocation and evidence and inherits no approval, fix-round
count, metrics, reviewer provenance, completion status, or recovery claim from
the missing execution.

For resume or recovery, locate the active task ID; read `03-state.toml` and
`02-execution-graph.toml`; inspect Git status and current revision; compare it
with each recorded node revision; validate completed-node evidence; and count
active `running`, `implemented`, and `reviewing` nodes. More than one active node
is an unrecoverable conflict: record it and block. With one active node, read
only its brief, context, and report, then resolve it through a permitted
lifecycle transition before considering ready nodes. Only when no active node
remains may the controller select the first valid ready node. Record the
observed revision and every reconciliation result in state/report artifacts.

Durable artifacts win over conversation context. Git and repository evidence win
over durable artifacts. On disagreement, record the mismatch and recover only
when the next action is deterministic; otherwise mark the workflow blocked. Do
not guess, silently repair history, or mark a node complete from a report alone.

For an interrupted running node, inspect its report, expected write scope,
current diff, verification evidence, and recorded revision. Resume only if that
evidence determines the next action; otherwise block. Repeating resume without
repository changes must choose the same next action and must not redispatch a
completed verified node.

For a dispatch-compatible node, also load its persisted logical assignment,
reason codes, source/attempt revisions, context/scope references or
fingerprints, escalation history, batch membership/outcomes, and exact
verification evidence. Resume uses that assignment idempotently. Reclassify only
when an explicit, versioned plan or repository invalidation names the affected
node and records the reason, evidence, and replacement assignment; never
reclassify a completed node or silently reassign a running node. Missing or
conflicting assignment evidence blocks.

Batch recovery remains sequential. Preserve every member ID and outcome; a
partial batch retains completed-member evidence but unlocks no downstream node
unless explicit member-level dependencies authorize it. Old manifests without
dispatch fields resolve to their documented Change 1 defaults, and simple
graph-free workflows remain graph-free.

## Reviewer invocation recovery

Before trusting review or final evidence, validate the complete canonical
invocation envelope owned by [handoffs.md](handoffs.md), recompute its result
digest, and confirm its mode-specific Level 1 provenance, target binding,
terminal result, and unchanged repository state. Explicitly unavailable Level 2
receipts are acceptable; inferred receipts are not. Graph-free and durable
recovery use the same rule and fail closed on any missing, stale, changed,
duplicated, reused, generic, or mode-mismatched evidence.
The expected result path must remain bound to the graph node report, completed
produced bytes must use that same unique resolved path, and the digest-bound
result must contain exactly one `invocation_id=<id>` LF/CRLF logical line.

`planned` without dispatch remains deterministic pending work; it may be
dispatched once through an available approved mode. `dispatched` without a
terminal matching artifact is unresolved and blocks rather than guessing or
duplicating dispatch. `completed` is reusable only when its matching artifact,
mode-specific Level 1 and non-mutation evidence, report digest, revision, and
state remain current; unavailable Level 2 fields do not require redispatch. A
completed valid external task or matching compatibility reference is therefore
accepted idempotently. Repeated resume then records no new invocation or metrics
entry. `blocked` and `failed` remain blocked until an
explicit new invocation is authorized. A missing record, copied provenance,
reused review invocation for final, stale evidence after a fix/revision change,
duplicate terminal processing, controller-edited/missing envelope, or
unknown/conflicting Level 1 fields blocks. A graph
whose implementation nodes look complete but lacks required review/final gates
remains incomplete and blocks for graph amendment and fresh configured-reviewer
invocations. Never infer reviewer success from metrics, a role label, or a
generic subagent artifact.

Before consuming a terminal envelope that uses the legacy reviewer-profile path,
the controller must establish its supported, human-approved migration origin
from `.planning/task-workflow/<task-id>/`. Structural validator acceptance is
not migration provenance. If that origin is unavailable, resume blocks legacy
reuse and requires a fresh invocation with the canonical reviewer profile.

For every syntactically readable current or historical invocation, reserve its
valid non-`unavailable` invocation ID and every populated external task ID, URL,
or reference before considering the narrow schema-old failed-history skip.
Invocation IDs use their own namespace; external identities share one namespace,
so cross-field duplicates block in either manifest order. The skip requires a valid reservable
invocation ID and only missing/unknown top-level schema findings; unreadable or
otherwise malformed history is not inferred or skipped.

## Unsupported operational wave input

A manifest containing a root `waves` key, a `parallelism` value other than
`off`, a `max_parallel_agents` value other than `1`, or non-empty legacy
wave review-scope fields cannot resume. Fail closed before reconciliation: do
not mutate state, dispatch agents, recreate workspaces, apply or integrate
packages, cancel work, or infer a sequential recovery. Repeating resume without
repository changes returns the same unsupported-capability result.

The retired recovery protocol is preserved only as non-normative future design
material in
[`../../../docs/parallel-wave-design.md`](../../../docs/parallel-wave-design.md).
