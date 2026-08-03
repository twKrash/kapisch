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

```text
python scripts/validate_kapisch.py --contract-dir skills/kapisch --task-dir <consumer-repository>/.kapisch/runs/example
python -m unittest discover -s tests/kapisch_validation
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

## Development

Run `python scripts/test_portable_package.py` and the validator tests before
release. This verifies isolated portability, not installation through Codex. See [CONTRIBUTING.md](CONTRIBUTING.md),
[acceptance.md](docs/acceptance.md), and [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
