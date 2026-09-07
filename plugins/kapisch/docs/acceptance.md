# Acceptance status

Automated tests establish package and contract behavior. Live acceptance
separately proves marketplace resolution, session discovery, named-agent
dispatch, durable execution, and the installed public validator.

## Current matrix

| Surface | Status | Evidence |
| --- | --- | --- |
| Marketplace layout and canonical plugin source | passed | root `tests/test_marketplace.py` |
| Portable package and validator | passed | `scripts/test_portable_package.py` and `tests/kapisch_validation` |
| 2.0.0 local-profile compatibility candidate | passed for tested runtime tree `ab0f00708d4baee9ebb8b81005d6f2e3a92c6daa`; final release SHA pending | [2.0.0 Windows record](acceptance-windows-v2.0.0.md) |
| Unix-like release 1.0.0 | historical complete | [historical runtime record](acceptance-runtime.md) |
| Windows 11 Desktop + WSL2 release baseline | historical complete | [1.0.1 Windows record](acceptance-windows-v1.0.1.md) |
| 1.0.1 exact release SHA and remote tag | historical complete | [1.0.1 Windows record](acceptance-windows-v1.0.1.md) |
| Pre-2.0 Windows/release candidate rows | historical | prior acceptance records |
| Native Windows without WSL | pending required 2.0.0 automated CI; live flow not claimed | [2.0.0 Windows record](acceptance-windows-v2.0.0.md) |
| OpenAI public Plugin Directory | out of scope | Git-backed `kapisch-local` is the distribution path |

## Automated acceptance

Run from the plugin directory:

```text
python -m unittest discover -s tests/kapisch_validation
python scripts/test_portable_package.py
```

Run from the repository root:

```text
python -m unittest discover -s tests
git diff --check
```

Project-understanding procedures, role boundaries, handoffs, and independent
review remain covered by the contract acceptance suite.

## Latest CI evidence

Tested runtime SHA: `ab0f00708d4baee9ebb8b81005d6f2e3a92c6daa`

CI workflow: `34055905476`

| Check | Status |
| --- | --- |
| Linux CI | PASS |
| Windows `windows-profile-setup` | PASS |

The suites cover strict manifest versions, lifecycle and previous-snapshot
compatibility, digest and UTF-8 handling, reviewer invocation evidence, legacy
durable-run migration, profile identity and drift, presentation themes,
delegation records, installed console-command discovery, and the canonical
marketplace source. For 2.0.0, profile coverage verifies current schema state,
explicit managed replacement, drift/collision refusal, legacy refusal with no
mutation, and rejection of old journal schemas. Historical verified legacy
quality records are not a current test claim.

## Live acceptance boundary

A release flow uses a new authenticated `CODEX_HOME`, an unrelated clean
consumer repository, and a marketplace reference pinned to one full commit SHA.
It must prove marketplace resolution, all six optional profile installs, a fresh
durable `$kapisch` task, independent review and final readiness, a separate
read-only reviewer, and the installed `kapisch-validate` command returning `[]`.

The 1.0.0 Linux and 1.0.1 Windows Desktop + WSL2 flows are historical evidence;
they do not establish the pending 2.0.0 native-Windows CI result.

## Delegation boundary

Read-only `repository-read` and `external-read` delegation records are
supported for version-3 durable graphs. Delegated `external-write` and
`destructive` routes fail closed. No acceptance result authorizes installation,
authentication, commit, push, publication, sending, or destructive work.
