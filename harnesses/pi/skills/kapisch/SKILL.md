---
name: kapisch
description: Use only when the user explicitly requests KAPISCH or repository-local authoritative instructions require KAPISCH.
---

# KAPISCH Pi adapter

The discovered canonical KAPISCH contract owns workflow and artifact semantics. Canonical contract path: `../../../../plugins/kapisch/skills/kapisch/SKILL.md`, resolved relative to this loaded Pi skill's directory. Read its current contents and resolve canonical normative references relative to that canonical skill directory; do not copy or duplicate canonical workflow instructions here. This adapter owns only Pi execution mechanics.

KAPISCH is explicitly opt-in. Ordinary Pi work MUST NOT activate KAPISCH just because it is complex or may benefit from planning, architecture work, or review. Activate it only when the user explicitly requests KAPISCH or authoritative repository-local instructions explicitly require it.

## Human-decision capture

The effective user-role input received from Pi is trusted under the selected host's trust model. The adapter does not authenticate the person or require proof of original keystrokes or pre-extension integrity. The extension captures the next non-empty text input only when the latest assistant message contains one complete, valid top-level `kapisch-decision` block; quoted, incomplete, nested, malformed, or superseded markers do not create decisions. It accepts `direct_operator`, `operator_reported_external`, and `external_artifact` sources. For these pending-request answers, the extension is the sole producer and writes one immutable record under `.kapisch/runs/<Pi session ID>/decisions/<decision_id>.json` before forwarding; the coordinator binds that same record and never duplicates it. External-artifact requests require a stable `source_ref`. TUI, RPC, JSON, and print input are supported when the Pi session is persistent and project storage is writable; on missing session or storage failure, a pending answer stays blocked. Ambiguous answers remain raw evidence and are not interpreted as approval.

For the one-task direct-prompt route, an explicit and unambiguous user instruction that bounds the task and scope is already authorization; do not ask the user to approve that same scope again. The coordinator may materialize exactly one `HumanDecision` using the existing portable fields and `.kapisch/runs/<run-id>/decisions/<decision_id>.json` layout, using the existing fields with a unique `decision_id` and `question_id`, the request verbatim in `question` and `answer`, relevant existing `governing_inputs`, the authorized `subject` and `scope`, `decision_type=approval`, and `source_kind=direct_operator`. A stable host message ID may be used as `question_id`; do not require a message digest or other input-provenance proof. Bind that same `decision_id` to the WorkOrder. The direct path is the coordinator's record for that user instruction; the input extension does not auto-capture ordinary prompts, and must not create a second record for it. If the prompt is ambiguous or unbounded, clarify before persisting authorization or dispatching. A host message reference identifies stored text; it does not prove physical identity or original keystrokes. Downstream aggregation and Outcome cite the persisted decision and its `decision_id`; agent or reviewer output alone never creates a HumanDecision. `/kapisch-decision` explains how to answer an explicit pending request using normal Pi input, with no second prompt. `/kapisch-decision-dismiss` dismisses without granting authorization, and `/kapisch-decision-repair` requests regeneration of an invalid request without creating a decision.
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
`.kapisch/runs/<run-id>`. An explicit, unambiguous user prompt that bounds the
one task and its scope is authorization; do not ask for redundant approval. The
coordinator may materialize exactly one `HumanDecision` in the existing
`decisions/<decision_id>.json` layout, using the existing fields with a unique `decision_id` and `question_id`, the
request verbatim in `question` and `answer`, relevant existing
`governing_inputs`, the authorized `subject` and `scope`,
`decision_type=approval`, and `source_kind=direct_operator`. A stable host
message ID may be used as `question_id`; do not require a message digest or
other input-provenance proof. Bind that same `decision_id` to the
WorkOrder. The extension only persists answers to explicit pending decision
requests; it does not auto-record ordinary input or duplicate the coordinator's
direct-prompt record. Clarify ambiguous or unbounded instructions before
recording approval or dispatching. A host message reference identifies stored text, not physical identity or original keystrokes. On resume, resolve
and validate the decision's immutable source and governing inputs, then
reassess applicability; missing, stale, or mismatched evidence blocks. Continue
to apply the canonical scope and external-effect safeguards.

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
