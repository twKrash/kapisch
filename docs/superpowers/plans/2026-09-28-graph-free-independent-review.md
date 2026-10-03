# Graph-Free Independent Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- []`) syntax for tracking.

**Goal:** Add graph-free `workflow=review` dispatch to one fresh `kapisch-reviewer`, returning findings for the orchestrator to judge.

**Architecture:** Extend canonical workflow normalization and the Pi adapter’s dispatch contract. Standalone review is explicitly tagged so the shared reviewer profile returns findings only; durable task/milestone reviews retain existing evidence and decision contracts. No runtime code or durable graph schema changes are expected.

**Tech Stack:** Markdown contracts, generated Pi agent markdown, TypeScript `node:test`, Bun, Python unittest, release metadata.

**Spec:** `docs/superpowers/specs/2026-09-28-graph-free-independent-review-design.md`

## Global Constraints

- Standalone review is graph-free and creates no durable workflow artifacts.
- Standalone reviewer is read-only, runs in a fresh context, and returns findings; parent/orchestrator judges them.
- Task and milestone workflow review behavior and evidence requirements remain unchanged.
- Keep the six-role catalog and validator schemas unchanged; add no dependency.
- Plugin behavior changes require an intentional semantic-version bump across the Codex plugin, Python package, and Pi package, plus a current changelog entry.

## Review Focus

- Review-only intent accidentally routed to task/milestone → regression test proves explicit review selection is independent and graph-free.
- Standalone reviewer emits a formal decision or requests durable artifacts → tests pin findings-only behavior, unconditional scope/coverage-gap reporting, and preserve durable-mode instructions.
- Graph-free task delegation broadens unintentionally → regression assertions retain task’s no-delegation and milestone durable behavior.
- Generated Pi reviewer drifts from canonical profile → generator check and existing generated-agent tests.
- Working-tree review omits staged, unstaged, or in-scope untracked file content → explicit procedure/test covers each source.
- Plugin/Pi version metadata drifts → version-lockstep and version-check scripts.

## Task Structure

### Task 1: Add graph-free review routing and contract tests

**Files:**
- Modify: `plugins/kapisch/skills/kapisch/SKILL.md`
- Modify: `plugins/kapisch/skills/kapisch/references/request-normalization.md`
- Modify: `plugins/kapisch/skills/kapisch/references/review.md`
- Modify: `plugins/kapisch/skills/kapisch/references/handoffs.md`
- Modify: `plugins/kapisch/skills/kapisch/references/pressure-scenarios.md`
- Modify: `harnesses/pi/skills/kapisch/SKILL.md`
- Test: `harnesses/pi/tests/package.test.ts`

**Interfaces:**
- Consumes: approved standalone-review design.
- Produces: documented `workflow=review` value and Pi dispatch contract selecting one fresh `kapisch-reviewer`, with no graph/artifact creation.

- [x] **Step 1: Write a failing regression test** asserting canonical workflow value/selection, Pi reviewer dispatch and fresh context, findings-only standalone result, and absence of graph/artifact requirements; also assert task and milestone contracts remain intact.
- [x] **Step 2: Run `bun test harnesses/pi/tests/package.test.ts` and confirm it fails on the missing `review` contract.**
- [x] **Step 3: Update the canonical workflow and normalization/review contracts, then Pi adapter instructions with the minimal graph-free route and standalone mode marker.**
- [x] **Step 4: Run the focused test and confirm it passes.**

### Task 2: Add standalone findings-only reviewer behavior and release metadata

**Files:**
- Modify: `plugins/kapisch/agents/kapisch-reviewer.toml`
- Regenerate: `harnesses/pi/agents/kapisch-reviewer.md` using `bun harnesses/pi/scripts/generate-agents.ts`
- Test: `harnesses/pi/tests/package.test.ts` or a focused reviewer-contract test in `harnesses/pi/tests/`
- Modify: `plugins/kapisch/.codex-plugin/plugin.json`
- Modify: `plugins/kapisch/pyproject.toml`
- Modify: `harnesses/pi/package.json`
- Modify: `plugins/kapisch/CHANGELOG.md`
- Modify: `README.md` and `plugins/kapisch/README.md` for the new candidate version.
- Modify: `tests/test_marketplace.py` to track synchronized version and candidate provenance.
- Modify: `plugins/kapisch/tests/kapisch_validation/fixtures/deterministic-generated-artifacts/expected-sha256.json` for the changed canonical reviewer-profile digest.
- Create/update: `plugins/kapisch/docs/acceptance-windows-v2.3.0.md` and `plugins/kapisch/docs/acceptance.md` with candidate status and reproducible runtime-tree evidence.

**Interfaces:**
- Consumes: `workflow=review` packet from Task 1, tagged as standalone.
- Produces: conditional reviewer instructions: standalone binds the requested scope, inspects staged/unstaged/relevant untracked worktree contents, reports scope, verification, and coverage gaps even when findings exist, and makes no approve/ready decision; existing durable invocations retain current canonical evidence/decision behavior.

- [x] **Step 1: Add failing assertions for standalone-vs-durable reviewer instructions; run the focused Pi test and confirm expected failure.**
- [x] **Step 2: Add the conditional standalone behavior to the canonical reviewer source and regenerate the Pi agent; keep generated content sourced from TOML.**
- [x] **Step 3: Bump shared version from 2.2.0 to 2.3.0 and add a changelog entry describing graph-free independent review.**
- [x] **Step 4: Run focused Pi tests and `bun run check:generated`; confirm pass.**
- [x] **Step 5: Run `python scripts/check_plugin_version.py --base HEAD`; it exits 0 but reports `material=false` because this worktree is uncommitted, so source-tree classification remains unverified until a commit range exists.**

## Final Verification

- [x] Pi tests: 11 passed; generated-agent check passed from export of runtime tree `594cb899b855ef3489204a26885ee3595eefde27`.
- [x] KAPISCH validation: 490 passed; portable-package check passed from same exported tree.
- [x] Root release-metadata suite: 18 passed in candidate worktree; `git diff --check` passed.
- [x] Fresh final code review found no issues. CI, native Windows/live marketplace acceptance, final release SHA, and committed-range version classification remain pending.
