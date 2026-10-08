# Stage 6.5 — Comparison-base producer contract

**Status: PROPOSED / DOCS-ONLY / PENDING INDEPENDENT REVIEW AND EXPLICIT
REPOSITORY-OWNER APPROVAL OF THIS EXACT COMMIT**

This document proposes the separately gated comparison-base producer required
by the approved M1.2 review-evidence persistence contract. It defines one
immutable factual producer and its loader; it does not implement the producer,
change retained schemas, or authorize M1.2 persistence, dispatch, authority,
readiness, approval, or eligibility behavior.

Approval, when recorded, applies only to this exact document revision and the
bounded producer contract below. Any semantic edit invalidates that approval
and requires a fresh independent review and owner approval tied to the new
commit SHA.

## 1. Purpose and prerequisite boundary

The M1.2 contract requires `comparison_base` to come from an existing
immutable producer that owns the branch/work-target base and binds it to the
validated Stage 5 plan candidate and review target. The current
`PlanApprovalCandidate`, `ProposedScopeRef`, and Stage 4 attempt records do not
carry that binding. This contract supplies the missing producer boundary only.

The producer exists so a later graph-free M1.2 publisher can copy one validated
base anchor without accepting a caller-selected revision. It does not make the
base current authority and does not prove writer quiescence. A later M1.2
publisher must still validate the exact pre-dispatch fingerprint and the
base/head relationship before publishing review evidence.

This contract intentionally covers only graph-free whole-branch review
targets. Milestone, approved-plan graph coverage, detached/synthetic targets,
and any checked-plan consumer remain outside scope.

## 2. Earlier durable review-target binding

The current `PlanApprovalCandidate`, proposed scope, and Stage 4 attempt do not
persist a branch target or review purpose. The comparison-base producer must
not fill that gap from a caller argument or ambient branch state. A separate,
earlier Stage 5 **review-target producer** is therefore a mandatory input to
this contract.

The Stage 5 review-target producer is the sole initial owner of the target
selection and comparison-root decision. Its target-selection input and policy
must come from a separately reviewed Stage 5 target-selection contract; this
document does not invent a caller API or treat the current candidate/attempt
schemas as if they already contained that input. If that producer or contract
is absent, M1.2 remains blocked.

The Stage 5 review-target producer first publishes one immutable,
content-addressed **review-target reservation** at:

```text
.kapisch/v3/authority/review-target-bindings/<binding_digest>.json
```

The planned Stage 4 attempt used by this contract must retain the exact
reservation locator in an attempt-owned closed `review_target_binding_ref`
field:

```json
{
  "path": ".kapisch/v3/authority/review-target-bindings/<binding_digest>.json",
  "sha256": "<binding_digest>"
}
```

The current Stage 4 attempt variant does not contain this field. Adding this
attempt-owned reference is a separately reviewed Stage 4 attempt-binding
contract; until it exists, this producer refuses and M1.2 remains blocked. The
approved Stage 5 `PlanApprovalCandidate` remains unchanged and retains its exact
governance-bound digest. The attempt-owned reference breaks the publication
cycle: the reservation binds the approved candidate, plan identity, target,
root, and expected artifact digests, while the attempt binds the exact
reservation bytes.

The reservation's closed payload is:

```json
{
  "protocol_version": 3,
  "review_target_binding_contract": "review-target-binding/1",
  "run_id": "<run identity>",
  "stage_id": "s-<32 lowercase hexadecimal stage ID>",
  "plan_candidate_ref": {
    "path": ".kapisch/v3/authority/plan-approval-candidates/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest>"
  },
  "plan_id": "<validated Stage 5 plan identity>",
  "target": {
    "kind": "whole-branch",
    "ref": "refs/heads/<canonical branch ref>"
  },
  "purpose": "iteration" | "final",
  "comparison_root": {
    "source": "stage5-target-binding",
    "anchor": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
    "must_differ_from_head": true | false
  },
  "comparison_base_ref": {
    "path": ".kapisch/v3/runs/<run_id>/review-inputs/comparison-bases/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest of the exact base artifact>"
  },
  "object_format": "sha1" | "sha256",
  "base": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
  "head": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
  "review_target_ref": {
    "path": ".kapisch/v3/authority/review-targets/<target_digest>.json",
    "sha256": "<target_digest>"
  }
}
```

The review-target producer publishes the reservation only after the validated
Stage 5 plan identity and reserved stage identity exist. It owns `target`,
`purpose`, `comparison_root`, base choice, and observed head; it refuses an
absent or ambiguous producer-owned target binding. It constructs the exact
target and base payloads, computes both content digests, and persists both
expected references before publishing either dependent artifact. The producer
must set `comparison_root.anchor` to the exact root from its durable Stage 5
target binding, require `base == comparison_root.anchor`, and refuse when the
anchor is absent, ambiguous, or not a commit in `object_format`.
`must_differ_from_head` is persisted rather than inferred, is always true for a
`final` target, and when true requires a strict ancestor. Equality is allowed
only when the producer-owned binding explicitly permits an empty iteration
comparison; ancestry alone never chooses a root. The established root is
immutable for one stage: retries within that same stage may reuse only the
exact same reservation, while every failed-attempt retry or corrective
follow-on with a new `stage_id` must allocate a fresh reservation even when the
root/target is unchanged. Any root, target, purpose, or observed-head change
also requires a new eligible `stage_id`, new reservation, new target/base
artifacts, and new review scope/invocation identities. The producer never
recomputes a root from a later HEAD, merge-base, or current branch.

After the approved candidate and planned attempt exist, the attempt-binding
producer retains the exact `review_target_binding_ref`; the target producer
then publishes the immutable, content-addressed target artifact at the
reservation's `review_target_ref`. Its exact closed payload is:

```json
{
  "protocol_version": 3,
  "review_target_contract": "review-target/1",
  "run_id": "<run identity>",
  "stage_id": "s-<32 lowercase hexadecimal stage ID>",
  "plan_candidate_ref": {
    "path": ".kapisch/v3/authority/plan-approval-candidates/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest>"
  },
  "plan_id": "<validated Stage 5 plan identity>",
  "target": {
    "kind": "whole-branch",
    "ref": "refs/heads/<canonical branch ref>"
  },
  "purpose": "iteration" | "final",
  "comparison_root": {
    "source": "stage5-target-binding",
    "anchor": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
    "must_differ_from_head": true | false
  },
  "comparison_base_ref": {
    "path": ".kapisch/v3/runs/<run_id>/review-inputs/comparison-bases/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest of the exact base artifact>"
  },
  "object_format": "sha1" | "sha256",
  "base": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
  "head": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>"
}
```

The comparison-base producer later publishes the exact base payload at the
reservation's `comparison_base_ref`.

The reservation and target artifacts are canonical UTF-8 JSON, atomically
durable, content-addressed where referenced, and no-replace. A second
reservation for the same candidate/stage, a target at a different digest, or
any conflicting producer identity is a refusal. Missing, changed,
unsupported, or caller-selected reservation or target bytes block the
comparison-base producer. The reservation is the explicit earlier durable
owner required by this contract; no fixed-path lookup, caller argument, or
ambient branch state can substitute for it.

## 3. Closed comparison-base artifact

The comparison-base producer may publish one canonical UTF-8 JSON artifact per
planned Stage 6.5 attempt only at the exact digest-addressed path reserved by
the review-target reservation:

```text
.kapisch/v3/runs/<run_id>/review-inputs/comparison-bases/<sha256>.json
```

The path and digest are not caller-selectable. Publication is atomic, durable,
and no-replace. A second artifact for the same expected digest is a conflict,
never a repair or overwrite. The producer must first load the review-target
reservation and its target artifact, then require the target's
`comparison_base_ref` to match the exact bytes it is about to publish.

The exact closed payload is:

```json
{
  "protocol_version": 3,
  "comparison_base_contract": "comparison-base/1",
  "run_id": "<run identity>",
  "stage_id": "s-<32 lowercase hexadecimal stage ID>",
  "plan_candidate_ref": {
    "path": ".kapisch/v3/authority/plan-approval-candidates/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest>"
  },
  "plan_id": "<validated Stage 5 plan identity>",
  "target": {
    "kind": "whole-branch",
    "ref": "refs/heads/<canonical branch ref>"
  },
  "purpose": "iteration" | "final",
  "comparison_root": {
    "source": "stage5-target-binding",
    "anchor": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
    "must_differ_from_head": true | false
  },
  "object_format": "sha1" | "sha256",
  "base": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
  "head": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>"
}
```

The object is closed: no aliases, extra fields, null values, abbreviated IDs,
ref names outside `refs/heads/`, ranges, symbolic revisions, or post-publication
recomputation are accepted. The `base` and `head` prefixes must equal
`object_format`. The `head` is the exact target HEAD observed by the
review-target producer and reserved in `comparison_base_ref`; it is not
resolved again by a later loader. The base artifact's `run_id`, `stage_id`, `plan_id`, `target`, `purpose`,
`comparison_root`, `object_format`, `base`, and `head` must equal the
corresponding fields in the earlier review-target reservation and target
artifact.

The producer must reject a target that is not a canonical branch ref, a target
whose observed object format is unavailable, or a base/head/root that cannot be
verified as commits in that format. `base` must equal
`comparison_root.anchor` and must be an ancestor of or equal to `head`. If
`comparison_root.must_differ_from_head` is true, `base` must be a strict
ancestor. It is always true for `purpose = "final"`; the producer must never
silently choose `head`, a recent ancestor, or an empty comparison when the
producer-owned root binding is missing or disagrees.

## 4. Producer ownership and bindings

The comparison-base producer is the sole byte producer of the base artifact;
the earlier review-target producer is the sole semantic owner of its target,
purpose, base choice, and expected digest. Storage only retains bytes and may
not synthesize, repair, or replace either artifact. The comparison-base
producer must derive every field from validated persisted inputs:

1. `run_id` and `stage_id` come from the existing durable Stage 4 planned
   attempt. The producer refuses an unowned, missing, or already-conflicting
   stage identity.
2. It loads the attempt-owned exact `review_target_binding_ref`, verifies the
   reservation's content-addressed path and SHA-256, and validates the
   reservation's canonical bytes and closed shape.
3. `plan_candidate_ref` and `plan_id` are the exact identities in the
   reservation. The producer loads and validates that approved candidate and
   retained bundle, verifies candidate/run/stage and exact plan identity/bytes,
   and refuses an installed/current-bundle substitution. It then loads the
   target artifact from the reservation's `review_target_ref`, verifies its
   content-addressed path and SHA-256, and validates its canonical bytes and
   closed shape before reading any base bytes.
4. `target` and `purpose` are copied from the reservation and target artifact.
   The comparison-base producer cannot accept or change a caller branch, work
   target, or purpose.
5. `comparison_root`, `object_format`, `base`, and `head` are copied from the
   exact target capture reserved by the review-target producer. The producer
   verifies `base == comparison_root.anchor`, applies the persisted
   `must_differ_from_head` rule, verifies ancestry, and verifies that the
   canonical base bytes hash to `comparison_base_ref.sha256` before
   publication.

The artifact is valid only when the candidate's retained bundle declares the
approved `review-evidence/1` and `review-invocation/1` capability. Older
bundles remain valid for their existing operations but cannot consume this
producer contract. The producer never amends the candidate, plan, target, purpose, reservation,
target artifact, or bundle after publication.

## 5. Publication order and consumer binding

The producer runs only after the planned Stage 4 attempt and its `stage_id`
are durably owned. Publication is strict:

1. The approved Stage 5 plan candidate and planned Stage 4 attempt own their
   exact immutable identities; the attempt owns `stage_id`.
2. The Stage 5 review-target producer validates that candidate and attempt,
   owns the whole-branch target, purpose, and comparison root, constructs the
   exact target and base payloads, computes all digests, and publishes the
   content-addressed review-target reservation containing the approved
   `plan_candidate_ref`.
3. The attempt-binding producer retains the reservation's exact locator in the
   attempt-owned `review_target_binding_ref` field.
4. The target producer publishes the exact content-addressed review-target
   bytes reserved by the reservation, including the expected
   `comparison_base_ref`.
5. The comparison-base producer loads and validates the reservation and target,
   then publishes the exact digest-addressed base bytes reserved by the target.
   No caller can choose a different path or digest.
6. Only after the reservation, attempt binding, target, and base artifacts are
   durable may the M1.2 review-scope publisher load the base fact.

The later graph-free review-scope publisher must:

- load the validated planned attempt and its exact attempt-owned
  `review_target_binding_ref`;
- verify the reservation's content-addressed path and SHA-256;
- load the target artifact from the reservation's `review_target_ref`;
- verify the target artifact's content-addressed path and SHA-256;
- load the exact comparison-base artifact at the target artifact's
  `comparison_base_ref.path`;
- verify the comparison-base bytes hash exactly to
  `comparison_base_ref.sha256`;
- validate all canonical bytes, closed shapes, plan identity, target, purpose,
  comparison root, object format, and commit anchors;
- require all artifacts' `run_id` and `stage_id` to equal the persisted
  attempt;
- require the reservation's `plan_candidate_ref` to equal the exact approved
  candidate and its `plan_id` to equal the candidate's exact plan identity;
- require the attempt-owned `review_target_binding_ref` to equal the
  reservation;
- require `base == comparison_root.anchor` and apply the persisted strictness
  rule;
- copy the target producer's exact `purpose` into `review-scope/1` rather than
  accepting a caller/request purpose; and
- copy only the base artifact's exact `base` anchor into `review-scope/1`,
  refusing missing, conflicting, stale, substituted, or digest-mismatched
  producer bytes.

The review-scope publisher must not compare the producer `head` with the
pre-dispatch fingerprint yet: the frozen M1.2 order captures that fingerprint
after scope publication. After the fingerprint exists, the invocation publisher must require producer
`head == fingerprint.head` before publishing the invocation. It must also
re-read the producer-owned `target.ref` (for example, the exact `refs/heads/...`
ref) and require that it still resolves to that same captured head; missing,
moved, or unrelated branch-ref state blocks invocation publication. The later
complete-chain validator must recheck producer head, invocation head,
fingerprint head, and named-target-ref equality. The request and invocation
purpose must equal the
scope's copied producer purpose byte-for-byte; the complete-chain validator
must recheck that equality and the final strict-root rule. The review-scope
publisher must not recompute a new base, ask Git for a newer base, infer a base
from ancestry, accept a request field as a replacement, or continue when any
producer artifact is absent. A changed target HEAD requires a new target
binding, new comparison-base artifact, new scope, and new invocation identity.

## 6. Cold restart and refusal rules

A cold loader reconstructs the producer fact from the validated planned
attempt's `review_target_binding_ref`, the reservation's
`plan_candidate_ref`/`review_target_ref`, the target's persisted
`comparison_base_ref`, the digest-addressed base path, and validated persisted
candidate/attempt records alone. It never relies on controller memory, ambient
branch state, the installed bundle, or caller honesty. The attempt-owned
reservation locator is verified first; its candidate/target locators and the
target artifact's expected digest-addressed base reference are authoritative
for locating the bytes.

The loader blocks on:

- missing, noncanonical, duplicate-key, unknown-field, or non-replaceable
  target or base bytes;
- a missing or conflicting attempt-owned `review_target_binding_ref` or
  review-target reservation;
- a reservation whose content-addressed path or SHA-256 does not match the
  attempt-owned locator;
- a target locator whose content-addressed path or SHA-256 does not match the
  reservation's `review_target_ref`;
- a target artifact whose run or stage identity does not match the reservation,
  artifact, or persisted attempt;
- a missing, changed, or unsupported retained plan candidate or bundle;
- a target ref that is not the producer-owned validated whole-branch target;
- a missing, unexpected, or digest-mismatched `comparison_base_ref`;
- a base artifact loaded from any path other than the exact expected path;
- base bytes whose SHA-256 differs from the expected digest, even when their
  ancestry is otherwise valid;
- a missing or mismatched `comparison_root`, a wrong object format, invalid
  anchor grammar, missing commit, non-ancestor base, or violated strictness
  rule;
- `purpose`, run, stage, approved-candidate, target, or root binding
  disagreement between the reservation, target, and base artifacts;
- a second target artifact for the same candidate/stage, a second base
  artifact for the expected digest, or any conflicting producer identity; or
- any attempt to repair either artifact from a later HEAD, current branch,
  controller memory, or a caller-selected revision.

The producer loader does not require the future pre-dispatch fingerprint;
that equality is a later invocation/complete-chain gate. Historical loading of
a valid producer fact is factual only. It does not establish a live
writer-quiescence boundary, current repository authority, approval, readiness,
or eligibility.

## 7. Compatibility and non-goals

This contract does not change the M1.2 `review-scope/1` vocabulary: that scope
continues to carry the exact `comparison_base` anchor, not a second caller-
selected field or an unbound artifact path. The validated target/base
artifacts are the sole durable source from which that anchor may be copied.

This contract does not implement or authorize:

- review-scope, request, reservation, uncertainty, invocation, result, or
  backlink publication;
- reviewer dispatch, host execution, result production, or reconciliation;
- milestone or approved-plan-backed review coverage;
- writer-quiescence enforcement or current-authority claims;
- new workflow statuses, lifecycle transitions, adapter APIs, or gate records;
- changes to retained schemas, bundle bytes, Stage 7 transition rules, or
  existing Stage 4 meanings.

## 8. Acceptance and approval gate

A future implementation may begin only after this exact contract is
independently reviewed and explicitly approved by the repository owner. The
approval must identify this document's exact commit SHA and confirm that:

1. the separately gated Stage 5 target-selection contract supplies the only
   producer input; the review-target producer is the sole semantic owner of the
   durable target, purpose, comparison root, base choice, and expected base
   digest;
2. the attempt-owned reservation locator binds the exact content-addressed
   target artifact bytes to the approved Stage 5 candidate and stage, and the
   target binds the exact base digest;
3. the comparison-base producer is the sole byte producer of the exact
   digest-addressed base artifact and cannot alter the earlier binding;
4. the attempt binding plus reservation, target, and base artifacts bind the
   exact Stage 4 attempt, Stage 5 plan candidate, whole-branch target, purpose,
   comparison root, object format, base, and observed head;
5. no caller-selected, ancestry-inferred, or recomputed base is accepted;
6. canonical bytes, no-replace publication, expected-digest verification,
   ancestry, persisted root strictness, immutable-root/new-stage replacement,
   and cold-restart refusal rules are enforced;
7. every new `stage_id` receives a new reservation, including retries and
   corrective follow-ons, and named-target-ref equality is revalidated before
   invocation;
8. pre-dispatch head equality is checked only after the fingerprint exists by
   the invocation/complete-chain validators, not prematurely by scope
   publication;
9. the contract is graph-free and does not authorize M1.2 persistence or
   authority behavior by itself; and
10. writer-quiescence, checked-plan consumer, and any current-authority
   approvals remain separate prerequisites.

Implementation verification must include fresh-process tests for canonical
shape, duplicate/unknown fields, reservation-to-target digest binding, exact
target/base path derivation, no-replace conflicts, reservation publication
before target publication and target publication before base publication,
retained-candidate and bundle binding, attempt-owned reservation binding,
expected base digest mismatch, comparison-root equality and strictness,
object-format anchors, ancestry, equal base/head final refusal, target-head
drift, fresh reservations for new stage IDs, named-target-ref revalidation,
pre-dispatch head validation at invocation time, missing producer bytes, cold
restart, and caller/base substitution refusal. A successful runtime
`GateApprovalRecord` is not governance approval for this contract.
