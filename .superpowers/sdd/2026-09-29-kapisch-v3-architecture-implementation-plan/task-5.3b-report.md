# Stage 5.3b implementation report

Status: implemented and committed; no AcceptanceRecord producer/publication, plan promotion, or gate consumer was added.

## Changed files
- `core/kapisch_core/authority.py`: exports transient frozen `AuthorityBinding` and `active_authority(repo, scope_ref)`.
- `core/kapisch_core/_authority_census.py`: census facade.
- `core/kapisch_core/_authority_records.py`: validates committed acceptance records, referenced approvals, complete historical authority-basis projections and graph relationships before filtering.
- `core/kapisch_core/storage.py`: permits the acceptance namespace and distinguishes absent namespace from records disappearing during census.
- `tests/core/test_authority_records.py`: real persisted acceptance/approval regressions for applicability, cold reconstruction, basis target/identity/digest/projection failures (including a nonmatching acceptance), historical basis validity after supersession, coverage rules, invalid global records, read-time disappearance, and empty namespace.
- Plan Stage 5.3b and architecture spec §30.5: approved `ProposedScopeRef` trust-boundary clarification.

## Validation
- RED for basis integrity: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k test_invalid_historical_authority_basis_blocks_even_when_nonmatching -v` failed in all four malformed-binding subcases because census did not reject them (the intended missing-validation behavior).
- RED for enumeration race: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k test_acceptance_disappearing_after_listing_blocks_census -v` failed because no fail-closed error was raised after deletion.
- GREEN focused: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -v` — 8 tests passed.
- Absent namespace regression: `PYTHONPATH=core python -m unittest discover -s tests/core -k missing_acceptance_namespace -v` — passed.
- Full suite: `PYTHONPATH=core python -m unittest discover -s tests/core` — 284 tests passed (expected CLI negative-argument usage text emitted).
- `git diff --check` — passed before follow-up commit.
- Reconciliation: `ruff format core/kapisch_core/_authority_records.py core/kapisch_core/storage.py tests/core/test_authority_records.py` — 3 files left unchanged; formatting diff from HEAD retained and reviewed, no behavior changes.
- Final-file focused rerun: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -v` — 8 tests passed.
- Final-file full-suite rerun: `PYTHONPATH=core python -m unittest discover -s tests/core` — 284 tests passed (expected CLI negative-argument usage text emitted).
- Final `git status --porcelain` after the reconciliation commit: empty (clean).

## Review findings disposition
- P1 addressed: before filtering, each historical repository-decision authority-basis binding now resolves by qualified identity to a committed AcceptanceRecord and must exactly match its digest, scope ref, applicability, and direct source dependencies. Tests cover absent target, altered digest, wrong qualified origin, mismatched applicability on nonmatching records, and valid historical basis after later supersession.
- P2 addressed: only missing namespace/directory during namespace open yields an empty listing. A listed record disappearing at read time raises `ValueError("authority record disappeared during census")`; deterministic race regression confirms fail-closed behavior. Empty namespace remains a valid empty census.

## Self-review and residual risks
- Census verifies historical target bytes/projections but does not reject valid historical basis merely because the target later became superseded or its live source changed. Later authoritative gate owners check current source freshness under §30.5.
- No schema/record format changes, AcceptanceRecord publication, plan promotion, or gate consumer was introduced.
- Initial Stage 5.3b RED/fixture details and earlier commit reconciliation are documented in preceding report entries.

## Commits
- `d0c3a61b4c1a684e588c8bfb966ca904f8a5c20f` — initial Stage 5.3b implementation.
- `159e662fe28b685322179c86176fc66f394683ab` — test formatting/report reconciliation.
- `37be6909d4a2bb0d957e83cf55cc0957844d391c` — report SHA correction.
- `c46967c1e9e1313fe55eb8be92dd84b29ed7a365` — review findings fixes.
- Formatting/report reconciliation follow-up commit contains the Ruff-only diff for the three files and this report update; no behavior changes.
- Final worktree status after formatting/report reconciliation: clean.
