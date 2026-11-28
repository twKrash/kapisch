# Early Reviewer Methodology Slice Implementation Plan

> **For agentic workers:** Use this plan task-by-task. No commit, push, merge, release, or deployment is authorized.

**Goal:** Deliver an owner-prioritized early WS-3.1 slice that makes the currently supported `kapisch-reviewer` independently useful for documentation, cross-document, code, and implementation review while preserving existing review rigor and leaving the rest of WS-3.1 and the approved WS-4 scope intact.

**Architecture:** Keep one canonical Markdown reviewer baseline and reusable Markdown methods; preserve the current Pi/Codex packaging paths as adapters to that shared source. The baseline owns target discovery, evidence, authority, Decision Challenge, iterative method selection, and reporting. It loads a conditional method only when its trigger is present or discovered, using ordinary harness file/search tools. No registry, selector engine, new agent, workflow, Kernel state, or mandatory context extension is added.

**Tech Stack:** Markdown product/reviewer instructions; existing Python package/test mechanisms; existing Pi agent generation and test mechanisms; existing Codex plugin packaging and acceptance tests.

**Spec:** `docs/superpowers/specs/2026-10-25-kapisch-product-realignment-design.md` §§5.4, 5.8–5.14, 6.7, and acceptance scenarios; owner-approved design and clarifications in the task request. Product-spec and roadmap amendments in Task 4 record this early slice without replacing the governing detailed requirements.

## Global Constraints

- Review is independent judgment; standalone review returns findings only and is neither human authorization nor permission to act.
- Documentation and cross-document collections are first-class targets; general document review does not require a Git diff.
- Decision Challenge is mandatory in the standalone reviewer baseline for material decisions, including consequential decisions implicit in code, configuration, tests, or observed behavior. Legacy plugin V3/V4 reviews retain their self-contained profile procedure and existing skill/transport contracts; Core-backed reviews use validated retained CoreBundle role/policy contracts. External methodology retrieval remains deferred until its content/version can be bound.
- Mutation and Side-effect Justification is mandatory whenever reviewed work introduces or materially affects a write, update, deletion, state transition, or external effect.
- Standalone method selection is iterative: newly discovered decisions, dependencies, risks, or effects can trigger additional method retrieval and application during a review. Durable review retains its existing legacy plugin or retained-Core instruction path until external methods are durably bound.
- Preserve the eight portable lens families and existing severity, confidence, causal-scope, risk-depth, positive/negative verification, compatibility, concurrency, persistence, isolation, audit, migration, and recovery methods.
- User focus supplements applicable mandatory review; it cannot suppress material issues outside that focus or prevent activation of a method triggered by later discovery. Existing explicit/automatic lens semantics may be preserved only where they do not suppress mandatory checks.
- Findings require concrete scope-linked evidence and supported causality/consequences. No finding is required when the solution is correct, proportionate, and adequately verified.
- Use ordinary native file/search tools; optional context management is never a hard prerequisite. Report inaccessible required evidence or instructions as a limitation.
- Keep the approved WS-4 design and current roadmap placement of the remaining portable report, review gates, conformance, and adapter work. WS-13/14 remain non-gating for WS-4.
- No unrelated runtime, schema, adapter, dependency, workflow-engine, or Kernel changes. No commit or external action.

## Review Focus

1. **Non-diff document scope:** A specification/plan or artifact collection with no Git diff must bind its identity, status, audience, governing sources, and evidence and be reviewable; test with a documentation-only acceptance case.
2. **Risk discovered after initial selection:** A review that discovers a new dependency, material decision, or mutation must retrieve and apply the newly relevant method without reloading the whole corpus; test dynamic method selection.
3. **Implicit decision:** A consequential behavior encoded only in code/configuration/tests must be challenged as a decision; test an implementation that faithfully follows a materially flawed undocumented choice.
4. **Ownership and negative invariant:** A write affecting another tenant/domain or an unauthorized actor must be detected, and successful-path-only tests must not be treated as proof of isolation; test cross-boundary and negative-evidence cases.
5. **Correct reference case:** A simple, safe, adequately verified change must permit an empty findings report; test false-positive restraint and rejection of subjective alternatives.

---

## Existing coverage and gaps

The current Codex reviewer package is not a blank slate: `plugins/kapisch/skills/kapisch/references/review.md` and `risk.md` already provide deep diff-oriented review procedures, risk/depth selection, dynamic recomputation of derived lenses when focus is automatic, semantic bundles, causal findings, behavioral/invariant evidence matrices, and positive/negative verification. `plugins/kapisch/tests/kapisch_validation/test_review_contracts.py` and the pressure-scenario suite preserve important parts of that behavior. Retain these methods and tests.

The bounded gaps are general non-diff documentation and cross-document reviews as first-class target types; the six §5.14 methods and the two new cross-cutting procedures (Decision Challenge and Mutation and Side-effect Justification) as operational, retrievable instructions for standalone review; and dynamic retrieval beyond existing lens recomputation. Legacy plugin workflows retain the complete embedded procedure and existing skill/transport contracts; Core-backed workflows retain their validated CoreBundle authority. Neither loads unbound external methodology. Existing project-understanding material covers repository discovery, not a full replacement for these standalone reviewer procedures. Existing structural tests do not establish LLM behavioral quality or actual packaged-harness behavior.

## File map

- `plugins/kapisch/skills/kapisch/references/review.md` — the canonical standalone reviewer procedure across current harnesses: discovery, first-class target binding, mandatory Decision Challenge, iterative method-selection/retrieval, evidence and findings. Core role/policy surfaces own durable target binding and review authority; standalone prompts retrieve this baseline rather than duplicating its methodology.
- `plugins/kapisch/skills/kapisch/references/risk.md` — existing risk-depth/lens selection rules; retain and align them with new target types and iterative discovery without weakening existing triggers.
- `plugins/kapisch/skills/kapisch/references/reviewer-methodologies/` — new selectively retrievable Markdown methods: `mutation-and-side-effect-justification.md` and one file each for semantic consistency, dependencies/traceability, authority/ownership, temporal/lifecycle consistency, proof obligations/evidence quality, and executability/feasibility/simplicity.
- `plugins/kapisch/agents/kapisch-reviewer.toml`, `plugins/kapisch/roles/reviewer.md`, `core/contracts/roles/reviewer.md`, and `core/contracts/policy/review.md` — thin harness/role and policy surfaces; remove conflicting approval language and avoid maintaining competing methodology prose. Preserve versioned V4 transport and integrated-review behavior outside standalone mode.
- `harnesses/pi/scripts/generate-agents.ts`, `harnesses/pi/agents/kapisch-reviewer.md`, and `harnesses/pi/tests/generated-agents.test.ts` — existing Pi generated reviewer adapter and freshness/discoverability checks; extend the existing packaging path to make the shared baseline and method files accessible without copying independent prompt text.
- `harnesses/pi/skills/kapisch/SKILL.md`, `harnesses/pi/tests/package.test.ts`, `plugins/kapisch/scripts/test_portable_package.py`, and relevant package tests — verify reviewer invocation and method-resource availability through existing distribution mechanisms.
- `plugins/kapisch/tests/kapisch_validation/test_review_contracts.py` — structural contracts for standalone-only baseline retrieval, iterative selection, preservation of existing review rigor, and package/resource references.
- `plugins/kapisch/tests/kapisch_validation/fixtures/reviewer-methodology/` — paired defective and correct document/code review cases with expected finding/no-finding rationales; these are LLM behavioral evaluation inputs, not deterministic Python conformance claims.
- `plugins/kapisch/docs/acceptance-reviewer-methodology.md` — concise acceptance/evidence record separating structural checks from live-model outcomes and limitations.
- `docs/superpowers/specs/2026-10-25-kapisch-product-realignment-design.md` — amend only the governing reviewer-methodology and delivery-order requirements needed to record Decision Challenge, Mutation and Side-effect Justification, and this owner-prioritized early slice; do not redesign WS-4.
- `docs/superpowers/product-realignment-tracker.md` and `docs/superpowers/plans/2026-11-05-kapisch-execution-order-amendment.md` — record the bounded early delivery, completion evidence, remaining WS-3.1 work, and unchanged later placement/dependencies.

## Task 1: Reconcile the reviewer baseline and harness surfaces

**Files:** existing baseline/reviewer sources listed above; no new architecture or workflow files.

- [x] Re-read current Codex reviewer prompt, Pi generator output, canonical Core role/policy, review/risk/severity methods, and existing review acceptance tests. Record the current owner of each substantive rule before editing; do not discard already-tested review behavior.
- [x] Refactor the canonical Markdown review baseline to make document/document-collection targets first-class and define target/scope/status/audience/governing sources/evidence/limitations discovery without requiring a diff.
- [x] State Decision Challenge in the baseline as mandatory, covering explicit and implicit decisions, validity, constraints/invariants, alternatives only when materially safer/simpler/feasible, completeness, and decision-to-implementation/verification fidelity.
- [x] Define iterative discovery: after every material newly discovered decision, dependency, effect, ownership boundary, persistence/concurrency issue, or risk, identify and retrieve any newly applicable method before concluding. Do not reload unrelated methods or require a registry/engine.
- [x] Align authority/output language across role and policy files: standalone review reports findings and limitations only; findings do not approve, authorize, or supersede human decisions. Keep integrated V4 contract semantics distinct and unchanged.
- [x] Extend structural tests to fail if document-only review requires a diff, Decision Challenge is optional, implicit implementation decisions are excluded, standalone approval authority returns, new discoveries cannot activate methods, or user focus suppresses applicable mandatory checks.
- [x] Run the focused review-contract tests and confirm legacy code-review matrix, causal findings, risk depth, and severity assertions still pass.

## Task 2: Add selectively loaded methodologies and balanced reference cases

**Files:** seven conditional Markdown methods under `plugins/kapisch/skills/kapisch/references/reviewer-methodologies/`; mutation method; existing review/risk baseline; fixture directory; acceptance evidence.

- [x] Add six §5.14 methods as separate Markdown files, each documenting when to load, relevant evidence, checks, and how to report limitations/findings. Preserve the specified procedure for semantic consistency, traceability, authority, temporal/lifecycle consistency, proof/evidence, and feasibility/simplicity.
- [x] Add Mutation and Side-effect Justification as a distinct conditional method. Trigger it for material new or affected writes, updates, deletions, state transitions, or external effects, including indirect effects; follow reviewed changes and materially affected consumers only. Cover necessity, ownership, authorization/scope, timing/retries/concurrency/partial effects when relevant, cross-domain impact, and positive/negative verification.
- [x] Make standard file-reading/search the documented retrieval path. A missing method file or failed retrieval is an explicit limitation; never silently claim full coverage or replace it with an unverified summary.
- [x] Add paired reference cases: flawed and correct decisions; cross-document stale/contradictory authority/dependency/proof cases; unnecessary or broad/unauthorized/cross-tenant mutation; successful-path-only tests missing a negative invariant; and a correct, simple, adequately tested solution whose expected report is empty.
- [x] Each case includes the target/scope, relevant evidence, intended method triggers (including any discovered after initial classification), expected finding class or explicit no-finding rationale, and disallowed speculative/subjective findings.
- [x] Extend structural tests to assert method trigger coverage, independent selective files, iterative activation, preservation of the eight lenses, and balanced positive/negative reference cases. Do not claim these source assertions establish LLM behavior.
- [x] Run focused methodology structural tests and inspect the fixtures for supported causal scenarios and proportionality.

## Task 3: Adapt existing Pi/Codex packaging and verify usability

**Files:** `plugins/kapisch/agents/kapisch-reviewer.toml`, `harnesses/pi/scripts/generate-agents.ts`, generated Pi reviewer, Pi/plugin packaging tests and docs.

- [x] Reduce harness-specific reviewer text to invocation/permissions/transport and pointers to shared Markdown; do not restate or independently maintain methodology.
- [x] Use existing package and Pi generation mechanisms to expose the canonical baseline and conditional method files at predictable locations the reviewer can read with ordinary native tools. Do not add a mandatory extension, external context server, new registry, or dynamic selection engine.
- [x] Ensure reviewer instructions retrieve only baseline plus currently applicable methods, and can retrieve more after discovery; ensure missing package assets cause a disclosed limitation rather than silent fallback.
- [x] Regenerate Pi agent artifacts using the existing generator and verify freshness, expected agent discoverability, and plugin package inclusion with existing tests. Do not edit generated files by hand.
- [ ] Verify separately that the supported Pi and Codex reviewer invocation surfaces are present and their read/search capabilities can reach the shared resources. Static artifact checks prove packaging structure only, not real model behavior.
- [x] Run focused generator/package tests and inspect the produced assets for accidental embedded copies of the full method corpus or stale/duplicated instructions.

## Task 4: Align product requirements and roadmap status

**Files:** product design spec, product realignment tracker, execution-order amendment.

- [x] Update the governing product spec with the mandatory Decision Challenge and mutation-method trigger/coverage requirements; document dynamic selection and implicit implementation decisions; retain the eight lenses and six existing §5.14 methods without creating new top-level lens families.
- [x] Record the owner-prioritized early reviewer-methodology slice before WS-4 implementation planning, with its bounded acceptance evidence and exact limits.
- [x] Update tracker status only for the accepted early slice actually verified. Keep remaining portable ReviewReport, integrated review gates, deterministic WS-10 conformance, and production adapters at their existing roadmap placement; do not mark all WS-3.1 done.
- [x] Preserve the approved WS-4 design and its dependencies; explicitly retain WS-13 and WS-14 as non-gating for WS-4. Do not make this slice depend on Kernel, Project Context, modular Skills collection, or future adapters.
- [x] Cross-check spec, tracker, and execution order for authority, status, dependency, and temporal consistency; avoid duplicating the detailed normative method text in roadmap documents.

## Task 5: Verify, evaluate, and independently review

**Files:** acceptance record and affected instructions/packages/tests only.

- [x] Run focused Python review-contract/package tests and the relevant Pi generated-agent/package tests. Run repository-required narrow lint/type checks for modified code. Do not broaden to unrelated full-suite work without a failure or risk reason.
- [x] Run the documentation-only, cross-document, decision, mutation/ownership, verification-adequacy, code-regression, proportionality, selective-loading, and supported-harness usability reference cases through the supported Pi reviewer invocation. Record model/runtime and exact scope in the acceptance record; do not infer behavior from static prompts or generated files.
- [x] If live harness/model execution is unavailable, record that explicit limitation and report structural/package verification separately. Do not treat one invocation as deterministic conformance or as proof of consistent LLM behavior.
- [x] Obtain a fresh, independent, read-only review of the complete change. The reviewer examined code/docs and all tracked/untracked changes, confirmed KRM-002/KRM-006 resolved, and found no new findings. The review remained findings-only; no approval or readiness was issued. Durable method binding and live durable dispatch/restart remain deferred.
- [x] Update the acceptance evidence with exact checks run, omitted checks, live-harness status, independent-review findings, and unresolved risks. Keep this task in progress if verification or review leaves a material issue unresolved.

## Completion criteria

The slice is complete only when the baseline, conditional methods, package access, roadmap alignment, focused structural tests, and independent review are verified; balanced behavior cases are recorded; and any live-harness evaluation is accurately distinguished from structural evidence. Remaining WS-3.1 deliverables retain their prior roadmap status. No commit or external action is part of this plan.
