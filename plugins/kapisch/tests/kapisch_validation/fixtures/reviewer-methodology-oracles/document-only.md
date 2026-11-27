# Evaluator-only oracle

**Target scope:** review every artifact in `reviewer-methodology/targets/document-only/`; no Git diff is required for this reference case.

**Triggered methods:** semantic consistency, executability/feasibility, proof/evidence, and mutation/side-effect justification (the plan proposes deletion).


**Severity source:** use the reviewer-visible `references/severity.md`; these evaluator expectations are not reviewer input.

**Severity calibration** (the reviewer receives only target files and canonical severity policy):

- `DOC-F1 — P1`: the global selector permits cross-tenant deletion, independently of whether the caller is authenticated. `DOC-F2 — P1`: checking ownership after deletion cannot prevent an unauthorized effect. These may be reported separately or as one finding only if both independent causes and remedies remain explicit. P1 is blocking and matches the confirmed plan-level permission/isolation violations. P0 requires evidence that the impact is immediate or highly credible as catastrophic; the supplied plan establishes cross-tenant risk but gives no scale, reversibility, or imminent-execution evidence. Do not lower to P2 merely because the plan is proposed.
- `DOC-F3 — P2`: the proposed positive test verifies archiving rather than removal and omits the explicit unauthorized-caller and tenant-preservation acceptance checks. This is a required-coverage gap, not evidence that an implementation already failed.
- `DOC-F4 — P2, question/likely`: the plan adds a 30-day eligibility rule not grounded in the supplied spec. Ask for its authoritative source or owner confirmation; do not assert that no external policy exists.
- Do not require a separate finding for “without tenant ownership” if the reviewer reasonably reads it as an ownerless record distinct from the explicitly protected other-tenant records. The correction and regression coverage should still preserve both cases.
- Do not require a finding merely because the plan does not cite the co-supplied specification by filename/version; at most report a non-blocking traceability suggestion if useful.

Proportionality guard: Do not claim a deletion, breach, or implementation defect has already occurred. The plan is proposed and the specification is draft v2. Preserve P1 for the concrete permission/isolation defect and P2 for the coverage gap. Do not inflate P1 to P0 without the additional catastrophic-impact evidence required by `severity.md`; equally, do not treat proposed status alone as a reason to downgrade the confirmed defect. Do not claim execution or an incident occurred. Keep questions conditional and distinguish them from confirmed contradictions.
