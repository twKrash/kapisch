# Changelog

## Unreleased

The 1.2.0 release candidate below is prepared locally but has not been tagged or
published.

## 1.2.0 - 2026-08-31 (release candidate)

Backward-compatible v4 durable controller capability.

- Added immutable stage outcomes and a deterministic, digest-bound controller view.
- Added explicit controller-view rendering and eligible v3-to-v4 migration tools.
- Added bounded controller/role transport contracts and provider-independent benchmark comparison.
- Retained v1-v3 compatibility and existing review/final-readiness semantics.

Benchmark acceptance, independent review, final readiness, tagging, and publication remain pending; this candidate is not released.

## 1.1.0 - 2026-08-28 (release candidate)

Cost-aware Codex agent runtime configuration without workflow-policy changes.

- Added installer-time `balanced`, `quality`, and `budget` profile sets while
  preserving the same six logical roles, identities, instructions, sandbox
  boundaries, and independent reviewer contract.
- Made `balanced` the default for new installations; `quality` preserves the
  1.0.1 quality-first routing baseline and `budget` provides a lower-effort
  configuration for routine work in well-understood repositories.
- Added explicit, managed-only `--replace-managed` switching with identity,
  state, installed-digest, collision, drift, and concurrent-change checks plus
  a machine-local prepared/committed recovery journal for caught failures and
  process interruption.
- Added the selected profile set to new local-state records while keeping
  verified 1.0.x records inspectable as legacy quality configurations without
  rewriting them.
- Reused existing factual workflow-metrics fields for later comparisons. Model,
  effort, invocation, retry, elapsed-time, and token/cache values remain
  unavailable unless the Codex execution surface actually exposes them.
- Added focused routing, instruction-equivalence, install, inspect, switching,
  drift, rollback, legacy-state, user/project scope, portable-package, and
  release-consistency coverage.
- Changed no logical routing, risk classification, permissions, review or final
  requirements, approval authority, durable artifact format, validator
  semantics, sequential execution, or ecosystem routing.

No percentage token or cost reduction is claimed. Runtime savings require
paired acceptance measurements. TOON and other serialization changes remain out
of scope. The candidate is not released until live acceptance, independent
review, final readiness, tagging, and publication are completed separately.

## 1.0.1 - 2026-08-23

Windows compatibility and release-documentation update for issue #21.

- Completed the live release-baseline flow on Windows 11, Codex Desktop, and
  WSL2: exact-SHA marketplace resolution, six matching project profiles,
  durable `$kapisch` execution, independent review, final readiness, and the
  installed public validator returning `[]` with exit code 0.
- Passed the profile-setup and portable-package suites with native Windows
  CPython 3.11. No Windows-only fork or OS-name branch was needed.
- Added a standard-library release-consistency test for the two version fields,
  canonical marketplace source, immutable README commands, changelog, and
  Windows acceptance record.
- Reworked the landing pages and reconciled release, compatibility, acceptance,
  roadmap, and contribution documentation.
- Changed no production workflow, CLI, schema, profile identity, dependency, or
  runtime behavior because the clean acceptance reproduced no KAPISCH defect.

The exact release-SHA rerun, CI result, and remote `v1.0.1` tag verification
passed and are recorded in
[`docs/acceptance-windows-v1.0.1.md`](docs/acceptance-windows-v1.0.1.md).

## 1.0.0 - 2026-08-23

First immutable KAPISCH release, tagged `v1.0.0` at
`d186b90592f65f9861c680d852ee05723f982903`.

- Protected persisted workflow history across resume snapshots: task and graph
  identity are immutable, prior nodes cannot disappear, terminal artifact and
  evidence bindings cannot be rewritten, and graph growth blocks until a
  versioned amendment protocol exists.
- Closed durable policy, node-routing, and workflow-status vocabularies; unknown
  values now fail with structured supported alternatives, and completed
  workflows cannot carry a non-terminal next action or reopen as running when a
  valid compatible predecessor is supplied.
- Hardened validator artifact loading: malformed, non-UTF-8, and unreadable
  manifest, state, and review evidence now fail closed with structured findings.
- Packaged the repository as the Git-backed `kapisch-local` marketplace with a
  single canonical plugin bundle under `plugins/kapisch`.
- Documented separate marketplace configuration and later plugin installation;
  OpenAI public Plugin Directory submission remains out of scope.
- Added presentation-only `default` and original industrial-mystic `foundry`
  themes with a closed vocabulary contract and semantic-firewall coverage.
- Kept theme selection outside durable schemas, validation, routing,
  permissions, review requirements, and side-effect authority.
- Added optional ecosystem capability routing (Change 7): the controller may
  delegate one bounded step to an available Codex skill or plugin capability
  while remaining the sole route controller; the normative contract lives in
  `skills/kapisch/references/ecosystem-routing.md`.
- Added durable delegation evidence (`delegations/00-route.toml` plus per-step
  context and evidence) for version-3 durable runs, with the `ecosystem=auto|off`
  control and fail-closed fallback behavior.
- Added manifest version 3 (`policies.ecosystem_routing`,
  `nodes[].delegation_ids`) while preserving version-1 and version-2 parsing,
  defaults, fixtures, and byte-preserving legacy migration.
- Extended the validator with structural route validation for version-3 durable
  manifests. This automated coverage does not establish external-effect
  recovery safety. Issue #10 implemented the fail-closed boundary: delegated
  `external-write` and `destructive` routes are rejected even with explicit
  authority. Enabling those effects still requires a future reconciliation
  protocol; step lifecycle and graph-free delegation remain deferred.
- Added native-Windows-safe optional profile setup and fail-closed catalog
  preflight without overwriting existing profiles.
- Added the installed `kapisch-validate` command with bundled contract
  discovery while retaining the source-checkout compatibility wrapper.

This release is bound to the immutable commit tagged `v1.0.0`, which passed the
clean Unix-like runtime acceptance recorded in
[`docs/acceptance-runtime.md`](docs/acceptance-runtime.md) (installed
`kapisch-validate` returned `[]` with exit code 0). Windows acceptance is
recorded separately in
[`docs/acceptance-windows-v1.0.1.md`](docs/acceptance-windows-v1.0.1.md).

## 0.1.0 - 2026-07-21

- Initial extraction of the KAPISCH Codex plugin.
- Added portable role contracts, optional Codex agent templates, and the
  standard-library-only durable-evidence validator.
- Added automated package-level clean-copy, profile-lifecycle, and legacy
  migration coverage plus documented collision, dogfood, and rollback paths.
  It did not perform a live Codex installation or runtime acceptance.
