# Archived Task-Workflow Parallel-Wave Design

> **Non-normative archive.** This document preserves the retired S4 design for
> possible future evaluation. It is not an active task-workflow contract and
> does not authorize wave preview, creation, dispatch, workspace provisioning,
> leasing, package application, integration, cancellation, resume, or
> finalization. Active durable execution is sequential and operational wave
> input fails closed.

## Why this is archived

Stabilization S4 chose archive-only removal instead of implementing a live
two-member controller. The design accumulated safety requirements that cannot
be represented reliably by documentation and a read-only validator alone. A
future proposal must be separately approved and implemented as an executable
controller before any part of this protocol becomes normative.

Re-entry requires executable tests for eligibility rejection, isolated
workspaces, package integrity and scope, barriers, deterministic integration,
partial failure, cancellation, idempotent resume, and independent review
coverage. It also requires a documented threat model, portability analysis, and
an explicit decision updating the active contracts. No future implementation
may infer authority from this archive.

## Retired bounded model

The design allowed one wave containing at most two already-ready implementation
nodes. Review and final nodes were never eligible. Node identity, assignment,
status, reports, knowledge, and verification remained in the ordinary durable
graph; a wave record supplied only coordination evidence.

A proposed policy used `parallelism=auto|off` and
`max_parallel_agents=1|2`. Selection was deterministic by persisted node
`sequence`, then node ID. Completion order, filesystem order, model preference,
and response timing were never ordering inputs. A sequential composite batch
remained one executor unit and could not be split across a wave.

Illustrative coordination shape:

```yaml
waves:
  - id: W01
    status: planned
    base_revision: abc1234
    member_node_ids: [T02, T03]
    scheduling_reasons: [independent-scopes, isolated-workspaces]
    isolation_strategy: git-worktree-patch-package
    integration_order: [T02, T03]
    barrier: pending
    members:
      - node_id: T02
        status: wave_running
        workspace: .worktrees/task-example-W01-T02
        package:
          path: packages/W01-T02.patch
          format: unified-diff
          sha256: package-content-digest
          byte_size: 1234
          base_revision: abc1234
          declared_write_scope_fingerprint: scope-fingerprint
          actual_changed_paths: [src/example.py]
          actual_paths_digest: paths-content-digest
          validation: pending
      - node_id: T03
        status: wave_running
        workspace: .worktrees/task-example-W01-T03
        package:
          path: packages/W01-T03.patch
          format: unified-diff
          sha256: package-content-digest
          byte_size: 1234
          base_revision: abc1234
          declared_write_scope_fingerprint: scope-fingerprint
          actual_changed_paths: [tests/example_test.py]
          actual_paths_digest: paths-content-digest
          validation: pending
    integration_terminal:
      id: I-W01
      status: pending
      report: waves/W01-integration.md
      completed_member_node_ids: [T02, T03]
```

The retired lifecycle was `planned -> dispatched -> running -> at_barrier ->
integrating -> verifying -> complete`. Running or barrier work could block or
fail; non-integrated work could be cancelled only by explicit authority. Member
states mirrored that lifecycle. A wave was not complete until packages, scope,
barrier, ordered integration, verification, and its controller-owned integration
terminal all passed.

## Eligibility and collision rules

Two nodes were candidates only when all of the following were proven before
dispatch:

- neither directly or transitively depended on the other;
- both used the same immutable recorded base;
- briefs, persisted assignments, read scopes, write scopes, shared-resource
  scopes, interfaces, and verification were complete;
- write sets were disjoint, and neither read a path or interface the other wrote;
- neither touched a common generated output, lock file, registry,
  schema/migration chain, configuration source, mutable fixture, external/local
  runtime resource, or release artifact;
- neither contained an unresolved design decision;
- deterministic integration was known; and
- each node had a suitable isolated execution and test environment.

Missing, dynamic, broad, or inconsistent scope was unknown and forced
sequential fallback. Read/read overlap was safe only without shared mutable
state. Write/write was unsafe. Write/read required a dependency. Disjoint paths
never overrode a semantic shared-state hazard. Scheduling did not reclassify a
node, change its logical tier, or reduce review depth.

## Isolation and workspace provisioning

The proposed write-capable strategy used one clean detached Git worktree per
member from the common base and one deterministic unified-diff package per
member. Concurrent writers never shared a working directory, index, branch,
generated-output directory, or mutable test environment. The primary branch was
not an execution workspace.

Because this repository has post-checkout bootstrap behavior, each worktree
required a controller-owned empty hooks directory created before `git worktree
add`. Evidence included its canonical absolute path, ownership, empty-directory
manifest digest, successful emptiness check, the exact
`git -c core.hooksPath=<canonical-directory> worktree add ...` invocation and
result, the resolved hook path, and confirmation that no bootstrap ran. Missing,
relative, changed, post-hoc, or mismatched evidence made the workspace
untrusted.

Provisioning did not run bootstrap scripts, install or sync dependencies, build
artifacts, copy or link `.env` files, or expose credentials or local data absent
separate explicit approval. Dirty worktrees were never reused, and worktrees
with unrecorded changes were preserved rather than deleted.

## Shared test-resource lease design

When members needed one mutable test service, the design serialized access
through one controller-owned wave-level queue. Before dispatch it recorded the
resource ID, complete fixed member order, current holder, queue status, and
unique grant/release event IDs. Member briefs prohibited access until the
controller granted the head member's lease.

The queue states were `pending`, `granting`, `held`, `releasing`, `complete`,
or `blocked`. Only the head member could hold the lease. Interrupted or
conflicting grant/hold/release evidence blocked; the controller never guessed
that the next member could proceed. Integration could not begin until every
required serialized-resource queue was complete.

## Package, barrier, and integration evidence

Each immutable package recorded its format, SHA-256, byte size, producing base,
declared-scope fingerprint, actual changed paths and digest, and validation
result. At the barrier the controller recomputed all digests, compared declared
and actual scope, confirmed the common base, and checked for new semantic
conflicts. An out-of-scope package was preserved but blocked.

The primary had to be clean before integration. The proposed canonical state
contained:

```yaml
head_revision: abc1234
index_clean: true
untracked_clean: true
untracked_status_sha256: exact-nul-delimited-untracked-list-digest
diff_algorithm: git-diff-binary-v1
diff_sha256: exact-binary-diff-digest
```

`untracked_status_sha256` covered the exact bytes of
`git ls-files --others --exclude-standard -z`. `git-diff-binary-v1` covered the
exact bytes of `git -c core.quotepath=true -c core.autocrlf=false diff --binary
--no-ext-diff --no-textconv HEAD`. Unreproducible configuration, attributes,
encoding, or path behavior blocked instead of substituting another digest.

Integration followed persisted node order only after all members reached the
barrier. Before touching the primary, the controller materialized each step in a
fresh detached validation worktree. For later steps it verified and applied the
immutable ordered package prefix, checked every expected prefix state, then
checked and applied the current package. The step persisted full expected
pre/post states, predecessor, package digest, materialization commands/results,
and observed pre/post states.

An `applying` recovery record compared the primary with the complete expected
state: pre-state meant safe to retry, post-state meant finalize without reapply,
and any other state blocked. A missing, reordered, tampered, stale,
out-of-scope, conflicting, or already-applied package never proceeded. Patch
applicability was not treated as proof of semantic compatibility, and automatic
conflict resolution or semantic merge was prohibited.

## Failure, cancellation, and resume

Partial failure preserved every report, package, and verification result but did
not mark members complete or partially integrate by default. The record kept
original membership and any explicit amendment. A failed member could use one
bounded eligible retry or recorded sequential fallback. Cancellation preserved
evidence and dirty workspaces and did not roll back already integrated work by
guesswork.

Recovery loaded the persisted wave, members, workspaces, packages, barrier,
integration chain, and terminal evidence; inspected Git and every recorded
workspace; and recomputed package and state digests. It never redispatched a
member with a valid completed package and never applied a package twice. A
missing workspace was tolerable only with a valid package. A changed primary,
ambiguous state, incomplete evidence, stale base, extra active node, third
member, or second active wave blocked. Repeated resume without repository
changes had to choose the same next action.

## Knowledge, metrics, and review

Member context packages contained only selected verified knowledge. Members
could propose candidate facts, hints, shortcuts, pitfalls, and questions in
their own reports, but could not mutate or promote the shared ledger or affect
another member during the same wave. The barrier reconciled candidates with
source attribution; contradictions blocked promotion.

Only the controller wrote shared metrics. Proposed wave evidence included IDs,
statuses, common base, scheduling reasons, isolation and hooks evidence,
workspace/package integrity, declared/actual scopes, integration order, barrier,
verification, leases, failure, and cancellation. Metrics never established
reviewer provenance or approval.

An integration terminal verified only deterministic integration. It was not an
independent review. A later review scope would have named each completed wave
and its matching terminal, validated report and verification digests, member
coverage, and full resulting primary state, while avoiding duplicate member
coverage. Review and final remained configured-reviewer-only and
revision-bound.

## Retired dogfood scenario

The documentation fixture paired one bounded standard-tier change with one
fully specified cheap-tier label/test change. They had disjoint bounded scopes,
the same base, isolated worktrees, hook-safe provisioning, deterministic package
order, and serialized access to any shared test service. A dependent consumer,
a shared generated registry, and a sequential composite batch remained outside
the pair. Reverse completion order did not affect integration order. Failure,
scope violation, missing isolation, stale base, or package conflict blocked and
never triggered an automatic semantic merge.

This scenario was design pressure only. It never executed agents or proved the
protocol safe.
