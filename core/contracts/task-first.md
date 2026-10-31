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

The coordinator creates Run and WorkOrder. Before start, Run records an `attempt_allocation` containing a unique attempt ID and output path. `validate_dispatch` is a read-only preflight; `claim_dispatch` revalidates and atomically creates the fixed `dispatch-claim.json` before the host adapter is invoked. The claim records `status=claimed` and binds the Run, WorkOrder reference/digest, Decision ID/digest, attempt ID, and output reference. Exclusive creation allows only one process to claim that Run. A persisted claim with no collected result is uncertain and blocks automatic redispatch after restart; this slice has no retry or claim-recovery mechanism. After collection, Run records the Attempt, report, and Outcome references/digests; it is not authorization. WorkOrder references one HumanDecision and exactly one task. HumanDecision is immutable and includes `decision_id`, `question_id`, original question, answer, subject, scope, decision type, source kind, optional attribution, and the governing-input ref/digest snapshot. Adapter session identifiers and host handles are adapter metadata, never portable identity. An adapter that captures a pending-request answer writes a supplied `run_id` under the portable run path; legacy requests without one stay in the adapter's session-local path.

Applicability is recomputed for the exact decision, WorkOrder subject/scope, answer, and governing inputs. The coordinator persists `applicability.json` with those bindings, a result (`applicable`, `not_applicable`, or `ambiguous`), and a reason. It is derived evidence, not an independent authority source: only an explicit direct or attributed human decision can authorize work. The coordinator must mark refusal, conditional, uncertain, stale, or out-of-scope responses non-applicable/ambiguous and seek clarification; it must not infer approval from `decision_type=approval`. The core fails closed on anything other than `applicable`, or any stale/mismatched binding. It does not attempt natural-language classification.

WorkOrder records one task, non-empty acceptance criteria, required capabilities, worker route/role, canonical-implementer availability, and decision/applicability refs and digests. An ordinary route requires the canonical implementer. The one-task host-native fallback is eligible only when the canonical implementer is unavailable and the persisted applicability evidence explicitly authorizes this bounded route. Do not mislabel a host-native worker as an implementer. Capability probes use `supported`, `unsupported`, or `unknown` plus a reason. Required capabilities block dispatch unless actually supported and explained; no capability is inferred or silently emulated. Call `claim_dispatch` before host start with current adapter capabilities and canonical-implementer availability; it performs the read-only `validate_dispatch` checks, then persists the one-shot claim. An existing claim or any Run already carrying Attempt/report/Outcome references blocks dispatch, as do pre-existing Attempt/output files and unknown/unsupported/unproven required capabilities.

The human-input boundary is the sole HumanDecision producer: the host input adapter captures one explicit pending-request answer, while the coordinator produces one direct-prompt record. Neither path creates duplicate approval. Coordinator owns the single Attempt record and lifecycle references; worker writes only its unique output. The aggregator owns the report and binds it to the exact Attempt digest, output reference/digest, WorkOrder, Decision, task coverage, and acceptance criteria. It records `failures`, `conflicts`, `missing_references`, and `unresolved_issues` as explicit empty arrays for a successful result; omitted arrays do not count as empty. Coordinator validates all records and publishes Outcome only for one successful attempt and a complete valid report. Outcome grants no external-effect permission.

## Required record fields

Keys are literal. Missing, mistyped, or contradictory keys fail closed, and
unknown extra keys are ignored except where noted. The dispatch claim and the
Outcome are compared for exact equality, so they must contain exactly the
listed keys.

- **Run:** `run_id`, `workorder_ref`, `workorder_digest`, `attempt_allocation`
  (`attempt_id`, `output_ref`); after collection `attempt_ref`,
  `attempt_digest`, `aggregation_ref`, `aggregation_digest`; after publication
  `outcome_ref`, `outcome_digest`.
- **HumanDecision:** `decision_id`, `question_id`, `question`, `answer`,
  `subject`, `scope`, `decision_type`, `source_kind`, `governing_inputs`;
  `source_ref` is required for `external_artifact`.
- **Applicability:** `decision_id`, `decision_ref`, `decision_digest`,
  `answer_digest`, `subject`, `scope`, `governing_inputs`, `result`, `reason`,
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
- **Outcome:** the coordinator persists exactly the object returned by
  `validate_acceptance`, so hand-authored or partial Outcomes never match; a
  worker or aggregator never writes one.

## Validation and restart

The core validates exact bytes/digests, project-root confinement, same-Run references, decision identity uniqueness, required `question_id`, authorization scope, applicability, one-task shape, Attempt/WorkOrder/Decision bindings, dispatch-claim/Run/WorkOrder/Decision bindings, report/Attempt digest and output-reference/digest bindings, output evidence, and complete coverage. Governing Git inputs must be tracked and match the stored digest in HEAD, the index, and the working tree; any change requires reassessment. Missing, malformed, duplicate, failed, stale, unsupported, or mismatched artifacts fail closed.

After writing `outcome.json`, record its reference and digest in Run. A fresh process calls `validate_outcome`, which reloads Run, WorkOrder, HumanDecision, Applicability, Attempt, report, and evidence from portable refs, recomputes acceptance, and compares it with the persisted Outcome. Do not recover authority from process memory, conversation history, or a host session; never recreate missing records silently.
