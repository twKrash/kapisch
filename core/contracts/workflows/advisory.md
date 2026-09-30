<!-- kapisch-workflow: {"id":"advisory","metadata_scope":"workflow-specific","stages":["research","design","gate"],"gates":["human-decision"],"review_scopes":[]} -->
# Advisory workflow

Use advisory for graph-free repository research and bounded architecture or product proposals. The controller owns scope, source-authority discovery, and any user-facing decision request; researchers and architects return evidence and options, never approval.

An accepted decision is an explicit `Gate.HUMAN_DECISION` bound to its exact scope and governing sources. Acceptance is not reviewer approval (`Gate.APPROVAL`), implementation authority, or permission for a side effect; approval of a plan is a separate human decision. Promotion requires a separately approved plan bound to the accepted snapshot and current source bytes. Without a conformant validator, work may remain non-authoritative research, but no accepted decision or plan approval may be claimed.
