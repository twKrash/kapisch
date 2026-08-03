# Independent review and final readiness

This reference is the normative owner of review and final evidence semantics,
including the two review passes, evidence checklist and matrix, decisions,
revision freshness, and output shape. [handoffs.md](handoffs.md) separately owns
where that evidence and its invocation envelope are stored.

The reviewer records the exact target, base revision, reviewed head revision,
working-tree state, risk, depth, active lenses, and review scope in the returned
report. Passing tests, an architect plan, implementer summary, or earlier
approval are not proof. Inspect the actual state in fresh context and do not
modify implementation files.

## Review scopes

An **iteration review** is bound to `iteration_base...iteration_head`: one
completed milestone node, bounded implementation task, remediation finding,
approved fix round, or small documentation-contract adjustment. It inspects
only that delta, its acceptance criteria and focused verification, directly
affected callers/contracts/invariants, approved-scope compliance, and obvious
local regressions. It approves only the iteration delta.

An iteration review does not require complete PR-diff review, repository-wide
caller reconstruction, a whole-branch invariant evidence matrix, final-readiness
assessment, or repetition of previously approved unrelated work. Out-of-delta
findings may be observations and must not silently expand scope. If one is
blocking for the iteration's safety, return
`do-not-approve` with blocker `material-scope-expansion` and request a user
decision.

A **whole-branch review** is bound to `merge_base...final_head` and runs after
all approved iterations or at an explicit integration or delivery/final-readiness
boundary. It inspects the accumulated branch using the complete review contract
below and is the only review that can approve the branch for final readiness.
Any implementation change after its approval makes that approval stale.

For an ordinary one-step task, `task_base...task_head` is the entire task diff,
so its task review may be the whole-branch review; do not require two identical
reviews. For milestone work, review each completed node as its own iteration,
then run one integrated whole-branch review. A bounded fix receives an
iteration review of its new base-to-head delta and the original finding; after
all fixes, run or rerun the whole-branch review once.

Within one bounded remediation or milestone session, iteration reviews may reuse
the same independent read-only reviewer thread. Every iteration result still
binds to its exact `iteration_base` and `iteration_head`; approval of one
iteration never approves a later one, and the reviewer must not edit files. A
whole-branch review, including a final whole-branch re-review after fixes, must
use a fresh independent reviewer context. Fresh context is mandatory for
whole-branch review and final readiness, not for every bounded iteration.

## Automatic policy

| Work or boundary | Independent review | Separate final readiness |
| --- | --- | --- |
| Mechanical task, `review=auto` | No | No, unless a delivery boundary applies |
| Mechanical task, `review=always` | Fresh review | Only at a delivery boundary |
| Behavioral task | Fresh review, standard or deep by risk | Only at a delivery boundary |
| High-risk task | Deep review with derived lenses | Only at a delivery boundary |
| Versioned project-understanding or architecture-documentation output | Fresh review of evidence fidelity, scope, clarity, and repository consistency | Only at a delivery boundary |
| Milestone | Integrated deep review | Always |

The versioned project-understanding row takes precedence over a mechanical or
documentation-only classification under `review=auto`. It includes architecture
maps, documentation-drift corrections, onboarding documents, and decision
records. The reviewer approves or rejects the written delta; it does not choose
or approve the underlying architecture or product decision.

Final readiness is required for commit preparation, PR preparation, merge,
release, deployment handoff, and an explicit
ready-to-commit/merge/release/final request. “Review my current branch before I
open a PR” requests review, not final. “Check whether this is ready to open a
PR” requests a separate final readiness decision and requires a current
approving review. Publication and Git side effects still require explicit
authority.

Final is never the first behavioural review. An ordinary reviewed local task may
end after independent review when no delivery boundary applies. High risk alone
does not require final; it strengthens review depth and lenses. `review=always`
also strengthens review and does not create a final boundary.

## Whole-branch review passes

Whole-branch reviews perform both passes:

1. **Independent impact review**: inspect the full diff; inventory changed files
   and symbols; identify entry points; search callers/consumers; identify state,
   side effects, compatibility boundaries, and user-visible outcomes; reconstruct
   behaviour from code/tests; and list plausible failures.
2. **Contract and adversarial review**: compare user request, approved plan,
   acceptance criteria, invariants, and repository policy. For every changed
   behaviour trace `entry point -> validation -> identity and permission checks ->
   state transition -> persistence -> audit or external effect -> returned or
   delivered result`. An untraced public caller, observable branch, or state
   transition is a blocking review gap.

### Behavioral branch matrix and scope

When the reviewed delta changes observable behavior, both iteration and
whole-branch reviews require a Behavioral branch matrix. Enumerate every
observable branch, including invalid-input and pause/resume paths. Use these
same 10 columns in this order:

1. entry point;
2. trigger;
3. state before the transition;
4. pending or persisted state;
5. reconstructed state after resume (include resumed inputs and explicitly
   identify what is restored, reused, recalculated, normalized, or lost);
6. authorization and policy context;
7. side effect or persistence result;
8. final public result/status;
9. regression coverage; and
10. status: pass, finding, or unverified.

For an iteration review, the matrix covers changed behavioral entry points in
the bounded delta and their directly affected callers, contracts, state
transitions, and public outcomes. For a whole-branch review, it covers every
changed behavioral entry point across `merge_base...final_head`; a delta-only
matrix is insufficient.
For documentation-only work with no changed observable behavior, do not create
an artificial empty matrix; record why the matrix is not applicable in the
review evidence. Any missing required changed branch is a blocking review gap.

## Review evidence

Every iteration review records its iteration base/head, target, working-tree
state, acceptance criteria, focused verification and omissions, directly
affected callers/contracts/invariants, scope-compliance result, coverage gaps,
residual risk, reviewer provenance, and decision. Missing, mismatched, or
unrecorded required evidence means `do-not-approve` for that iteration. The LLM
interprets written findings and recommendations. Python provides structural
evidence only and does not authoritatively establish review scope, dependency
coverage, reviewer identity, or approval.

Every whole-branch review and final-readiness decision records this complete
checklist:

- target, base revision, reviewed revision, and working-tree state;
- `review_role: reviewer`, `reviewer_profile`, and matching completed canonical
  invocation evidence for an approved dispatch mode that records the configured
  independent-review process;
- a change inventory and caller/consumer search;
- verification performed and explicit omissions; and
- coverage gaps and residual risk.

A missing, mismatched, or unrecorded checklist item means `do-not-approve` for
a whole-branch review and `not-ready` for final.
An implementer, architect, or generic subagent may provide advisory analysis,
but advisory generic subagent analysis cannot approve a review or final result.
Recorded role, profile, and invocation fields do not by themselves prove runtime
reviewer identity or read-only execution.

## Configured reviewer invocation

An approving decision requires a completed canonical invocation for the named
repository reviewer, fresh target-state evidence, a matching result digest, and
unchanged repository state as an operational process requirement. The
LLM/controller selects iteration or whole-branch scope, and the independent
reviewer inspects the actual Git range and repository state and records the
exact base and head. Current Python does not authoritatively enforce semantic
review scope, dependency coverage, reviewer identity, or final approval.
[handoffs.md](handoffs.md) is the normative owner of
the invocation paths, supported dispatch modes, envelope fields, provenance
levels, lifecycle, and failure conditions. Copied role fields, self-review,
generic analysis, or an invocation from another mode remain advisory.

## Controller approval-reporting check

Before reporting a workflow as approved, ready, or successfully reviewed, the
controller must inspect current workspace evidence and determine:

1. whether independent review or final readiness was required;
2. whether the configured reviewer was invoked;
3. whether the canonical invocation artifact was created before dispatch;
4. whether the exact returned result was persisted afterward;
5. whether the result applies to the current reviewed revision and working-tree
   state; and
6. whether the returned review contains all evidence required for its applicable
   scope, including caller/consumer coverage, verification and explicit
   omissions, coverage gaps, residual risk, and any required Invariant evidence
   matrix; and
7. whether the returned decision is `approve` or `ready`, as applicable.

If any required answer is no, unknown, unavailable, stale, or unsupported by
current workspace evidence, the controller must not report approval or
readiness. It reports the result as advisory, blocked, incomplete, or stale.

## Invariant evidence matrix

Use an **Invariant evidence matrix** for every applicable high-risk or
state, recovery, concurrency, permissions, migration, or workflow-policy
whole-branch review. Each applicable row records: source claim; schema or
example; normal transition; failure or cancellation; resume; consumers or
policy; negative scenario; fallback or bootstrap; evidence; and status (`pass`,
`finding`, or `N/A`). Every `N/A` must include its reason. The matrix is part of
whole-branch review evidence, not a substitute for the two passes or checklist.

## Output order

1. Decision: `approve` or `do-not-approve`
2. Findings by severity
3. Change inventory
4. Trace evidence
5. Verification evidence
6. Coverage gaps and unverified areas
7. Reviewed revision and working-tree state
8. Residual risk

Each finding has stable ID, severity, confidence, location, trigger, impact,
evidence, required fix, and required regression coverage. See
[severity.md](severity.md).

## User-visible review status

The controller must distinguish advisory analysis from approving review in its
user-visible response.

When canonical approving evidence exists, report the decision together with the
reviewed revision and canonical artifact location.

When canonical approving evidence does not exist, explicitly call the result
advisory and state that it does not approve the task, branch, or final
readiness.

Do not use phrases such as “the reviewer approved”, “the workflow review
passed”, “ready”, or equivalent wording for generic subagent analysis,
chat-only review, missing invocation evidence, stale evidence, or an
unpersisted result.
Approving example:

> Configured independent review approved revision `<sha>`. Canonical invocation
> and result evidence are stored under `<path>`.

Advisory example:

> Independent advisory analysis found no blocking issues, but this is not an
> approving task-workflow review because canonical review evidence was not
> persisted.

## Durable integrated review

After all durable-execution nodes complete, independently review the complete
diff against its merge base using `behavior,data,recovery,compatibility,tests`;
add `security,permissions,privacy,tenant-isolation` when routing affects those
boundaries.
Inspect manifest semantics, transitions, recovery/Git reconciliation, scheduling,
node artifacts, knowledge authority/lifecycle, handoff compatibility,
natural-language routing, stale approvals, bounded fixes, docs, and pressure
scenarios. Specifically challenge duplicate resumes, skipped/dependency-violating
nodes, stale state trusted over Git, completed-node reruns, evidence-free reports,
candidate knowledge injection, advisory override of binding rules, parallel or
mechanic/model-tier dispatch, cyclic fixing, and stale final approval.

For dispatch-compatible changes, search the full diff and durable examples for
mechanic misrouting, detail-based risk downgrade, unsafe force-standard or tier
override, missing assignment/attempt/escalation evidence, completed-node
reclassification, running-node reassignment, lost batch member identity,
partial-batch unlocking, stale binding/advisory context use, model IDs in graphs,
unsupported operational parallel fields, reviewer tier/independence downgrade,
and unsupported cost/cache claims. Review the dogfood fixture as documentation
only: it must not dispatch agents or schedule work.

An integrated finding may use one eligible `fix_policy=blocking` round only when
the existing bounded-fix rules permit it. Review that fix as a new iteration
against the original finding. After all fixes, rerun the whole-branch review
before final readiness; creating a fix node or artifact never adds a graph cycle.

## Revision-bound final

Final readiness is decided by a fresh independent reviewer inspecting the actual
merge-base-to-current-head Git range and repository state. Validator exit 0 is
necessary structural evidence only. The reviewer compares the recorded base,
reviewed head, and working-tree state with current state. Any relevant
production, test, migration, configuration, API, or behavioural delta makes
approval stale: return `not-ready` and require a fresh whole-branch review at
the new final head. Final also verifies blocking fixes, checks for unreviewed
behaviour, records exact checks and omissions, inspects tracked, staged,
unstaged, and relevant untracked files, checks secrets/generated/local/
machine-specific/planning artifacts, confirms docs and migrations match, and
returns `ready` or `not-ready` with current and approved revisions, issues,
verification, gaps, residual risk, and a suggested commit message.

The fresh independent reviewer returns `not-ready` when the configured review
process or reviewer identity cannot be established, the required evidence
checklist is incomplete, an applicable Invariant evidence matrix is incomplete,
or a matrix row is stale for the current revision or working-tree state.
Advisory generic subagent analysis, metrics, and prior invocations cannot replace
that review. Validator errors are blocking, but absence of validator findings
never creates approval. Final returns `not-ready` whenever semantic coverage
cannot be demonstrated, even if the validator exits 0.
