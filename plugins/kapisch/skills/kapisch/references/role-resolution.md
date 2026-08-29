# Role resolution

The LLM/controller selects from the closed logical role catalog: `architect`,
`researcher`, `implementer`, `implementer-lite`, `mechanic`, and `reviewer`.
It uses the request, repository context, and explicit constraints; repository
Python does not resolve roles, models, profiles, or dispatchability.

Codex runtime resolves the configured `.codex/agents/*.toml` profiles, chooses
the actual available model, dispatches the selected agent, and reports the
invocation result. The role TOMLs remain directly supported by Codex. A failed
or missing required reviewer invocation blocks approval; it is not predicted or
replaced by a repository resolver.

Installer-time `balanced`, `quality`, and `budget` profile sets configure only
the Codex `model` and `model_reasoning_effort` fields for those same six logical
profiles. They do not create roles or alter role selection, risk, review depth,
approval, permissions, or durable logical tiers. Python may deterministically
render an explicitly selected installed profile set; it never chooses the
semantic role or changes the set per request.

A skill or plugin capability is not a logical role, executor class, profile, or
model tier. The six-role catalog stays closed, and capability selection follows
role resolution: a delegated capability may supply methodology, repository
tooling, or an external integration for a bounded substep of the assigned
role's work, but it never replaces or reclassifies that role. Capability
selection and delegated-step behavior are owned by
[ecosystem-routing.md](ecosystem-routing.md).

Durable artifacts record factual invocation and review metadata only. The
validator checks that metadata for schema, revision, digest, freshness, and
state consistency; it does not emulate runtime registration or permissions.
