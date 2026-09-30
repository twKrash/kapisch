# Risk policy

Risk is independent of implementation complexity. Classify impact from repository evidence and stated consequences; do not lower risk because a task looks easy, a cheaper logical tier is selected, or a worker proposes a narrower label. Use the role/tier floors in [dispatch policy](dispatch.md).

- **low**: no production behaviour, public-contract, persistent-state, permission, privacy, or external-side-effect change.
- **medium**: scoped production behaviour, ordinary bug fixes or refactors, multi-file work, or bounded compatibility impact.
- **high**: authentication, authorization, permissions, tenant/household/owner/user isolation, privacy, signed context, migrations, persistent data, concurrency, locking, retries/idempotency, destructive operations, external side effects, public compatibility, recovery, or rollback. Any high-risk trigger makes the work high risk.

An agent may raise risk when evidence reveals a trigger. Lowering a high classification requires concrete repository evidence that the trigger does not apply; convenience, scope wording, a specialist capability, or a cheaper tier is not evidence. High-risk work requires the role/tier floor and deep independent review. Review depth may increase with risk; risk alone does not invent a final-readiness requirement. Unknown impact that could change authority or safety remains unresolved and blocks the affected gate.

## Review depth

- **quick**: bind scope, inspect every changed hunk and directly affected test, trace changed public or safety boundaries, and run focused verification. Valid only when no production behaviour, public contract, persistent state, permission, privacy, or external side effect changes.
- **standard**: add directly affected callers and consumers, contract and compatibility edges, relevant negative/error paths, and regression-test adequacy.
- **deep**: add every applicable review lens, adversarial negative paths, cross-boundary invariants, and applicable failure, cancellation, pause/resume, persistence, rollback, recovery, migration, concurrency, permission, privacy, audit, and operational behaviour. Produce the applicable evidence matrices in the review contract.

Depth changes inspection breadth, never correctness or severity. Every depth blocks a discovered P0/P1 defect. Default depth follows risk: low → quick, medium → standard, high → deep.

## Review lenses

Use all lenses applicable to changed behavior; explicit additions may expand coverage but cannot suppress an obvious P0/P1 issue or a lens required by a high-risk trigger. Canonical order: `behavior`, `security`, `permissions`, `privacy`, `tenant-isolation`, `concurrency`, `data`, `migration`, `api`, `compatibility`, `tests`, `operations`, `audit`, `recovery`. Record why each selected lens applies.

| Change surface | Applicable lenses |
| --- | --- |
| Authentication or signed context | security, permissions, api, tests, audit |
| Tenant/household/owner/user scope | security, permissions, privacy, tenant-isolation, data, tests |
| Database or migration | data, migration, concurrency, recovery, operations, tests |
| Async, scheduler, or lifecycle | behavior, concurrency, recovery, operations, tests |
| Public API or schema | api, behavior, compatibility, tests |
| External side effect | behavior, permissions, data, audit, recovery, operations, tests |
| Production refactor | behavior, compatibility, tests |
| Mechanical-only change | tests and focused final-readiness checks |

A capability or delegation never lowers risk, depth, required lenses, or regression coverage. High-risk work must retain independent review regardless of who performed a bounded substep.
