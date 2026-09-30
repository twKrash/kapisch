# Resume policy

Resume only from validated persisted v3 authority, the exact locally retained bundle bytes named by its digest, and freshly observed repository/provider evidence. Recheck active governing sources, plan dependencies, current repository state, invocation and result bindings, and ordered attempt history. Do not rely on prior conversation, caller claims, a previous snapshot, or a replaceable controller view to supply missing authority.

Refuse v2, unknown, malformed, corrupt, incomplete, or same-version-different bundle state. An unresolved dispatch remains blocked unless safe read-only reconciliation observes the same operation ID; never redispatch it. Preserve verified completed work, and block ambiguous evidence rather than infer success or failure.

Durable runs require the bundled `identity_contract` value `stage-attempt/1`; protocol version 3 alone does not assert support. Load only the exact locally retained canonical bundle bytes named by the digest, and verify them on every resume; never substitute the installed distribution bundle. A missing or corrupt retained bundle blocks even if a newer distribution has the same protocol number.

Preserve append-only attempt history and exact stage IDs, creation bindings, evidence references, and contiguous zero-based sequence. A retry is a new stage attempt with a new ID and explicit eligible predecessor; do not infer identities, nodes, or retry relationships from status, order, or conversation. Graph-free workflows carry no graph or node IDs. Milestone node execution requires exact retained graph/scope and approved-plan bindings; absent graph may represent only pre-execution state.

Inspect every retained operation reservation and immutable invocation fact before dispatch or authoritative completion, including facts not referenced by current state. Orphan, uncertain, malformed, or unbound facts veto dispatch; they do not supply affirmative completion or gate evidence. Reconcile only the original operation under its persisted adapter lookup binding. Missing state or receipt never proves that the operation was not sent.
