# Bundled script usage

## Resolve the plugin root

The consumer repository is the target for task paths; it may differ from the command's current working directory. It is not the KAPISCH plugin root. Never resolve `scripts/` from `$PWD` or guess a checkout path.

Pi includes each discovered skill's path in its system prompt. Use that runtime path for the active KAPISCH Pi skill, then follow the canonical skill path already declared by the Pi adapter. Once that canonical `SKILL.md` is loaded, retain its resolved file path. Its directory is `<plugin-root>/skills/kapisch`; resolve `../..` from that directory to get `<plugin-root>`. Use the resulting absolute path in shell commands. This derives the location at runtime; do not hard-code a machine-specific checkout path, search the consumer repository, or read guessed settings/files. If the active skill path is unavailable, ask for the KAPISCH install path rather than guessing.

From any working directory, invoke a bundled script like this, substituting the runtime-resolved plugin root and absolute consumer path:

```sh
python "<plugin-root>/scripts/validate_kapisch.py" \
  --task-dir "<consumer-repository>/.kapisch/runs/<task-id>"
```

The installed `kapisch-validate` command is also usable when already available on `PATH`; do not assume Pi or another host installed it. `--help` is available on the CLI scripts below for exact options. `test_portable_package.py` is a test runner, not a CLI.

## Script inventory and safety

| Script | Purpose and safety |
|---|---|
| `validate_kapisch.py` | Read-only structural validation. Preferred direct invocation when the console command is unavailable. |
| `setup_profile.py` | Normal inspection is read-only. An interrupted managed-profile switch may trigger recovery even without `--install`, restoring managed profile files. Treat recovery as writing; run only when requested and authorized. Pass `--project-dir` explicitly; `--install` writes profiles, and `--replace-managed` replaces managed profiles. |
| `migrate_legacy_run.py` | Copies a legacy run into `.kapisch/runs/`; requires `--approve`. Migration changes the target repository, so run only for an explicitly requested migration and pass `--project-dir` explicitly. |
| `migrate_controller_view_v4.py` | Copies and migrates a v3 task directory to a v4 destination; requires `--approve` and writes the destination. Use only for an explicitly requested migration. |
| `render_controller_view.py` | Regenerates derived controller-view/state files inside a task directory. It writes artifacts; do not run as a generic repair or validation step. |
| `compare_controller_benchmark.py` | Reads baseline/candidate benchmark JSONL and prints a comparison. Maintainer analysis tool, not part of normal task execution. |
| `test_portable_package.py` | Runs the portable-package maintainer check. Do not run as a task helper. |

The required CLI flags do not replace user authorization. Prefer validation for inspection; do not invoke migration, installation, or rendering scripts to repair user data without explicit direction.
