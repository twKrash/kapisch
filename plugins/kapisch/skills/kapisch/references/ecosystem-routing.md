# Ecosystem capability routing and delegation evidence

This reference is the sole normative owner of ecosystem capability selection
and delegated-step behavior: how the KAPISCH controller may use an available
Codex skill or plugin capability for a bounded step, and what durable evidence
every delegation must produce. Request normalization is owned by
[request-normalization.md](request-normalization.md); logical-role selection by
[role-resolution.md](role-resolution.md); risk by [risk.md](risk.md); artifact
placement and write ownership by [handoffs.md](handoffs.md); durable graphs by
[execution-graph.md](execution-graph.md); recovery by [resume.md](resume.md);
and review/final evidence by [review.md](review.md).

## Scope and ownership

Ecosystem capability routing is an optional, sequential capability-delegation
layer owned by the existing KAPISCH controller. KAPISCH may use an available
Codex skill or plugin capability for one bounded step, but it remains
responsible for request normalization, role and risk selection, focused
context, authority, human gates, durable evidence, recovery, independent
review, and final readiness.

This change adds no logical role, agent profile, MCP server, agent-process
manager, semantic router, daemon, or second workflow controller. The six-role
catalog stays closed. A skill or plugin is a capability bundle, not a seventh
role, executor class, profile, or model tier. Capability selection follows role
and risk selection and never changes the selected role, risk, review depth,
required lenses, or approval authority. Additional task detail or a specialist
capability never lowers risk.

The controller selects and uses a bounded skill or plugin-backed capability; it
does not hand ownership of the KAPISCH route to the plugin. A delegated
capability supplies methodology, repository tooling, or an external integration
for one bounded step. It cannot renormalize the top-level request, expand
scope, or take ownership of later gates.

## Selection procedure

The controller applies this order:

1. Normalize the user request and explicit KAPISCH controls.
2. Resolve workflow shape, task identity, scope, acceptance criteria, risk,
   logical role, review needs, and existing authority.
3. If the user explicitly names a skill or plugin, treat that name as a binding
   capability constraint. Do not silently substitute another capability.
4. Otherwise consider only capabilities visibly available in the current
   session. Never claim that the visible set is exhaustive.
5. Select the smallest capability whose documented purpose covers the bounded
   substep without changing its authority or acceptance boundary.
6. If multiple candidates imply materially different behavior, data access,
   external systems, or side effects, stop for one focused user decision.
7. Persist the delegated-step context before invocation.
8. Start only one delegated step, persist its observed result or exact error,
   and verify it before advancing.
9. Feed the verified result back into the existing KAPISCH role and workflow;
   the capability does not decide the next route.
10. Apply ordinary independent-review and final-readiness policy to the complete
    resulting delta.

## User controls and fallback

The expert control is `ecosystem=auto|off` with default `auto`. Ordinary
natural language remains the normal interface; `ecosystem` constrains the
LLM/controller's interpretation, never a separate entry point.

- `ecosystem=off` prevents capability delegation but does not disable ordinary
  KAPISCH roles or built-in repository tools.
- An explicit skill or plugin mention overrides `auto` and is required when the
  user has mandated a particular methodology or integration. Under
  `ecosystem=off`, a mandated capability cannot be delegated: report the
  conflict and the safe setup or selection action rather than silently ignoring
  the mention or delegating anyway.
- If an explicitly required capability is unavailable, block and report the
  missing capability and safe setup or selection action. Do not silently
  substitute another capability.
- If an automatically selected capability is unavailable, fall back to native
  KAPISCH execution only when the same approved outcome remains achievable
  without changing methodology, data boundary, or authority. Disclose the
  fallback.
- Do not install, enable, sign in to, or alter configuration as a fallback.
- Do not choose a capability from name similarity alone. Use its current
  documented description and exposed actions.

Graph-free workflows do not delegate in the current scope. An explicit
capability constraint in a graph-free workflow blocks and asks the user to
promote the work to a durable version-3 graph or to relax the constraint before
native execution. An automatic selection may use the disclosed native fallback
only when the approved outcome remains unchanged; otherwise it asks whether to
promote the work to a durable graph.

Delegation fails closed: any ambiguity about capability identity, availability,
authority, or side-effect boundary stops for a user decision or blocks with the
missing capability and a safe next action. Never claim capability presence,
authority, or effect without observable evidence.

## Composition and recursion

The route stays flat and explainable. A delegated capability cannot recursively
delegate the KAPISCH route or invoke `$kapisch`. If its documented procedure
requires another capability, the controller evaluates that need and records a
new sibling delegated step with its own context, authority, and evidence.
Delegation never revives operational waves, parallel scheduling, worktree
integration, or multi-writer execution: the controller invokes at most one
delegated capability at a time. Graph-free delegation (a route record without a
version-3 execution graph) is deferred to a later change.

## Delegation evidence layout

Delegation evidence is mandatory whenever KAPISCH uses an ecosystem capability,
including when the user selected `handoff=chat`. It is required for route
explanation, review, and safe resume; it is not an optional presentation
handoff. It is a separate route record under the task run directory. Within
the current scope the record is validated only as part of version-3 durable
runs; graph-free delegation is deferred to a later change:

```text
.kapisch/runs/<task-id>/
└── delegations/
    ├── 00-route.toml
    └── D01/
        ├── 00-context.md
        └── 01-evidence.md
```

### `delegations/00-route.toml`

A closed, versioned schema with these root fields:

- `version`;
- `task_id`;
- stable `route_id`;
- route `source_revision`;
- ordered `steps`;
- optional reverse-DNS `extensions` for runtime-specific receipts.

Each step records the minimum delegation metadata needed to identify the
selected capability and its maximum effect class:

- stable `id` and non-negative `sequence`;
- `parent_node_id` — the owning graph node; every shipped step must name one;
- `selection_mode = explicit|automatic`;
- `capability_kind = skill|plugin-skill|plugin-tools`;
- `requested_capability` and `resolved_capability`;
- `source_plugin` when actually exposed, otherwise `unavailable`;
- maximum `effect_class`;
- `authority_mode` and an in-context `authority_ref`;
- context and evidence paths plus lowercase SHA-256 digests;
- optional exposed runtime/tool receipts below reverse-DNS `extensions`.

Step lifecycle tracking (planned/started/completed/blocked/failed states) and
per-step repository revision chains are deferred to later changes backed by
demonstrated needs; the graph node lifecycle and revision evidence already
exist on the execution graph. The same applies to sophisticated
resume/external-effect reconciliation. Because that machinery is deferred, the
validator rejects `external-write` and `destructive` routes regardless of their
authority metadata, while read-only (`repository-read`, `external-read`) and
`repository-write` delegated effect classes remain accepted.

The effect classes are:

- `repository-read`;
- `repository-write`;
- `external-read`;
- `external-write`;
- `destructive`.

Every authority mode requires a non-empty in-context `authority_ref`; the
literal `unavailable` is not an authority reference. The authority modes are:

- `request-scoped`: the already-approved request authorizes this bounded read or
  workspace action;
- `explicit-step`: the user explicitly approved this exact side-effect step.

One record represents one maximum effect class. Mixed-effect workflows split at
the authority boundary. For example, GitHub diagnosis (`external-read`), local
repair (`repository-write`), and posting a PR comment (`external-write`) are
three sequential records rather than one opaque operation; the external write
requires `authority_mode = explicit-step` and a valid in-context
`authority_ref`.

Unknown root or step fields, aliases, and out-of-enum values fail closed, as do
duplicate step IDs or sequence values. Runtime receipts live only below
reverse-DNS `extensions`; they never change a step's recorded meaning.

Step IDs are stable identifiers matching `D` followed by at least two digits
(`D01`, `D02`, ...). The exact closed field names are:

```toml
version = 1
task_id = "example"
route_id = "example-route"
source_revision = "base"

[[steps]]
id = "D01"
sequence = 1
parent_node_id = "T01"                    # the owning graph node
selection_mode = "explicit"               # explicit|automatic
capability_kind = "skill"                 # skill|plugin-skill|plugin-tools
requested_capability = "instruction-only-skill"
resolved_capability = "instruction-only-skill"
source_plugin = "unavailable"             # plugin id when actually exposed
effect_class = "repository-read"          # repository-read|repository-write|external-read|external-write|destructive
authority_mode = "request-scoped"         # request-scoped|explicit-step
authority_ref = "request:example"
context_path = "delegations/D01/00-context.md"
context_sha256 = "0123...64 lowercase hex..."
evidence_path = "delegations/D01/01-evidence.md"
evidence_sha256 = "4567...64 lowercase hex..."
```

Every step records a context file and digest (persisted before invocation) and
an evidence file and digest (persisted after the step resolves). Both files
must be valid UTF-8 inside the task directory, with exact lowercase SHA-256
digests of the persisted bytes; the literal `unavailable` is used only where
the schema allows it (`source_plugin`), never for required context or evidence
paths/digests. Step lifecycle states
(`planned`/`started`/`completed`/...) and per-step repository revisions are
deferred to a later change: the graph node lifecycle and revision evidence
already cover them, and the route record identifies the selected capability and
its maximum effect class. `resolved_capability` is required (not
`unavailable`). Every authority mode requires a non-empty in-context
`authority_ref`. `external-write` and `destructive` remain schema enum values so
their intent can be diagnosed precisely, but default validation rejects them;
`authority_mode = "explicit-step"` does not override that restriction.

### `Dnn/00-context.md`

The controller writes a self-contained, focused context containing:

- parent task or graph node;
- exact bounded goal and expected output;
- requested and resolved capability;
- observable selection reason;
- accepted input paths, symbols, resources, and context references;
- data that may cross the repository boundary;
- authority already granted;
- actions that still require a gate;
- forbidden actions;
- success and verification checks;
- fallback or blocking behavior.

Do not include full conversation history, broad repository content, secrets, or
unrelated durable knowledge "just in case."

### `Dnn/01-evidence.md`

The controller persists:

- observed outcome;
- capability and tools actually observed;
- relevant returned data or bounded output references;
- local files or external resources affected;
- external operation IDs or URLs when exposed;
- exact commands/checks and results;
- changed artifacts or unchanged-state evidence when exposed;
- omissions, errors, ambiguity, and retry safety;
- verification against the parent acceptance criteria.

Do not fabricate a separate agent or skill result when the skill was applied
inline. Record the actual observable operations and evidence.

The controller remains the sole writer of the route, context, and evidence
records. A delegated researcher, architect, reviewer, skill, or plugin tool does
not modify shared KAPISCH state merely to record its own result.

## Authority and side-effect boundaries

- **Authority cannot be laundered through a delegate.** A skill or plugin may
  not infer commit, push, merge, publish, send, destructive, dependency-install,
  configuration, authentication, or external-write authority.
- **Installation and authentication are outside routing.** KAPISCH never
  installs, enables, authenticates, or reconfigures a skill, plugin, connector,
  or MCP server automatically.
- **External side effects are split at the gate.** Preparation and preview are
  separate from execution. An external write or destructive action requires
  exact, explicit authority for its target and payload.
- **Reviewer authority is not delegable.** Specialist review skills and tools
  may provide advisory evidence or a review lens, but only a fresh canonical
  `reviewer` invocation may approve or declare final readiness.
- **Runtime provenance is recorded only when exposed.** Installed filenames,
  requested names, prompts, output wording, or controller claims do not prove
  that a runtime selected a particular skill or plugin. Unexposed receipts are
  recorded as `unavailable`.

## Resume and side-effect recovery

Delegated-step lifecycle states, revision chains, replacement records, and
resume reconciliation are deferred to a later change. The current route is
implemented structural metadata, not a recovery state machine or external-effect
runtime acceptance. Delegated execution is therefore restricted to
`repository-read` and `external-read`. The validator rejects `external-write`
and `destructive` even with `authority_mode = explicit-step`: authority does not
provide effect reconciliation, and an interrupted effect cannot be classified
as safely retryable. Repeated resume must preserve that fail-closed result.

The restriction may be lifted only after a versioned lifecycle records intent,
start, provider result, and completion; resume can reconcile ambiguous outcomes
read-only against stable provider operation identifiers; retries require a
provider-supported idempotency contract; and interruption/crash tests prove that
unknown outcomes block without duplicating effects. This does not promise
exactly-once delivery.

## Validator boundary

Repository Python validates the route record structurally and read-only:
supported route version and closed root/step schemas; required fields, scalar
and list types, and allowed enums; stable delegation-ID grammar; unique step
IDs and sequence values; task-directory path containment; rejection of
symlinked evidence; required UTF-8 context and evidence files; lowercase
SHA-256 format and exact byte-digest matches; fail-closed rejection of
external-write/destructive steps even with explicit authority; graph
parent ownership, unique graph references, and route/manifest identity; and
read-only effect classes for review/final delegations. Step lifecycle states
and per-step repository revisions are deferred to a later change and are not
validated here. Structural acceptance is not execution acceptance: only
`external-write` and `destructive` routes are rejected; read-only
(`repository-read`, `external-read`) and `repository-write` routes remain
executable.

Python does not implement capability discovery or installation; description
matching or semantic selection; request parsing or route planning;
user-authority inference; plugin, connector, tool, or agent dispatch;
external-system reconciliation; semantic output sufficiency; or reviewer
identity or approval authority. Capability selection and delegation remain
controller decisions. Prose in this repository never implies that Python
performs selection or dispatch.
