# Project understanding

This reference owns bounded read-only repository-understanding procedures.
The controller interprets the question and fixes a scope before research;
the `researcher` collects evidence and returns advisory findings only. Python
does not answer architecture questions, select evidence, write documentation,
or approve conclusions.

## Evidence boundary

Every research request states the question, repository or revision, included
areas, relevant exclusions, and desired output. Start with applicable
`AGENTS.md` files and repository policy, then inspect current source, tests,
versioned documentation, configuration, and relevant Git history. Cite concrete
paths, symbols, tests, or commits for material claims and distinguish directly
observed facts from inferences and unresolved questions.

Keep the search proportional to the question. Stop and report the boundary when
the answer would require unavailable evidence, execution with side effects,
access outside the approved repository scope, or an architecture or product
decision. Optional retrieval, indexing, or search tools may help locate evidence,
but they are not required and their stored summaries never outrank the current
repository or substitute for opening the cited source.

Research is advisory and read-only. It does not establish approval, final
readiness, or permission to edit files. A request to update documentation is a
separate implementation step based on a human-accepted evidence report.
"Accepted" means that the user explicitly accepts the report as downstream
scope, or that the original request explicitly scopes a follow-on write from
that report. It is input acceptance only, not researcher approval, independent
review, or approval of an architecture or product decision.

The controller normally assigns the writing step to the closed-catalog
`implementer` role and retains the single-writer boundary. The sole exception is
an exact authoritative-document synchronization that satisfies every mechanic
condition in [dispatch.md](dispatch.md); it may use `mechanic`. The assigned
executor rechecks cited evidence at the current revision, records changed files
and verification, and does not silently expand the research conclusion.
Behavioural, architectural, policy, or public-contract changes retain all
stronger applicable review requirements.
In addition, every versioned project-understanding or architecture-documentation
output receives independent review under [review.md](review.md), including maps,
drift corrections, onboarding documents, and decision records even when they do
not change behaviour or a public contract. The reviewer checks evidence fidelity,
scope, clarity, and repository consistency; it does not choose or approve the
underlying architecture or product decision.

## Architecture question

For a bounded architecture question:

1. Restate the exact question and boundary, including what is intentionally not
   being mapped.
2. Trace the smallest relevant path through entry points, ownership boundaries,
   data or control flow, persistence and external interfaces.
3. Identify enforcing tests and configuration, plus any mismatch between the
   apparent design and executable behaviour.
4. Return evidence-backed facts, explicit inferences, risks, unknowns, and a
   concise answer. Do not turn the answer into a redesign proposal unless the
   user separately asks for one.

## Architecture map

An architecture map records only repository-supported elements needed for its
declared audience and question. Include the revision, scope and exclusions;
components and their responsibilities; dependency or call direction; important
data stores and external systems; primary entry points; cross-cutting policy or
security boundaries; and evidence references. Mark inferred edges and unresolved
ownership explicitly. Prefer the smallest diagram or table that makes the
relationships clearer than prose, and include a prose summary so the result is
usable without a renderer.

## Documentation-drift check

Treat documentation as the claim set and current executable repository evidence
as the comparison target. For each material claim checked, report `current`,
`stale`, `ambiguous`, or `unverified`, with both the documentation location and
the source, test, configuration, or history evidence used. Do not rewrite stale
text during evidence collection. Proposed corrections belong to a separate
writing step, and uncertainty remains visible rather than being normalized into
new wording.

## Onboarding summary

An onboarding summary names its audience and task, then gives the minimum useful
orientation: repository purpose, supported runtime and development entry points,
major component ownership, common change and test paths, applicable policy,
important generated or local-only artifacts, and known sharp edges. Link each
operational instruction to current repository evidence. Do not invent setup
steps, stability guarantees, or ownership from convention alone.

## Decision-record preparation

Decision-record preparation gathers evidence; it does not choose or approve an
option. Return the decision question, context and constraints, decision drivers,
viable options found in the approved scope, evidence-backed trade-offs, affected
boundaries, migration or rollback considerations, unresolved questions, and the
human decision still required. An `architect` may turn accepted evidence into a
bounded proposal. The decision owner approves the choice; the controller then
assigns the approved record-writing scope to the `implementer` and retains the
single-writer boundary. Independent review checks every resulting versioned
decision record for evidence fidelity and repository consistency without
approving the decision itself. Never label a prepared or proposed record as
accepted.

## Research handoff

For `handoff=file|both`, the controller owns the durable
`00-research.md` lifecycle defined in [handoffs.md](handoffs.md). The researcher
returns evidence only and never writes this artifact.

Return:

- resolved role and advisory status;
- question, revision, scope, and exclusions;
- facts with repository evidence;
- inferences and their supporting facts;
- unknowns, conflicts, and confidence limits;
- the requested map, drift matrix, onboarding summary, or decision-record
  preparation;
- verification performed and skipped; and
- recommended next step, with no approval or edit claim.
