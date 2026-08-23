# Changelog

## Unreleased

No pending changes.

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

The exact release-SHA rerun, CI result, and remote `v1.0.1` tag verification are
publication gates and are recorded in
[`docs/acceptance-windows-v1.0.1.md`](docs/acceptance-windows-v1.0.1.md).

## 1.0.0 - 2026-08-23

First immutable KAPISCH release, tagged `v1.0.0` at
`d186b90592f65f9861c680d852ee05723f982903`.

- Published the canonical `kapisch-local` marketplace and plugin bundle.
- Added the standard-library validator, durable version-3 evidence, optional
  profile setup, presentation themes, and fail-closed read-only ecosystem
  routing.
- Completed clean Unix-like marketplace, plugin, reviewer, `$kapisch`, and
  installed-validator acceptance. See
  [`docs/acceptance-runtime.md`](docs/acceptance-runtime.md).

## 0.1.0 - 2026-07-21

- Extracted the portable KAPISCH skill, role contracts, validator, fixtures,
  tests, and compatibility documentation.
