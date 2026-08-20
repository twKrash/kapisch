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
