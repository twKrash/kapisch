---
name: KAPISCH
description: >-
  Use when a repository task needs repeatable planning, implementation,
  independent review, final-readiness, or narrow mechanical cleanup.
---

# KAPISCH Workflow

## Durable artifact validation

For read-only structural validation of a sequential durable TOML artifact tree,
run `python scripts/validate_kapisch.py
--contract-dir skills/kapisch --task-dir <task-dir>`. See
[`scripts/README.md`](scripts/README.md). The validator does not dispatch,
repair, schedule, or approve work.

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
```

The five normal controls are optional and have safe defaults:

| Control | Values and default |
| --- | --- |
| `workflow` | `auto|task|milestone` (`auto`) |
| `review` | `auto|always` (`auto`) |
| `handoff` | `chat|file|both` (`both`) |
| `fix_policy` | `manual|blocking` (`manual`) |
| `task_id` | `<id>` (safely derived when useful) |

Structured syntax is for expert and compatibility use only:

```text
$KAPISCH workflow=task review=auto task_id=reconnect
$KAPISCH mode=review base=origin/main review_target=branch
```

Legacy or expert fields such as `mode`, `risk`, `depth`, `focus`, `dispatch`,
and `batching` remain supported through
[request normalization](references/request-normalization.md).

## What happens

The LLM/controller interprets natural language, applies explicit controls, and
selects `task` or `milestone` from the conversation and repository context.
`workflow=task` is graph-free; `workflow=milestone` requires an explicitly
approved multi-step plan and durable sequential artifacts. Material scope growth
stops for a user decision rather than reusing narrower approval.
Graph-free means that no execution graph, manifest, durable task nodes, or
sequential execution state is required. It does not mean artifact-free.

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
[`../../docs/parallel-wave-design.md`](../../../../../docs/parallel-wave-design.md).

## Contract ownership

This file owns the public interface and shared safety boundaries. Canonical
owners are: LLM interpretation and explicit-control precedence in
[request-normalization.md](references/request-normalization.md); logical-role
selection and Codex runtime dispatch in [role-resolution.md](references/role-resolution.md); risk in
[risk.md](references/risk.md); review/final evidence in
[review.md](references/review.md); durable artifacts and invocation envelopes in
[handoffs.md](references/handoffs.md); sequential schema in
[execution-graph.md](references/execution-graph.md); and recovery in
[resume.md](references/resume.md).

The validator checks only its implemented structural artifact invariants. It
does not authoritatively establish iteration or whole-branch scope, dependency
coverage, reviewer identity, a complete approval chain, or final readiness.
Markdown contracts and the independent reviewer remain authoritative for
semantic review and final-readiness decisions. Pressure scenarios are
non-normative challenge cases.
