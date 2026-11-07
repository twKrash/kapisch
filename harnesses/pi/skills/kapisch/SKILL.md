---
name: kapisch
description: Use only when the user explicitly requests KAPISCH or repository-local authoritative instructions require KAPISCH.
---

# KAPISCH Pi adapter

The discovered canonical KAPISCH contract owns workflow and artifact semantics. Canonical contract path: `../../../../plugins/kapisch/skills/kapisch/SKILL.md`, resolved relative to this loaded Pi skill's directory. Before any workflow selection or dispatch, use Pi's `read` tool to load the complete current canonical `SKILL.md`; do not use `grep`, search snippets, or agent summaries as a substitute. If the tool reports truncation, continue with `read` offsets until the file ends. Then read the normative references required by the selected workflow. If the canonical contract cannot be loaded completely, stop before classifying or dispatching. This adapter owns only Pi-specific loading and execution mechanics; canonical workflow instructions remain in the shared contract.

KAPISCH is explicitly opt-in. Ordinary Pi work MUST NOT activate KAPISCH just because it is complex or may benefit from planning, architecture work, or review. Activate it only when the user explicitly requests KAPISCH or authoritative repository-local instructions explicitly require it.

## Human-decision capture

The effective user-role input received from Pi is trusted under the selected host's trust model. The adapter does not authenticate the person or require proof of original keystrokes or pre-extension integrity. The extension captures the next non-empty text input only when the latest assistant message contains one complete, valid top-level `kapisch-decision` block; quoted, incomplete, nested, malformed, or superseded markers do not create decisions. It accepts `direct_operator`, `operator_reported_external`, and `external_artifact` sources. Each task-first request must include its owning Run's canonical lowercase UUIDv4 `run_id`; missing or malformed IDs are invalid and remain blocked. The extension writes only into an existing Run folder without `dispatch-claim.json`; otherwise it blocks the input and warns that the request may carry a wrong Run id (for example after context compaction), so `/kapisch-decision-repair` can regenerate it. The extension never substitutes Pi session identity. For a valid request, it is the sole HumanDecision producer at this Pi input boundary and writes one immutable record before forwarding to `<state_root>/.kapisch/runs/<run_id>/decisions/<decision_id>.json`. It derives `state_root` as the primary checkout from the session cwd and fails closed when Git is unavailable or the checkout/common-directory mapping is unsupported. The core separately receives `source_root`, the checkout whose Git inputs are assessed, and validates it against `state_root`. Decisions are Run-local: no decision file from another Run is consulted or reused as authority. External-artifact requests require a stable `source_ref`. TUI, RPC, JSON, and print input are supported. Records preserve decision facts and contain no Pi session ID. Ambiguous answers remain raw evidence and are not interpreted as approval.

This extension captures only answers to explicit pending decision requests. Ordinary direct prompts are not auto-captured; the coordinator owns direct-prompt records under the canonical one-task contract, and this extension must not duplicate them. `/kapisch-decision` explains how to answer a pending request through normal Pi input; `/kapisch-decision-dismiss` dismisses without granting authorization; `/kapisch-decision-repair` requests regeneration without creating a decision. For a structurally valid request whose Run is missing or already dispatched, it rechecks persisted Run state when invoked and requests a replacement for the current active Run; it never grants authorization.
## Role mapping

Use `pi-subagents` and the exact canonical role selected by KAPISCH. Do not substitute generic Pi agents after KAPISCH controls the workflow:

- architect -> kapisch-architect
- researcher -> kapisch-researcher
- implementer -> kapisch-implementer
- implementer-lite -> kapisch-implementer-lite
- mechanic -> kapisch-mechanic
- reviewer -> kapisch-reviewer

If a mapped agent is unavailable, follow the canonical contract's blocking or escalation behavior; do not silently choose a different role. For the canonical contract's user-authorized one-task host-native exception only, dispatch the bounded task to Pi's native `worker` role and disclose explicitly that the runtime role is `worker`, not `kapisch-implementer`, along with its capabilities/limits. This is a task-specific host route, not a canonical role mapping or general fallback; ordinary canonical role mappings remain unchanged.

For `workflow=review`, dispatch exactly one fresh `kapisch-reviewer` child with
an explicit `review_mode=standalone` marker, the requested review scope, and
criteria. Do not create a durable graph or review-evidence artifacts; return the
reviewer's findings to the parent/orchestrator for judgment. This mode is
separate from reviewer dispatch inside task/milestone execution.

## Execution boundary

Use fresh child contexts by default. Send bounded task packets and canonical artifact references, not full parent history or duplicated reports. Keep canonical evidence and artifact contracts authoritative; Pi transcripts are not portable evidence unless KAPISCH says otherwise. Record only observable Pi provenance and do not invent evidence equivalence.

Model and reasoning defaults come from each agent's generated Pi configuration. Operator or project agent overrides may replace those defaults. Do not choose a model manually, assume fallback, or treat model availability as authority.

Pi tools do not grant permission. Preserve canonical authority, safety, approval, independent-review, evidence, recovery, and readiness requirements. Independent review requires a distinct `kapisch-reviewer` invocation. Treat canonical KAPISCH distribution as read-only workflow source; current task artifacts belong to the consumer repository.

Pi cannot enforce command-level restrictions on `bash`; child Bash calls pass through. Tool allowlists and native tool permissions do not make shell execution read-only. Do not claim that Pi runtime alone prevents shell-side mutation.
