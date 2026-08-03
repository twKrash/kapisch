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
