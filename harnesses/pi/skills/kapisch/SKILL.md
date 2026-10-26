---
name: kapisch
description: Use only when the user explicitly requests KAPISCH or repository-local authoritative instructions require KAPISCH.
---

# KAPISCH Pi adapter

The discovered canonical KAPISCH contract owns workflow and artifact semantics. Canonical contract path: `../../../../plugins/kapisch/skills/kapisch/SKILL.md`, resolved relative to this loaded Pi skill's directory. Read its current contents and resolve canonical normative references relative to that canonical skill directory; do not copy or duplicate canonical workflow instructions here. This adapter owns only Pi execution mechanics.

KAPISCH is explicitly opt-in. Ordinary Pi work MUST NOT activate KAPISCH just because it is complex or may benefit from planning, architecture work, or review. Activate it only when the user explicitly requests KAPISCH or authoritative repository-local instructions explicitly require it.

## Human-decision capture

When asking the operator to resolve a decision, append a visible fenced `kapisch-decision` JSON block to that assistant message. Include `question_id`, `question`, `governing_inputs` (`ref` and lowercase 64-character `digest`), `subject`, `scope`, `decision_type` (`answer`, `correction`, `approval`, `risk_acceptance`, or `external_effect_authorization`), and one `source_kind`: `direct_operator`, `operator_reported_external`, or `external_artifact`. Add `source_ref` and `approving_party` when available. The next UI-backed operator input is recorded verbatim as `answer`; the extension does not interpret it as approval. If the response is ambiguous, clarify before proceeding. For an uncertain remote effect, state the exact operation and target, and require the operator to answer exactly `AUTHORIZE`; denial or any other answer must keep retry blocked. Validated external observations are not supported by this adapter yet.

The extension ignores extension-injected and headless input. Pi exposes RPC input without locality or forwarding provenance, so the adapter currently rejects all RPC input, including local stdio RPC, until the host can prove its origin. Agent and reviewer messages are never decision sources.

Example:

```kapisch-decision
{"question_id":"Q-1","question":"May I proceed to staging?","governing_inputs":[{"ref":"context:C0","digest":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}],"subject":"release plan","scope":"staging only","decision_type":"approval","source_kind":"direct_operator"}
```

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
`.kapisch/runs/<run-id>`: when the current user prompt directly authorizes the
task, bind the WorkOrder approval source ref and content digest to that exact
user message. Map the generic ref to the exact Pi session/message in adapter-
owned metadata and store the canonical message digest there; keep host paths out
of the WorkOrder. Bind governing inputs with immutable Git commit/blob IDs. The
approval summary is derived, not authority. On resume, resolve and validate the
message mapping, digest, and governing-input refs; missing or mismatched
bindings block. Dispatch one worker attempt at a time and collect its uniquely
located output. An in-scope local retry uses a
fresh attempt ID/output location, preserves the prior attempt, and does not
change or reapprove the WorkOrder; no per-attempt approval is required. The
parent directs retries and never redispatches automatically. For an uncertain
remote effect, block retry until an authoritative outcome query or explicit
scoped TUI-backed human authorization. The parent LLM owns evidence aggregation,
Outcome, and handoff. Reviewer dispatch is optional; if dispatched, at most one
`kapisch-reviewer` returns findings-only evidence that the parent persists as
advisory, with no canonical invocation or approval artifacts. On a fresh session
reread the run files and repository state; missing or failed output stays
incomplete. RPC-based approval is unsupported because Pi cannot establish
locality; block that route and use only the visible TUI-backed user input
boundary.

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
