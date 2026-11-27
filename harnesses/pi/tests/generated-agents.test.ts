import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  canonicalAgents,
  expectedReviewerResources,
  generateAgentMarkdown,
} from "../scripts/generate-agents.ts";

const root = new URL("../../../", import.meta.url);
const generated = new URL("../agents/", import.meta.url);
const required = [
  "kapisch-architect",
  "kapisch-researcher",
  "kapisch-implementer",
  "kapisch-implementer-lite",
  "kapisch-mechanic",
  "kapisch-reviewer",
];

test("all canonical agents generate byte-stable, faithful Pi definitions", async () => {
  const profiles = await canonicalAgents(root);
  assert.deepEqual(
    profiles.map(({ name }) => name).sort(),
    [...required].sort(),
  );
  const first = profiles.map((profile) => generateAgentMarkdown(profile));
  const second = profiles.map((profile) => generateAgentMarkdown(profile));
  assert.deepEqual(first, second);

  profiles.forEach((profile, index) => {
    const path = new URL(`${profile.name}.md`, generated);
    const committed = readFileSync(path, "utf8");
    assert.equal(committed, first[index]);
    assert.match(committed, new RegExp(`^name: \\\"${profile.name}\\\"$`, "m"));
    assert.equal(committed.match(/^---$/gm)?.length, 2);
    const body = committed.split(/^---\s*$/m)[2];
    assert.equal(body, `\n${profile.developer_instructions}`);
    assert.ok(
      committed.includes(`description: ${JSON.stringify(profile.description)}`),
    );
    assert.doesNotMatch(committed, /(?:^|\s)(?:\/home\/|\/Users\/|[A-Z]:\\)/);
    assert.doesNotMatch(committed, /Generated (?:at|on):|timestamp:/i);
  });
});

test("Pi model and thinking derive from canonical profile values", async () => {
  const profiles = await canonicalAgents(root);
  for (const profile of profiles) {
    const output = generateAgentMarkdown(profile);
    assert.ok(output.includes(`thinking: ${profile.model_reasoning_effort}`));
    if (profile.name !== "kapisch-reviewer")
      assert.ok(output.includes(`model: openai/${profile.model}`));
  }
  assert.ok(
    generateAgentMarkdown(
      profiles.find(({ name }) => name === "kapisch-reviewer")!,
    ).includes("model: openai/gpt-6.1-sol"),
  );
});

test("all six canonical profiles use the specified GPT-6 routing", async () => {
  const profiles = await canonicalAgents(root);
  const byName = new Map(profiles.map((profile) => [profile.name, profile]));
  const expected = {
    "kapisch-architect": ["gpt-6.1-sol", "high"],
    "kapisch-reviewer": ["openai/gpt-6.1-sol", "high"],
    "kapisch-researcher": ["gpt-6-luna", "medium"],
    "kapisch-implementer": ["gpt-6-luna", "medium"],
    "kapisch-implementer-lite": ["gpt-6-luna", "medium"],
    "kapisch-mechanic": ["gpt-6-luna", "low"],
  } as const;
  for (const [name, [model, effort]] of Object.entries(expected)) {
    const profile = byName.get(name as (typeof profiles)[number]["name"]);
    const output = generateAgentMarkdown(profile!);
    assert.ok(
      output.includes(
        `model: ${model.startsWith("openai/") ? model : `openai/${model}`}`,
      ),
    );
    assert.ok(output.includes(`thinking: ${effort}`));
  }
});

test("Pi packages shared reviewer methods as retrievable resources, not prompt duplication", async () => {
  const resources = await expectedReviewerResources(root);
  assert.ok(resources.has("reviewer-baseline.md"));
  assert.ok(resources.has("review.md"));
  assert.ok(resources.has("risk.md"));
  assert.ok(resources.has("severity.md"));
  assert.ok(resources.has("reviewer-methodologies/mutation-and-side-effect-justification.md"));
  assert.ok(resources.has("reviewer-methodologies/semantic-consistency.md"));
  assert.ok(resources.has("reviewer-methodologies/dependencies-and-traceability.md"));
  assert.ok(resources.has("reviewer-methodologies/authority-and-ownership.md"));
  assert.ok(resources.has("reviewer-methodologies/temporal-and-lifecycle-consistency.md"));
  assert.ok(resources.has("reviewer-methodologies/proof-obligations-and-evidence-quality.md"));
  assert.ok(resources.has("reviewer-methodologies/executability-feasibility-and-simplicity.md"));
  for (const [relative, expected] of resources) {
    const source = new URL(`../../../plugins/kapisch/skills/kapisch/references/${relative}`, import.meta.url);
    const generatedResource = new URL(`../skills/kapisch/references/${relative}`, import.meta.url);
    assert.equal(readFileSync(generatedResource, "utf8"), expected);
    assert.equal(readFileSync(source, "utf8"), expected);
  }
  const reviewer = readFileSync(new URL("../agents/kapisch-reviewer.md", import.meta.url), "utf8");
  assert.match(reviewer, /reviewer-baseline\.md/);
  assert.match(reviewer, /durable workflow mode/);
  assert.match(reviewer, /plugins\/kapisch\/roles\/reviewer\.md/);
  assert.match(reviewer, /Version-4 transport return/);
  const standaloneMode = reviewer.indexOf("review_mode=standalone");
  const baselineReference = reviewer.indexOf("reviewer-baseline.md");
  const durableMode = reviewer.indexOf("durable workflow mode");
  assert.ok(standaloneMode >= 0 && standaloneMode < baselineReference);
  assert.ok(baselineReference < durableMode);
  assert.match(reviewer.slice(durableMode), /do not require.*external.*methodology/i);
  const reviewContract = resources.get("review.md");
  assert.ok(reviewContract);
  assert.match(reviewContract, /working-tree\s+target/);
  assert.match(reviewContract, /git ls-files --others --exclude-standard/);
  assert.match(reviewContract, /mismatches the request/);
  assert.doesNotMatch(reviewer, /### Behavioral branch matrix and scope/);
  assert.doesNotMatch(reviewer, /# Mutation and Side-effect Justification/);
});
