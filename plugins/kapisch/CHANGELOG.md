# Changelog

## Unreleased

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
  context and evidence) for graph-free and version-3 durable runs, with the
  `ecosystem=auto|off` control and fail-closed fallback behavior.
- Added manifest version 3 (`policies.ecosystem_routing`,
  `nodes[].delegation_ids`) while preserving version-1 and version-2 parsing,
  defaults, fixtures, and byte-preserving legacy migration.
- Extended the validator with `--scope delegations` and automatic route
  validation for version-3 durable manifests, keeping Python structural,
  deterministic, and read-only.

## 0.1.0 - 2026-07-21

- Initial extraction of the KAPISCH Codex plugin.
- Added portable role contracts, optional Codex agent templates, and the
  standard-library-only durable-evidence validator.
- Added executable clean-install, profile lifecycle, and legacy migration
  acceptance coverage plus documented collision, dogfood, and rollback paths.
