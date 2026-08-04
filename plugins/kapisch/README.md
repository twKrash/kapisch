# KAPISCH

KAPISCH is a lightweight Codex-native workflow contract and validation plugin
for safe, explainable repository work. It supplies portable role contracts,
human approval gates, and a read-only Python 3.11 validator for durable TOML
evidence; Codex remains responsible for agent dispatch, model selection, and
sandboxing.

## Install

This plugin is distributed through the Git-backed `kapisch-local` marketplace,
not OpenAI's public Plugin Directory. Configure the marketplace first:

```text
codex plugin marketplace add twKrash/kapisch --ref main
```

Install KAPISCH later when it should become active:

```text
codex plugin add kapisch@kapisch-local
```

Start a new Codex session, then invoke `$kapisch` in a repository task. The
plugin works without custom agent profiles, but that degraded mode is advisory
only: independent review and final-readiness approval require an explicitly
installed, successfully invoked reviewer profile.

## Optional profiles

`agents/` contains templates only. They are not activated by plugin installation.
From this plugin directory, inspect the project-scoped target and then explicitly
install only a missing profile:

```text
python scripts/setup_profile.py --role reviewer --project-dir <consumer-repository>
python scripts/setup_profile.py --role reviewer --project-dir <consumer-repository> --install
```

For a user-scoped target, use `--scope user` (use `--user-dir` only for a
controlled alternate home). The script refuses filename and profile-identity
collisions, never overwrites, renames, or deletes profiles, records template and
installed SHA-256 revisions under the matching `.kapisch/local-state/`, and
reports installed-profile and template drift. See
[compatibility.md](docs/compatibility.md) for removal and rollback.

## Durable artifacts and migration

New artifacts live under `.kapisch/runs/<task-id>/`; cache and machine-local
state belong in `.kapisch/cache/` and `.kapisch/local-state/`. Add `.kapisch/`
to each consuming repository's `.gitignore`.

Legacy `.planning/task-workflow/<task-id>/` evidence is read-only migration input
under compatibility version 1. From this plugin directory, run:

```text
python scripts/migrate_legacy_run.py --project-dir <consumer-repository> --task-id <task-id> --approve
```

This performs the explicit copy-and-validate operation into the consumer
repository's `.kapisch/runs/`. It preserves the source, does not rewrite
historical bytes, paths, digests, or invocation records, and does not combine
evidence between namespaces. If validation fails, it retains the source and
creates no destination. KAPISCH never creates new legacy artifacts.

## Validator

The validator uses only the Python 3.11 standard library and never writes,
dispatches, schedules, routes requests, invokes Git, or grants approval.
Delegation evidence is validated the same way: a version-3 durable run with
`delegation_ids` on graph nodes automatically validates the matching
`delegations/00-route.toml` record and its digest-bound context/evidence files.
Findings use `TWV-DELEG-*` error codes.

From the plugin directory (development), the validator runs directly:

```text
python scripts/validate_kapisch.py --contract-dir skills/kapisch --task-dir <consumer-repository>/.kapisch/runs/example
python -m unittest discover -s tests/kapisch_validation
```

After marketplace installation, `$kapisch` runs from the consumer repository,
which does not contain the plugin's `scripts/` or `skills/` paths. Resolve the
script and `--contract-dir` from the installed plugin root (the directory
containing `skills/kapisch/SKILL.md`) and keep only `--task-dir` rooted in the
consumer:

```text
python <plugin-root>/scripts/validate_kapisch.py --contract-dir <plugin-root>/skills/kapisch --task-dir <consumer-repository>/.kapisch/runs/example
```

## Project understanding

KAPISCH can route bounded architecture questions, architecture maps,
documentation-drift checks, onboarding summaries, and decision-record
preparation through its read-only researcher contract. Research reports cite
current repository evidence and remain separate from documentation edits,
architecture decisions, and independent review. See
[`project-understanding.md`](skills/kapisch/references/project-understanding.md).

## Presentation themes

Use `theme=default` (the default) or `theme=foundry` to change user-visible
terminology. Foundry is an original industrial-mystic vocabulary pack. Themes
change labels only: canonical roles, controls, permissions, routing, artifacts,
status values, validation, and approval gates remain unchanged. See
[`themes.md`](skills/kapisch/references/themes.md).

## Delegated ecosystem capabilities

KAPISCH may delegate one bounded step to an available Codex skill or plugin
capability while remaining the sole route controller: request normalization,
role and risk selection, focused context, authority, human gates, durable
evidence, recovery, independent review, and final readiness stay with KAPISCH.
The expert control is `ecosystem=auto|off` (default `auto`); ordinary natural
language remains the normal interface, and an explicit skill or plugin mention
overrides `auto` as a binding capability constraint. Every delegation is
recorded under `.kapisch/runs/<task-id>/delegations/` — a route record plus one
context and evidence pair per step — even when the user selected
`handoff=chat`. See
[`ecosystem-routing.md`](skills/kapisch/references/ecosystem-routing.md), the
sole normative owner of selection and delegated-step behavior.

Delegation is currently supported only by durable version-3 graphs. A graph-free
workflow does not delegate: an explicit capability request blocks for the user
to promote the work to a durable graph or relax that constraint, while an
automatic selection may use native execution only when the approved outcome is
unchanged.

### Example: explicit delegation

The user names a skill, for example "run the checklist review of this diff
with the installed documentation-review skill." KAPISCH treats that name as a
binding constraint, selects it with `selection_mode=explicit`, persists the
step context before invocation, and records the requested and resolved
capability plus the observed result in `delegations/`. It never silently
substitutes another capability.

### Example: automatic read-only selection

The controller may automatically select a plugin-bundled read-only skill that
is visibly available in the current session for a bounded read-only substep,
recording `selection_mode=automatic` and a `repository-read` or `external-read`
effect class. Selection uses the capability's current documented description
and exposed actions, never name similarity alone, and never claims the visible
set is exhaustive. If the selected capability is unavailable, KAPISCH falls
back to native execution only when the same approved outcome remains achievable
without changing methodology, data boundary, or authority — and discloses the
fallback.

### Example: external-write gate

Preparation for an external write (for example posting a pull-request comment)
stops at the gate after preview. The controller presents the exact target and
payload and waits for explicit approval; only then does it execute with
`authority_mode=explicit-step` and a valid in-context `authority_ref`, and it
persists the external result (operation ID or URL when exposed) in the step's
evidence. Authority cannot be laundered through a delegate, and an
external-write or destructive step is never blindly retried on resume.

### Example: unavailable capability

If the user explicitly requires a capability that is unavailable, KAPISCH
blocks and reports the missing capability and a safe setup or selection action;
it never installs, enables, signs in to, or reconfigures anything as a
fallback. If only an automatically selected capability is unavailable, the
disclosed native fallback is used solely when the approved outcome is
unchanged.

## Development

Run `python scripts/test_portable_package.py` and the validator tests before
release. This verifies isolated portability, not installation through Codex. See [CONTRIBUTING.md](CONTRIBUTING.md),
[acceptance.md](docs/acceptance.md), and [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
