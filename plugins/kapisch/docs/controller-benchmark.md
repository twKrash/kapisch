# Controller benchmark

Use equivalent clean worktrees and fixed task definitions. Retain raw JSONL outside committed durable evidence.

Run baseline and candidate for: a bounded behavioral implementation/review task; a high-risk durable task with research, implementation, whole-branch review, final readiness, and one blocking fix; and worker/reviewer interruption-resume scenarios.

Each JSONL record has run ID, variant, role, invocation, input/output/cache tokens, turns, elapsed time, workflow/validator outcome, review decision/findings, test result, and resume result. Unknown provider measurements are `null`, never estimated as zero.

Compare with `python scripts/compare_controller_benchmark.py --baseline baseline.jsonl --candidate candidate.jsonl --format json`. Review cached and uncached input separately. No numeric release threshold exists before baseline measurement; human acceptance requires lower parent work without compensating child work or reduced review, durable-validation, correctness, or resume evidence.
