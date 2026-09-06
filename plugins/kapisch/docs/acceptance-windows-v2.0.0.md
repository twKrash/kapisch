# Windows acceptance record — 2.0.0

**Status: PENDING.** This is the release-candidate acceptance record. Native
Windows automated CI is required; a separate native-PowerShell live acceptance
run is optional.

- Release: `2.0.0`; intended immutable tag: `v2.0.0`.
- Tested runtime SHA: `b36c5303f2732b136a9764b086e3a998054bcf80`.
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

The clean Task 4 runtime tree completed root discovery (16 tests), plugin
validation discovery (370 tests), and the portable-package check (370 tests).
This is 756 passed, 0 platform-capability skips. The validator help command also
exited 0. automated evidence is bound to this exact runtime tree.

## Native Windows CI expectation

The `windows-profile-setup` GitHub Actions job on `windows-latest`, Python 3.11,
is required before merge or release. It has not been observed for this candidate,
so this record does not claim native Windows success.

## Optional live acceptance

A separate native-PowerShell live acceptance run is optional. If performed, it
must be recorded as observed evidence and does not replace the required CI job.

## Release boundary

Review, final readiness, merge, authorized release preparation, and remote tag
verification remain pending. Do not create, push, publish, or verify the tag
while preparing this candidate.
