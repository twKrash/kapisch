<!-- kapisch-workflow: {"id":"milestone","stages":["research","design","gate","implement","review","final"],"gates":["human-decision","approval","side-effect"]} -->
# Milestone workflow

Use milestone for approved multi-step work with an explicit dependency graph. The controller records the approved plan, graph, one active writer, and ordered attempts. Execute dependencies sequentially; prior complete verified work is not repeated. Material scope expansion requires renewed authority.

Each dispatch has a stable operation ID and a persisted `dispatch-uncertain` marker before the adapter call. Never redispatch an unresolved operation. Final readiness requires a fresh independent whole-branch review against current repository state, no unreviewed delta, and validated persisted evidence. Unknown capability, incomplete provenance, or missing validator blocks approval/readiness.
