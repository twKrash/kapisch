---
name: kapisch
description: Use only when the user explicitly requests KAPISCH or repository-local authoritative instructions require KAPISCH.
---

# KAPISCH Pi adapter

The discovered canonical KAPISCH contract owns workflow and artifact semantics. Canonical contract path: `../../../../plugins/kapisch/skills/kapisch/SKILL.md`, resolved relative to this loaded Pi skill's directory. Read its current contents and resolve canonical normative references relative to that canonical skill directory; do not copy or duplicate canonical workflow instructions here. This adapter owns only Pi execution mechanics.

KAPISCH is explicitly opt-in. Ordinary Pi work MUST NOT activate KAPISCH just because it is complex or may benefit from planning, architecture work, or review. Activate it only when the user explicitly requests KAPISCH or authoritative repository-local instructions explicitly require it.

## Human-decision capture

The effective user-role input received from Pi is trusted under the selected host's trust model. The adapter does not authenticate the person, recover original keystrokes, or verify pre-extension input integrity. The extension captures the next non-empty text input only when the latest assistant message contains one complete, valid top-level `kapisch-decision` block; quoted, incomplete, nested, malformed, or superseded markers do not create decisions. It accepts these source kinds: `direct_operator`, `operator_reported_external`, and `external_artifact`. For this one-task Pi path, the extension is the designated human-input-boundary producer for captured `HumanDecision` records: it assigns `decision_id` and persists the immutable record once. The coordinator validates and binds that same record to the WorkOrder; it does not create or reconcile a second record. The raw answer, question, governing inputs, subject, scope, decision type, source kind, optional source reference and approving-party attribution are stored before forwarding under `.kapisch/runs/<Pi session ID>/decisions/<decision_id>.json`. The optional OS operator label is informational, not authentication. TUI, RPC, JSON, and print inputs are supported when the Pi session is persistent and project storage is writable; on missing session or storage failure, the pending answer stays blocked. An ambiguous answer remains raw evidence and must not be interpreted as approval. Downstream aggregation and Outcome processing must read and cite the persisted decision and its `decision_id`; agent or reviewer output alone never creates a HumanDecision. `/kapisch-decision` explains how to answer using normal Pi input, with no second prompt. `/kapisch-decision-dismiss` dismisses without granting authorization, and `/kapisch-decision-repair` requests regeneration of an invalid or interrupted request without creating a decision.

## Role mapping

Use `pi-subagents` and the exact canonical role selected by KAPISCH. Do not substitute generic Pi agents after KAPISCH controls the workflow:

- architect -> kapisch-architect
- researcher -> kapisch-researcher
- implementer -> kapisch-implementer
- implementer-lite -> kapisch-implementer-lite
- mechanic -> kapisch-mechanic
- reviewer -> kapisch-reviewer

If a mapped agent is unavailable, follow the canonical contract's blocking or escalation behavior; do not silently choose a different role. For the canonical contract's user-authorized one-task host-native exception only, dispatch the bounded task to Pi's native `worker` role and disclose explicitly that the runtime role is `worker`, not `kapisch-implementer`, along with its capabilities/limits. This is a task-specific host route, not a canonical role mapping or general fallback; ordinary canonical role mappings remain unchanged.

For this exception, follow the canonical file-based contract under
`.kapisch/runs/<run-id>`. This Pi package does not capture ordinary user input
as a HumanDecision, so the direct-prompt route is blocked unless the coordinator
has a bindable record from the designated producer. Never treat the initial
prompt itself as persisted authority. Use the host-persisted message reference
and its digest only to identify content Pi recorded, not as proof of physical
identity, original keystrokes, or pre-extension integrity. If a supported flow
produces a HumanDecision, include its persisted decision-file path and
`decision_id` in aggregation and Outcome references. Continue to apply the
canonical scope, applicability, and external-effect safeguards.

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
