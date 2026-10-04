## Kapisch self-hosting boundary

When working in the Kapisch repository, do not use Kapisch itself to design,
architect, plan, implement, orchestrate, dispatch, or otherwise execute work
on Kapisch.

This prohibition includes Kapisch advisory, architecture, research,
implementation-planning, task/milestone execution, worker dispatch, and other
Kapisch-managed development workflows.

### Standalone reviewer exception

`kapisch-reviewer` may be used standalone as an independent read-only reviewer
after the design, implementation plan, or code being reviewed was produced
outside Kapisch's own orchestration workflows.

When reviewing Kapisch itself, `kapisch-reviewer` must:

- operate only in standalone review mode;
- remain read-only;
- not invoke Kapisch advisory, architecture, planning, execution, dispatch,
  worker, or implementation workflows;
- not create or modify implementation plans, architecture artifacts, workflow
  authority, or source files;
- not execute proposed fixes;
- review only the supplied scope against repository evidence and governing
  specifications;
- return findings and recommendations only.

The external controller or human decides whether and how findings are applied.

### Required review lenses

For durable workflows, explicitly check:

**Cold-restart invariant:** every durable workflow must be reconstructible
after process restart from validated persisted authority alone, without relying
on controller memory, caller honesty, or unpersisted conversational state.

**Producer-ownership invariant:** every consumed durable artifact must have an
explicit producer earlier in the lifecycle, and every generated authority
field must have exactly one owning producer.

Standalone review does not grant Kapisch authority to manage development of
Kapisch itself.

### Code Standards

- Python code must follow PEP 8 and normal Python best practices:
  <https://peps.python.org/pep-0008/>
- Prefer simple, explicit, idiomatic Python over clever
  abstractions or framework-like indirection.
- Apply the Single Responsibility Principle: each module, class, and
  function should have one primary reason to change.
- Apply SOLID principles where they improve separation of responsibilities,
  substitutability, and dependency boundaries. Do not introduce abstractions solely
  to satisfy SOLID mechanically.
- Prefer composition and small focused functions over inheritance.
  Introduce inheritance, `Protocol`, ABCs, registries, factories, or plugin
  abstractions only when an actual interchangeable implementation boundary exists.
- Preserve existing architecture and infrastructure by default. Do not introduce
  a new dependency, storage mechanism, framework, persistence model, or
  architectural layer unless the existing capabilities are demonstrably insufficient.
- Keep public modules and interfaces small. Implementation details should
  remain private unless they are intentionally part of the supported contract.
- Avoid circular imports and bidirectional module dependencies. Dependencies
  should flow from higher-level orchestration toward focused lower-level components.
- Keep one source of truth for validation, canonicalization, serialization,
  identity, and protocol semantics. Do not duplicate the same semantic transformation
  in multiple modules.
- Prefer immutable value objects for durable identities, protocol facts, and
  validated domain data when mutation is not part of the contract.
- At protocol and persistence boundaries, validate inputs explicitly and
  fail closed. Do not silently normalize, infer, repair, downgrade, or
  reinterpret malformed or unsupported authoritative data unless the governing
  contract explicitly requires it.
- Errors at public or protocol boundaries should be deterministic and intentional.
  Do not leak accidental implementation exceptions where a stable validation or
  domain error is expected.
- Do not rely on process memory, conversational context, caller honesty,
  or mutable derived views for durable authority. Persisted authoritative state
  must remain sufficient for cold restart.
- Every consumed durable artifact must have one explicit earlier producer.
  Generated authority fields must have exactly one owning producer.
- Keep filesystem access, subprocess execution, parsing, canonical encoding,
  validation, policy decisions, state transitions, external effects, and
  presentation concerns separate when they have different reasons to change.
- Pass the narrowest required data between components. Avoid passing broad
  state or context objects when a smaller immutable value or reference is sufficient.
- Do not create speculative abstractions for anticipated future requirements.
  Extract a new module or abstraction when a concrete second responsibility or
  implementation boundary appears.
- Preserve backward or retained-format semantics exactly where compatibility is
  required.
  Never silently reinterpret old persisted data using newer semantics.
- New behavior and bug fixes require focused regression tests. Tests should prove
  the changed behavior and should fail when that behavior is removed or broken.
- Test negative, invalid, stale, crash/recovery, and boundary cases for code dealing
  with persistence, authority, concurrency, permissions, identities, or external
  effects.
- Do not weaken a contract, validation rule, safety property, or test merely to
  make an implementation pass.
- Keep changes narrowly scoped. Do not perform unrelated cleanup, formatting, refactoring,
  dependency upgrades, or behavior changes in the same task unless they
  are required for correctness.
- Prefer readable names and explicit control flow. Comments should explain invariants,
  ownership, non-obvious constraints, or why a decision exists, not restate
  the code.

### Implementation Structure

- A production module should have one primary responsibility.
- Public facade modules may be intentionally small and delegate implementation
  to focused private modules.
- Reassess module structure when a production module approaches approximately
  350 lines or a function approaches approximately 60 lines. These are review
  triggers, not hard limits.
- Modules above approximately 500 lines or functions above approximately 100
  lines require an explicit justification or decomposition before final review.
- Do not split code mechanically to satisfy line-count targets;
  split only along coherent responsibility boundaries.
