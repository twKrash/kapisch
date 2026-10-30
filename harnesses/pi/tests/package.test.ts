import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = new URL("../../../", import.meta.url);
const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const normalizeWhitespace = (text: string) => text.replace(/\s+/g, " ").trim();

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

  assert.match(section("Historical evidence and current status"), /claims remain historical[\s\S]*fresh\s+Pi-Bolt smoke[\s\S]*not a tracked acceptance harness[\s\S]*Do not treat it as full acceptance/i);
  assert.match(glance, /latest formal review[\s\S]*K84-IND-001 \(P2\)/i);
  assert.match(normalizeWhitespace(glance), /earlier K84-010 WorkOrder-binding finding was fixed with a regression assertion/i);
  const reviewSummary = /bounded standalone review of this seven-file docs\/test delta found one confirmed P3 \(K84-WT-001\): assertions rejected equivalent Markdown line wrapping/i;
  assert.match(normalizeWhitespace(glance), reviewSummary);
  assert.match(normalizeWhitespace(glance.replace("K84-WT-001): assertions", "K84-WT-001):\n  assertions")), reviewSummary);
  assert.match(glance, /bounded standalone review of this seven-file docs\/test delta found one confirmed P3[\s\S]*normalize whitespace[\s\S]*no other diff-causal findings/i);
  assert.match(glance, /All four GitHub checks for `1cbc5ac`\s*completed successfully/i);
  assert.doesNotMatch(glance, /independent review of #84/i);
  assert.match(tracker, /Last updated: 2026-10-30/);
  assert.match(normalizeWhitespace(tracker), /all four GitHub checks for `1cbc5ac` completed successfully/i);
  assert.match(glance, /Pi pending-request HumanDecision capture is covered by tracked\s+tests and the earlier RPC smoke/i);
  assert.match(glance, /fresh real-Pi smoke[\s\S]*authorized direct prompt[\s\S]*Outcome/i);
  assert.match(glance, /disposable non-Git run[\s\S]*did not establish the implementer-unavailable\s+fallback condition/i);
  assert.match(row(workstreams, "WS-1"), /`PARTIAL \/ IN PROGRESS`[\s\S]*manual real-Pi smoke[\s\S]*K84-IND-001/i);
  assert.match(row(workstreams, "WS-1.1"), /`IN PROGRESS`.*one direct path smoke-tested.*not a tracked\/reusable consumer test/i);
  assert.match(row(workstreams, "WS-1.3"), /Tracked tests cover pending-request source-kind fields[\s\S]*new direct-prompt smoke persisted a `direct_operator` decision/i);
  assert.match(row(coverage, "AC1"), /One manual smoke[\s\S]*no tracked acceptance test/i);
  assert.match(row(coverage, "AC2"), /package tests assert no redundant direct approval[\s\S]*scope-change reassessment[\s\S]*remain unverified/i);
  assert.match(row(coverage, "AC7"), /tracked tests compare[\s\S]*HumanDecision facts only[\s\S]*no same-WorkOrder cross-adapter comparison/i);
  assert.match(row(coverage, "AC8"), /fresh Pi session[\s\S]*did not restart from pre-existing WorkOrder/i);
  assert.match(row(coverage, "AC10"), /\| partial \| Local Pi package install[\s\S]*Reviewer installation/i);
  assert.match(blockers, /Open review finding K84-IND-001 \(P2\)[\s\S]*HTML comment or[\s\S]*<pre>/i);
  assert.match(blockers, /Tracked end-to-end acceptance remains incomplete[\s\S]*no tracked\s+reusable WorkOrder consumer\/comparison harness/i);
  assert.match(blockers, /Tracked end-to-end acceptance remains incomplete[\s\S]*no tracked\s+reusable WorkOrder consumer\/comparison harness/i);
  assert.match(nextSlice, /WS-1\.2 tracked harness[\s\S]*Full decision-to-Outcome acceptance remains incomplete/i);
  assert.doesNotMatch(tracker, /current Pi does not capture decisions|extension only gates\/repairs|decision capability is unavailable/i);
  assert.match(historical, /commit `8ed3f85`/);
  assert.match(historical, /historical and superseded as evidence for current Pi decision capture/i);
});

test("direct one-task authorization binds one durable decision without another prompt", () => {
  const canonical = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const resume = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/resume.md", import.meta.url), "utf8");
  const adapter = readFileSync(new URL("../README.md", import.meta.url), "utf8");
  const piSkill = readFileSync(new URL("../skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const oneTask = canonical.split("The one-task path is file-based")[1]?.split("A mandated skill")[0] ?? "";

  assert.match(oneTask, /current user prompt itself explicitly and unambiguously authorizes/);
  assert.match(oneTask, /persist exactly one immutable `HumanDecision`[\s\S]*decisions\/<decision_id>\.json[\s\S]*workorder\.json[\s\S]*before dispatch/i);
  assert.match(oneTask, /WorkOrder[\s\S]*decision_id[\s\S]*missing[\s\S]*invalid[\s\S]*do not dispatch/i);
  assert.match(oneTask, /attempts\/<attempt_id>\.json[\s\S]*aggregation\.md[\s\S]*outcome\.json/i);
  assert.match(oneTask, /attempt evidence[\s\S]*aggregation\.md[\s\S]*outcome\.json[\s\S]*same[\s\S]*decision_id/i);
  assert.match(resume, /on resume[\s\S]*if the HumanDecision or WorkOrder is missing[\s\S]*block instead of reconstructing/i);
  assert.match(oneTask, /coordinator must first persist exactly one immutable `HumanDecision`[\s\S]*before dispatch/i);
  assert.match(oneTask, /do not create a second record or ask for another approval of the same scope/i);
  assert.match(oneTask, /existing HumanDecision fields[\s\S]*unique `decision_id` and `question_id`[\s\S]*`question` and `answer`[\s\S]*`decision_type=approval`[\s\S]*`source_kind=direct_operator`/);
  assert.doesNotMatch(oneTask, /host-persisted user message.{0,120}digest|digest.{0,120}host-persisted user message/i);
  assert.match(oneTask, /source_kind=direct_operator[\s\S]*WorkOrder cites the applicable `decision_id`/i);
  assert.match(oneTask, /ambiguous[\s\S]*do not create an approval decision or dispatch[\s\S]*ask a focused clarification/i);
  assert.match(adapter, /canonical KAPISCH skill owns direct-prompt authorization and the one-task file-based artifact lifecycle/i);
  assert.match(piSkill, /ordinary direct prompts are not auto-captured[\s\S]*coordinator owns direct-prompt records under the canonical one-task contract/i);
  assert.doesNotMatch(piSkill, /coordinator must persist exactly one immutable `HumanDecision`/i);
  assert.match(resume, /one-task host-native[\s\S]*exactly one valid match/i);
  assert.match(resume, /host-persisted message reference may identify that request but is not an input-provenance prerequisite/i);
  assert.match(resume, /initial direct user instruction[\s\S]*must persist exactly one durable `HumanDecision` before WorkOrder dispatch/i);
  assert.match(resume, /on resume[\s\S]*missing[\s\S]*block instead of reconstructing/i);
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
  const workOrderPublication = /persist `workorder\.json` with that exact `decision_id`, bounded task and scope, worker role\/capability disclosure, and output location before dispatch/;
  const normalizedCanonical = normalizeWhitespace(canonical);
  assert.match(normalizedCanonical, workOrderPublication);
  assert.match(normalizeWhitespace(canonical.replace("bounded task and scope, worker role", "bounded task and scope,\n  worker role")), workOrderPublication);
  assert.doesNotMatch(normalizedCanonical.replace("that exact `decision_id`", "a decision"), workOrderPublication);
  assert.doesNotMatch(normalizedCanonical.replace("output location before dispatch", "output location after dispatch"), workOrderPublication);
  assert.match(canonical, /attempts\/<attempt_id>\.json[\s\S]*aggregation\.md[\s\S]*outcome\.json/i);
  assert.match(canonical, /advisory[\s\S]*persisted/i);
  assert.match(canonical, /fresh session[\s\S]*reread/i);
  assert.match(canonical, /never redispatch automatically/i);
  assert.match(canonical, /in-scope local retry[\s\S]*fresh attempt ID and output location[\s\S]*preserv(?:e|es) the prior attempt[\s\S]*without changing or reapproving the WorkOrder[\s\S]*no per-attempt approval is required/i);
  assert.match(canonical, /current user prompt itself explicitly and unambiguously authorizes[\s\S]*coordinator must first persist exactly one immutable `HumanDecision`[\s\S]*before dispatch[\s\S]*do not create a second record or ask for another approval of the same scope/i);
  assert.match(canonical, /HumanDecision[\s\S]*decision_id[\s\S]*WorkOrder[\s\S]*applicability is assessed\s+separately/i);
  assert.match(canonical, /immutable source refs or digests[\s\S]*missing, stale, or mismatched[\s\S]*block continuation/i);
  assert.match(adapter, /effective user-role input received from Pi[\s\S]*trusted under the selected host's trust model/i);
  assert.match(adapter, /TUI[\s\S]*RPC[\s\S]*JSON[\s\S]*print/i);
  assert.match(adapter, /before any workflow selection or dispatch[\s\S]*use Pi's `read` tool[\s\S]*complete current canonical `SKILL.md`[\s\S]*do not use `grep`/i);
  assert.match(adapter, /latest assistant message[\s\S]*one complete, valid top-level `kapisch-decision` block/);
  assert.match(adapter, /kapisch-decision-dismiss[\s\S]*dismisses without granting authorization/i);
  assert.match(adapter, /kapisch-decision-repair[\s\S]*requests regeneration[\s\S]*without creating a decision/i);
  assert.match(adapter, /ordinary direct prompts are not auto-captured[\s\S]*coordinator owns direct-prompt records/i);
  assert.match(normalization, /one-task host-native[\s\S]*precedence[\s\S]*graph-free delegation/i);
  assert.match(normalization, /precedence[\s\S]*task-review wording[\s\S]*resume\.md/i);
  assert.match(review, /one-task host-native[\s\S]*advisory[\s\S]*persisted/i);
  assert.match(canonical, /one-task exception[\s\S]*reviewer dispatch is optional[\s\S]*no canonical review invocation\/approval artifacts/i);
  assert.match(canonical, /ordinary task\/milestone review requirements[\s\S]*remain unchanged/i);
  assert.match(review, /one-task host-native[\s\S]*optional[\s\S]*findings-only[\s\S]*no canonical invocation or approval artifacts[\s\S]*cannot claim `approve` or `ready`/i);
  assert.match(resume, /one-task host-native[\s\S]*fresh session[\s\S]*never redispatch automatically/i);
  assert.match(resume, /Before trusting a WorkOrder[\s\S]*HumanDecision[\s\S]*source reference[\s\S]*governing-input refs\/digests[\s\S]*applicability[\s\S]*missing, stale, mismatched, or inapplicable[\s\S]*block continuation/i);
  assert.match(adapter, /worker[\s\S]*not `kapisch-implementer`/);
  assert.match(adapter, /ordinary canonical role mappings[\s\S]*unchanged/i);
});

test("portable HumanDecision contract covers external sources without host-session authority", () => {
  const canonical = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const resume = readFileSync(new URL("../../../plugins/kapisch/skills/kapisch/references/resume.md", import.meta.url), "utf8");
  const section = canonical.split("## Portable HumanDecision contract")[1]?.split("\n## ")[0] ?? "";

  assert.notEqual(section, "");
  assert.match(section, /immutable[\s\S]*direct_operator[\s\S]*operator_reported_external[\s\S]*external_artifact/i);
  assert.match(section, /WorkOrder[\s\S]*decision_id[\s\S]*applicability is assessed\s+separately/i);
  assert.match(section, /governing_inputs[\s\S]*subject[\s\S]*scope/);
  assert.doesNotMatch(section, /Pi|TUI|RPC|sessionManager/i);
  assert.match(canonical, /current user prompt itself explicitly and unambiguously authorizes[\s\S]*coordinator must first persist exactly one immutable `HumanDecision`[\s\S]*before dispatch[\s\S]*do not create a second record or ask for another approval of the same scope/i);
  assert.match(resume, /HumanDecision[\s\S]*external source[\s\S]*applicability/i);
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

test("Pi adapter trusts effective user input and exposes durable decisions downstream", () => {
  const adapter = readFileSync(new URL("../skills/kapisch/SKILL.md", import.meta.url), "utf8");
  const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");

  assert.match(adapter, /effective user-role input received from Pi/i);
  assert.match(adapter, /TUI[\s\S]*RPC[\s\S]*JSON[\s\S]*print/i);
  assert.match(adapter, /direct_operator[\s\S]*operator_reported_external[\s\S]*external_artifact/);
  assert.match(adapter, /\.kapisch\/runs\/<Pi session ID>\/decisions/);
  assert.match(adapter, /ordinary direct prompts are not auto-captured[\s\S]*coordinator owns direct-prompt records/i);
  assert.match(adapter, /ambiguous answers remain raw evidence and are not interpreted as approval/i);
  assert.doesNotMatch(adapter, /coordinator must persist exactly one immutable `HumanDecision`/i);
  assert.doesNotMatch(adapter, /immutable original-input provenance|capture is unavailable/i);
  assert.match(readme, /canonical KAPISCH skill owns direct-prompt authorization/i);
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
  assert.match(skill, /before any workflow selection or dispatch[\s\S]*use Pi's `read` tool[\s\S]*complete current canonical `SKILL\.md`[\s\S]*do not use `grep`/i);
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
