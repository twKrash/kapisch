# Stage 6.5 M1.2 — Review-evidence persistence contract freeze

**Status: PROPOSED / DOCS-ONLY / PENDING INDEPENDENT REVIEW AND EXPLICIT
REPOSITORY-OWNER APPROVAL OF THIS EXACT COMMIT**

This document freezes the bounded M1.2 persistence contract proposed after the
M1.1 format/model increment. It is a proposal, not implementation authority.
No production code, retained schema, bundle bytes, or runtime gate record is
changed by this document.

Approval, when recorded, applies only to this exact document revision and the
bounded M1.2 scope below. A later semantic change invalidates the approval and
requires a new independent review and approval tied to the new commit SHA.
A runtime `GateApprovalRecord` is not governance evidence for this
implementation authorization; repository-owner approval of the exact reviewed
commit is required.

## 1. Bounded scope

M1.2 may persist and cold-load the immutable review-evidence chain under an
existing Stage 4 operation identity, preserving fail-closed behavior and
without dispatching an adapter.

M1.2 includes only:

- the closed `review-scope/1` artifact and its core/controller publisher;
- exact review request, pre-dispatch fingerprint, reservation, uncertainty,
  invocation, and result-chain binding rules;
- immutable operation-scoped evidence paths and checked loading;
- a narrowly guarded, idempotent run-state backlink repair;
- regression coverage for publication ordering, ownership, digest equality,
  refusal, and cold restart.

M1.2 does not introduce or authorize:

- reviewer dispatch, reviewer-return production, host execution, or result
  production;
- Stage 5 consumer support or authority eligibility;
- writer-quiescence enforcement or a writer-quiescence producer;
- Stage 7 lifecycle transitions, new statuses, retry policy, reconciliation
  dispatch, or adapter APIs;
- changes to retained schemas, existing bundle bytes, or the Stage 7.0
  transition matrix.

The prior M0 §11 implementation gate remains unchanged until this exact
proposal is approved. This document proposes one narrow, explicit amendment to
that gate: after repository-owner approval of this exact reviewed commit, the
factual-only M1.2 persistence unit may be implemented without waiting for the
separate writer-quiescence approval. That amendment does not authorize current
authority. The existing Stage 6.5 stop gate remains in force for current use:
until the independently reviewed writer-quiescence producer and contract
receive their separate approval, persisted evidence is factual history only
and cannot establish current authority, approval, readiness, or eligibility.
If this exact amendment is not approved, the prior M0 §11 implementation gate
continues to prohibit M1.2 persistence.

## 2. Canonical representation and identities

All new immutable JSON is UTF-8 canonical JSON using the repository's existing
`canonical_json` rules. Loaders reject duplicate keys, unknown or missing
fields, noncanonical bytes, malformed identities, digest mismatches, aliases,
and substituted artifacts.

A review revision anchor is the closed string form:

```text
sha1:<40 lowercase hexadecimal commit>
sha256:<64 lowercase hexadecimal commit>
```

The prefix is the observed Git object format. Ref names, abbreviated IDs,
ranges, symbolic revisions, and post-publication recomputation are invalid.
The anchor parser must agree with the observed repository object format.

`ReviewInvocation.base` and `.head` retain their M1.1 field names and string
wire types, but M1.2 persistence validation applies the exact anchor grammar
above. The corresponding fingerprint retains its existing `{object_format,
head, ...}` representation; equality compares the parsed anchor to those
factual fields.

## 3. Closed review-scope/1 artifact

The exact canonical payload is closed to these fields:

```json
{
  "protocol_version": 3,
  "scope_contract": "review-scope/1",
  "run_id": "<run identity>",
  "stage_id": "<stage identity>",
  "purpose": "iteration" | "final",
  "plan_candidate_ref": {
    "path": ".kapisch/v3/authority/plan-approval-candidates/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest>"
  },
  "comparison_base": "sha1:<commit>" | "sha256:<commit>",
  "coverage": {
    "kind": "graph-free-task"
  }
}
```

For milestone coverage the closed `coverage` value is instead:

```json
{
  "kind": "milestone",
  "node_ids": ["<sorted unique node identity>", "..."]
}
```

No other coverage fields are permitted. `node_ids` must be nonempty, sorted
by their canonical identity bytes, and duplicate-free. The scope has no
invocation locator, result locator, operation ID, reviewer return, provenance,
or other backlink.

The `plan_candidate_ref` shape and path are the existing Stage 5
`PlanApprovalCandidate` reference contract. The publisher loads and validates
the exact candidate and its retained bundle; it does not accept caller-supplied
scope bytes or an arbitrary serialized coverage object.

The core/controller review-scope publisher is the sole producer. It runs only
after the existing Stage 4 planned attempt has durably produced and owned the
`stage_id`; it derives the payload from that validated run/stage context and
the exact retained `PlanApprovalCandidate`. It may copy `comparison_base` only
from the separately approved immutable comparison-base producer described in
§7; it must not accept a caller-selected base. It owns the scope reference and
publishes the immutable bytes before the review request or invocation. It must
verify:

- the candidate belongs to the same run and is the current validated plan
  candidate for the stage;
- graph-free coverage is emitted only for a graph-free candidate;
- milestone coverage is derived from the approved plan's complete retained
  graph and node scopes;
- a milestone `final` scope contains every approved graph node exactly once;
- an `iteration` scope contains only the bounded node/work owned by that review
  stage and does not expand coverage from caller input;
- `comparison_base` is the exact binding loaded from the separately approved
  comparison-base producer, resolves to a commit in the observed object
  format, and is not caller-selected;
- the resulting digest and canonical path are retained without replacement.

The scope digest is the SHA-256 digest of the exact canonical scope bytes. Its
repository-relative locator is:

```text
.kapisch/v3/runs/<run_id>/review-inputs/scopes/<scope_digest>.json
```

A scope cannot be replaced, repaired from controller memory, or substituted by
a rendered diff, `head`, an applicability-scope descriptor, or a nearby file.

## 4. Retained-bundle compatibility

A retained bundle supports this contract only when its retained, immutable
payload explicitly contains both exact capability values:

```text
review_contract = "review-evidence/1"
review_schema_variant = "review-invocation/1"
```

The exact supported variant covers the M0 `ReviewInvocation` vocabulary, the
`review-scope/1` dependency above, and a retained run-schema definition that
contains the optional top-level `review_result_ref` field with the exact closed
shape in §5. Protocol version, role, field presence, installed/current bundle
contents, or a coincidental schema definition never imply support.

A separate, independently reviewed and repository-owner-approved
**schema/bundle capability amendment** is a hard prerequisite to M1.2
persistence implementation. That prerequisite must add the exact
`review_contract` and `review_schema_variant` capability values to a new
retained bundle variant and add the matching closed run-schema definition for
`review_result_ref`; it is a separate commit/PR and is not part of this
contract-freeze commit. The M1.2 implementation must depend on that exact
approved capability amendment and must refuse to publish `review_result_ref`
under any older retained bundle whose run schema does not define it.

The current bundle and all older retained bundles remain byte-immutable. A
bundle without both exact capability values remains valid for the operations it
already supported but must fail closed for Stage 6.5 review persistence. No
schema or bundle bytes are changed by this proposal. During historical recovery,
`ReviewInvocation.retained_bundle` is the sole bundle-routing source. The
loader must not substitute the installed bundle or infer support from a newer
bundle.

## 5. Exact immutable paths and producer ownership

All paths below are repository-relative and operation-scoped where stated.
Every immutable write is atomic, durable, and no-replace.

| Artifact | Exact path | Sole producer |
| --- | --- | --- |
| Review scope | `.kapisch/v3/runs/<run_id>/review-inputs/scopes/<scope_digest>.json` | core/controller review-scope publisher |
| Request | `.kapisch/v3/runs/<run_id>/requests/<operation_id>.json` | existing Stage 4 request producer |
| Pre-dispatch fingerprint | `.kapisch/v3/runs/<run_id>/review-inputs/<operation_id>/pre-dispatch-fingerprint.json` | repository inspection/fingerprint producer |
| Reservation | `.kapisch/v3/runs/<run_id>/invocations/<operation_id>/planned.json` | existing Stage 4 reservation producer |
| Dispatch uncertainty | `.kapisch/v3/runs/<run_id>/invocations/<operation_id>/dispatch-uncertain.json` | existing Stage 4 uncertainty producer |
| Review invocation | `.kapisch/v3/runs/<run_id>/invocations/<operation_id>/review-invocation.json` | invocation publisher |
| Reviewer return | `.kapisch/v3/runs/<run_id>/invocations/<operation_id>/reviewer-return.json` | reviewer only; future dispatch unit |
| Host provenance | `.kapisch/v3/runs/<run_id>/invocations/<operation_id>/host-provenance-attestation.json` | host/adapter only; future dispatch unit |
| Review result | `.kapisch/v3/runs/<run_id>/invocations/<operation_id>/review-result.json` | result publisher; future result unit |

The last three paths are frozen for chain validation but are not produced by
M1.2. Their producers remain distinct: the controller cannot author reviewer
judgment or host provenance, and the host cannot rewrite reviewer evidence.
Storage is not a semantic producer merely because it retains bytes.

Mutable run state may contain only this repairable, non-authoritative exact
optional top-level field when a complete result chain exists:

```json
{
  "review_result_ref": {
    "path": ".kapisch/v3/runs/<run_id>/invocations/<operation_id>/review-result.json",
    "sha256": "<digest of exact review-result bytes>"
  }
}
```

`review_result_ref` is the sole accepted field name and has exactly the
`{path, sha256}` shape shown above. It is omitted rather than null when no
complete result chain exists. Its path must contain the same run and reserved
operation identity as the validated chain; aliases, another operation, a
caller-selected path, or a null value are invalid. The guarded backlink
publisher is its sole producer. It is not an approval, readiness, capability,
or lifecycle status.

## 6. Cross-record binding and publication order

The exact candidate `operation_id` in the canonical request must equal the
reserved operation ID byte-for-byte. The request, attempt, reservation,
scope, invocation, and result chain must agree on run identity, stage identity,
role, purpose, bundle capability, adapter binding, the existing Stage 4
assignment scope digest, the distinct review-scope digest, and all applicable
plan/fingerprint declarations.

The existing Stage 4 attempt `scope_digest` retains its existing meaning: it
binds the approved run/node assignment and remains equal to the Stage 4 request
packet's `scope_digest`. The `review-scope/1` digest is a distinct
`review_scope` locator in the review request profile and in
`ReviewInvocation.scope`; it must never replace or be compared as the Stage 4
assignment scope digest. For a node-scoped iteration, the review coverage must
be contained by the owned node scope while the two digests remain distinct.
For graph-free and milestone-final attempts, the existing Stage 4 assignment
rules remain authoritative and the review-scope coverage rules above apply in
addition.

The review request profile therefore has one exact additional review binding:
`review_scope`, an `ImmutableArtifactLocator` whose path is the retained
`review-scope/1` path and whose digest is its exact byte digest. It has no
second scope byte field. Existing Stage 4 `scope_digest` is preserved
unchanged. The invocation must bind `request.review_scope` exactly through its
`scope` locator.

The invocation must bind the exact retained bundle, request, attempt,
operation, review scope, base, head, included-untracked declaration, and
pre-dispatch fingerprint. The result must bind the exact invocation and
operation and retain the M0 reviewer-return, post-result, and host-provenance
relationships without rewriting them.

Publication order is strict and durable:

1. retain and validate the compatible bundle;
2. persist the planned reviewer attempt through existing Stage 4, producing and
   owning `stage_id` and preserving its existing assignment `scope_digest`;
3. publish the closed `review-scope/1` derived from that persisted attempt;
4. publish request inputs and the canonical review request, including the exact
   `review_scope` locator, through Stage 4;
5. capture and retain the factual pre-dispatch fingerprint;
6. reserve the exact candidate operation through Stage 4;
7. publish the existing dispatch-uncertain fact and its state observation;
8. publish `review-invocation.json` with all dependency digests validated;
9. after the complete immutable result chain exists, publish the guarded state
   backlink under the rules below.

No later step repairs an earlier missing producer, creates a second operation,
reuses a substituted candidate, or grants dispatch/authority permission.

## 7. Base/head contract and comparison-base prerequisite

`comparison_base` and `ReviewInvocation.base` are the same exact anchor. The
base must resolve to a commit in the observed object format and must be an
ancestor of or equal to the exact `head` anchor at invocation publication.
`ReviewInvocation.head` is the exact HEAD commit in the pre-dispatch
fingerprint; it is not resolved again after publication.

The comparison base is not a controller choice. It must be copied from an
existing immutable, durable producer that owns the branch/work-target base and
binds that base to the validated Stage 5 plan candidate and review target.
The current `PlanApprovalCandidate`, `ProposedScopeRef`, and Stage 4 attempt
records do not contain such a base binding. Therefore the **comparison-base
producer contract is an explicit prerequisite**: until a separate reviewed
contract identifies its immutable artifact, fields, producer, plan/target
binding, whole-branch-final rule, and cold-restart loader, M1.2 persistence
implementation must stop. The review-scope publisher must not invent that
producer, accept an arbitrary caller base, or treat syntax/ancestry alone as
proof of a whole-branch target.

That separate producer must reject `base == head` for a final whole-branch
review whenever the approved target requires an earlier comparison root; the
scope publisher may only validate and copy its exact decision. `head` remains
the exact pre-dispatch fingerprint HEAD. The reviewer, result, post-result,
and current-state validators preserve the already-required four-way fingerprint
equality and exact base/head bindings. They do not rebase to a later HEAD. A
new base or head after publication requires a new scope and new invocation.
Base/head are commit anchors only; the complete staged, tracked-worktree, and
included-untracked review state is the `RepositoryStateFingerprint`.

## 8. Guarded backlink and cold restart

The backlink publisher runs only under repository/run serialization and an
expected run revision. Before publishing it, the loader must validate the
complete immutable chain and prove exact equality for:

- run, stage, and reserved operation identity;
- compatible retained bundle and request bytes/digest;
- closed scope bytes/digest and exact plan-candidate reference;
- invocation base/head/purpose/included-untracked declarations;
- pre-dispatch fingerprint and required producer order;
- reviewer return, host provenance, post-result, and review-result bindings;
- every cited artifact's canonical bytes, digest, path root, and producer.

The append preserves the validated state/history prefix, increments the
expected revision exactly once, changes no authority fields or lifecycle
status, and is idempotent for the same exact backlink. It cannot publish a
backlink to a different operation or chain.

Cold restart behavior is closed:

| Persisted condition | Disposition |
| --- | --- |
| Exact valid backlink and exact complete chain | Load normally. |
| Missing backlink and one exact operation-bound complete chain | Repair the backlink only under serialization and expected revision. |
| Partial chain | Block. |
| Missing or digest-mismatched referenced artifact | Block. |
| Conflicting occupied identity | Block. |
| Backlink points to another chain | Block. |
| Unresolved `dispatch-uncertain` | Remain unresolved and block chain completion and backlink repair; never redispatch, obtain adapter capability, or reconcile. Stage 7 may later define separate read-only reconciliation for the exact retained operation. |
| Multiple or ambiguous candidate chains | Block; never select newest/closest records. |
| Controller memory is the only source for a missing fact | Block. |

Backlink repair never reruns a reviewer, creates an operation, creates
authority, recaptures a missing producer artifact, or converts factual evidence
into current eligibility.

Historical-chain validation is separate from current eligibility. Any current
authoritative use must independently establish and verify the live
writer-quiescence boundary and current repository state. A persisted prior
quiescence record cannot prove that the boundary remains active after restart.
M1.2 does not reconcile an unresolved operation or obtain adapter capability;
Stage 7 may later add read-only reconciliation under its own separately frozen
contract.

## 9. Refusal and compatibility matrix

M1.2 refuses structural closed-record or persistence loading for duplicate/
unknown/missing fields, noncanonical bytes, path traversal or aliases,
cross-run paths, wrong bundle capability, unsupported retained schema variant,
missing `review_result_ref` schema capability, missing scope producer, missing
comparison-base producer, changed plan candidate, incomplete milestone
coverage, invalid base or head anchors, non-ancestor base,
fingerprint-head mismatch, candidate/reserved operation mismatch,
request/reservation digest mismatch, wrong stage/role/adapter/assignment-scope/
review-scope/purpose binding, missing producer order, partial chain,
conflicting identity, ambiguous chain, stale expected revision, invalid
`review_result_ref`, unresolved `dispatch-uncertain`, or any attempt to infer
authority from persisted evidence.

Historical factual-chain loading and the permitted exact-backlink-only repair do
not require a live writer-quiescence boundary. Current authoritative use,
current eligibility, readiness, and approval claims must refuse when the live
writer-quiescence producer/contract is missing, unverifiable, lost, or
mismatched, or when current repository capture fails. This distinction is
mandatory: absence of live quiescence cannot make a valid historical factual
chain disappear, and historical loading cannot turn that chain into authority.

Existing Stage 4 unsupported-gate refusals and lifecycle validation remain
unchanged. M1.2 does not add a workflow status or reinterpret an existing one.
Stage 7.0 remains the sole owner of the task/milestone transition matrix.

## 10. Required verification before implementation

After this exact proposal is independently reviewed, repository-owner approval
must identify:

- this document's exact commit SHA;
- the bounded M1.2 scope in §1;
- that approval is not Stage 6.5 closure, writer-quiescence approval, or
  authority activation;
- that this exact commit explicitly approves the narrow factual-only amendment
  to the prior M0 §11 implementation gate described in §1;
- that any semantic edit requires a new review and approval;
- that the separately approved schema/bundle capability amendment and
  separately approved comparison-base producer contract are prerequisites to
  M1.2 implementation;
- that the separate writer-quiescence approval remains required for any current
  authority, readiness, approval, or eligibility claim.

Only after this proposal/amendment approval **and** both prerequisite approvals
may factual-only implementation begin. The implementation PR must remain docs/schema/bundle-
boundary compliant and must include fresh-process regressions for scope
closure, bundle compatibility, exact identities, publication crashes,
conflicting chains, backlink repair, unresolved uncertainty, and cold restart.
No implementation is authorized by this proposal's existence or by a runtime
`GateApprovalRecord`.

## 11. Explicit non-claims

This contract does not claim that the current retained bundle supports
`review-evidence/1`, that Stage 6.4 is accepted, that writer quiescence exists,
that Stage 6.5 is complete, or that any persisted invocation/result is current,
authoritative, approved, ready, or eligible. It freezes the exact proposal for
those decisions to be reviewed and approved later.
