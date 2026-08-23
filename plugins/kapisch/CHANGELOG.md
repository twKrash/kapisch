# Changelog

## 1.0.0 - 2026-08-23

The first immutable, runtime-accepted KAPISCH release (tag `v1.0.0`).

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
[`plugins/kapisch/docs/acceptance-runtime.md`](plugins/kapisch/docs/acceptance-runtime.md)
(installed `kapisch-validate` `[]`/exit 0). Native-Windows runtime acceptance is
tracked in a separate issue.

## Unreleased

(No pending changes yet.)

## 0.1.0 - 2026-07-21

- Initial extraction of the KAPISCH Codex plugin.
- Added portable role contracts, optional Codex agent templates, and the
  standard-library-only durable-evidence validator.
- Added automated package-level clean-copy, profile-lifecycle, and legacy
  migration coverage plus documented collision, dogfood, and rollback paths.
  It did not perform a live Codex installation or runtime acceptance.
