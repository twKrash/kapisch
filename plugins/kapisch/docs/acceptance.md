# Acceptance status

Automated tests establish package and contract behavior. Live acceptance
separately proves marketplace resolution, session discovery, named-agent
dispatch, durable execution, and the installed public validator.

## Current matrix

| Surface | Status | Evidence |
| --- | --- | --- |
| Marketplace layout and canonical plugin source | passed | root `tests/test_marketplace.py` |
| Portable package and validator | passed | `scripts/test_portable_package.py` and `tests/kapisch_validation` |
| Unix-like release 1.0.0 | complete | [historical runtime record](acceptance-runtime.md) |
| Windows 11 Desktop + WSL2 release baseline | complete | [1.0.1 Windows record](acceptance-windows-v1.0.1.md) |
| 1.0.1 exact release SHA and remote tag | complete | [1.0.1 Windows record](acceptance-windows-v1.0.1.md) |
| Native Windows without WSL | automated Python gates passed; live flow not yet claimed | [1.0.1 Windows record](acceptance-windows-v1.0.1.md) |
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

The suites cover strict manifest versions, lifecycle and previous-snapshot
compatibility, digest and UTF-8 handling, reviewer invocation evidence, legacy
migration, profile identity and drift, presentation themes, delegation records,
installed console-command discovery, and the canonical marketplace source.
Project-understanding procedures, role boundaries, handoffs, and independent
review policy remain covered by the extraction-acceptance suite.

## Live acceptance boundary

A release flow uses a new authenticated `CODEX_HOME`, an unrelated clean
consumer repository, and a marketplace reference pinned to one full commit SHA.
It must prove:

1. the cached marketplace and installed plugin resolve to that SHA;
2. all six optional profiles install without collision or drift;
3. a fresh session completes a durable `$kapisch` task;
4. named independent review and final readiness return explicit decisions;
5. a separate read-only reviewer changes no consumer files; and
6. the installed `kapisch-validate` command returns `[]` and exit code 0 without
   `--contract-dir`.

Version 1.0.0 completed this flow on Linux. Version 1.0.1 completed it on
Windows Desktop with WSL2 at the exact release SHA, including remote tag
verification.

## Delegation boundary

Read-only `repository-read` and `external-read` delegation records are
supported for version-3 durable graphs. Delegated `external-write` and
`destructive` routes fail closed because interrupted external effects cannot be
reconciled safely. No acceptance result creates an exactly-once guarantee or
authorizes installation, authentication, commit, push, publication, sending, or
destructive work.
