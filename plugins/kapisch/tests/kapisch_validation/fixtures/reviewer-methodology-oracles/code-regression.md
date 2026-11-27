# Evaluator-only oracle

**Target scope:** review every artifact in `reviewer-methodology/targets/code-regression/`; no Git diff is required for this reference case.

**Triggered methods:** the code-review and applicable risk/severity procedures, proof/evidence, authority/security, and mandatory Decision Challenge for the security-relevant default.


**Severity source:** use the reviewer-visible `references/severity.md`; these evaluator expectations are not reviewer input.

**Severity calibration:** `CODE-F1 — P1, confirmed behavior / likely authorization impact`: a missing role claim now resolves to `admin`, contrary to the previous `viewer` default, on a function stated to enforce an administration endpoint. P1 is blocking for the directly supported permission regression. Do not elevate to P0 without evidence of an immediate or highly credible catastrophic consequence; do not downgrade merely because the exploit path is not shown beyond the stated endpoint use.

Expected: identify the changed default and the missing-role trigger; recommend deny-by-default and a negative test. Unknown non-missing role values are not mapped to `admin` by the supplied code, so do not claim they trigger this defect. State that broader caller reachability and runtime effects are unverified.

Proportionality guard: Do not report unrelated style or refactoring concerns, claim an exploit or incident occurred, or infer behavior for unknown non-missing role values.
