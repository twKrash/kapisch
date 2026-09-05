# Codex agent profile sets

KAPISCH 1.1.0 keeps one six-role logical catalog and offers three installer-time
Codex runtime configurations. Logical executor classes and `model_tier` values
are durable workflow requirements, not concrete model or reasoning-effort
claims. Profile sets resolve the runtime `model` and
`model_reasoning_effort`; they do not change role semantics, workflow selection,
risk, permissions, review independence, final readiness, approval authority,
durable evidence, validator behavior, sequential execution, or ecosystem
routing.

## Routing matrix

| Role | balanced (default) | quality | budget |
| --- | --- | --- | --- |
| architect | `gpt-5.6-sol` / `high` | `gpt-5.6-sol` / `high` | `gpt-5.6-terra` / `high` |
| researcher | `gpt-5.6-terra` / `medium` | `gpt-5.6-terra` / `high` | `gpt-5.6-luna` / `high` |
| implementer | `gpt-5.6-terra` / `medium` | `gpt-5.6-terra` / `medium` | `gpt-5.6-terra` / `low` |
| implementer-lite | `gpt-5.6-luna` / `high` | `gpt-5.6-luna` / `high` | `gpt-5.6-luna` / `high` |
| mechanic | `gpt-5.6-luna` / `low` | `gpt-5.6-luna` / `low` | `gpt-5.6-luna` / `low` |
| reviewer | `gpt-5.6-terra` / `high` | `gpt-5.6-sol` / `high` | `gpt-5.6-terra` / `medium` |

The installer `PROFILE_SET_ROUTING` is the canonical runtime resolver; this
table is its operator-facing rendering. A durable `model_tier=high` remains a
logical high-risk workflow requirement in every set: it does not imply Sol.
Thus quality may resolve the high-tier reviewer to Sol/high, balanced may
resolve it to Terra/high, and budget uses its approved routing above. Actual
model and effort are profile-set/runtime facts, not inferred durable evidence.

Use `balanced` for normal work. Use `quality` for difficult architecture, broad
ambiguity, unusually sensitive work, or when the higher-capability profile is
preferred for architecture, research, and review. Use `budget` for routine work
in well-understood repositories when usage efficiency matters.

These are configurations, not quality or approval claims. A high-risk task under
`budget` remains high-risk and still requires the same independent review. If an
installed model cannot satisfy a required role, KAPISCH fails or escalates under
its existing contracts; it never substitutes self-review or fabricates approval.

## Inspect and install

Inspection is the default and does not create or modify the consumer:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository>
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget
```

Installation is explicit. Omitting `--profile-set` selects `balanced`:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository> --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set balanced --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set quality --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget --install
```

Project scope is the default. For the existing explicit user-scoped surface, use
`--scope user --user-dir <user-home>`.

## Switch a managed installation

First inspect the desired set, then explicitly authorize managed replacement:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget --install --replace-managed
```

Replacement is permitted only when the destination identity, adjacent catalog,
local-state paths and identity, and installed digest all verify. User drift,
unrelated profiles, identity collisions, unreadable state, an unknown profile
set, or a concurrent change blocks the entire catalog. The installer stages all
new bytes and writes a machine-local prepared/committed recovery journal before
publishing any replacement. A caught failure restores the prior profile and
state bytes immediately unless recovery detects a later external edit, which it
preserves. A process-level interruption is recovered before the next setup
inspection or installation: a prepared transaction rolls back, while
a fully committed transaction only finishes cleanup. Commit-time and
postcondition identity checks catch a catalog collision inserted after
preflight; the unrelated file is preserved. Switching back uses the same
inspect-then-explicit-replace sequence.

An exclusive machine-local PID lock prevents a second setup process from
treating an active journal as an interrupted transaction. A stale lock is
removed only after the recorded owner process is no longer alive. Recovery
preserves any destination bytes changed after interruption, even when a
verified rollback backup still exists; the subsequent inspection reports that
user drift instead of overwriting it.

The PID-file protocol does not claim complete safety for simultaneous stale-lock
reclamation or a partial initial lock write. Hardening those concurrent-process
boundaries is deferred to
[issue #23](https://github.com/twKrash/kapisch/issues/23); callers should avoid
running setup concurrently until that issue is resolved.

The current transaction also does not claim hardened containment through every
descendant symlink, junction, or reparse point; preservation of all destination
security metadata; or conditional publication against every external atomic
rename. Those filesystem boundaries are deferred to
[issue #25](https://github.com/twKrash/kapisch/issues/25) (KPR24-001,
KPR24-003, and KPR24-008). Until then, callers must use a trusted ordinary
filesystem tree and avoid concurrent external edits to managed paths.

Recovery is the sole exception to inspect-only non-mutation: it completes the
rollback or cleanup already authorized by the interrupted explicit replacement.
Ordinary inspection does not create a lock file or require write access to the
managed local-state directory. When an interrupted transaction is present,
inspection first acquires the switch lock and performs only that recovery.
The journal lives under `.kapisch/local-state/` and is not a durable workflow
artifact, validator input, telemetry record, or semantic routing source.

New records contain `profile_set`. Verified 1.0.x records without it remain
inspectable as `quality` only when the recorded template digest matches the
shipped quality bytes. They are never silently rewritten.

## Observability boundary

KAPISCH persists only factual invocation data on surfaces that expose it. The
existing final-only workflow metrics may record configured model/effort,
invocations, retries, elapsed time, and token/cache totals when observed;
unavailable values stay `unavailable`. The validator is not a cost estimator or
semantic router. No percentage savings are claimed without paired runtime data.
