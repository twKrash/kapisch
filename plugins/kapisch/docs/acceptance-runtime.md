# Clean-runtime acceptance record

Status: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

This checked-in record is the evidence accumulator for issue #11. Repository
preparation, automated tests, and this template do not establish Codex runtime
acceptance or authorize a release. The clean-environment acceptance process must
replace every applicable placeholder with observed evidence; it must not infer
results from source inspection or automated tests.

## Environment and Codex surface

- Date/time: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Operator/reviewer: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- OS and architecture: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Codex product/surface: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Codex version/build: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Python version: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

### Native Windows surface

**TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run on an actual
native Windows Codex surface.** Native Windows surface evidence is not available
on the Linux box that prepared this document. Linux execution, path simulation,
and automated Windows-path tests must not be reported as native Windows Codex
runtime evidence.

## Clean-state preconditions

Record how each condition was checked and its observed result:

- No pre-existing `kapisch-local` marketplace configuration:
  **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- No pre-existing KAPISCH plugin installation or cached source:
  **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- No pre-existing KAPISCH skill/profile exposure in the starting session:
  **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Clean test repository and relevant configuration locations:
  **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Any unavoidable retained state and its isolation:
  **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

## Commands and actions performed

Record exact commands/actions in order, including exit status where exposed.
Use a **two-stage, revision-bound** flow so acceptance does not require a tag to
exist yet:

- **Stage 1 — acceptance (no tag required):** exercise the exact commit SHA that
  will become the release, using an immutable remote revision (a commit SHA or a
  pre-release tag) — never a mutable branch/`main`. For the clean-env gate this
  means installing from an immutable remote ref of the exact candidate commit,
  not a source checkout.
- **Stage 2 — release (after acceptance):** the human release step chooses the
  version and tags that same accepted commit; only then does the released
  install path reference the tag.

```text
TEMPLATE-PLACEHOLDER — record Stage-1 acceptance: codex plugin marketplace add twKrash/kapisch --ref <accepted-commit-SHA|pre-release-tag>
TEMPLATE-PLACEHOLDER — record codex plugin add kapisch@kapisch-local
TEMPLATE-PLACEHOLDER — record session restart/new-session action
TEMPLATE-PLACEHOLDER — record profile setup and validator commands
```

## Plugin discovery result

**TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run.** Record the
fresh-session discovery action, exposed plugin/skill identifiers, output or
receipt when available, and whether KAPISCH was absent before installation and
present afterward. Record unexposed receipts as `unavailable`; do not infer
them.

## `$kapisch` invocation result

**TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run.** Record the
exact task/prompt, selected surface, observed invocation result, degraded-mode
disclosure if profiles are absent, and relevant durable evidence paths. Do not
substitute source inspection or validator success for invocation evidence.

## Reviewer invocation result

**TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run.** Record the
explicit reviewer-profile setup, resolved profile identity and revision,
invocation action, canonical invocation evidence path, result digest, and
whether the outcome was advisory or approval-capable. Installation alone does
not prove reviewer invocation.

## Validator result

**TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run.** Record the
installed command or documented wrapper used, exact task directory, command,
exit status, finding count, and output. Repository-side unit-test results may be
listed separately but are not runtime validator evidence.

## Known limitations and exclusions

- OpenAI public Plugin Directory submission is out of scope; distribution uses
  the Git-backed `kapisch-local` marketplace.
- Delegated `external-write` and `destructive` effects fail closed. No
  reconciliation protocol or exactly-once guarantee is claimed.
- Runtime acceptance does not authorize a version bump, tag, push, publication,
  or release; those remain human-confirmed actions.
- Additional observed limitations: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

## Accepted revision and release tag

- Accepted commit SHA: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**
- Stage-1 acceptance revision exercised (exact SHA or pre-release tag):
  **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance/release run**
- Stage-2 immutable release tag (`>=0.2.0`, exact value chosen by the human
  release step): **TEMPLATE-PLACEHOLDER — to be recorded by the release run**
- Evidence reviewer decision and date: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

The accepted commit must be the commit actually exercised in Stage 1. The
Stage-2 tag must resolve to that same accepted commit. A branch name, `main`,
an anticipated version, or this template's preparation commit is not a
substitute.

---

## Linux local packaging/validator smoke test (NOT the clean runtime acceptance)

**Status: local smoke test only.** This is NOT issue #11's clean-runtime
acceptance. It installs from the developer source checkout (a mutable, local
path), not from an immutable remote revision, so it does not exercise the
documented GitHub install path or satisfy the no-source-checkout precondition
of the real acceptance. It is recorded as disposable local evidence of
packaging + validator behavior. The real Stage-1 acceptance must rerun these
steps from an immutable remote revision (commit SHA / pre-release tag).

- Date/time: 2026-08-20 (~12:00 CEST)
- Operator/reviewer: Hermes agent on the operator's Linux host
- OS/arch: Arch Linux, x86_64
- Codex surface/version: standalone `codex-cli` (`codex-cli 0.148.0`), Git-backed marketplace
- Python version: 3.11+ (host interpreter)

Clean-state preconditions: isolated `CODEX_HOME=/tmp/kapisch-accept-clean`
(fresh directory; no pre-existing marketplace, plugin cache, or KAPISCH
profiles). NOTE: marketplace source was the developer checkout
`/home/agent/projects/kapisch-issue-11` — a mutable local path, not an immutable
remote ref — so this does not meet the clean-env no-source-checkout gate.

Commands/actions (exact, as executed):
1. `codex plugin marketplace add /home/agent/projects/kapisch-issue-11`
   → `Added marketplace kapsch-local` (installed root: the repo)
2. `codex plugin marketplace list`
   → `kapisch-local  /home/agent/projects/kapisch-issue-11`
3. `codex plugin add kapisch@kapisch-local`
   → `Added plugin kapisch from marketplace kapisch-local` (root `.../plugins/cache/kapisch-local/kapisch/0.1.0`)
4. `codex plugin list`
   → `kapisch@kapisch-local  installed, enabled  0.1.0`
5. Successful installed-validator run (from cwd `/tmp`, outside the source
   checkout) against a valid task directory:
   `python <installed-root>/scripts/validate_kapisch.py --task-dir <fixtures>/valid-v3-no-delegation --format json`
   → output `[]` (no findings), exit status `0`. This is the positive case:
   installed validation succeeds through the public command + bundled (fallback)
   resources.
6. Error-path installed-validator run (same command, incomplete task dir):
   → structured finding `TWV-PARSE-MISSING-ARTIFACT` (missing
   `02-execution-graph.toml`), exit status `2`. Proves the error path, not the
   acceptance success criterion.

Installation/discovery result (installation and packaging, NOT fresh-session
runtime discovery): the marketplace was recognized and the single `kapisch`
plugin was installed + enabled from a clean env. The installed bundle contains
`skills/kapisch/SKILL.md`, its references and themes, and all six roles
(`roles/*.md`) plus the reviewer agent file. This establishes packaging and
install-time visibility. It is NOT evidence that a fresh interactive Codex
session resolves `$kapisch` or the profiles at runtime — no such session was
started here, so no runtime-discovery claim is made.

`$kapisch` / fresh-session invocation: **not exercised.** A fresh Codex session
was not started and `$kapisch` was not invoked. The PATH-alias creation step was
blocked because the isolated `CODEX_HOME` sits under `/tmp`, which Codex refuses
for helper binaries ("Refusing to create helper binaries under temporary dir
`/tmp`") — a host-path hygiene guard of this local test CODEX_HOME, not a plugin
defect. The installed validator was invoked directly via its script (steps
5-6) and ran correctly; that is validator invocation, not a fresh-session
`$kapisch`.

Validator contract source: this installed bundle has **no
`kapisch_validation/contracts` package** (it is a plugin-bundle copy, not a
pip-installed wheel), so the validator resolved contracts via the documented
`skills/kapisch` fallback path in `_bundled_contract_resource()`. The
`importlib.resources` bundled-contracts path is only exercised after an actual
wheel install and was NOT exercised here. Exact, uncontradicted.

Reviewer invocation: reviewer profile exists in the bundle
(`agents/kapisch-reviewer.toml`); a reviewer *execution* (a fresh session
resolving the reviewer role) was NOT run here and is not claimed.

Known limitations:
- Windows native surface not exercised (this is a Linux host); must be recorded
  from an actual Windows Codex surface per #11.
- `$kapisch` PATH-alias binary not created under an isolated `/tmp` CODEX_HOME
  (host-path hygiene); documented, expected to resolve in a real user home.
- OpenAI public Plugin Directory submission is out of scope (local `kapisch-local`
  marketplace only).
- No version/tag/release should be cut from this Linux-run evidence alone.

## Blockers left for human / twKrash decision
- Native Windows surface evidence (required for #11 acceptance).
- The actual immutable release tag + version bump + release record (explicitly a
  human-confirmed action per the issue; not done here).
