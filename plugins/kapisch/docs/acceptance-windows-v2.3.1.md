# Windows acceptance record — 2.3.1

**Status: local contract and package tests passed; CI, native Windows, live marketplace, and release acceptance are pending.** No native Windows or live marketplace result is claimed.

- Release: `2.3.1`; intended immutable tag: `v2.3.1`.
- Tested runtime SHA: `66234d7e3d98bbba25d7c61cf65b1c889494cee4`.
- The SHA identifies a Git tree object, not a commit.
- Reproduce the tree from the candidate base with a temporary Git index, adding candidate source and test files while excluding `docs/superpowers/**`, `plugins/kapisch/docs/acceptance.md`, and this candidate acceptance record. Then run `git write-tree`.
- Local KAPISCH validator suite: 490 passed, 0 platform-capability skips.
- Pi harness suite (`bun test` in `harnesses/pi`): 12 passed; portable-package check passed.
- Root release-metadata suite: 18 passed.
- Direct bundled validator `--help` invocation from an unrelated Pi consumer working directory: passed.
- CI and native Windows/live marketplace acceptance: pending.
- Automated runtime evidence is bound to this exact source tree.
- Final release SHA: pending review, merge, and authorized release preparation.

This patch clarifies how agents derive the bundled-script root from the loaded
KAPISCH skill path. It changes no runtime script behavior.
