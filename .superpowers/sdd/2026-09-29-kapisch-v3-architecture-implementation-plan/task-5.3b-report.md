# Stage 5.3b implementation report

Status: implemented and committed; no AcceptanceRecord producer/publication, plan promotion, or gate consumer was added.

## Changed files
- `core/kapisch_core/authority.py`: exports the transient frozen `AuthorityBinding` and `active_authority(repo, scope_ref)` API.
- `core/kapisch_core/_authority_census.py`: census facade.
- `core/kapisch_core/_authority_records.py`: committed AcceptanceRecord parsing, GateApproval reference validation, graph relationship checks, applicability filtering, and binding derivation.
- `core/kapisch_core/storage.py`: permits reading the existing `acceptances` authority namespace; no record/schema format changes.
- `tests/core/test_authority_records.py`: persisted accepted-record fixtures cover exact key matching, disjoint scopes, `all` consuming scope, producer-run deletion/cold reconstruction, malformed unmatched global records, valid full-coverage supersession, and rejected incomplete supersession coverage.
- Plan Stage 5.3b and architecture spec §30.5: record approved `ProposedScopeRef` locator/trust-boundary wording.

## Validation
- RED: `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -k test_authority_census_uses_persisted_structural_scope_and_rejects_invalid_graph -v` initially failed as expected because `active_authority` was absent. An early rerun then exposed invalid `propose_scope` test setup; corrected it to the five-argument API and persisted real acceptance/approval fixtures.
- GREEN focused: same exact command — passed (1 test).
- `PYTHONPATH=core python -m unittest discover -s tests/core -p test_authority_records.py -v` — passed (4 tests).
- `PYTHONPATH=core python -m unittest discover -s tests/core` — passed (280 tests; expected CLI negative-argument usage text emitted).
- `git diff --check` — passed.

## Self-review and residual risks
- Census validates all discovered acceptance envelopes and referenced repository-decision approvals/evidence before filtering; plan approvals do not count as repository authority. Persisted scope bytes are reloaded by exact `ProposedScopeRef`; invalid unrelated global acceptance data blocks filtering. Relationships are qualified and digest-bound; cycles, competing supersessions, and incomplete structural coverage fail closed.
- Bindings are transient and rebuilt from retained records. Deleted producer run state does not revoke a surviving acceptance.
- Current-source freshness is intentionally not recomputed inside this census; later authoritative gate owners remain responsible for current source checks under §30.5. No claims of arbitrary-deletion detection are made.
- Initial RED was the expected missing-API import failure; the subsequent fixture setup error was corrected before GREEN. No unresolved source/spec conflict found.

Commit: `8dc5cca` (`feat(v3): derive global authority bindings`).
