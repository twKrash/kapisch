# Stage 5.2 implementation report

## Scope and result

Implemented the Stage 5.2 external human-artifact input binder within the three approved source/test files. The public `authority` facade exposes the new record, closed source enum, and binder. Existing Stage 5.1 receipt APIs and tests remain intact.

`ExternalArtifactInput` carries a reference, exact `bytes`, and `ExternalInputSource.EXTERNALLY_SUPPLIED`. The binder validates input types/source, rejects the v3 approval envelope shape (protocol version 3 with the schema's approval fields), hashes the exact supplied bytes, and emits an `EvidenceRef` containing the reference, SHA-256, run/gate/decision/target/scope bindings. This is a boundary assertion, not cryptographic proof of authorship. It does not claim arbitrary filesystem bytes are human-written. No controller/model-text API was added to produce this input.

## TDD record

The first attempted focused run failed during test-module import because the public API did not exist, before an assertion could exercise the feature. A subsequent intermediate focused run failed because the test asserted for `text_digest` instead of the artifact's content `sha256`; these are not valid feature RED evidence. After correcting the test to assert the binder's defined evidence and rejecting the approval envelope/source mismatch, the focused test passed.

To produce a meaningful API-absence RED after recovery, temporarily restored the original facade (without the Stage 5.2 exports) and ran the new focused test: it failed importing `ExternalArtifactInput` from the facade. The working facade was immediately restored. This demonstrates that the test detects the missing public contract, though it is not a record of the original pre-edit TDD sequence.

## Validation

- Focused new test: passed (`PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -k test_controller_gate_blocks_without_external_artifact_input -v`): 1 test passed.
- Full authority module: passed (`PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -v`): 2 tests passed, including the Stage 5.1 host-receipt regression.
- Core suite: passed (`PYTHONPATH=core python -m unittest discover -s tests/core -v`): 138 tests passed.
- Conformance suite: passed (`PYTHONPATH=core python -m unittest discover -s tests/conformance -v`): 18 tests passed.
- `git diff --check`: passed.
- Scope inspection: exactly the requested authority facade, private evidence module, and authority test file are source/test changes.
- Verified commit: `71232680b23d8ef4651e27b62cceb554a5937d5d` (`feat(v3): bind external approval evidence`).
- At commit verification, working tree was clean and there were no staged files.

## Fix round 1 — reviewer findings K52-001 and K52-002

Added regressions first. Before production changes, the focused external-artifact tests failed as expected: three malformed digest cases (short, uppercase, non-hex) were accepted, and a valid JSON object containing a 5000-digit integer raised `ValueError` from `json.loads`. The empty digest case already failed due to the existing non-empty target check.

The binder now validates scope digests against the same lowercase 64-hex digest pattern used by the host-receipt binder. JSON recognition parses ordinary integers normally but preserves integers over 4300 digits as strings, avoiding Python's integer-string conversion limit while still parsing the rest of the JSON object. Consequently recognizable protocol-v3 approval envelopes remain rejected, including records with oversized unrelated numeric fields, while non-envelope exact bytes can bind and are hashed unchanged.

Fix-round validation:

- Focused regressions: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -k test_external_artifact -v` — 2 tests passed.
- Full authority module: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -v` — 4 tests passed, including Stage 5.1 receipt coverage.
- Core suite: `PYTHONPATH=core python -m unittest discover -s tests/core -v` — 140 tests passed.
- Conformance suite: `PYTHONPATH=core python -m unittest discover -s tests/conformance -v` — 18 tests passed.
- `git diff --check` — passed.

Changed files in fix round: `core/kapisch_core/_human_evidence.py`, `tests/core/test_authority.py`, and this report. The earlier commit `71232680b23d8ef4651e27b62cceb554a5937d5d` is unchanged; this fix round is a separate follow-up commit.

## Fix round 2 — runtime-independent JSON integer parsing

Added a regression that lowers `sys.set_int_max_str_digits(640)` with restoration in `finally`. Before the production fix, the focused test failed with `ValueError` for a 1000-digit integer in a non-envelope artifact. The same regression also checks that a recognizable v3 approval envelope with an unrelated 1000-digit number is explicitly rejected.

The parser now preserves JSON integer tokens as decimal strings during envelope recognition, so behavior is independent of the interpreter integer conversion limit. Protocol version recognition accounts for this representation (`"3"` for JSON integer 3), leaving the envelope-field test in place. Non-envelope bytes continue through to exact-byte SHA-256 binding.

Fix-round 2 validation:

- Focused regression: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -k test_external_artifact_integer_parsing_ignores_runtime_digit_limit -v` — 1 passed.
- Authority module: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -v` — 5 passed.
- Core suite: `PYTHONPATH=core python -m unittest discover -s tests/core -v` — 141 passed.
- Conformance suite: `PYTHONPATH=core python -m unittest discover -s tests/conformance -v` — 18 passed.
- `git diff --check` — passed.


The digest check rejects non-string and anything other than 64 lowercase hexadecimal characters. The integer parser only avoids conversion of exceptionally long integer tokens; JSON structure and protocol-version parsing stay intact, so a recognizable v3 approval envelope is still caught rather than broadly allowing it through. Exact artifact bytes continue to determine SHA-256. Source remains the single supported `externally-supplied` enum member; Stage 5.1 receipt binding is unchanged.


The binder hashes original bytes directly and uses deterministic sorted compact JSON for the evidence identifier. Scope binding values are taken from the supplied `GateTarget`; no inferred controller approval is treated as evidence. The v3 approval-envelope rejection is intentionally structural and limited to the specified schema shape; it cannot prove who created arbitrary bytes. The source enum is closed to the schema-supported `externally-supplied` value. The existing 5.1 receipt validation/binding test remains unchanged and passes.

Largest changed production function is `bind_external_human_artifact` (about 20 lines); changed modules remain small and below architecture size thresholds.

## Fix round 3 — preserve JSON numeric version semantics

Added RED cases under `sys.set_int_max_str_digits(640)` (restored in `finally`) for numeric protocol versions `3`, `3.0`, and `3e0`, each with an unrelated 1000-digit integer. Before the production correction, the `3.0` and `3e0` cases incorrectly bound, while string `"3"` was incorrectly rejected as an envelope. The test also verifies the non-envelope 1000-digit integer still binds with its exact-byte SHA-256.

The parser now converts only integer tokens of at most 15 digits to `int`; longer integer tokens remain strings. Envelope detection accepts numeric JSON version values equal to 3, including float/exponent spellings, while requiring a numeric type (excluding booleans), so a JSON string `"3"` is not confused with numeric version 3. The 15-digit conversion cap is well below Python's minimum supported configurable integer-string limit; long values are never converted.

Fix-round 3 validation:

- Focused regression: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -k test_external_artifact_integer_parsing_ignores_runtime_digit_limit -v` — 1 passed.
- Authority module: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -v` — 5 passed.
- Core suite: `PYTHONPATH=core python -m unittest discover -s tests/core -v` — 141 passed.
- Conformance suite: `PYTHONPATH=core python -m unittest discover -s tests/conformance -v` — 18 passed.
- `git diff --check` — passed.


Initial Stage 5.2 implementation commit: `71232680b23d8ef4651e27b62cceb554a5937d5d` (`feat(v3): bind external approval evidence`).

Review-fix commits: `847d9a835ce4557f17bae30899bb963fba5f66d8` (scope digest and parser failures), `44b4de41ef905eb849167f0e3b5f05d52fa80508` (runtime-independent integer parsing), and `a411701a686b1ffa31b0c5aefbc5755bb90701e5` (numeric protocol-version semantics). Report update: `9704d59fc05411f6c03d913a8c71b22dafe60e2c`. Stage 5.2 is complete at this report revision; final tracked worktree was clean with no staged files.
