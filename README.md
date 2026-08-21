# KAPISCH local marketplace

This repository is the Git-backed local marketplace for KAPISCH. It is not an
OpenAI public Plugin Directory submission. Codex stores a configured marketplace
snapshot locally; users choose if and when to install or enable the plugin.

## Add the marketplace

### Development path (works today, no release tag required)

For day-to-day use against a source checkout (not a released install), add the
marketplace from this repository directly:

```text
codex plugin marketplace add ./path/to/kapisch          # local source checkout
codex plugin marketplace add twKrash/kapisch --ref main # or the live repo branch
```

This is the runnable development path. It intentionally does not use an
immutable released tag (none exists yet), and `main` / a local checkout is
mutable.

### Released path (once the immutable tag exists)

After the human release step publishes an immutable `>=0.2.0` tag, install from
that released revision:

```text
codex plugin marketplace add twKrash/kapisch --ref <release-tag>
```

Replace `<release-tag>` with the published immutable tag recorded in
[`plugins/kapisch/docs/acceptance-runtime.md`](plugins/kapisch/docs/acceptance-runtime.md).
The exact version/tag is chosen by the human release step; do not use mutable
`main` for a released installation.

Confirm that Codex knows the marketplace (either path):

```text
codex plugin marketplace list
```

## Install or enable KAPISCH later

Install from the configured local marketplace when ready:

```text
codex plugin add kapisch@kapisch-local
```

Alternatively, open `/plugins` in Codex CLI, choose **KAPISCH Local**, and
install or enable KAPISCH there. Start a new Codex session after installation so
the bundled skill is loaded.

This is the documented installation path, not proof of runtime acceptance. The
issue #11 acceptance record accumulates evidence in `plugins/kapisch/docs/acceptance-runtime.md`;
Linux immutable-install, installed-validator, live `$kapisch` invocation, and
shipped-agent-profile evidence are recorded there, while the native-Windows
runtime observation, isolated-auth clean flow, and the release sequence remain
outstanding and must be recorded before the issue can close.

Refresh the local marketplace snapshot after repository updates:

```text
codex plugin marketplace upgrade kapisch-local
```

The installable bundle and its full documentation live in
[`plugins/kapisch`](plugins/kapisch/README.md). The catalog is
[`marketplace.json`](.agents/plugins/marketplace.json).

`main` is mutable. The bundled manifest version is `0.1.0`, while current
changes remain `Unreleased`; neither state is an immutable released tag. A
release follows only after runtime acceptance records the accepted commit.

## License

Apache-2.0. See [LICENSE](LICENSE).
