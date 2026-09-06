# Windows acceptance record — 1.2.2

**Status: PENDING.** This file is the release-candidate acceptance template, not
evidence that the 1.2.2 tag, release, or live runtime acceptance exists.

- Release: `1.2.2`; intended immutable tag: `v1.2.2`.
- Tested runtime SHA: `7ccc2b6a4987cac416f1566debc47e45fc1c2b14`.
- Final release SHA: pending review, merge, and authorized release preparation.
- Remote tag verification: pending; do not create or publish the tag during candidate preparation.
- Supported release-blocking Windows surface: Windows 11, Codex Desktop/CLI, and WSL2.
- Native no-WSL live support: not claimed.

## Required automated evidence

Run native Windows Python 3.11 profile/setup tests and the portable-package
suite, plus the normal Linux/root release gates. Record exact versions, commands,
counts, and outputs. Linux results do not substitute for Windows execution.

The profile checks must cover balanced default, explicit balanced/quality/budget
selection, all six identities and routing pairs, project and user scope,
inspect-only behavior, explicit install, managed switching, drift and collision
refusal, rollback after injected failure, selected-set state/digests, verified
legacy 1.0.1 replacement only with `--install --replace-managed`, and Windows
path handling.

### Current candidate evidence — 2026-09-06

The automated evidence is bound to this exact runtime tree:
`7ccc2b6a4987cac416f1566debc47e45fc1c2b14`. It is not exact-release-SHA or
tag evidence. The evidence-record update does not change the tested runtime
tree.

- Linux root suite: 10 tests passed.
- Linux validator suite: 276 tests passed.
- Linux portable package: 276 tests passed; `portable-package=passed`.
- Linux focused profile/setup suite: 46 tests passed.
- Validator and profile setup help smokes passed; `compileall` and
  `git diff --check` passed.
- Native Windows GitHub Actions CPython 3.11.9 focused profile/setup baseline:
  46 tests passed; hotfix-specific coverage remains pending for this candidate.
- Native Windows GitHub Actions CPython 3.11.9 portable-package baseline:
  272 passed, 4 platform-capability skips; `portable-package=passed`.
  Hotfix-specific coverage remains pending for this candidate.

Known limitation: the PID-file lock does not fully serialize simultaneous
stale-lock reclamation and a partial initial lock write can require manual local
cleanup. This concurrency hardening is explicitly deferred to
[issue #23](https://github.com/twKrash/kapisch/issues/23); 1.2.2 makes no claim
for concurrent setup invocations across those boundaries.

## Required live acceptance

Use a new authenticated WSL `CODEX_HOME` and clean consumer repositories pinned
to the exact candidate SHA. Install and inspect `quality` in one consumer and
`balanced` in an equivalent consumer. Run the same bounded KAPISCH task where
practical, followed by configured independent review, final readiness, and the
installed public validator without `--contract-dir`.

Record only observed role invocations, resolved profiles/models/efforts when the
runtime exposes them, task results, review decisions, validator results, retries,
elapsed time, and token/cache usage when exposed. Unavailable values remain
unavailable. Correctness and review quality must remain intact. Do not claim a
percentage saving without sufficient comparable runtime token data.

## Release boundary

After automated and live evidence, independent whole-branch review, and separate
final readiness are current, an authorized maintainer may commit, tag, publish,
and verify the immutable release in a separate explicitly authorized action.
Until then, this document remains pending acceptance.
