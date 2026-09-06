# KAPISCH

KAPISCH gives Codex a compact, explainable workflow for planning, repository
work, independent review, and durable evidence validation. This repository is
the Git-backed `kapisch-local` marketplace; it is not an OpenAI public Plugin
Directory submission.

## Support

| Surface | Verified status for the 2.0.0 release candidate |
| --- | --- |
| Windows 11 + Codex Desktop + WSL2 | Historical 1.0.1 release baseline passed; 2.0.0 live acceptance remains pending. |
| Linux | Historical live 1.0.0 flow passed; 2.0.0 automated evidence is recorded separately. |
| Native Windows, no WSL | Native Windows CI is required before release; success is not yet claimed. |

Following [OpenAI's WSL guidance](https://learn.chatgpt.com/docs/windows/wsl),
keep both `CODEX_HOME` and consumer repositories in the Linux filesystem (for
example, `~/code`) rather than under `/mnt/c`.

## Quick start

After the immutable 2.0.0 tag is published, the released installation command is:

```text
codex plugin marketplace add twKrash/kapisch --ref v2.0.0
codex plugin add kapisch@kapisch-local
```

Start a fresh Codex session after installation, then ask Codex to use
`$kapisch` for a repository task.

For development against mutable source:

```text
codex plugin marketplace add twKrash/kapisch --ref main
codex plugin add kapisch@kapisch-local
```

This is the runnable development path; do not use mutable `main` as a released
installation reference.

## Optional profiles

Plugin installation does not activate the six agent-profile templates. Install
them explicitly into a consumer repository when approval-capable review or
specialized routing is needed. **The legacy profile state is unsupported and is
not automatically migrated.** Follow the [manual cleanup procedure](plugins/kapisch/docs/compatibility.md#legacy-profile-cleanup)
before a fresh inspection and install.

```text
python plugins/kapisch/scripts/setup_profile.py --all --project-dir <consumer-repository> --install
```

New installations default to the cost-oriented `balanced` runtime profile set.
Profile sets change only Codex model/reasoning configuration; KAPISCH risk,
permissions, independent review, and final-readiness rules do not change. See
the [profile-set guide](plugins/kapisch/docs/profile-sets.md).

## Validator

The validator is read-only, uses the Python 3.11 standard library, and discovers
its bundled contracts automatically.

```text
python -m pip install <plugin-root>
kapisch-validate --task-dir <consumer-repository>/.kapisch/runs/<task-id> --format json
```

## Documentation

- [Plugin guide](plugins/kapisch/README.md)
- [Windows 2.0.0 acceptance record](plugins/kapisch/docs/acceptance-windows-v2.0.0.md)
- [Windows 1.0.1 historical acceptance](plugins/kapisch/docs/acceptance-windows-v1.0.1.md)
- [Historical Unix 1.0.0 acceptance](plugins/kapisch/docs/acceptance-runtime.md)
- [Compatibility and rollback](plugins/kapisch/docs/compatibility.md)
- [Acceptance matrix](plugins/kapisch/docs/acceptance.md)
- [Marketplace catalog](.agents/plugins/marketplace.json)

## License

Apache-2.0. See [LICENSE](LICENSE).
