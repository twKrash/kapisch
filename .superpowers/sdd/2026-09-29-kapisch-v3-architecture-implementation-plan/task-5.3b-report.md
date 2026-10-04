

## Standalone finding K53B-01 — regression isolation (resolved)

The prior grouped malformed-basis regression was inadequate because an earlier invalid record could make later assertions pass. Replaced it with seven separate test methods; each test gets a fresh repository/acceptance namespace and requires the precise expected `ValueError` reason. Cases independently cover absent snapshot, wrong origin run, wrong decision ID, changed target digest, changed scope ref, changed applicability, and changed source dependencies. Every malformed basis is attached to an acceptance that does not match the queried consuming scope. The valid historical-basis-after-supersession test remains.

Mutation effectiveness: temporarily disabled the exact `if binding != expected:` production comparison in an isolated source mutation, ran `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k authority_basis_rejects_changed -v`, observed all four projected-field tests (digest, scope ref, applicability, source dependencies) fail because no error was raised, then restored the production file. This confirms each equality-dependent regression independently detects removal of the comparison.

Final validation on the corrected test file:
- `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -v` — 14 tests passed.
- `PYTHONPATH=core python -m unittest discover -s tests/core` — 290 tests passed; expected CLI negative-argument usage output.
- `ruff format --check tests/core/test_authority_records.py` — passed (already formatted).
- `git diff --check` — passed.

K53B-01 is resolved. Final worktree status is expected clean after the test/report-only follow-up commit; no production changes were made for this finding.
