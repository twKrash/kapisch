# WS-2 Design Addendum — Decision Applicability, Reassessment, Supersession, Run-Local Authority

Status: **Revision 3** (owner correction 2026-11-06, requested during PR #86 review; implementation authorized, changes stay uncommitted until separately authorized). Scope: tracker WS-2 (Phase 1), decision-level half of AC2.
Authority: [product realignment design](2026-10-25-kapisch-product-realignment-design.md) §5.1 and §8 AC2;
[execution-order amendment](../plans/2026-11-05-kapisch-execution-order-amendment.md) Phase 1;
PR #85 owner comment (2026-11-05, issuecomment-6652819982): judgment stays declarative and LLM-driven;
the deterministic kernel enforces authority, artifact integrity, dependency eligibility, lifecycle
transitions and acceptance boundaries; no separate agent runtime, no Python duplication of LLM reasoning.

**Foundational principle (Revision 3): Runs are isolated execution contexts; project knowledge is durable and
shared.** Independent Runs share durable project knowledge but never share execution authority, and canonical
Run history survives the lifecycle of temporary source worktrees.

### Replaced semantics (Revision 2 → Revision 3)

| Revision 2 (approved 2026-11-06, shipped in PR #86 at 13aa9df) | Revision 3 |
| --- | --- |
| A WorkOrder may reference a HumanDecision stored in any Run (cross-Run reuse) | `decision_ref` must live in the owning Run; cross-Run references are rejected. Prior knowledge is reused as context, not as authority |
| `decision_id` unique project-wide | unique within a Run; the same `decision_id` may exist in different Runs |
| Supersession graph enumerated over `.kapisch/runs/*/decisions/` | enumerated over the owning Run only; a superseder in Run A never affects Run B |
| One `root` = state location and Git source | `state_root` (primary checkout, holds `.kapisch/runs/<run_id>/`) and `source_root` (checkout or worktree whose Git inputs are validated) |
| Any `[A-Za-z0-9._-]` Run id; Pi producer falls back to the Pi session id | canonical lowercase UUIDv4 Run id, enforced by kernel and producer; no session-id fallback |
| `run_id` chose storage and was not a decision field | `run_id` is a required decision field and must equal the owning Run |
| §2.6 retention of cross-Run authority | §2.6 retention of Run history in `state_root` |
| WS2-KR-002 (cross-Run and same-Run supersession race) | resolved by Run-local ownership and post-claim decision re-read (§2.7) |

Unchanged: immutable decisions and snapshots, digest bindings, reassessment, applicability results, explicit
`supersedes`, fail-closed dispatch eligibility, prospective dispatch-only boundary, freshness checks.

## 1. Division of responsibility

| Concern | Owner | Mechanism |
| --- | --- | --- |
| Is there relevant project knowledge (tracked docs, ADRs, approved artifacts, Jira/Confluence, published policies)? Does it bear on this Run? | LLM coordinator | Markdown guidance; sources and provenance recorded in Run-local artifacts |
| Does the Run-local authorization still cover the proposed work (subject, scope, action)? Is a change to inputs substantive? | LLM coordinator | Markdown guidance; result and reason persisted in `applicability.json` |
| Are decision, applicability and WorkOrder bindings, ownership, digests and current Git inputs valid? Is the decision superseded within its Run? Is dispatch eligible? | Kernel | Fail-closed validation in `core/kapisch_core/_task_authority.py` and its helpers |
| Who creates a HumanDecision, including one carrying `supersedes`? | Human-input boundary | Host input adapter (pending-request) or coordinator (direct prompt). Never inferred, never by workers or reviewers |
| Which root is state and which is source? | Harness supplies, kernel validates | Explicit parameters, validated against Git; never guessed |

The kernel never decides semantic equivalence of questions, scope coverage, relevance of project knowledge or
substantiveness of a change.

## 2. Decisions

1. **Run-local authority.** HumanDecisions, applicability assessments, supersession, attempts and Outcomes
   belong to one Run and live under `<state_root>/.kapisch/runs/<run_id>/`.
   - `decision_ref` must be exactly `.kapisch/runs/<run_id>/decisions/<decision_id>.json` for the owning
     Run; any other Run directory is rejected deterministically (`decision reference is outside its Run`).
     Project-root confinement, digest verification, symlink rejection and the `<decision_id>.json` filename
     rule remain. `applicability_ref` stays inside the consuming Run.
   - Every decision record carries `run_id`, which must equal the owning Run (`decision run mismatch`).
   - `decision_id` is unique within the Run's `decisions/` directory, not across Runs. No global decision index, project-wide authority graph or cross-Run lookup exists.
   - A decision from Run A never authorizes or revokes execution in Run B.
2. **Run identity.** A Run id is a canonical lowercase UUIDv4 (`xxxxxxxx-xxxx-4xxx-[89ab]xxx-xxxxxxxxxxxx`).
   The kernel rejects any other form (path, `run.json.run_id`, decision `run_id`). The coordinator creates
   each Run before asking any question by calling the kernel's `create_run(state_root)`, which generates a
   UUIDv4 and exclusively creates the empty Run directory; the LLM never types an id. After compaction,
   restart or handoff the id is recovered from disk (open Runs have no `dispatch-claim.json`; ambiguity is
   asked, not guessed). A pending-input producer writes only into an existing, undispatched Run directory and
   otherwise blocks with a possibly-wrong-Run-id warning. Missing, duplicate, malformed or misrouted ids
   fail closed.
3. **state_root and source_root.**
   - `state_root`: the canonical project-level storage location, the **primary checkout** of the repository
     (its `.git` is the common Git directory). All Kapisch execution state lives at
     `<state_root>/.kapisch/runs/<run_id>/`. Feature worktrees never own it; removing a worktree cannot
     remove Run history.
   - `source_root`: the Git checkout (primary or linked worktree) whose HEAD, index and working-tree bytes
     are inspected for governing inputs. It may equal `state_root`.
   - Public kernel entry points take `state_root` (positional, replaces `root`) and a required keyword-only
     `source_root`. A single private validator (`_task_roots._validated_roots`) accepts the pair only when:
     both are existing directories and Git checkout roots (`rev-parse --show-toplevel` equals the path); both
     share one common Git directory; and `state_root` is the primary working tree (`rev-parse --git-dir`
     equals `--git-common-dir`, which is `<state_root>/.git`). Otherwise `invalid state_root/source_root
     mapping`. Bare, separate-git-dir and other layouts fail closed until a harness supplies an
     explicitly configured, validated mapping.
   - No discovery in the kernel. The harness determines the roots (the Pi producer derives the primary
     checkout from the session cwd using the same rule and fails closed); the kernel only validates.
   - Governing-input freshness (HEAD, index, working tree) runs against `source_root`. State files are read
     and written only under `state_root`. The Run records no machine path; `source_root` is supplied per call
     (like capabilities), so a Run validates from a cold process after its worktree is removed by passing a
     surviving checkout (typically the primary).
   - Portable records stay free of Pi-specific session identifiers.
4. **Project knowledge versus execution authority.** Tracked documentation and ADRs, approved architecture
   and implementation artifacts, external sources (Jira, Confluence or others the harness exposes) and
   explicitly published instructions are durable shared context and evidence. They are never reusable
   execution permission. The coordinator interprets relevance and preserves source provenance (via the
   Run-local HumanDecision `source_kind`/`source_ref`, and `reason`/`governing_inputs` in
   `applicability.json`); the kernel validates the resulting Run-local authorization. A human-approved PR
   merge makes approved repository artifacts shared project knowledge; it does not promote any Run-local
   HumanDecision. No knowledge database, synchronization layer or ingestion framework is introduced.
5. **Reassessment and re-binding (unchanged semantics, Run-local).** The decision and its `governing_inputs`
   snapshot stay immutable.
   - `applicability.json` has optional `original_governing_inputs` and keeps `governing_inputs` as the
     **assessed** (current) inputs. `original_governing_inputs` must equal the decision's snapshot exactly;
     the WorkOrder's `governing_inputs` must equal the applicability's assessed inputs. When
     `original_governing_inputs` is absent the record keeps #85 meaning (assessed must equal the decision
     snapshot).
   - Assessed inputs are validated against current HEAD, index and working tree of `source_root`.
     Original inputs are historical and only shape- and equality-checked. Both historical snapshots use the
     producer shape: a list, possibly empty, of exact `{ref, digest}` records with non-empty string refs and
     lowercase SHA-256 digests. Duplicate and opaque/non-Git refs are allowed historically. Optional emitted
     `source_ref` and `approving_party` are absent or non-empty strings. `external_artifact` requires a
     non-empty `source_ref`. A present empty `original_governing_inputs` is valid only when the decision
     snapshot is also empty; null/malformed/mismatching originals are invalid. A selected decision with empty
     governing inputs still cannot authorize a WorkOrder (`work order requires governing Git inputs`).
     Selected authority remains approval-only, non-empty and strict-portable/unique.
   - `subject` and `scope` in applicability and WorkOrder must equal the decision's, byte for byte.
     Reassessment cannot widen or alter subject, scope or action. Narrowing per task is WS-4.
   - `result` vocabulary: `applicable`, `not_applicable`, `ambiguous`, `reassessment_required`. Only
     `applicable` with a non-empty `reason` authorizes dispatch; other recognized values block with distinct
     errors; unknown/malformed values are a separate error. `superseded` is **not** a persisted result.
   - If the Run's authorization no longer covers the work, the coordinator records `not_applicable` or
     `ambiguous` and obtains a fresh Run-local HumanDecision.
6. **Explicit supersession (Run-local).** A new HumanDecision may carry optional `supersedes`: a non-empty
   list of `{decision_id, decision_ref, decision_digest}` (no repeated target ID or reference, no extra keys).
   - Produced by the human-input boundary with the new decision; the coordinator never adds it.
   - Every target `decision_ref` must be in the same Run directory as the superseder (cross-Run targets are
     rejected). Kernel validates well-formed entries; target exists with the recorded digest and
     `decision_id`; no self-reference; no cycles. Structure, identity, self-reference and cycles are validated
     before edge digests.
   - **Prospective and dispatch-only**: `validate_dispatch` and `claim_dispatch` reject a WorkOrder whose
     decision is the explicit target of any valid superseding decision **in the same Run**. Transitive; not
     undone by later supersession of the superseder. `validate_acceptance`, `validate_outcome`, claimed
     attempts and completed Outcomes are not re-judged and never mutated.
   - Enumeration boundary: exactly `<state_root>/.kapisch/runs/<run_id>/decisions/*.json` of the owning Run;
     every enumerated file validates; an unparseable or malformed decision fails dispatch closed. Other
     Runs' files are never read. The reader accepts the producer's `decision_type` vocabulary; only the
     selected authorizing decision must be `approval`. Each file is read once per dispatch call; no persisted
     index or cross-call cache. Complexity is bounded by the Run's own decisions.
   - `supersedes` is authority-bearing and optional. Older validators ignore it; the contract states this
     version boundary. Pi producers do not emit it until WS-11.
7. **Concurrency model and WS2-KR-002.** The supported model is exactly one active coordinator/authority
   writer per Run. Independent Runs share no authority graph, so no cross-Run race exists (this resolves the
   original finding, which concerned a shared graph). A Run's superseder is published by that Run's own
   human-input boundary, sequentially with that Run's dispatch. If a second writer violates the single-writer
   model, `claim_dispatch` still closes the scan-to-claim window: after creating the claim and marking the Run
   `claimed` it re-reads the Run's decisions and fails before host start if the selected decision is now
   superseded, leaving the claimed Run for operator reconciliation. Decision files are published atomically,
   so a superseder published before the claim is always seen. No lock or distributed synchronization is
   added. Exclusive claim creation still guarantees a single claim per Run.
8. **No global question identity.** `question_id` is an opaque non-empty string; no question index.
9. **Scope coverage.** Semantic assessment is Markdown. Per-task authorization bindings, in-scope additions
   without re-prompt and out-of-scope blocking are WS-4. AC2 stays partial until then.

### 2.6 Retention of Run history

Run history (decisions, applicability, WorkOrder, attempts, Outcomes) lives in `state_root`, independent of
source worktrees. A decision referenced by a WorkOrder and every decision reached through its `supersedes`
chain must remain retained and byte-for-byte unmodified for as long as the Run is validated. Superseding
decisions must also be retained: deleting a superseder can make an older decision eligible again. Removing a
Run directory breaks cold-restart validation: a missing selected decision fails closed with `missing
referenced decision`; a missing chain target with `supersedes target is missing`. These are stable validation
errors, not permission to repair or recreate authority. Retention policy, archival and GC are owner-decided
and out of scope; no deletion of Run history is introduced. Deleting a feature worktree after merge deletes no
Run history.

## 3. Record changes (producer ownership)

| Artifact | Field | Producer | Validator | Persisted-format effect |
| --- | --- | --- | --- | --- |
| Run | `run_id` canonical UUIDv4 | coordinator via `create_run` (exclusive Run directory) | `task_contract._run_directory` | stricter id form |
| HumanDecision | `run_id` (required) | human-input boundary (Pi producer from the request's Run id) | `_task_decisions` | additive but required; pre-realignment records without it are rejected, no migration |
| HumanDecision | `supersedes` (optional) | human-input boundary | dispatch-only `_task_supersession` | additive, authority-bearing |
| applicability.json | `original_governing_inputs` (optional), `result` += `reassessment_required` | coordinator | `_task_authority` | additive |
| WorkOrder | `decision_ref` must be in the owning Run | coordinator | `_task_authority` | reference location tightened |

Cold restart: all state reconstructs from the Run's persisted files under `state_root`; `state_root` and
`source_root` are supplied by the harness and validated. No new durable index, database, event log or second
record.

## 4. Markdown contract changes

`core/contracts/task-first.md` states: Run id minting and exclusive creation; `state_root`/`source_root`
and where records are written; Run-local decisions and the project-knowledge procedure (consult, cite,
obtain a Run-local decision); the reassessment procedure; when a fresh decision is mandatory; the
`supersedes` producer rule; the single-writer model and post-claim same-Run supersession check; the result vocabulary;
retention (§2.6) and the stable errors. A minimal stable labelled JSON block documents persisted fields,
closed results and diagnostics. Package checks assert headings/labels and metadata against the kernel's
actually used constants/error class, never sentence wording. Editing `task-first.md` does not feed
`core-bundle.json`; if any bundle input changes, regenerate outputs and run `build_bundle.py --check` and Pi
`check:generated`.

## 5. Tests (deterministic adapters only, no host identifiers)

Isolation: two Runs in one primary checkout with distinct ids and independent decisions; same `decision_id`
allowed in different Runs; cross-Run `decision_ref` and cross-Run `supersedes` target rejected; supersession in
Run A never changes dispatch eligibility in Run B; a malformed decision in Run B never fails Run A.
Roots: Run validates after its feature worktree is removed (state in primary, surviving `source_root`);
state persisted in the primary while Git inputs validate against the intended feature worktree (and fail
against a different checkout); incorrect/unavailable/foreign-repository/linked-worktree-as-state/subdirectory
mappings fail closed. Identity: non-UUIDv4, mismatching or missing Run ids and decision `run_id` fail closed.
Lifecycle: completed Outcomes unaffected by later supersession; cold-process reconstruction from persisted
Run-local artifacts. Retained: HumanDecision source attribution, applicability statuses, reassessment,
empty-historical rules, one read per decision per call, kernel never mutates decision files, retention
failures on cold restart. Pi: producer requires a Run id (no session fallback), writes to the primary
checkout from a linked worktree, records `run_id`, fails closed on malformed/missing ids and unresolvable
roots.

## 6. Non-goals

Semantic scope matcher; question index; database or event sourcing; global authority service, lock or
index; knowledge database or ingestion framework; DAG or per-task authorization (WS-4); retry/recovery
(WS-5); external-effect authorization (WS-6); Claude/Codex producers (WS-11/WS-12); retroactive invalidation
of Runs or Outcomes; migration of pre-realignment decisions.

## 7. Open items for owner

1. **Pre-existing:** `validate_run` calls `_validate_workorder` for dispatch, acceptance and outcome, so the
   current-input freshness check also runs in `validate_outcome`/`validate_acceptance`. A later input change
   (or a different `source_root`) can fail validation of a completed Outcome. Preserved here; decide whether a
   follow-up limits freshness to dispatch time.
2. A harness whose layout is not a standard primary checkout (bare, separate git dir) needs an explicitly
   configured, kernel-validated mapping; not designed here.
3. Pre-realignment decision records (no `run_id`, session-id directories) are rejected, not migrated.
