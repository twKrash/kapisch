# Task-local knowledge discipline

Use one readable ledger at
`.kapisch/runs/<task_id>/knowledge/records.toml`:

```toml
version = 1

[[records]]
id = "D-001"
kind = "decision"
scope = "task:example"
authority = "binding"
status = "verified"
statement = "Durable artifacts and Git evidence are authoritative."
source = "01-plan.md"
verified_at_revision = "abc1234"
applies_when = ["durable execution is active"]
```

Kinds are `fact`, `decision`, `tradeoff`, `hint`, `shortcut`, `pitfall`, and
`question`; authority is `binding`, `advisory`, or `informational`; lifecycle is
`candidate`, `verified`, `promoted`, `rejected`, `superseded`, or `expired`.
Records have stable IDs, scope, concise statement, source, verified revision
when applicable, applicability conditions, and supersession/expiry information
when applicable. Supported scopes include `task:<id>`, `milestone:<id>`,
`module:<name>`, `repository`, and `workflow:kapisch`.

The version-1 ledger is a closed schema. Its root fields are `version` (required
integer `1`), `records` (required array), and optional reverse-DNS `extensions`.
Each record preserves append history and has these required fields:

| Field | Type/values |
| --- | --- |
| `id` | non-empty unique string |
| `kind` | `fact`, `decision`, `tradeoff`, `hint`, `shortcut`, `pitfall`, or `question` |
| `scope` | `task:<id>`, `milestone:<id>`, `module:<name>`, `repository`, or `workflow:kapisch` |
| `authority` | `binding`, `advisory`, or `informational` |
| `status` | `candidate`, `verified`, `promoted`, `rejected`, `superseded`, or `expired` |
| `statement` | non-empty string |
| `source` | non-empty string |
| `applies_when` | array of strings; duplicate values are removed and the remainder is sorted lexically |

Optional record fields are `verified_at_revision`, `superseded_by`,
`expires_at_revision`, `preconditions`, `forbidden_cases`,
`required_verification`, `fallback_executor`, `fallback_behavior`, and
reverse-DNS `extensions`. All scalar fields are non-empty strings and the three
condition/verification fields are arrays of strings; their declared order is
preserved. `superseded` requires `superseded_by`, `expired` requires
`expires_at_revision`, and `shortcut` requires non-empty `preconditions`,
`forbidden_cases`, `required_verification`, plus `fallback_executor` or
`fallback_behavior`. Unknown fields, unsupported values, duplicate IDs, invalid
extensions, and missing conditional fields are rejected.

Writers must use the pure renderer
`kapisch_validation.knowledge.render_knowledge_records(raw)` and persist its
returned UTF-8 bytes. The renderer emits canonical TOML with root order
`version`, `records`, `extensions`; record order is append order, and no
selection, history, or repair behavior is performed by the validator.

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
