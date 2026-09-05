# Contributing

Keep KAPISCH portable and small. Do not add dependencies, services, platform
forks, hidden schedulers, semantic routers, or approval engines.

For cross-platform work:

- use `pathlib` and explicit UTF-8 for text;
- hash raw bytes read in binary mode;
- prefer capability checks over OS-name branches; and
- test native Windows paths separately from WSL or mounted filesystems.

Behavior and durable-evidence changes need focused fixtures and tests. The
validator remains read-only structural verification; it does not dispatch,
write artifacts, infer authority, or decide semantic approval.

Run from `plugins/kapisch`:

```text
python -m unittest discover -s tests/kapisch_validation
python scripts/test_portable_package.py
python scripts/validate_kapisch.py --help
```

Under WSL, first confirm that `tempfile.gettempdir()` is on the Linux
filesystem. If it resolves under `/mnt/c`, prefix POSIX filesystem-sensitive
test commands with `TMPDIR=/tmp`; FIFO and permission semantics on a mounted
Windows filesystem are not representative Linux results.

Also run `python -m unittest discover -s tests` and `git diff --check` from the
repository root. Windows-sensitive changes must pass the profile and portable
suites on native Windows Python 3.11.

## Version decisions

Every PR that changes shipped plugin behavior makes an intentional semantic
version decision. Major is an intentional incompatible public, plugin, or
durable-contract break; minor is a backward-compatible feature, workflow/schema
capability, new durable version, or material runtime behavior; patch is a
backward-compatible bug fix. No bump is limited to non-shipping planning,
documentation, fixtures, tests, or unrelated metadata and must be explicit.

The shipped path set is `skills/`, `roles/`, `agents/`,
`kapisch_validation/`, `scripts/`, and `.codex-plugin/`. Run
`python ../../scripts/check_plugin_version.py --base <base-ref>` from this
directory (or the equivalent root command). It requires synchronized
`plugin.json`/`pyproject.toml` versions and a current changelog entry; a material
shipped-path change must increase the version.
