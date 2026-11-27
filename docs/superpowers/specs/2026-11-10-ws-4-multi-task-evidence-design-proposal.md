# WS-4 Multi-task WorkOrders and Evidence Handoffs — Design Proposal

Date: 2026-11-10
Status: **Draft for owner review; final-state outputs, resume context, harness-owned security decisions, handoff recovery, and Run layout approved; no runtime implementation authorization.**

This proposal records the owner-approved WS-4 evidence-handoff scope, final-state output validation, compact task-resume
context, harness-owned content-security decisions, and the existing Run location. Other expanded-format semantics remain
proposed and are not canonical.
It does not authorize runtime implementation or behavior. It adds no global lifecycle cursor, automatic successor
selection, unique-successor rule, or cross-Run authorization.

## 1. Governing material and boundary

The [product realignment spec](2026-10-25-kapisch-product-realignment-design.md) remains governing. This is the WS-4 expanded-format design. The first slice preserves the current `state_root` meaning and `<state_root>/.kapisch/runs/<run_id>` location. External Run-store configuration, relocation, and platform-specific permission machinery are deferred; they do not improve task delivery or compaction recovery. The WS-2 normative body and legacy semantics remain unchanged. Other expanded-format differences remain subject to complete design approval. Relevant sources:

- Product spec, especially §§5.1–5.7 and §6.
- [WS-2 decision applicability design](2026-11-05-ws-2-decision-applicability-design.md), especially §§2.1–2.9 and §7.
- [Task-first core contract](../../../core/contracts/task-first.md), which remains the current implemented single-task contract.
- [Execution-order amendment](../plans/2026-11-05-kapisch-execution-order-amendment.md), which assigns WS-4 the DAG, task/attempt identity, and aggregation barrier; task-level authorization
  is tracked under WS-4 in the tracker. Phase 1 is deterministic/test adapters only; production Pi support remains
  WS-11.

### WS-2 compatibility and retained Run location

| WS-2 rule | Legacy single-task format | Expanded-format proposal |
| --- | --- | --- |
| Run-local decision/applicability authority and one coordinator | Unchanged | Unchanged; revisions remain in the same Run and use its authority unless a new HumanDecision is required. |
| §2.1 cross-Run lookup | No cross-Run authority lookup | A selected evidence import may read only named evidence artifacts and persists a consumer-owned result; it never imports authority. |
| §2.2 open-Run discovery and §3 Run creation | Legacy discovery/recovery behavior unchanged | Expanded continuation requires the harness-persisted explicit Run reference; the harness produces and the kernel validates it. Missing/invalid continuation reference prompts for Run ID or explicit search permission; no guessing, scanning, or replacement Run. Unrelated workflow without reference starts fresh. Production harness support is WS-11. Legacy discovery/recovery remains unchanged; every legacy reader/input producer must reject expanded state before shared deployment. |
| State-root resolution and Run storage location | Current API `state_root` means the primary Git checkout; `create_run` validates it as a Git checkout, then appends `.kapisch/runs`. | Unchanged for this slice: keep `state_root` as the primary checkout and store Runs at `<state_root>/.kapisch/runs/<run_id>`. External Run-store overrides, migration, root discovery, and platform-specific permission handling are deferred to a separate design only if a concrete need arises. Cold restart uses the explicit Run reference and current location; a missing requested Run prompts or fails stably, with no scan or replacement.
| Expanded HumanDecision admission (format-specific) | Legacy input producer remains restricted to the existing undispatched-Run rule, including `dispatch-claim.json` check | Expanded Run accepts decisions from the human-input producer only while valid/open, through the serialized final Outcome publication boundary. Malformed/forked history or malformed Outcome state fails closed, never interpreted as open. The durable authorization decision commit (the point at which the kernel publishes the task's authorized claim/attempt decision) marks that task started for source admission: a genuinely new source for that task after this point requires HumanDecision; before it, selection may occur within approved scope. A provisional attempt-ID reservation is allocation only; it neither closes admission nor authorizes use or execution. The claim request freezes selected source/evidence refs; changing them requires a new request and full admission recheck. |
| Expanded supplemental operation approvals | Legacy HumanDecision shapes/decision types unchanged | Human-input producer owns `operation_authorizations[]` on supplemental approvals using existing decision types. Entries bind operation, basis WorkOrder revision digest, target tasks and operands; kernel validates Run, operation, basis, target and consumer. Supplements are distinct from selected base approval and cannot widen or implicitly supersede it. |
| §2.5 applicability reference and freshness | Existing `<run>/applicability.json`; per-call `source_root` behavior unchanged | Revisioned applicability; each WorkOrder revision binds `baseline_workspace_id` and exact baseline-observation reference/digest. The adapter must resolve that binding; no session-cwd or `source_root` fallback. Task subsets are checked in assigned execution workspaces; top-level union at baseline. |
| §2.6 retention | Run history is retained; no implicit deletion | Retain Run history and selected Run-local evidence needed for continuation or to explain accepted work. Human/skill chooses canonical project artifacts and their long-term storage; Kapisch does not pin Git objects or archive those artifacts. D9 permits cleanup of unreferenced scratch copies, rebuildable indexes/caches, and the non-authoritative resume note after Outcome is sealed. |
| §2.7 single-writer and post-claim re-read | Legacy single-writer/post-claim decision re-read unchanged | Expanded format uses the existing local kernel lock/publication boundary for short serialized authority publications; task admission rechecks current eligibility and selected bindings. No lock is held across setup or worker execution. |

This table describes proposed expanded-format differences only; it does not supersede WS-2's normative Run location or requirements. The WS-2 document gains only an informational note, and all legacy WS-2 rules remain normative. The current runtime remains governed by the task-first contract until implementation is separately authorized. Other expanded-format behavior remains subject to complete design approval. Every legacy reader and input producer must reject unsupported expanded state before shared-state deployment; isolated test roots do not establish that guarantee.

### Owner-confirmed scope and governing requirements

- The owner approved evidence-only handoffs in WS-4; imported evidence never grants or reuses authorization. This
  draft records that scope approval; canonical runtime changes still require approval.
- Product spec §5.1(5–6) and WS-2 §2.9 require reassessment and demonstrably in-scope task additions without
  duplicate approval.
- Each Run retains its own decision and applicability. The coordinator judges semantic scope; the kernel validates
  structural bindings.
- Phase 1 remains deterministic/test adapters only; production Pi support remains WS-11.
- Durable facts must be reconstructible after restart from persisted records with explicit producers.

### Owner choices recorded; overall design approval pending

The owner replaces the earlier D1(A) actual-write prohibition with final-state output validation: declared task outputs are compared with the post-setup worker baseline, while transient writes that do not appear in delivered output are not tracked. The owner approves a compact task-resume note and delegates content-security decisions to the active harness policy; the kernel does not impose a cross-harness secret-pattern scanner. The kernel still enforces scope, containment, symlink safety, exact byte identity, and durable decision bindings. D2(A) through D8(A) remain selected; D9 records context-efficient retrieval and post-Outcome cleanup. Actual stop-and-restart execution is deferred to WS-5; WS-4 records interrupted/unknown state and keeps the Run blocked. Other expanded-format semantics remain proposed pending complete design approval. WorkOrder revisions remain immutable; each claim keeps its initial revision binding, while later human-authorized context amendments are appended to the active attempt rather than rewriting that claim.

### User workflow and context continuity

One Run represents the durable user-requested workflow, not one chat session or one agent. The SDD lifecycle may use
triage, research, human architecture decisions, spec/plan, review, and implementation/verification artifacts. Stage
artifacts remain external/Git artifacts with their original authors and provenance; no core stage-state record,
stage counter, or stage transition is added. Before the first WorkOrder, the coordinator selects relevant artifact
references and the harness persists them in its existing durable session/handoff metadata alongside the explicit Run
reference. After a WorkOrder exists, bind consumed artifacts through `evidence_inputs` and context manifests. The
coordinator selects; harness persists references; original artifact authors remain producers. References include
stable source identity/version or digest as applicable, are evidence not authority, and missing required references
block continuation rather than prompting an implicit scan. Reconstruct the next valid action from validated
decisions and referenced evidence, never a remembered stage label. Human answers and pivots are authority;
researcher/architect/worker outputs are evidence until accepted.

An expanded Run resumes only when its explicit Run ID is persisted in the harness's existing durable session/handoff
metadata before continuation relies on it; the harness produces that reference and the kernel validates the
referenced Run. This is not discovery by scanning Runs. Missing/invalid reference during requested continuation
requires asking for the Run ID or explicit permission to search; never guess, scan, or silently create a
replacement. A genuinely unrelated workflow with no Run reference starts a fresh Run. Older-Run searches require
explicit human direction. This expanded rule does not change legacy WS-2/task-first recovery behavior; production
harness support remains WS-11. A researcher searches older Run evidence only when the human explicitly asks;
selected evidence is then deliberately imported, never as inherited authority.

Context is retrieved selectively: indexes locate relevant sources, and each stage/subagent receives a bounded
context package of relevant passages and source/version references rather than the whole corpus. The index is a
search aid, not authority. Durable decisions, WorkOrder revisions, attempt history, and provenance needed to explain
accepted work belong to Run history; unreferenced scratch copies and rebuildable indexes may be cleaned up under §7.

While a task is active, the coordinator may maintain one compact task-local `resume.md` checkpoint in the Run. It
contains status, canonical references, bounded summaries, unresolved questions, next action, logical workspace
reference, and output/validation references; it contains no raw payload excerpts, transcripts, or hidden reasoning.
The coordinator owns its semantic content. Before publication, the active harness applies its own security policy and
binds an assessment to the exact note digest; the kernel atomically publishes only with that assessment. A blocked,
missing, or ambiguous assessment means the optional note is omitted. WorkOrders, HumanDecisions, captured outputs, and
validation records remain authoritative. On restart, the coordinator loads the note only from the explicit Run,
checks its references, and inspects workspace/output state; canonical records and workspace evidence override it. If
missing or stale, a replacement may be written only from available evidence, otherwise ask the human. After Outcome
is sealed, an operator may remove the note and unselected scratch; WS-4 performs no automatic cleanup. A crash can
lose uncheckpointed reasoning; recovery must re-inspect persisted state and ask rather than guess.

## 2. Format routing and compatibility options

Keep the current single-task validator and retained Run-state behavior unchanged. Do not call the expanded task
format “v2”: the core already uses v2 for persisted Run state. Proposed identifier: `multi_task_dag_v1`.

Run-first routing is required, and selected D6(A) preserves every previously accepted legacy shape. Legacy
expanded-state rejection relies on `dispatch_state` validation in `task_contract.py:97–102` and WorkOrder `tasks` rejection in
`_task_authority.py:136–137`; both exact checks and all legacy readers/input producers must reject unsupported expanded state before
shared deployment. An unknown extra key alone is not a boundary. The old format remains supported without migration;
only new expanded Runs receive multi-task behavior. In either case, the new validator routes from the validated Run
format first, then requires matching Run/WorkOrder identifiers and schema; mismatches fail closed, never fall back
to v1.

Allocate the Run directory exclusively, then publish its immutable envelope file without replacement using the
existing file-publication boundary. An existing destination remains untouched. An incomplete allocation without a
valid envelope is inert and cannot execute; it need not be invisible or atomically published as a directory.
Preserve isolated D7(A) roots until shared coexistence is demonstrated, and preserve the accepted
power-loss/storage-rollback limitation.

| Run envelope | WorkOrder shape | Required result |
| --- | --- | --- |
| Legacy v1 shape | Singular `task`, no `tasks` | Preserve existing v1 behavior and unknown-field semantics; no migration. |
| Legacy-looking record with exact new format key (D6(B) only) | Any shape other than a valid expanded envelope + `tasks[]` | Route to expanded validation and reject; D6(B) explicitly accepts this compatibility exception. Under D6(A), retain legacy unknown-field behavior for structurally legacy records. |
| Expanded `multi_task_dag_v1` envelope | Non-empty `tasks[]`, no singular `task`, exact matching format | Validate as the expanded format. |
| Expanded Run envelope | Missing `tasks`, unknown/mismatched identifier, or mixed shapes | Reject; never fall back to v1. |
| Legacy Run envelope | `tasks[]` or expanded-only WorkOrder shape | Reject under the legacy validator. |

The exact envelope/discriminator must be checked against the current validator and all repository fixtures. A
fixture audit cannot prove private retained-state compatibility. Selected D6(A) preserves every previously accepted
legacy shape. Never infer format from timestamps, filenames, controller memory, or implicit scanning.

## 3. WorkOrder revisions and task authorization

One coordinator serializes the Run control plane. It authors WorkOrder/applicability revisions and initiates claims;
the proposed kernel publication boundary validates and exclusively publishes canonical records. Workers do not
publish authority. Each revision is a full immutable snapshot with a monotonic sequence and parent digest. One
assessment record per revision contains per-task scope and carry-forward entries, avoiding one tiny file per
task/revision.

The top-level `governing_inputs` must equal the Run applicability assessment and remain the run-wide freshness gate. Each
revision stores coordinator-selected `baseline_workspace_id` plus the exact adapter-produced baseline-binding observation
reference and digest. The adapter records the logical ID, repository identity, and durable adapter-owned workspace
reference; host paths/handles remain adapter metadata. Missing, ambiguous, substituted, or invalid binding blocks; no
session-cwd or arbitrary `source_root` fallback. Authorization binds existing plan/authority/handoff evidence and
selected predecessor evidence, not future setup snapshots or completion observations. This expanded binding does not
change legacy WS-2 per-call `source_root` behavior. Each task declares a non-empty `governing_inputs[]` subset whose
union equals the top-level set, plus `write_targets[]` for intended final outputs; transient writes are not monitored.
For each fresh task workspace, validate the task's governing-input subset against the baseline before applying any
handoff. A `repository_state` handoff's destination is in the dependent task's declared `write_targets[]`; an
evidence-only handoff has no workspace destination.

Before attempt-ID reservation or authorization, the kernel validates the selected repository-state destination set as a
whole. It applies each declared mapping to every selected file or deletion entry, normalizes the resulting safe relative
paths, and rejects duplicate targets (even when contents match) and any target that is a path-component ancestor of
another file/deletion target; common directory prefixes are allowed. Evidence-only handoffs have no destination and do
not enter this check. A conflict produces a deterministic refusal with no reservation, attempt, setup write, or worker;
there is no coalescing, last-writer-wins behavior, or implicit merge.

Before claim authorization, the dependent harness assesses the exact selected predecessor bytes. Any harness-owned
review must finish with `allow` before authorization; `block`, missing, or pending assessment refuses the claim with
no attempt or setup writes. The authorization binds that assessment. After authorization, materialize only selected,
digest-verified manifest entries and record the same assessment in the handoff observation; then record the post-setup
worker baseline. Compare final outputs against that post-setup baseline, so
unchanged handoff bytes are not recaptured as dependent outputs. The dependent consumes those exact bytes by reference
to the predecessor manifest; changed or new final bytes are a new dependent output and receive the dependent
harness's security assessment. A handoff may overlap a governing-input path only if that exact path is authorized in
the dependent WorkOrder; the original baseline input is validated before overlay and remains separately identified.
Capture declared additions, replacements, and deletions against the post-setup baseline, validate scope and acceptance,
and seal output evidence before workspace release. Setup observations and the post-setup baseline are attempt evidence.
Workspaces are fresh and separately bound; cross-task workspace assignment and same-task stop-and-restart are out of
scope for WS-4. A confirmed interruption is recorded from adapter-owned stop evidence; partial outputs are not captured,
and the task/workspace binding is preserved. Unknown activity retains active occupancy under D8(A). Both conditions
block completion; WS-5 owns fresh-attempt recovery.
No cleanup or reset is implied. Each WorkOrder revision binds exact input digests separately from the frozen semantic
task contract.

External context such as a wiki page, GitHub issue, or Jira ticket is selected as `evidence_inputs[]`, not silently added by
a researcher or worker. Planned predecessor handoffs are declared `handoffs[]` selectors, not governing inputs or
surprise external sources. The coordinator records the source/version and affected tasks in a new WorkOrder revision
and, when applicable, a context amendment; the original task contract and claim remain unchanged. By default the
harness steers an affected live worker with the amendment and asks it to reassess its current work. WS-4 does not
start a new attempt after a human stop request: confirmed interruption is recorded without partial-output capture and
blocks completion while preserving the task/workspace association; unknown activity retains active occupancy. Fresh-
attempt recovery and checkpoint compatibility belong to WS-5. The core records authorization and
history but does not depend on a particular harness steering API.

Each task also declares scope, acceptance criteria, required capabilities, `depends_on[]`, frozen `handoffs[]`, repository
access, and `write_targets[]` (required for mutating tasks; empty only for read-only work). Each handoff selector has
stable `handoff_id`, predecessor task ID (which must appear in `depends_on`), output role/artifact selector, mode
(`evidence_only` or `repository_state`), and an optional destination mapping. For `repository_state`, a destination must be a path in the dependent task's declared `write_targets[]`; overlap with a
governing input is permitted only when that exact output path is explicitly authorized. `evidence_only` handoffs have no
destination.
These selectors are part of the semantic task-contract digest/freeze rules. Handoffs are never `governing_inputs` and
do not enlarge the Run input union. Capture and materialize only selected output-manifest entries, never an unfiltered
live workspace. Validate source, selector, and destination using existing facilities. No mechanism is required to
observe or report writes that are absent from the final selected outputs.

Task IDs must be unique, path-safe, and case-fold-unique. Dependencies must refer to declared tasks and contain no
duplicate, self-edge, or cycle. A revision may add a demonstrably in-scope task without a duplicate approval. It may
not silently remove or narrow any approved task, whether claimed or not: that is a scope change requiring a
Run-local HumanDecision referenced by the revision assessment. Every task that appeared in any revision remains in
final accounting with an explicit disposition; removal never erases history. A claimed task's semantic contract
(identity, scope, dependencies, acceptance criteria, capabilities, handoffs, and write targets) is frozen. Input
IDs/digests are a separate revision binding; changed digests do not rewrite earlier claims and any reuse is governed
by D4. A semantically changed execution intent receives a new task ID. Competing revision heads, broken parent
digests, or sequence gaps fail closed. This slice provides no reconciliation or repair procedure.

One coordinator-produced revision assessment records for each task the Run/revision/task identity, exact WorkOrder
and semantic task-contract digests, task input-binding digest, selected Run-local decision/applicability references,
coordinator scope result (`in_scope`, `out_of_scope`, or `ambiguous`), and reason. Under selected D4(A), a carry-forward
entry binds the source claim/result, structural equality checks, changed authority/inputs, and the coordinator's
semantic compatibility judgment. Changed task meaning requires a new task ID; old results are carried only when this
explicit assessment finds them compatible. The kernel verifies semantic task-contract structure and exact
input-binding digests; it does not infer compatibility. Carry-forward never rewrites the historical claim or makes
an old claim under a superseded decision newly authorized.

The coordinator owns semantic scope judgment; the kernel validates identities, references, digest equality, revision
sequence, and scope-record shape. Demonstrably in-scope task additions proceed under the existing decision without
another scope-approval ceremony. A planned predecessor handoff is a frozen `handoffs[]` selector, not a governing
input or surprise source. Ambiguous or materially out-of-scope changes pause affected dispatch for a Run-local
HumanDecision. Missing, stale, mismatched, or out-of-scope assessments cannot authorize dispatch. A later Run still
requires its own authorization.

There is one selected base approval per WorkOrder revision; it retains WS-2's approval-only semantics and exact
Run-level subject/scope equality plus applicability checks. A per-task scope-subset assessment is a coordinator
judgment, not separate per-task approval. Supplemental operation approvals use `operation_authorizations[]` on a supplemental
HumanDecision using an existing `decision_type`; each entry binds `operation`, `basis_workorder_ref` and digest, explicit `task_ids`,
and operation-specific `operands`. Examples: removal names exact tasks; scope reduction names exact task IDs and
authorized reduction/proposal reference+digest; post-start source addition names affected tasks and source
identity/version or acquisition selector. WS-4 has no restart operation; stop-and-restart is deferred to WS-5. The human-input producer alone
authors these fields; the coordinator cannot attach them to a generic answer. The kernel validates owning Run,
operation, basis revision, target and consuming revision/request. For a harness-authorized `capture_exception`, operands are exactly the kernel-produced output-capture request
reference/digest and attempt ID; the immutable request binds the harness identity, effective security-policy reference
and digest, disposition/rule findings, and complete sorted output selector/path/kind set and file-byte digests; deletion entries have no byte digest. One approval authorizes that entire request only. A
supplemental approval is not the selected base approval and is not forced through base subject/scope equality; it
cannot replace, widen, or implicitly supersede
base authority or retroactively authorize a claim. `source_ref` remains provenance and is not repurposed. Only
explicit `supersedes` authored by the human-input producer supersedes. Authorization binding order is: Run-local base
Decision → applicability revision → WorkOrder revision → revision assessment → claim. Claims retain original
revision/authority bindings; reassessment never rewrites past facts or imports authority.

## 4. Immutable execution records and crash behavior

The expanded-format Run index records its task format and immutable Run identity; it does not carry mutable task
status. Proposed Run-local records are:

```text
.kapisch/runs/<run_id>/
  run.json                                  # complete format envelope; no-replace published
  workorders/<revision_seq>.json
  applicability/<revision_seq>.json
  decisions/<decision_id>.json
  revision-assessments/<revision_seq>.json  # per-task scope/carry-forward entries
  tasks/<task_id>/claim-requests/<request_id>.json  # references frozen handoff_id and realized accepted bindings
  tasks/<task_id>/attempt-reservations/<request_id>.json  # kernel-owned attempt ID/output-location reservation; not execution authority
  tasks/<task_id>/claims/<claim_seq>.json   # append-only per-task chain
  tasks/<task_id>/claim-decisions/<request_id>.json  # kernel start/refusal result
  tasks/<task_id>/context-amendments/<amendment_id>.json  # proposed/delivered/acknowledged/assessed linkage
  tasks/<task_id>/context-manifests/<context_id>.json  # selected context; before authorization
  tasks/<task_id>/resume.md                       # coordinator-authored, harness-assessed optional context; non-authoritative
  tasks/<task_id>/output-capture-requests/<attempt_id>.json  # one kernel-owned review request per attempt; contains deterministic capture_id

  tasks/<task_id>/attempts/<attempt_id>.json  # kernel-owned canonical result
  outputs/<attempt_id>/manifest.json  # sole canonical output manifest, immutable/no-replace
  outputs/<attempt_id>/<manifest_digest>/  # content-addressed package bytes; no second manifest
  outputs/<attempt_id>/.publication-staging/  # kernel-owned scratch, never authority or package inventory
  tasks/<task_id>/observations/<observation_id>.json  # kind-tagged repository_handoff, worker_interruption, or amendment_transport fact
  tasks/<task_id>/validation/<attempt_id>.json  # kernel validation/result for an authorized attempt
  validation/final/<gate_sequence>.json  # kernel final structural validation
  workspace-observations/<observation_id>.json  # baseline_workspace_binding or execution_workspace_binding; setup baseline is attempt evidence

  aggregation-requests/<invocation_id>.json  # coordinator intent
  aggregations/<sequence>.json               # kernel envelope + aggregator payload
  coordinator-gates/<sequence>.json  # per-task eligibility/amendment assessments; final completion_assessment
  evidence-capture-requests/<capture_id>.json
  evidence/<input_id>/<manifest_digest>/manifest.json
  evidence-imports/<import_id>.json
  outcome.json                              # kernel-published after completion and final-validation recheck
```

The layout and producers in §9 define the proposed record contract; implementation must preserve them or obtain
design approval for changes. A typed `repository_handoff` observation exists only when repository state is needed; it binds
the request, selected source artifact and digest, target logical workspace, and verification result/digest.
Evidence-only handoff needs no checkout mutation. An explicit evidence import may read selected producer artifacts,
then persists a consumer-owned receipt/package; this is not cross-Run authority lookup. The v1 `dispatch-claim.json` remains
unchanged for legacy Runs.

A refusal is immutable and creates no attempt. Setup and worker effects after authorization belong to the ordinary
attempt result and validation; unknown activity retains occupancy under D8(A). No refusal-specific capture record or
disposition exists.

- **Publication and legacy boundary:** expanded format reuses the existing local kernel locking/publication boundary
  for short authorization/publication operations, not task execution duration. `_locking._locked()` is an existing local lock
  primitive whose `.kapisch/v3` namespace requires deliberate integration. Legacy WS-2 single-writer and post-claim
  decision re-read behavior remains unchanged. Immutable record publication reuses `_invocation._publish_immutable()` and
  `storage._atomic_write_at()`; neither promises atomic whole-directory publication. Package-file publication needs
  the focused cross-directory staging arrangement in §7, not direct use of either helper inside the package inventory. `create_run()` exclusively allocates an empty directory, after which the
  immutable envelope file is published. An incomplete allocation is inert and cannot execute; retain isolated D7(A)
  roots until shared coexistence is demonstrated.
- **Per-task claim and attempt history:** the coordinator persists each request; the kernel exclusively creates the
  next monotonic claim slot with its parent digest. There may be only one active worker for a task. WS-4 has no
  stop-and-restart or retry operation. A confirmed interruption is a terminal attempt result with adapter-owned stop
  evidence; it captures no partial outputs and preserves the task/workspace association. Unknown activity retains
  active occupancy under D8(A). Both block dependents/completion; partial workspace state is not reused in WS-4. The
  `resume.md` note preserves context only, not workspace state. A request refused before authorization may be explicitly
  resubmitted under the same admission checks because no setup writer existed. Retry of an authorized failed/interrupted
  attempt, fresh attempt IDs, and checkpoint compatibility belong to WS-5, which must prove the prior writer stopped
  and define how partial state is handled. No automatic retry.
- **Attempt lifecycle:** persist the coordinator-owned claim request, then preflight task scope, authority,
  capabilities, selected predecessor evidence, and conflict-free handoff destinations before reservation. A persisted
  request without a reservation or decision is preauthorization intent; on cold restart, rerun preflight against its
  immutable refs and current authority/gate. A preflight refusal, including on restart, has no reservation or attempt ID.
  Before requesting an execution-workspace binding, the kernel publishes one immutable
  `tasks/<task_id>/attempt-reservations/<request_id>.json` record. It assigns a Run-unique opaque `attempt_id` and
  logical output location and binds the exact request reference/digest. Its fixed request-keyed path and no-replace
  publication allow at most one reservation per request. This reservation is allocation only: it is not an attempt
  result, authorization, setup permission, or worker start. The adapter then publishes `execution_workspace_binding`
  for that reservation, binding its reserved attempt ID to the logical execution `workspace_id` and repository
  identity; the binding performs no setup, materialization, or workspace writes. Under the serialized kernel boundary,
  recheck occupancy, current authority/gate, reservation, binding, selected evidence, and workspace availability, then
  publish one immutable authorization or refusal. Authorization is the commit point and marks the task started. A
  refusal after reservation references it, creates no `attempts/<attempt_id>.json`, and never frees or reuses that ID.
  On cold restart, a reservation without a final decision becomes an immutable refusal because the adapter was not
  authorized. Resubmission uses a new request ID and repeats admission. Only after authorized commit does the adapter perform
  declared setup/materialization and verify it; only successful setup invokes the worker. Setup failure is an ordinary
  failed attempt with `worker_invoked: false`. Unknown setup/worker status retains occupancy under D8(A), with no
  relaunch or inferred completion. After the adapter reports the attempt complete, ordinary attempt evidence captures
  declared final outputs and required status evidence before workspace release. WS-4 never relaunches an
  interrupted/unknown attempt or assigns one task's workspace to another task. This contract does not observe transient
  writes or claim that a restored file was never modified.
- The existing local kernel lock/publication boundary covers only short authority/publication operations, never
  setup or worker execution. Safe pause/detach leaves uncertain records and occupancy untouched; independent work
  requires explicit Run selection/authorization and a different proven-isolated workspace. Detachment is not
  abandonment authority or stop proof. Formal repair/abandonment remains WS-5.
- Revisions and claim chains use monotonic sequence slots, parent digests, and exclusive creation. The kernel
  rejects gaps/forks and never selects the newest file. Malformed/forked history stays blocked; there is no
  coordinator reconciliation or repair in this slice. Removal/narrowing of any approved task requires a Run-local
  HumanDecision and the task remains in final accounting.
- **Amendment lifecycle:** distinguish `proposed` (coordinator amendment referencing any required HumanDecision),
  `delivered` (adapter observation), `acknowledged` (adapter observation proving transport/receipt only), and `assessed`
  (coordinator gate disposition against amended requirements). These are separate durable facts; acknowledgment is
  not semantic compliance. An amendment delivered after the worker has stopped, or without delivery evidence, is not
  consumed. If an amendment is required for acceptance, an attempt not shown to satisfy it cannot be accepted,
  release dependencies, or count toward completion. Preserve original claim/result rather than rewriting their
  historical context. Steering/delivery, acknowledgment, stop and terminal-status capabilities are declared only
  when required by the selected operation; unsupported, unknown, or unproven capability blocks that operation. A
  harness unable to deliver asks for a safe restart only when stop and terminal-status proof are supported; disclosure alone is
  not a substitute. A steered attempt retains the original claim and amendment IDs.
- A durable authorization without terminal adapter evidence is unknown, not proof of start or stop; it retains
  occupancy under D8(A), with no automatic recovery or relaunch. Raw host output is not itself a canonical attempt.
- Under selected D7(A), Phase 1 uses deterministic/test adapters and isolated state roots not visible to legacy Pi
  or coordinator recovery. Shared-state coexistence is deferred; production Pi lifecycle/recovery remains WS-11.
- Drift in any top-level WorkOrder input blocks new claims until applicability is reassessed; the task subset
  identifies affected work. Under selected D8(A), an incomplete Run stays open for reassessment; no
  abandonment/closure record can release an unknown writer. Pause/detach is an operator escape only; it does not
  prove stop or authorize release. A validated Outcome records completion.

## 5. Aggregation barrier and dependency release

The LLM aggregator produces evidence; the kernel validates structure and bindings; the coordinator alone applies
dependency and acceptance policy and chooses transitions. A kernel structural pass or raw aggregator result cannot
release a dependent task.

Handoff dataflow is sealed predecessor attempt/output → aggregation report → coordinator eligibility gate →
dependent context manifest → authorized dependent attempt. Status accounting in an aggregation report may consume
validated durable WorkOrder, claim/decision, and attempt records plus its persisted trigger; the coordinator owns any
explicit status snapshot included in that trigger. A missing or unavailable expected record is incomplete status
evidence, and absence alone is not terminal. Any completed-output fields in a report, semantic acceptance, dependency
release, and historical verification consume only immutable attempt/output/validation records and digests captured
after writer stop and before workspace release. None reads a released execution checkout to reconstruct an earlier
result.
The WorkOrder freezes each predecessor/output selector in task `handoffs[]`; the claim request identifies its
`handoff_id` and realizes the accepted predecessor attempt/output-manifest/gate bindings. The kernel verifies those
bindings against the report, gate and accepted eligibility, then validates/publishes the dependent context manifest
with exact bytes/digests and evidence used before authorization. Handoffs do not become governing inputs or change
the baseline governing-input set; task outputs remain separately captured artifacts. Evidence passing alone never changes a checkout. Only if the dependent task needs repository state,
the adapter materializes it to the explicitly bound target `workspace_id`, emits a verified handoff observation in
`tasks/<task_id>/observations/<observation_id>.json`, and the kernel validates it before context consumption. Without a valid required workspace handoff,
block; no implicit merge.

1. Every aggregation report covers every task in its named WorkOrder revision, including unclaimed, pending,
   blocked, unknown, interrupted, failed, and missing tasks. It binds all claims, attempts, context amendments,
   output digests, acceptance criteria, and refusal refs for requests refused before authorization. Task-local
   failures/conflicts name task IDs; cross-task issues have explicit affected-task sets.
2. Each aggregation invocation has a persisted sequence/trigger and exact claim set. Under selected D2(A), reports
   are immutable and linear per Run, and every report after the first names the immediately preceding report head,
   including ordinary later-result reports. No timestamp or “newest file” authority. A revision change must be
   explicit in the report and accompanied by required carry-forward assessments; no claimed or unknown task may
   disappear from the chain/final accounting.
3. The coordinator writes one `coordinator-gates/<sequence>.json` assessment per report. It records per-task acceptance/dependency
   eligibility, exact report and kernel structural-validation refs, affected issues, amendment assessed
   dispositions, and reasoning. For admission of dependent task D, the relevant predicate is: each required
   predecessor is currently eligible; each selected result/output binding still matches the frozen handoff selector
   and accepted gate; no unresolved issue explicitly affects D or a required predecessor; and no Run-wide blocking
   issue applies. The coordinator records explicit affected task IDs for issues and withdrawals, including
   already-authorized descendants under D3(A); ambiguous effects cannot be represented as affecting nobody. Report
   numbering or explanatory wording changes alone do not invalidate an unchanged predicate. The final gate also
   carries a `completion_assessment` covering all historical tasks/claims and remaining required work. This is the sole persisted
   result that releases new dependent claims or supports a complete Outcome. The kernel checks only shape, identity,
   coverage, and digests.
4. New claims bind the actual report and coordinator gate evidence used for each relevant dependency, not an
   unconditional global-head token. Missing/failure on an independent branch is reported but does not itself block
   an accepted predecessor gate. Revalidate relevant predecessor eligibility and accepted output bindings at
   admission; unrelated report-head movement alone does not refuse dispatch. Persist the exact report/gate evidence
   used.
5. If a later report withdraws earlier acceptance, the claim that was already dispatched retains its historical
   binding. The coordinator must record the current assessment of its in-flight result and final completion; no
   automatic retroactive mutation of claims. Under selected D3(A), the coordinator explicitly assesses affected
   in-flight dependents and final completion; unresolved required defects block a complete Outcome.
6. Final reporting covers every task ID ever published in the Run and every claim across all revisions, including
   refused-before-start, unknown, and interrupted claims. A refusal has no attempt or setup evidence; unknown
   authorized activity retains occupancy. Any removed/narrowed requirement remains present with its Run-local
   HumanDecision disposition. A complete Outcome requires a coordinator completion assessment proving all remaining
   required tasks accepted and no unresolved required issue. Final kernel validation binds exact final
   report/gate/evidence references and digests, plus the canonical admitted decision IDs and digests, is published
   before Outcome, and does not depend on a future Outcome digest. The coordinator authors the Outcome semantically;
   the kernel validates and immutably publishes it only after rechecking those bindings and completion conditions
   through the existing local publication boundary. Outcome binds the final report digest, completion-gate digest,
   and `validation/final/<gate_sequence>.json` digest; stale final validation blocks publication. It is not human approval.

An incomplete report is valid evidence, not acceptance. Under selected D2(A), the Run-wide sequence may cross
WorkOrder revisions only through explicit revision references and carry-forward assessments; it preserves full
Run-wide task/claim accounting.

An aggregation request may follow a durable claim decision, terminal attempt result, output-capture/validation result,
or an explicit status snapshot. The coordinator persists the exact claim set and either a trigger reference/digest to a
durable record or an explicit status snapshot containing expected source references and observed statuses; the
aggregator consumes the request and publishes the report. Snapshots are accounting evidence only: they cannot stand in
for a durable terminal claim/attempt result or sealed output. A missing expected record is `missing`/`unavailable`
incomplete status evidence; absence alone is not terminal evidence.

Each report separates claim/attempt status from output sealing. A preauthorization refusal is a terminal claim decision
but has no attempt. An authorized attempt without terminal adapter evidence is `unknown` and retains occupancy. A
terminal attempt result may be reported while required output capture or validation is pending, blocked, or unavailable.
For a mutating task, output is sealed only by the kernel-published canonical manifest and attempt-validation record;
terminal status or an empty output list alone is not acceptance. Unknown activity or unsealed required output prevents acceptance of that task and release of dependents that
require it; a complete Outcome is also blocked while any task in its declared completion scope remains unknown or has
unsealed required output. The coordinator gate may release a
dependent only after validating required predecessor acceptance and sealed output references.

## 6. Workspace use and operator pause

The core binds a portable logical `workspace_id`; it never persists machine paths. Same-Run active or unknown holders
are derived from persisted admission and attempt results. Unknown setup or worker status retains occupancy under
D8(A). A proven stop is not authorization to restart or reuse partial state in WS-4. A confirmed interrupted attempt retains its task/workspace association and partial state; an unknown worker retains
active occupancy until stop is proven. WS-5 defines recovery. Do not add a workspace-reservation chain or bespoke cross-Run
ownership protocol.

The host/harness remains responsible for physical workspace ownership, isolation, and reporting when an attempt is
complete or its status is unknown. Final-output validation does not attempt to observe transient writes or prove that a
file was never changed and restored. Capture the declared output package only after the task reports completion; if
execution status is unknown, retain occupancy and do not publish or hand off its output. Do not add a filesystem
watcher, sandbox, syscall layer, or custom POSIX/ACL policy for this contract. Existing equal-root compatibility remains
only where required workspace separation is proven.

An operator may pause and detach from uncertain work without changing authority. Detachment neither proves writers
stopped nor releases occupancy, and damaged records remain untouched. Independent work requires explicit Run
selection/authorization and a different proven-isolated workspace. No abandonment state or authority is introduced;
formal repair/abandonment remains WS-5.

## 7. Evidence-only inputs between WorkOrders

`governing_inputs` remain tracked-Git freshness inputs. Each WorkOrder revision may select `evidence_inputs[]` with stable,
case-fold-unique, path-safe `input_id`, role, source/producer identity, and one of these modes:

- **Reference-only:** optional evidence only. The human selects a durable project artifact and its canonical location,
  optionally with skill advice; the WorkOrder records provider/repository identity, stable artifact ID, exact immutable
  version/object ID where available, selected path/selector, digest, and approval/publication provenance. A mutable URL
  or branch/tag name alone is not an immutable identity. Kapisch does not decide long-term retention, pin Git refs, or
  archive canonical project artifacts. Availability and verification limits remain explicit; a required artifact that
  cannot be retrieved or verified fails closed. This mode cannot satisfy a required Run-local continuation package
  or byte-copy requirement.
- **Canonical Git artifact reference:** `git_artifact` is allowed only for a human-selected durable,
  approved/published project artifact—not a temporary task commit, branch, worktree output, patch, or other
  intermediate. Bind exact repository identity, immutable object ID, selected path/selector, verified digest, and
  approval/publication provenance. Do not pin refs or otherwise retain Git objects merely because a task produced
  them. Bind only the final canonical identity after publication; for a squash merge, select the final object ID and never retain or infer identity from the discarded branch commit. If a required reference is later missing or
  unverifiable, fail closed. A Git reference is not a byte copy, Run-local continuation evidence, or a
  post-rejection fallback. Human-selected source retention remains outside Kapisch's control.
- **Retained snapshot:** capture exact selected bytes into a content-addressed package in the consuming Run. A
  single-file digest is SHA-256 of bytes; a multi-file package uses a canonical sorted manifest of safe relative
  paths and per-file SHA-256 digests, then hashes that manifest. Apply containment and symlink checks to actual
  paths at capture time, not to an opaque `source_ref`. The kernel-owned capture operation writes the package; source
  adapters supply bytes but cannot write canonical records. Capture only explicitly selected, safe relative POSIX
  paths. Normalize separators and reject absolute paths, `..`, path escapes, and symlinks using actual source and
  destination paths. The core does not implement a cross-harness secret scanner, content-pattern list, or secret
  classification. The active harness applies its own configured security policy to every payload the Run will persist
  or pass to a worker, including task outputs, selected evidence, continuation copies, and resume-note content. The
  adapter identifies the effective harness rules (for example, Pi's applicable `AGENTS.md` instructions or Claude
  Code's applicable `agents/claude.md`/repository instructions) without importing their syntax into the core. It binds
  the assessment to the exact harness/profile identity, effective policy reference/digest, disposition
  (`allow`, `block`, or `human_review`), and sorted selected path/byte-digest set. Missing, stale, ambiguous, or
  mismatched assessments block publication.

  The kernel stores harness disposition and assessment binding but does not reinterpret its findings or claim stronger
  enforcement than the active harness provides. An assessment governs only the exact bytes and does not authorize
  task scope, execution, or completion; those remain governed by WorkOrder/claim/validation authority. A `block` or
  missing assessment produces no package; for a task output it writes a failed validation and blocks dependents under
  D8(A). An `allow` may proceed. A `human_review` assessment may create one immutable output-capture request only if
  that harness policy explicitly permits human review; otherwise it remains blocked. The core cannot override a
  harness `block`. The attempt-keyed request contains deterministic `capture_id` (`cap-` plus SHA-256 of canonical
  request fields excluding the ID), attempt-result reference/digest, exact harness/profile and policy identity, the
  assessment, and the complete sorted output selector/path/kind set and file-byte digests; deletion entries have no byte digest. A matching HumanDecision authorizes only
  that request. On restart, no approval means re-prompt; an approval revalidates file-entry digests and tombstone
baseline/final state before idempotent continuation. For external evidence, continuation copies, and resume notes, a `human_review` disposition remains blocked until the
  harness completes its own review and returns `allow`; the core creates no separate exception request for these
  copies. The request does not contain output bytes.
  Capture only explicitly selected outputs/paths or patches needed for a dependency or selected evidence, never the
  whole repository. Verify the original manifest digest on every use. A previously approved immutable package may be
  consumed by reference or materialized byte-for-byte into a dependent's fresh workspace; this is not another
  Run-local capture. The dependent harness decides whether it may use that package before materialization, and the adapter records that
  assessment in the handoff observation. Unchanged handoff bytes are not recaptured against the post-setup worker
  baseline; changed/new bytes receive a new assessment from the dependent attempt's harness. Git references never bypass required copies. Check containment and every source/destination path
  component and final target for symlinks before publication. Trusted verification may hash bytes for identity without
  exposing them to a model. Exact payloads are never silently redacted. Object identity or a prior harness decision is
  not blanket authority for new or changed bytes. Optional canonical-artifact evidence may instead be explicitly
  selected reference-only.
- **Verified prior Outcome:** an explicit importer reads only the selected producer artifacts and invokes the
  format-specific historical verifier. It imports evidence, never authority. A v1 Outcome that cannot pass its
  supported verifier may be retained only as unverified evidence.

After the applicable authorization check in §1, publication order is capture first, selection second. The coordinator
writes an acquisition request; the active harness assesses the exact selected bytes under its own configured security
policy and supplies a durable assessment bound to harness/profile identity, effective policy reference/digest,
disposition, and sorted path/byte digests. Missing, stale, or mismatched assessment blocks capture. The kernel
publishes the content-addressed package and a receipt binding request, assessment, consumer Run, source identity/version,
capture mode, and selected digests; only then may a WorkOrder revision select the exact manifest/receipt digest.
Capture does not itself authorize or select work, so an orphan/unselected package is inert. The manifest may bind its
consumer Run and acquisition request, but not the digest of a future WorkOrder revision; this avoids a digest cycle.
Different bytes under the same logical `input_id` produce a different manifest-addressed path. Capture only context
needed for the task; indexes may locate relevant passages without copying or loading the whole corpus.

After the terminal attempt result is published, the kernel validates the harness assessment against the complete
declared output-entry inventory: selector/path/kind and file-byte digests, with no byte digest for a deletion tombstone. A `block`, missing/ambiguous assessment, or structural/containment failure
captures no output and writes one failed `tasks/<task_id>/validation/<attempt_id>.json`; the task blocks dependents
and the Run remains open under D8(A). An `allow` proceeds directly. A `human_review` result can proceed only when
that harness policy permits human review; the kernel then
writes one immutable `tasks/<task_id>/output-capture-requests/<attempt_id>.json` for the attempt. The request
contains a deterministic `capture_id` (`cap-` plus SHA-256 of canonical fields excluding the ID), attempt-result
reference/digest, exact harness/profile and policy identity, assessment, and the complete sorted output selector/path/kind
inventory with file-byte digests; deletion tombstones have no byte digest, as defined in §8. The attempt-keyed path and no-replace publication enforce at most one request per attempt; a conflicting
existing request fails closed. No output bytes are stored in the request. The coordinator asks the human to approve
that exact request or leave it pending. `capture_exception` binds the exact request reference/digest and attempt ID and
is accepted only when the harness disposition permits human review. On restart, no matching approval means re-prompt; a matching approval means the kernel rechecks workspace identity,
re-hashes each file entry, and confirms each deletion tombstone's path existed in the persisted post-setup baseline and
remains absent from the final workspace. Changed or missing file bytes, or a changed tombstone state, fail closed. A post-completion revision requires a separate authorized WS-5 attempt, not an in-place
edit. The task and Run remain open under D8(A), the workspace remains occupied, and no dependent is released until
capture, manifest, and validation succeed; WS-4 defines no decline or incomplete-Outcome closure.

The kernel writes the content-addressed package with per-file no-replace publication. Its scratch directory is
`outputs/<attempt_id>/.publication-staging/`, a sibling of `<manifest_digest>/` on the same filesystem, outside the
canonical package inventory. The kernel exclusively creates a fresh staging file for each write; it never resumes,
overwrites, or trusts a leftover staging file. Under the existing containment/symlink checks and verified directory
descriptors, it writes the authorized bytes, verifies their expected digest, fsyncs and closes the file, then links it
without replacement into the expected package path and fsyncs that destination directory. No temporary file is
created inside the package inventory. Direct use of `_atomic_write_at()` there is unsuitable because it creates
its temporary file beside the destination. This is a focused publication operation, not a new transaction protocol.

Staging entries are kernel-owned non-authoritative scratch, never manifest entries, handoff selectors, recovery
inputs, or evidence. They grant no permission to capture different bytes. WS-4 retains them after success, failure,
or interruption without automatic cleanup; an operator may remove them only after Outcome is sealed. On recovery,
the kernel ignores staging residue, verifies existing canonical package files and fills only missing expected files
from the already authorized source after the required identity/digest rechecks. If required source bytes are missing
or changed, recovery fails closed; it does not promote staging residue. An existing destination is verified and reused,
never replaced. Recovery fsyncs verified canonical files and their containing directory hierarchy before manifest
publication. Mismatched or extra files inside the canonical package inventory still fail closed. After every package byte verifies,
the kernel publishes the sole immutable `outputs/<attempt_id>/manifest.json`, whose digest locates
`outputs/<attempt_id>/<manifest_digest>/` and whose body binds the attempt, harness assessment, and any request/decision.
The kernel then publishes the sole `tasks/<task_id>/validation/<attempt_id>.json`. A crash after package completion but
before the manifest resumes by verification and manifest publication; an existing manifest is verified and reused.
Conflicting manifest or validation records fail closed. No exception registry or separate check record is needed.

Under selected D5(A), every verified import writes a consumer-owned `evidence-imports/<import_id>.json` receipt containing producer
Run/Outcome reference and digest, verifier version/mode, exact artifact digests inspected, and result. The kernel
produces it after verification; it is never caller-supplied. V1 verification checks current source inputs in
`_task_authority.py:143` and current capability context; if recorded inputs have drifted, verification fails under that
current-input check. Missing required capability context also fails. Such evidence may be retained only as
explicitly unverified; no legacy verifier changes. The consumer retains the receipt and selected evidence needed to
explain accepted work.

The WorkOrder revision records evidence selection and provenance, not approval of its own future digest. Each
attempt binds selected context before authorization; a restarted attempt gets separately selected context and never
relies on hidden prior host/model state. A researcher may propose but never select sources. Prefer targeted passages
or artifacts that address the current question, with enough source/version identity to explain their use. Search
indexes are retrieval aids, not authority, and need not be loaded wholesale into model context. Retain Run history
and the selected evidence/provenance needed to explain accepted work under WS-2 §2.6; unreferenced scratch copies
and rebuildable indexes may be removed by an operator only after Outcome is sealed. Missing content that a durable record depends on
fails historical validation closed. Human context > External Artifacts > Local Artifacts is coordinator guidance
only. “Current” requires explicit supersession/applicability evidence. Earlier Outcomes may inform a new WorkOrder
but cannot authorize it.

## 8. Capture, validation, and historical evidence

Option C separates present eligibility from verification of completed historical facts. This expanded-format
proposal leaves legacy v1 behavior unchanged. A live workspace is consulted only while the operation still owns it
and before release. WS-4 never reuses a workspace across tasks or starts a replacement attempt after interruption.
After release, aggregation, acceptance, and historical verification consume sealed attempt/output/validation
evidence, never the released checkout.

- **Dispatch:** validate the entire Run input union against the applicability assessment and freshness policy; drift
  blocks new claims until reassessment. Validate each task's declared subset and selected authority, capabilities,
  and dependency evidence. A declared final output may overlap a governing-input path only when the WorkOrder
  explicitly authorizes that output. An unrelated sibling commit is not a blanket equality gate.
- **Attempt capture:** authorization binds existing plan, authority, handoff selectors, selected predecessor
  evidence, and approved context only. The adapter performs declared setup after authorization and records typed
  native evidence for setup result, worker invocation, and stop. Successful setup invokes the worker; setup failure
  is an ordinary failed attempt with `worker_invoked: false`. Unknown setup/worker status retains occupancy; no replay or
  inferred completion. On completion, ordinary attempt evidence carries the active harness security assessment and
  the kernel captures declared final outputs before workspace release. A preauthorization refusal has no attempt,
  no setup writes, and no worker; there is no separate pre-start capture lifecycle.
- **Final-state output validation:** every mutating task declares `write_targets[]`; the kernel captures and validates
  final changes against the post-setup worker baseline before workspace release. A declared output may overlap a
  governing input when explicitly in scope. Transient write/restore activity is not observed or represented; only
  captured outputs can be delivered, and unchanged handoff entries remain referenced from their producer manifest (§6).
- **Output-entry and file-metadata semantics:** the canonical output manifest contains one deterministically sorted
  entry per selected changed path. A `file` entry records a normalized safe relative path and SHA-256 of exact bytes; a
  `deletion` entry is an explicit tombstone allowed only when that path existed in the post-setup worker baseline and
  is absent at final capture. A path absent in both states, or outside selection, has no entry; omission never means
  deletion. The manifest digest covers both entry kinds, while the content-addressed package contains bytes only for
  `file` entries. A successful capture with no changes publishes a canonical empty manifest.

  Only regular-file bytes and paths are supported. Mode/executable bits, timestamps, ownership, ACLs, extended
  attributes, hard-link identity, and empty-directory state are not captured, compared, copied, or verified;
  metadata-only changes produce no output. Symlinks and special files in selected output paths fail capture closed. A
  task that requires unsupported metadata preservation is outside this proposal and cannot be treated as an accepted
  output.

  The harness assessment binds the complete sorted selector/path/kind set and file-byte digests; deletion entries have
  no byte digest. A selected `repository_state` tombstone deletes only its exact mapped path within declared
  `write_targets[]`; `evidence_only` handoffs never mutate a workspace. Materialization copies file bytes only, not source
  metadata. Historical verification validates the canonical manifest and file-entry bytes/digests and accepts deletions
  only from explicit tombstones; it never infers deletion from a missing blob or rereads a released workspace.
- **Historical Outcome verification:** verify persisted Run, revision assessments, claims, typed adapter/native
  observations, authorized-attempt validations, output manifests, coordinator gates, aggregation lineage, and
  evidence/import receipts. Do not reread the current execution checkout. Missing/tampered records produce a
  deterministic historical-evidence error, not a current-staleness error. `.kapisch/` is trusted local state; digests
  do not protect against an actor able to rewrite the whole state root.
- **Later consumption:** validate a claimed “verified Outcome” through the supported producer-format verifier, then
  treat it only as evidence in the consuming Run's independent applicability assessment and persist the consumer
  receipt (§7).

Capture-before-release remains normative: seal the selected final-output package before workspace release. WS-4 does
not assign a task workspace to another task and does not implement same-task restart. Final-state output validation
replaces D1(A)'s transient-write rule; there is no claim that writes later restored are detected.
Cross-Run physical safety remains an existing host responsibility, not ambient historical-context scanning or a new
core registry.

## 9. Cold restart and producer ownership

At cold restart, the kernel reconstructs format, revision heads, selected Run-local authority, task assessments,
claim requests, attempt reservations, claim decisions, attempt results, typed observations, ordinary attempt validations,
output-capture requests, coordinator gates, report lineage, evidence receipts, and Outcome solely from persisted records.
A reservation without a final decision becomes an immutable refusal; its attempt ID is never reassigned. The harness supplies the explicit Run
reference and screens a persisted `resume.md` under its own current security policy before exposing it to the coordinator;
the coordinator checks note references and treats it as advisory context only. The note cannot supply authority. The persisted harness Run reference is a continuation pointer, not execution
authority. Missing or malformed authority fails closed.

Every durable authority/evidence record has one semantic producer and publication point. Coordinator-authored
semantic content is structurally validated and immutably published at the kernel boundary. The sole mutable
`resume.md` is optional, non-authoritative context. The coordinator authors semantic content, the active harness
supplies an assessment bound to its exact digest, and the kernel atomically replaces it only with that assessment. It
is replaceable, not reconstructible; canonical records/workspace state can support a new summary but may not recover
lost reasoning. This
proposal does not prescribe a new lock protocol: expanded authorization and publication reuse the existing local
kernel lock/publication boundary for short operations, never across setup or
worker execution. Existing helpers include `_locking._locked()` (whose `.kapisch/v3` namespace
needs deliberate integration), `_invocation._publish_immutable()` and `storage._atomic_write_at()` (immutable file publication, not atomic directory
publication), `store_bundle()` (supported verified bundle format only), `capture_worktree()` (identity-bound repository facts;
ignored files excluded), and `_reservation_census()` (validation example, not worker occupancy).

Run allocation uses exclusive empty-directory allocation followed by immutable no-replace envelope-file publication.
Incomplete allocation is inert and cannot execute; do not promise invisible directory publication. D7(A) isolated
Phase-1 roots remain mandatory until shared coexistence is demonstrated. Legacy WS-2 single-writer/post-claim
re-read semantics remain unchanged.

| Artifact/fact | Producer and validation boundary |
| --- | --- |
| `run.json` identity and expanded-format envelope | Coordinator supplies intent; kernel validates and publishes the immutable file after exclusive directory allocation. Preserve current Run identity and `<state_root>/.kapisch/runs` location; no external-store marker or repository-ID layer is introduced in this slice. |
| Explicit continuation reference | Harness persists Run ID in existing durable session/handoff metadata; kernel validates the referenced Run. |
| Decisions, applicability, WorkOrders, revision assessments, gates | Their existing semantic owners; kernel validates ownership, references, sequence, and digests before immutable publication. |
| Claim request and claim slot | Coordinator owns request intent; the adapter supplies a harness security assessment for selected repository-state handoff bytes, bound to their exact manifest entries and effective policy identity. The request persists that assessment; the kernel checks the binding before authorization and exclusively allocates the next slot. |
| `tasks/<task_id>/attempt-reservations/<request_id>.json` | Kernel-owned immutable allocation record, zero or one per claim request (created only after preflight succeeds). Its fixed request-keyed path and no-replace publication allow at most one reservation per request. It binds the request reference/digest to one Run-unique `attempt_id` and logical output location before the adapter produces an execution-workspace binding. It is not authorization, an attempt result, or permission to start. The adapter binding and final kernel decision consume its reference/digest; restart turns an unresolved reservation into refusal. The kernel never reuses a reserved ID. |
| `tasks/<task_id>/claim-decisions/<request_id>.json` | Kernel-owned immutable final authorization/refusal decision; request ID is coordinator-produced in the earlier claim request. Authorization binds the reservation reference/digest and exact execution `workspace_id` plus adapter-binding reference/digest. A refusal after reservation binds that reservation; a pre-reservation refusal has no attempt ID. Occupancy reconstruction/check, current authority/gate recheck, and final-decision publication are one serialized short-lock transition. Durable authorization publication is the commit point: after it, crash/unknown activity retains occupancy. No lock spans execution. First consumer is cold-restart occupancy reconstruction and claim admission. |
| `tasks/<task_id>/context-manifests/<context_id>.json` | Coordinator semantically selects context; kernel validates and publishes canonical manifest. Context ID is coordinator-produced in the earlier claim request; inputs include selected evidence/gate bindings; first consumer is authorization decision. |
| `tasks/<task_id>/resume.md` | Coordinator owns the compact, optional, non-authoritative note and checks references. It contains status, references, and bounded summaries, not raw payload excerpts or transcripts. The active harness assesses note bytes before exposure or replacement; the kernel atomically publishes a replacement only with an assessment bound to the exact note digest. A blocked/ambiguous note is not exposed or published; the last permitted note, if any, remains nonauthoritative. On restart, canonical records and current workspace evidence win; the note is replaceable, not reconstructible, and may require a human prompt. It never authorizes work. Cleanup is operator-controlled and only after Outcome is sealed. |
| `validation/final/<gate_sequence>.json` | Kernel-owned final structural validation; gate sequence is coordinator-produced in the earlier final gate; inputs include final report/gate and referenced evidence; first consumer is Outcome publication. |
| `evidence-capture-requests/<capture_id>.json` | Coordinator-produced intent for importing selected external evidence; capture ID binds consumer Run/source selection/version/mode. The harness assessment is bound to exact source bytes and policy identity; the kernel consumes the request and assessment to perform capture. The core does not reinterpret content-security findings. |
| Authorized attempt result and `tasks/<task_id>/validation/<attempt_id>.json` | Adapter reports completion and supplies the active harness assessment bound to the exact declared output-entry selector/path/kind inventory and file-entry byte digests; deletion tombstones have no byte digest. It also binds harness/profile and effective policy identity. The kernel publishes the immutable terminal attempt result first. `allow` captures the declared set; `block`/missing assessment produces no package and one failed validation; `human_review` creates one request only when permitted by that harness policy. After an exact matching HumanDecision, the kernel revalidates file-entry digests and tombstone baseline/final state, publishes the content-addressed package and sole fixed-path manifest, then the sole validation. A confirmed interruption uses adapter-owned `worker_interruption` evidence, produces no output package, and preserves the task/workspace association; unknown activity has no terminal result and retains active occupancy under D8(A). Temporary Git object IDs are not durable artifact identities or retention locators. Setup failure is an ordinary failed attempt with `worker_invoked: false`. |
| `tasks/<task_id>/output-capture-requests/<attempt_id>.json` | Kernel-produced immutable pending-output record for a harness-authorized human review; at most one per attempt, enforced by fixed path and no-replace publication. Its body contains deterministic `capture_id`, attempt-result reference/digest, harness/profile and policy identity, assessment, and complete sorted output selector/path/kind set and file-byte digests; deletion entries have no byte digest. The coordinator's first consumer is the review prompt; recovery consumes the record and any matching HumanDecision. It contains no output bytes and cannot override a harness `block`. |
| `outputs/<attempt_id>/<manifest_digest>/` and `outputs/<attempt_id>/manifest.json` | Kernel-owned output package and sole manifest; §8 defines file entries and explicit deletion tombstones, while the package directory stores bytes only for file entries. Package files are published without replacement from verified, fsynced staging files outside the package inventory (§7). Kernel-owned `.publication-staging/` is non-authoritative scratch, never a recovery input; residue is retained without automatic cleanup. Recovery verifies canonical files and fills missing expected files from authorized, rechecked sources, rejecting mismatched/extra package bytes. The fixed manifest path is published only after package verification; SHA-256 of canonical manifest bytes determines `manifest_digest`, which the manifest body omits to avoid a digest cycle. |
| `tasks/<task_id>/observations/<observation_id>.json` | Adapter-owned typed evidence. `kind=repository_handoff` binds request, source artifact ref/digest, target logical workspace, harness security assessment reference/digest, and verification result/digest. `kind=worker_interruption` binds attempt/workspace IDs and adapter evidence that the worker stopped; the kernel uses it to publish a terminal interrupted attempt result without output capture. `kind=amendment_transport` binds amendment and attempt IDs plus delivery/acknowledgment facts. Fields not applicable to the declared kind are absent. These records are evidence, not authority. |
| `workspace-observations/<observation_id>.json` | Adapter-owned typed identity evidence. `kind=baseline_workspace_binding` binds WorkOrder revision, `baseline_workspace_id`, repository identity, and adapter-owned durable workspace reference. `kind=execution_workspace_binding` binds the exact kernel reservation reference/digest, its reserved attempt ID, logical execution `workspace_id`, and repository identity; it is produced after reservation and before authorization and proves binding only, not execution or permission to write. Host paths/handles remain adapter metadata. Setup/worker baseline observations belong to ordinary attempt evidence, not authorization. |
| Context amendment and delivery/acknowledgment facts | Coordinator owns amendment; adapter owns `amendment_transport` observations with the fields defined above; coordinator gate owns semantic assessment. |
| Human-selected canonical artifact reference | The human selects the durable artifact and destination, optionally with skill advice; the coordinator records the exact final source/version, selector, digest, and approval/publication provenance in the WorkOrder or selected evidence. The harness resolves availability; the kernel validates the reference. No automatic pinning or archiving. |
| Evidence packages and import receipts | Kernel capture/import boundary owns Run-local receipts; `store_bundle()` is reused only for its supported verified format. |
| Aggregation request/report and Outcome | Coordinator owns the persisted request, trigger/status snapshot, and gate assessment; aggregator owns report payloads; the kernel validates and immutably publishes canonical records. |
| Same-Run occupancy and physical ownership | Derived from named Run admission/attempt evidence; physical cross-Run safety remains host responsibility. |

No actor writes another actor's canonical record. Hashes detect mismatches but do not protect against an actor able
to rewrite the entire trusted local state root.

Expanded HumanDecisions are produced by the human-input boundary while the Run is valid/open; an amendment is a
distinct coordinator record, not a HumanDecision. Decision admission and Outcome publication use the existing
serialized publication boundary. Malformed history fails closed. Under D8(A), incomplete Runs remain open; only
validated completion closes admission. The v1 `dispatch-claim.json` behavior is unchanged.

## 10. Focused acceptance tests required before implementation

- Legacy fixtures preserve all accepted shapes and semantics. Expanded routing is Run-format-first; existing
  destinations remain untouched; incomplete allocations cannot execute. D7(A) isolation remains mandatory. Existing
  empty Run allocation remains supported.
- DAG/revision validation rejects unsafe/duplicate IDs, malformed dependencies/cycles, sequence forks/gaps, and
  semantic changes to claimed tasks. In-scope additions proceed without duplicate approval; removal/narrowing
  requires Run-local HumanDecision and remains in final accounting.
- Admission rechecks the relevant gate predicate: current required-predecessor eligibility, selected result/output
  bindings, and unresolved issues explicitly affecting the dependent or required predecessors; run-wide blocking
  issues apply. Unrelated report-head advance alone permits admission. Acceptance withdrawal, changed selected
  artifacts, or newly applicable issues block it. Coordinator explicitly assesses issue/withdrawal effects on
  already-authorized descendants under D3(A); ambiguous affected sets cannot mean “affects nobody.”
- Handoff destination preflight rejects duplicate normalized file/deletion targets and file-versus-descendant conflicts
  before reservation or authorization, even for equal bytes; common directory prefixes and distinct declared targets
  remain explicit selections, never an implicit merge.
- Mutating tasks declare final `write_targets[]`; capture records changes from the post-setup worker baseline,
  including additions, replacements, and deletions. Validate original governing inputs before applying handoffs.
  Unselected workspace residue is not packaged or passed to dependents. A repository-state handoff destination is
  within the dependent task's `write_targets[]`; evidence-only handoffs have no destination. Test predecessor output
  approved by the harness and handed off: unchanged bytes are consumed by reference without recapture, while changed
  bytes receive a new dependent-harness assessment. Tests also distinguish a changed file from a deletion tombstone,
  preserve omission as no change, reject unsupported file types, verify that metadata-only changes are outside the
  contract, validate tombstone handoff and cold-restart verification, and revalidate file digests plus tombstone
  baseline/final state during human-review recovery.
- Before authorization, refusal has no attempt, setup writes, or worker. A request without reservation/decision
  re-runs exact preflight after restart; an unresolved reservation recovers as refusal. A refusal after reservation keeps
  its reserved ID but creates no attempt result; no reserved ID is reused. After
  authorization, setup failure is an ordinary failed attempt with `worker_invoked: false`; unknown setup/worker status
  retains occupancy under D8(A), without relaunch or inferred stop. Authorization binds existing plan/authority/handoff and selected predecessor
  evidence, never future setup snapshots. Required final outputs are captured after the adapter reports task completion
  and before workspace release; unknown status blocks capture and retains active occupancy. A confirmed interruption
has no partial-output capture and retains its task/workspace association; WS-4 starts no replacement attempt.
- A temporary task commit never qualifies as `git_artifact`, even when its role was declared or its object ID and
  digest are known. If selected output is required for dependency continuation or restart, bind only the selected
  Run-local snapshot and its receipt/digest. For canonical Git evidence, test that a human-selected, approved/published
  artifact is recorded by its final object ID/version, selector, digest, and publication provenance. Include a squash-
  merge case proving the discarded feature-branch object is neither retained nor treated as the canonical identity.
  Test harness security dispositions for `allow`, `block`, and policy-permitted `human_review`, each bound to exact
  harness/profile, effective-policy identity, attempt, and output digests. Verify that the kernel never reinterprets or
  overrides a harness denial, and that only an exact pending request can receive a HumanDecision when the harness
  permits review. Test crash recovery while writing a package: verify existing files, fill missing files, reject
  mismatched/extra package files, publish one fixed manifest, then one validation. Inject write failure and interruption
  after staging creation, during writing, after final-name linking, and before the publication operation returns.
  Staging residue remains outside the canonical inventory and is never promoted or cleaned up automatically;
  recovery reproduces the same package, fixed manifest, and validation. Required byte copies remain mandatory.
- Existing helper reuse is bounded: local lock/publication applies only to short transitions, not task lifetime;
  file publication does not publish a directory atomically. Host workspace-isolation and terminal-status limits are described in §6.
- Pause/detach leaves uncertain records and occupancy untouched; detachment proves neither stop nor release and
  imports no authority. Independent work requires explicit Run selection and a different proven-isolated workspace.
- Reports cover all tasks/claims across revisions; no abandoned state or duplicate pre-start outcomes. Retained
  observation records explicitly type the observation and define only applicable fields. Tests verify producer
  ownership, cold restart, immutable evidence, capture-before-release, unknown/interrupted-status retention without
  relaunch, D2 linear reports, and D8(A) open incomplete Runs. Aggregation tests cover terminal and explicit persisted status-snapshot
  triggers, missing/unavailable results, and terminal attempts whose required outputs are not sealed; a snapshot
  cannot substitute for terminal attempt evidence or sealed output, and none may release unknown occupancy, blocked
  dependents, or complete Outcomes. An independent-branch case with accepted, sealed-output task A, unknown/unsealed task
  B, and task C depending only on A verifies C remains eligible, B's dependents remain blocked, and the Run stays
  incomplete. Resume-note tests cover harness assessment/omission,
  material findings, task/handoff boundaries, restart after compaction/crash, stale references, and human steering.
  Verify that a stopped attempt cannot start a new attempt or release its workspace in WS-4; recovery is WS-5.
  Preserve the accepted power-loss/storage-rollback limitation.

## 11. Owner decisions recorded; overall design approval pending

The owner selected options A for D2–D8, replaced D1(A)'s transient-write rule with final-state output validation,
approved the compact task-resume note, delegated content-security decisions to the active harness, and deferred
stop-and-restart to WS-5. These are design decisions, not runtime authorization. Same-Run in-scope task additions follow the product-spec reassessment rule without duplicate
approval; materially changed/ambiguous scope and any post-start external-context addition require a Run-local
HumanDecision. D9 reflects the owner's context-efficiency and cleanup requirements. Remaining expanded-format
semantics still require design approval before implementation.

1. **D1 — Final-state outputs (owner-approved).** Each mutating task declares `write_targets[]` as its intended final
   outputs. At task completion, capture and validate changes against the post-setup worker baseline before workspace
   release. An explicitly authorized output may replace a governing-input path; validate the original baseline input
   before an authorized handoff overlay, then keep the input identity separate from produced bytes. Transient writes,
   including writes later restored, are not observed or recorded. Only selected manifest outputs or referenced upstream
   outputs are delivered to dependent tasks; unchanged handoff bytes are not recaptured by the dependent.
2. **D2 — Aggregation lineage across revisions (selected A).** (A) Keep one linear Run-wide report chain; every
   report names its WorkOrder revision and parent report, and revision transitions include explicit carry-forward
   entries — **selected**. (B) Start a separate report chain for each WorkOrder revision and link chains with an
   explicit coordinator assessment. Neither option permits forks, timestamp selection, or cherry-picking.
3. **D3 — Later report withdraws predecessor acceptance (selected A).** (A) Preserve existing claim bindings; new
   claims use the current gate, and the coordinator explicitly assesses in-flight effects and final completion —
   **selected**, consistent with prospective dispatch. An unresolved required-work defect blocks a complete Outcome.
   (B) Require affected in-flight dependents to be requalified before their results can be accepted. Neither option
   rewrites earlier claims or completed Outcomes.
4. **D4 — Carry-forward after authority/applicability changes (selected A).** (A) At the target revision, require a
   coordinator assessment binding the original claim/result, structural equality, changed inputs/authority, and
   semantic compatibility — **selected**. (B) Count an old result automatically only when task structure and
   relevant bindings are unchanged; across changed authority/inputs keep it as evidence but require new work. A new
   HumanDecision never retroactively invalidates its original dispatch; its reuse effect is separately assessed.
5. **D5 — Promise of “verified prior Outcome” (selected A).** (A) Persist a consumer-owned verification-at-import
   receipt with Outcome/artifact digests, verifier version/mode, and result — **selected for the first slice**; v1
   verification fails after governing-input drift under `_task_authority.py:143` and requires current capability context, so
   failure may be retained only as explicitly unverified evidence. (B) Retain a self-contained package sufficient to
   rerun a supported historical verifier, with greater storage/sensitivity cost. Reference-only/unverified evidence
   remains separate either way.
6. **D6 — Legacy format compatibility (selected A).** (A) Preserve every previously accepted legacy shape by routing
   through a structurally legacy-rejected expanded envelope/WorkOrder shape — **selected**. (B) Reserve the exact
   new format key globally even in otherwise valid legacy records, explicitly accepting that compatibility
   exception. Repository fixtures cannot audit private retained state; an unknown extra key alone is not a safe
   discriminator.
7. **D7 — Expanded state visible to legacy discovery during Phase 1 (selected A).** (A) Keep expanded Runs in
   isolated deterministic/test roots not discoverable by legacy Pi or coordinator recovery — **selected**, matching
   the execution-order amendment. (B) If shared-state coexistence is required, add a minimal fail-closed guard to
   every legacy discovery/recovery path before sharing state; full production Pi lifecycle/input/recovery remains
   WS-11 either way.
8. **D8 — Closing an incomplete/unknown Run (selected A).** (A) Keep it open and retain occupancy for unknown
   writers until they are proven stopped or a defined recovery path resolves them — **selected**; simplest and
   safest. (B) Permit explicit coordinator closure/abandonment referencing a HumanDecision; closure stops new claims
   but does not release an unknown writer or erase outputs. Retry/recovery remains WS-5.
9. **D9 — Context-efficient evidence and cleanup (selected policy).** Treat prompt/context capacity—not disk—as the
   scarce resource: index sources for search and load only relevant passages. While a Run is active, retain immutable
   authority/history, selected Run-local output packages, and one compact current resume note per active task, keyed by
   `run_id` and task/artifact identity—not `sessionId`. The active harness owns content-security decisions for note
   contents and other payloads; the kernel records the bound assessment but applies no universal secret scanner. The
   note is not authority. After Outcome is sealed, keep final outputs, validation, and provenance needed to explain
   delivery; an operator may remove the note and unselected scratch, but WS-4 does no automatic cleanup. These packages
   are execution evidence, not canonical project artifacts. The human chooses durable project artifacts and their
   storage locations; Kapisch records selected references/digests/provenance but does not pin or archive those
   artifacts. Never load the whole corpus into an agent context by default.

10. **D10 — Human-directed canonical artifact retention and harness-owned capture decisions (owner-approved).** The
    human chooses which project outputs are durable and where they are stored; Kapisch records selected references,
    versions/digests, and publication provenance without pinning temporary Git objects or archiving canonical artifacts.
    Temporary outputs needed for continuation are captured before workspace release only after the active harness
    supplies an assessment bound to the exact bytes, harness/profile, and effective policy identity. The kernel stores
    that disposition and enforces exact task scope, containment, symlink safety, and digest integrity; it does not scan,
    classify, redact, or override harness content decisions. A `block` or missing assessment means no capture. A
    `human_review` result permits one immutable request at `tasks/<task_id>/output-capture-requests/<attempt_id>.json`
    only if the harness policy permits human review. Its deterministic `capture_id` binds the exact attempt, assessment, policy identity, selectors, paths, kinds, and
    file-byte digests; deletion tombstones have no byte digest. A matching HumanDecision with `operation=capture_exception` and exact operands
    `{capture_request_ref, capture_request_digest, attempt_id}` approves only that request, and is accepted only when
    permitted by the harness. Without approval, the request remains pending, the task blocks
    dependents, and the Run stays open under D8(A); WS-4 has no decline or incomplete-Outcome closure. Recovery
    re-prompts if no decision exists; otherwise it re-hashes file entries, revalidates each tombstone against persisted
    post-setup baseline presence and final-state absence, and resumes the same package/manifest publication.
    Once captured, the exact immutable package may be referenced or materialized byte-for-byte into a dependent's fresh
    workspace without another Run-local capture. The dependent harness decides whether it may use the package;
    unchanged handoff bytes are not recaptured against the post-setup baseline, while changed/new bytes receive a new
    assessment. External evidence and resume notes also require the active harness's decision; WS-4 adds no
    cross-harness content exception. After Outcome is sealed, an operator may remove the note and unselected scratch;
    WS-4 does not clean automatically. Post-completion revision and actual stop-and-restart require a separate
    human-authorized WS-5 attempt. No harness denial can be waived by a core-level capture exception.
11. **D11 — Run-store location (simplified first slice).** Preserve the existing `state_root` API and default
    `<state_root>/.kapisch/runs/<run_id>` location. Do not add `run_store_root`, external-root configuration,
    project/store UUIDs, markers, custom POSIX/ACL validation, relocation, or previous-root search in WS-4. The
    external-store idea is deferred unless a concrete operational need justifies a separate design.

## 12. Acceptance criteria for the pending design

Definitions in §§1–11 are authoritative. These acceptance tests verify the selected design and required invariants; they are not alternate rules.

1. Accept a handoff whose declared output path overlaps a governing input only when that exact output is authorized
   by the WorkOrder. Capture/materialize only the selected immutable output package; handoffs remain non-authority evidence.
2. For human-selected canonical Git evidence, bind exact repository identity, final immutable object ID/version,
   selector/path, digest, and approval/publication provenance; do not create Run-owned refs or persist a temporary task
   commit as canonical. A squash-merge test selects the final published object and proves the discarded branch object
   is neither retained nor treated as equivalent. Missing required references fail closed. For required Run-local
   copies, test the active harness's assessment bound to exact bytes and effective policy identity; `block` yields no
   package or Git-pointer fallback, while `human_review` proceeds only through the harness-permitted flow. The core
   must not impose a universal secret-pattern scanner or override a harness decision.
3. Demonstrate legacy single-writer/post-claim re-read behavior unchanged and expanded local lock/publication
   boundary usage; Decision-first blocks stale completion and Outcome-first closes decision admission. No bespoke
   lock protocol or execution-duration lock.
4. Pause/detach does not establish stop or release occupancy. Independent explicit Run work is permitted only in a
   different proven-isolated workspace; no abandonment authority.
5. Test the explicit relevant-gate predicate and affected sets: unrelated head advance alone permits admission;
   changed selected bindings, acceptance withdrawal, relevant issue or run-wide blocker blocks; affected descendants
   are explicitly assessed.
6. Before authorization, refusal produces no attempt, setup writes, or worker. After authorization, setup failure is
   a real failed attempt with `worker_invoked: false`; unknown activity retains occupancy. No pre-start capture/disposition
   subsystem remains.
7. Exclusive Run allocation plus immutable envelope-file publication leaves existing destinations untouched;
   incomplete allocation is inert; legacy empty allocation remains supported; D7 isolation stays mandatory. No
   invisible/atomic-directory promise.
8. Review layout, producer table, restart language, and acceptance cases for no duplicate pre-start outcomes,
   duplicate source-admission definitions, orphan producer/record rows, or untyped observation records. Name the
   retained observation kind and conditional fields.
9. Preserve `state_root` and the current `.kapisch/runs/<run_id>` layout; test explicit Run-reference recovery with no
   scan or replacement. Test the exhaustive Run-format × WorkOrder-shape routing matrix, including every accepted legacy
   shape and rejection without fallback for expanded/mixed/mismatched formats. Test final output deltas against the
   post-setup worker baseline, including additions, replacements, and deletions. Verify original governing-input checks
   happen before handoff overlay; repository-state destinations are in dependent `write_targets[]`. Task workspaces
   are fresh and never assigned across tasks. Test predecessor output approved by its harness → handoff → dependent:
   unchanged bytes remain a reference without recapture; changed bytes get a new dependent-harness assessment. Test
   harness `allow`/`block`/`human_review` dispositions, exact request binding, no core override, and a harness-blocked
   evidence or resume-note copy. Test deterministic request identity in the attempt-keyed path and crash recovery after
   attempt result, request, approval, partial package, complete package, fixed manifest, and validation; existing
   package files are verified, missing files filled, and mismatched/extra files rejected. Inject failure/interruption
   after staging creation, during writing, after final-name linking, and before publication returns; leftover staging
   files must neither poison the canonical inventory nor supply recovery bytes. Verify no automatic scratch cleanup,
   missing/changed authorized-source rejection, and unchanged rejection of unexpected canonical package files.
   Assert at most one request,
   manifest, and validation per attempt. Test pending re-prompt under D8(A), exact `capture_exception` operands,
   wrong-attempt/path and digest-mismatch rejection, producer ownership, and capture/import receipts. A stopped or
   confirmed interruption preserves task/workspace association without partial-output capture; unknown activity retains
active occupancy. Neither may relaunch in WS-4; recovery is WS-5.
   Test resume-note assessment/omission, canonical records winning over stale notes, operator cleanup only after sealed
   Outcome, stale references, human steering, and amendment facts/cold restart at each producer-order boundary. No
   whole-corpus scan, transient-write history, or automatic cleanup is required. Test amendment proposed/delivered/acknowledged/assessed
   facts in producer order and cold restart at each intermediate state. Add cases supplementing (not replacing) rules
   already present in prose.

The accepted power-loss/storage-rollback limitation remains. No runtime authorization is granted by these design
criteria. Cross-check the tracker and execution-order plan against D1, D9, D10, and D11: post-setup final-state
outputs, the optional non-authoritative resume note, harness-owned security decisions, WS-5 stop/restart recovery, and
deferred external roots must agree. The kernel cannot override a harness block; a human review can authorize only the
exact request when the harness policy permits it. Structural, containment, scope, and digest failures remain
fail-closed.

## 13. Deferred implementation sequence and change boundary

After complete design approval and separately authorized implementation planning:

1. Before runtime implementation, update the canonical task-first contract for post-setup final-output capture,
   task-local resume context, and harness-owned security assessments while preserving its existing `state_root` and
   `.kapisch/runs` layout. Do not link this draft from the runtime-loaded contract before that step. Keep any WS-2 note
   informational; preserve its historical normative body and legacy semantics, and reject unsupported expanded state
   in every legacy reader/input producer before shared-state deployment.
2. Implement the bounded WS-4 records, deterministic-adapter dataflow, explicit handoffs, admission, capture
   validation, aggregation and completion gates. Reference existing durable SDD artifacts; do not build a stage
   engine.
3. Keep production steering in WS-11, reusable conformance in WS-10, and checkpoint compatibility/general recovery
   in WS-5. No automatic retry.
4. Validate the §12 acceptance criteria. Do not add event sourcing, transaction coordination, authoritative indexes,
   or durability beyond the explicit task-resume note, pending output-capture request, and final-output package.

This revision updates the WS-4 proposal, its informational note in the WS-2 design file, and the execution-order plan and tracker summaries so they agree on D1, D9, D10, and D11. `core/contracts/task-first.md` remains unchanged and has no link or note pointing to this unapproved proposal. The WS-2 historical normative body and all legacy semantics remain unchanged. No executable sources or tests change; this grants no runtime authorization.
