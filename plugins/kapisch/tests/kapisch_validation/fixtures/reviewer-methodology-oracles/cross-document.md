# Evaluator-only oracle

**Target scope:** review every artifact in `reviewer-methodology/targets/cross-document/`; no Git diff is required for this reference case.

**Triggered methods:** semantic consistency, dependencies/traceability, authority/ownership, temporal/lifecycle consistency, proof/evidence, executability, and mutation/side-effect justification.


Expected: identify the accepted ADR conflict with the approved product spec; cyclic D1/D2 dependencies; the newer status report claiming completion without evidence; and tests that do not prove owner-request and cross-tenant invariants. The decision's accepted status does not make it correct.

Proportionality guard: Do not assert the unrun disabled-tenant or cross-tenant tests passed; identify the report’s limited enabled-tenant scope and the unsupported status transition without inferring an actual production deletion.
