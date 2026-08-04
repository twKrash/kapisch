# KAPISCH Roadmap

KAPISCH is the implemented standalone plugin, distributed from this repository
through the Git-backed `kapisch-local` marketplace. Legacy task-workflow
identifiers are supported migration inputs; new artifacts use `.kapisch/`.

This roadmap is separate from the product milestones of the source application.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| planned | No implementation is merged. |
| implemented | The documented code or contract is merged. |
| reviewed | Required project review evidence exists for the implemented scope. |
| runtime accepted | A named supported Codex surface exercised the documented flow. |
| released | An immutable version/tag identifies an accepted commit. |
| deferred/archived | Intentionally outside the active supported runtime. |

Automated package, validator, and marketplace tests establish implementation
coverage; they are not Codex runtime acceptance.

During extraction, provide an explicitly bounded compatibility path for existing
`KAPISCH` invocations and durable artifacts. New installations and newly
created artifacts use only the canonical KAPISCH identifiers.

## Canonical identifiers

| Concept | Identifier |
| --- | --- |
| Public product | `KAPISCH` |
| Repository | `twKrash/kapisch` |
| Plugin ID | `kapisch` |
| Primary skill | `$kapisch` |
| Python package | `kapisch_validation` |
| Artifact namespace | `.kapisch/` |
| Legacy identifier | `KAPISCH` |

## Local artifacts and project knowledge

The `.kapisch/` directory is local and gitignored by default, but its contents
have distinct retention rules. Canonical project knowledge remains in versioned
repository documentation, source, tests, and Git history.

```text
.kapisch/
├── runs/<task-id>/
├── cache/
└── local-state/
```

- `runs/<task-id>/` contains durable local execution and review evidence. It is
  inspectable but not a cache: deleting it prevents resume and invalidates any
  recovery, approval, or readiness claim that requires the missing evidence.
- `cache/` contains derived, revision-bound, inspectable, deletable cache
  records. A cache miss falls back safely to fresh repository reads.
- `local-state/` contains machine-local runtime state. It is neither durable
  workflow evidence nor canonical project knowledge.

## Product direction

KAPISCH should become a lightweight, Codex-native workflow contract and
validation plugin, not another self-contained workflow platform. The LLM or
skill interprets requests and applies the portable contract; Codex resolves
configured agents, models, sandboxing, and dispatch; Python validates persisted
structural evidence and artifact integrity without judging semantic sufficiency.
Its core responsibilities are:

- interpret natural-language repository tasks and select the smallest safe route;
- assign bounded specialist roles and logical model tiers through Codex-native
  agent profiles;
- use explicit human-in-the-loop gates for material scope, architectural choices,
  review fixes, publication, and other meaningful side-effect boundaries;
- support graph-free work and optional durable dependency-aware execution;
- preserve compact, revision-bound handoffs and task-local knowledge so verified
  context can be reused without replaying whole conversations;
- validate durable TOML artifacts, lifecycle, freshness, and reviewer evidence
  with a bundled Python 3.11 standard-library validator; and
- keep presentation themes, including an original industrial-mystic `foundry`
  theme, separate from workflow semantics and safety policy.

The intended dependency boundary is Codex, Git for repository work, and Python
3.11 for deterministic validation. The portable validator must not require
Node.js or third-party Python packages; plugin installation and runtime remain
subject to the capabilities of the installed Codex client. KAPISCH must not add
a daemon, database, MCP server, container runtime, or separate orchestration
service.

## Next milestone — standalone KAPISCH repository

Status: implemented and reviewed; runtime acceptance and release remain
planned under [issue #11](https://github.com/twKrash/kapisch/issues/11).
The source extraction and Git-backed local-marketplace layout are implemented.
Clean Codex installation, fresh-session discovery, reviewer invocation, and
`$kapisch` acceptance have not been exercised. OpenAI public Plugin Directory
submission is deferred/archived. See [acceptance.md](acceptance.md),
[compatibility.md](compatibility.md), and [collision-check.md](collision-check.md).

Goal: extract the reusable skill, portable role contracts, Codex agent-profile
templates, validator, tests, and public documentation from the source
application into a standalone Git-backed local marketplace repository without
weakening the current workflow invariants.

Required work:

1. Validate the working name `KAPISCH` across the OpenAI/Codex plugin ecosystem,
   GitHub, package registries, and adjacent AI coding tools before publishing.
   Decide the public display name, repository name, plugin ID, and primary skill
   invocation together so they do not drift.
2. Create the standalone repository as a Git-backed local marketplace with the
   minimal supported Codex plugin layout under `plugins/kapisch`, repository
   catalog metadata, license, README, changelog, contribution guidance, and CI.
3. Move the current `KAPISCH` skill, normative references, Python standard-library
   validator, fixtures, and validator tests into the standalone plugin layout.
4. Separate portable `KAPISCH` role contracts from Codex-specific custom-agent
   templates. Portable contracts own role semantics; bundled templates contain
   only Codex runtime settings. Use namespaced profile identities such as
   `kapisch-reviewer`, not just namespaced filenames, and do not assume plugin
   installation activates templates.
5. Add an explicit, human-approved setup path that copies a template into a
   project-scoped `.codex/agents/` profile or optional user-scoped
   `~/.codex/agents/` profile. Setup must detect identity collisions, preserve
   user modifications, record template and installed-profile revisions, report
   drift, and never overwrite, rename, or delete an existing profile silently.
   Any role-to-profile binding is KAPISCH-owned compatibility metadata, not
   hidden Codex configuration or routing logic.
6. Support a degraded built-in-agent mode when custom profiles are unavailable.
   This mode may provide advisory analysis but cannot satisfy approving
   independent-review or final-readiness gates. Approval-capable review requires
   a successfully invoked configured reviewer profile and fresh canonical
   invocation evidence bound to its logical role, resolved profile, revision,
   target, and result digest.
7. Remove source-application-specific assumptions from the portable plugin while
   preserving repository-local policy discovery through `AGENTS.md` and relevant
   project documentation.
8. Keep Python isolated as a read-only verification engine. It must not become a
   request parser, semantic router, agent scheduler, model resolver, artifact
   writer, Git wrapper, or approval authority.
9. Define the migration and dogfood path for the source application, including
   whether it consumes the standalone plugin directly or temporarily retains a
   compatibility copy during stabilization. Legacy `.planning/task-workflow/`
   artifacts remain readable without mutation under an explicit compatibility
   version. Migration is an explicit, user-approved copy-and-validate operation
   into `.kapisch/runs/<task-id>/`; it retains the source until the destination
   validates and the user accepts it, never combines evidence across namespaces,
   and never rewrites historical bytes, paths, digests, or invocation records.
   KAPISCH creates no new legacy artifacts.
10. Verify natural-language routing, role/profile resolution, graph-free review,
   durable sequential execution, resume, reviewer invocation evidence, and final
   readiness against the extracted plugin.
11. Treat the GitHub repository as locally distributable only after
   `codex plugin marketplace add twKrash/kapisch --ref main` and installation of
   `kapisch@kapisch-local` work in a clean Codex environment and the bundled
   validator test suite passes without application-repository imports.
12. Define the compatibility removal boundary and rollback path from active
    KAPISCH profiles to prior user-owned configuration.
13. Convert newly created task-local knowledge records to canonical TOML during
    extraction. Legacy non-TOML knowledge records are migration inputs only;
    Python validates persisted machine-readable facts but does not select,
    promote, or write knowledge.

Exit criteria:

- the standalone marketplace repository and its sole `plugins/kapisch` bundle
  are the canonical source of KAPISCH;
- the portable validator runs without Node.js or third-party Python packages;
- the validator remains Python 3.11 standard-library only and read-only;
- focused automated coverage establishes implemented schema, lifecycle,
  reference, digest, freshness, migration, and no-new-legacy-write invariants;
  semantic scope, reviewer identity, approval-chain completeness, and final
  readiness remain controller and independent-review decisions;
- The source application can use the extracted plugin without carrying an independent
  divergent implementation;
- the public name and identifiers have passed a documented collision check;
- a clean plugin installation works without custom agents, while full approving
  review becomes available only after explicit profile setup;
- active Codex profiles are generated or installed outside the plugin cache and
  remain replaceable runtime configuration;
- portable role contracts do not depend on repository-specific `.codex` paths;
- new KAPISCH machine-readable knowledge and durable artifacts are TOML, while
  legacy artifacts remain readable only through the documented compatibility
  path; and
- deleting durable run evidence demonstrably blocks resume and any evidence
  claim that depends on it, while deleting cache records safely falls back to
  repository reads.

Non-goals for this milestone:

- parallel agent scheduling or worktree integration;
- automatic semantic approval or automatic review-fix loops;
- a database, daemon, MCP service, or separate orchestration runtime;
- a Python request parser, semantic router, agent scheduler, model resolver,
  artifact writer, Git wrapper, approval engine, or hidden automation layer;
- automatic profile activation, overwrite, deletion, approval, review-fix,
  commit, push, or merge;
- persistent memory or retrieval data that outranks current repository evidence;
- measured token-saving claims before observable runtime evidence exists;
- presentation-theme implementation within this extraction milestone; Change 6
  is a separate post-extraction slice;
- submission to OpenAI's public Plugin Directory; distribution uses the
  Git-backed `kapisch-local` marketplace; and
- cross-machine synchronization, remote evidence storage, or shared workflow
  state between developers.

## Foundation 0 — implemented and reviewed

- Establish the role-based `plan`, `implement`, `review`, `mechanic`, and
  `final` workflow, normalized requests, durable handoffs, and independent
  review/final-readiness contracts.

## Change 1 — implemented and reviewed

- Add durable sequential execution: a versioned graph and state, one active
  standard `implementer`, lifecycle-controlled resume, task briefs, contexts,
  reports, and a task-local knowledge ledger.

## Change 2 — implemented and reviewed

Completed after independent integrated review and initial final-readiness
evidence. This status edit requires a fresh final-readiness refresh on the
resulting working-tree state.

- Define cost-aware *logical* routing for mechanical, prescriptive, bounded,
  and design work without changing the current Change 1 bootstrap.
- Add a deterministic, non-behavioural mechanic contract and an
  implementer-lite contract for completely specified behavioural work; either
  must escalate ambiguity rather than make design choices.
- Record replaceable logical model tiers, focused context selection, persisted
  assignments, bounded escalation, sequential composite batches, and routing
  observability in the workflow documentation and configuration.
- Preserve version-1 compatibility defaults and add scenario-based evidence
  for routing, resume, batching, escalation, context freshness, and review
  independence.

## Change 3 — implemented and reviewed

Completed following the valid Round 13 integrated review. This status-only edit
requires fresh final readiness on the resulting revision; provenance-only
generic analysis is not completion evidence.

- Define bounded parallel-ready scheduling, collision handling, isolated
  execution, deterministic integration, and recovery controls after Change 2's
  independent review evidence. The active Change 3 bootstrap remains sequential;
  it must not use the scheduler it is introducing.

## Stabilization S1 — implemented and reviewed

Completed in this revision because the policy change and roadmap update together
deliver this stabilization slice.

- Define the supported execution surface as graph-free workflows plus optional
  durable sequential execution.
- Quarantine parallel waves as an experimental design capability until an
  executable controller and validator enforce their safety invariants.
- Prevent new wave creation, dispatch, resume, cancellation, and integration
  through operational routing.
- Preserve the existing wave protocol as design input rather than claiming
  runtime support.

## Stabilization S2 — implemented, partially complete

- The validator and its existing structural coverage are implemented. Its
  completion is blocked by [#5](https://github.com/twKrash/kapisch/issues/5),
  [#6](https://github.com/twKrash/kapisch/issues/6), and
  [#7](https://github.com/twKrash/kapisch/issues/7): deterministic unreadable
  artifact handling, closed policy/state vocabularies, and immutable resume
  snapshots remain unresolved.
- Existing coverage validates sequential durable manifests, state,
  node references, dependency ordering, legal transitions, review scopes,
  review/final ordering, and canonical reviewer invocation envelopes.
- It does not establish complete resume or idempotency safety.
- Provide valid and invalid fixtures reproducing missing `review_scope`, stale
  review evidence, malformed invocation envelopes, and illegal transitions.
- Do not implement waves or a scheduler in this stage.

## Stabilization S3 — implemented and reviewed

Completed by consolidating the existing supported contracts without changing
workflow behavior. Parallel waves remain experimental and deferred to S4.

- Consolidate normative documentation boundaries:
  - `SKILL.md` owns the public interface and role boundaries;
  - `request-normalization.md` owns request resolution;
  - `review.md` owns review and final evidence;
  - `handoffs.md` owns artifact storage and invocation envelopes;
  - `execution-graph.md` owns durable schema;
  - `resume.md` owns recovery behavior.
- Replace duplicated normative text with concise links and summaries.
- Define one deterministic sequential controller transition table.
- Define recovery when ignored `.planning` state is missing: existing local
  execution cannot resume, but a fresh revision-bound review may start.
- Do not change the supported workflow behavior while consolidating contracts.

## Stabilization S4 — implemented and reviewed

Implemented and reviewed by choosing archive-only removal. Graph-free workflows and durable
sequential execution are the sole active surfaces; operational wave input fails
closed, while the retired protocol is deferred/archived in
[parallel-wave-design.md](parallel-wave-design.md).

- Preserve version-1/version-2 sequential compatibility and the
  `parallelism=off`, `max_parallel_agents=1`, and root-`waves` rejection
  sentinels.
- Keep empty legacy wave review-scope fields readable, reject non-empty values,
  and omit those fields from new examples.
- Preserve ordinary advisory subagent collaboration outside durable waves.
- Reconsider parallel routing only through a new approved decision and an
  executable controller with tests for eligibility rejection, isolated
  workspaces, package integrity, barriers, deterministic integration, partial
  failure, cancellation, and idempotent resume.
- Do not add broader parallelism, semantic auto-merge, or more than two agents.

## UX and portability simplification — implemented and reviewed

Completed after S4 without changing durable execution semantics.

- Make ordinary language the normal interface and keep compact fields as expert
  compatibility controls.
- Keep workflow shape and logical role selection in the Markdown skill contract;
  Codex runtime owns configured profile/model resolution and dispatch.
- Preserve every S1-S4 invariant, including fail-closed operational waves.

## Change 4 — measured cost and context discipline

Status: deferred until the standalone plugin is stable and runtime observations
are available.

- Measure routing, model-tier, context-size, handoff reuse, validator, and review
  outcomes using auditable evidence.
- Define token and cost accounting without treating estimates, model list prices,
  or self-reported agent savings as observed results.
- Add deterministic cache eligibility, revision binding, freshness classes,
  invalidation, hit/miss evidence, and safe fallback to fresh repository reads.
- Keep documentation and Git history canonical; caches remain derived, local,
  inspectable, and deletable.
- Keep cost measurement in an optional benchmark harness, not the core plugin.
  Core artifacts may record runtime fields that Codex exposes; unavailable
  fields remain `unavailable` and must never be estimated as observations.
- Use a fixed representative task corpus and paired baseline-versus-KAPISCH
  runs. Record observed role/profile/model-tier fields, invocations, retries,
  elapsed time, cache evidence, HITL gates, validator/review outcomes, and
  input or cached-token counts only when the runtime exposes them.
- Do not turn the validator, cache, or benchmark harness into a semantic router
  or hidden persistent memory service.

## Change 5 — project understanding and architecture documentation

Status: implemented and reviewed. Policy B covers only advisory researcher dogfood. The
preserved Round 0 negative review led to profile-path and lifecycle fixes;
canonical Round 1 approved the resulting pre-correction staged delta. The first
distinct final-readiness pass returned `not-ready` because the portable reviewer
role embedded a Codex-specific path and this roadmap did not reflect the
canonical review history. Those findings were corrected, canonical Round 2
approved the complete corrected delta, and a distinct final-readiness decision
returned `ready`. This status-only edit changes the staged state and therefore
requires a fresh whole-delta approving review and distinct final-readiness
decision before the resulting completed state is itself ready. Change 5 does
not depend on Change 4 measurement work.

- Add bounded read-only architecture questions through the `researcher` role.
- Add architecture mapping, documentation drift checks, onboarding summaries,
  and decision-record preparation as explicit procedures.
- Separate evidence collection, documentation writing, and independent review.
- Keep source files, tests, repository policy, and versioned documentation as the
  source of truth; optional retrieval tools may assist but are not required.

## Change 6 — presentation themes

Status: implemented and reviewed as a separate post-extraction slice after the extracted public
contracts and artifact vocabulary stabilized. The change-6 dogfood run
(`change6-presentation-themes-dogfood` under the local `.kapisch/runs/`)
recorded the review history: the research handoff documented the delta and
found that an earlier status claim of a fresh-context review with no actionable
findings was not supported by durable evidence; Round 0 returned `do-not-approve`
on that unsupported claim and on the absent pre-dispatch invocation evidence;
the first status correction pre-claimed its own review outcome and was rejected
by Round 1; the text was restaged to end at existing evidence; Round 2 approved
the corrected whole delta under the user-attested external-task path; and a
distinct final-readiness decision returned `ready`. The runtime did not expose
configured reviewer-profile receipts, and this status-only edit changes the
reviewed state; fresh approval-capable review and a distinct final-readiness
decision are therefore required before the resulting completed state is itself
ready. The standalone milestone's pending manual local-marketplace import and
installation acceptance remain orthogonal. Change 6 does not depend on Change 4
measurement work.

- Add presentation-only terminology themes with `default` and an original
  industrial-mystic `foundry` theme as the first examples.
- Allow themes to rename user-visible roles, procedures, gates, and status text
  without changing artifact schemas, logical role IDs, permissions, routing,
  validation, or safety behavior.
- Keep localization separate from lore or presentation themes.

## Change 7 — composable Codex ecosystem routing

Status: implemented and reviewed. Clean Codex installation, fresh-session
discovery, reviewer invocation, and `$kapisch` runtime acceptance remain
planned under [issue #11](https://github.com/twKrash/kapisch/issues/11); this
is not runtime accepted or released. The maintainer's scope-reduction
decision (2026-08-04, PR #4) is implemented: the route record carries the
minimum delegation metadata (selected capability, maximum effect class,
authority, digest-bound context/evidence); the parallel route lifecycle/revision
engine, graph-free delegation, and resume/external-effect reconciliation
machinery are deferred/archived pending demonstrated needs and
[#10](https://github.com/twKrash/kapisch/issues/10). The change-7
dogfood run (`change7-ecosystem-routing-dogfood` under the local
`.kapisch/runs/`) recorded the review history: the research handoff assessed
the definition of done and flagged the evidence gaps; Round 0 approved the
implementation with thirteen non-blocking findings; a bounded P3 fix round
resolved every fixable finding; Round 1 approved the corrected whole delta
under the user-attested external-task path; a distinct final-readiness decision
returned `ready` for that state; the roadmap status edit and the final-review
amendment received their own fresh reviews (Rounds 2 and 3); the PR review
blockers were addressed in the review fix round. This status text itself
changes the reviewed state; fresh approval-capable review and a distinct
final-readiness decision are required before the resulting state is reported
completed or ready. Change 7 does not depend on Change 4 measurement work.

- Allow KAPISCH routes to delegate bounded work to existing Codex skills and
  plugins instead of reimplementing their methodology or integrations.
- Preserve one explainable route, explicit authority, focused context, durable
  evidence, and human gates across delegated steps.
- Do not become a replacement GitHub client, CI platform, retrieval database, or
  agent-process manager.

## Durable invariants

- Risk is distinct from execution complexity. Extra task detail never lowers
  risk, review depth, required lenses, or regression coverage.
- A mechanic never changes behaviour. It is deterministic and non-behavioural;
  uncertainty routes to a stronger executor.
- Implementer-lite may perform only completely specified behavioural work. It
  makes no design choices, never expands scope, and never reinterprets
  acceptance criteria; ambiguity escalates to a stronger executor.
- Cheap execution never weakens review: independent review and final readiness
  remain high-tier and appropriately deep regardless of implementation tier.
- Models are replaceable. Durable graphs store logical tier names, never model
  identifiers.
- Assignment is persisted before dispatch; resume preserves a running
  assignment and never silently reclassifies a completed, verified node.
- Automatic escalation is durable and bounded to one; an identical retry needs
  changed context or scope.
- Batches retain member IDs and outcomes while remaining one sequential
  execution unit.
- Focused context selection is deterministic: it admits only applicable,
  verified or promoted records in reference order and handles stale
  binding and advisory records under their documented rules.
- Commit and push authority remains explicit; routing never authorizes either.
- Cost, caching, and savings claims require measured, auditable evidence.
- Human approval gates apply only at meaningful judgment, scope, safety, or
  side-effect boundaries; they must not become automatic confirmation noise.
- Themes may alter presentation only and never workflow semantics, permissions,
  evidence, validation, or approval.
