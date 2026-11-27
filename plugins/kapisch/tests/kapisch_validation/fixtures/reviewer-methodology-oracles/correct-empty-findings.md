# Evaluator-only oracle — never this oracle in reviewer input

The reviewer receives only the target and legitimate context. This oracle is evaluator-only and must never be provided to the reviewer.

**Target scope:** review every artifact in `reviewer-methodology/targets/correct-empty-findings/`; no Git diff is required for this reference case.

**Triggered methods:** universal reviewer baseline and Decision Challenge; Semantic Consistency applies to the display-only label and blank/default behavior; Dependencies and Traceability applies to the established default and unchanged identifier/access-check contracts; Proof Obligations and Evidence Quality applies to the tests' unchanged-state claims; Executability, Feasibility, and Simplicity applies to the optional input and direct implementation. These methods are applicable even though no finding is expected.

**Not triggered:** Mutation and Side-effect Justification (no mutation or external effect); Authority and Ownership (no identity, authorization, or ownership change); Temporal and Lifecycle Consistency (no lifecycle, concurrency, or timing behavior).

Expected: empty findings. This solution is bounded, correct, simple, and adequately verified. A new dependency or abstraction is a false positive absent further requirements.

Proportionality guard: Do not recommend added architecture or dependencies absent requirements; do not invent an authorization or persistence effect because the target explicitly excludes those uses and verifies unchanged state.
