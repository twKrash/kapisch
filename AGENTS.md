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
