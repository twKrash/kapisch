# Clean-runtime acceptance record — release 1.0.0

**Status: COMPLETE for Unix-like at `v1.0.0`.** Clean Unix-like Codex runtime
acceptance passed at the release commit (tag `v1.0.0`). Native-Windows Codex
runtime acceptance is **deferred to [issue #21](https://github.com/twKrash/kapisch/issues/21)**
(owns Windows Desktop + WSL acceptance, any Windows fixes, and patch release
`v1.0.1`). The immutable `v1.0.0` tag remains at the accepted commit and is
not moved.

Older intermediate SHAs (`f92b996`, `b614425`, `c519ced`, `09a29f2`) appear
below only as historical/intermediate evidence; they are **not** the accepted
release candidate.

## Accepted revision and release tag

- Version: **1.0.0** (both canonical fields: `pyproject.toml` and
  `.codex-plugin/plugin.json`).
- Immutable tag: **`v1.0.0`** — annotated, pushed, and verified to resolve
  exactly to the accepted commit below.
- **RELEASE_SHA (accepted):** `d186b90592f65f9861c680d852ee05723f982903`
- Intermediate artifact-verification revision (historical only):
  `b61442564d82aef1fd21f6b7a83071829fac8858`

## Environment and Codex surface

- Date/time: 2026-08-23
- OS/arch: Linux 7.1.8-arch1-3, x86_64
- Codex surface/version: authenticated standalone `codex-cli 0.148.0`
  (ChatGPT OAuth, logged in inside a fresh home)
- Python version: 3.11.16

### Native Windows surface — DEFERRED to issue #21

Native-Windows Codex runtime acceptance is **not** part of this record. By
maintainer decision it is tracked in
[issue #21](https://github.com/twKrash/kapisch/issues/21), which owns Windows
Desktop + WSL acceptance, any demonstrated Windows fixes, and immutable patch
release `v1.0.1`. Structural Windows portability (Windows CI portable-package
gate) is green but is not Codex runtime acceptance.

## Clean Unix-like acceptance — PASSED (2026-08-23)

Run from a **brand-new authenticated `CODEX_HOME`** and a **separate fresh
consumer Git repository**, with no KAPISCH source checkout, marketplace cache,
plugin, skill, or profile pre-existing in either. Authentication used `codex
login` inside the fresh home (ChatGPT OAuth); no `auth.json` was copied.

### Marketplace and plugin

```text
# Marketplace at the exact accepted SHA (never main)
codex plugin marketplace add twKrash/kapisch --ref d186b90592f65f9861c680d852ee05723f982903
# -> Added marketplace `kapisch-local` from .../kapisch.git#d186b90...

codex plugin add kapisch@kapisch-local
# -> Added plugin `kapisch`; version 1.0.0, installed, enabled
```

Marketplace resolved to exactly the accepted SHA; plugin installed/enabled at
`1.0.0`. All six agent profiles were installed into the consumer with matching
hashes (no collision/drift); each parses with `name`, `description`, and
`developer_instructions`.

### Live `$kapisch` invocation (durable end-to-end)

```text
codex exec --json --ephemeral --sandbox workspace-write -C $CONSUMER \
  'Use $kapisch with DURABLE end-to-end execution for this acceptance task: add a short Installation section to README.md and run it through the durable sequential execution graph, writing the canonical durable artifacts (02-execution-graph.toml and 03-state.toml) under .kapisch/runs/<task_id>/. Do not commit, push, publish, authenticate external services, or perform external writes. Report the selected KAPISCH role, exact task ID, durable artifact directory, and every artifact file written.'
```

- Selected role: `implementer` (pre-release run) / `mechanic` (RELEASE_SHA run).
- Durable artifacts written under `.kapisch/runs/<task_id>/`: `01-plan.md`,
  `02-execution-graph.toml`, `03-state.toml`, `tasks/T01-*`, `tasks/R01-*`,
  `tasks/F01-*`, `reviews/round-0/*`, `reviews/final/*`.
- Final status: `complete`.

### Reviewer result

- The independent iteration reviewer returned **`approve`**; the separate
  final-readiness reviewer returned **`ready`** (lifecycle `completed`).
- Canonical invocation evidence:
  `.kapisch/runs/<task_id>/reviews/round-0/00-review-invocation.toml` and
  `reviews/final/00-final-invocation.toml`.

> **Open item (not resolved in this record) — see issue #21 / re-review:**
> The decision-bearing reviewer runs above were produced inside a
> **`workspace-write`-parent** durable run. A **read-only-parent**
> decision-bearing `kapisch-reviewer` run is required to prove the shipped
> profile's read-only boundary (parent runtime sandbox overrides are reapplied
> to spawned agents per the official subagent docs). On this `codex-cli
> 0.148.0` host the read-only-parent dispatch returned
> **`resolution-failure`** (the named profile did not resolve under read-only;
> the agent correctly refused a generic substitute). A decision-bearing
> read-only-parent run is being obtained on another surface.

### Public validator

The validation package was installed (pip wheel install, `kapisch-validation
1.0.0`) and the **public console command** was run against a valid durable task
directory:

```text
$ kapisch-validate --task-dir <valid-durable-task-dir> --format json
[]
$ echo $?
0
```

Output `[]` (no findings), exit `0`, using the public `kapisch-validate`
`[project.scripts]` entry point with bundled-contract discovery (override
`--contract-dir`). This is the installed public interface required by #11 (not
the `scripts/validate_kapisch.py` compatibility wrapper).

## Release sequence

- Version and changelog: `1.0.0` in both canonical fields; changelog has a dated
  `1.0.0` release and a fresh empty `Unreleased` section; README released path
  uses immutable `v1.0.0`.
- Tests: Linux marketplace 7/7; Linux portable-package 245/245; Windows CI
  portable-package gate green; `git diff --check` clean.
- Tag: `v1.0.0` annotated and pushed; remote tag peels exactly to the accepted
  RELEASE_SHA `d186b90…`.

## Known limitations and exclusions

- OpenAI public Plugin Directory submission is out of scope; distribution uses
  the Git-backed `kapisch-local` marketplace.
- Delegated `external-write` and `destructive` effects fail closed; no
  reconciliation protocol or exactly-once guarantee is claimed.
- Native-Windows Codex runtime acceptance is **deferred to issue #21**; this
  release's runtime acceptance is Unix-like only.
- The read-only-parent decision-bearing reviewer claim is open (see above).
