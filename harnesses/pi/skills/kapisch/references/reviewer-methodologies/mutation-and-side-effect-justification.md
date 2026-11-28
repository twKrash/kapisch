# Mutation and Side-effect Justification

## Activation

Load this method whenever the review target introduces or materially affects writes, updates, deletions, state transitions, or external effects. Include database records, files/durable artifacts, API mutations, events/messages, caches, access-control changes, external systems, lifecycle/ownership state, and indirect callback/cascade/trigger/downstream effects. Apply it to proposed mutations in documents and actual mutations in implementation. Follow the reviewed change and materially affected behavior/consumers; do not inventory unrelated historical writes.

## Review each relevant operation

- **Necessity and intent:** Should it happen? Which requirement, decision, or invariant justifies it? Can the outcome be achieved without it? Is it unnecessary or premature?
- **data and resource ownership:** Whose user, tenant, domain, aggregate, service, component, or resource is affected? Are boundaries respected? Could unrelated data, an unrelated entity, another tenant, or another domain be changed?
- **Authority and scope:** Is the initiating actor authorized, or could an unauthorized actor perform it? Are selectors, filters, ownership checks, and permissions sufficient? Are exactly the intended entities and fields affected, within approved scope?
- **Timing and lifecycle:** Are preconditions and workflow ordering valid? Where relevant, can retries, concurrency, interruption, or partial failure duplicate or misorder the effect?
- **Consequences and cross-domain impact:** Which consumers observe it? Do events and external outcomes match persisted state? Are dependent data, invariants, compatibility, and domain boundaries preserved? Could indirect effects escape the intended scope?
- **Verification:** Do tests prove the intended effect and that it does not occur without preconditions/authorization? Where applicable, do they prove unrelated entities, tenants, and resources remain unaffected? Are relevant failure, concurrency, retry, and partial-completion cases covered? Successful-path-only tests do not prove negative authorization or ownership invariants.

Report only concrete, target-related defects or evidence gaps. State the owning invariant, location/claim, evidence, plausible trigger, supported consequence, and actionable fix or missing verification. Do not claim cross-tenant exposure or a race unless the reviewed selectors/flow/evidence support it.
