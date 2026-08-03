# Risk, depth, and review lenses

`risk=auto` is the default. Classify before selecting the effective review path:

- **low**: no production behaviour, public contract, persistent-state, permission,
  privacy, or external-side-effect change (for example formatting or verified
  mechanical renames only).
- **medium**: scoped production behaviour, ordinary bug fixes/refactors, multi-file
  work, or bounded compatibility impact.
- **high**: authentication, authorization, permissions, tenant/household/owner/user
  isolation, privacy, signed context, migrations, persistent data, concurrency,
  locking, retries/idempotency, destructive operations, external side effects,
  public compatibility, recovery, or rollback. Any trigger makes risk high.

An agent may increase automatic risk. It may decrease it only by recording a
concrete reason in the handoff. Depth defaults to `quick` for low, `standard` for
medium, and `deep` for high. Depth changes inspection breadth, never correctness:
a quick review still blocks discovered P0/P1 defects.

Supported lenses, in canonical recording and display order, are: `behavior`,
`security`, `permissions`, `privacy`, `tenant-isolation`, `concurrency`, `data`,
`migration`, `api`, `compatibility`, `tests`, `operations`, `audit`, `recovery`.
State why each active lens applies.

`focus=auto` derives only the relevant automatic lenses. An explicit-only focus
such as `focus=security,permissions` activates only its named lenses. A mixed
focus such as `focus=auto,concurrency` is the deduplicated union of derived
automatic lenses and every explicit lens: explicit lenses add coverage and never
remove auto-selected coverage. Record and display every resolved set once in the
canonical order above. A manual focus cannot suppress an obvious P0/P1 outside it.

| Change | Auto lenses |
| --- | --- |
| Auth or signed context | security, permissions, api, tests, audit |
| Tenant/household/owner/user scope | security, permissions, privacy, tenant-isolation, data, tests |
| Database or migration | data, migration, concurrency, recovery, operations, tests |
| Async, scheduler, or lifecycle | behavior, concurrency, recovery, operations, tests |
| Public API or schema | api, behavior, compatibility, tests |
| Reminder, tool call, or external side effect | behavior, permissions, data, audit, recovery, operations, tests |
| Production refactor | behavior, compatibility, tests |
| Mechanical only | tests and quick final-readiness checks |
