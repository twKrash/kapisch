# Logical model tiers and configured roles

Logical executor classes and model tiers are stable, replaceable routing values.
They map to the currently configured Codex roles below; durable graphs retain
only logical values and never model IDs.

| Logical executor class | Minimum logical tier | Configured role | Current configured model |
| --- | --- | --- | --- |
| `mechanic` | `cheap` | `mechanic` | `gpt-5.6-luna` |
| `implementer-lite` | `cheap` | `implementer-lite` | `gpt-5.6-luna` |
| `implementer` | `standard` | `implementer` | `gpt-5.6-terra` |
| `architect` | `high` | `architect` | `gpt-5.6-sol` |
| `reviewer` | `high` | `reviewer` | `gpt-5.6-sol` |

| Logical tier | Configured role use |
| --- | --- |
| `cheap` | `mechanic` or `implementer-lite`, both configured with `gpt-5.6-luna`, when the dispatch contract permits it. |
| `standard` | `implementer` with `gpt-5.6-terra`; independent `reviewer` with `gpt-5.6-sol` remains permitted above this minimum. |
| `high` | `architect` and `reviewer`, both configured with `gpt-5.6-sol`. |

`reviewer` is independent of the implementation executor and is never below
the standard tier. High-risk integrated review and final readiness use the high
tier `reviewer`. Changing a configured model updates this mapping and role TOML;
it does not change graph semantics or role boundaries.

High-risk prescriptive work is the explicit exception to cheap
`implementer-lite`: it maps to `implementer` at `standard` before independent
high-tier review.
