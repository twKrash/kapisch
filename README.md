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

This is the runnable development path against mutable code. For a released
installation, use the published immutable tag `v1.0.0` instead (see "Released
path" below).

### Released path (immutable tag `v1.0.0`)

Install from the released immutable revision:

```text
codex plugin marketplace add twKrash/kapisch --ref v1.0.0
```

This is the published immutable tag; use it (or any later release tag) rather
than mutable `main` for a released installation. The exact accepted revision is
recorded in [`plugins/kapisch/docs/acceptance-runtime.md`](plugins/kapisch/docs/acceptance-runtime.md).

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
issue #11 clean Unix-like runtime acceptance for release **1.0.0** (tag
`v1.0.0`) is recorded in `plugins/kapisch/docs/acceptance-runtime.md`:
immutable-install, installed-validator (`[]`/exit 0), live `$kapisch`
invocation, and shipped-agent-profile evidence. Native-Windows Codex runtime
acceptance is deferred to [issue #21](https://github.com/twKrash/kapisch/issues/21)
(for the `v1.0.1` patch), so it is not a blocker for closing the Unix-facing
release work in #11.

Refresh the local marketplace snapshot after repository updates:

```text
codex plugin marketplace upgrade kapisch-local
```

The installable bundle and its full documentation live in
[`plugins/kapisch`](plugins/kapisch/README.md). The catalog is
[`marketplace.json`](.agents/plugins/marketplace.json).

`main` is mutable. The current released version is **1.0.0** (immutable tag
`v1.0.0`); changes made after this release live under `Unreleased` until the
next release. Use the immutable tag for released installations, not `main`.

## License

Apache-2.0. See [LICENSE](LICENSE).
