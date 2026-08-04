# Request normalization

The LLM/controller owns interpretation of natural-language repository requests.
Repository Python has no request parser, routing API, intent schema, or rule
engine.

Explicit controls such as `workflow=task`, `review=always`, `mode=review`,
`risk=high`, `theme=foundry`, and `ecosystem=off` constrain the
LLM/controller's interpretation.
When controls and prose conflict, explicit controls take precedence; explicit
prose constraints, active durable context, repository evidence, and safe
defaults follow. Material ambiguity about scope, authority, active task, public
behavior, security, or an approved plan stops for a user decision.

`theme` is the sole presentation-only control. It follows the selection and
fallback rules in [themes.md](themes.md) and is removed from semantic
normalization before workflow shape, role, risk, review, approval, or authority
is decided. It is not a durable manifest policy. Thus two otherwise identical
requests with different themes normalize to the same workflow semantics.

Naming a skill or plugin is explicit capability wording: a user who mandates a
particular methodology or integration (for example "use the X plugin to
inspect this") states a binding capability constraint, not a suggestion.
`ecosystem=auto|off` is an explicit control with default `auto`. An explicit
mention overrides `ecosystem=auto`; under `ecosystem=off` a mandated capability
cannot be delegated, and the controller reports the conflict and a safe setup
or selection action instead of ignoring the mention or delegating anyway. The
selection, fallback, and fail-closed rules for delegated steps are owned by
[ecosystem-routing.md](ecosystem-routing.md).

The LLM/controller selects `task` or `milestone`, logical roles, risk, review
needs, and whether a request is read-only. It records only the durable facts
needed by the artifact contract. `workflow=task` is graph-free; a milestone uses
approved, sequential durable artifacts. Operational waves remain unsupported.

The validator parses those persisted TOML artifacts and validates their schema,
paths, transitions, and factual consistency. It does not re-derive or second
guess the conversational decision.

## Repository instruction freshness

After checkout, reset, rebase, merge, branch switch, worktree change, or another
repository update that may change repository instructions, the controller must
reread the current KAPISCH `SKILL.md` and the normative references needed
for the selected workflow before any later classification, dispatch, review/final
decision, or completion report.

Instructions loaded before the repository change are stale context and must not
be used as authority for later classification, dispatch, review, final
readiness, artifact requirements, or completion reporting.
