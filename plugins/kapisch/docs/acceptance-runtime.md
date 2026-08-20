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
The marketplace command must use the immutable human-confirmed `>=0.2.0`
release tag, never mutable `main`.

```text
TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run
codex plugin marketplace add twKrash/kapisch --ref <release-tag>
codex plugin add kapisch@kapisch-local
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
- Immutable release tag (`>=0.2.0`, exact value chosen by the human release
  step): **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance/release run**
- Evidence reviewer decision and date: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

The accepted commit must be the commit actually exercised. The tag must resolve
to that accepted commit. A branch name, `main`, an anticipated version, or this
template's preparation commit is not a substitute.

---

## Linux acceptance result (recorded from actual run)

- Date/time: 2026-08-20 (~12:00 CEST)
- Operator/reviewer: Hermes agent on the operator's Linux host (twKrash-workspace)
- OS/arch: Arch Linux, x86_64
- Codex surface/version: standalone `codex-cli` (`codex-cli 0.148.0`), Git-backed marketplace
- Python version: 3.11+ (host interpreter)

Clean-state preconditions: ran with an isolated `CODEX_HOME=/tmp/kapisch-accept-clean`
(fresh directory; no pre-existing marketplace, plugin cache, or KAPISCH profiles).
No developer checkout was on the repo path at test time beyond the source itself.

Commands/actions (exact, as executed):
1. `codex plugin marketplace add /home/agent/projects/kapisch-issue-11`
   → `Added marketplace kapsch-local` (installed root: the repo)
2. `codex plugin marketplace list`
   → `kapisch-local  /home/agent/projects/kapisch-issue-11`
3. `codex plugin add kapisch@kapisch-local`
   → `Added plugin kapisch from marketplace kapisch-local` (root `.../plugins/cache/kapisch-local/kapisch/0.1.0`)
4. `codex plugin list`
   → `kapisch@kapisch-local  installed, enabled  0.1.0`
5. From cwd `/tmp` (outside the source checkout), run the installed validator
   against a real task directory and record its exit status/findings:
   `python <installed-root>/scripts/validate_kapisch.py --task-dir <fixture>/task --format json`
   → resolved a structured finding `TWV-PARSE-MISSING-ARTIFACT` for the missing
   `02-execution-graph.toml` at the required path, exit status `2`. This exercises
   contract resolution (default `--contract-dir`), task-dir parsing, finding
   formatting, and non-zero exit handling from the installed plugin — not just
   `--help`.

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
defect. The installed validator was invoked directly via its script (see step 5)
and ran correctly; that is validator invocation, not a fresh-session `$kapisch`.

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
