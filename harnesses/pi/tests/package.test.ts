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
