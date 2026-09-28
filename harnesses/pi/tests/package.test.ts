import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = new URL("../../../", import.meta.url);
const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("Pi package exposes skill and pi-subagents agents declaratively", () => {
  assert.equal(pkg.pi?.skills?.includes("./skills/kapisch"), true);
  assert.ok(pkg["pi-subagents"]?.agents?.includes("./agents") || pkg.pi?.subagents?.agents?.includes("./agents"));
  assert.equal(pkg.pi?.extensions, undefined);
  assert.equal(pkg.version, JSON.parse(readFileSync(new URL("../../../plugins/kapisch/.codex-plugin/plugin.json", import.meta.url), "utf8")).version);
  assert.equal(pkg.version, readFileSync(new URL("../../../plugins/kapisch/pyproject.toml", import.meta.url), "utf8").match(/^version = "([^"]+)"/m)?.[1]);
});

test("standalone review workflow is graph-free and delegates findings only", () => {
  const canonical = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const normalization = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/request-normalization.md", import.meta.url), "utf8");
  const review = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/review.md", import.meta.url), "utf8");
  const handoffs = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/handoffs.md", import.meta.url), "utf8");
  const scenarios = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/pressure-scenarios.md", import.meta.url), "utf8");
  const adapter = readFileSync(new URL("../skills/kapisch/SKILL.md", import.meta.url), "utf8");

  assert.match(canonical, /auto\|advisory\|task\|review\|milestone/);
  assert.match(canonical, /workflow=review[\s\S]*?graph-free[\s\S]*?kapisch-reviewer/);
  assert.match(normalization, /workflow=review[\s\S]*?independent review/);
  assert.match(review, /standalone graph-free review[\s\S]*?findings only[\s\S]*?parent\/orchestrator/i);
  assert.match(review, /do not gate a completed[\s\S]*?standalone findings-only response/i);
  assert.match(handoffs, /standalone `workflow=review`[\s\S]*?no canonical reviewer[\s\S]*?invocation or result artifacts/i);
  assert.match(handoffs, /approving review or final still requires its canonical invocation[\s\S]*?result artifacts/i);
  assert.match(scenarios, /workflow=review[\s\S]*?findings only[\s\S]*?`mode=review`[\s\S]*?`mode=final`[\s\S]*?pre-dispatch[\s\S]*?canonical invocation/i);
  assert.match(adapter, /workflow=review[\s\S]*?fresh[\s\S]*?kapisch-reviewer[\s\S]*?standalone/);
  assert.match(adapter, /review_mode=standalone/);
  assert.match(normalization, /workflow=task[\s\S]*?does not support delegation/);
  assert.match(canonical, /workflow=milestone[\s\S]*?durable sequential artifacts/);
});

test("standalone reviewer returns findings without weakening durable review", () => {
  const reviewer = readFileSync(new URL("../../../plugins/kapisch/agents/kapisch-reviewer.toml", import.meta.url), "utf8");

  assert.match(reviewer, /review_mode=standalone/);
  assert.match(reviewer, /standalone review mode[\s\S]*?findings only[\s\S]*?parent\/orchestrator/i);
  assert.match(reviewer, /skip steps 8 and 9/i);
  assert.match(reviewer, /do(?:es not| not) create[^.]*durable[^.]*artifacts/i);
  assert.match(reviewer, /If a revision is unresolvable[\s\S]*?standalone[\s\S]*?findings-only scope blocker/i);
  assert.match(reviewer, /durable workflow mode[\s\S]*?full review contract/i);
  assert.match(reviewer, /In durable workflow mode[\s\S]*?bounded v4 transport limits apply[\s\S]*?In standalone mode[\s\S]*?Do not return a v4 payload/i);
  assert.match(reviewer, /For a working-tree target[\s\S]*?staged[\s\S]*?unstaged[\s\S]*?untracked files[\s\S]*?inspect the contents/i);
  assert.match(reviewer, /Always report requested scope[\s\S]*?verification performed\/omitted[\s\S]*?coverage gaps even when findings exist/i);
  assert.match(reviewer, /Return approve only/);
});

test("canonical contract path resolves relative to the loaded Pi skill", () => {
  const skillUrl = new URL("../skills/kapisch/SKILL.md", import.meta.url);
  const skill = readFileSync(skillUrl, "utf8");
  const canonicalPath = skill.match(/Canonical contract path: `([^`]+)`/)?.[1];
  assert.equal(canonicalPath, "../../../../plugins/kapisch/skills/kapisch/SKILL.md");
  assert.ok(canonicalPath);

  const resolved = new URL(canonicalPath, skillUrl);
  const expected = new URL("../../../plugins/kapisch/skills/kapisch/SKILL.md", import.meta.url);
  assert.equal(fileURLToPath(resolved), fileURLToPath(expected));
  assert.match(readFileSync(resolved, "utf8"), /^---\nname: kapisch\n/);
});

test("skill activation stays explicitly opt-in", () => {
  const skill = readFileSync(new URL("../skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const description = skill.match(/^description:\s*([\s\S]*?)(?=\n\S|$)/m)?.[1] ?? "";
  assert.match(description, /explicitly requests KAPISCH|repository.*require KAPISCH/i);
  assert.doesNotMatch(description, /complex|planning|architecture|review|suitable/i);
  assert.match(skill, /only when[\s\S]{0,240}explicitly requests KAPISCH/i);
  assert.match(skill, /ordinary Pi work MUST NOT activate KAPISCH/i);
  assert.match(skill, /architect\s*->\s*kapisch-architect/);
  assert.match(skill, /researcher\s*->\s*kapisch-researcher/);
  assert.match(skill, /implementer\s*->\s*kapisch-implementer/);
  assert.match(skill, /implementer-lite\s*->\s*kapisch-implementer-lite/);
  assert.match(skill, /mechanic\s*->\s*kapisch-mechanic/);
  assert.match(skill, /reviewer\s*->\s*kapisch-reviewer/);
});
