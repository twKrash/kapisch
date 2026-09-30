# Review policy

Review is independent judgment, not a controller-authored checklist result. Bind invocation and result to the exact target, scope, and repository revision. Iteration review covers its declared delta; whole-branch review covers the complete target with fresh context. A later relevant implementation delta invalidates prior final evidence.

## Behavioral branch matrix

When the reviewed delta changes observable behaviour, both iteration and whole-branch reviews require a Behavioral branch matrix. Enumerate every observable branch, including invalid-input and pause/resume paths, in this order:

1. entry point;
2. trigger;
3. state before the transition;
4. pending or persisted state;
5. reconstructed state after resume, including inputs and what is restored, reused, recalculated, normalized, or lost;
6. authorization and policy context;
7. side effect or persistence result;
8. final public result/status;
9. regression coverage; and
10. status: `pass`, `finding`, or `unverified`.

Iteration scope covers changed behavioural entry points in the bounded delta and directly affected callers, contracts, transitions, and public outcomes. Whole-branch scope covers every changed behavioural entry point across the complete branch; a delta-only matrix is insufficient. For documentation-only work with no changed observable behaviour, do not create an artificial empty matrix; record why it is not applicable. A missing changed branch is a blocking review gap.

## Invariant evidence matrix

Produce an Invariant evidence matrix for every applicable high-risk or state, recovery, concurrency, permissions, migration, or workflow-policy whole-branch review. Each applicable row records: source claim; schema or example; normal transition; failure or cancellation; resume; consumers or policy; negative scenario; fallback or bootstrap; evidence; and status (`pass`, `finding`, or `N/A`). Every `N/A` must include its reason. The matrix is review evidence, not a substitute for branch tracing or verification.

## Review depth and evidence

Apply depth and lenses from the Risk policy. Quick is valid only when there is no production behaviour, public contract, persistent state, permission, privacy, or external-side-effect change. Standard adds affected callers/consumers, compatibility edges, negative/error paths, and regression adequacy. Deep adds adversarial negative paths, cross-boundary invariants, applicable failure/cancellation/resume, persistence, rollback, recovery, migration, concurrency, permission, privacy, audit, and operational coverage, plus every applicable matrix above. Every depth blocks a discovered P0/P1 defect.

Record target, base and reviewed revision, working-tree state, changed-file inventory, caller/consumer coverage, verification performed and omitted, coverage gaps, residual risk, and reviewer provenance. A standalone review returns findings only; it cannot approve or claim final readiness. Read-only instructions alone do not prove mutation confinement. If reviewer identity, context, enforcement, or required evidence is unavailable, block authority rather than silently downgrade.

A finding records stable ID, severity, confidence, location, trigger, causal relationship, impact, evidence, required fix, and required regression coverage. Use one finding per root cause and cite the changed evidence edge establishing how the reviewed delta introduced, exposed, or made the behavior unsafe. Confidence is `confirmed`, `likely`, or `question`; speculative concerns are never reported as confirmed defects.

- **P0**: immediate or highly credible catastrophic impact, such as security compromise, cross-tenant exposure, destructive data loss, or credential disclosure. Always blocks approval.
- **P1**: likely core-workflow failure, permission/isolation/invariant violation, persisted incorrect state, unrecoverable migration, or credible serious incident. Blocks approval.
- **P2**: bounded correctness, resilience, compatibility, observability, or coverage defect. Blocks when acceptance criteria are violated, no safe workaround exists, persisted incorrect state is at risk, or required regression coverage is missing.
- **P3**: non-blocking maintainability, clarity, or cleanup unless repository policy requires otherwise.

Authoritative approval or readiness requires validated reviewer provenance and current repository-state evidence. Validator success is structural evidence only; it does not prove semantic coverage, reviewer identity, or approval. A standalone review remains advisory even when findings are empty.
