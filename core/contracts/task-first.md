# Task-first single-task contract

This contract covers one persisted Run, one authorized WorkOrder containing exactly one task, one Attempt, one aggregation report, and a coordinator-produced Outcome. It does not schedule tasks, retry work, or invoke an LLM. Files are project-relative JSON references with SHA-256 digests over exact bytes.

## Portable records and authority

The canonical layout is relative to `state_root`, the primary checkout that owns durable state:

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

Before asking any decision question, the coordinator creates the Run with `create_run(state_root)`: it generates a canonical lowercase UUIDv4 and exclusively creates the empty `.kapisch/runs/<run_id>/` directory, so an existing directory fails creation. Never type or invent a Run id. `run.json` is created exclusively later, once the WorkOrder exists. After compaction, restart, or handoff, recover the id from disk, not from conversation: open Runs are Run directories without `dispatch-claim.json`, and if more than one could belong to the task, ask the human rather than guess. A task-first decision request must carry this Run's `run_id`; missing, malformed, or misrouted ids fail closed. A pending-input adapter must not infer identity from a session or process id, and it writes only into an existing Run directory that has no `dispatch-claim.json`; otherwise it blocks the input and tells the user the request may carry a wrong Run id. The host input adapter produces the decision for an explicit pending-request answer; the coordinator produces a separate record for a direct human prompt. Neither path duplicates the other's record. A HumanDecision includes `source_kind`; optional `source_ref` and `approving_party` are absent or non-empty strings, and `external_artifact` requires a non-empty `source_ref`. Portable records contain no session or child-process identity. Pre-realignment HumanDecisions without `run_id` are rejected; there is no migration or fallback.

`state_root` is the canonical primary working tree of the repository (its `.git` is the common Git directory). Every Run artifact, including HumanDecisions, is stored only under `<state_root>/.kapisch/runs/<run_id>/`. `source_root` is the existing primary checkout or linked worktree whose HEAD, index, and working-tree bytes are checked for governing-input freshness. They may be equal, but the harness supplies both explicitly; public kernel entry points take `state_root` positionally and a required keyword-only `source_root`. One private validator accepts the pair only when both are existing Git checkout roots (`rev-parse --show-toplevel` equals each path), both share one common Git directory, and `state_root` is primary (`--git-dir` equals `--git-common-dir`, which is `<state_root>/.git`). Missing roots, bare/separate-git-dir layouts, and other invalid mappings fail with `invalid state_root/source_root mapping`; there is no kernel-side root discovery. Freshness reads use `source_root`; state reads and writes use `state_root`. No machine-specific root is persisted, so a fresh process can validate a Run after its source worktree is removed by supplying a surviving checkout.

## Run-local decisions, reassessment, and supersession

HumanDecisions and all other execution authority are Run-local. A HumanDecision has a required `run_id` equal to its owning Run. Its `decision_ref` must be exactly `.kapisch/runs/<run_id>/decisions/<decision_id>.json`; a reference to another Run fails with `decision reference is outside its Run`, and a missing, non-string, or mismatched record field fails with `decision run mismatch`. Decision IDs are unique only within that Run's `decisions/` directory. `question_id` is an opaque non-empty string; there is no global question index or same-question ambiguity rule. No global decision index or authority graph exists, and no file from another Run is read to authorize, revoke, or disambiguate this Run.

Project knowledge is shared; execution authority is not. Before asking, consult relevant tracked documentation, ADRs, approved plans and implementation artifacts, external sources exposed by the harness, and explicitly published instructions. Cite current Git evidence in `governing_inputs`; preserve external provenance with `source_kind` and `source_ref`. Those sources can inform the coordinator's semantic applicability judgment, but a decision from another Run is never reusable permission. If this Run lacks applicable authorization, or coverage is ambiguous, record the Run-local assessment and obtain a new Run-local HumanDecision. A human-approved PR merge makes the approved repository artifacts shared project knowledge; it does not promote or copy a Run-local HumanDecision.

The coordinator assesses whether the exact subject, scope, and action are covered and whether changed inputs require reassessment; semantic judgment stays outside the kernel. A WorkOrder references one decision and one task. The selected authorizing decision must be `approval` with non-empty governing Git inputs; other recognized decisions remain valid records but do not authorize it. The immutable decision and its original `governing_inputs` snapshot are never rewritten. Applicability binds the exact decision ID/reference/digest, answer digest, subject, scope, and assessed inputs. Optional `original_governing_inputs` must equal the decision snapshot exactly. When absent, assessed inputs must equal that snapshot; when present, original inputs are historical and shape/equality checked only. Both snapshots use a list (possibly empty) of exact `{ref, digest}` records with non-empty refs and lowercase SHA-256 digests; duplicate and opaque/non-Git refs are allowed historically. Current assessed inputs are checked against `source_root` HEAD, index, and working tree, and WorkOrder inputs must equal the assessed snapshot. An empty historical decision snapshot cannot authorize dispatch because selected authority and fresh WorkOrder inputs remain non-empty. Decision, applicability, and WorkOrder subject and scope must be byte-for-byte equal; reassessment cannot widen or change subject, scope, or action. Only `applicable` with a non-empty reason permits dispatch; `not_applicable`, `ambiguous`, and `reassessment_required` block with distinct errors. Unknown/malformed result values are invalid, and `superseded` is never a persisted result. When this Run's authorization no longer covers the work, the coordinator records `not_applicable` or `ambiguous` and obtains a fresh Run-local HumanDecision. Per-task authorization bindings and in-scope/out-of-scope DAG rules are WS-4.

Only the human-input boundary may add `supersedes` when producing a new immutable decision. Supersession is prospective, transitive, and dispatch-only. `validate_dispatch` and `claim_dispatch` enumerate and validate only `<state_root>/.kapisch/runs/<run_id>/decisions/*.json` for the owning Run; malformed files fail dispatch closed. A supersedes target in another Run fails with `supersedes target is outside its Run`. Acceptance, claimed Attempts, and completed Outcomes are not re-judged or mutated. Older validators ignore this authority-bearing field; Host producers do not emit it until WS-11.

The supported concurrency model is exactly one active coordinator/authority writer per Run. Independent Runs share no authority graph or cross-Run race. `claim_dispatch` re-reads this Run's decisions after it creates the claim and marks the Run `claimed`; if the selected decision is superseded by then, it fails before the host starts and leaves the claimed Run for operator reconciliation. Because decision files are published atomically, a superseder that a second writer publishes before the claim is always seen, and one published after it is prospective. No lock or distributed synchronization is added. Exclusive claim creation still guarantees one claim per Run.

### Retention of Run history

Retain Run history under `state_root`. Every selected decision and its supersedes chain must remain byte-for-byte unchanged while the Run is validated; superseding decisions must also be retained because deleting one can make an older decision eligible again. Removing a Run directory breaks cold-restart validation and fails closed with the relevant missing-reference error. Retention policy, archival, and garbage collection are owner-decided and out of scope. A source worktree may be removed without deleting Run history.

### Machine-checkable decision contract

The stable block label and field names below are contract metadata, not prose assertions. Diagnostics list kernel-owned stable errors; the `superseded` diagnostic is the prefix before the decision ID. `ContractError` is the existing public error class, not a new exception type.

<!-- ws2-decision-contract -->
```json
{
  "run_identity": {
    "format": "canonical lowercase UUIDv4",
    "producer": "coordinator",
    "creation": "exclusive Run directory via create_run"
  },
  "roots": {
    "state_root": "primary checkout",
    "source_root": "Git checkout"
  },
  "human_decision": {
    "run_id_required": true
  },
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
    "missing_decision": "missing referenced decision",
    "invalid_run_identity": "invalid Run identity",
    "decision_outside_run": "decision reference is outside its Run",
    "supersedes_outside_run": "supersedes target is outside its Run",
    "decision_run_mismatch": "decision run mismatch",
    "invalid_root_mapping": "invalid state_root/source_root mapping"
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
- **HumanDecision:** `decision_id`, required owning `run_id`, `question_id`,
  `question`, `answer`, `subject`, `scope`, `decision_type`, `source_kind`, `governing_inputs`;
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

Every public kernel entry receives an explicit `state_root` and keyword-only `source_root`; one root validator checks both once and fails with `invalid state_root/source_root mapping` unless they are checkout roots in the same repository and `state_root` is primary. The core validates canonical Run IDs, exact bytes/digests, confinement under `state_root`, same-Run references, decision identity uniqueness only within the owning Run's decisions directory, required HumanDecision `run_id`, authorization scope, applicability, one-task shape, Attempt/WorkOrder/Decision bindings, dispatch-claim/Run/WorkOrder/Decision bindings, report/Attempt digest and output-reference/digest bindings, output evidence, and complete coverage. Governing Git inputs must be tracked and match the stored digest in HEAD, the index, and the working tree of `source_root`; any change requires reassessment. Missing, malformed, duplicate, failed, stale, unsupported, or mismatched artifacts fail closed. The uniqueness check assumes complete enumeration of intact local artifact directories; it is not a security boundary against arbitrary local filesystem corruption or a subject able to modify authoritative artifacts. An unreadable directory omitted by a filesystem API can hide a duplicate Decision ID, so uniqueness is guaranteed only over artifacts visible to the validator.

After writing `outcome.json`, record its reference and digest in Run. A fresh process calls `validate_outcome`, which reloads Run, WorkOrder, HumanDecision, Applicability, Attempt, report, and evidence from portable refs, recomputes acceptance, and compares it with the persisted Outcome. Do not recover authority from process memory, conversation history, or a host session, and never recreate missing records silently. Harness-specific session history may help locate work product for human-assisted recovery, but must not be required, parsed by the portable core, or treated as proof that an unrecorded effect did not occur.
