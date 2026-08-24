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
