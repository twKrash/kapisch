# Canonical dispatch contract

This reference describes the durable assignment facts that the LLM/controller
records after choosing a logical role. [role-resolution.md](role-resolution.md)
owns the LLM/runtime boundary. It does not create a scheduler, classify English
requests, or resolve profiles. Durable execution is sequential; operational
waves are unsupported.

## Delegation annotates an assignment

Using an ecosystem capability annotates an existing role assignment; it never
creates an executor class or tier. The controller may delegate one bounded
substep of the assigned role's work to an available skill or plugin capability,
but the persisted role, executor class, model tier, review depth, and approval
authority stay unchanged, and delegation never dispatches a second executor.
At most one delegated step may be active: delegation is sequential and never
revives parallel scheduling, worktree integration, or multi-writer execution.
The selection procedure, fallback, and delegation evidence contract are owned by
[ecosystem-routing.md](ecosystem-routing.md).

## Observable classification

Classify from the approved task's stated behaviour change, acceptance criteria,
invariants, exact scope, public boundaries, side effects, migration or recovery
needs, dependency state, and declared risk. Persist concise reason codes and the
source revision and schema version with the assignment; do not persist hidden
reasoning, token costs, cache observations, or model identifiers.

`execution_class` is independent from risk. More detail can make an assignment
deterministic, but never lowers risk, review depth, required lenses, or
regression coverage.

| Execution class | Executor class | Logical tier | Deterministic boundary |
| --- | --- | --- | --- |
| `mechanical` | `mechanic` | `cheap` | Only when every mechanic condition below is met. |
| `prescriptive` (non-high-risk) | `implementer-lite` | `cheap` | Fully specified behavioural work with no design choice. |
| `prescriptive` (high-risk) | `implementer` | `standard` | High risk promotes the executor and preserves deep review. |
| `bounded` | `implementer` | `standard` | Scoped work that needs normal implementation judgment. |
| `design` | `architect` | `high` | Architecture, security, migration, concurrency, or material ambiguity. |

The table is a minimum-strength policy. High-risk prescriptive work canonically
uses `implementer` at `standard`, never `implementer-lite` or `cheap`, and
retains deep independent high-tier review. High risk alone does not require
final; final readiness follows the delivery-boundary policy in
[review.md](review.md).

## Mechanic eligibility

Use `mechanic` only when all of these are observable from the approved request:

1. The files and exact non-behavioural outcome are specified.
2. The change is deterministic and requires no design, product, or policy
   decision.
3. It changes no production behaviour, public wording, API, schema, permission,
   persistence, migration, or architectural boundary, except for the exact
   authoritative-documentation synchronization case below.
4. Required verification is explicit and sufficient to show the mechanical
   result.

The sole public-wording exception is verbatim synchronization from an already
approved authoritative document to an identified target. It is mechanical only
when the request names both source and target, the copied content is exact, and
the task introduces no new or reinterpreted policy, product, or public-contract
wording. Verification must compare the target with the authoritative source.
Any ambiguity, adaptation, or source-authority question routes to a stronger
executor.

Examples that are decisively not mechanical include persisting new state,
changing a test expectation, creating or revising public wording outside that
narrow synchronization case, altering permissions, adding a dependency,
modifying an API/schema, or choosing between plausible implementations.

## Overrides and escalation

A user may safely upgrade an assignment to a stronger executor, tier, review
depth, or lens set. Refuse a requested downgrade that would violate declared or
derived risk, required review depth/lenses, the mechanic conditions, permission
or security invariants, or an approved plan's acceptance criteria.

One automatic escalation is permitted per persisted assignment. It records the
trigger, stable prior/new assignment and attempt IDs, source/attempt revisions,
and context/scope evidence. A retry with identical context and scope cannot
escalate again. A `design` node blocks for an architect amendment; only an
amended, explicitly approved plan may be assigned for implementation.

## Sequential batches

Batching is optional and never parallel. A batch is eligible only when every
member has the same compatible executor class and logical tier, independent
scope, no unresolved dependency between members, compatible permissions and
verification, and an explicit composite acceptance boundary. Persist the batch
ID, ordered member IDs, each member's assignment and outcome, and exact
member/composite verification evidence and results.

A batch is one sequential composite execution unit. It completes only when
every member completes. On partial completion, preserve successful-member
evidence but unlock no downstream work unless explicit member-level dependencies
allow it; otherwise the batch remains unresolved.

Persist each assignment, attempt, escalation, batch, and verification record
before its associated lifecycle transition. On resume, validate stable IDs,
source/attempt revisions, context/scope evidence, batch membership/outcomes,
and verification results against repository evidence before selecting the next
permitted transition; missing or conflicting evidence blocks the node.

`dispatch` selects implementation executor assignments only. For
`dispatch=single`, every implementation node must persist
`executor_class=implementer` and `model_tier=standard`; block or reject another
implementation assignment with an observable mismatch reason and never silently
reroute a running node. A `kind: review` or `kind: final` node instead retains
its mandatory independent `executor_class=reviewer`, `model_tier=high` under
both `single` and `auto`; it is never a batch member and is not an
implementation-dispatch exception.

## Logical durable values

Durable graphs use only the six closed roles: `mechanic`, `implementer-lite`,
`implementer`, `architect`, `researcher`, and `reviewer`. `researcher` is
advisory/read-only and never an implementation node, approval role, or batch
member. `reviewer` is additionally valid only for `kind: review` or `kind:
final` nodes at the `high` tier; it is never an implementation-dispatch target
or batch member.
Durable graphs use `cheap`, `standard`, and `high` logical tiers and documented
execution classes. These are replaceable routing values, not model identifiers.
They do not claim a model, token, cache, cost, or performance outcome.
