# Stage 5.2 implementation report

## Scope and result

Implemented the Stage 5.2 external human-artifact input binder within the three approved files. The public `authority` facade exposes the new record, closed source enum, and binder. Existing Stage 5.1 receipt APIs and tests remain intact. No commit has yet been created in this report.

`ExternalArtifactInput` carries a reference, exact `bytes`, and `ExternalInputSource.EXTERNALLY_SUPPLIED`. The binder validates input types/source, rejects the v3 approval envelope shape (protocol version 3 with the schema's approval fields), hashes the exact supplied bytes, and emits an `EvidenceRef` containing the reference, SHA-256, run/gate/decision/target/scope bindings. This is a boundary assertion, not cryptographic proof of authorship. It does not claim arbitrary filesystem bytes are human-written. No controller/model-text API was added to produce this input.

## TDD record

The first attempted focused run failed during test-module import because the public API did not exist, before an assertion could exercise the feature. A subsequent intermediate focused run failed because the test asserted for `text_digest` instead of the artifact's content `sha256`; these are not valid feature RED evidence. After correcting the test to assert the binder's defined evidence and rejecting the approval envelope/source mismatch, the focused test passed.

To produce a meaningful API-absence RED after recovery, temporarily restored the original facade (without the Stage 5.2 exports) and ran the new focused test: it failed importing `ExternalArtifactInput` from the facade. The working facade was immediately restored. This demonstrates that the test detects the missing public contract, though it is not a record of the original pre-edit TDD sequence.

## Validation

- Focused new test: passed.
- Full authority module: 2 tests passed, including the restored Stage 5.1 host-receipt regression.
- Core suite: 138 tests passed.
- Conformance suite: 18 tests passed.
- `git diff --check`: passed.
- Scope inspection: exactly the requested authority facade, private evidence module, and authority test file are changed.
- No staged files.

## Self-review

The binder hashes original bytes directly and uses deterministic sorted compact JSON for the evidence identifier. Scope binding values are taken from the supplied `GateTarget`; no inferred controller approval is treated as evidence. The v3 approval-envelope rejection is intentionally structural and limited to the specified schema shape; it cannot prove who created arbitrary bytes. The source enum is closed to the schema-supported `externally-supplied` value. The existing 5.1 receipt validation/binding test remains unchanged and passes.

Largest changed production function is `bind_external_human_artifact` (about 20 lines); changed modules remain small and below architecture size thresholds.

## Commit

Not created yet. Intended boundary subject: `feat(v3): bind external approval evidence`.
