# KAPISCH plugin

KAPISCH is a Codex-native workflow contract with portable agent roles, explicit
human gates, durable `.kapisch/runs/` evidence, and a read-only Python validator.
Codex continues to own agent dispatch, model selection, and sandboxing.

## Install

This plugin is distributed through the Git-backed `kapisch-local` marketplace,
not the OpenAI public Plugin Directory. After an authorized maintainer publishes
the immutable `v2.0.0` tag, install it with:

```text
codex plugin marketplace add twKrash/kapisch --ref v2.0.0
codex plugin add kapisch@kapisch-local
```

For mutable development only:

```text
codex plugin marketplace add twKrash/kapisch --ref main
codex plugin add kapisch@kapisch-local
```

The release tag is immutable; `main` is mutable. Start a fresh Codex session
after installation so `$kapisch` is available.

## Use

```text
Use $kapisch to fix the reconnect bug and add a regression test.
Use $kapisch with DURABLE end-to-end execution for this approved plan.
Use $kapisch to review my current branch before I open a PR.
```

New durable runs live under `.kapisch/runs/<task-id>/`. Add `.kapisch/` to the
consumer repository's `.gitignore`.

## Optional profiles

The templates in `agents/` are not activated by plugin installation. First
inspect a fresh target, then explicitly install it:

```text
python scripts/setup_profile.py --role reviewer --project-dir <consumer-repository>
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set balanced --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set quality --install
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget --install
```

`profile_state_version = 1` is the current local-state schema, not the plugin
version. New installs default to `balanced`; select `quality` or `budget` only
when intended. Same-set or changed-routing/profile-set updates are detected but
require explicit replacement:

```text
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget
python scripts/setup_profile.py --all --project-dir <consumer-repository> --profile-set budget --install --replace-managed
```

Setup refuses drift and identity/catalog collisions. Unsupported legacy state is
diagnostic-only: it receives no automatic migration or cleanup. Use the
[Manual cleanup procedure](docs/compatibility.md#legacy-profile-cleanup), then
inspect and install again. Removing the plugin and removing optional profiles
are separate operations; plugin removal does not remove profiles, and profile
removal is a deliberate user action.

See [profile sets](docs/profile-sets.md) for routing, replacement, recovery, and
legacy outcomes.

## Validator

The validator uses only the Python 3.11 standard library. It reads durable TOML
evidence; it never dispatches agents, writes artifacts, invokes Git, or grants
approval.

```text
python -m pip install <plugin-root>
kapisch-validate --task-dir <consumer-repository>/.kapisch/runs/example --format json
python <plugin-root>/scripts/validate_kapisch.py --task-dir <consumer-repository>/.kapisch/runs/example
```

## Compatibility

Version-1 through version-4 durable manifests remain readable. Version-4
snapshots include a derived controller view; version-3 runs migrate to version 4
only through the explicit copy-and-validate command. Older
`.planning/task-workflow/<task-id>/` runs remain read-only inputs and migrate
only through the explicit approved command:

```text
python scripts/migrate_legacy_run.py --project-dir <consumer-repository> --task-id <task-id> --approve
```

Windows 11
with Codex Desktop and WSL2 is the release-blocking Windows surface. Native
Windows CI is required before release; live no-WSL support is not yet claimed.
See [compatibility.md](docs/compatibility.md).

## Development checks

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
- [Durable-run legacy migration and profile compatibility](docs/compatibility.md)
- [Profile sets and switching](docs/profile-sets.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Change 7 execution history and acceptance plan](docs/change-7-execution-plan.md)

## License

Apache-2.0. See [LICENSE](LICENSE).
