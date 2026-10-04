# Stage 5.3b implementation report

Status: implemented and committed; no AcceptanceRecord producer/publication, plan promotion, or gate consumer was added.

## Changed files
- `core/kapisch_core/authority.py`: exports transient frozen `AuthorityBinding` and `active_authority(repo, scope_ref)`.
- `core/kapisch_core/_authority_census.py`: census facade.
- `core/kapisch_core/_authority_records.py`: validates committed acceptance records, referenced approvals, complete historical authority-basis projections and graph relationships before filtering.
- `core/kapisch_core/storage.py`: permits the acceptance namespace and distinguishes absent namespace from records disappearing during census.
- `tests/core/test_authority_records.py`: real persisted acceptance/approval regressions for applicability, cold reconstruction, authority-basis target/identity/digest/projection failures (including a nonmatching acceptance), historical basis validity after supersession, coverage rules, invalid global records, read-time disappearance, and empty namespace.
- Plan Stage 5.3b and architecture spec §30.5: approved `ProposedScopeRef` trust-boundary clarification.

## Validation — initial Stage 5.3b and K53B-01 review fixes
- Initial RED: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k test_authority_census_uses_persisted_structural_scope_and_rejects_invalid_graph -v` initially failed because `active_authority` was absent. An early rerun exposed invalid `propose_scope` test setup; corrected it to the existing five-argument API and persisted real acceptance/approval fixtures.
- Initial GREEN: the exact focused command above passed after implementation.
- Review-fix RED for basis integrity: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k test_invalid_historical_authority_basis_blocks_even_when_nonmatching -v` failed in all four malformed-binding subcases because census did not reject them (expected missing-validation behavior).
- Review-fix RED for enumeration race: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k test_acceptance_disappearing_after_listing_blocks_census -v` failed because no fail-closed error was raised after deletion.
- Final focused suite: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -v` — 14 tests passed.
- Absent-namespace regression: `PYTHONPATH=core python -m unittest discover -s tests/core -k missing_acceptance_namespace -v` — passed.
- Final full core suite: `PYTHONPATH=core python -m unittest discover -s tests/core` — 290 tests passed; expected CLI negative-argument usage text emitted.
- Mutation check: temporarily disabled `if binding != expected:` in an isolated source mutation, then ran `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k authority_basis_rejects_changed -v`; all four digest/scope-ref/applicability/source-dependency tests failed because the expected error was not raised. Production source was restored.
- Formatting: `ruff format --check tests/core/test_authority_records.py` — passed (already formatted).
- `git diff --check` — passed.

## Review findings disposition
- P1 addressed: before filtering, each historical repository-decision authority-basis binding resolves by qualified identity to a committed AcceptanceRecord and must exactly match its record digest, scope ref, applicability, and direct source dependencies. The corrected regressions each use a fresh acceptance namespace and assert the expected error class/reason for absent snapshot, wrong origin run, wrong decision ID, altered digest, altered scope ref, altered applicability, and altered source dependencies. Each malformed record is nonmatching to the queried consuming scope. The mutation check confirms that removing the projection comparison breaks each projection-field test. Valid historical basis remains valid if its target is later superseded.
- P2 addressed: only missing namespace/directory during namespace open yields an empty listing. A listed record disappearing at read time raises `ValueError("authority record disappeared during census")`; deterministic race regression confirms fail-closed behavior. Empty namespace remains a valid empty census.
- K53B-01 addressed at commit `7c672d006eb72240907b2c69a5e0f2baedaab9b9`: replaced the shared, maskable malformed-basis subtests with seven independent fresh-repository regressions. No production change was made for K53B-01.

## Self-review and residual risks
- Census verifies historical target bytes/projections but does not reject valid historical basis merely because the target later became superseded or its live source changed. Later authoritative gate owners check current source freshness under §30.5.
- No schema/record format changes, AcceptanceRecord publication, plan promotion, or gate consumer was introduced.
- Initial Stage 5.3b RED/fixture details and earlier worktree reconciliation are retained in commit/report history.

## Commits
- `d0c3a61b4c1a684e588c8bfb966ca904f8a5c20f` — initial Stage 5.3b implementation.
- `159e662fe28b685322179c86176fc66f394683ab` — test formatting/report reconciliation.
- `37be6909d4a2bb0d957e83cf55cc0957844d391c` — report SHA correction.
- `c46967c1e9e1313fe55eb8be92dd84b29ed7a365` — standalone review findings P1/P2 fixes.
- `5da10887d086e7d01c2366cd8fb2773ef94e4953` — review-fix report update.
- `59e72e3e432a751ff0fa7c1ae10e18ee2e0b51f6` — Ruff-format reconciliation.
- `7c672d006eb72240907b2c69a5e0f2baedaab9b9` — K53B-01 test correction.
- Report-only correction is now staged for commit; final `git status --porcelain` will be checked after that commit.
