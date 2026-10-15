# Stage 4 `stage-evidence/1` — gated implementation plan

**No commits, push, PR, publication, or production implementation are authorized by this planning task.** Only this plan document may change. Implementation and independent review require separate delegation. Do not use Kapisch to plan, orchestrate, dispatch, or execute this work.

## 1. Baseline, governing evidence, and approval boundaries

Worktree: `/home/agent/.herdr/worktrees/kapisch/feat-stage4-stage-evidence-1-full`.
Branch: `feat/stage4-stage-evidence-1-full`; inspected base:
`cedd5ff4d92283e0dd82e6b8c2a425469bf0dc8c` (`origin/main` starting point).

Read and preserve:

- `AGENTS.md`: self-hosting prohibition, fail-closed boundaries, cold restart, single producer, narrow changes, module/function review triggers.
- **Normative:** `docs/superpowers/specs/2026-09-29-kapisch-v3-architecture-design.md` §32.1–32.6, approved via PR #77; §30.7 defines the approved exact candidate/approval chain. §31 is explicitly a pending Stage 7 contract, not permission to implement Stage 7.
- `docs/superpowers/plans/2026-09-29-kapisch-v3-architecture-implementation-plan.md`, Stage 4.0 identity/history/retry/reservation rules and amendment, Tasks 4.1–4.4: preserve existing public protocol API and storage semantics.
- `docs/superpowers/plans/2026-10-08-stage-6-5-comparison-base-producer-contract.md` §§2, 4–6: §32 explicitly references its exact root/reservation structures and dependencies. That document remains **PROPOSED**; this plan consumes only structures/checks required by approved §32, not its unapproved producer implementation.
- `docs/superpowers/plans/2026-10-06-stage-6-5-m1-2-contract-freeze.md` §§3–5 supplies downstream namespace/chronology context, not authorization to implement M1.2.
- `docs/superpowers/plans/2026-10-12-stage-evidence-bundle-compatibility-contract.md` still says **DRAFT**. Runtime capability support nevertheless already shipped in PR #81 at this base; source and merged history establish that implementation, not permission for other draft work.

**Scope clarification:** the external controller confirmed a **gated Stage 4-only plan**: implement all independently specified §32 consumer/history/recovery behavior; external producer/policy prerequisites stay blocked. Do not stop the independent Stage 4 work merely because live Stage 5/6.5 activation is unavailable. Stop any individual step that would require inventing an external contract.

### Already merged — do not implement again

PR #81 owns `compile_bundle`, closed declaration verification, `supports_stage_evidence`, supported identity fingerprints, optional `stage_evidence_contract` schema property, the three canonical bundle copies, and capability/retention tests. `supports_stage_evidence(bundle)` and `supports_review_evidence(bundle)` already exist in `core/kapisch_core/bundle.py`. Call them on the exact digest-verified retained bundle; do not inspect capability fields independently. Stage-only support does not imply review support.

**No schema, policy-in-bundle, identity fingerprint, compiler, generated-copy, legacy-fixture, or retained-bundle changes are needed or allowed by §32.** Keep all retained bytes/digests unchanged. A requirement for such a change is a stop-and-review condition, not a reason to regenerate.

### Remaining Stage 4 behavior

Allow exactly one evidence-only second `planned` observation for an eligible graph-free task reviewer attempt, bind the unique exact producer-owned reservation/root, enforce pre-dispatch and chronology vetoes under shared locks, and support distinct missing-binding recovery and read-only already-bound validation. No generic same-status append, new status/identity/field, dispatch, retry expansion, Stage 5 selection/production, Stage 6.5 persistence, or Stage 7 lifecycle implementation.

## 2. Source diagnosis and implementation seams

Current source confirms the amendment is absent:

- `_state._validate_history` rejects **every** later `planned` row. `_parse_state`, `_load_run_context`, `load_state`, and `_publish_state_locked` own parsing, retained-schema dispatch, revision/prefix checks, evidence digests, and atomic replacement.
- `protocol.py` is a seven-symbol facade; `tests/core/test_protocol_modules.py` freezes names/signatures. Preserve that API; do not add a public binder/recovery API or CLI command.
- `_locking._locked(repo, run_id)` already acquires repository then run lock. `_invocation.persist_request`, `reserve_operation`, and `publish_uncertainty` use it. Reuse this exact protocol; do not add a separate evidence lock.
- `_validation_inventory._inventory` inventories `invocations/` but returns when it is absent; it does **not** inventory request-only or request-input orphans. Its current supported invocation files are `planned.json`, `dispatch-uncertain.json`, `observed.json`, and `blocked.json`. New-append veto must also detect unsupported/malformed dispatch facts, not silently skip them.
- `validation._validate_state` blanket-refuses global-authority `approved_plan`, and `_validation_graph._validate_plan` expects legacy `{path, sha256}` plan refs. The §32 path needs a **narrow historical checked-PlanRef consumer**, not removal of all unsupported-gate protection.
- `_plan_candidate.validate_plan_approval_candidate` validates the historical exact plan/scope/bundle/authority chain. `_gate_approval.load_gate_approval` validates immutable approval/evidence. `_promotion.promote_plan` checks current eligibility and is **not** a historical loader; do not call it from already-bound validation or recovery that would repair approval state.
- `_invocation._validate_reservation`, `_validate_packet_inputs`, `_authority._validate_packet_authority`, and `_validation_inventory` mix existing packet structure with live-authority checks. Historical §32 validation must not inherit current-authority refusals or the legacy PlanRef shape; live request/reservation authorization must remain blocked where it is blocked today.

### File ownership (future implementation only)

| File | One responsibility / allowed change |
| --- | --- |
| `core/kapisch_core/_history.py` (new) | Extract existing structural history validation from `_state` without changing legacy behavior; implement only §32's exact structural exception and binding-position projection. No filesystem, approval, or lock access. |
| `core/kapisch_core/_review_target_records.py` (new) | Read-only contained census and canonical closed parsing of §32's root/reservation facts; validate paths, digests, identities, cross-candidate uniqueness and cross-stage root consistency. No producer, target-selection policy, Git recapture, or publication. Future external producers must reuse this contract reader rather than duplicate semantics. |
| `core/kapisch_core/_stage_evidence.py` (new) | Stage 4 lock-scoped orchestration: exact historical candidate/checked PlanRef validation, separate append eligibility, downstream-absence/pre-dispatch gates, and already-bound validation. Own public-facade-compatible load/publication wrappers, with unchanged signatures. |
| `core/kapisch_core/_state.py` | Retain low-level parsing/load/atomic publication, revisions and prefix ownership; delegate pure history checks. Ordinary internal publication must not introduce an unchecked binding. Freeze candidate/checked PlanRef references once binding pins them, just as operation/node bindings already protect execution references. |
| `core/kapisch_core/protocol.py` | Route public load/publication through the checked Stage 4 orchestration while retaining exact exports/signatures. Request/reservation/uncertainty exports unchanged. |
| `core/kapisch_core/_validation_inventory.py` | Reuse contained fact discovery for complete pre-dispatch veto, including request-only orphans; distinguish read-only historical packet validation from current execution authorization. No new invocation format or result producer. |
| `core/kapisch_core/_invocation_inventory.py` (new, focused extraction) | Descriptor-relative request/request-input/invocation and operation-scoped review-input discovery, including unreadable/unknown entries. Share discovery with veto and existing validator; retain existing chronology/ownership in `_validation_inventory`. Do not introduce a durable index. |
| `core/kapisch_core/_invocation.py`, `_authority.py` | Only minimal separation needed to reuse existing factual packet/reservation checks in historical validation without granting new live authority. Never disable current publication checks. If needed, extract common factual validation to a focused private module rather than growing `_invocation`. |
| `core/kapisch_core/validation.py` | Validate §32 histories under repository-then-run locks, invoke the historical chain reader, retain diagnostics API and unrelated unsupported-gate refusals; never auto-append during validation. |
| `tests/core/test_stage_evidence.py` (new) | Public-API append/reload/recovery, exact external-fact fixtures, negative identity/compatibility, subprocess and concurrency/fault coverage. |
| `tests/core/test_protocol.py`, `test_validation.py`, `test_protocol_modules.py` | Focused integration/regressions in existing owners; do not weaken old rejection vectors. `test_gate_approval.py` and `test_bundle.py` remain regression dependencies. |

Dependency direction matters: pure history/storage readers must not import state or high-level gate orchestration. `_stage_evidence` may consume `_state` and historical approval loaders; `_state` must not import `_stage_evidence`, `_promotion`, or `_gate_approval`. Keep raw internal load separate from full public validation to avoid recursive `load_state -> approval -> load_state` or nested flock acquisition. Reuse one shared atomic publication implementation: the checked coordinator validates under the locks, then commits that exact state through a narrow internal commit seam; ordinary internal publication cannot bypass new-binding eligibility. No public/caller `validated=True`, capability override, or lock-held assertion supplies authority.

Current sizes are already `_state` 480, `_invocation` 659, `_validation_inventory` 445, `_promotion` 479, and `storage` 521 lines. The history/inventory extractions above are responsibility-based, not cosmetic. Do not enlarge already oversized modules without focused decomposition or explicit reviewer justification. Keep unrelated Stage 5/storage refactoring out; inspect largest functions against AGENTS.md's 60/100-line triggers.

## 3. Interfaces and durable producer/consumer ledger

Unchanged supported calls:

- `publish_state(repo, run_id, state, expected_revision) -> None`: the sole public append boundary. A caller may propose the second row, but the implementation derives and checks the unique locator from persisted facts; caller contents are not authority.
- `load_state(repo, run_id) -> RunState`: full checked public loading of already-bound histories, read-only with respect to workflow artifacts/history.
- `validate_run(repo, run_id, gate=None) -> list[ValidationError]`: ordinary full historical validation, including §32; requested unimplemented gates still return `unsupported-gate`.
- Existing request/reservation/uncertainty signatures and authority checks remain unchanged.

Private interfaces should pass narrow immutable projections: structural creation/binding indices; exact validated candidate/PlanRef/bundle; and validated reservation/root locators. Keep `validate_existing_binding_locked(...)` separate from `validate_new_binding_locked(...)`; the former must never call the latter. No persistence/cache for projections. The checked coordinator owns locks; readers and locked helpers do not reacquire them.

| Durable fact / fields | Sole producer | Stage 4 consumption |
| --- | --- | --- |
| Run identity/workflow/bundle digest; first `planned` creation identity | Existing controller/Stage 4 state creation | Load exact persisted state; no new identities during binding/recovery. |
| Candidate, retained plan, approval/evidence, checked `PlanRef` | Existing approved Stage 5.5 producers | Use candidate-pinned bundle, exact GateApproval and equality of checked PlanRef to candidate/record. Never infer approval from candidate existence or repair missing approval/backlink in this operation. |
| `comparison-root/1`, candidate-derived path | **External Stage 5 target-selection producer** | Read exact bytes under run containment, candidate/plan/target/object-format match; preserve established root across stages. Stage 4 never chooses/recreates anchor. |
| `review-target-binding/1` reservation and all target/purpose/base/head/expected-ref fields | **External Stage 5 target-selection producer** | Census all candidates before filtering; closed canonical payload, exact digest-addressed filename and identities; derive locator from it. No reservation rewrite/replacement. |
| Second `planned` cumulative observation | **Stage 4 checked publication** | Exactly one existing evidence array plus exactly one reservation locator; persisted atomically after all checks. Later rows retain locator exactly. |
| `review-target/1`, comparison-base, review-scope | External Stage 5 target, Stage 6.5 base, Stage 6.5 scope producers respectively | Before new binding, detect premature facts and refuse. Later existence does not invalidate historical binding. Do not produce or validate a new downstream workflow in this scope. |
| Request, operation reservation, uncertainty, observations | Existing Stage 4/input/host owners | Complete persisted census vetoes a new binding; later supported, correctly owned facts are checked historically, never dispatched/adopted/repaired by this reader. |

Exact consumed structures are the **closed payloads** in the comparison-base proposal §2, only as incorporated by §32:

- Root keys: `protocol_version`, `comparison_root_contract`, `run_id`, `plan_candidate_ref`, `plan_id`, `target`, `object_format`, `anchor`.
- Reservation keys: `protocol_version`, `review_target_binding_contract`, `run_id`, `stage_id`, `plan_candidate_ref`, `plan_id`, `target`, `purpose`, `comparison_root_ref`, `comparison_root`, `comparison_base_ref`, `object_format`, `base`, `head`, `review_target_ref`.
- Root path: `review-inputs/comparison-roots/<candidate_sha256>.json` beneath the run. Reservation path: `review-inputs/review-target-bindings/<binding_sha256>.json`. Locator is exactly `{kind: "review-target-binding/1", path: <run-relative reservation path>, sha256: <binding_sha256>}`. Producer payload references use their exact repository-relative `.kapisch/v3/...` forms, never freely stripped arbitrary prefixes.
- Nested references/target/root binding are closed as specified there; digests are lowercase full SHA-256; anchor prefixes and lengths agree with `sha1`/`sha256`; only canonical `refs/heads/...` whole-branch targets qualify. No aliases, nulls, normalization, unknown/duplicate fields, self-digest fields, branch resolution, or inferred root. Check `base == root.anchor` and persisted final strictness; do not implement the later comparison-base producer's Git ancestry/capture workflow here.

## 4. TDD implementation sequence

Each step is **red -> smallest green -> focused refactor**. Record an actual failing behavioral assertion before implementing it; missing fixtures/packaging tools are not feature red tests. No commit is part of any step.

### 1 — Establish fixtures and preserve old history behavior

Create test-only external-fact builders in `test_stage_evidence.py`: retain a real supported bundle, create a task/scope and real approved candidate/checked PlanRef through existing public APIs (reuse the setup pattern in `test_gate_approval.py`), then publish a reviewer creation row. Construct exact canonical root/reservation bytes in temporary repositories only. These fixtures impersonate an **external earlier producer for testing**; they are not a new production Stage 5 API.

Extract `_validate_history` to `_history.py` and retain a private compatibility import if existing tests require it. First prove old valid/rejected histories remain identical. Add failing tests for exact second-row structure, later locator retention, creation-row locator forgery, third `planned` row, duplicate locator, and unchanged optional-field presence. Structure alone may recognize the exception but must not grant publication without contextual validation.

### 2 — Closed read-only root/reservation consumer

Red tests for zero/two reservations, two different candidate refs for the same stage, bad path/filename/hash, duplicate/unknown fields, noncanonical bytes, missing/wrong root, target/purpose substitution, unsupported bundle and cross-stage root replacement. Implement descriptor-relative complete census before candidate filtering using existing storage primitives and `_validation_json._json`; require canonical full bytes and exact identities. Missing expected evidence is a refusal; absent unrelated optional namespaces are not corruption. Unreadable/malformed inventory cannot establish absence or uniqueness.

Validate the historical candidate via `validate_plan_approval_candidate` and approval via `load_gate_approval`; compare the run/candidate bundle digests and reconstructed checked PlanRef exactly. Reuse these validators, not a second approval implementation. Do not call approval recovery/publication or `promote_plan`.

### 3 — Complete pre-dispatch and premature-publication veto

Red cases with **only a request** (no invocation directory), orphan input snapshots, reservation, uncertainty, observed/blocked facts, receipt/result/verification or unknown invocation facts, an operation-scoped `review-inputs/<operation_id>/pre-dispatch-fingerprint.json` or other dispatch-related input, malformed ownership, unreadable/symlinked inventory, and a restored valid planned prefix with surviving dispatch artifacts. Inventory all requests/facts before deciding whether they belong to this attempt; ambiguous/malformed ownership fails closed rather than being filtered away. Known unrelated valid facts must not spuriously veto another stage.

Census downstream target/base/scope namespaces, including unreferenced facts for this exact stage, not just expected target/base paths; use the M1.2 scope namespace `review-inputs/scopes/`. Reject premature publication and conflicting producer identities. Do not require or publish these future artifacts to validate a new binding. Preserve ordinary existing operation inventory semantics for histories that never use §32.

### 4 — Checked public append and lock integration

Red public-API test: `publish_state` accepts exactly one second `planned` row only after a separately durable creation row and unique root/reservation. Reject creation+binding in one initial publication, binding first introduced on a non-planned row, skipped/intervening observations for this attempt, third binding, changed kind/role/producer/scope/node/retry, extra evidence, altered prefix, stale revision, and batched progression that evades pre-dispatch checks.

Use the existing repository-then-run lock pair continuously over reload/revision/prefix checks, all reservation/dispatch/downstream census reads, approval validation and final atomic state write. Check task/no graph, reviewer/no node, `review/iteration` or `final/final`, exact retained stage+review capabilities, approved graph-free chain, and sole/latest creation row. Compare the proposed locator with the census-derived one. Both state and reservation remain unchanged on rejection. Do not broaden generic same-status transitions or live dispatch permissions.

### 5 — Cold recovery, idempotence, and read-only history

Use subprocesses with no retained Python/controller objects. A recovery caller reconstructs a proposal from persisted state and the exact reservation/root and calls the unchanged `publish_state`; the API independently rechecks everything. No extra public recovery command is required.

- Reservation durable/state old: append the one missing row only if every new-append check still passes.
- State write success/acknowledgement lost: reload, discover and validate exact binding; caller performs **no new publication**, leaving revision/bytes unchanged.
- Repeated recovery is a no-op; stale concurrent proposals reject normally. A failed writer cannot assume success or retry a write based on memory.
- Already bound: full public load/validation uses historical persisted approval/root/reservation/history, including exact later cumulative evidence and supported status transitions. Do not reapply pre-dispatch veto, latest-planned requirement, mutable authority/source freshness, current branch or downstream-absence checks.
- Prove historical binding still validates after valid `dispatch-uncertain`, terminal `complete`, and permitted cancellation/interruption histories. New live dispatch remains unsupported where currently unsupported. Preserve existing operation producer/chronology/digest checks through a narrowly fact-only historical path; do not add Stage 6.5 packet/result formats to make a fixture pass.
- If a later history uses an external packet/evidence contract not independently approved/implemented, retain that consumer's unsupported diagnostic; report it as an external acceptance gate, not as failure of the historical binding and not permission to implement that consumer.
- Missing binding with any later observation/dispatch fact is **not** repaired. Missing/tampered cited artifacts always block, even on historical loads. Read-only validation never writes history, repairs approvals, or creates evidence.

### 6 — Compatibility and negative matrix

Parameterize graph-free review/final success plus final strict-root rejection, eligible retry with unchanged creation/retry semantics, and separately authorized corrective follow-on with no retry link. Keep failed/completed predecessor restrictions; a new ID alone never permits a retry or root replacement.

Reject milestone/node/other workflows/roles/kinds, standalone findings-only use, unsupported/missing capability, candidate-only/no GateApproval, mismatched checked PlanRef, alternate bundle, changed candidate/plan/stage/root, arbitrary same-status evidence additions, terminal mutation, removed/reordered/duplicated old evidence, and later locator replacement. Test old legacy, global-authority pre-capability, review-only, stage-only and combined retained variants. Histories never using this locator retain **exactly** their old validation/unsupported-gate behavior; a generic evidence shape never implies eligibility. Old bytes/digests and public API remain unchanged after distribution upgrade.

### 7 — Concurrency and durability boundaries

Use independent processes and deterministic barriers (existing protocol tests provide patterns), not sleep-only races:

- Two same-revision binders: one append, one stale/conflict; cold reload has one locator and no duplicate row.
- Binder versus existing request publisher: the shared repository/run locks prevent inventory-to-state races. A request that wins first vetoes binding; a later request never retroactively invalidates historical binding and gains no new execution permission.
- Test-only external reservation writer honors the same lock pair: a second reservation is refused at its future producer boundary; if conflicting facts preexist, Stage 4 refuses rather than selecting. This tests lock interoperability, **not** a production Stage 5 producer implementation.
- Inject failures before state replacement, after replacement and during file/directory fsync/acknowledgement. Preserve the immutable reservation; recover from observed old/new durable state, never rewrite a row or publish downstream evidence after an uncertain acknowledgement.
- Test reservation-publication crash windows using the external fixture writer. Verify symlink/path escape, unreadable census, changed prefix, history bound and unsupported-platform failures preserve authority bytes and never dispatch. Lock-file infrastructure is not workflow evidence.

### 8 — Acceptance and external activation gate

**Stage 4 end-to-end acceptance:** real existing approved candidate chain -> public durable creation -> test-supplied exact external root/reservation -> public checked bind -> fresh-process load/validate -> crash/recover/no-op -> later supported historical progression -> unchanged historical validation. Every rejection asserts unchanged state revision/history/reservation/root and no target/base/scope publication or dispatch. Snapshot bytes before read-only calls and compare afterward.

**Not yet runnable as a live product workflow:** real Stage 5 root/reservation/target production -> Stage 6.5 base -> scope -> invocation/result. §32 requires this downstream order, but Stage 5 target-selection policy/API has no approved implementation contract in the inspected repository, and the comparison-base proposal remains unapproved. Do not implement these to claim green E2E. Add/execute real cross-producer integration acceptance only after their independent approvals and implementations, reusing Stage 4 checks and the same locks. Report Stage 4 consumer acceptance separately from blocked live activation.

## 5. Commands and review evidence

From the worktree root, use the supported Linux/Python 3.11 CI-equivalent environment (with packaging build prerequisites already provisioned); do not change dependencies or production code to fix this planning environment.

```bash
# Each red/green slice: select the new test name with -k.
PYTHONPATH=core python -m unittest discover -s tests/core -p test_stage_evidence.py -k '<case>' -v
PYTHONPATH=core python -m unittest discover -s tests/core -p test_stage_evidence.py -v
PYTHONPATH=core python -m unittest discover -s tests/core -p test_protocol.py -v
PYTHONPATH=core python -m unittest discover -s tests/core -p test_validation.py -v
PYTHONPATH=core python -m unittest discover -s tests/core -p test_protocol_modules.py -v
PYTHONPATH=core python -m unittest discover -s tests/core -p test_gate_approval.py -v
PYTHONPATH=core python -m unittest discover -s tests/core -p test_bundle.py -v
PYTHONPATH=core python -m unittest discover -s tests/core -v
PYTHONPATH=core python -m unittest discover -s tests/conformance -v
PYTHONPATH=core python tooling/build/build_bundle.py --check
python -m compileall -q core/kapisch_core
git diff --check
git status --short
```

This plan was source/spec-checked at the stated base. Existing baseline runs during planning: protocol-module **7/7**, validation **36/36**, bundle **36/37**, canonical bundle `--check` **pass**. The bundle-suite failure is `test_installed_wheel_contains_exact_bundle_resource`: current Python **3.14.7** cannot import `setuptools.build_meta`. This is an environment/packaging blocker, not evidence for changing Stage 4 or weakening that test. Re-run in the supported provisioned environment; full core/conformance/hosted CI were not claimed run here.

After implementation, require independent external read-only review of the whole supplied diff against §32 and AGENTS.md, especially public API preservation, no new import cycles/nested locks, factual/history versus live-authority separation, exact retained bundles, complete pre-filter census, and no producer creep. Report changed-module line counts/largest functions and any decomposition justification. Standalone reviewer findings never approve scope or authorize fixes/publication.

## 6. Risks, hard stops, and completion checklist

- **External approval gate, not a Stage 4 design gap:** §32 specifies the binding consumer, but explicitly leaves Stage 5 target-selection policy/API undefined. No inspected approved source supplies it. The comparison-base proposal and remaining M1.2 consumers are independently gated. Live workflow activation remains blocked.
- **Historical consumer trap:** deleting `unsupported-gate` globally or invoking `promote_plan` from a historical load would broaden authority or reject valid old facts. Allow only the exact §32 historical checked chain; keep execution refusals and unrelated history behavior intact.
- **Internal bypass/recursion:** all public binding publication paths must run contextual checks; raw parsing must never confer authority. Ensure existing internal plan/uncertainty publication cannot smuggle a new locator or replace pinned historical refs. Avoid approval-loader/state-loader recursion and reacquiring the same lock through a fresh descriptor.
- **Chronology limit:** persisted immutable artifacts and ordered history support the specified crash model, not proof against privileged fabrication or coherent rollback of all witnesses. Do not claim mtime-based chronology, authorship, universal suffix-loss detection, or a new anti-rollback journal.
- **Unspecified external details:** if detecting a required fact would need a new external namespace, payload, selection rule, or authority field not defined by §32's incorporated sources, stop that integration and report exact source/gap. Never add a schema/capability/migration or normalize unsupported data to make acceptance pass.

Completion requires: exact single eligible append; exact no-op recovery; historical loading after valid progression; negative/concurrency/crash/compatibility matrices; no changed production producer ownership; all capability checks on exact retained bytes; no new public APIs/schema/generated bytes; green regression evidence (or separately reported environment failures); independent review; and an explicit statement that real Stage 5/6.5 activation remains blocked. Commits/publication remain unauthorized unless the owner separately authorizes them.
