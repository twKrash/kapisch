<!-- kapisch-workflow: {"id":"task","stages":["implement","review"],"gates":["approval","side-effect"]} -->
# Task workflow

Use task for one bounded unit of work. Tasks are graph-free: do not invent a milestone graph. Bind requirements, scope, authority, and verification before dispatch. Behavioral changes require independent review when approval is claimed; a task review may cover its complete task diff without duplicating identical review work.

Human approval and permission for a side effect are distinct gates. Record verified completion and evidence in durable v3 state before claiming authoritative completion. Any authoritative gate requires the conformant validator; missing validation blocks the claim, not merely the workflow display.
