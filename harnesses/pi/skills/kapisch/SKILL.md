---
name: kapisch
description: Use only when the user explicitly requests KAPISCH or repository-local authoritative instructions require KAPISCH.
---

# KAPISCH Pi adapter

The discovered canonical KAPISCH contract owns workflow and artifact semantics. Canonical contract path: `../../../../plugins/kapisch/skills/kapisch/SKILL.md`, resolved relative to this loaded Pi skill's directory. Read its current contents and resolve canonical normative references relative to that canonical skill directory; do not copy or duplicate canonical workflow instructions here. This adapter owns only Pi execution mechanics.

KAPISCH is explicitly opt-in. Ordinary Pi work MUST NOT activate KAPISCH just because it is complex or may benefit from planning, architecture work, or review. Activate it only when the user explicitly requests KAPISCH or authoritative repository-local instructions explicitly require it.

## Human-decision capture

HumanDecision capture is unavailable on this Pi runtime because the host cannot establish immutable original-input provenance. Do not create new `kapisch-decision` request blocks or treat the persisted current user prompt, `ui.input()` results, or ordinary chat text as authority. The one-task direct-prompt WorkOrder route is unsupported and fails closed until Pi supplies immutable original-input provenance. If a workflow requires a HumanDecision, report it blocked; do not proceed as approved. The extension gates input only for a complete top-level decision block in the latest assistant message; quoted, incomplete, nested, and superseded marker text does not gate ordinary input. In UI modes, a pending gate explains why input was not forwarded. `/kapisch-decision-dismiss` clears the gate without granting authorization or creating a HumanDecision, and tells the agent to keep the gated workflow blocked. `/kapisch-decision` refuses without prompting, writing a HumanDecision, or sending a completion message. `/kapisch-decision-repair` may request regeneration of complete but malformed or interrupted requests, but creates no HumanDecision and grants no continuation. Agent and reviewer messages are never decision sources.

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
`.kapisch/runs/<run-id>`. The canonical current-prompt route is unsupported on
this Pi runtime: neither the persisted current user prompt nor `ui.input()`
results provide immutable original-input provenance. Fail closed; do not
construct or approve a WorkOrder from either source. This is runtime-specific
and does not change the canonical contract. Only resume this route when a host
API supplies immutable original-input provenance; do not infer it from a digest
of transformed text or from TUI controls.

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
