# Dispatch policy

`evaluate_action_policy()` is the sole authority for static role, stage, tier, review-scope, gate, effect, and capability admissibility. Workflow metadata is a workflow-specific contract inventory, not the complete admissible set, a required sequence, or a lifecycle matrix. Every declared value must remain admissible under that evaluator; metadata never grants permission or makes an otherwise-invalid combination valid.

Implementation role/tier floors are:

| Execution class | Risk | Minimum role | Minimum tier |
| --- | --- | --- | --- |
| mechanical | any | mechanic | cheap |
| prescriptive | low or medium | implementer-lite | cheap |
| prescriptive | high | implementer | standard |
| bounded | any | implementer | standard |

Non-high-risk prescriptive work uses `implementer-lite` at `cheap`; high-risk prescriptive work uses `implementer` at `standard`.

A `design` stage uses `architect` at `high`; `research` uses `researcher` at `standard`; `review` and `final` use `reviewer` at `high`. A bounded-delegate assignment must preserve the assigned role's corresponding tier floor. A role or tier may be strengthened, never weakened below its floor. These are logical roles and tiers, not provider, model, or harness choices.

Dispatch only an admissible role, stage, tier, effect, and capability combination under static core policy. Repository writes require enforced write capability; unknown or advisory capability is insufficient. External-write and destructive effects remain unsupported absent a separately approved safe protocol.

The controller is the single writer. For durable work, persist a stable operation ID, exact request, and `dispatch-uncertain` state before invoking an adapter. A missing receipt does not prove dispatch did not occur. Never repeat an unresolved operation; reconcile only that exact operation when the adapter can observe it safely.
