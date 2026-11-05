# KAPISCH Pi package

Local Pi package exposing the thin KAPISCH skill, six canonical roles through pi-subagents, and an adapter that captures explicit HumanDecision answers from Pi's effective user input.

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

Canonical model IDs become Pi `openai/<model-id>` IDs; reasoning effort maps unchanged to Pi `thinking`. Defaults: architect and reviewer `gpt-6.1-sol`/high; researcher, implementer, implementer-lite, and mechanic `gpt-6-luna` with medium effort except mechanic at low. User/project `agentOverrides` and per-run overrides take precedence over package defaults.

## Capabilities and limitations

The `human-decisions.ts` extension trusts effective user-role text delivered to Pi; it does not authenticate the person or require original-keystroke or pre-extension integrity proof. For a complete, valid top-level `kapisch-decision` block in the latest assistant message, it records the next non-empty answer verbatim before forwarding. It supports TUI, RPC, JSON, and print input. A request carrying `run_id` needs only writable project storage; a request without `run_id` also needs a persistent Pi session, and stays blocked if that session or the write is unavailable. A task-first `kapisch-decision` request may include an opaque portable `run_id`; when present, the extension writes `.kapisch/runs/<run_id>/decisions/<decision_id>.json`, keeping the Pi session ID out of portable references and decision identity. Requests without `run_id` retain the adapter-local session path for existing non-task-first use. Records preserve the question, governing inputs, subject, scope, source kind, and available source reference or approving-party attribution.

The canonical KAPISCH skill owns direct-prompt authorization and the one-task file-based artifact lifecycle. This package's input extension records answers only for explicit pending decision requests; it does not capture ordinary prompts or create coordinator-owned direct-prompt records. `/kapisch-decision` explains how to answer a pending request through normal Pi input; `/kapisch-decision-dismiss` dismisses without authorization; `/kapisch-decision-repair` requests regeneration without creating a decision.

Read-only roles omit Pi `edit` and `write` tools and deny those tools through native child permissions. Writers receive `edit` and `write`; no role enables nested subagents. Researcher and reviewer receive Bash for required Git/history and focused evidence operations. pi-subagents cannot constrain Bash commands, so Bash is not shell-level read-only and must not be described as enforced read-only behavior. No model-callable decision-writing tool is added. Optional tools may aid navigation but are not canonical evidence or authority.

## Generate and validate

Bun and Python 3.11+ (for the standard-library TOML parser) are development prerequisites. Run from the repository root:

```sh
bun run --cwd harnesses/pi generate
bun run --cwd harnesses/pi check:generated
bun test harnesses/pi/tests/*.test.ts
```

Generation updates committed `agents/*.md`; the check command only compares expected output and never writes. CI runs the check and tests. Package version is lockstep with canonical KAPISCH release metadata (`plugins/kapisch/.codex-plugin/plugin.json` and `plugins/kapisch/pyproject.toml`); version drift fails tests.

The bounded one-task path follows the portable record contract in `core/contracts/task-first.md`. Keep Pi session and child handles adapter-owned; report each required capability as supported, unsupported, or unknown with a reason, and block when a required capability is not proven supported.
