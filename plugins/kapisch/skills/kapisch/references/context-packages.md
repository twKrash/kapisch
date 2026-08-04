# Focused context packages

Build a task context package from durable files in this stable order:

1. normalized request, approved plan, task brief, and invariants;
2. selected binding decisions and required review findings;
3. exact scope, public interfaces, callers/consumers, and verification evidence;
4. verified applicable pitfalls and shortcuts; and
5. only then relevant advisory implementation context.

Dispatch is file-based: the selected package is written to the task's durable
context artifact and the assigned role reads that artifact rather than relying
on transient conversation context. A broad repository scan is justified only
when targeted files cannot establish a public boundary, caller/consumer, risk,
or verification requirement; record the reason and resulting files.

Reference counts are advisory budgets: `cheap=4`, `standard=8`, and `high=16`.
Record a justified budget overrun in the context artifact. A budget never blocks
necessary correctness, safety, security, or compatibility inspection, and it
does not establish a cache or token-saving claim without evidence.

## Delegated-step context package

When a delegated step uses an ecosystem capability, the controller writes the
step's self-contained focused context as `delegations/Dnn/00-context.md` with
the exact required contents defined in the
[`Dnn/00-context.md` section](ecosystem-routing.md#dnn00-contextmd) of
[ecosystem-routing.md](ecosystem-routing.md); this file does not duplicate that
schema. Data minimization applies strictly: include only the accepted input
paths, symbols, resources, and context references the step needs, and record
explicitly which data may cross the repository boundary. Do not include full
conversation history, broad repository content, secrets, or unrelated durable
knowledge "just in case." The package is written before the step starts, is
digest-bound in `00-route.toml`, and is mandatory regardless of `handoff`
mode.
