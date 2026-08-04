# Change 7 execution plan — composable Codex ecosystem routing

Status: implementation complete; review and final-readiness evidence in the
`change7-ecosystem-routing-dogfood` run under the local `.kapisch/runs/`
(originally "execution plan only; implementation has not started").

## Outcome

Implement Change 7 as an optional, sequential capability-delegation layer owned
by the existing KAPISCH controller. KAPISCH may use an available Codex skill or
plugin capability for a bounded step, but it remains responsible for request
normalization, role and risk selection, focused context, authority, human gates,
durable evidence, recovery, independent review, and final readiness.

The change must not add a logical role, agent profile, MCP server, agent-process
manager, semantic Python router, or second workflow controller.

The current portable baseline was verified while preparing this plan:

```text
python scripts/test_portable_package.py
Ran 96 tests
OK
portable-package=passed
```

Fresh baseline recorded 2026-08-04 on the merged marketplace layout
(origin/main `88c5eda`, branch `codex/change7-ecosystem-routing`):

```text
cd plugins/kapisch
python scripts/test_portable_package.py
portable-package=passed
python -m unittest discover -s tests/kapisch_validation
Ran 100 tests
OK
```

## Product and runtime assumptions

Codex documents a plugin as a bundle that can contribute skills, connectors,
and MCP tools. A skill provides reusable methodology; connectors and MCP tools
provide live data or controlled actions. Plugin installation, skill discovery,
connector authentication, external-service authorization, and tool-call
approval remain separate runtime controls. Installed plugin capabilities may
also require a new session before they are available.

Accordingly, this plan treats a plugin as a capability bundle rather than an
independently scheduled worker. The controller selects and uses a bounded skill
or plugin-backed capability; it does not hand ownership of the KAPISCH route to
the plugin.

Current product references:

- [Plugins](https://learn.chatgpt.com/docs/plugins)
- [Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Skills and plugins](https://learn.chatgpt.com/docs/skills-and-plugins)
- [Skill controls](https://learn.chatgpt.com/docs/enterprise/skills)

## Non-negotiable design decisions

1. **KAPISCH remains the sole route controller.** A delegated capability
   supplies methodology, repository tooling, or an external integration for one
   bounded step. It cannot renormalize the top-level request, expand scope, or
   take ownership of later gates.
2. **The six-role catalog remains closed.** `architect`, `researcher`,
   `implementer`, `implementer-lite`, `mechanic`, and `reviewer` retain their
   existing meanings. A skill or plugin is not a seventh role, executor class,
   profile, or model tier.
3. **Role and risk selection precede capability selection.** Additional task
   detail or a specialist capability never lowers risk, review depth, required
   lenses, or regression coverage.
4. **Delegation is sequential.** At most one delegated step may be active. This
   change does not revive operational waves, parallel scheduling, worktree
   integration, or multi-writer execution.
5. **Authority cannot be laundered through a delegate.** A skill or plugin may
   not infer commit, push, merge, publish, send, destructive, dependency-install,
   configuration, authentication, or external-write authority.
6. **Installation and authentication are outside routing.** KAPISCH never
   installs, enables, authenticates, or reconfigures a skill, plugin, connector,
   or MCP server automatically.
7. **External side effects are split at the gate.** Preparation and preview are
   separate from execution. An external write or destructive action requires
   exact, explicit authority for its target and payload.
8. **Reviewer authority is not delegable.** Specialist review skills and tools
   may provide advisory evidence or a review lens, but only a fresh canonical
   `reviewer` invocation may approve or declare final readiness.
9. **Runtime provenance is recorded only when exposed.** Installed filenames,
   requested names, prompts, output wording, or controller claims do not prove
   that a runtime selected a particular skill or plugin. Unexposed receipts are
   recorded as `unavailable`.
10. **Python remains structural and read-only.** It validates schemas,
    references, digests, lifecycle, and factual consistency. It does not discover
    capabilities, choose a route, judge semantic fit, infer authority, dispatch,
    write artifacts, or approve work.

## Phase 0 — prerequisite and scope gate

Change 7 is currently marked as future work after standalone extraction, while
clean installation and marketplace acceptance remain pending in
[`acceptance.md`](acceptance.md).

Before implementation begins:

1. Complete a clean Codex installation, plugin discovery, and `$kapisch`
   invocation check, or explicitly record an approved deviation that permits
   Change 7 implementation before that acceptance is complete.
2. Treat clean installation as the hard engineering prerequisite. Marketplace
   publication may remain a release gate rather than a coding gate.
3. Record the supported surface matrix:
   - Codex desktop and CLI can exercise plugin-bundled skills and tools.
   - A surface without plugin support may still expose local skills and must
     degrade safely.
4. Preserve the roadmap statement that Change 7 does not depend on Change 4.
5. Treat Change 6 as independent presentation work; themes must not affect this
   routing contract.
6. Capture a fresh portable-package baseline immediately before the first
   implementation change.

### Approved deviation (2026-08-04)

The user approved implementing Change 7 before clean Codex installation,
plugin discovery, and `$kapisch` invocation acceptance complete. Clean-install
and marketplace import/installation acceptance remain separate manual release
gates recorded in `acceptance.md`; they are not coding gates for this change.
Phase 8 clean-environment scenarios are therefore recorded as pending manual
acceptance evidence, not executed in this environment.

## Phase 1 — establish the normative routing contract

Add `skills/kapisch/references/ecosystem-routing.md` as the sole normative owner
of ecosystem capability selection and delegated-step behavior.

### Selection procedure

The controller applies this order:

1. Normalize the user request and explicit KAPISCH controls.
2. Resolve workflow shape, task identity, scope, acceptance criteria, risk,
   logical role, review needs, and existing authority.
3. If the user explicitly names a skill or plugin, treat that name as a binding
   capability constraint. Do not silently substitute another capability.
4. Otherwise consider only capabilities visibly available in the current
   session. Never claim that the visible set is exhaustive.
5. Select the smallest capability whose documented purpose covers the bounded
   substep without changing its authority or acceptance boundary.
6. If multiple candidates imply materially different behavior, data access,
   external systems, or side effects, stop for one focused user decision.
7. Persist the delegated-step context and planned lifecycle before invocation.
8. Start only one delegated step, persist its observed result or exact error,
   and verify it before advancing.
9. Feed the verified result back into the existing KAPISCH role and workflow;
   the capability does not decide the next route.
10. Apply ordinary independent-review and final-readiness policy to the complete
    resulting delta.

### User controls and fallback

- Add an expert `ecosystem=auto|off` control. Ordinary natural language remains
  the normal interface.
- `ecosystem=off` prevents capability delegation but does not disable ordinary
  KAPISCH roles or built-in repository tools.
- An explicit skill or plugin mention overrides `auto` and is required when the
  user has mandated a particular methodology or integration.
- If an explicitly required capability is unavailable, block and report the
  missing capability and safe setup or selection action.
- If an automatically selected capability is unavailable, fall back to native
  KAPISCH execution only when the same approved outcome remains achievable
  without changing methodology, data boundary, or authority. Disclose the
  fallback.
- Do not install, enable, sign in to, or alter configuration as a fallback.
- Do not choose a capability from name similarity alone. Use its current
  documented description and exposed actions.

### Composition and recursion

Keep the route flat and explainable. A delegated capability cannot recursively
delegate the KAPISCH route or invoke `$kapisch`. If its documented procedure
requires another capability, the controller evaluates that need and records a
new sibling delegated step with its own context, authority, lifecycle, and
evidence.

### Contract files to update

| File | Required change |
| --- | --- |
| `skills/kapisch/SKILL.md` | Summarize ecosystem routing, fallback, authority, and approval boundaries; add the new normative owner. |
| `references/request-normalization.md` | Define explicit capability wording and `ecosystem=auto|off` precedence. |
| `references/role-resolution.md` | Separate logical roles/profiles from skill and plugin capabilities. |
| `references/dispatch.md` | State that delegation annotates an existing role assignment and never creates an executor class or tier. |
| `references/risk.md` | Preserve high-risk classification for external side effects, permissions, retries, and recovery. |
| `references/context-packages.md` | Define the delegated-step context package and data minimization rules. |
| `references/handoffs.md` | Own artifact placement, controller write ownership, and evidence delivery. |
| `references/execution-graph.md` | Define version-3 graph references to delegated steps. |
| `references/resume.md` | Define interrupted-step reconciliation and non-duplicating external-write recovery. |
| `references/review.md` | Require review of selection, authority, data exposure, results, fallback, and recovery; keep delegated review advisory. |
| `references/pressure-scenarios.md` | Add positive and negative Change 7 routing scenarios. |

Role documents may receive narrow clarifications that delegated methodology
cannot exceed each role's permissions. No new role file or `agents/*.toml`
profile should be added, and existing profile runtime settings should not change.

## Phase 2 — introduce durable delegation evidence

Use a separate route record so a graph-free workflow remains graph-free:

```text
.kapisch/runs/<task-id>/
└── delegations/
    ├── 00-route.toml
    └── D01/
        ├── 00-context.md
        └── 01-evidence.md
```

Delegation evidence is mandatory whenever KAPISCH uses an ecosystem capability,
including when the user selected `handoff=chat`. It is required for route
explanation, review, and safe resume; it is not an optional presentation
handoff.

### `delegations/00-route.toml`

Define a closed, versioned schema with these root fields:

- `version`;
- `task_id`;
- stable `route_id`;
- route `source_revision`;
- ordered `steps`;
- optional reverse-DNS `extensions` for runtime-specific receipts.

Each step records:

- stable `id` and non-negative `sequence`;
- `parent_node_id`, or the literal `unavailable` for graph-free work;
- `status = planned|started|completed|blocked|failed`;
- `selection_mode = explicit|automatic`;
- `capability_kind = skill|plugin-skill|plugin-tools`;
- `requested_capability` and `resolved_capability`;
- `source_plugin` when actually exposed, otherwise `unavailable`;
- maximum `effect_class`;
- `authority_mode` and an in-context `authority_ref`;
- context and evidence paths plus lowercase SHA-256 digests;
- source and resulting repository revisions;
- optional exposed runtime/tool receipts below reverse-DNS `extensions`.

The effect classes are:

- `repository-read`;
- `repository-write`;
- `external-read`;
- `external-write`;
- `destructive`.

The authority modes are:

- `request-scoped`: the already-approved request authorizes this bounded read or
  workspace action;
- `explicit-step`: the user explicitly approved this exact side-effect step.

One record represents one maximum effect class. Mixed-effect workflows split at
the authority boundary. For example, GitHub diagnosis, local repair, and posting
a PR comment are three sequential records rather than one opaque operation.

### `Dnn/00-context.md`

The controller writes a self-contained, focused context containing:

- parent task or graph node;
- exact bounded goal and expected output;
- requested and resolved capability;
- observable selection reason;
- accepted input paths, symbols, resources, and context references;
- data that may cross the repository boundary;
- authority already granted;
- actions that still require a gate;
- forbidden actions;
- success and verification checks;
- fallback or blocking behavior.

Do not include full conversation history, broad repository content, secrets, or
unrelated durable knowledge “just in case.”

### `Dnn/01-evidence.md`

The controller persists:

- lifecycle outcome;
- capability and tools actually observed;
- relevant returned data or bounded output references;
- local files or external resources affected;
- external operation IDs or URLs when exposed;
- exact commands/checks and results;
- resulting revision or unchanged-state evidence;
- omissions, errors, ambiguity, and retry safety;
- verification against the parent acceptance criteria.

Do not fabricate a separate agent or skill result when the skill was applied
inline. Record the actual observable operations and evidence.

The controller remains the sole writer of the route, context, and evidence
records. A delegated researcher, architect, reviewer, skill, or plugin tool does
not modify shared KAPISCH state merely to record its own result.

## Phase 3 — add manifest version 3

The current manifest parser uses a strict closed schema for versions 1 and 2.
Adding delegation fields silently to version 2 would change the meaning of an
existing version.

Implement version 3 as follows:

1. Preserve version-1 and version-2 parsing, defaults, fixtures, and migration
   behavior without rewriting them.
2. Make newly created durable graphs version 3 after Change 7 lands.
3. Add required policy `ecosystem_routing = "auto|off"`.
4. Add `delegation_ids = []` to each node.
5. Resolve each referenced ID against `delegations/00-route.toml`.
6. Require every referenced step's `parent_node_id` to match the owning graph
   node.
7. Prevent a step from being referenced by multiple nodes.
8. Prevent an implementation node from completing while any required delegated
   step is planned, started, blocked, failed, missing, stale, or invalid.
9. Permit review/final nodes to reference only `repository-read` or
   `external-read` advisory steps.
10. Keep a review/final node's decision bound to its existing canonical reviewer
    invocation and result artifact.
11. Do not change node-status transitions, deterministic node selection,
    parallelism sentinels, assignment semantics, batches, or logical model tiers.

Version 1 and 2 manifests must reject version-3-only fields rather than silently
adopting new behavior. Reading an old manifest must never create a route record
or delegation fields.

## Phase 4 — extend the validator

Add `kapisch_validation/delegations.py` plus only the supporting dataclasses and
helpers needed for structural validation.

### Structural checks

Validate:

- supported route version and closed root/step schemas;
- required fields, correct scalar/list types, and allowed enums;
- stable delegation-ID grammar;
- unique step IDs and unique sequence values;
- ordered, sequential lifecycle with at most one `started` step;
- no later step starting or completing before every preceding step completes;
- task-directory path containment;
- rejection of symlinked evidence;
- required UTF-8 context and evidence files;
- lowercase SHA-256 format and exact byte-digest matches;
- completed steps having a resolved capability and complete evidence;
- blocked/failed terminal steps retaining diagnostic evidence;
- external-write/destructive steps having `authority_mode=explicit-step` and a
  valid authority reference;
- graph parent ownership, unique graph references, and node/step lifecycle
  consistency;
- read-only effect classes for review/final delegations.

### Explicit validator boundary

Do not implement:

- capability discovery or installation;
- description matching or semantic selection;
- request parsing or route planning;
- user-authority inference;
- plugin, connector, tool, or agent dispatch;
- external-system reconciliation;
- semantic output sufficiency;
- reviewer identity or approval authority.

### CLI behavior

- Preserve the current default durable validator behavior.
- Add `--scope delegations` for graph-free delegation records.
- During version-3 durable validation, automatically validate the route record
  and every graph reference.
- Keep deterministic `text|json` output, stable error ordering, exit status 0/2,
  standard-library-only Python 3.11 support, and read-only operation.

## Phase 5 — implement resume and side-effect recovery

Extend `references/resume.md` and structural validation with these controller
rules:

1. `planned` may start once after the capability and authority are revalidated.
2. `started` is unresolved. Resume inspects the effect class, context, evidence,
   repository state, and exposed external operation identifiers before deciding
   anything.
3. A read-only step may be repeated only when doing so is safe and the record
   clearly identifies the new attempt.
4. A repository-write step follows existing Git/diff reconciliation and must not
   infer completion from a summary alone.
5. An external-write or destructive step is never blindly retried. Reconcile
   read-only against the external system when already authorized and possible;
   otherwise block for user direction.
6. A completed step is reusable only while its context, evidence digest,
   capability binding, revisions, and resulting state remain current.
7. A blocked or failed step does not silently select a substitute capability.
   Replacement requires a new explicit or automatic selection record and, when
   material, renewed user approval.
8. Repeated resume against unchanged evidence returns the same next action and
   creates no duplicate tool call or external effect.

## Phase 6 — test-first implementation and fixtures

Add contract and validator tests before treating prose as implemented behavior.

### Positive fixtures

1. Graph-free explicit instruction-only skill.
2. Graph-free automatically selected read-only plugin skill.
3. Version-3 durable implementation node with one completed delegation.
4. Multiple sequential delegations with distinct authority classes.
5. External read followed by an explicitly approved external write.
6. Review node consuming read-only advisory specialist evidence while the
   canonical reviewer owns the decision.
7. Valid completed delegation accepted idempotently on resume.
8. Existing version-1 and version-2 fixtures unchanged and still valid.

### Negative fixtures and scenarios

1. Explicitly required capability unavailable.
2. Unknown route field, capability kind, effect class, authority mode, or
   lifecycle.
3. Duplicate delegation ID or sequence.
4. Path traversal, symlink, missing context/evidence, invalid UTF-8, or digest
   mismatch.
5. Completed step with `resolved_capability=unavailable`.
6. External write or destructive action without `explicit-step` authority.
7. A later step started/completed while an earlier step is unresolved.
8. Graph parent mismatch, reused step ID, or orphaned required reference.
9. Completed graph node with an incomplete, blocked, or failed delegation.
10. Reviewer/final delegation attempting a write.
11. Delegation to KAPISCH itself or attempted recursive route ownership.
12. Automatically installing/authenticating an unavailable capability.
13. Interrupted external write being blindly repeated.
14. Requested plugin name or controller prose being treated as runtime proof.
15. Specialist review output being treated as approving review/final evidence.
16. A capability expanding files, behavior, data boundary, or external action
    beyond the approved context.

### Test locations

- Add `tests/kapisch_validation/test_delegations.py`.
- Extend `test_manifest.py`, `test_transitions.py`, `test_cli.py`,
  `test_hardening.py`, and `test_extraction_acceptance.py` where their existing
  ownership applies.
- Add valid and invalid fixture directories under
  `tests/kapisch_validation/fixtures/`.
- Extend `scripts/test_portable_package.py` with one graph-free delegation
  validation and one version-3 durable validation from the isolated copy.
- Preserve the existing legacy-migration byte-comparison tests.

## Phase 7 — public documentation and packaging

Update:

- `README.md` with one explicit-delegation example, one automatic read-only
  example, one external-write gate, and one unavailable-capability fallback;
- `docs/acceptance.md` with automated and manual ecosystem-routing coverage;
- `docs/compatibility.md` with manifest-v3 compatibility and confirmation that
  legacy migration remains byte-preserving;
- `CONTRIBUTING.md` with the rule that delegation changes need fixtures and may
  not add a semantic resolver;
- `.codex-plugin/plugin.json` descriptions only as necessary to describe the
  new capability accurately;
- `CHANGELOG.md` for the eventual next minor release.

Do not add hard dependencies on named third-party skills or plugins to the
plugin manifest. Examples are non-normative and must not create a preferred
vendor registry. Keep the plugin's own capability list free of a bundled MCP
server unless a separately approved future change adds one.

## Phase 8 — clean-environment acceptance

Exercise these scenarios in a clean installed Codex environment:

1. Explicitly invoke an installed instruction-only skill through KAPISCH.
2. Automatically select a plugin-bundled read-only skill.
3. Use an external-read connector with only the focused context.
4. Prepare an external write, stop at the gate, approve the exact target and
   payload, execute it, and persist the external result.
5. Name an unavailable plugin and verify fail-closed behavior.
6. Run on a surface without plugin support and verify disclosed native fallback
   or a precise blocker.
7. Install a plugin and verify its capability only in a fresh session when the
   runtime requires that refresh.
8. Interrupt a started external-write step and verify resume does not duplicate
   it.
9. Use a specialist review capability and verify that it remains advisory until
   the configured KAPISCH reviewer produces canonical evidence.
10. Verify that KAPISCH never installs, authenticates, commits, pushes,
    publishes, sends, or performs destructive work without the corresponding
    explicit authority.

Record exposed capability identifiers, surface, plugin/skill availability,
context and evidence paths, human gates, exact checks, and outcomes. Record
unexposed runtime receipts as `unavailable`; do not infer them.

## Phase 9 — integrated review, final readiness, and roadmap status

Treat this as high-risk workflow-policy work because it introduces external
data/action boundaries, retry behavior, and recovery rules.

1. Run the focused unit suite and portable-package acceptance.
2. Perform a fresh configured whole-branch review of the actual delta.
3. Require an Invariant evidence matrix covering:
   - capability selection and fallback;
   - role/risk preservation;
   - context and data minimization;
   - local/external authority;
   - normal, failed, interrupted, and resumed lifecycle;
   - duplicate external-effect prevention;
   - graph-free and durable consumers;
   - version-1/version-2 compatibility;
   - reviewer/final non-delegability;
   - validator boundary and negative scenarios.
4. Address only explicitly authorized review findings and re-review every fix.
5. Run a separate fresh final-readiness invocation against the complete current
   state.
6. After acceptance and readiness exist, update the Change 7 roadmap status and
   review that status-changing delta again. Do not claim that the prior
   readiness automatically covers a later status edit.
7. Keep commit, push, marketplace publication, and release as separately
   authorized actions.

## Definition of done

Change 7 is complete only when all of the following are true:

- `ecosystem-routing.md` is the single normative owner and all related contracts
  link to it without duplicating or contradicting its rules;
- explicit and automatic capability selection are explainable and fail closed;
- graph-free and durable delegated steps have inspectable, digest-bound evidence;
- manifest version 3 cross-validates graph nodes and delegated steps;
- version-1 and version-2 manifests and compatibility defaults remain unchanged;
- legacy migration remains explicit, byte-preserving, source-retaining, and
  free of new legacy writes;
- the validator remains Python 3.11 standard-library-only, deterministic,
  structural, and read-only;
- external writes and destructive actions require exact explicit authority;
- interrupted external effects cannot be repeated without reconciliation;
- delegated methodology never changes role, risk, review depth, model tier, or
  approval authority;
- no new role, agent profile, MCP server, daemon, database, scheduler, worktree
  manager, semantic router, registry, or hard plugin dependency was introduced;
- existing and new unit tests plus portable isolation pass;
- representative clean-environment skill/plugin routes pass;
- a configured independent whole-branch reviewer approves the complete delta;
- a distinct final-readiness invocation returns `ready` for the current state;
- the completed roadmap status itself is covered by fresh evidence.

## Explicit non-goals

- Building a GitHub client, CI platform, retrieval service, connector, or MCP
  server inside KAPISCH.
- Installing, enabling, authenticating, updating, or removing other plugins or
  skills.
- Persisting a vendor catalog, capability ranking, semantic matching database,
  or preferred-plugin list.
- Delegating controller ownership, risk classification, approval, or final
  readiness.
- Parallel skill execution, multi-agent scheduling, worktree integration, or
  automatic conflict resolution.
- Automatic commit, push, PR creation, merge, release, publication, sending, or
  destructive execution.
- Cost, token, cache, latency, or savings claims before Change 4 establishes
  measured evidence.
