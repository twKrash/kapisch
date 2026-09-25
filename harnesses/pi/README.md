# KAPISCH Pi package

Local Pi package exposing the thin KAPISCH skill and six canonical KAPISCH roles through pi-subagents. It adds no runtime extension and does not alter KAPISCH workflow semantics.

## Install and update

Prerequisites: Pi 0.87.1 or later, pi-subagents 0.71.0 or later, and a local KAPISCH checkout.

From the consumer project, install project-locally so Pi does not change `~/.pi/agent/settings.json`:

```sh
cd /path/to/consumer
pi install --local /absolute/path/to/kapisch/harnesses/pi
```

This records the package in the consumer project's `.pi/settings.json`; Pi package installation cannot discover resources without a package entry. The package loads in place (no copies to `~/.pi`). To update a local-path install, update the KAPISCH checkout and run `/reload` in Pi. To remove it, run `pi remove --local /absolute/path/to/kapisch/harnesses/pi`.

## Included agents

`kapisch-architect`, `kapisch-researcher`, `kapisch-implementer`, `kapisch-implementer-lite`, `kapisch-mechanic`, and `kapisch-reviewer`. The skill is explicitly opt-in: use only when the user requests KAPISCH or authoritative repository-local instructions require it.

Canonical model IDs become Pi `openai-codex/<model-id>` IDs; reasoning effort maps unchanged to Pi `thinking`. Defaults: architect and reviewer `gpt-6-sol`/high; researcher, implementer, implementer-lite, and mechanic `gpt-6-luna` with medium effort except mechanic at low. User/project `agentOverrides` and per-run overrides take precedence over package defaults.

## Capabilities and limitations

Read-only roles omit Pi `edit` and `write` tools and deny those tools through native child permissions. Writers receive `edit` and `write`; no role enables nested subagents. Researcher and reviewer receive Bash for required Git/history and focused evidence operations. pi-subagents cannot constrain Bash commands, so Bash is not shell-level read-only and must not be described as enforced read-only behavior. No user-specific extension or discovery tool is required. Optional tools may aid navigation but are not canonical evidence or authority.

## Generate and validate

Bun and Python 3.11+ (for the standard-library TOML parser) are development prerequisites. Run from the repository root:

```sh
bun run --cwd harnesses/pi generate
bun run --cwd harnesses/pi check:generated
bun test harnesses/pi/tests/*.test.ts
```

Generation updates committed `agents/*.md`; the check command only compares expected output and never writes. CI runs the check and tests. Package version is lockstep with canonical KAPISCH release metadata (`plugins/kapisch/.codex-plugin/plugin.json` and `plugins/kapisch/pyproject.toml`); version drift fails tests.
