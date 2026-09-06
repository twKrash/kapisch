# Codex agent profile sets

KAPISCH provides one six-role logical catalog with `balanced`, `quality`, and
`budget` installer-time runtime configurations. Profile sets change runtime
model and reasoning effort only; they do not change role semantics, durable
model tiers, workflow authority, permissions, independent review, final
readiness, validator behavior, or routing policy.

## Routing matrix

| Role | balanced (default) | quality | budget |
| --- | --- | --- | --- |
| architect | `gpt-5.6-sol` / `high` | `gpt-5.6-sol` / `high` | `gpt-5.6-terra` / `high` |
| researcher | `gpt-5.6-terra` / `medium` | `gpt-5.6-terra` / `high` | `gpt-5.6-luna` / `high` |
| implementer | `gpt-5.6-terra` / `medium` | `gpt-5.6-terra` / `medium` | `gpt-5.6-terra` / `low` |
| implementer-lite | `gpt-5.6-luna` / `high` | `gpt-5.6-luna` / `high` | `gpt-5.6-luna` / `high` |
| mechanic | `gpt-5.6-luna` / `low` | `gpt-5.6-luna` / `low` | `gpt-5.6-luna` / `low` |
| reviewer | `gpt-5.6-terra` / `high` | `gpt-5.6-sol` / `high` | `gpt-5.6-terra` / `medium` |

## Inspect and install

Inspection is current-state diagnosis and does not create or modify the
consumer:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository>
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget
```

Install only after inspection:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository> --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget --install
```

## Update a managed installation

Same-set and changed-routing/profile-set updates are detected. They require an
explicit replacement after inspection:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget --install --replace-managed
```

Replacement refuses user drift, unrelated identities, collisions, unreadable or
missing state, and concurrent changes. A missing-plus-replacement catalog is
refused as a whole; it is not partially installed. Current schema-3 journals
recover only an explicitly authorized interrupted replacement and preserve later
external edits.

Unsupported legacy profile state and journal schemas 1–2 have a generic
`unsupported legacy` outcome: they are rejected without mutation, migration, or
recovery. Follow the [manual cleanup procedure](compatibility.md#legacy-profile-cleanup),
then inspect and install a current catalog.

## Observability boundary

KAPISCH persists only factual invocation data on surfaces that expose it. The
validator is not a cost estimator or semantic router, and no percentage savings
are claimed without paired runtime data.
