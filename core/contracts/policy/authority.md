# Human authority and retained semantics

## Legacy retained runs

A retained run using the legacy authority contract remains interpretable only under the exact retained `CoreBundle` bytes and digest that governed that run. `global-authority/1` and later code do not reinterpret legacy `accepted_snapshot` data under newer semantics. Legacy evidence remains valid only for the legacy contract that produced it.

## Global authority boundaries

`HumanActionClaim` preserves host-observed action and anti-replay ownership facts. It is evidence, not a human decision, reviewer approval, side-effect permission, or repository authority.

`GateApprovalRecord` is the durable record of explicit human approval for one complete `GateApprovalPayload`. It binds run, gate, identity, scope, subject, and evidence. It does not itself commit repository authority.

`AcceptanceRecord` is the only global repository-authority commit. A repository-decision `GateApprovalRecord` remains an approval record until a separate consumer revalidates it and publishes the corresponding `AcceptanceRecord`; never infer repository authority from a GateApproval alone. Acceptance preserves governing-source dependencies and amendment/supersession edges. Human acceptance cannot override an active normative source.

For plan approval, retain the exact candidate plan bytes and governing bindings first; then publish the durable `GateApprovalRecord` for that exact plan. Only after that commit may a consumer produce or repair a checked `PlanRef`, after revalidating the referenced bytes against the approved identity and digest. `PlanRef` is a repairable backlink, not approval or authority. Stage 5.3a does not retain candidate plan bytes, publish or load plan approvals, or publish `PlanRef`; Stage 5.5 owns plan-byte retention, approval, and promotion. Side-effect permission is a separate gate; Stage 5.3a does not publish side-effect-permission records before their request producer exists.

## Human evidence and external artifact retention

A host-action approval references a retained `HumanActionClaim`; repeating receipt fields in a controller-owned envelope cannot substitute for the host-observed action. A receipt records observable origin, not cryptographic identity.

External approval input must be an `ExternalArtifactInput` marked `EXTERNALLY_SUPPLIED`. Core validates its exact canonical bytes against the complete `GateApprovalTarget` before retaining them. Core derives the immutable path `.kapisch/v3/authority/human-artifacts/<sha256>.json`; caller reference is never a repository path. `GateApprovalRecord` stores the derived path and digest. Exact read-back and digest comparison are required; a same-path byte collision, tamper, missing artifact, or uncertain write that cannot be resolved by exact read-back fails closed. An orphan artifact grants no approval or authority. A digest binds bytes, not authorship; do not claim stronger guarantees.

## Historical validity versus current eligibility

Loading a retained approval establishes its historical schema, target, and evidence bindings. It does not establish that the approval is currently governing, fresh, or eligible for promotion or execution. Consumers must re-evaluate current governing sources and freshness; changed dependencies stale downstream use until re-evaluation and a fresh human decision. Historical GateApproval and Acceptance records remain immutable.

## Reviewer approval

In the legacy protocol, `Gate.HUMAN_DECISION` records explicit human choice, `Gate.APPROVAL` records independent reviewer approval, and `Gate.SIDE_EFFECT` records separate human permission for an authorized effect. Explicit human approval of a plan is a `Gate.HUMAN_DECISION` bound to that plan, not a consequence of `Gate.APPROVAL` reviewer judgment.

Reviewer judgment is separate from explicit human decisions and side-effect permission. A reviewer approval neither supplies nor implies a second human approval. The reviewer owns review judgment; the adapter owns observed invocation facts; the controller binds, but never authors, those external facts.
