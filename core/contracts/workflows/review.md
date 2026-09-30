<!-- kapisch-workflow: {"id":"review","stages":["review"],"gates":[]} -->
# Review workflow

Use review for independent findings on an explicitly supplied target and scope. A standalone review is findings-only: it creates no approval or readiness authority and may run without durable validation.

The reviewer judges evidence and reports findings; the controller cannot author reviewer judgment. Any review result used for an authoritative task, milestone, or final gate must bind to its invocation, target, repository revision, and required repository-state evidence, then pass the conformant validator. A final whole-branch review is a fresh invocation, distinct from iteration review.
