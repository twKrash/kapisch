# Handoff artifacts

This reference is the normative owner of artifact storage, controller write
ownership, delivery guarantees, reviewer invocation envelopes, and task-ID
placement. Review and final evidence meaning is owned by [review.md](review.md);
recovery of these artifacts is owned by [resume.md](resume.md).

Use `handoff=both` by default: the controller writes a durable handoff and
summarizes it in chat. `handoff=file` writes without the chat summary.
`handoff=chat` suppresses optional research/plan/implementation/mechanic delivery
files, but an approving review or final still requires its canonical invocation
and result artifacts. A chat-only review/final without those artifacts is
advisory only and cannot approve.

The controller must never infer that `workflow=task`, graph-free execution,
`handoff=chat`, read-only subagents, an unchanged working tree, or the absence
of a durable execution graph waives canonical review or final artifact
requirements.

When required invocation or result artifacts are absent from the current
workspace, treat them as not created. Conversation summaries, subagent claims,
copied reviewer fields, or recollection of an earlier result do not substitute
for current durable evidence.

Handoffs are uncommitted working-tree artifacts under:

```text
.kapisch/runs/<task_id>/
```

Use the root directory for research, plan, mechanic, and non-review
implementation artifacts. Store every review and final artifact under
`reviews/`:

```text
.kapisch/runs/<task_id>/
  00-research.md       # project-understanding research when requested
  00-context.md
  01-plan.md
  02-execution-graph.toml  # optional durable execution
  03-state.toml            # optional durable execution
  03-state.md              # optional non-authoritative rendered view
  tasks/T01-brief.md       # optional durable execution
  tasks/T01-context.md
  tasks/T01-report.md
  knowledge/records.toml
  reviews/
    round-0/00-review-invocation.toml
    round-0/03-review.md
    round-1/02-implementation.md
    round-1/03-review.md
    round-2/02-implementation.md
    round-2/03-review.md
    final/00-final-invocation.toml
    final/05-final.md
```

`round=0` is the independent reviewer’s initial review. A user-approved follow-up
uses `round=1`; later rounds increment from there. The controller persists the
implementer's returned evidence in `02-implementation.md` and the independent
reviewer's exact returned evidence in `03-review.md` in the same round directory.
Do not create a later round without explicit user approval, except a bounded
pre-authorized `fix_policy=blocking` round described below.

## Delivery guarantee

For `handoff=file` or `handoff=both`, the controller resolves the task ID and
creates the designated handoff artifact before dispatching the role. Initialize
it with `status: in_progress`. After receiving the role result, the controller
persists the exact returned evidence plus a stable invocation/attempt ID and
result digest, then updates it to `status: complete`, `blocked`, or `failed`.

A blocked or failed handoff must retain the exact command and error when one
exists, the completed and skipped work, and the next safe action. If the
handoff path itself cannot be written, report that durability failure in chat;
do not silently continue without an artifact.

Use only the file for the current mode:

```text
00-research.md         project-understanding research
00-context.md          plan input context, written by plan mode when useful
01-plan.md             plan
02-implementation.md   implementation summary
03-review.md           review
04-mechanic.md         mechanical cleanup
reviews/final/05-final.md final readiness review
```

For a project-understanding `researcher` route with `handoff=file|both`, the
controller initializes `00-research.md` before dispatch and completes its
lifecycle from the researcher's exact returned evidence under the same delivery
guarantee. The researcher remains read-only and never writes the handoff.

The controller is the sole writer of every handoff. Research, plan,
implementation, mechanic, review, and final roles return structured evidence
only; the controller persists it in the relevant mode-specific artifact. This
prevents a researcher, reviewer, or architect from modifying the workspace
merely to create an artifact, while preserving a durable, attributable record.

When durable execution is active, the manifest, state, tasks, and ledger extend
rather than replace these artifacts. Initialize the graph/state before dispatch,
update them after every transition, and preserve completed evidence. The
controller performs these writes from role-returned evidence. See
[execution-graph.md](execution-graph.md), [resume.md](resume.md), and
[knowledge-discipline.md](knowledge-discipline.md).

Every artifact named by a graph node, handoff, review, or final-readiness
contract must be created before its transition or dispatch. Before returning,
persist the report and state reference. Missing named evidence blocks; chat-only
results never substitute for durable evidence.

## Delegation evidence

Delegation records live under `.kapisch/runs/<task_id>/delegations/` as
`00-route.toml` plus `Dnn/00-context.md` and `Dnn/01-evidence.md`, with the
exact schema and required contents defined in
[ecosystem-routing.md](ecosystem-routing.md). They are separate from review
artifacts and are mandatory whenever KAPISCH uses an ecosystem capability,
including with `handoff=chat`: they are required for route explanation, review,
and safe resume, not an optional presentation handoff. The controller remains
the sole writer of the route, context, and evidence records; a delegated
researcher, architect, reviewer, skill, or plugin tool does not modify shared
KAPISCH state merely to record its own result. Inline skill application is
recorded as observed operations, never as a fabricated separate agent result.

## Canonical reviewer invocation artifact

The sole canonical reviewer-invocation representation is a pre-dispatch file:
`reviews/round-<n>/00-review-invocation.toml` for `mode=review` and
`reviews/final/00-final-invocation.toml` for `mode=final`. Do not duplicate this
record in a separate graph collection. The graph/state may reference its stable
ID and path, but never replace it.

The controller creates the file with a stable invocation ID before dispatch. It
uses a closed, flat top-level schema: unknown fields and aliases fail closed,
and optional runtime or transport metadata belongs only below reverse-DNS
namespaced `extensions`. Every invocation records a required non-empty
`external_task_request` string with no alias, plus: mode (`review` or `final`);
dispatch mode (`runtime-named-spawn` or `external-named-task`); requested
role/profile; stable task name; non-`unavailable` `dispatching_controller` task
or session reference; target/base/revision; canonical pre-dispatch
`working_tree_state`; its `pre_dispatch_state_digest`; canonical
`post_review_working_tree_state`; its `post_review_state_digest`;
`lifecycle_status` (`planned|dispatched|completed|blocked|failed`); expected
result artifact; and terminal result. Required fields have no aliases or inferred
defaults. A `runtime-named-spawn` additionally records the
exact spawn request with `agent_type="reviewer"` and `fork_turns="none"`, then
the matching successful spawn result and returned task name/nickname when
exposed, and records `external_task_request: unavailable`. At `planned`, its
returned spawn task name is exactly `unavailable`; later lifecycles allow only
the requested `task_name` or documented `unavailable` when no name is exposed. An
`external-named-task` instead records the exact self-contained request in
`external_task_request` before dispatch and a stable external task/session ID or
URL distinct from the controller. The stable task name and every populated
external ID, URL, or reference also differ from `dispatching_controller`. When
neither runtime ID nor URL is exposed, the controller
generates and persists a unique `external_task_ref` before the external task
starts; it records `external_task_id: unavailable`,
`external_task_url: unavailable`, and
`identity_assurance: user-attested-external-reference`. The user attests that
the task was created separately and that the UI selected the repository Reviewer
agent. The generated reference must match
`ext-[a-z0-9][a-z0-9-]{2,79}`. The self-contained request and digest-bound
completed result each contain exactly one case-sensitive logical line
`external_task_ref=<ref>`, split only at LF or CRLF boundaries and with no
leading/trailing whitespace or surrounding prose. Omission, a changed value,
substring coincidence, or duplicate exact lines fail closed. The generated
reference is not runtime-provided identity. When a runtime ID or URL is
populated, `external_task_ref: unavailable`, assurance remains
`external-named-task`, and neither request nor result requires a fallback token.
`dispatched` means
that the external identity or compatibility reference and request are recorded.
On completion either mode records the exact raw reviewer-result bytes at the
graph node's declared report path. The expected path always equals that node
report; on completion the produced path equals it too, while a non-completed
produced path remains `unavailable`. Review and final nodes may not reuse or
alias one resolved report path. The envelope records `result_encoding = "utf-8"`,
their 64-character lowercase
SHA-256 digest, returned reviewer fields, terminal agent status when exposed,
and the independently recomputed post-review Git state. The result echoes the
invocation ID as exactly one case-sensitive `invocation_id=<id>` LF/CRLF logical
line, with no surrounding prose, but not its own digest.

`identity_assurance` is the only assurance field. Its exact values are
`observable-named-dispatch`, `external-named-task`, and
`user-attested-external-reference`; `assurance_level` and all aliases are
unknown top-level fields. A matching `runtime-named-spawn` uses
`observable-named-dispatch`, unavailable external identity fields, false
Reviewer-selection attestation, and reviewer task/result names distinct from
the controller. An external task with a runtime-supplied ID or URL uses
`external-named-task`; the fallback described above uses
`user-attested-external-reference`. External provenance is operational and
human-attested, not cryptographic runtime attestation. Runtime-only Level 2
fields (`runtime_invocation_id`, `runtime_assignment_receipt`,
`effective_sandbox_receipt`, resolved role/config, or permission profile) are
optional capability fields below `extensions`. Record actual values only when
exposed; otherwise write `unavailable`. Requested profile, model, task name,
reviewer output, metrics, and parent configuration never establish Level 2. A
requested reviewer `read-only` policy is distinct from unavailable effective
sandbox proof; Level 1 relies on the selected mode's independent-context
evidence and unchanged repository-state evidence instead.
The controller alone transitions `planned -> dispatched` immediately around the
selected mode, then `dispatched -> completed|blocked|failed`. At `planned` or
`dispatched`, result and returned fields are the literal `unavailable`; identity,
`external_task_request`, expected result path, `result_encoding = "utf-8"`, and
pre-dispatch state are already populated. The fallback request-line check already
applies; the result-line check begins only at `completed`. `completed` means a
complete result was returned,
including a negative decision. Review decisions are exactly `approve` or
`do-not-approve`; final decisions are exactly `ready` or `not-ready`; every
other lifecycle status has `returned_decision = "unavailable"`. A Level 1
invocation may become `completed` without Level 2 metadata. It blocks for a
missing/mismatched runtime spawn request, missing
`agent_type="reviewer"` or `fork_turns="none"` for that mode, task-name mismatch,
an external task equal to the controller, a missing, changed, duplicated, or
reused `external_task_ref`, missing external Reviewer-selection attestation,
generic output, stale revision/state, changed repository state, digest mismatch,
incomplete reviewer evidence, unavailable reviewer role, or failed dispatch.

Graph status remains distinct from invocation lifecycle. A completed review
with `approve`, or final with `ready`, completes its node. A completed negative
decision fails its node. Invocation `blocked`/`failed` maps to the corresponding
node status. Only `approve` establishes an approving-review pointer, and only
`ready` completes final readiness.

The pre/post Git payloads use this exact ordered UTF-8 representation with no
trailing newline:

```text
head=<revision>;index_sha256=<digest>;staged_diff_sha256=<digest>;unstaged_diff_sha256=<digest>;status_sha256=<digest>;relevant_untracked_count=0;relevant_untracked_sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The component digests are SHA-256 of raw output from, respectively,
`git ls-files --stage -z`,
`git diff --cached --binary --full-index --no-ext-diff`,
`git diff --binary --full-index --no-ext-diff`,
`git status --porcelain=v1 -z --untracked-files=all`, and
`git ls-files --others --exclude-standard -z`. Relevant untracked output must be
empty. Each state digest is SHA-256 of its exact payload. Approval requires the
pre/post payloads and digests to match, and
`returned_working_tree_state` echoes the pre-dispatch payload.

The controller's envelope is mandatory and has stable fields: invocation ID;
mode; dispatch mode; mode-specific spawn request/result or external-task
identity (ID/URL or the compatibility `external_task_ref`); the required
`external_task_request`; role-selection
attestation; stable task name; canonical encoding (`utf-8`);
exact returned-content reference or inline bytes; SHA-256 digest of those bytes;
pre/post Git-state digests; and the reviewer-returned target, base, revision,
working-tree state, role, profile, decision, and findings. Runtime-only Level 2
fields are included only when exposed, otherwise explicitly `unavailable`. The
controller may add transport metadata but must not rewrite reviewer-returned
fields. The review/final artifact references this envelope and repeats its ID and
digest. A missing Level 1 spawn/non-mutation field, noncanonical bytes, or digest
mismatch blocks approval and resume; unavailable Level 2 metadata does not.

An approving artifact is invalid when its invocation record is missing,
mismatched, reused, stale for its revision/state, incomplete, or not terminally
`completed` with matching mode-specific evidence. A review invocation cannot
satisfy final: final always has its own fresh `final/00-final-invocation.toml` and
distinct reviewer task or runtime spawn. Same-task mentions, copied role/profile
fields, generic subagent reports, and metrics are advisory only. They cannot
create, transition, or substitute invocation evidence.

These canonical fields preserve controller-supplied structural process evidence.
The reviewer records the exact base and head in the returned report, but current
Python does not authoritatively establish semantic review scope, dependency
coverage, reviewer identity, a complete approval chain, or final readiness.

Before any narrow failed-history compatibility skip, the controller and
validator reserve every valid non-`unavailable` invocation ID in its own
namespace and every populated external task ID, URL, or reference in one shared
external-identity namespace from each syntactically readable current or
historical envelope. Duplicate external identities, including cross-field reuse,
fail regardless of manifest order. Only a failed review/final with a valid reservable invocation ID and
schema findings limited to missing or unknown top-level fields may be preserved
as schema-old non-approving history; unreadable, wrong-shape,
malformed-extension, or otherwise invalid evidence is never silently skipped.

### Reviewer dispatch fixture

Fixture records use one `dispatch_mode` only. A valid `external-named-task`
fixture has a distinct external task ID/URL, or, when both are unavailable, a
pre-persisted controller-generated `external_task_ref` such as
`ext-final-72956c-01`. The compatibility fixture records the two unavailable
runtime fields and `identity_assurance: user-attested-external-reference`, has
user-attested Reviewer UI selection, requested
`.codex/agents/kapisch-reviewer.toml`, and stores its self-contained request in
`external_task_request`. The returned canonical profile path records that
attested UI selection; it is Level 1 evidence, not a runtime assignment receipt.
That request and the digest-bound result each contain the exact canonical
`external_task_ref=<ref>` logical line once. It also
has matching result digest/returned role/profile/target state and unchanged
pre/post Git state. A same-task mention, generic external task, missing, changed,
duplicated, or reused reference, missing attestation, or a review record reused
for final is invalid. Resume accepts a completed matching reference
idempotently. This fixture is documentation-only and never launches an agent.

Validation-only compatibility keeps already-completed envelopes from the prior
profile layout readable without rewriting their bytes: the requested and
returned profiles may both be `.codex/agents/reviewer.toml` when
`lifecycle_status=completed`. A historical `blocked` or `failed` envelope may
also retain that legacy requested profile while every result and returned field
remains `unavailable`. Mixed profile identities, arbitrary paths, and the legacy
path on any planned or dispatched invocation are invalid. Every newly created
invocation uses
`.codex/agents/kapisch-reviewer.toml`; compatibility acceptance never authorizes
a new legacy-profile dispatch.

This exception is structural validation, not validator-enforced migration
provenance. The controller must establish that the envelope came from the
supported, explicitly approved `.planning/task-workflow/<task-id>/` migration
before consuming it as legacy evidence. When that supported origin is not
available, block reuse and require a fresh canonical-profile invocation. Stored
bytes and digests detect inconsistency but do not prove authorship or creation
history; this creation-policy trust boundary remains controller-owned.

## Final-only workflow metrics

When persisted `workflow_metrics=final` is requested, only the controller maintains
`.kapisch/runs/<task_id>/metrics.md`. It is ignored with `.kapisch/`;
do not stage it or emit interim metric summaries in chat. Update the local record
after terminal attempt/invocation/batch/fix transitions. Emit one concise
aggregate exactly once after the terminal final-readiness attempt when terminal
evidence is available, whether its result is `ready`, `not-ready`, `blocked`, or
`failed`; never emit an interim summary.

Workers never write this shared file; they return observable evidence in existing
reports. The controller aggregates stable terminal IDs once in deterministic
order and resume never double-counts them. For every
attempt, record role, configured model/reasoning when known, mode,
invocation count, terminal outcome, commit/review/fix references, and available
elapsed-time evidence. Record token totals, provider usage, or percentages only
when the execution surface supplies them; otherwise write `unavailable`, never
an estimate. Exclude prompts, secrets, private context, hidden reasoning, and
unredacted tool output.
Metrics may reference a reviewer invocation but never establish reviewer
provenance or approve a review.

Only the controller writes handoff artifacts under
`.kapisch/runs/<task_id>/`. Planning and review/final roles use
read-only context and return evidence; implementation roles may write only their
approved task scope. No role may use handoff creation to justify unrelated source,
docs, tests, configuration, or repository-state changes.

Never put secrets, credentials, tokens, private keys, or unrelated personal
data in a handoff.
Start every handoff with mode, role, date, branch, task ID, round when present,
status, user goal, constraints, commands/results, assumptions, open questions,
and the next step. Also record the canonical normalized request and source:
resolved goal, mode, risk, depth, focus, target/base, plan or findings,
acceptance criteria, invariants, explicit restrictions, fix policy and maximum
rounds, concise routing reasons, active-context reuse, and unresolved material
ambiguity. Do not store hidden reasoning. Preserve compatibility with existing
artifacts by adding these fields as a readable section rather than requiring a
schema version.

## Review evidence and bounded fixes

Plan/implementation artifacts record their scoped inputs, changes, and
verification. Review/final artifacts store the evidence and decision defined by
[review.md](review.md), which is the sole owner of checklist, matrix, freshness,
and approval semantics. This file owns their paths, invocation references, and
controller persistence. When metrics were requested, final artifacts reference
`metrics.md`; metrics never substitute for review evidence.

When dispatch-compatible routing is used, durable handoffs and state also record
the logical assignment and observable reason codes; source and attempt revisions;
context references or fingerprints; attempt and escalation IDs/history; batch
and member IDs/outcomes; and exact verification evidence/results. Record only
observable evidence: never hidden reasoning, model identifiers, fabricated
cost/cache metrics, or savings claims without evidence. An assignment preview is
recorded as proposed and does not authorize work before plan approval.

`fix_policy=manual` is the default: after round 0 the user explicitly selects
findings and authorizes the next round. `fix_policy=blocking` pre-authorizes only
one round by default (`max_fix_rounds=1`) of confirmed P0/P1/blocking-P2 findings
when the reviewer states a concrete fix and it remains in approved files and
behaviour. It cannot cover likely/question/P3 findings, new dependencies, public
contract expansion, or architecture, product, security-policy, migration-strategy,
or permission-model decisions. Count the automatic fix rounds; stop when the
limit is reached. Every fix receives a fresh independent reviewer validation.

Automatic fix authorization never authorizes commits, pushes, dependency installs,
resets, destructive commands, or a later unlimited loop.

## Task ID

Use an explicit `task_id` only when it matches
`[a-z0-9][a-z0-9-]{2,79}`. Otherwise:

1. Reuse `<task_id>` if `plan`, `context`, or `issues` names a file **or
   directory** under `.kapisch/runs/<task_id>/`, including a
   `reviews/round-<round>/` subdirectory.
2. Otherwise derive an ID from `task`: lowercase it, remove markdown and
   quotes, replace non-`a-z0-9` runs with `-`, collapse and trim `-`, then keep
   the first 48 characters.
3. Ask for `task_id` if the result is empty or one of: `fix`, `update`,
   `changes`, `task`, `work`, `review`, `implementation`, or `cleanup`. If a
   directory already belongs to a different task, append `-2`, `-3`, and so on.

Once created, reuse the canonical task ID for all later modes. Read a supplied
handoff before inspecting other repository files.

Examples:

```text
task="M16C: request IDs + audit logs" -> m16c-request-ids-audit-logs
task="Fix the empty-memory CLI error" -> fix-the-empty-memory-cli-error
context=".kapisch/runs/refresh-readme/" -> reuse refresh-readme
```

## Version-4 compact outcomes

Each terminal attempt stores one immutable
`stage-outcomes/<attempt-id>.toml`. It binds assignment/attempt identity,
lifecycle, bounded findings and verification references, detailed report digest,
and reviewer invocation facts where applicable. It excludes transcripts, raw
tool output, hidden reasoning, and runtime transport fields. Detailed reports
remain canonical evidence; compact outcomes do not replace review or final
invocations.
For a reviewer-finding redispatch, the digest-bound detailed reviewer report records one contiguous canonical finding block: `finding_id`, `finding_severity`, `finding_summary`, and `finding_scope`, one `key: value` field per line in that order. The compact finding must exactly equal one such block; values from separate blocks and prefixes never authorize redispatch.
