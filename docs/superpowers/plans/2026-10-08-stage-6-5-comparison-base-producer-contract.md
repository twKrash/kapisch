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

## 2. Closed producer artifact

The sole producer publishes one canonical UTF-8 JSON artifact per planned
Stage 6.5 attempt at this exact repository-relative path:

```text
.kapisch/v3/runs/<run_id>/review-inputs/comparison-bases/<stage_id>.json
```

The path is derived from the validated run and stage identities; callers cannot
select it. Publication is atomic, durable, and no-replace. A second artifact
for the same `<run_id>, <stage_id>` is a conflict, never a repair or overwrite.

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
`object_format`. The `head` is the exact target HEAD observed by this producer;
it is not resolved again by a later loader.

The producer must reject a target that is not a canonical branch ref, a target
whose observed object format is unavailable, or a base/head that cannot be
verified as commits in that format. `base` must be an ancestor of or equal to
`head`. For `purpose = "final"`, `base == head` is refused whenever the
validated review target requires an earlier comparison root; the producer must
not silently downgrade that target to an empty comparison.

## 3. Producer ownership and bindings

The comparison-base producer is the sole semantic producer of this artifact.
Storage only retains bytes and may not synthesize, repair, or replace it. The
producer must derive every field from validated persisted inputs:

1. `run_id` and `stage_id` come from the existing durable Stage 4 planned
   attempt. The producer refuses an unowned, missing, or already-conflicting
   stage identity.
2. `plan_candidate_ref` is the exact canonical reference supplied by the
   validated Stage 5 plan candidate. The producer loads that candidate and its
   retained bundle, verifies the candidate's run identity and exact plan bytes,
   and refuses an installed/current-bundle substitution.
3. `target` is the producer-owned whole-branch review target bound to that
   validated candidate and stage. The producer does not accept a caller's
   branch or work-target string as authority; if the validated Stage 5 target
   binding is absent, ambiguous, or differs from the producer's target, it
   refuses publication.
4. `purpose` is copied from the validated review target. It cannot be changed
   by a review-scope caller.
5. `object_format`, `base`, and `head` are copied from one observed target
   capture in that format. The producer verifies ancestry before publication and
   retains the exact observed values.

The artifact is valid only when the candidate's retained bundle declares the
approved `review-evidence/1` and `review-invocation/1` capability. Older
bundles remain valid for their existing operations but cannot consume this
producer contract. The producer never amends the candidate, plan, target, or
bundle after publication.

## 4. Publication order and consumer binding

The producer runs only after the planned Stage 4 attempt and its `stage_id`
are durably owned. Its publication precedes the M1.2 review-scope publisher.
The later graph-free review-scope publisher must:

- load the exact artifact from the canonical run/stage path;
- validate its canonical bytes, closed shape, candidate reference, target,
  purpose, object format, and commit anchors;
- require its `run_id` and `stage_id` to equal the persisted attempt;
- require its candidate reference to equal the validated current Stage 5
  candidate for that attempt;
- copy only the artifact's exact `base` anchor into `review-scope/1`;
- require the producer's `head` to equal the pre-dispatch fingerprint HEAD;
- require the invocation `head` and pre-dispatch fingerprint to retain that
  same exact head; and
- refuse missing, conflicting, stale, substituted, or digest-mismatched
  producer bytes.

The review-scope publisher must not recompute a new base, ask Git for a newer
base, infer a base from ancestry, accept a request field as a replacement, or
continue when the producer artifact is absent. A changed target HEAD requires
a new producer artifact, new scope, and new invocation identity.

## 5. Cold restart and refusal rules

A cold loader reconstructs the producer fact from the canonical path and
validated persisted candidate/attempt records alone. It never relies on
controller memory, ambient branch state, the installed bundle, or caller
honesty.

The loader blocks on:

- missing, noncanonical, duplicate-key, unknown-field, or non-replaceable
  producer bytes;
- a path whose run or stage identity does not match the artifact;
- a missing, changed, or unsupported retained plan candidate or bundle;
- a target ref that is not the producer-owned validated whole-branch target;
- a base/head anchor with the wrong object format, invalid grammar, missing
  commit, or non-ancestor base;
- a producer head that differs from the pre-dispatch fingerprint or invocation
  head;
- `purpose`, run, stage, candidate, or target binding disagreement;
- a second artifact for the same stage or conflicting producer identity; or
- any attempt to repair the artifact from a later HEAD, current branch,
  controller memory, or a caller-selected revision.

Historical loading of a valid producer fact is factual only. It does not
establish a live writer-quiescence boundary, current repository authority,
approval, readiness, or eligibility.

## 6. Compatibility and non-goals

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

## 7. Acceptance and approval gate

A future implementation may begin only after this exact contract is
independently reviewed and explicitly approved by the repository owner. The
approval must identify this document's exact commit SHA and confirm that:

1. the producer is the sole semantic owner of the immutable artifact;
2. the artifact binds the exact Stage 4 attempt, Stage 5 plan candidate,
   whole-branch target, purpose, object format, base, and observed head;
3. no caller-selected or recomputed base is accepted;
4. canonical bytes, no-replace publication, ancestry, target-head equality,
   and cold-restart refusal rules are enforced;
5. the contract is graph-free and does not authorize M1.2 persistence or
   authority behavior by itself; and
6. writer-quiescence, checked-plan consumer, and any current-authority
   approvals remain separate prerequisites.

Implementation verification must include fresh-process tests for canonical
shape, duplicate/unknown fields, exact path derivation, no-replace conflicts,
retained-candidate and bundle binding, object-format anchors, ancestry, equal
base/head final refusal, target-head drift, missing producer bytes, cold restart,
and caller/base substitution refusal. A successful runtime `GateApprovalRecord`
is not governance approval for this contract.
