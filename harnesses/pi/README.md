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

The `human-decisions.ts` extension trusts the effective user-role text delivered to Pi's `input` handler; it does not authenticate the person or verify original keystrokes or pre-extension integrity. For a complete, valid top-level `kapisch-decision` block in the latest assistant message, it records the next non-empty text answer verbatim before forwarding it. It supports TUI, RPC, JSON, and print input when Pi has a persistent session and writable project storage; pending decisions remain blocked if the session or write is unavailable. Each record is stored under `.kapisch/runs/<Pi session ID>/decisions/<decision_id>.json` with its question, governing inputs, subject, scope, decision type, source kind, and available source reference or approving-party attribution. The portable decision record contains no OS username or host-session identifiers; Pi-specific storage metadata remains adapter-owned. For the one-task Pi path, this input extension is the sole HumanDecision producer at the human input boundary: it assigns `decision_id` and persists the immutable record once. The coordinator validates and binds that record's `decision_id` to the WorkOrder; it does not create a competing record. Decisions reported from meetings, wiki pages, or issues must enter through the active human input boundary under the same contract, not through a separate producer. Ambiguous answers remain raw evidence and are not converted into approval. Downstream aggregation and Outcome processing must read and cite the same record; agent and reviewer output alone never creates a HumanDecision. `/kapisch-decision` explains that the user should answer through normal Pi input; it does not open a second prompt. `/kapisch-decision-dismiss` dismisses without granting authorization, and `/kapisch-decision-repair` requests regeneration of malformed or interrupted requests without creating a decision. The canonical contract permits a direct-prompt WorkOrder only when the coordinator can persist and bind its HumanDecision. This Pi package does not capture ordinary input as a HumanDecision, so the direct-prompt one-task route is not supported here; block that route here unless a bindable record exists from the designated producer. The extension captures only answers to pending decision requests.

Read-only roles omit Pi `edit` and `write` tools and deny those tools through native child permissions. Writers receive `edit` and `write`; no role enables nested subagents. Researcher and reviewer receive Bash for required Git/history and focused evidence operations. pi-subagents cannot constrain Bash commands, so Bash is not shell-level read-only and must not be described as enforced read-only behavior. No model-callable decision-writing tool is added. Optional tools may aid navigation but are not canonical evidence or authority.

## Generate and validate

Bun and Python 3.11+ (for the standard-library TOML parser) are development prerequisites. Run from the repository root:

```sh
bun run --cwd harnesses/pi generate
bun run --cwd harnesses/pi check:generated
bun test harnesses/pi/tests/*.test.ts
```

Generation updates committed `agents/*.md`; the check command only compares expected output and never writes. CI runs the check and tests. Package version is lockstep with canonical KAPISCH release metadata (`plugins/kapisch/.codex-plugin/plugin.json` and `plugins/kapisch/pyproject.toml`); version drift fails tests.
