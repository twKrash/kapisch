# KAPISCH local marketplace

This repository is the Git-backed local marketplace for KAPISCH. It is not an
OpenAI public Plugin Directory submission. Codex stores a configured marketplace
snapshot locally; users choose if and when to install or enable the plugin.

## Add the marketplace from GitHub

Configure the marketplace without installing KAPISCH:

```text
codex plugin marketplace add twKrash/kapisch --ref main
```

Confirm that Codex knows the marketplace:

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

This is the documented installation path, not proof of runtime acceptance:
clean installation, discovery, reviewer invocation, and `$kapisch` acceptance
remain planned under [issue #11](https://github.com/twKrash/kapisch/issues/11).

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
