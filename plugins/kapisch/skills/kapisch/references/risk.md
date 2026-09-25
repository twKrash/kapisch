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

The controller resolves risk, depth, and active lenses before dispatch. The
reviewer records those values and may raise risk or depth when mandatory
discovery reveals a concrete trigger; record that trigger. The existing rule for
lowering automatic risk still applies. Depth changes breadth, not severity or
approval correctness: every depth blocks a discovered P0/P1 defect.

## Depth execution

### Quick

Bind scope; inspect every changed hunk; inventory changed files and symbols;
inspect directly affected tests; trace changed public contracts or safety
boundaries when present; and run focused verification. Quick is valid only when
there is no production behavior, public contract, persistent state, permission,
privacy, or external-side-effect change.

### Standard

Standard adds to quick: trace directly affected callers and consumers, contract
and compatibility edges, relevant negative and error paths, and regression-test
adequacy for changed behavior.

### Deep

Deep adds to standard: apply every active lens; inspect adversarial negative
paths and cross-boundary invariants; cover applicable failure, cancellation,
resume, persistence, rollback, recovery, migration, concurrency, permission,
privacy, audit, and operational behavior; and produce required Behavioral
branch and Invariant evidence matrices under the review contract.

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

Ecosystem capability presence never lowers risk. Delegating a bounded substep to
a skill or plugin capability does not change the classification: external side
effects, permissions, retries/idempotency, and recovery remain high-risk
triggers regardless of which capability performs the work, and review depth,
required lenses, and regression coverage are preserved. Additional task detail
or a specialist capability never downgrades risk. See
[ecosystem-routing.md](ecosystem-routing.md).
