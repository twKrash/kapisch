# Windows acceptance record — 2.2.0

**Status: preliminary candidate evidence; final 2.2.0 acceptance is pending.**
The Windows result below covers the original PR #44 implementation head, before
the authority-validation fixes in this update. No live native-PowerShell
marketplace flow is claimed.

- Release: `2.2.0`; intended immutable tag: `v2.2.0`.
- Tested runtime SHA: `25818d8f1b9162d89d05ea8458ca1ce44a73480d`.
- CI runs: `36356057859` (`push`) and `36356059919` (`pull_request`).
- Linux `ci`: `PASS`; Windows `windows-profile-setup`: `PASS` on that tested head.
- Current local KAPISCH suite after authority fixes: 482 passed, 0 platform-capability skips; CI on corrected branch is pending.
- automated evidence is bound to this exact runtime tree; it does not establish
  final release readiness for the current branch.
- Final release SHA: pending review, merge, and authorized release preparation.
- Remote tag verification: pending; do not create or publish the tag during
  candidate preparation.

The 2.2.0 candidate adds graph-free advisory architecture snapshots and
content-addressed promotion plans. The current fixes reject unbound plans,
symlink-based supersession bypasses, and malformed relationship records.
The initial CI evidence predates those fixes; update this record after CI runs
on the corrected branch head.
