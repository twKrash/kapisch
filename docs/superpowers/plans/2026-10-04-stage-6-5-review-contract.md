# Stage 6.5 M0 — Review/final format freeze

**Status: M1.1 FORMAT/MODEL UNIT REPORTED; CAPABILITY AMENDMENT PENDING OWNER APPROVAL; M1.2+ PENDING**

This document preserves the documentation-only M0 format-freeze history. No
retained, verifiable owner approval source currently binds the exact capability
amendment head. This PR therefore contains two separately bounded,
non-authoritative units: the M1.1 format/model increment and the schema/bundle
capability amendment defined in §10.1. Neither supplies persistence, dispatch,
writer-enforcement, authority-eligibility, or host-API authority. M1.2 and later
remain pending independent approval.

### Approval disposition (bounded M1.1 and capability amendment)

The exact Stage 6.5 M1.1 format/model unit and the separately gated capability
amendment in §10.1 are reviewable increments, not a stage closure. Independent
read-only review of the complete capability delta found no P0–P2 findings;
owner approval must still bind the exact final commit before merge. Do not infer
approval for M1.2 persistence or any later authority behavior; those remain
pending and gated below.

## 1. Scope and explicit non-goals

M0 defines the closed conceptual records and their producer/binding rules for
review and final evidence. The historical M0 artifact was documentation-only; this PR contains a bounded,
non-authoritative M1.1 format/model implementation and the separately gated
§10.1 capability amendment, both pending their stated approval gates. This does
not authorize writer enforcement, persistence, dispatch, authority eligibility,
adapters, or host APIs. The capability amendment in
§10.1 may add one new retained bundle variant while preserving all historical
bundle bytes; it does not broaden runtime authority. M1.2/M2/M3 are not
included.

No host writer-enforcement API, receipt shape, or storage schema is invented
here. The writer-quiescence requirement below is a future
authority prerequisite, not something supplied by Stage 6.4 or this document.

The separately gated schema/bundle capability amendment in §10.1 is limited to
retained format recognition and validation. It introduces no runtime producer or
authority transition.

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

`ReviewerReturn` is the proposed immutable reviewer-owned return artifact:

```text
{
  invocation,
  operation,
  request,
  target,
  fingerprint,
  report,
  report_digest,
  decision
}
```

`HostProvenanceAttestation` is the proposed immutable host/adapter-owned
attestation envelope:

```text
{
  reviewer_return,
  reviewer_return_digest,
  execution_identity,
  execution_context,
  dispatch_facts
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
  reviewer_return,
  post_result,
  provenance
}
```

`reviewer_return` and `provenance` are distinct closed locators: the former
locates the reviewer-owned judgment artifact and the latter locates the
host-owned attestation envelope. Neither is an alias for the other.

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
  invocation publisher owns the reference. Request bytes bind the existing
  `attempt` and exact adapter/lookup/request inputs, plus `scope`, `base`,
  `head`, `purpose`, and fingerprint requirements. They are published before
  operation reservation and contain the controller-proposed candidate
  `operation_id` required by Stage 4 §4.0.2. That candidate is not durable
  operation authority until reservation, but it is the operation identity
  candidate that reservation must compare byte-for-byte with the reserved
  `operation_id`; this is not a second field or a new frozen identity. Request
  bytes never contain an invocation locator or result locator.
- `attempt` is the qualified Stage 4 attempt identity `{run_id, stage_id}`.
  Run creation is the sole producer of `run_id`; attempt creation references
  that `run_id` and is the sole producer of `stage_id`. `stage_id` retains its
  Stage 4 meaning: one stable stage-attempt identity; private `attempt_id` is
  not a wire field.
- `operation` is the final qualified Stage 4 operation locator/identity
  `{run_id, operation_id}` carried by the retained operation reservation.
  Operation reservation is the sole producer of durable `operation_id` ownership;
  it atomically binds that ID to the already-published request digest, existing `run_id` and
  `stage_id`, and selected adapter binding. The adapter may return a provider
  ID as factual provenance but never produces or replaces `operation_id`.
  `ReviewInvocation` is published only after this reservation and therefore
  contains both the request locator and the final operation locator; it never
  publishes a proposed token as operation authority.
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
- `included_untracked` is the exact ordered set of canonical lowercase-hex
  encodings of raw Git path bytes, using the existing Stage 6
  `_repository_encoding.encode_git_path` contract, whose bytes are intentionally
  included in review evidence. The invocation producer owns the declaration.
  The repository observer owns factual path/content observations and rejects
  non-regular included entries under Stage 6. Unincluded relevant untracked
  paths remain an authority blocker.
- `pre_dispatch_fingerprint` is an `ImmutableArtifactLocator` for the exact
  canonical `RepositoryStateFingerprint` observed before dispatch. The
  repository-inspection/fingerprint producer owns factual fields and digest;
  the invocation publisher owns the outward reference. Fingerprint bytes
  contain no invocation/result locator, and a caller-supplied digest is not
  accepted.

### 2.3 ReviewerReturn and HostProvenanceAttestation fields

- `ReviewerReturn` is the immutable reviewer-return artifact. The reviewer is
  the sole producer of every assertion field in it: the exact causal
  `invocation`, final qualified `operation`, `request`, `target`, and
  reviewer-returned `fingerprint` bindings; exact `report` bytes and
  `report_digest`; and the reviewer-owned `decision`. The operation binding
  references the already reserved operation; it does not produce
  `operation_id`. No controller or host/adapter may author, rewrite,
  summarize, upgrade, or substitute any of these fields.
- `report` is an external immutable locator for the exact reviewer report
  bytes. `report_digest` is the reviewer-returned SHA-256 digest of those exact
  bytes and must equal `report.sha256`.
- `decision` is exactly one reviewer-owned literal: `clear`, `findings`, or
  `inconclusive`. These are review outcomes, not approval or readiness.
- `HostProvenanceAttestation` is a separate immutable host/adapter-owned
  envelope. The host/adapter is the sole producer of factual
  `execution_identity`, `execution_context`, and `dispatch_facts`. It must
  reference the exact `reviewer_return` locator and its
  `reviewer_return_digest`; it does not author, rewrite, interpret, or
  duplicate the reviewer return or judgment.

### 2.4 ReviewResult fields

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
  only factual returned binding. Its `operation_id` is the final operation ID
  from the retained reservation, never the controller's pre-reservation
  candidate. Every member must equal the corresponding invocation binding.
  There are no separate `ReviewResult.base` or `ReviewResult.head` fields.
- `scope` is the same external immutable scope locator bound by the invocation.
  The result publisher owns the outward reference and must prove byte/digest
  equality; it cannot narrow, widen, or reinterpret scope.
- `fingerprint` is an external immutable locator for the canonical fingerprint
  observed for the returned review result. The repository observer/fingerprint
  producer owns its factual fields and digest; the result publisher owns the
  outward reference. It is compared with `pre_dispatch_fingerprint` under the
  exact rules in §3.
- `reviewer_return` is an external immutable locator for the exact
  reviewer-owned `ReviewerReturn` artifact. Its digest is checked against the
  exact artifact bytes. The result publisher may retain and bind the returned
  locator, but does not produce or duplicate any reviewer-return field.
- `post_result` is an external immutable locator for the factual post-result
  observation. The repository observer owns its bytes and digest; the result
  publisher owns the outward reference. It is not a current-state claim.
- `provenance` is an external immutable locator for the exact
  `HostProvenanceAttestation` envelope. Its envelope must reference the exact
  `reviewer_return` locator and digest; it contains only factual host/adapter
  execution identity, context, and dispatch facts. It does not author, rewrite,
  interpret, or duplicate the reviewer judgment. This is a proposed evidence
  relationship, not a runtime host API or schema.

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
2. `ReviewInvocation.request.sha256` equals the exact request bytes. Those
   bytes bind the existing attempt and exact adapter/lookup/request inputs,
   and contain the controller-proposed candidate `operation_id` required by
   Stage 4 §4.0.2. The candidate is not durable authority until reservation,
   but reservation must compare it byte-for-byte with the reserved
   `operation_id`; absent or substituted candidates are refused. Request bytes
   contain no back-reference to the invocation or result.
3. The reserved operation's immutable binding is the sole producer of durable
   `operation_id` ownership and must bind the exact `ReviewInvocation.request`
   digest, `run_id`, `stage_id`, adapter binding, and candidate `operation_id`.
   The candidate and reserved operation ID must be byte-for-byte equal. The
   invocation's `operation` must resolve to that exact final reservation/
   operation locator; a request-only or mismatched proposed-token reference
   cannot satisfy it.
4. `ReviewInvocation.scope` and `pre_dispatch_fingerprint` resolve to exact
   external immutable bytes and neither artifact refers back to the invocation.
5. `ReviewResult.invocation` resolves to the exact invocation bytes and digest;
   the invocation is found by its qualified Stage 4 identity, not a self-link.
6. `ReviewResult.request` equals `ReviewInvocation.request` byte-for-byte and
   digest-for-digest, while its later `ReviewerReturn` and `ReviewResult`
   bindings must also resolve to the final reserved operation identity.
7. `ReviewResult.scope` and `target` equal the invocation's bindings; they are
   not independently caller-selected result metadata.
8. `ReviewResult.reviewer_return`, `post_result`, `provenance`, and
   `fingerprint` each resolve to exact retained bytes, and each producer's
   digest is recomputed before use. None refers back to the owning result.
9. The authoritative equality rule is one four-way equality, over canonical
   fingerprint bytes (and their recomputed digests):
   `pre_dispatch_fingerprint == ReviewResult.fingerprint ==
   post_result == independently_captured_current_fingerprint`. All four
   checkpoints must be present, unambiguous, independently resolved, and
   canonically equal. Any mismatch, missing checkpoint, unreadable artifact,
   or ambiguity blocks authority. In particular, `post_result` cannot silently
   become the accepted baseline after reviewer mutation: the independent
   current capture is still required and must equal the pre-dispatch and
   reviewer-returned fingerprints. A permitted, explicitly scoped iteration
   delta must instead create a new invocation; it never relaxes equality on
   one result. The repository observer/fingerprint producer is sole producer
   of all four factual fingerprint artifacts; invocation/result publishers
   only bind external locators.
10. The reviewer-return artifact must bind one exact `invocation`, final
   qualified `operation`, `request`, `target`, and reviewer-returned `fingerprint` to
   exactly one `decision`, `report`, and `report_digest`. The result's
   `reviewer_return.sha256` and the attestation's `reviewer_return_digest` must
   both equal the SHA-256 of those exact reviewer-return bytes; the reviewer
   return's fingerprint must equal `ReviewResult.fingerprint`. Each binding is
   checked against the retained immutable artifacts and the result's canonical
   bytes. The host/adapter attestation must reference the exact
   `reviewer_return` digest and must contain only its factual execution
   identity, context, and dispatch facts. The controller cannot author,
   replace, upgrade, or duplicate either artifact, or derive a different
   decision from the report. A mismatch, unknown decision, missing reviewer
   return, missing host attestation, conflicting producer claim, or missing
   reviewer-return digest binding blocks authority.

A missing, outside-root, unreadable, malformed, digest-mismatched, or
ambiguous locator is a refusal. No locator is repaired by selecting a nearby
file, newest file, current bundle, or controller memory.

## 4. Distinct final-stage operation and context

A final review is not a flag on an iteration review. It requires a new Stage 4
`stage_id`, a new Stage 4 `operation_id`, a new `ReviewInvocation`, and a new
`ReviewResult`. Its `purpose` is the closed final purpose, its target is the
whole required branch scope, and its `pre_dispatch_fingerprint`, post-result
fingerprint, current validation fingerprint, reviewer return, and host
attestation are fresh bindings.

Final review also requires distinct reviewer context and host attestation.
Reusing a reviewer thread, context, reviewer return, operation, or result
from an iteration review cannot satisfy the final record, even if the bytes are unchanged. Later
implementation or repository change invalidates prior final evidence; it does
not mutate or relabel the old record. A final result is evidence for a later
eligibility decision, not itself a readiness judgment produced by the
validator.

## 5. Publication ordering and immutable artifacts

The required future publication sequence is:

1. Retain the exact bundle, scope, request, and other cited immutable input
   artifacts. Request/evidence publication binds the existing attempt and
   exact adapter/lookup/request inputs and contains the Stage 4
   controller-proposed candidate `operation_id`; it is not durable authority.
2. Capture and retain the pre-dispatch fingerprint.
3. Atomically reserve the exact Stage 4 operation. Operation reservation is
   the sole producer of durable `operation_id` ownership and binds it to the
   already-published request digest, `run_id`/`stage_id`, adapter binding, and
   candidate `operation_id`; the candidate and reserved ID must match
   byte-for-byte. An absent or substituted candidate blocks reservation.
4. Publish the immutable Stage 4 `dispatch-uncertain` fact and durably publish
   the state pointer/ack that cites the reservation and uncertainty. This
   precedes review invocation publication and any adapter call.
5. Publish the immutable `ReviewInvocation` (which has no self-locator),
   containing the already-published request locator and final operation
   locator/identity.
6. Dispatch only after all prior publications and authority checks succeed.
7. Durably retain the exact report bytes and the observer-produced fingerprint
   artifact cited by the reviewer return, including their exact digests.
8. Publish the immutable `ReviewerReturn` whose `invocation` points to the
   already retained exact `ReviewInvocation` and whose report/fingerprint
   locators resolve to those already retained artifacts.
9. Publish the immutable `HostProvenanceAttestation` referencing the exact
   published `ReviewerReturn` locator and digest.
10. Durably retain the post-result observation and independently captured
    current fingerprint artifacts, including their exact digests.
11. Publish the immutable `ReviewResult` referencing only already-published
    invocation, reviewer-return, host-attestation, post-result, fingerprint,
    and request dependencies.
12. Evaluate structural validity and authority eligibility, preserving the
    four-way fingerprint equality rule.

A crash before or after the adapter call has the same recovery treatment:
reconcile the original reserved `operation_id` read-only, using the original
request and lookup context; never redispatch it. The pre-reservation candidate
is carried in that original request/packet and must be present and byte-for-byte
identical to the reserved ID; it is not durable authority until reservation.
An absent, substituted, missing, ambiguous, or mismatched candidate or
reconciliation leaves the operation blocked. A crash between any publication
steps likewise leaves the operation blocked until the already-retained
producer artifacts and already-published dependency chain are reconstructed;
missing report/fingerprint retention, a host attestation before its reviewer
return, or a result before all cited dependencies is a refusal. A result cannot
waive the uncertainty ordering or create a replacement operation.

No artifact is overwritten. Atomic state/backlink updates may point at already
published immutable artifacts, but mutable state is never the sole copy of
invocation, reviewer return, host attestation, result, or fingerprint authority.
An orphan
artifact is safety-veto evidence: it may be reconciled only when all producer
and digest relationships are reconstructible; it never supplies missing state,
approval, or a result by itself.

## 6. Identity and acyclic dependency fixtures

These conceptual fixtures freeze producer ownership and dependency direction;
they are not runtime tests or schema files.

**Positive:** run creation produces `run_id=R1`; attempt creation references
`R1` and produces `stage_id=S1`; external request/scope/pre-fingerprint bytes
are published first, with the request binding `(R1,S1)` and exact
adapter/lookup/request inputs and the Stage 4 controller-proposed candidate
`operation_id=O1` (not yet durable authority); operation reservation then
sole-produces durable ownership of `operation_id=O1` and atomically binds it to
the request digest, `(R1,S1)`, adapter binding, and candidate `O1`, requiring
byte-for-byte equality; the uncertain fact/state pointer references `(R1,S1,O1)`;
then `ReviewInvocation` binds both the request locator and final operation
locator/identity `(R1,S1,O1)`. The exact report bytes and the observer-produced fingerprint artifact cited
by the reviewer return are durably retained first. The reviewer then publishes
a `ReviewerReturn` whose `invocation` points to that earlier exact
`ReviewInvocation` locator and which binds the exact operation, request, target,
fingerprint, decision, report, and report digest. The host/adapter then publishes
a separate `HostProvenanceAttestation` referencing that exact reviewer-return
digest. Post-result observation and independently captured current fingerprint
artifacts are retained next; a result then externally locates the already
published invocation, reviewer return, host attestation, and same request, and
binds the target and outward post/fingerprint locators. This dependency graph
is acyclic and producer-before-consumer.

**Negative:** reject request bytes with an absent candidate `operation_id`, a
candidate substituted from the Stage 4 request/packet, or a candidate treated as
final durable authority before reservation. Reject an operation reservation
whose reserved `operation_id` does not equal the candidate byte-for-byte, whose
request digest, run/stage binding, or adapter binding differs, or that is not
the sole producer of durable final ID ownership. Reject an invocation published
before the reservation or one whose request/operation bindings do not resolve
to the same retained request digest and final operation reservation. Permit the required `ReviewerReturn.invocation`
link to the earlier exact `ReviewInvocation` locator. Reject only a self-link from a
`ReviewerReturn` to itself, any link from a `ReviewerReturn` to the later
`ReviewResult`, or any dependency cycle. Also reject request, scope,
fingerprint, report, post-result, or host-attestation bytes that contain a
locator back to their owning invocation/result; reject an operation that
manufactures a new `run_id`; reject an attempt that manufactures or changes
`run_id`; reject a result with separate `base`/`head` fields; reject a result
published before the uncertain state pointer or before its cited immutable
dependencies; and reject any retry/dispatch after an unresolved crash-before/
after-call operation. Reject missing host attestation, missing reviewer return,
a host attestation that does not reference the exact reviewer-return digest,
conflicting producer claims, or any controller-authored reviewer field.

**Fingerprint positive:** accept authority only when the pre-dispatch,
reviewer-returned/result, post-result, and independently captured current
canonical fingerprints are all present and equal.

**Fingerprint negative:** after a reviewer mutates the repository, reject a
result even when its post-result fingerprint is internally consistent; the
new independent current fingerprint differs from the pre-dispatch and
reviewer-returned fingerprints, so `post_result` cannot become the baseline.
Also reject any missing or ambiguous one of the four checkpoints.

**Crash/ordering positive:** after a crash at any publication boundary,
restart can reconstruct the chain from the retained invocation, exact report
and reviewer-returned fingerprint artifacts, published reviewer return,
published host attestation, and retained post-result/current artifacts before
publishing the result. Each consumer is published only after its cited
producer is durable.

**Crash/ordering negative:** refuse a chain that publishes `ReviewerReturn`
before its exact report bytes or reviewer-returned fingerprint artifact is
retained, publishes host attestation before the reviewer return, or publishes
`ReviewResult` before the post-result/current artifacts or any other cited
dependency. Refuse a restart that relies on an unpersisted publication, a
mutable pointer as the sole artifact, controller memory, or a redispatch after
an unresolved dispatch uncertainty.

**Decision/provenance positive:** accept a structurally eligible return when
an immutable reviewer return binds the exact invocation, final operation,
request, target, and reviewer-returned fingerprint to `decision=clear` (or exactly
`findings`/`inconclusive`) and a `report_digest` equal to the retained report
bytes, and an immutable host attestation references that exact reviewer-return
digest with factual execution identity/context/dispatch facts. The controller
only transports these artifacts.

**Decision/provenance negative:** block authority when the decision is `approve`,
unknown, or controller-authored; when the report digest differs from
`report.sha256`; when any reviewer-return binding is absent or mismatched; when
host attestation is absent or references a different reviewer-return digest; or
when host and reviewer claims conflict. A controller substitution or host
attestation that duplicates or rewrites reviewer judgment also blocks.

## 7. Refusal and compatibility rules

Cold or live validation refuses:

- an orphan invocation/result/locator, missing producer, missing referenced
  bytes, path escape, malformed record, or SHA-256 mismatch;
- a result whose invocation, request, target, scope, base/head, operation,
  attempt, or fingerprint binding differs from its invocation;
- a result lacking the four-way pre-dispatch/result/post-result/current
  canonical fingerprint equality, or relying on `post_result` as a replacement
  baseline after mutation;
- an unknown or controller-authored reviewer decision, a missing reviewer
  return, a missing host attestation, conflicting producer claims, a host
  attestation referencing the wrong reviewer-return digest, or a
  `report_digest` that does not equal the exact retained report bytes;
- tampered or replaced immutable bytes, including same-path/different-digest
  bytes;
- request bytes with an absent or substituted Stage 4 candidate `operation_id`,
  a candidate treated as durable final authority before reservation, an
  invocation published before operation reservation, or a final operation
  reservation whose candidate and reserved `operation_id` differ byte-for-byte,
  or whose request digest, run/stage binding, adapter binding, or operation
  locator does not match;
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
cross-record bindings are present and consistent. It requires both the
reviewer-owned return and the host-owned attestation, with the attestation
referencing the exact reviewer-return digest and neither producer claiming the
other's fields. Structural validity does not prove that a reviewer was
independent, that a report is causally adequate, or that a branch is ready.

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
both reviewer-return and host-attestation producer order and their exact digest
relationship, validate immutable publication sequence, and independently recapture
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

## 10.1 Schema/bundle capability amendment — separately gated prerequisite

This bounded amendment is included in the implementation PR as a prerequisite
for, but not as, M1.2 persistence. It authorizes only the following exact
retained-format changes:

1. Add the exact CoreBundle capability values
   `review_contract = "review-evidence/1"` and
   `review_schema_variant = "review-invocation/1"`.
2. Add the optional top-level `review_result_ref` run-schema field with the
   closed operation-keyed `{path, sha256}` shape, exact operation/path binding,
   lowercase SHA-256 validation, and no aliases.
3. Preserve historical Stage 5.4/5.5 identity variants and reject partial,
   weakened, malformed, or unsupported capability declarations.
4. Refresh only the canonical generated bundle copies and conformance fixtures;
   older retained bundle bytes remain valid and unchanged.
5. Keep capability recognition fail-closed and introduce no persistence,
   dispatch, reconciliation, writer-enforcement, readiness, eligibility, or
   authority producer.

Acceptance requires canonical-byte and digest verification, historical-bundle
compatibility tests, negative tests for partial/weakened schemas and malformed
patterns, frozen-schema validator coverage (including boolean schemas, boolean
`$ref` targets, `anyOf`, overlapping `patternProperties`, and tuple-valued
type arrays), generated-copy equality, and an independent read-only review.
The independent review is complete with no remaining P0–P2 findings. Owner
approval remains pending and must identify this exact amendment commit SHA;
semantic changes require a fresh review and fresh owner approval.

## 11. Stop / gate before M1.2+

M1.1 format/model implementation is the exact bounded unit reported above,
not a stage closure or verified approval. Do not begin M1.2 persistence or any
authority behavior until all of the following remain independently approved
and recorded:

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
7. The required Stage-5 prerequisites and gates, including any retained
   lifecycle prerequisites that must precede Stage 6.5.
8. A separately reviewed owner and contract for writer-quiescence enforcement,
   including host coverage and restart behavior. No M1.2 implementation may
   invent this owner or an enforcement API.
9. Persistence, dispatch, and authority-eligibility contracts, each with their
   own reviewed producer ownership and cold-restart behavior.
10. The exact §10.1 schema/bundle capability amendment is independently
    reviewed and owner-approved with approval bound to its exact commit SHA.

Until this gate is satisfied, M1.2+ remains **PENDING INDEPENDENT APPROVAL**;
no Stage 6.5 persistence or authority behavior is authorized.
