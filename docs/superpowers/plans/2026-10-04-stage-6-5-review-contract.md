# Stage 6.5 M0 — Review/final format freeze

**Status: PROPOSED / PENDING INDEPENDENT APPROVAL**

This document freezes the proposed Stage 6.5 evidence vocabulary only. It is
not an implementation plan authorization and supplies no runtime behavior. It
is based on `origin/main` at `9cd506c` and the reviewed Stage 6.5 planner/reviewer
gate. This M0 artifact is documentation-only.

## 1. Scope and explicit non-goals

M0 defines the closed conceptual records and their producer/binding rules for
review and final evidence. It does not create `review.py`, `validation.py`,
writer enforcement, persistence code, schemas, bundles, adapters, host APIs,
or validation behavior. It does not amend retained schemas or retained bundle
bytes. M1/M2/M3 are not included.

No host writer-enforcement API, capability name, receipt shape, or storage
schema is invented here. The writer-quiescence requirement below is a future
authority prerequisite, not something supplied by Stage 6.4 or this document.

## 2. Frozen vocabulary and ownership

The following terms are exact field names. Fields are closed: an implementation
must reject unknown, missing, duplicated, or ambiguous fields rather than
silently infer them.

### 2.1 Locator and evidence records

`ImmutableArtifactLocator` is the common locator/evidence record:

```text
{path, sha256}
```

- `path` is a repository-contained relative path to one immutable retained
  artifact. It is not an absolute path, URL, host path, or caller-selected
  external reference.
- `sha256` is the lowercase SHA-256 digest of the exact artifact bytes at
  `path`.
- The artifact publisher is the sole producer of the artifact bytes and their
  digest. The record owner is the sole producer of the reference to that
  artifact. A consumer resolves `path`, recomputes the digest, and requires
  equality; equal strings without equal bytes are invalid.

`EvidenceLocator` uses the same exact fields and relationship. It denotes
retained evidence bytes rather than an authority decision. It is not a review
judgment and cannot make a gate eligible.

`ReviewInvocation` is the proposed closed record:

```text
{
  retained_bundle,
  request,
  attempt,
  operation,
  scope,
  base,
  head,
  purpose,
  included_untracked,
  pre_dispatch_fingerprint
}
```

`ReviewResult` is the proposed closed record:

```text
{
  invocation,
  request,
  target,
  scope,
  fingerprint,
  report,
  post_result,
  provenance
}
```

`ReviewInvocation` has no self-locator. Its identity is the existing qualified
Stage 4 tuple `{run_id, stage_id, operation_id}` from `attempt` and
`operation`; no record contains a locator to its own bytes. All artifact
locators point outward to immutable bytes whose contents do not refer back to
the owning invocation or result. The field vocabulary is deliberately distinct
from any retained schema. M0 freezes meaning and relationships; later
implementation must obtain approval before adding or changing wire fields.

### 2.2 ReviewInvocation fields

- `retained_bundle` is an `ImmutableArtifactLocator` for the exact retained
  CoreBundle bytes used by this operation. The Stage 4 bundle-retention
  producer owns the bytes and digest. The invocation publisher owns this
  reference and must not substitute the installed/current bundle.
- `request` is an `ImmutableArtifactLocator` for exact review request bytes.
  The controller/request producer owns request content and its digest; the
  invocation publisher owns the reference. Request bytes bind `attempt`,
  `operation`, `scope`, `base`, `head`, `purpose`, and fingerprint requirements,
  but never contain an invocation locator or result locator.
- `attempt` is the qualified Stage 4 attempt identity `{run_id, stage_id}`.
  Run creation is the sole producer of `run_id`; attempt creation references
  that `run_id` and is the sole producer of `stage_id`. `stage_id` retains its
  Stage 4 meaning: one stable stage-attempt identity; private `attempt_id` is
  not a wire field.
- `operation` is the qualified Stage 4 operation identity `{run_id,
  operation_id}`. Operation reservation is the sole producer of
  `operation_id`; it references the existing `run_id` and `stage_id`. The
  adapter may return a provider ID as factual provenance but never produces or
  replaces `operation_id`.
- `scope` is an `ImmutableArtifactLocator` for one exact closed scope
  representation. The scope producer owns those immutable bytes and digest;
  the invocation publisher owns the outward reference. Scope bytes contain no
  invocation/result locator. A scope is not inferred from a rendered diff or
  `head` alone.
- `base` and `head` are the exact revision identities selected for this review.
  The invocation producer owns the declared bindings; the repository observer
  owns only factual revision observations. A result must match both.
- `purpose` is exactly one literal: `iteration` or `final`. The controller is
  its sole producer; a result cannot relabel one as the other.
- `included_untracked` is the exact ordered set of repository-relative paths
  whose bytes are intentionally included in review evidence. The invocation
  producer owns the declaration. The repository observer owns factual
  path/content observations and rejects non-regular included entries under
  Stage 6. Unincluded relevant untracked paths remain an authority blocker.
- `pre_dispatch_fingerprint` is an `ImmutableArtifactLocator` for the exact
  canonical `RepositoryStateFingerprint` observed before dispatch. The
  repository-inspection/fingerprint producer owns factual fields and digest;
  the invocation publisher owns the outward reference. Fingerprint bytes
  contain no invocation/result locator, and a caller-supplied digest is not
  accepted.

### 2.3 ReviewResult fields

- `invocation` is an external `ImmutableArtifactLocator` for the one retained
  `ReviewInvocation`; the result publisher owns this outward reference. The
  referenced invocation is resolved by its qualified Stage 4 identities, not by
  a self-reference.
- `request` is the external request locator bound by the invocation. The result
  publisher owns the outward reference and must prove byte/digest equality with
  `ReviewInvocation.request`; request bytes do not refer back to this result.
- `target` is exactly:

  ```text
  {run_id, stage_id, operation_id, base, head}
  ```

  The invocation publisher owns the requested target; the result producer owns
  only factual returned binding. Every member must equal the corresponding
  invocation binding. There are no separate `ReviewResult.base` or
  `ReviewResult.head` fields.
- `scope` is the same external immutable scope locator bound by the invocation.
  The result publisher owns the outward reference and must prove byte/digest
  equality; it cannot narrow, widen, or reinterpret scope.
- `fingerprint` is an external immutable locator for the canonical fingerprint
  observed for the returned review result. The repository observer/fingerprint
  producer owns its factual fields and digest; the result publisher owns the
  outward reference. It is compared with `pre_dispatch_fingerprint` under the
  exact rules in §3.
- `report` is an external immutable locator for exact reviewer report bytes.
  The reviewer is the sole producer of judgment/report content. The controller
  may retain exact returned bytes and bind them, but may not author, rewrite,
  summarize, or upgrade the judgment. Report bytes do not refer to this result.
- `post_result` is an external immutable locator for the factual post-result
  observation. The repository observer owns its bytes and digest; the result
  publisher owns the outward reference. It is not a current-state claim.
- `provenance` is an external immutable locator for factual reviewer/invocation
  provenance. The host/adapter is the sole producer of those factual bytes;
  the controller may transport and retain them, but may not invent reviewer
  identity, context, execution, or independence. Provenance bytes do not refer
  to this result.

## 3. Repository fingerprint and containment relationships

`RepositoryStateFingerprint` is the Stage 6 semantic repository fact, not a
rendered diff. It binds the repository object-ID algorithm and HEAD identity;
stage-aware index entries; tracked worktree type/mode/content or deletion; and
untracked inventory, with exact byte digests only for paths listed in
`included_untracked`. Its canonical path encoding and ordering are those frozen
by Stage 6.4's approved repository contract.

Every artifact locator in either record must resolve beneath the containing
repository authority root. Containment is checked on the resolved path, with
symlink/path traversal escape refused. The locator's `sha256` is always the
SHA-256 of the exact bytes at that contained path. A fingerprint digest is the
SHA-256 of its canonical fingerprint bytes, not of a diff, index serialization,
stat cache, timestamp, or report formatting.

The required digest relationships are:

1. `ReviewInvocation.retained_bundle.sha256` equals the exact retained bundle
   bytes loaded for the invocation; an installed or newer bundle cannot satisfy
   it.
2. `ReviewInvocation.request.sha256` equals the exact request bytes and the
   request's embedded operation/attempt/scope bindings; request bytes contain
   no back-reference to the invocation or result.
3. `ReviewInvocation.scope` and `pre_dispatch_fingerprint` resolve to exact
   external immutable bytes and neither artifact refers back to the invocation.
4. `ReviewResult.invocation` resolves to the exact invocation bytes and digest;
   the invocation is found by its qualified Stage 4 identity, not a self-link.
5. `ReviewResult.request` equals `ReviewInvocation.request` byte-for-byte and
   digest-for-digest.
6. `ReviewResult.scope` and `target` equal the invocation's bindings; they are
   not independently caller-selected result metadata.
7. `ReviewResult.report`, `post_result`, `provenance`, and `fingerprint` each
   resolve to exact retained bytes, and each producer's digest is recomputed
   before use. None refers back to the owning result.
8. The canonical equality rules are: pre-dispatch and result fingerprints
   must be equal for an unchanged review target; post-result must equal the
   result fingerprint when the result observation is the same checkpoint;
   current is a newly captured fingerprint and must equal the accepted
   post-result fingerprint for authority eligibility. Any unequal canonical
   bytes/digests block. A permitted, explicitly scoped iteration delta must
   instead create a new invocation; it never relaxes equality on one result.
   The repository observer/fingerprint producer is sole producer of all four
   factual fingerprint artifacts; invocation/result publishers only bind
   external locators.

A missing, outside-root, unreadable, malformed, digest-mismatched, or
ambiguous locator is a refusal. No locator is repaired by selecting a nearby
file, newest file, current bundle, or controller memory.

## 4. Distinct final-stage operation and context

A final review is not a flag on an iteration review. It requires a new Stage 4
`stage_id`, a new Stage 4 `operation_id`, a new `ReviewInvocation`, and a new
`ReviewResult`. Its `purpose` is the closed final purpose, its target is the
whole required branch scope, and its `pre_dispatch_fingerprint`, post-result
fingerprint, current validation fingerprint, report, and provenance are fresh
bindings.

Final review also requires distinct reviewer context/provenance. Reusing a
reviewer thread, context, report, operation, or result from an iteration review
cannot satisfy the final record, even if the bytes are unchanged. Later
implementation or repository change invalidates prior final evidence; it does
not mutate or relabel the old record. A final result is evidence for a later
eligibility decision, not itself a readiness judgment produced by the
validator.

## 5. Publication ordering and immutable artifacts

The required future publication sequence is:

1. Retain the exact bundle, scope, request, and other cited immutable input
   artifacts.
2. Capture and retain the pre-dispatch fingerprint.
3. Reserve the exact Stage 4 operation with its request/attempt binding.
4. Publish the immutable Stage 4 `dispatch-uncertain` fact and durably publish
   the state pointer/ack that cites the reservation and uncertainty. This
   precedes review invocation publication and any adapter call.
5. Publish the immutable `ReviewInvocation` (which has no self-locator).
6. Dispatch only after all prior publications and authority checks succeed.
7. Retain the reviewer report, factual provenance, post-result observation,
   and result fingerprint as immutable external artifacts.
8. Publish the immutable `ReviewResult` binding the qualified invocation and
   exact request.
9. Independently capture the current fingerprint and evaluate structural
   validity and authority eligibility.

A crash before or after the adapter call has the same recovery treatment:
reconcile the original `operation_id` read-only, using the original request
and lookup context; never redispatch it. Missing, ambiguous, or mismatched
reconciliation leaves the operation blocked. A result cannot waive the
uncertainty ordering or create a replacement operation.

No artifact is overwritten. Atomic state/backlink updates may point at already
published immutable artifacts, but mutable state is never the sole copy of
invocation, report, result, provenance, or fingerprint authority. An orphan
artifact is safety-veto evidence: it may be reconciled only when all producer
and digest relationships are reconstructible; it never supplies missing state,
approval, or a result by itself.

## 6. Identity and acyclic dependency fixtures

These conceptual fixtures freeze producer ownership and dependency direction;
they are not runtime tests or schema files.

**Positive:** run creation produces `run_id=R1`; attempt creation references
`R1` and produces `stage_id=S1`; operation reservation references `(R1,S1)` and
produces `operation_id=O1`; the uncertain fact/state pointer references
`(R1,S1,O1)`; external request/scope/pre-fingerprint bytes are published
without back-references; then `ReviewInvocation` binds their locators and
`(R1,S1,O1)`. A result externally locates that invocation and the same request,
then binds an exact target and outward report/provenance/post/fingerprint
locators. This dependency graph is acyclic.

**Negative:** reject an invocation containing an `invocation` self-locator;
reject request, scope, fingerprint, report, post-result, or provenance bytes
that contain a locator back to their owning invocation/result; reject an
operation that manufactures a new `run_id`; reject an attempt that manufactures
or changes `run_id`; reject a result with separate `base`/`head` fields;
reject a result published before the uncertain state pointer; and reject any
retry/dispatch after an unresolved crash-before/after-call operation.

## 7. Refusal and compatibility rules

Cold or live validation refuses:

- an orphan invocation/result/locator, missing producer, missing referenced
  bytes, path escape, malformed record, or SHA-256 mismatch;
- a result whose invocation, request, target, scope, base/head, operation,
  attempt, or fingerprint binding differs from its invocation;
- tampered or replaced immutable bytes, including same-path/different-digest
  bytes;
- an uncertain, absent, or mismatched operation observation;
- a retained legacy bundle that does not explicitly support the Stage 6.5
  review/final contract; protocol version alone is not capability evidence;
- any unsupported Stage 5 gate or missing Stage 5 authority evidence; and
- any missing, unverifiable, lost, or mismatched writer-quiescence boundary.

Legacy bundles and retained schemas remain byte-immutable and are not upgraded,
rewritten, or interpreted as containing these fields. This M0 document creates
no compatibility path and no new retained schema.

## 8. Structural validity versus authority eligibility

**Structural validity** means that closed fields, types, containment, producer
order, identity relationships, exact retained bytes, canonical digests, and
cross-record bindings are present and consistent. Structural validity does not
prove that a reviewer was independent, that a report is causally adequate, or
that a branch is ready.

**Authority eligibility** is a separate later decision. It additionally
requires the applicable Stage 5 authority chain and supported gate contract,
current governing evidence, valid review purpose/scope, fresh final evidence
where required, and an independently verified writer-quiescence boundary held
through capture, validation, and authoritative publication. A structurally
valid result can therefore remain non-authoritative or findings-only.

Stage 5 gates not supported by their owning implementation remain blocked;
M0 does not authorize human approval, repository acceptance, plan approval,
side-effect permission, promotion, dispatch, or readiness. Reviewer findings
alone never become approval.

## 9. Cold-restart reconstruction

After restart, the validator reconstructs the operation from persisted
validated authority alone: discover the containing immutable artifacts, verify
all locators and digests, load the retained bundle named by the invocation,
resolve the Stage 4 `run_id`/`stage_id`/`operation_id` relationships, validate
producer order and immutable publication sequence, and independently recapture
current repository facts. It does not rely on controller memory, a caller
assertion, an unpersisted conversation, a mutable view, telemetry, or a prior
in-memory fingerprint.

A missing backlink may be repaired only from one exact, unambiguous immutable
chain. A missing or ambiguous chain blocks. A prior persisted claim that a
writer boundary existed is not proof that the boundary remains active after
restart; live enforcement must be established and independently verified again
by the future owner.

## 10. Writer-quiescence boundary — explicit future blocker

Stage 6.4 capture performs repeated observations and rejects races detected by
its checkpoints, but it is not an atomic filesystem snapshot and does not stop
writers. The existing advisory repository lock does not stop arbitrary
external writers. This M0 artifact supplies no writer lock, host capability,
API, schema, receipt, or enforcement mechanism.

Before any fingerprint is treated as current authority, a future Stage 6.5
implementation must define and independently verify an enforceable
writer-quiescence boundary bound to the repository and the specific
invocation/validation attempt. It must cover every relevant fingerprint input,
including shared Git metadata and effective ignore policy, and remain in force
through capture, validation, and publication of the authoritative transition.
Cold restart must establish or reconcile live enforcement; a persisted prior
boundary cannot substitute for it. Missing, unverifiable, lost, or mismatched
boundary evidence blocks authority.

This boundary is therefore an explicit future authority blocker, not a feature
of Stage 6.4 and not a capability of M0.

## 11. Stop / gate before M1

Do not begin M1 persistence implementation until all of the following are
independently approved and recorded:

1. The exact closed `ReviewInvocation` and `ReviewResult` field vocabulary and
   every sole producer/ownership mapping in this document.
2. The locator, containment, canonical-byte, SHA-256, and cross-record
   relationships, including orphan/tamper/legacy-bundle refusal.
3. Reuse of Stage 4 `stage_id` and `operation_id` meanings without a second
   wire identity or reinterpretation.
4. The distinct final operation and fresh whole-branch context requirement.
5. The publication ordering, immutable-artifact, and cold-restart rules.
6. The structural-validity versus authority-eligibility split and the explicit
   refusal of unsupported Stage 5 gates.
7. A separately reviewed owner and contract for writer-quiescence enforcement,
   including host coverage and restart behavior. M1 may not invent this owner
   while implementing persistence.

Until this gate is satisfied, this document remains **PROPOSED / PENDING
INDEPENDENT APPROVAL**, and no Stage 6.5 authority behavior is authorized.
