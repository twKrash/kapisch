# Evaluator-only oracle

**Target scope:** review every artifact in `reviewer-methodology/targets/mutation-ownership/`; no Git diff is required for this reference case.

**Triggered methods:** mutation/side-effect justification, authority/ownership, and proof/evidence.


Expected: identify cross-tenant deletion because caller-selected event_id is not globally unique and tenant ownership is absent from selector/check. The success-path test does not prove denial/unrelated-tenant preservation. Load mutation, authority/ownership, and proof methods.

Proportionality guard: Do not claim a runtime incident occurred; identify the concrete selector/ownership defect and supported cross-tenant consequence in the reviewed function.
