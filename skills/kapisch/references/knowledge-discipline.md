# Task-local knowledge discipline

Use one readable ledger at
`.kapisch/runs/<task_id>/knowledge/records.yaml`:

```yaml
version: 1
records:
  - id: D-001
    kind: decision
    scope: task:example
    authority: binding
    status: verified
    statement: Durable artifacts and Git evidence are authoritative.
    source: 01-plan.md
    verified_at_revision: abc1234
    applies_when: [durable execution is active]
```

Kinds are `fact`, `decision`, `tradeoff`, `hint`, `shortcut`, `pitfall`, and
`question`; authority is `binding`, `advisory`, or `informational`; lifecycle is
`candidate`, `verified`, `promoted`, `rejected`, `superseded`, or `expired`.
Records have stable IDs, scope, concise statement, source, verified revision
when applicable, applicability conditions, and supersession/expiry information
when applicable. Supported scopes include `task:<id>`, `milestone:<id>`,
`module:<name>`, `repository`, and `workflow:kapisch`.

Implementers may propose candidates. Only `verified` or `promoted` records are
eligible for selection. Context selection is deterministic, in this order:
explicit node `context_refs`; applicable scoped binding records; verified
applicable pitfalls and shortcuts; then relevant interfaces needed to establish
the task boundary. Explicit records remain in reference order. Candidates,
rejected, expired, superseded, and unrelated records are excluded. Candidates
never enter later contexts automatically, and promotion to repository
documentation requires a separate approved change.

A stale binding record requires conflict resolution against current repository
evidence before it can guide execution; unresolved conflict blocks rather than
silently selecting a replacement. A stale advisory record is excluded until it
is reverified. Advisory hints and shortcuts never override user instructions,
repository policy, approved plans, binding records, invariants, review findings,
or current evidence. Shortcuts additionally state preconditions, forbidden
cases, required verification, and fallback executor or behaviour; unmet
preconditions use the normal flow or block.
