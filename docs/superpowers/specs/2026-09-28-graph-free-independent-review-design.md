# Graph-Free Independent Review Workflow Design

**Date:** 2026-09-28
**Status:** Approved by user
**Target:** KAPISCH Pi and canonical workflow contract

## Summary

Add `workflow=review` as a first-class, graph-free path for an independent review request. KAPISCH dispatches one fresh `kapisch-reviewer` context, which inspects the requested repository scope and returns evidence-backed findings. The invoking session/orchestrator evaluates those findings and owns any approval or next action.

This path does not create or require a durable execution graph, task manifest, review-invocation artifact, or workflow lifecycle. It is distinct from a review step within `task` or `milestone`, whose existing durable evidence and approval rules remain unchanged.

## Goals

- Allow a user to request an independent fresh-context review without starting a durable workflow.
- Give standalone review an explicit `review` workflow value, rather than an exception to graph-free task delegation rules.
- Preserve the reviewer’s read-only, evidence-first behavior and the parent session’s decision authority.
- Return findings with severity, confidence, location, impact, evidence, and suggested fix/regression coverage.
- Keep existing advisory, task, and milestone semantics unchanged.

## Non-goals

- Do not create or mutate a durable execution graph or persist KAPISCH review evidence for standalone review.
- Do not have the reviewer approve, reject, or declare ready; the parent/orchestrator judges the findings.
- Do not alter reviewer behavior when invoked inside durable task or milestone workflows.
- Do not expand graph-free delegation to researcher, architect, implementer, or arbitrary plugin capabilities.
- Do not implement review automation, repair, or remediation.

## Behavior

1. A request whose intent is independent review selects `workflow=review` (or an explicit `workflow=review` control). It must not be normalized as task or milestone merely to enable reviewer dispatch.
2. The controller sends one bounded request to a fresh `kapisch-reviewer` context, including the repository and requested review target/scope and any explicit review criteria.
3. Reviewer inspects that scope read-only and returns findings only. Each finding includes a stable identifier, severity (P1/P2/P3, with P0 only for critical issues), confidence, location, trigger/cause, impact, evidence, and suggested fix and regression coverage. If no findings, say so and state scope and verification performed/omitted.
4. Reviewer does not emit an approval/readiness decision or require workflow evidence artifacts. Parent/orchestrator remains responsible for judging findings and deciding what to do next.
5. Standalone review creates no graph, manifest, durable run directory, or review evidence artifacts. A later implementation request is a separate request and follows its own workflow selection.
6. Existing reviewer calls inside task/milestone workflows continue to use the canonical invocation and persisted-result contracts.

## Affected contract surfaces

- Canonical skill: workflow control vocabulary, workflow selection, and description of graph-free review behavior.
- Request normalization: route review-only requests to `review`; retain task’s no-delegation rule and all other capability constraints.
- Pi adapter: map `review` to one fresh `kapisch-reviewer` dispatch without starting workflow orchestration or creating graph artifacts.
- Reviewer agent: distinguish standalone findings-only output from durable workflow review, without changing the existing in-workflow contract.
- Regression tests: assert workflow selection and dispatch, absence of durable-graph requirements, findings-only standalone reporting, and unchanged task/milestone behavior.

## Acceptance criteria

- `review` appears as a documented workflow value with explicit graph-free semantics.
- Standalone independent review dispatches `kapisch-reviewer` in fresh context and returns findings to the invoking session.
- Standalone review does not require or create durable workflow artifacts and does not report approve/ready.
- Durable task/milestone review requirements remain intact.
- Tests pin both new behavior and unchanged workflow boundaries.
