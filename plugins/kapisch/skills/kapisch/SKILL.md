---
name: kapisch
description: >-
  Use when a repository task needs repeatable planning, implementation,
  independent review, final-readiness, narrow mechanical cleanup, or bounded
  read-only project understanding such as architecture questions and maps,
  documentation-drift checks, onboarding summaries, and decision-record
  preparation.
---

# KAPISCH Workflow

## Durable artifact validation

For read-only structural validation of a sequential durable TOML artifact tree,
run the installed validator with `--task-dir` rooted in the consumer repository:

```text
kapisch-validate --task-dir <consumer-repository>/.kapisch/runs/<task-id>
```

The installed command discovers its bundled contracts independently of the
working directory. `--contract-dir PATH` is an expert override, not required
for normal use. See the [validator section in the repository
README](../../README.md#validator). The validator does not dispatch, repair,
schedule, or approve work.

Validator exit 0 is necessary structural evidence only; validator errors are
blocking. Exit 0 does not establish iteration or whole-branch scope, dependency
coverage, reviewer identity, a complete approval chain, or final readiness.
Those remain process decisions for the LLM/controller and an independent
reviewer inspecting the actual Git range and repository state.

## Quick start

Natural language is the complete normal interface:

```text
Fix the reconnect bug and add a regression test.

Investigate duplicate reminder delivery; fix only if local/no API or migration.

Execute the approved M18 plan end-to-end.

Review my current branch before I open a PR.

Map the repository architecture and explain where reminder delivery is owned.

Check whether the architecture documentation still matches the current code.
```

The seven normal controls are optional and have safe defaults:

| Control | Values and default |
| --- | --- |
| `workflow` | `auto|task|milestone` (`auto`) |
| `review` | `auto|always` (`auto`) |
| `handoff` | `chat|file|both` (`both`) |
| `fix_policy` | `manual|blocking` (`manual`) |
| `task_id` | `<id>` (safely derived when useful) |
| `theme` | `default|foundry` (`default`) |
| `ecosystem` | `auto|off` (`auto`) |

Structured syntax is for expert and compatibility use only:

```text
$kapisch workflow=task review=auto task_id=reconnect
$kapisch mode=review base=origin/main review_target=branch
$kapisch theme=foundry workflow=task
$kapisch workflow=task ecosystem=off
```

Legacy or expert fields such as `mode`, `risk`, `depth`, `focus`, `dispatch`,
and `batching` remain supported through
[request normalization](references/request-normalization.md).

`theme` changes presentation labels only. It never changes controls, canonical
role IDs, profiles, routes, permissions, artifact fields or values, validation,
review depth, gates, or side-effect authority. See
[themes.md](references/themes.md).

## What happens

The LLM/controller interprets natural language, applies explicit controls, and
selects `task` or `milestone` from the conversation and repository context.
`workflow=task` is graph-free; `workflow=milestone` requires an explicitly
approved multi-step plan and durable sequential artifacts. Material scope growth
stops for a user decision rather than reusing narrower approval.
Graph-free means that no execution graph, manifest, durable task nodes, or
sequential execution state is required. It does not mean artifact-free.
Graph-free workflows do not delegate in the current scope. A mandated skill or
plugin blocks for a user choice to promote the work to a durable version-3 graph
or relax the capability constraint; an automatic selection may use the disclosed
native fallback only when the approved outcome is unchanged.

Before reporting approval or readiness, apply the controller
approval-reporting check defined in [review.md](references/review.md).

After a checkout, reset, rebase, merge, branch switch, worktree change, or
other repository update that may change instructions, reread the current skill
and applicable normative references before any later classification, dispatch,
review/final decision, or completion report. See [request
normalization](references/request-normalization.md).

When independent review or final readiness is required, the controller must
still create the canonical pre-dispatch invocation artifact and persist the
returned reviewer result. Without those artifacts, the result is advisory only
and cannot be reported as approve or ready.
Risk is independent of workflow shape. Behavioral tasks receive independent
review. An ordinary reviewed local task may end after independent review when
no delivery boundary applies. High risk strengthens review depth and lenses;
High risk alone does not require final readiness. Final readiness is separate
and required for commit preparation, PR preparation, merge, release, deployment
handoff, an explicit ready-to-commit/merge/release/final request, and every
milestone. “Review my current branch before I open a PR” requests review, not
final readiness. “Check whether this is ready to open a PR” requests final
readiness. The LLM/controller chooses a logical role; Codex resolves configured
profiles and models and reports actual invocation results. If required reviewer
invocation is unavailable, approval is blocked and must not be fabricated.

Independent review has two scopes. An **iteration review** is bound to the
current bounded delta and approves only that delta; use it for a completed
milestone node or approved fix without repeating previously approved work. A
**whole-branch review** is bound to the accumulated merge-base-to-final-head
diff and runs at the final integration or delivery boundary. Only a
whole-branch review can support final readiness; any later implementation delta
makes its approval stale. A normal one-step task needs only its one complete
task review, not two identical reviews. [review.md](references/review.md) owns
the detailed scope, evidence, and fix-round rules.

Shared side-effect boundaries remain explicit: no inferred commit, push,
dependency, destructive, or external-action authority. Durable execution is
sequential only: new manifests use `parallelism=off` and
`max_parallel_agents=1`. Operational waves are unsupported and fail closed;
the retired protocol is archive material only in
[`../../docs/parallel-wave-design.md`](../../docs/parallel-wave-design.md).

Ecosystem capability routing is an optional, sequential capability-delegation
layer: the controller may use an available Codex skill or plugin capability for
one bounded step under `ecosystem=auto`, but KAPISCH remains the sole route
controller and owns normalization, role/risk selection, focused context,
authority, human gates, durable evidence, recovery, independent review, and
final readiness. `ecosystem=off` prevents delegation without disabling ordinary
roles or built-in repository tools. An explicit skill or plugin mention is a
binding capability constraint; an unavailable capability blocks with the safe
setup or selection action, and an automatic selection may fall back to native
KAPISCH execution only when the approved outcome stays achievable without
changing methodology, data boundary, or authority, with the fallback disclosed.
Delegation is supported only by durable version-3 graphs. In a graph-free
workflow, an explicit capability request blocks for a user decision to promote
the work or relax the request; it is never silently delegated or executed
natively. Automatic selection follows the native-fallback rule above.
Delegation never creates a role, executor class, profile, tier, or second
controller, never lowers risk or review depth, cannot launder authority, never
installs or authenticates anything, and never approves or declares readiness.
Every delegation produces mandatory route/context/evidence records even with
`handoff=chat`. See
[ecosystem-routing.md](references/ecosystem-routing.md).

## Project understanding

Architecture questions, maps, documentation-drift checks, onboarding summaries,
and decision-record preparation use the bounded read-only `researcher` route in
[project-understanding.md](references/project-understanding.md). Research
collects attributable repository evidence; it does not edit documentation or
make an architecture decision. Any requested documentation change is a separate
implementation step assigned to the closed-catalog `implementer` role under the
controller's single-writer boundary, with its own scope and verification. The
sole exception is an exact authoritative-document synchronization that satisfies
every mechanic condition in [dispatch.md](references/dispatch.md); it may use
`mechanic`, but it retains the project-understanding review requirement below.
Every versioned project-understanding or architecture-documentation change then
receives independent review, including maps, drift corrections, onboarding
documents, and decision records, whether or not it changes behaviour or a public
contract. Review checks the evidence and recorded output; it does not make or
approve the underlying architecture or product decision. Current source, tests,
repository policy, versioned documentation, and Git history remain authoritative;
optional retrieval tools are aids only and are never required or treated as a
stronger source of truth.

## Contract ownership

This file owns the public interface and shared safety boundaries. Canonical
owners are: LLM interpretation and explicit-control precedence in
[request-normalization.md](references/request-normalization.md); logical-role
selection and Codex runtime dispatch in [role-resolution.md](references/role-resolution.md); risk in
[risk.md](references/risk.md); review/final evidence in
[review.md](references/review.md); durable artifacts and invocation envelopes in
[handoffs.md](references/handoffs.md); sequential schema in
[execution-graph.md](references/execution-graph.md); and recovery in
[resume.md](references/resume.md). Bounded repository understanding and its
evidence/write/review separation are owned by
[project-understanding.md](references/project-understanding.md). Ecosystem
capability selection and delegated-step behavior are owned by
[ecosystem-routing.md](references/ecosystem-routing.md).
Presentation vocabulary and its strict separation from workflow semantics are
owned by [themes.md](references/themes.md).

The validator checks only its implemented structural artifact invariants. It
does not authoritatively establish iteration or whole-branch scope, dependency
coverage, reviewer identity, a complete approval chain, or final readiness.
Markdown contracts and the independent reviewer remain authoritative for
semantic review and final-readiness decisions. Pressure scenarios are
non-normative challenge cases.

## Thin controller for version-4 durable runs

For a version-4 durable run, the controller normally reads only
`04-controller-view.toml`, then dispatches the selected role with its brief,
context, repository binding, and explicitly relevant artifact references. The
specialist reads detailed evidence; the controller does not copy reports,
transcripts, raw tool output, or completed-stage context into later prompts.

Stage outcomes live at `stage-outcomes/<attempt-id>.toml` and bind compact
status, bounded findings, verification references, and retry provenance to
canonical detailed evidence. They never approve review or final readiness.
Reviewers still inspect the actual Git range independently and require the
canonical invocation evidence.

Regenerate a missing or stale controller view only through the explicit
renderer after canonical validation. Block on corrupt projections, missing
canonical evidence, ambiguous active state, or failed validation. Legacy
version-1 through version-3 runs retain their existing resume behavior.

Re-dispatch requires a persisted allowed reason, predecessor attempt, and
budget effect. Confidence-only or generic follow-up re-dispatch is forbidden.
Load transcripts, full run trees, old reports, or debug history only for a
recorded, bounded recovery/debug reason.
