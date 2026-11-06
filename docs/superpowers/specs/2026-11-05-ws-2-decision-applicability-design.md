# WS-2 Design Addendum — Decision Applicability, Reuse, Reassessment, Supersession

Status: APPROVED by owner 2026-11-06 (design and implementation plan; implementation authorized, changes stay uncommitted). Scope: tracker WS-2 (Phase 1), decision-level half of AC2.
Authority: [product realignment design](2026-10-25-kapisch-product-realignment-design.md) §5.1 and §8 AC2;
[execution-order amendment](../plans/2026-11-05-kapisch-execution-order-amendment.md) Phase 1;
PR #85 owner comment (2026-11-05, issuecomment-6652819982): judgment stays declarative and LLM-driven;
the deterministic kernel enforces authority, artifact integrity, dependency eligibility, lifecycle
transitions and acceptance boundaries; no separate agent runtime, no Python duplication of LLM reasoning.
Owner approval of this direction: 2026-11-05; revised design and implementation plan approved with implementation authorized: 2026-11-06 (conversation). No commit, push or merge is authorized.

## 1. Division of responsibility

| Concern | Owner | Mechanism |
| --- | --- | --- |
| Is there already an applicable decision (duplicate-question prevention, incl. decisions reported from external records)? | LLM coordinator | Markdown guidance; no kernel index of questions |
| Does the existing authorization still cover the proposed work (subject, scope, action)? Is a change to inputs substantive? | LLM coordinator | Markdown guidance; result and reason persisted in `applicability.json` |
| Are decision, applicability and WorkOrder bindings, digests and current Git inputs valid? Is the decision superseded? Is dispatch eligible? | Kernel | Fail-closed validation in `core/kapisch_core/_task_authority.py` and its helpers |
| Who creates a HumanDecision, including one carrying `supersedes`? | Human-input boundary | Host input adapter (pending-request) or coordinator (direct prompt). Never inferred. Real-harness producer coverage is WS-11 |

The kernel never decides semantic equivalence of questions, scope coverage or substantiveness of a change.

## 2. Decisions

1. **Cross-Run reuse.** A WorkOrder may reference an immutable HumanDecision stored in any Run:
   `decision_ref` must resolve under `.kapisch/runs/<run>/decisions/<decision_id>.json` (any `<run>`), keeping
   project-root confinement, digest verification, symlink rejection, exact `<decision_id>.json` filename and the
   existing project-wide `decision_id` uniqueness check. Decisions are never copied or re-created. The
   `decision_ref`-inside-current-Run restriction is removed; the `applicability_ref` restriction (inside the
   consuming Run) is unchanged.
2. **Reassessment and re-binding.** The decision and its `governing_inputs` snapshot stay immutable.
   - `applicability.json` gains `original_governing_inputs` and keeps `governing_inputs` as the **assessed**
     (current) inputs. `original_governing_inputs` must equal the decision's snapshot exactly; the
     WorkOrder's `governing_inputs` must equal the applicability's assessed inputs. When
     `original_governing_inputs` is absent the record keeps today's meaning (assessed must equal the decision
     snapshot), so records written under #85 stay valid.
   - Assessed inputs are validated against current HEAD, index and working tree exactly as today
     (`_task_governing_inputs.py`). Original inputs are historical and are only shape- and equality-checked.
     Both historical snapshots use the actual producer's shape: a list, possibly empty, of exact `{ref, digest}`
     records with non-empty string refs and lowercase SHA-256 digests. Duplicate and opaque/non-Git refs are
     allowed historically; portability, uniqueness and freshness are selected/current WorkOrder requirements,
     not global historical-reader policy. Optional emitted `source_ref` and `approving_party` are absent or
     non-empty strings; null/absent request metadata is omitted by the producer. `external_artifact` requires
     a non-empty `source_ref`; `run_id` chooses storage and is not emitted as a decision field.
     A present empty `original_governing_inputs` is valid only when the decision snapshot is also empty;
     null/malformed/mismatching originals are invalid. Presence and absence remain distinct: present compares
     exactly with the original; absent requires assessed==original (#85). A selected decision with empty
     governing inputs still cannot authorize a WorkOrder, even with fresh assessed inputs and explicit
     original=[]: preserve `work order requires governing Git inputs`. Selected authority remains approval-only,
     non-empty and strict-portable/unique; assessed WorkOrder inputs remain non-empty and fresh in Git.
   - `subject` and `scope` in applicability and WorkOrder must still equal the decision's, byte for byte.
     Reassessment cannot widen or alter subject, authorization scope or action. Narrowing per task is WS-4.
   - `result` vocabulary: `applicable`, `not_applicable`, `ambiguous` (as documented today) plus
     `reassessment_required`. Only `applicable` with a non-empty `reason` authorizes dispatch. Any other
     recognized value blocks with a distinct deterministic error; an unknown or malformed value is a separate
     error. `superseded` is **not** a persisted result: it is a kernel-derived dispatch error (decision 3), so
     supersession has one source of truth.
   - If the existing authorization no longer covers the work, or coverage is ambiguous, the coordinator
     records `not_applicable` or `ambiguous` and obtains a fresh HumanDecision (Markdown rule).
3. **Explicit supersession.** A new HumanDecision may carry an optional `supersedes`: a non-empty list of
   `{decision_id, decision_ref, decision_digest}` objects (no repeated target ID or reference, no extra keys).
   - Produced by the human-input boundary together with the new decision; the coordinator never adds it.
   - Kernel validates: well-formed entries; target exists at `decision_ref` with the recorded digest and
     `decision_id`; no self-reference; no cycles through `supersedes` chains. `question_id` need not match.
     Validate structure, target identity, self-reference and cycles before verifying edge digests; an invalid
     cyclic record therefore has a deterministic cycle diagnostic without constructing a digest fixed point.
   - Consequence is **prospective and dispatch-only**: `validate_dispatch` and `claim_dispatch` reject a
     WorkOrder whose decision is the explicit target of any valid superseding decision found under
     `.kapisch/runs/*/decisions/`. Supersession is transitive and not undone by later supersession of the
     superseding decision. `validate_acceptance`, `validate_outcome`, claimed Runs and completed Outcomes are
     not re-judged for supersession and are never mutated.
   - Enumeration boundary: scanning reads every `*.json` under those directories; an unparseable or malformed
     decision file fails dispatch closed. The shared HumanDecision reader accepts the existing producer's
     `decision_type` vocabulary (`answer`, `correction`, `approval`, `risk_acceptance`,
     `external_effect_authorization`); only the selected WorkOrder authorizing decision must be `approval`.
     Valid historical empty-input decisions do not block unrelated dispatch and can be targets or superseders.
     Enumerate and parse decision files once per dispatch validation. Build temporary identity→record/path/digest,
     reference and forward-edge lookups; resolve targets, self/cycles, edge digests and selected eligibility from
     that same byte snapshot, including selected WorkOrder authority. No persisted index or module-level/cross-call
     cache. Complexity: O(N log N + E) time plus total input-byte parsing; O(N + E) auxiliary graph space plus
     parsed records. Each decision file is read once, not once per node/edge.
     Global graph integrity and eligibility validation run exclusively
     inside `validate_dispatch` (and `claim_dispatch` through delegation), never during `validate_run` or
     `_validate_workorder`; local decision loading does not validate `supersedes`. Thus an unrelated later
     malformed decision does not introduce a new acceptance/Outcome failure. PR85-009 is unchanged: incomplete directory enumeration under
     arbitrary local filesystem corruption is not covered.
   - `supersedes` is authority-bearing and optional. Older validators ignore it and would still honor the
     target; the contract states this version boundary. Pi producers do not emit it until WS-11.
4. **No global question identity.** `question_id` remains an opaque non-empty string. No question index,
   no same-question ambiguity rule.
5. **Scope coverage.** Semantic assessment is Markdown. Per-task authorization bindings, in-scope additions
   without re-prompt and out-of-scope blocking are WS-4. AC2 stays partial until both pass.

### 2.6 Retention of cross-Run decision authority

A referenced HumanDecision, and every decision reached through its `supersedes` chain, must remain retained
and byte-for-byte unmodified for as long as any Run or WorkOrder references it. Completion of the original
Run does not end this obligation. Removal or archival of a Run directory containing a still-referenced decision
breaks cold-restart validation: a missing selected decision fails closed with `missing referenced decision`;
a missing supersedes-chain target fails closed with the distinct `supersedes target is missing` diagnostic.
These are stable validation errors, not permission to repair, infer, copy or recreate authority. The kernel
never mutates decision files. Retention policy, archival mechanisms and garbage collection are out of scope
and owner-decided; no retention service or new runtime infrastructure is introduced.

Superseding decisions must also be retained. Supersession is derived at dispatch from the persisted superseder; deleting a superseder can make an older superseded decision eligible again, even when nothing references the superseder. Until a future retention/GC policy is approved, do not delete any HumanDecision record, including an apparently unreferenced superseder. (Owner clarification 2026-11-06.)

## 3. Record changes (producer ownership)

| Artifact | Field | Producer | Validator | Persisted-format effect |
| --- | --- | --- | --- | --- |
| HumanDecision | `supersedes` (optional) | human-input boundary | dispatch-only `_task_supersession` | additive, authority-bearing, documented version boundary |
| applicability.json | `original_governing_inputs` (optional), `result` += `reassessment_required` | coordinator | `_task_authority` | additive; absent field keeps #85 meaning |
| WorkOrder | none new; `decision_ref` may point to another Run; `governing_inputs` = assessed | coordinator | `_task_authority` | semantic relaxation of ref location only |

Cold restart: all state reconstructs from the decision files, applicability, WorkOrder and Run. No new durable
index, database, event log or second record.

## 4. Markdown contract changes

`core/contracts/task-first.md` (and resume/handoff guidance where it mentions decisions) state: the lookup
procedure before asking; reuse of an existing decision across Runs; the reassessment procedure and the
authority boundary in decision 2; when a fresh decision is mandatory; the `supersedes` producer rule; the
result vocabulary; historical-empty vs selected-current rules; and §2.6 retention obligations and missing-reference
errors. Full semantic guidance remains prose. A minimal stable labelled JSON block documents persisted applicability
and supersedes fields, closed results and stable diagnostics. Package checks assert headings/labels and metadata
against the kernel's actually used constants/error class, never sentence wording. Editing `task-first.md` does not feed `core-bundle.json`; if any bundle input changes,
regenerate all bundle outputs and run `build_bundle.py --check` and Pi `check:generated`. Package tests that
read the text may need focused updates.

## 5. Tests (tracked, deterministic adapters only, no host identifiers)

Cross-Run reuse; immutable original snapshot and mismatch rejection; successful reassessment after governing
input drift; drift without reassessment still blocked; changed subject or scope rejected; each blocked result
and unknown result; supersession with a different `question_id`; invalid references, digest mismatch,
self-reference and cycles; superseded decision blocks dispatch and claim but not validation of an existing
completed Outcome; external-record (`external_artifact` / `operator_reported_external`) reuse with source
attribution; fresh-process reconstruction; existing #85 records unchanged. Keep HEAD/index/working-tree
freshness tests green. Add explicit empty-historical scan/unrelated-dispatch and target/superseder cases;
selected empty-input rejection with the existing error; original=[] presence/mismatch semantics; one read per
decision and one glob per dispatch call (including two calls proving no retained cache); missing selected and
chain references after archival fail closed on cold restart; kernel decision files remain unmodified.

| Added revision-2 proof | Named regression(s) in the implementation plan |
| --- | --- |
| Producer snapshot shape; selected empty rejection | `test_ws2_historical_reader_matches_producer_snapshot`, `test_ws2_empty_selected_inputs_cannot_authorize` |
| Empty originals distinct from absence and mismatches | `test_ws2_empty_original_snapshot_presence_semantics`, `test_ws2_present_empty_original_mismatches_nonempty_snapshot` |
| Empty histories allowed in scan/chains and unrelated dispatch | `test_ws2_graph_accepts_producer_snapshot_and_empty_chain`, `test_ws2_dispatch_accepts_unrelated_empty_historical_inputs` |
| Single enumeration/read; no cross-call cache | `test_ws2_graph_reads_each_file_once`, `test_ws2_dispatch_reads_each_decision_once_per_call` |
| Retention/restart and immutable decisions | `test_ws2_missing_retained_reference_fails_closed_after_restart`, `test_ws2_kernel_never_mutates_any_decision_file` |
| Stable metadata rather than prose coupling | `PackageTests.test_task_first_decision_guidance` |

## 6. Non-goals

Semantic scope matcher; question index; database or event sourcing; new orchestration subsystem; DAG or
per-task authorization (WS-4); retry/recovery (WS-5); external-effect authorization (WS-6); Pi/Claude producer
changes (WS-11/WS-12); retroactive invalidation of Runs or Outcomes.

## 7. Open items for owner

1. **Pre-existing:** `validate_run` calls `_validate_workorder` for dispatch, acceptance and outcome, so the
   current-input freshness check already runs again in `validate_outcome`/`validate_acceptance`. A later input
   change can therefore already fail validation of a completed Outcome. This addendum preserves that
   behavior (owner: keep HEAD/index/working-tree freshness) and does not add new retroactive checks.
   Cross-Run reuse makes the situation more visible. Decide whether a follow-up should limit freshness to
   dispatch time; do not change it inside WS-2.
2. Tracker edits (merged #85, WS-2 evidence, AC2 task-level clauses assigned to WS-4 with a dependency) are a
   separate docs change after plan approval.
