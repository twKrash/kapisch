# Clean-runtime acceptance record

Status: **PARTIAL — clean Unix-like acceptance COMPLETE at RELEASE_SHA
`d186b90` (release 1.0.0, tag `v1.0.0`); native-Windows surface and the final
release-sequence are deferred/remain outstanding (Windows in a separate
issue).**

This checked-in record is the evidence accumulator for issue #11. Repository
preparation, automated tests, and this template do not establish Codex runtime
acceptance or authorize a release. The clean-environment acceptance process must
replace every applicable placeholder with observed evidence; it must not infer
results from source inspection or automated tests.

## Environment and Codex surface

- Date/time: 2026-08-20T23:26:43+02:00 (Linux evidence)
- Operator/reviewer: Hermes agent on the operator's Linux host (preparation
  evidence; final clean run is a separate human/Windows step)
- OS and architecture: Linux 7.1.8-arch1-3, x86_64
- Codex product/surface: authenticated standalone `codex-cli 0.148.0`
- Codex version/build: 0.148.0
- Python version: 3.11.16

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

- Intermediate artifact-verification revision (historical/intermediate
  evidence, NOT the final accepted release candidate):
  `b61442564d82aef1fd21f6b7a83071829fac8858` — the revision whose shipped
  artifacts (six parseable agent profiles, portable package, CI) were verified.
- Final accepted release candidate: **COMPLETE on Unix-like** — clean Unix-like
  runtime acceptance passed (see "Clean Unix-like acceptance" below) at release
  version **1.0.0** (tag `v1.0.0`). Native-Windows runtime acceptance is
  **deferred to a separate issue** (per maintainer decision), so the accepted
  release candidate for this PR is the Unix-verified revision only.
- Stage-1 acceptance revision exercised (exact SHA or pre-release tag):
  not yet completed for the final candidate. Earlier immutable-remote
  install/validator evidence exists at `f92b996...` and artifact verification at
  `b614425...`; both are historical/intermediate evidence, not the accepted
  candidate.
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

## Linux runtime evidence (findings 1-4) — artifact revision `b614425`

**Status:** earlier immutable remote install and installed-validator acceptance
passed at `f92b996`; fresh authenticated `$kapisch` model invocation passed from
the real user home; the shipped agent profiles and portable-package gate were
verified green at the artifact revision `b61442564d82aef1fd21f6b7a83071829fac8858`
(the first revision containing all six `developer_instructions` profiles and the
`wheel` removal; this is also the revision twKrash's exact-head Windows probe
verified). Subsequent commits on this prep branch (e.g. `c45d219`) are
documentation-only and do not alter the verified release artifacts. The release
tag, when cut, must still bind to the **exact SHA exercised in the final clean
Unix/Windows reruns** — not to this artifact revision automatically. The
isolated-auth clean live flow required by finding 2 is not satisfied by this
evidence.

- Date/time: 2026-08-20T23:26:43+02:00
- OS/arch: Linux 7.1.8-arch1-3, x86_64
- Codex surface/version: authenticated standalone `codex-cli 0.148.0`
- Artifact revision (all required fixes, verified at this SHA):
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

### Candidate reviewer-profile probe (named-agent resolution + read-only sandbox observation)

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

**Least-privilege probe (twKrash finding #4):** the shipped `kapisch-reviewer`
profile declares `sandbox_mode = "read-only"`. An earlier probe dispatched it
under a parent `--sandbox danger-full-access` override, which (per current
OpenAI documentation) does not preserve the profile's declared read-only
boundary. A least-privilege re-run was then executed with a **`read-only`
parent sandbox** (via the `deepseek` Codex profile to work around the primary
OpenAI profile's usage limit). Result: the named `kapisch-reviewer` custom agent
**did resolve and run under the read-only boundary** — this is **named-agent
resolution plus read-only sandbox observation only**, not reviewer acceptance:
a runtime message-delivery limitation meant the concrete review task text never
reached the spawned agent, so it executed a read-only review autonomously and
no explicit `approve`/`do-not-approve` decision was returned; no decision was
fabricated. The read-only agent's own verification pass flagged three
documentation drifts (head-binding staleness, template placeholders at the top,
and README wording) — see the fixes below. A clean decision-bearing
least-privilege run still needs to be re-attempted once the primary profile's
usage limit clears (2026-08-22) and/or on the Windows surface.

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

### Finding 2: isolated authenticated live flow — COMPLETED (2026-08-23)

Finding 2's clean authenticated live flow was executed successfully. A
brand-new empty `CODEX_HOME` (`/tmp/kapisch-clean-home-TtcZ4t`) was authenticated
**in place** with `codex login` (ChatGPT OAuth, not a copied `auth.json`), and a
separate fresh consumer Git repository (`/tmp/kapisch-clean-consumer-GBohnk`)
was created with no pre-existing marketplace, plugin, skill, profile, or KAPISCH
source checkout. Details are recorded in the "Clean Unix-like acceptance"
section below. This flow requires an interactive browser login in the fresh
home, which a fully headless CLI cannot complete alone; it was performed with
the operator's assistance. The native-Windows surface execution remains a
separate outstanding item.

---

## Clean Unix-like acceptance (COMPLETE, 2026-08-23)

**Status: PASSED.** This is the issue #11 clean-runtime acceptance on a Unix-like
surface, run from a clean authenticated home and a separate clean consumer,
without any developer source checkout. Marketplace added at the exact immutable
SHA; plugin installed/enabled; live `$kapisch` durable invocation succeeded;
named reviewer approved; installed validator returned `[]`, exit 0.

- Date/time: 2026-08-23
- OS/arch: Linux 7.1.8-arch1-3, x86_64
- Codex surface/version: authenticated standalone `codex-cli 0.148.0`
  (ChatGPT OAuth, logged in inside the fresh home)
- Python version: 3.11.16
- Marketplace ref: exact commit SHA `09a29f25b31c0f72de17a4db7e23e7c70063be6c`
  (= `5c609ea…`, the later commit is docs-only; release artifacts identical)
- Fresh `CODEX_HOME`: `/tmp/kapisch-clean-home-TtcZ4t` (empty before `codex login`)
- Fresh consumer repo: `/tmp/kapisch-clean-consumer-GBohnk` (git init, README only)

### Clean-state preconditions (verified)

- Fresh `CODEX_HOME` did not exist before `mktemp`; it was empty at creation.
- Fresh consumer repo had only `README.md`; no marketplace, plugin, skill,
  profile, or `$kapisch` cache in either starting environment.
- Authentication was performed in-place with `codex login` inside the fresh
  home; verified `Logged in using ChatGPT`. No `auth.json` was copied.

### Commands executed and results

```text
# 1. Marketplace at exact SHA (never main)
codex plugin marketplace add twKrash/kapisch --ref 09a29f25b31c0f72de17a4db7e23e7c70063be6c
# -> Added marketplace `kapisch-local` from .../kapisch.git#09a29f2...
#    Installed root: $CODEX_HOME/.tmp/marketplaces/kapisch-local

# 2. Install/enable plugin
codex plugin add kapisch@kapisch-local
# -> Added plugin `kapisch`; version 0.1.0, installed, enabled

# 3. Install all six profiles into consumer, verify no collision/drift
python $PLUGIN/scripts/setup_profile.py --all --project-dir $CONSUMER --install
# -> 6 profiles installed: status=installed, template_sha256 == installed_sha256

# 4. Live durable $kapisch invocation (workspace-write session)
codex exec --json --ephemeral --sandbox workspace-write -C $CONSUMER \
  'Use $kapisch with DURABLE end-to-end execution ... add an Installation section to README.md ...'
# -> role=implementer, task_id=add-a-short-installation-section-to-readme-md
#    durable artifacts under .kapisch/runs/<task_id>/:
#    01-plan.md, 02-execution-graph.toml, 03-state.toml, tasks/T01-*, reviews/round-0/*,
#    reviews/final/00-final-invocation.toml, reviews/final/05-final.md
#    R01 reviewer returned `approve`; final lifecycle completed/ready

# 5. Installed validator against the generated task
python $PLUGIN/scripts/validate_kapisch.py --task-dir $CONSUMER/.kapisch/runs/<task_id> --format json
# -> [] (no findings)
#    exit 0
```

### Result

- Live `$kapisch` invocation: selected role `implementer`, produced a durable
  task with the full canonical artifact set (graph + state + plan + tasks +
  round-0 review + final review).
- Named reviewer R01 returned explicit `approve`; F01 final review lifecycle
  `completed` / returned decision `ready`.
- Installed validator: output `[]`, exit code `0`.

### Note on the graph-free pitfall

The acceptance task as originally phrased ("add a short Installation section")
is simple isolated work, which Kapisch routes to the **graph-free** flow and
writes **no** `02-execution-graph.toml`; the installed validator rejects such a
directory with `TWV-PARSE-MISSING-ARTIFACT`. Requesting **durable end-to-end
execution** makes the controller emit the canonical graph/state artifacts and
passes validation. This is documented here so the pre-release acceptance step
uses the durable-execution phrasing.

---

## RELEASE_SHA acceptance (1.0.0, 2026-08-23) — PASSED

**Status: PASSED.** The clean Unix-like acceptance rerun at the final release
commit `d186b90592f65f9861c680d852ee05723f982903` (= `RELEASE_SHA`, tag
`v1.0.0`), in brand-new authenticated homes/consumer (no copied auth).

- Date/time: 2026-08-23
- OS/arch: Linux 7.1.8-arch1-3, x86_64
- Codex surface/version: authenticated standalone `codex-cli 0.148.0`
  (ChatGPT OAuth, logged in inside the fresh home)
- Python version: 3.11.16
- `RELEASE_SHA`: `d186b90592f65f9861c680d852ee05723f982903` (immutable tag `v1.0.0`)
- Fresh `CODEX_HOME`: `/tmp/kapisch-release-home-UvG0kJ` (empty before `codex login`)
- Fresh consumer repo: `/tmp/kapisch-release-consumer-qjJ1ir` (git init, README only)

Results:
- Marketplace resolved to exact `RELEASE_SHA`; plugin installed/enabled at
  version **1.0.0**.
- All six profiles installed into the consumer, no collision/drift.
- Live durable `$kapisch` invocation: role `mechanic`, task
  `add-a-short-installation-section-to-readme-md-an`, durable artifacts written
  (`01-plan.md`, `02-execution-graph.toml`, `03-state.toml`, T01/R01/F01 tasks,
  round-0 + final reviews), final status `complete`.
- Independent iteration review returned `approve`; separate final-readiness
  review returned `ready` (lifecycle `completed`).
- **Installed validator: `[]`, exit 0** at `$CONSUMER/.kapisch/runs/<task_id>`.

This is the binding acceptance evidence for release 1.0.0. Native-Windows
acceptance is deferred to a separate issue per the maintainer decision.

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
