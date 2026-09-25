import assert from "node:assert/strict";
import { test } from "node:test";
import { agentPolicy } from "../policy/agents.ts";

const readOnly = ["kapisch-architect", "kapisch-researcher", "kapisch-reviewer"];
const writers = ["kapisch-implementer", "kapisch-implementer-lite", "kapisch-mechanic"];

test("Pi capability classes match canonical responsibilities", () => {
  assert.deepEqual(Object.keys(agentPolicy).sort(), [...readOnly, ...writers].sort());
  for (const name of readOnly) {
    const policy = agentPolicy[name as keyof typeof agentPolicy];
    assert.equal(policy.acceptanceRole, "read-only");
    assert.ok(!policy.tools.includes("edit"));
    assert.ok(!policy.tools.includes("write"));
    assert.deepEqual(policy.permissions, { edit: "deny", write: "deny" });
    assert.equal(policy.allowNestedSubagents, false);
  }
  for (const name of writers) {
    const policy = agentPolicy[name as keyof typeof agentPolicy];
    assert.equal(policy.acceptanceRole, "writer");
    assert.ok(policy.tools.includes("edit"));
    assert.ok(policy.tools.includes("write"));
    assert.equal(policy.allowNestedSubagents, false);
  }
});

test("researcher and reviewer receive Bash without mutation tools", () => {
  for (const name of ["kapisch-researcher", "kapisch-reviewer"] as const) {
    assert.ok(agentPolicy[name].tools.includes("bash"));
    assert.ok(!agentPolicy[name].tools.includes("edit"));
    assert.ok(!agentPolicy[name].tools.includes("write"));
  }
  assert.ok(!agentPolicy["kapisch-architect"].tools.includes("bash"));
});

test("capability policy owns no canonical descriptions or model routing", () => {
  for (const policy of Object.values(agentPolicy)) {
    assert.equal("model" in policy, false);
    assert.equal("thinking" in policy, false);
    assert.equal("description" in policy, false);
    assert.equal("developer_instructions" in policy, false);
  }
});
