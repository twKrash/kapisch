<!-- kapisch-workflow: {"id":"milestone","metadata_scope":"workflow-specific","stages":["research","design","gate","implement","review","final"],"gates":["human-decision","approval","side-effect"],"review_scopes":["iteration","whole-branch"]} -->
# Milestone workflow

Use milestone for approved multi-step work with an explicit dependency graph. The controller records the approved plan, graph, one active writer, and ordered attempts. Execute dependencies sequentially; prior complete verified work is not repeated. Material scope expansion requires renewed authority.

Each dispatch has a stable operation ID and a persisted `dispatch-uncertain` marker before the adapter call. Never redispatch an unresolved operation. The explicit human decision that accepts the plan is separate from reviewer approval (`Gate.APPROVAL`) and permission for side effects (`Gate.SIDE_EFFECT`). None implies or substitutes for another. Final readiness requires a fresh independent whole-branch review against current repository state, no unreviewed delta, and validated persisted evidence. Unknown capability, incomplete provenance, or missing validator blocks approval/readiness.
