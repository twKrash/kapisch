# KAPISCH

KAPISCH is a lightweight Codex-native workflow contract and validation plugin
for safe, explainable repository work. It supplies portable role contracts,
human approval gates, and a read-only Python 3.11 validator for durable TOML
evidence; Codex remains responsible for agent dispatch, model selection, and
sandboxing.

## Install

Install this repository as a Codex plugin, then invoke `$kapisch` in a
repository task. The plugin works without custom agent profiles, but that
degraded mode is advisory only: independent review and final-readiness approval
require an explicitly installed, successfully invoked reviewer profile.

## Optional profiles

`agents/` contains templates only. They are not activated by plugin installation.
After reviewing a template, use `scripts/setup_profile.py --role reviewer` to
inspect the project-scoped target and rerun it with `--install` only to copy a
missing profile. For a user-scoped target, use
`--scope user` (use `--user-dir` only for a controlled alternate home). The script
refuses filename and profile-identity collisions, never overwrites, renames, or
deletes profiles, records template and installed SHA-256 revisions under the
matching `.kapisch/local-state/`, and reports installed-profile and template
drift. See [compatibility.md](docs/compatibility.md) for removal and rollback.

## Durable artifacts and migration

New artifacts live under `.kapisch/runs/<task-id>/`; cache and machine-local
state belong in `.kapisch/cache/` and `.kapisch/local-state/`. Add `.kapisch/`
to each consuming repository's `.gitignore`.

Legacy `.planning/KAPISCH/<task-id>/` evidence is read-only migration input
under compatibility version 1. Run
`python scripts/migrate_legacy_run.py --task-id <task-id> --approve` to perform
the explicit copy-and-validate operation into `.kapisch/runs/`. It preserves the
source, does not rewrite historical bytes, paths, digests, or invocation
records, and does not combine evidence between namespaces. If validation fails,
it retains the source and creates no destination. KAPISCH never creates new
legacy artifacts.

## Validator

The validator uses only the Python 3.11 standard library and never writes,
dispatches, schedules, routes requests, invokes Git, or grants approval.

```text
python scripts/validate_kapisch.py --contract-dir skills/kapisch --task-dir .kapisch/runs/example
python -m unittest discover -s tests/kapisch_validation
```

## Development

Run `python scripts/test_clean_install.py` and the validator tests before
release. See [CONTRIBUTING.md](CONTRIBUTING.md),
[acceptance.md](docs/acceptance.md), and [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
