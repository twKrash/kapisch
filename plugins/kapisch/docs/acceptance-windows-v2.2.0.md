# Windows acceptance record — 2.2.0

**Status: corrected candidate CI passed; final 2.2.0 release acceptance is pending.**
No live native-PowerShell marketplace flow is claimed.

- Release: `2.2.0`; intended immutable tag: `v2.2.0`.
- Tested runtime SHA: `1c2631f2c4e691d436d3822e8a0bafd02a91d651`.
- CI runs: `36362502034` (`push`) and `36362504465` (`pull_request`).
- Linux `ci` and Windows `windows-profile-setup`: `PASS` on that tested head.
- Current local KAPISCH suite after authority fixes: 482 passed, 0 platform-capability skips.
- automated evidence is bound to this exact runtime tree.
- Final release SHA: pending review, merge, and authorized release preparation.
- Remote tag verification: pending; do not create or publish the tag during
  candidate preparation.

The 2.2.0 candidate adds graph-free advisory architecture snapshots and
content-addressed promotion plans. The corrected implementation rejects
unbound plans, symlink-based supersession bypasses, malformed relationship
records, and relationships that do not bind a valid accepted snapshot.
