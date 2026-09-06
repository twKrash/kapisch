# Windows acceptance record — 2.0.0

**Status: PASS for automated CI.** This is the release-candidate acceptance
record. A separate native-PowerShell live acceptance run is optional.

- Release: `2.0.0`; intended immutable tag: `v2.0.0`.
- Tested runtime SHA: `f4204b800e1aca7f0354ebc496561c8181610768`.
- CI workflow: `34055905476`.
- Linux CI: `PASS`.
- Windows `windows-profile-setup`: `PASS`.
- Final release SHA: pending review, merge, and authorized release preparation.
- Remote tag verification: pending; do not create or publish the tag during candidate preparation.

## Compatibility boundary under test

Profile-state schema 1 and switch-journal schema 3 are current independent of
plugin semver. Legacy profiles and journal schemas 1–2 must be diagnosed and
rejected without mutation; current explicit replacement and schema-3 recovery
remain covered.

## Required automated evidence

Native Windows CI on `windows-latest` with Python 3.11 must run from the plugin
directory:

```text
python -m unittest discover -s tests/kapisch_validation -p test_setup_profile.py
python scripts/test_portable_package.py
```

## Current candidate evidence — 2026-09-06

Tested runtime SHA: `f4204b800e1aca7f0354ebc496561c8181610768`

CI workflow: `34055905476`

The tested runtime tree completed root discovery (17 tests), plugin validation
discovery (374 tests), and the portable-package check (374 tests). This is 765
passed, 0 platform-capability skips. The validator help command also exited 0.

## Native Windows CI result

The `windows-profile-setup` GitHub Actions job on `windows-latest`, Python 3.11,
completed successfully for this candidate. Linux CI also passed.

## Optional live acceptance

A separate native-PowerShell live acceptance run is optional. If performed, it
must be recorded as observed evidence and does not replace the required CI job.

## Release boundary

Review, final readiness, merge, authorized release preparation, and remote tag
verification remain pending. Do not create, push, publish, or verify the tag
while preparing this candidate.
