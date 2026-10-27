import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = new URL("../../../", import.meta.url);
const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("Pi package exposes skill and pi-subagents agents declaratively", () => {
  assert.equal(pkg.pi?.skills?.includes("./skills/kapisch"), true);
  assert.ok(pkg["pi-subagents"]?.agents?.includes("./agents") || pkg.pi?.subagents?.agents?.includes("./agents"));
  assert.equal(pkg.pi?.extensions?.includes("./extensions/human-decisions.ts"), true);
  assert.equal(existsSync(new URL("../extensions/human-decisions.ts", import.meta.url)), true);
  assert.equal(pkg.version, JSON.parse(readFileSync(new URL("../../../plugins/kapisch/.codex-plugin/plugin.json", import.meta.url), "utf8")).version);
  assert.equal(pkg.version, readFileSync(new URL("../../../plugins/kapisch/pyproject.toml", import.meta.url), "utf8").match(/^version = "([^"]+)"/m)?.[1]);
});

test("realignment tracker separates historical decision capture from current Pi capability", () => {
  const tracker = readFileSync(new URL("../../../docs/superpowers/product-realignment-tracker.md", import.meta.url), "utf8");
  const section = (heading: string) => tracker.match(new RegExp(`## ${heading}\\n([\\s\\S]*?)(?=\\n## |$)`))?.[1] ?? "";
  const row = (content: string, id: string) => content.split("\n").find((line) => line.startsWith(`| ${id} |`)) ?? "";
  const glance = section("At a glance");
  const workstreams = section("Workstreams");
  const coverage = section("Specification acceptance coverage");
  const blockers = section("Blockers, limitations, and unknowns");
  const nextSlice = section("Next recommended vertical slice");
  const historical = section("Evidence index");

  assert.match(section("Historical evidence and current status"), /decision-capture claims are superseded/i);
  assert.match(glance, /formal GitHub review\/approval remains pending/i);
  assert.match(glance, /advisory review completed[\s\S]*not GitHub approval/i);
  assert.doesNotMatch(glance, /independent review of #84/i);
  assert.match(tracker, /Last updated: 2026-10-27/);
  assert.match(glance, /decision-required work remains blocked on Pi/i);
  assert.match(row(workstreams, "WS-1"), /historical/i);
  assert.match(row(workstreams, "WS-1.1"), /`BLOCKED` on Pi.*immutable original-input provenance/i);
  assert.match(row(workstreams, "WS-1.3"), /`BLOCKED` on Pi.*immutable original-input provenance/i);
  assert.match(row(coverage, "AC2"), /not currently captured on Pi/i);
  assert.match(blockers, /local advisory review completed.*findings-only/i);
  assert.match(blockers, /not\s+GitHub approval[\s\S]*local candidate is still unpushed[\s\S]*formal PR review remains\s+pending/i);
  assert.match(blockers, /decision-required work is blocked on Pi/i);
  assert.match(nextSlice, /WS-1\.1 only after decision capability is verified/i);
  assert.match(historical, /commit `8ed3f85`/);
  assert.match(historical, /historical and superseded as evidence for current Pi decision capture/i);
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

test("one-task native worker exception has durable file authority and narrow precedence", () => {
  const canonical = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const normalization = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/request-normalization.md", import.meta.url), "utf8");
  const review = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/review.md", import.meta.url), "utf8");
  const resume = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/resume.md", import.meta.url), "utf8");
  const adapter = readFileSync(new URL("../skills/kapisch/SKILL.md", import.meta.url), "utf8");

  assert.match(canonical, /one-task host-native[\s\S]*\.kapisch\/runs\/<run-id>/i);
  assert.match(canonical, /Context[\s\S]*WorkOrder[\s\S]*Outcome/);
  assert.match(canonical, /attempt output[\s\S]*parent LLM[\s\S]*aggregate/i);
  assert.match(canonical, /advisory[\s\S]*persisted/i);
  assert.match(canonical, /fresh session[\s\S]*reread/i);
  assert.match(canonical, /never redispatch automatically/i);
  assert.match(canonical, /in-scope local retry[\s\S]*fresh attempt ID and output location[\s\S]*preserv(?:e|es) the prior attempt[\s\S]*without changing or reapproving the WorkOrder[\s\S]*no per-attempt approval is required/i);
  assert.match(canonical, /current user prompt[\s\S]*WorkOrder[\s\S]*without an extra approval ceremony/i);
  assert.match(canonical, /exact user message[\s\S]*content digest[\s\S]*approval summary is derived, not authority/i);
  assert.match(canonical, /immutable source refs or digests[\s\S]*missing, stale, or mismatched[\s\S]*block continuation/i);
  assert.match(adapter, /HumanDecision capture is unavailable[\s\S]*cannot establish immutable original-input provenance/i);
  assert.match(adapter, /Do not create new `kapisch-decision` request blocks or treat[\s\S]*as authority/i);
  assert.match(adapter, /If a workflow requires a HumanDecision, report it blocked/i);
  assert.match(adapter, /latest assistant message[\s\S]*quoted, incomplete, nested, and superseded marker text does not gate ordinary input/i);
  assert.match(adapter, /kapisch-decision-dismiss[\s\S]*without granting authorization[\s\S]*keep the gated workflow blocked/i);
  assert.match(adapter, /one-task direct-prompt WorkOrder route is unsupported/i);
  assert.doesNotMatch(adapter, /bind the WorkOrder approval source ref and content digest to that exact user message/i);
  assert.match(normalization, /one-task host-native[\s\S]*precedence[\s\S]*graph-free delegation/i);
  assert.match(normalization, /precedence[\s\S]*task-review wording[\s\S]*resume\.md/i);
  assert.match(review, /one-task host-native[\s\S]*advisory[\s\S]*persisted/i);
  assert.match(canonical, /one-task exception[\s\S]*reviewer dispatch is optional[\s\S]*no canonical review invocation\/approval artifacts/i);
  assert.match(canonical, /ordinary task\/milestone review requirements[\s\S]*remain unchanged/i);
  assert.match(review, /one-task host-native[\s\S]*optional[\s\S]*findings-only[\s\S]*no canonical invocation or approval artifacts[\s\S]*cannot claim `approve` or `ready`/i);
  assert.match(resume, /one-task host-native[\s\S]*fresh session[\s\S]*never redispatch automatically/i);
  assert.match(resume, /Before trusting a WorkOrder[\s\S]*approval `source_ref`[\s\S]*adapter metadata[\s\S]*canonical[\s\S]*message digest[\s\S]*governing-input refs\/digests[\s\S]*missing, stale, or mismatched[\s\S]*block continuation/i);
  assert.match(adapter, /worker[\s\S]*not `kapisch-implementer`/);
  assert.match(adapter, /ordinary canonical role mappings[\s\S]*unchanged/i);
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

test("internal-script guide resolves paths from the loaded KAPISCH skill", () => {
  const canonicalUrl = new URL("../../../plugins/kapisch/skills/kapisch/SKILL.md", import.meta.url);
  const canonical = readFileSync(canonicalUrl, "utf8");
  const readme = readFileSync(new URL("../../../plugins/kapisch/README.md", import.meta.url), "utf8");
  const guideUrl = new URL("references/internal-scripts.md", canonicalUrl);

  assert.equal(existsSync(fileURLToPath(guideUrl)), true, "canonical skill links to an existing script guide");
  const guide = readFileSync(guideUrl, "utf8");
  const scriptUrl = new URL("../../scripts/validate_kapisch.py", canonicalUrl);

  assert.match(canonical, /references\/internal-scripts\.md/);
  assert.match(readme, /skills\/kapisch\/references\/internal-scripts\.md/);
  assert.match(guide, /Pi includes each discovered skill's path in its system prompt/i);
  assert.match(guide, /current working directory/i);
  assert.match(guide, /consumer repository[\s\S]{0,60}may differ from the command's current working directory/i);
  assert.match(guide, /interrupted managed-profile switch[\s\S]{0,120}without `--install`[\s\S]{0,100}restor.*managed profile files/i);
  assert.match(guide, /resolve `\.\.\/\.\.` from that directory/i);
  assert.doesNotMatch(guide, /\/home\/|\/Users\/|[A-Z]:\\/);
  assert.equal(existsSync(fileURLToPath(scriptUrl)), true);
});
