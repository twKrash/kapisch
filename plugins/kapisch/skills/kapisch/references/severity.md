# Finding severity

- **P0** — immediate or highly credible catastrophic impact: security compromise,
  cross-tenant exposure, destructive data loss, credential disclosure, or similar.
  Always blocks approval.
- **P1** — likely core-workflow failure, permission/isolation/invariant violation,
  persisted incorrect state, unrecoverable migration, or credible serious incident.
  Always blocks approval.
- **P2** — bounded correctness, resilience, compatibility, observability, or
  coverage defect. Blocks when it violates acceptance criteria, lacks a safe
  workaround, risks persisted incorrect state, or lacks required regression coverage.
- **P3** — non-blocking maintainability, clarity, or cleanup. It does not block
  unless repository policy requires it.

Confidence is `confirmed`, `likely`, or `question`. Do not call a speculative
concern a confirmed blocking defect.
