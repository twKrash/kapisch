# Windows acceptance record — 2.3.0

**Status: local contract and package tests passed; CI, live Windows acceptance, and release acceptance are pending.** No native Windows or live marketplace result is claimed.

- Release: `2.3.0`; intended immutable tag: `v2.3.0`.
- Tested runtime SHA: `594cb899b855ef3489204a26885ee3595eefde27`.
- The SHA identifies a Git tree object, not a commit.
- Reproduce tree by initializing a temporary Git index from the candidate base, adding candidate source and test files, excluding `docs/superpowers/**` and the two candidate acceptance records (`plugins/kapisch/docs/acceptance.md` and `plugins/kapisch/docs/acceptance-windows-v2.3.0.md`), then running `git write-tree`. Acceptance and plan records are excluded to avoid self-reference.
- Local KAPISCH validator suite: 490 passed, 0 platform-capability skips, run from an export of this tree.
- Pi harness suite: 11 passed; portable-package check passed, both run from the exported tree.
- Root release-metadata suite: 18 passed in candidate worktree; not included in the runtime-tree claim.
- CI runs and native Windows/live marketplace acceptance: pending.
- Automated runtime evidence is bound to this exact source tree.
- Final release SHA: pending review, merge, and authorized release preparation.

The 2.3.0 candidate adds graph-free `workflow=review` for one fresh,
read-only `kapisch-reviewer` invocation. Standalone reviews return findings to
the parent/orchestrator and do not create durable workflow artifacts. Durable
task and milestone review contracts remain unchanged.
