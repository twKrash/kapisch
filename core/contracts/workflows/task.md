<!-- kapisch-workflow: {"id":"task","metadata_scope":"workflow-specific","stages":["implement","review","gate"],"gates":["human-decision","approval","side-effect"],"review_scopes":["iteration","whole-branch"]} -->
# Task workflow

Use task for one bounded unit of work. Tasks are graph-free: do not invent a milestone graph. Bind requirements, scope, authority, and verification before dispatch. Behavioral changes require independent review when approval is claimed; a task review may cover its complete task diff without duplicating identical review work.

`Gate.HUMAN_DECISION` is explicit human acceptance of a plan or other material choice; `Gate.APPROVAL` is independent reviewer approval; `Gate.SIDE_EFFECT` is separate human permission for an authorized effect. None implies or substitutes for another. Record verified completion and evidence in durable v3 state before claiming authoritative completion. Any authoritative gate requires the conformant validator; missing validation blocks the claim, not merely the workflow display.
