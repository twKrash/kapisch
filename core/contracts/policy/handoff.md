# Handoff policy

A handoff carries bounded task context, exact scope, required authority, declared effect ceiling, and evidence needed by the receiving role. The sender owns the assignment and requested work; the receiver owns its returned judgment or result; the controller binds producer, target, revision, and digest. Delegation cannot grant reviewer authority or exceed the initiating authority. External-write and destructive effects remain unsupported absent an explicitly approved safe protocol. Preserve single-writer ownership and ordered dependencies; a handoff report is not a human decision, reviewer approval, or validator result.

## Human decision packet

When a human decision is required, present the canonical packet shape:

```text
{id, kind, problem, why, decision_required, options, recommendation}
```

- `id` uniquely identifies this packet among outstanding human choices; do not impose transport-specific prefixes.
- `kind` names the decision domain.
- `problem` states the choice that blocks progress; `why` states why an explicit choice is needed.
- `decision_required` states exactly what the human must decide.
- `options` is the ordered array of up to three materially different options; each option's `id` is unique within the packet, `description` states the choice, and `consequences` states material effects.
- `recommendation` identifies one listed option by ID or is `unavailable`; it is advice, never a decision or authority grant. Never record an agent recommendation as a human decision.

Do not omit the problem, why the choice is needed, or the specific decision required. A human answer must map unambiguously to exactly one packet ID among outstanding choices; otherwise ask a focused question and record no decision.

This is a human-facing decision contract, not a persistence or lifecycle schema. Do not import transport, storage, status, or identifier-prefix conventions from prior contracts. Persisted authority and evidence structures belong to their owning schema contracts.

Durable handoff identity is owned by the controller and is never inferred from a human choice, worker output, adapter/provider ID, filename, session, or conversation. A handoff to an attempt binds its run, exact stage ID, scope, role, and applicable approved node/plan authority. The controller-created stage ID identifies one attempt; a retry is separately identified and explicitly linked. The controller may transport externally owned evidence but must not claim its authorship. Persist requests and prerequisite evidence before reserving an operation; after the complete reservation and durable uncertainty are published, the assigned adapter may be invoked once. Handoff or reservation alone is not dispatch proof, judgment, human approval, or authority to repeat an operation.
