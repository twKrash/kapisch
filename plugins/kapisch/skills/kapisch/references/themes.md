# Presentation themes

Themes are optional vocabulary layers for user-visible KAPISCH messages. They
may rename roles, procedures, gates, and lifecycle status text. They do not
change workflow meaning or machine-readable evidence.

The bundled themes are:

- `default`: direct product vocabulary;
- `foundry`: original industrial-mystic vocabulary inspired by ritualized
  machine maintenance and archival craft. It does not reuse franchise names,
  factions, characters, symbols, or quoted lore.

The LLM/controller selects `default` when `theme` is omitted. An explicit
`theme=default|foundry` control takes precedence over prose. A clear prose
request such as “use the foundry theme” may select the matching theme. An
unknown or ambiguous theme falls back to `default` and is reported as a
presentation fallback; it never blocks or changes the route.

Theme files live in `../themes/<id>.toml`. Each uses the same closed vocabulary
keys. The keys are canonical semantic identifiers and the values are display
labels. A controller may substitute only those values in explanatory prose.
When a themed gate or action could be ambiguous, show its canonical meaning on
first use, for example `Scope seal (material-scope approval)`.

## Semantic firewall

Theme selection never changes or aliases:

- request controls or their accepted values;
- logical role IDs, configured profile identities, model tiers, or dispatch;
- workflow shape, routing, risk, review depth, or required lenses;
- permissions, approval gates, fix authority, or any side-effect boundary;
- paths, artifact schemas, field names, field values, digests, invocation
  evidence, decision tokens, lifecycle states, or next-action tokens;
- validator behavior, errors, or exit status.

Canonical machine-readable values remain canonical. For example, a foundry
message may display `Forgehand`, but a durable assignment still records
`implementer`; `Sealed` may describe a node whose status remains `complete`.
Theme text cannot satisfy approval, reviewer identity, readiness, or artifact
requirements.

Theme selection is conversational presentation state. It is not a normative
manifest policy and must not be written into a KAPISCH schema field. A host that
needs diagnostic theme telemetry may use its own reverse-DNS namespaced
extension, but KAPISCH routing, validation, resume, and approval must ignore it.

## Localization boundary

Bundled theme values are English presentation vocabulary. Localization is a
separate rendering step applied after theme selection. A translation cannot
change canonical identifiers or semantics, and a lore or presentation theme
must not be used as a locale identifier.
