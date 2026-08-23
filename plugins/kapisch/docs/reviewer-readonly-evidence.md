# Read-only-parent decision-bearing reviewer evidence (release 1.0.0)

Surface: interactive `codex-cli 0.148.0` (ChatGPT OAuth), run 2026-08-23.
Parent sandbox: **read-only** (`permission_profile type=managed`,
`file_system type=restricted`, `entry access=read`, `<special>:root` — confirmed
in the session environment context).
Consumer repo: `~/kapisch-ro-hwlLHI` (fresh; separate from the kapisch source
checkout).
Reviewed range: `eafa7c9…bc2c1a0` (README.md only).

## Result

- **Resolved agent:** `/root/review_readme_commit` reported as the named
  `kapisch-reviewer` (custom agent from `.codex/agents/kapisch-reviewer.toml`).
  Task receipt confirmed; no generic/parent substitute used.
- **Exact decision:** **`do-not-approve`**
- **Finding:** `README.md:3` says only "run" without naming a command,
  executable, or prerequisites; the repository contains no runnable entry point
  or other installation instructions. Required fix: document the exact command
  and prerequisites, or state that the repository is not yet runnable.
- **Verification reported:** reviewed `eafa7c9...bc2c1a0`; `git diff --check`
  passed; no tests or documentation linting available.
- **Files changed by reviewer:** **No** (working tree clean apart from the
  pre-existing untracked `.codex/` profiles).

## Why this satisfies the blocker

This is a decision-bearing `kapisch-reviewer` run under a **read-only parent**
in which the named reviewer:

1. resolved (not a generic built-in substitute),
2. received the concrete task (base, head, file scope, read-only constraint,
   decision vocabulary, evidence requirements),
3. returned an **explicit decision** (`do-not-approve`) with a real finding, and
4. changed no files.

Parent sandbox overrides are reapplied to spawned agents per the official
subagent docs; the parent was read-only, so the spawned reviewer ran read-only.
This complements the earlier `workspace-write`-parent durable decision (which
produced `approve`/`ready` but did not prove the read-only boundary); this run
does.
