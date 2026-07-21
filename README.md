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
missing profile. The script refuses collisions, never overwrites, renames, or
deletes profiles, records template and installed SHA-256 revisions under
`.kapisch/local-state/`, and reports later user-modification drift.

## Durable artifacts and migration

New artifacts live under `.kapisch/runs/<task-id>/`; cache and machine-local
state belong in `.kapisch/cache/` and `.kapisch/local-state/`. Add `.kapisch/`
to each consuming repository's `.gitignore`.

Legacy `.planning/task-workflow/` evidence is read-only migration input. A
migration is a user-approved copy-and-validate operation into `.kapisch/runs/`:
preserve the source, do not rewrite historical bytes, paths, digests, or
invocation records, and do not combine evidence between namespaces. If the
destination fails validation, retain the source and stop. KAPISCH never creates
new legacy artifacts.

## Validator

The validator uses only the Python 3.11 standard library and never writes,
dispatches, schedules, routes requests, invokes Git, or grants approval.

```text
python scripts/validate_kapisch.py --contract-dir skills/kapisch --task-dir .kapisch/runs/example
python -m unittest discover -s tests/kapisch_validation
```

## Development

Run the validator tests and plugin manifest validation before release. See
[CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
