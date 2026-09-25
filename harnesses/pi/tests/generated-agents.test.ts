import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { canonicalAgents, generateAgentMarkdown } from "../scripts/generate-agents.ts";

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
  assert.deepEqual(profiles.map(({ name }) => name).sort(), [...required].sort());
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
    assert.ok(committed.includes(`description: ${JSON.stringify(profile.description)}`));
    assert.doesNotMatch(committed, /(?:^|\s)(?:\/home\/|\/Users\/|[A-Z]:\\)/);
    assert.doesNotMatch(committed, /Generated (?:at|on):|timestamp:/i);
  });
});

test("Pi model and thinking derive from canonical profile values", async () => {
  const profiles = await canonicalAgents(root);
  for (const profile of profiles) {
    const output = generateAgentMarkdown(profile);
    assert.ok(output.includes(`model: openai-codex/${profile.model}`));
    assert.ok(output.includes(`thinking: ${profile.model_reasoning_effort}`));
  }
});

test("all six canonical profiles use the specified GPT-6 routing", async () => {
  const profiles = await canonicalAgents(root);
  const byName = new Map(profiles.map((profile) => [profile.name, profile]));
  const expected = {
    "kapisch-architect": ["gpt-6-sol", "high"],
    "kapisch-reviewer": ["gpt-6-sol", "high"],
    "kapisch-researcher": ["gpt-6-luna", "medium"],
    "kapisch-implementer": ["gpt-6-luna", "medium"],
    "kapisch-implementer-lite": ["gpt-6-luna", "medium"],
    "kapisch-mechanic": ["gpt-6-luna", "low"],
  } as const;
  for (const [name, [model, effort]] of Object.entries(expected)) {
    assert.equal(byName.get(name as (typeof profiles)[number]["name"])?.model, model);
    assert.equal(byName.get(name as (typeof profiles)[number]["name"])?.model_reasoning_effort, effort);
  }
});
