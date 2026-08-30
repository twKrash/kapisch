# Logical model tiers and runtime profile resolution

Logical executor classes and model tiers are durable workflow requirements.
Durable graphs retain only those logical values; a `model_tier` never identifies
a model family, reasoning effort, token budget, or performance outcome.

| Logical executor class | Minimum logical tier | Durable workflow use |
| --- | --- | --- |
| `mechanic` | `cheap` | bounded mechanical work when dispatch permits it |
| `implementer-lite` | `cheap` | bounded implementation work when dispatch permits it |
| `implementer` | `standard` | implementation work, including high-risk prescriptive work |
| `architect` | `high` | architecture and design work |
| `reviewer` | `high` | independent review and final readiness |

`cheap`, `standard`, and `high` classify workflow requirements only. In
particular, `high` does not mean `gpt-5.6-sol` or any other concrete model.
The selected installer-time profile set resolves each role's runtime `model` and
`model_reasoning_effort`; the canonical resolver is
`scripts/setup_profile.py`'s `PROFILE_SET_ROUTING`, rendered for operators in
the profile-set routing matrix.

For example, the quality high-tier reviewer resolves to
`gpt-5.6-sol` / `high`, the balanced high-tier reviewer resolves to
`gpt-5.6-terra` / `high`, and the budget reviewer resolves according to the
approved budget matrix. None changes approval authority, review independence,
risk classification, or the durable reviewer/high workflow requirement.

Configured runtime model and effort are factual observations, not inferred
durable evidence. They may be recorded only on the existing observability
surfaces when actually observed; unavailable values remain unavailable.

High-risk prescriptive work is the explicit exception to cheap
`implementer-lite`: it requires `implementer` at `standard` before independent
high-tier review.
