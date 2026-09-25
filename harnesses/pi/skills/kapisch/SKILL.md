---
name: kapisch
description: Use only when the user explicitly requests KAPISCH or repository-local authoritative instructions require KAPISCH.
---

# KAPISCH Pi adapter

The discovered canonical KAPISCH contract owns workflow and artifact semantics. Read its current `SKILL.md` and task-applicable normative references before KAPISCH-controlled execution. This adapter owns only Pi execution mechanics.

KAPISCH is explicitly opt-in. Ordinary Pi work MUST NOT activate KAPISCH just because it is complex or may benefit from planning, architecture work, or review. Activate it only when the user explicitly requests KAPISCH or authoritative repository-local instructions explicitly require it.

## Role mapping

Use `pi-subagents` and the exact canonical role selected by KAPISCH. Do not substitute generic Pi agents after KAPISCH controls the workflow:

- architect -> kapisch-architect
- researcher -> kapisch-researcher
- implementer -> kapisch-implementer
- implementer-lite -> kapisch-implementer-lite
- mechanic -> kapisch-mechanic
- reviewer -> kapisch-reviewer

If a mapped agent is unavailable, follow the canonical contract's blocking or escalation behavior; do not silently choose a different role.

## Execution boundary

Use fresh child contexts by default. Send bounded task packets and canonical artifact references, not full parent history or duplicated reports. Keep canonical evidence and artifact contracts authoritative; Pi transcripts are not portable evidence unless KAPISCH says otherwise. Record only observable Pi provenance and do not invent evidence equivalence.

Model and reasoning defaults come from each agent's generated Pi configuration. Operator or project agent overrides may replace those defaults. Do not choose a model manually, assume fallback, or treat model availability as authority.

Pi tools do not grant permission. Preserve canonical authority, safety, approval, independent-review, evidence, recovery, and readiness requirements. Independent review requires a distinct `kapisch-reviewer` invocation. Treat canonical KAPISCH distribution as read-only workflow source; current task artifacts belong to the consumer repository.

Pi cannot enforce command-level restrictions on `bash`; child Bash calls pass through. Tool allowlists and native tool permissions do not make shell execution read-only. Do not claim that Pi runtime alone prevents shell-side mutation.
