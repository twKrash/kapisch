# Windows acceptance record — 2.1.0

**Status: PASS for automated CI.** This is release-candidate evidence; no live
native-PowerShell marketplace flow is claimed.

- Release: `2.1.0`; intended immutable tag: `v2.1.0`.
- Tested runtime SHA: `804957019eaee45116201202d463dc9f7345b312`.
- CI workflow: `34728390116` (`pull_request`).
- Linux `ci`: `PASS`.
- Windows `windows-profile-setup`: `PASS`.
- Final release SHA: pending review, merge, and authorized release preparation.
- Remote tag verification: pending; do not create or publish the tag during candidate preparation.

## Deterministic boundary under test

Portable KAPISCH-owned outputs use canonical UTF-8 bytes, stable field and
semantic-set ordering, and relative POSIX paths. Compatible historical readers
remain tolerant. Reports and verification attachments retain exact bytes for
digesting, while profile ownership and recovery state retain truthful
machine-local paths and process data. The full operator contract is in
[deterministic-artifacts.md](deterministic-artifacts.md).

## Required automated evidence

The workflow ran on Ubuntu and on `windows-latest` with Python 3.11. Native
Windows executed:

```text
python -m unittest discover -s tests/kapisch_validation -p test_setup_profile.py
$env:PYTHONHASHSEED='1'; python -m unittest tests.kapisch_validation.test_deterministic_acceptance -v
$env:PYTHONHASHSEED='8675309'; python -m unittest tests.kapisch_validation.test_deterministic_acceptance -v
python scripts/test_portable_package.py
```

## Candidate evidence — 2026-09-13

The Linux root, plugin, and copied portable-package suites completed 885 passed,
0 platform-capability skips. The two explicit deterministic acceptance runs each
passed 6 tests.

Native Windows completed 70 profile tests, two six-test deterministic runs, and
the copied 434-test portable-package suite. The portable suite reported 6
platform-capability skips and `portable-package=passed`.

Both jobs passed for tested runtime tree
`804957019eaee45116201202d463dc9f7345b312`. The automated evidence is bound to this exact runtime tree.

## Release boundary

Final review, merge, authorized release preparation, and remote tag verification
remain pending. No tag or release was created by this acceptance run.
