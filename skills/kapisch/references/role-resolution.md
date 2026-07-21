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

Durable artifacts record factual invocation and review metadata only. The
validator checks that metadata for schema, revision, digest, freshness, and
state consistency; it does not emulate runtime registration or permissions.
