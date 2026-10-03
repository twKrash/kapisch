# Stage 5.1 implementation report

Status: DONE

## Commit

- `8b9ed708a655ad278aadd53097b2839f13bc231d feat(v3): bind inbound human receipt`

## Implementation

Added immutable host-observation and exact gate-target records, and a binder returning an `EvidenceRef` with the session-local action ID and SHA-256 digest of action plus text. It rejects incomplete/malformed timestamps, non-inbound origins, and any run/gate/target/scope mismatch. Added a public `authority` facade and exports, the requested single binding test, and a canonical conformance receipt fixture.

## TDD evidence

Red command:

`PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -k test_host_receipt_binds_session_local_id_and_target -v`

Observed failure before production implementation: `ModuleNotFoundError: No module named 'kapisch_core.authority'`.

Green command (same exact command): passed; 1 test, `OK`.

## Validation

- `PYTHONPATH=core python -m unittest discover -s tests/core -v` — passed, 137 tests.
- `PYTHONPATH=core python -m unittest discover -s tests/conformance -v` — passed, 17 tests.
- `git diff --check` — passed.
- Self-review: diff restricted to authority types/binder and facade/export, named test and receipt fixture. No host dependencies or global provider ID requirement introduced.
- Commit completed; no staged files remain.

## Changed files

- `core/kapisch_core/authority.py`
- `core/kapisch_core/_human_evidence.py`
- `core/kapisch_core/__init__.py`
- `tests/core/test_authority.py`
- `tests/conformance/fixtures/v3/receipt.json`

## Residual risks

The receipt is supplied as a host-observed typed record; this function validates its shape and binding but cannot cryptographically prove the host observation, consistent with the architecture boundary. The conformance fixture is a wire example, not yet consumed by a fixture-specific test.

## Diff summary

Added the minimal session-local inbound human receipt model and target-bound evidence reference generation. No unrelated workflows or files modified.

# Stage 5.1 fix round 1

## Review findings addressed

- The core observation now mirrors producer-owned Stage 3 facts: session namespace and local action ID, inbound-human origin, run/gate/decision/target/scope digest, text digest, and timestamp. Stage 3 does not provide raw action/text in its `HumanActionReceipt`, nor a separate action digest. The prior core model's raw action/text and computed action+text digest were therefore removed; the supplied text digest is preserved exactly and no unavailable data is claimed.
- EvidenceRef identifier now contains the full deterministically serialized observation (sorted compact JSON), rather than action ID plus an incomplete digest. This retains the exact field bytes needed for future durable validation; target equality is checked. No controller-generated source is accepted.
- Timestamp parsing now follows Stage 3 RFC3339 shape/range/offset and known leap-second validation, implemented in core without tooling imports.
- The fixture now represents actual Stage 3 fields and is consumed by the core regression test.

## TDD

RED: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -v` failed before the implementation change with `TypeError: ObservedHumanAction.__init__() takes 10 positional arguments but 11 were given`, proving the old interface could not represent the producer receipt/session binding.

GREEN: same command passed: `Ran 1 test ... OK`. Regression coverage checks serialized identity changes for each bound target field/timestamp/content digest, distinguishes identical action IDs in different sessions, rejects invalid date-only timestamps, and consumes `tests/conformance/fixtures/v3/receipt.json`.

## Validation and files

- `PYTHONPATH=core python -m unittest discover -s tests/core -v` — passed, 137 tests.
- `PYTHONPATH=core python -m unittest discover -s tests/conformance -v` — passed, 17 tests.
- `git diff --check` — passed.
- Changed: `core/kapisch_core/_human_evidence.py`, `tests/core/test_authority.py`, `tests/conformance/fixtures/v3/receipt.json`.

## Unresolved issue

The binder is stateless and has no Stage 4 authority census/state argument. It cannot establish uniqueness/duplicate ownership of an action ID within a session. That requires a later state-level census/validator and is intentionally not added here. This receipt binding also cannot cryptographically prove the host observation; it makes no such claim.

# Stage 5.1 fix round 2

## TDD

RED: `PYTHONPATH=core python -m unittest discover -s tests/conformance -p test_fake_adapter.py -v; PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority.py -v` failed as expected: conformance fixture test raised `KeyError: 'gate'`; core test failed constructing the Stage 3 producer receipt because fixture passed unexpected `protocol_version`.

GREEN: same focused commands passed after correcting the fixture and translating Stage 3 `gate` to core `gate_id`; conformance: 13 tests, `OK`; core authority: 1 test, `OK`.

## Validation

- `PYTHONPATH=core python -m unittest discover -s tests/core -v` — passed, 137 tests.
- `PYTHONPATH=core python -m unittest discover -s tests/conformance -v` — passed, 18 tests.
- `git diff --check` — passed.

## Changed files

- `tests/conformance/fixtures/v3/receipt.json` — uses producer-shaped `gate` and no unrelated protocol-version field.
- `tests/conformance/test_fake_adapter.py` — asserts fixture is accepted structurally by Stage 3 conformance receipt binding.
- `tests/core/test_authority.py` — translates accepted producer receipt into core record losslessly, binds and checks retained fields; restores receipt-only target mismatch and controller/outbound-origin rejection and malformed timezone-offset rejection.

## Remaining concerns

Same-session duplicate ownership remains outside this stateless binder and belongs to later Stage 5 authority-consumer work. Host observation is not cryptographically authenticated by the binder. No production binder changes were needed.
