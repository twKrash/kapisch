# Evaluator-only oracle

**Target scope:** review every artifact in `reviewer-methodology/targets/verification-negative-invariant/`; no Git diff is required for this reference case.

**Triggered methods:** proof obligations/evidence and mutation/side-effect justification; inspect the actor-to-write path and its test coverage.


Expected: identify a code-level missing-authorization check because the function mutates the role store without using `actor`, and identify that the successful owner test does not establish non-owner denial or unrelated-user protection. State required negative tests; do not claim a deployed caller path, actual production write, or incident without caller/runtime evidence.

Proportionality guard: The function body itself has no authorization check before the role mutation, so an unauthorized direct call is supported by code; do not claim a deployed caller path or production incident without caller/runtime evidence. Independently note that the positive test cannot prove the negative invariant.
