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

- Current candidate/head commit SHA (contains all required fixes: shipped agent
  `developer_instructions`, `wheel` removal, CI/build metadata):
  `b61442564d82aef1fd21f6b7a83071829fac8858`
- Stage-1 acceptance revision exercised (exact SHA or pre-release tag):
  `b61442564d82aef1fd21f6b7a83071829fac8858` is the head whose shipped artifacts
  (six parseable agent profiles, portable package, CI) were verified; the clean
  isolated-auth live flow remains outstanding (see limitation below).
- Stage-2 immutable release tag (`>=0.2.0`, exact value chosen by the human
  release step): **TEMPLATE-PLACEHOLDER — to be recorded by the release run**
- Evidence reviewer decision and date: **TEMPLATE-PLACEHOLDER — to be recorded by the acceptance run**

The release tag, when cut by the human, must point to exactly the **final
accepted candidate SHA** — the commit that passes both the clean Unix-like and
native Windows acceptance reruns at the end. Prior intermediate commits
(the earlier `c519ced`, where the wheel-removal and agent fixes were NOT yet
both present) must **not** be tagged. As of this record, the final clean
Unix/Windows reruns have not yet completed, so no commit is yet a valid
release-tag target; the tag must bind to the exact SHA exercised in those final
runs and recorded above.

---

## Linux runtime evidence (findings 1-4) at the current candidate head `b614425`

**Status:** earlier immutable remote install and installed-validator acceptance
passed at `f92b996`; fresh authenticated `$kapisch` model invocation passed from
the real user home. The candidate revision for the fixes in this record is the
current head `b61442564d82aef1fd21f6b7a83071829fac8858` (the first revision
containing all six `developer_instructions` profiles and the `wheel` removal).
The isolated-auth clean live flow required by finding 2 is not satisfied by
this evidence.

- Date/time: 2026-08-20T23:26:43+02:00
- OS/arch: Linux 7.1.8-arch1-3, x86_64
- Codex surface/version: authenticated standalone `codex-cli 0.148.0`
- Current candidate head revision:
  `b61442564d82aef1fd21f6b7a83071829fac8858`
- Earlier immutable remote revision exercised by the install evidence below:
  `f92b996f763f462f2e145ef19cbe5e01e2a51359`
- Fresh install-only `CODEX_HOME`:
  `$HOME/kapisch-accept-f92b996-8qoBLQ`
- Python path/version: `$HOME/.hermes/hermes-agent/venv/bin/python`,
  Python 3.11.16
- Authenticated user home used only for live model/profile execution:
  `$HOME` (`CODEX_HOME=$HOME/.codex`); no credential material was
  copied into the fresh install-only home.

### Immutable remote install and installed validator

The fresh install-only home did not exist before `mktemp` created it. It had no
marketplace configuration, plugin cache, or KAPISCH profile. The marketplace
was fetched from GitHub by full commit SHA, not from the source checkout. Exact
commands and observed results:

```text
accept_home=$(mktemp -d "$HOME/kapisch-accept-f92b996-XXXXXX")
# printed $HOME/kapisch-accept-f92b996-8qoBLQ
CODEX_HOME="$accept_home" codex plugin marketplace add twKrash/kapisch --ref f92b996f763f462f2e145ef19cbe5e01e2a51359
# Added marketplace `kapisch-local` from
# https://github.com/twKrash/kapisch.git#f92b996f763f462f2e145ef19cbe5e01e2a51359
CODEX_HOME="$accept_home" codex plugin add kapisch@kapisch-local
# Added plugin `kapisch`; installed root:
# $HOME/kapisch-accept-f92b996-8qoBLQ/plugins/cache/kapisch-local/kapisch/0.1.0
git -C "$accept_home/.tmp/marketplaces/kapisch-local" rev-parse HEAD
# f92b996f763f462f2e145ef19cbe5e01e2a51359
python "$accept_home/plugins/cache/kapisch-local/kapisch/0.1.0/scripts/validate_kapisch.py" \
  --task-dir "$accept_home/.tmp/marketplaces/kapisch-local/plugins/kapisch/tests/kapisch_validation/fixtures/valid-v3-no-delegation" \
  --format json
# []
# exit 0
```

This proves a clean immutable GitHub marketplace install at the reviewed head
and successful execution of its installed validator. The fresh install-only
home was unauthenticated (`CODEX_HOME="$accept_home" codex login status` printed
`Not logged in`, exit 1), so it was not used to overclaim a live model run.

### Fresh authenticated `$kapisch` model invocation

For the required live model invocation, the same immutable SHA was installed in
the authenticated real user home with the two marketplace commands above, then
a new ephemeral Codex session was started. Exact invocation:

```text
codex exec --json --ephemeral -s read-only \
  -C "$HOME/projects/kapisch-issue-11" \
  -o "$HOME/kapisch-live-invocation-f92b996.txt" \
  'Use $kapisch for this read-only acceptance task: analyze how to add one sentence to README.md, but do not edit files or run commands. In your final response, state whether the kapisch skill was invoked and name the selected role.'
```

Result: exit 0. The fresh session emitted `I’m invoking the kapisch skill because
you explicitly requested it` and its final response began `Kapisch skill
invoked: Yes` and `Selected role: Acceptance`. It returned a five-point
read-only acceptance analysis and confirmed that it neither inspected/edited
files nor ran commands. This is live model invocation evidence, not merely
offline prompt composition or skill discovery.

### Earlier reviewer-profile execution attempt (blocked, not fabricated)

The installed setup command executed successfully against the real user home:

```text
python "$HOME/kapisch-accept-f92b996-8qoBLQ/plugins/cache/kapisch-local/kapisch/0.1.0/scripts/setup_profile.py" \
  --role reviewer --scope user --user-dir "$HOME" --install
# profile=$HOME/.codex/agents/kapisch-reviewer.toml
# status=installed
# installed_sha256=921c403e6679657bca6e5702192d62992c3a6292d058d59f4ddd9f3920e9f4e8
# exit 0
```

A separate fresh session then attempted to resolve and execute that exact named
role against `README.md`:

```text
codex exec --json --ephemeral -s read-only \
  -C "$HOME/projects/kapisch-issue-11" \
  -o "$HOME/kapisch-reviewer-execution-f92b996.txt" \
  'Run the installed kapisch-reviewer agent role from $HOME/.codex/agents/kapisch-reviewer.toml to review README.md. This is an execution acceptance check: do not substitute your own generic review if that named role cannot resolve. Do not edit files.'
```

Codex rejected the installed role during fresh-session composition, twice
emitting: `Ignoring malformed agent role definition: agent role file at
$HOME/.codex/agents/kapisch-reviewer.toml must define
developer_instructions`. The session confirmed that the available dispatch API
had no named installed-role selector and that CLI `--profile` targets
`$CODEX_HOME/<name>.config.toml`, not `.codex/agents/*.toml`; it therefore did
not substitute a generic reviewer. Consequently, profile installation and its
exact digest are proven, but actual `kapisch-reviewer` execution is **not**
proven on this Linux `codex-cli 0.148.0` surface. Approval/readiness remains
blocked; no reviewer result is claimed.

### Candidate reviewer-profile execution (completed, advisory)

After adding `developer_instructions` to the shipped candidate profile, a
project-scoped copy of that exact `kapisch-reviewer` TOML was placed under
`.codex/agents/` only for runtime resolution, then removed after the attempt.
The existing user-scoped profile was not overwritten: `setup_profile.py`
reported `status=collision`, `action=review; profile was not changed`, exit 2.
The authenticated ephemeral execution used `--sandbox danger-full-access`:

```text
codex exec --json --ephemeral --sandbox danger-full-access \
  -C "$HOME/projects/kapisch-issue-11" \
  -o /tmp/kapisch-reviewer-execution-c519ced.txt \
  'Spawn exactly one kapisch-reviewer custom agent to review README.md for concrete correctness or documentation defects. Wait for that named agent and return its exact decision and a concise summary. This is an execution acceptance check: do not substitute the parent agent or a built-in generic agent if kapisch-reviewer cannot resolve. Do not edit files.'
```

Result: exit 0. Before project-profile dispatch, the session emitted two
warnings that the stale user-scoped `$HOME/.codex/agents/kapisch-reviewer.toml`
was malformed because it lacked `developer_instructions`. It nevertheless
resolved the project-scoped candidate profile and reported: `The named
kapisch-reviewer is running now.` The terminal response recorded exact decision
`approve`, found no concrete correctness or documentation defects in
`README.md`, and stated that no files were edited. It also explicitly classified
the result as advisory because the no-edit acceptance prompt prevented creation
of canonical KAPISCH invocation artifacts. This proves named reviewer profile
resolution and execution on the authenticated Linux CLI surface.

**Least-privilege caveat (twKrash finding #4):** the shipped `kapisch-reviewer`
profile declares `sandbox_mode = "read-only"`, but this probe dispatched it
under the parent `--sandbox danger-full-access` override. Per current OpenAI
documentation, parent runtime sandbox overrides are reapplied to spawned agents,
so a `danger-full-access` parent does not preserve the profile's declared
read-only boundary. The broader override was required here only because the
acceptance prompt authorized no writes and the earlier `read-only`-scoped probe
could not resolve the named role; this means the run proves **named profile
resolution/execution**, but does **not** prove the shipped reviewer's read-only
boundary enforcement. A least-privilege re-run (parent `--sandbox read-only`
with the profile's own boundary) is required to close this and is currently
**pending**: it cannot be executed while `codex-cli` is rate-limited on this
host (usage-limit error, retry after 2026-08-22). This does not affect finding
3 (the profiles now parse and resolve) or the release gates, but the read-only
boundary evidence remains to be re-verified with least privilege.

This evidence does not establish canonical workflow approval or finding 2's
isolated-auth clean flow.

### Linux portable-package wheel-build rerun

With `build-system.requires = ["setuptools>=70.4"]` and no `wheel` dependency,
the isolated PEP 517 wheel-build path remained green. From `plugins/kapisch`:

```text
python scripts/test_portable_package.py
# Ran 245 tests in 5.491s
# OK
# portable-package=passed
# exit 0
```

The first attempt from the repository root failed with exit 2 because that
directory has no `scripts/test_portable_package.py`; rerunning the exact command
from its documented package directory above exercised the intended gate.

### Finding 2 limitation: isolated authenticated live flow unavailable

Finding 2 is **not satisfiable on this Linux-only, CLI-only host**. Authentication
lives in the real user Codex home, while a newly created isolated `CODEX_HOME`
has no live OAuth state. Copying credentials or reusing pre-existing state would
invalidate the requested clean isolation, and no supported mechanism on this
host can seed the isolated home with the live authenticated session. Therefore
no authenticated isolated-home + clean-consumer live flow is claimed or
fabricated. That evidence requires human execution on a real Codex Desktop/WSL2
surface (or another supported surface that can authenticate the isolated home).

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
- Operator/reviewer: automated agent on the operator's Linux host
- OS/arch: Arch Linux, x86_64
- Codex surface/version: standalone `codex-cli` (`codex-cli 0.148.0`), Git-backed marketplace
- Python version: 3.11+ (host interpreter)

Clean-state preconditions: isolated `CODEX_HOME=/tmp/kapisch-accept-clean`
(fresh directory; no pre-existing marketplace, plugin cache, or KAPISCH
profiles). NOTE: marketplace source was the developer checkout
`$HOME/projects/kapisch-issue-11` — a mutable local path, not an immutable
remote ref — so this does not meet the clean-env no-source-checkout gate.

Commands/actions (exact, as executed):
1. `codex plugin marketplace add "$HOME/projects/kapisch-issue-11"`
   → `Added marketplace kapsch-local` (installed root: the repo)
2. `codex plugin marketplace list`
   → `kapisch-local  $HOME/projects/kapisch-issue-11`
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
- Authenticated isolated-home + clean-consumer live execution (finding 2),
  which cannot be produced on this Linux-only CLI host without invalidating the
  isolation requirement.
- The actual immutable release tag + version bump + release record (explicitly a
  human-confirmed action per the issue; not done here).
