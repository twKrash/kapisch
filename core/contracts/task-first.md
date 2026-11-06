# Task-first single-task contract

This contract covers one persisted Run, one authorized WorkOrder containing exactly one task, one Attempt, one aggregation report, and a coordinator-produced Outcome. It does not schedule tasks, retry work, or invoke an LLM. Files are project-relative JSON references with SHA-256 digests over exact bytes.

## Portable records and authority

The canonical layout is:

```
.kapisch/runs/<run_id>/run.json
.kapisch/runs/<run_id>/workorder.json
.kapisch/runs/<run_id>/decisions/<decision_id>.json
.kapisch/runs/<run_id>/applicability.json
.kapisch/runs/<run_id>/dispatch-claim.json
.kapisch/runs/<run_id>/attempts/<attempt_id>.json
.kapisch/runs/<run_id>/aggregation.json
.kapisch/runs/<run_id>/outcome.json
```

The coordinator creates Run and WorkOrder; a new Run starts with `dispatch_state=ready`. Before start, Run records an `attempt_allocation` containing a unique attempt ID and output path. `validate_dispatch` is a read-only preflight; `claim_dispatch` revalidates, exclusively creates the fixed `dispatch-claim.json`, then atomically replaces Run with `dispatch_state=claimed` before the host adapter is invoked. The claim records `status=claimed` and binds the Run, WorkOrder reference/digest, Decision ID/digest, attempt ID, and output reference. The claimed Run state blocks redispatch if the best-effort claim is lost during an ordinary controller restart; exclusive creation also prevents concurrent claims. Neither Run replacement nor claim creation is explicitly synced to storage, so this does not guarantee survival of power loss or storage rollback. Any incomplete `claimed` Run is uncertain whether its claim or output is present or missing; absence does not prove that dispatch did not occur. Do not automatically redispatch an incomplete Run. A missing or unknown dispatch state is invalid and requires operator reconciliation. Inspect portable artifacts and actual work products; any available harness history may help a human investigate, but is optional evidence and never authority. If completion cannot be established, ask the operator to reconcile. An explicitly authorized retry uses a new Run, and uncertain external effects still require reconciliation or scoped human authorization. This slice does not automate recovery or retry. After collection, Run records the Attempt, report, and Outcome references/digests; it is not authorization. WorkOrder references one HumanDecision and exactly one task. HumanDecision is immutable and includes `decision_id`, `question_id`, original question, answer, subject, scope, decision type, source kind, optional attribution, and the governing-input ref/digest snapshot. Adapter session identifiers and host handles are adapter metadata, never portable identity. An adapter that captures a pending-request answer writes a supplied `run_id` under the portable run path; legacy requests without one stay in the adapter's session-local path.

## Decision reuse, reassessment, and supersession

Before asking the human, inspect existing HumanDecision records under `.kapisch/runs/*/decisions/`, including decisions reported from external records. The LLM coordinator decides whether subject, scope, action and the proposed work are already covered, and whether input changes are substantive. There is no kernel semantic matcher, global question index, or same-question ambiguity rule; `question_id` is an opaque non-empty string. If authorization does not cover the work or coverage is ambiguous, persist `not_applicable` or `ambiguous` and obtain a fresh HumanDecision. Never infer approval from `decision_type=approval` or agent advice.

The shared HumanDecision reader accepts `answer`, `correction`, `approval`, `risk_acceptance`, and `external_effect_authorization`; a selected WorkOrder authorizing decision must still have `decision_type=approval` and non-empty governing Git inputs. Unrelated valid decisions with empty snapshots do not block dispatch and can be supersession targets or superseders. The producer accepts optional request attribution as absent or null (omitted in emitted decisions), or a non-empty string; emitted `source_ref` and `approving_party`, when present, are non-empty strings. `external_artifact` requires `source_ref`; the producer emits no `run_id` field in the decision. A WorkOrder can reuse one original immutable decision from any Run at `.kapisch/runs/<run>/decisions/<decision_id>.json`. Never copy or re-create a decision in a consuming Run. Canonical layout, project-root confinement, exact filename and decision identity, project-wide uniqueness, exact-byte digests, and rejection of symlinked files or path components still apply. Applicability stays inside the consuming Run. External-record reuse preserves source attribution through the original decision reference and `source_kind`; `external_artifact` requires a non-empty `source_ref` in that original record. Outcome does not gain a `source_ref` field.

The coordinator persists applicability bindings to the exact decision ID/reference/digest, answer digest, WorkOrder subject/scope, and assessed `governing_inputs`, plus `result` and a non-empty `reason`. Only `applicable` authorizes work; `not_applicable`, `ambiguous`, and `reassessment_required` block with distinct errors, and unknown or malformed results are invalid. `superseded` is never a persisted applicability result: it is derived from explicit human authority by the dispatch validator.

For reassessment, keep the decision and its snapshot byte-for-byte unchanged. Persist the decision's exact original snapshot as `original_governing_inputs` in applicability and the reassessed current snapshot as `governing_inputs` in both applicability and WorkOrder; refresh applicability and WorkOrder digests in their consumers. `original_governing_inputs` is historical: both historical snapshots use the producer shape: a list (possibly empty) of exact `{ref, digest}` records, non-empty string refs and lowercase SHA-256 digests; repeated or non-Git refs are allowed historically. They must match exactly, in order; do not compare historical bytes with current Git. A present empty original snapshot is valid only when the decision snapshot is also empty. A present null, malformed, or mismatching snapshot is invalid. An empty original is not absence: presence compares the original snapshot, while absence requires assessed inputs to equal that snapshot. Selected WorkOrder authority still requires a non-empty, portable, unique governing-input snapshot in the decision and non-empty fresh Git inputs in the WorkOrder, so an empty-input decision never authorizes dispatch, even with an explicit empty original snapshot. Absence retains the #85 meaning: assessed inputs must equal the decision snapshot. Assessed inputs must still match HEAD, index and working-tree bytes. Reassessment cannot change subject, scope, or action authority. Per-task authorization and narrowing remain WS-4.

Only the human-input boundary produces `supersedes` together with a new immutable HumanDecision: the host input adapter for a pending request, or the coordinator recording a direct human prompt. A coordinator must never add inferred supersession to an existing decision. Absence means no edges; if present, `supersedes` must be a non-empty list of exact `{decision_id, decision_ref, decision_digest}` objects, with no repeated target ID or reference. Targets must exist with the stated ID and exact digest. Question IDs need not match. Self-reference and cycles are invalid; structure, target identities, self-reference and cycles are checked before target digests so cyclic invalid records need no digest fixed point to be rejected.

Supersession is prospective, transitive, and never revives an earlier target when its superseder is superseded. The global graph integrity and eligibility checks run only in `validate_dispatch` (and `claim_dispatch` through delegation), never in `validate_run`, `_validate_workorder`, acceptance, or Outcome validation. Dispatch reads every enumerated `*.json` under `.kapisch/runs/*/decisions/`, parses each HumanDecision including unconnected records exactly once per dispatch call, builds temporary identity/path/digest and forward-edge lookups, then validates the graph. The selected decision uses that same call-local byte snapshot. No persisted index or cross-call/module-level cache is used. Sorted enumeration and heap-based cycle validation cost O(N log N + E) time plus input-byte parsing, and O(N + E) auxiliary space; each file is read once. A later malformed decision file blocks dispatch but does not trigger new graph checks on an already claimed Run or completed Outcome. Graph validation and rejected dispatch are read-only; historical artifacts are not mutated or re-judged for supersession. Incomplete enumeration under arbitrary local filesystem corruption remains outside PR85-009. Existing current-input freshness checks still run at acceptance and Outcome validation; this pre-existing behavior is unchanged.

Older validators ignore `supersedes` and can still honor a superseded target: use a WS-2-capable validator before relying on this authority-bearing field. Harness producers must not emit this field until WS-11. No database, durable question index, event log, additional orchestration subsystem, or host identifier is introduced.

On task-first resume or handoff, reconstruct the original decision, current applicability, WorkOrder, Run and their exact bindings from persisted files; do not rely on conversation or copied authority. Reuse the original decision and reassess current inputs before new dispatch. A handoff or worker recommendation grants no human authority. Preserve claimed Runs and completed Outcomes; do not use supersession to authorize redispatch or to infer retry safety. The general v3 resume/handoff policies govern their separate stage-attempt lifecycle and are unchanged by this task-first addendum.

WorkOrder records one task, non-empty acceptance criteria, required capabilities, worker route/role, canonical-implementer availability, and decision/applicability refs and digests. An ordinary route requires the canonical implementer. The one-task host-native fallback is eligible only when the canonical implementer is unavailable and the persisted applicability evidence explicitly authorizes this bounded route. Do not mislabel a host-native worker as an implementer. Capability probes use `supported`, `unsupported`, or `unknown` plus a reason. Required capabilities block dispatch unless actually supported and explained; no capability is inferred or silently emulated. Call `claim_dispatch` before host start with current adapter capabilities and canonical-implementer availability; it performs the read-only `validate_dispatch` checks, then persists the one-shot claim. A `claimed` Run state, an existing claim, or any Run already carrying Attempt/report/Outcome references blocks dispatch, as do pre-existing Attempt/output files and unknown/unsupported/unproven required capabilities.

The human-input boundary is the sole HumanDecision producer: the host input adapter captures one explicit pending-request answer, while the coordinator produces one direct-prompt record. Neither path creates duplicate approval. Coordinator owns the single Attempt record and lifecycle references; worker writes only its unique output. The aggregator owns the report and binds it to the exact Attempt digest, output reference/digest, WorkOrder, Decision, task coverage, and acceptance criteria. It records `failures`, `conflicts`, `missing_references`, and `unresolved_issues` as explicit empty arrays for a successful result; omitted arrays do not count as empty. Coordinator validates all records and publishes Outcome only for one successful attempt and a complete valid report. Optional advisory review is findings-only: its coordinator-owned status is carried into Outcome but never gates acceptance or grants authority. Outcome grants no external-effect permission.

### Retention of cross-Run authority

A referenced HumanDecision and every decision in its `supersedes` chain must remain retained and byte-for-byte unmodified for as long as any Run or WorkOrder references it. Moving or archiving a Run directory that contains a still-referenced decision breaks cold-restart validation: missing selected decisions fail closed with `missing referenced decision`; missing chain targets fail closed with `supersedes target is missing`. The kernel never rewrites, archives or deletes decision files. Superseding decisions must also be retained. Supersession is derived at dispatch from the persisted superseder; deleting a superseder can make an older superseded decision eligible again, even when nothing references the superseder. Until a future retention/GC policy is approved, do not delete any HumanDecision record, including an apparently unreferenced superseder. Retention policy and garbage collection are out of scope and owner-decided; do not assume that a completed Run makes its decision safe to remove.

### Machine-checkable decision contract

The stable block label and field names below are contract metadata, not prose assertions. Diagnostics list kernel-owned stable errors; the `superseded` diagnostic is the prefix before the decision ID. `ContractError` is the existing public error class, not a new exception type.

<!-- ws2-decision-contract -->
```json
{
  "applicability": {
    "results": [
      "ambiguous",
      "applicable",
      "not_applicable",
      "reassessment_required"
    ],
    "binding_fields": [
      "decision_id",
      "decision_ref",
      "decision_digest",
      "answer_digest",
      "subject",
      "scope",
      "governing_inputs"
    ],
    "optional_fields": [
      "original_governing_inputs"
    ],
    "required_fields": [
      "result",
      "reason"
    ]
  },
  "supersedes": {
    "entry_fields": [
      "decision_digest",
      "decision_id",
      "decision_ref"
    ]
  },
  "error_classes": [
    "ContractError"
  ],
  "diagnostics": {
    "invalid_result": "invalid decision applicability result",
    "ambiguous": "decision applicability result is ambiguous",
    "not_applicable": "decision applicability result is not_applicable",
    "reassessment_required": "decision applicability result is reassessment_required",
    "missing_target": "supersedes target is missing",
    "superseded": "decision is superseded",
    "missing_decision": "missing referenced decision"
  }
}
```
<!-- /ws2-decision-contract -->

## Required record fields

Keys are literal. Missing, mistyped, or contradictory keys fail closed, and
unknown extra keys are ignored except where noted. The dispatch claim and the
Outcome are compared for exact equality, so they must contain exactly the
listed keys.

- **Run:** `run_id`, `workorder_ref`, `workorder_digest`, `dispatch_state`
  (`ready` before dispatch, `claimed` once consumed), `attempt_allocation`
  (`attempt_id`, `output_ref`); optional `advisory_review`; after collection `attempt_ref`,
  `attempt_digest`, `aggregation_ref`, `aggregation_digest`; after publication
  `outcome_ref`, `outcome_digest`.
- **HumanDecision:** `decision_id`, `question_id`, `question`, `answer`,
  `subject`, `scope`, `decision_type`, `source_kind`, `governing_inputs`;
  `source_ref` is required for `external_artifact`; optional `supersedes` follows
  the exact edge schema above.
- **Applicability:** `decision_id`, `decision_ref`, `decision_digest`,
  `answer_digest`, `subject`, `scope`, `governing_inputs`, `result`, `reason`;
  optional `original_governing_inputs` carries the historical snapshot,
  plus `host_native_fallback_authorized` and `fallback_authorization_reason`
  for the host-native fallback. `answer_digest` is SHA-256 over the UTF-8 bytes
  of the `answer` string itself, not over a file.
- **WorkOrder:** `workorder_id`, `decision_id`, `decision_ref`,
  `decision_digest`, `applicability_ref`, `applicability_digest`, `subject`,
  `scope`, `task` (`task_id`), `acceptance_criteria`, `governing_inputs`,
  `required_capabilities`, `worker_route`, `worker_role`,
  `canonical_implementer_available`. An extra `tasks` key is rejected
  outright; the one task lives under `task`.
- **Dispatch claim:** `status`, `run_id`, `run_ref`, `workorder_ref`,
  `workorder_digest`, `decision_id`, `decision_digest`, `attempt_id`,
  `output_ref`.
- **Attempt:** `attempt_id`, `task_id`, `workorder_id`, `workorder_ref`,
  `workorder_digest`, `decision_id`, `decision_digest`, `status`,
  `output_ref`, `output_digest`.
- **Aggregation report:** `coverage`, `acceptance_criteria`, `result`,
  `attempt_ref`, `attempt_digest`, `attempt_id`, `task_id`, `workorder_ref`,
  `workorder_id`, `workorder_digest`, `decision_id`, `decision_digest`,
  `output_ref`, `output_digest`, `failures`, `conflicts`,
  `missing_references`, `unresolved_issues`.
- **Advisory review status:** an optional coordinator-owned Run field. Omission
  means `{"status":"not_run"}`. A performed review records exactly
  `status=performed`, `workorder_ref`, `workorder_digest`, `attempt_ref`,
  `attempt_id`, and `attempt_digest`, each matching the accepted WorkOrder and
  Attempt. Malformed or rebound metadata fails closed. This records status, not
  approval, reviewer authority, or a prerequisite.
- **Outcome:** the coordinator persists exactly the object returned by
  `validate_acceptance`, including normalized `advisory_review` status, so
  hand-authored or partial Outcomes never match; a worker or aggregator never
  writes one.

## Validation and restart

The core validates exact bytes/digests, project-root confinement, same-Run references, decision identity uniqueness across enumerated canonical Decision artifacts, required `question_id`, authorization scope, applicability, one-task shape, Attempt/WorkOrder/Decision bindings, dispatch-claim/Run/WorkOrder/Decision bindings, report/Attempt digest and output-reference/digest bindings, output evidence, and complete coverage. Governing Git inputs must be tracked and match the stored digest in HEAD, the index, and the working tree; any change requires reassessment. Missing, malformed, duplicate, failed, stale, unsupported, or mismatched artifacts fail closed. The uniqueness check assumes complete enumeration of intact local artifact directories; it is not a security boundary against arbitrary local filesystem corruption or a subject able to modify authoritative artifacts. An unreadable directory omitted by a filesystem API can hide a duplicate Decision ID, so uniqueness is guaranteed only over artifacts visible to the validator.

After writing `outcome.json`, record its reference and digest in Run. A fresh process calls `validate_outcome`, which reloads Run, WorkOrder, HumanDecision, Applicability, Attempt, report, and evidence from portable refs, recomputes acceptance, and compares it with the persisted Outcome. Do not recover authority from process memory, conversation history, or a host session, and never recreate missing records silently. Harness-specific session history may help locate work product for human-assisted recovery, but must not be required, parsed by the portable core, or treated as proof that an unrecorded effect did not occur.
