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

The `human-decisions.ts` extension trusts effective user-role text delivered to Pi; it does not authenticate the person or require original-keystroke or pre-extension integrity proof. For a complete, valid top-level `kapisch-decision` block in the latest assistant message, it records the next non-empty answer verbatim before forwarding. It supports TUI, RPC, JSON, and print input when Pi has a persistent session and writable project storage; pending answers remain blocked if the session or write is unavailable. These extension-produced records use `.kapisch/runs/<Pi session ID>/decisions/<decision_id>.json` and preserve the request, subject, scope, source kind, and available source reference or approving-party attribution.

For the bounded one-task path, an explicit, unambiguous user prompt that authorizes the task and its scope needs no redundant approval question. The coordinator may materialize exactly one `HumanDecision` from the user request using the existing portable record format under `.kapisch/runs/<run-id>/decisions/<decision_id>.json`; use the existing HumanDecision fields with a unique `decision_id` and `question_id`, preserve the request verbatim in `question` and `answer`, include only relevant existing `governing_inputs`, set the authorized `subject` and `scope`, `decision_type=approval`, and `source_kind=direct_operator`, then bind that `decision_id` to the WorkOrder. A stable host message ID may be used as `question_id`; no message digest or other input-provenance proof is required. The pending-answer extension does not capture ordinary input and must not write a competing direct-prompt record. Ambiguous or unbounded input requires clarification before any approval record or dispatch. A host message reference identifies stored text; it does not authenticate identity or prove original keystrokes. Host-session details stay adapter-owned and out of the portable decision fields. Downstream aggregation and Outcome must cite the same decision. Agent and reviewer output alone never creates a HumanDecision. `/kapisch-decision` explains how to answer a pending request through normal Pi input, with no second prompt; `/kapisch-decision-dismiss` dismisses without authorization, and `/kapisch-decision-repair` requests regeneration without creating a decision.

Read-only roles omit Pi `edit` and `write` tools and deny those tools through native child permissions. Writers receive `edit` and `write`; no role enables nested subagents. Researcher and reviewer receive Bash for required Git/history and focused evidence operations. pi-subagents cannot constrain Bash commands, so Bash is not shell-level read-only and must not be described as enforced read-only behavior. No model-callable decision-writing tool is added. Optional tools may aid navigation but are not canonical evidence or authority.

## Generate and validate

Bun and Python 3.11+ (for the standard-library TOML parser) are development prerequisites. Run from the repository root:

```sh
bun run --cwd harnesses/pi generate
bun run --cwd harnesses/pi check:generated
bun test harnesses/pi/tests/*.test.ts
```

Generation updates committed `agents/*.md`; the check command only compares expected output and never writes. CI runs the check and tests. Package version is lockstep with canonical KAPISCH release metadata (`plugins/kapisch/.codex-plugin/plugin.json` and `plugins/kapisch/pyproject.toml`); version drift fails tests.
