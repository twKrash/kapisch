# KAPISCH plugin

KAPISCH is a Codex-native workflow contract with portable agent roles, explicit
human gates, durable `.kapisch/runs/` evidence, and a read-only Python validator.
Codex continues to own agent dispatch, model selection, and sandboxing.

## Install

This plugin is distributed through the Git-backed `kapisch-local` marketplace,
not the OpenAI public Plugin Directory.

Released installation:

```text
codex plugin marketplace add twKrash/kapisch --ref v1.0.1
codex plugin add kapisch@kapisch-local
```

Development installation from a local checkout:

```text
codex plugin marketplace add ./path/to/kapisch
codex plugin add kapisch@kapisch-local
```

Or track mutable `main` instead:

```text
codex plugin marketplace add twKrash/kapisch --ref main
codex plugin add kapisch@kapisch-local
```

The release tag is immutable; `main` and local checkouts are mutable. Start a
fresh Codex session after installation so `$kapisch` is available, as required
by the [Codex plugin workflow](https://learn.chatgpt.com/docs/plugins).

## Use

Natural language is the normal interface:

```text
Use $kapisch to fix the reconnect bug and add a regression test.
Use $kapisch with DURABLE end-to-end execution for this approved plan.
Use $kapisch to review my current branch before I open a PR.
```

New durable runs live under `.kapisch/runs/<task-id>/`. Add `.kapisch/` to the
consumer repository's `.gitignore`.

## Optional profiles

The templates in `agents/` are not activated by plugin installation. From this
plugin directory, inspect a target before installing it:

```text
python scripts/setup_profile.py --role reviewer --project-dir <consumer-repository>
python scripts/setup_profile.py --role reviewer --project-dir <consumer-repository> --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --install
```

Setup refuses collisions and never overwrites, renames, or deletes an existing
profile. It records and reports template and installed hashes, identity, and
drift. Project scope is the default; `--scope user` is available when explicitly
required.

## Validator

The validator uses only the Python 3.11 standard library. It reads durable TOML
evidence; it never dispatches agents, writes artifacts, invokes Git, or grants
approval.

```text
python -m pip install <plugin-root>
kapisch-validate --task-dir <consumer-repository>/.kapisch/runs/example --format json
python <plugin-root>/scripts/validate_kapisch.py --task-dir <consumer-repository>/.kapisch/runs/example
```

`--contract-dir` remains an expert override and is unnecessary for a normal
installed validation.

## Compatibility

Version-1 and version-2 durable manifests remain readable. Legacy
`.planning/task-workflow/<task-id>/` runs are read-only inputs and move only
through the explicit copy-and-validate command:

```text
python scripts/migrate_legacy_run.py --project-dir <consumer-repository> --task-id <task-id> --approve
```

Windows 11 with Codex Desktop and WSL2 is the release-blocking Windows surface.
Native Windows profile setup and portable-package tests pass on Python 3.11;
live no-WSL plugin support is claimed only after a complete observed run. See
[compatibility.md](docs/compatibility.md) and the
[Windows acceptance record](docs/acceptance-windows-v1.0.1.md).

## Development checks

From this directory:

```text
python -m unittest discover -s tests/kapisch_validation
python scripts/test_portable_package.py
python scripts/validate_kapisch.py --help
```

From the repository root, also run `python -m unittest discover -s tests` and
`git diff --check`.

## More documentation

- [Public workflow contract](skills/kapisch/SKILL.md)
- [Acceptance status](docs/acceptance.md)
- [Compatibility and rollback](docs/compatibility.md)
- [Roadmap](docs/roadmap.md)
- [Change 7 execution history and acceptance plan](docs/change-7-execution-plan.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
