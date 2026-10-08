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

That producer owns one immutable target-binding artifact at this exact path:

```text
.kapisch/v3/runs/<run_id>/review-inputs/review-targets/<stage_id>.json
```

Its closed payload is:

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
  "target": {
    "kind": "whole-branch",
    "ref": "refs/heads/<canonical branch ref>"
  },
  "purpose": "iteration" | "final",
  "comparison_base_ref": {
    "path": ".kapisch/v3/runs/<run_id>/review-inputs/comparison-bases/<sha256>.json",
    "sha256": "<64 lowercase hexadecimal digest of the exact base artifact>"
  },
  "object_format": "sha1" | "sha256",
  "base": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>",
  "head": "sha1:<40 lowercase hexadecimal commit>" | "sha256:<64 lowercase hexadecimal commit>"
}
```

The review-target producer is the sole semantic owner of `target` and
`purpose`. It derives them from a producer-owned, durable Stage 5 target
binding and the exact validated candidate/stage; it refuses when that binding
is absent or ambiguous. It also constructs the exact comparison-base payload,
computes its digest, and persists this expected `comparison_base_ref` before
the comparison-base bytes are published. Thus the base artifact has an
expected digest after restart rather than only a fixed-path lookup. The
producer binds its candidate reference, run, and stage exactly; a caller cannot
replace any of them.

The target-binding artifact is canonical UTF-8 JSON, atomically durable, and
no-replace. A second artifact for the same run/stage is a conflict. Missing,
changed, unsupported, or conflicting target-binding bytes block the comparison-
base producer. This contract does not pretend that the current candidate
schema already carries this binding: until the separately reviewed Stage 5
review-target producer exists and publishes it, M1.2 remains blocked.

## 3. Closed comparison-base artifact

The comparison-base producer may publish one canonical UTF-8 JSON artifact per
planned Stage 6.5 attempt only at the exact digest-addressed path reserved by
the target-binding artifact:

```text
.kapisch/v3/runs/<run_id>/review-inputs/comparison-bases/<sha256>.json
```

The path and digest are not caller-selectable. Publication is atomic, durable,
and no-replace. A second artifact for the same expected digest is a conflict,
never a repair or overwrite. The producer must first load the target-binding
artifact and require its `comparison_base_ref` to match the exact bytes it is
about to publish.

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
  "target": {
    "kind": "whole-branch",
    "ref": "refs/heads/<canonical branch ref>"
  },
  "purpose": "iteration" | "final",
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
resolved again by a later loader. The base artifact's `run_id`, `stage_id`,
`plan_candidate_ref`, `target`, `purpose`, `object_format`, `base`, and `head`
must equal the corresponding fields in the earlier review-target artifact.

The producer must reject a target that is not a canonical branch ref, a target
whose observed object format is unavailable, or a base/head that cannot be
verified as commits in that format. `base` must be an ancestor of or equal to
`head`. For `purpose = "final"`, `base == head` is refused whenever the
validated review target requires an earlier comparison root; the producer must
not silently downgrade that target to an empty comparison.

## 4. Producer ownership and bindings

The comparison-base producer is the sole byte producer of the base artifact;
the earlier review-target producer is the sole semantic owner of its target,
purpose, base choice, and expected digest. Storage only retains bytes and may
not synthesize, repair, or replace either artifact. The comparison-base
producer must derive every field from validated persisted inputs:

1. `run_id` and `stage_id` come from the existing durable Stage 4 planned
   attempt. The producer refuses an unowned, missing, or already-conflicting
   stage identity.
2. It loads the exact review-target artifact from its canonical run/stage path
   and validates its canonical bytes and closed shape before reading any base
   bytes.
3. `plan_candidate_ref` is the exact reference in that artifact. The producer
   loads that candidate and its retained bundle, verifies the candidate's run
   identity and exact plan bytes, and refuses an installed/current-bundle
   substitution.
4. `target` and `purpose` are copied from the review-target artifact. The
   comparison-base producer cannot accept or change a caller branch, work
   target, or purpose.
5. `object_format`, `base`, and `head` are copied from the exact target capture
   reserved by the review-target producer. The producer verifies ancestry and
   that the canonical base bytes hash to `comparison_base_ref.sha256` before
   publication.

The artifact is valid only when the candidate's retained bundle declares the
approved `review-evidence/1` and `review-invocation/1` capability. Older
bundles remain valid for their existing operations but cannot consume this
producer contract. The producer never amends the candidate, plan, target,
purpose, target-binding artifact, or bundle after publication.

## 5. Publication order and consumer binding

The producer runs only after the planned Stage 4 attempt and its `stage_id`
are durably owned. Publication is strict:

1. The Stage 5 review-target producer validates the exact candidate and stage,
   owns the whole-branch target and purpose, constructs the exact base payload,
   computes its digest, and publishes the closed review-target artifact with
   that expected `comparison_base_ref`.
2. The comparison-base producer loads that review-target artifact, validates
   its canonical bytes, and publishes the exact digest-addressed base bytes
   reserved by it. No caller can choose a different path or digest.
3. Only after both producer artifacts are durable may the M1.2 review-scope
   publisher load the base fact.

The later graph-free review-scope publisher must:

- load the exact review-target artifact from its canonical run/stage path;
- load the exact comparison-base artifact at the target artifact's
  `comparison_base_ref.path`;
- verify the comparison-base bytes hash exactly to
  `comparison_base_ref.sha256`;
- validate both canonical bytes, closed shapes, candidate references, target,
  purpose, object format, and commit anchors;
- require both artifacts' `run_id` and `stage_id` to equal the persisted
  attempt;
- require both candidate references to equal the validated current Stage 5
  candidate for that attempt;
- copy only the base artifact's exact `base` anchor into `review-scope/1`;
- require the producer's `head` to equal the pre-dispatch fingerprint HEAD;
- require the invocation `head` and pre-dispatch fingerprint to retain that
  same exact head; and
- refuse missing, conflicting, stale, substituted, or digest-mismatched
  producer bytes.

The review-scope publisher must not recompute a new base, ask Git for a newer
base, infer a base from ancestry, accept a request field as a replacement, or
continue when either producer artifact is absent. A changed target HEAD
requires a new target binding, new comparison-base artifact, new scope, and
new invocation identity.

## 6. Cold restart and refusal rules

A cold loader reconstructs the producer fact from the canonical review-target
path, its persisted `comparison_base_ref`, the digest-addressed base path, and
validated persisted candidate/attempt records alone. It never relies on
controller memory, ambient branch state, the installed bundle, or caller
honesty. The target artifact is loaded first; its expected digest-addressed
base reference is authoritative for locating the base bytes.

The loader blocks on:

- missing, noncanonical, duplicate-key, unknown-field, or non-replaceable
  target or base bytes;
- a target path whose run or stage identity does not match the artifact;
- a missing, changed, or unsupported retained plan candidate or bundle;
- a target ref that is not the producer-owned validated whole-branch target;
- a missing, unexpected, or digest-mismatched `comparison_base_ref`;
- a base artifact loaded from any path other than the exact expected path;
- base bytes whose SHA-256 differs from the expected digest, even when their
  ancestry is otherwise valid;
- a base/head anchor with the wrong object format, invalid grammar, missing
  commit, or non-ancestor base;
- a producer head that differs from the pre-dispatch fingerprint or invocation
  head;
- `purpose`, run, stage, candidate, or target binding disagreement between the
  target and base artifacts;
- a second artifact for the same stage or conflicting producer identity; or
- any attempt to repair either artifact from a later HEAD, current branch,
  controller memory, or a caller-selected revision.

Historical loading of a valid producer fact is factual only. It does not
establish a live writer-quiescence boundary, current repository authority,
approval, readiness, or eligibility.

## 7. Compatibility and non-goals

This contract does not change the M1.2 `review-scope/1` vocabulary: that scope
continues to carry the exact `comparison_base` anchor, not a second caller-
selected field or an unbound artifact path. The producer artifact is the
sole durable source from which that anchor may be copied.

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

1. the earlier Stage 5 review-target producer is the sole semantic owner of
   the durable target, purpose, base choice, and expected base digest;
2. the comparison-base producer is the sole byte producer of the exact
   digest-addressed base artifact and cannot alter the earlier binding;
3. the two artifacts bind the exact Stage 4 attempt, Stage 5 plan candidate,
   whole-branch target, purpose, object format, base, and observed head;
4. no caller-selected or recomputed base is accepted;
5. canonical bytes, no-replace publication, expected-digest verification,
   ancestry, target-head equality, and cold-restart refusal rules are enforced;
6. the contract is graph-free and does not authorize M1.2 persistence or
   authority behavior by itself; and
7. writer-quiescence, checked-plan consumer, and any current-authority
   approvals remain separate prerequisites.

Implementation verification must include fresh-process tests for canonical
shape, duplicate/unknown fields, exact target/base path derivation,
no-replace conflicts, target-binding publication before base publication,
retained-candidate and bundle binding, expected base digest mismatch,
object-format anchors, ancestry, equal base/head final refusal, target-head
drift, missing producer bytes, cold restart, and caller/base substitution
refusal. A successful runtime `GateApprovalRecord` is not governance approval
for this contract.
