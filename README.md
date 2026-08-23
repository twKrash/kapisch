# KAPISCH

KAPISCH gives Codex a compact, explainable workflow for planning, repository
work, independent review, and durable evidence validation. This repository is
the Git-backed `kapisch-local` marketplace; it is not an OpenAI public Plugin
Directory submission.

## Support

| Surface | Verified status for 1.0.1 |
| --- | --- |
| Windows 11 + Codex Desktop + WSL2 | Live release-baseline flow passed; exact release-SHA rerun remains a publication gate. |
| Linux | Live 1.0.0 flow passed; 1.0.1 automated suites pass on the unchanged runtime. |
| Native Windows, no WSL | Python 3.11 profile and portable-package suites pass; live plugin support is not yet claimed. |

Following [OpenAI's WSL guidance](https://learn.chatgpt.com/docs/windows/wsl),
keep both `CODEX_HOME` and consumer repositories in the Linux filesystem (for
example, `~/code`) rather than under `/mnt/c`.

## Quick start

Use the immutable 1.0.1 release tag:

```text
codex plugin marketplace add twKrash/kapisch --ref v1.0.1
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
specialized routing is needed. From a source checkout's repository root:

```text
python plugins/kapisch/scripts/setup_profile.py --all --project-dir <consumer-repository> --install
```

## Validator

The validator is read-only, uses the Python 3.11 standard library, and discovers
its bundled contracts automatically. Install it from the marketplace-cached
plugin directory or a source checkout; `<plugin-root>` is the directory that
contains the plugin's `pyproject.toml`:

```text
python -m pip install <plugin-root>
kapisch-validate --task-dir <consumer-repository>/.kapisch/runs/<task-id> --format json
```

## Documentation

- [Plugin guide](plugins/kapisch/README.md)
- [Windows 1.0.1 acceptance](plugins/kapisch/docs/acceptance-windows-v1.0.1.md)
- [Historical Unix 1.0.0 acceptance](plugins/kapisch/docs/acceptance-runtime.md)
- [Compatibility and rollback](plugins/kapisch/docs/compatibility.md)
- [Acceptance matrix](plugins/kapisch/docs/acceptance.md)
- [Marketplace catalog](.agents/plugins/marketplace.json)

## License

Apache-2.0. See [LICENSE](LICENSE).
