import assert from "node:assert/strict";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import registerHumanDecisions from "../extensions/human-decisions.ts";

const request = { question_id: "Q-1", question: "May I proceed?", governing_inputs: [{ ref: "context:C0", digest: "a".repeat(64) }], subject: "release", scope: "staging", decision_type: "approval", source_kind: "direct_operator" };
function assistant(value: unknown = request, stopReason = "stop", id = "assistant-1") {
  const text = `Approval needed.\n\n\`\`\`kapisch-decision\n${JSON.stringify(value)}\n\`\`\``;
  return { type: "message", id, message: { role: "assistant", stopReason, content: [{ type: "text", text }] } };
}
function assistantText(text: string, id = "assistant-text") {
  return { type: "message", id, message: { role: "assistant", stopReason: "stop", content: [{ type: "text", text }] } };
}
function fixture(branch: unknown[]) {
  const handlers: Array<(event: any, context: any) => Promise<any>> = [];
  const commands = new Map<string, (args: string, context: any) => Promise<void>>();
  const sent: any[] = [];
  const notices: string[] = [];
  let promptCalls = 0;
  registerHumanDecisions({
    on(_event: string, handler: any) { handlers.push(handler); },
    registerCommand(name: string, options: any) { commands.set(name, options.handler); },
    sendMessage(message: any, options: any) {
      sent.push({ message, options });
      branch.push({ type: "custom_message", id: `custom-${sent.length}`, customType: message.customType, content: message.content });
    },
  } as never);
  const context = {
    mode: "tui", hasUI: true,
    ui: { notify: (message: string) => notices.push(message), input: async () => { promptCalls += 1; return "transformed"; } },
    sessionManager: { getBranch: () => branch },
  };
  return { input: handlers[0], commands, context, sent, notices, promptCalls: () => promptCalls };
}
async function temp(run: (cwd: string) => Promise<void>) {
  const cwd = await mkdtemp(join(tmpdir(), "human-decision-"));
  try { await run(cwd); } finally { await rm(cwd, { recursive: true, force: true }); }
}

async function assertNoDecisionFiles(cwd: string) {
  assert.deepEqual(await readdir(join(cwd, ".kapisch")).catch(() => []), []);
}

test("ordinary Pi input continues without a pending marker, including busy, blank, and image input", async () => {
  const f = fixture([]);
  for (const event of [{ text: "steer", streamingBehavior: "steer" }, { text: "", images: [{}] }, { text: "  " }, { text: "follow", streamingBehavior: "followUp" }]) {
    assert.deepEqual(await f.input(event, f.context), { action: "continue" });
  }
});

test("quoted or incomplete marker syntax does not block ordinary input", async () => {
  for (const text of [
    "Documentation may show this opener:\n```kapisch-decision\n",
    `> \`\`\`kapisch-decision\n> ${JSON.stringify(request)}\n> \`\`\``,
  ]) {
    const f = fixture([assistantText(text)]);
    assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "continue" });
  }
});

test("a later ordinary assistant message retires an obsolete decision marker", async () => {
  const f = fixture([assistant(), assistantText("Ordinary follow-up without a decision request.", "assistant-2")]);
  assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "continue" });
});

test("list and tilde-fenced marker examples do not become requests", async () => {
  const examples = [
    `A list example:\n- marker:\n  \`\`\`kapisch-decision\n  ${JSON.stringify(request)}\n  \`\`\``,
    "~~~text\n```kapisch-decision\n" + JSON.stringify(request) + "\n```\n```kapisch-decision\n" + JSON.stringify(request) + "\n```\n~~~",
  ];
  for (const text of examples) {
    const f = fixture([assistantText(text)]);
    assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "continue" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    await f.commands.get("kapisch-decision-dismiss")!("", f.context);
    assert.equal(f.sent.length, 0);
  }
});

test("top-level request remains pending with surrounding prose or unrelated code fences", async () => {
  const requestText = `Approval needed.\n\n\`\`\`kapisch-decision\n${JSON.stringify(request)}\n\`\`\``;
  const examples = [
    `${requestText}\nPlease wait while I explain the request.`,
    `\`\`\`bash\necho unrelated\n\`\`\`\n\n${requestText}`,
  ];
  for (const text of examples) {
    const f = fixture([assistantText(text)]);
    assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "handled" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    assert.equal(f.sent.length, 0);
    await f.commands.get("kapisch-decision-dismiss")!("", f.context);
    assert.equal(f.sent.length, 1);
    assert.equal(f.sent[0].message.customType, "kapisch-decision-dismiss");
  }
});

test("list-container code examples do not mask a following top-level request", async () => {
  const fence = "`".repeat(3);
  const listFence = "`".repeat(4);
  const requestText = `${fence}kapisch-decision\n${JSON.stringify(request)}\n${fence}`;
  const examples = [
    `- ${listFence}text\n  ${fence}kapisch-decision\n  example only\n  ${fence}\n  ${listFence}\n\n${requestText}`,
    `1. ${listFence}text\n   ${fence}kapisch-decision\n   example only\n   ${fence}\n   ${listFence}\n\n${requestText}`,
    `10. ${listFence}text\n    ${fence}kapisch-decision\n    example only\n    ${fence}\n    ${listFence}\n\n${requestText}`,
    `  - ${listFence}text\n    ${fence}kapisch-decision\n    example only\n    ${fence}\n    ${listFence}\n\n${requestText}`,
    `- example:\n  ${listFence}text\n  ${fence}kapisch-decision\n  example only\n    ${fence}\n  ${listFence}\n\n${requestText}`,
    `- parent\n  - example:\n    ${listFence}text\n    ${fence}kapisch-decision\n    example only\n    ${fence}\n    ${listFence}\n\n${requestText}`,
    `- ${listFence}text\n  ${fence}kapisch-decision\n  example only\n  ${fence}\n\n${requestText}`,
  ];
  for (const text of examples) {
    const f = fixture([assistantText(text)]);
    assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "handled" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    assert.equal(f.sent.length, 0);
    await f.commands.get("kapisch-decision-dismiss")!("", f.context);
    assert.equal(f.sent.length, 1);
    assert.equal(f.sent[0].message.customType, "kapisch-decision-dismiss");
  }
});

test("standalone tilde decision-like fences do not become requests", async () => {
  const fence = "~".repeat(3);
  const examples = [
    `${fence}kapisch-decision\n${JSON.stringify(request)}\n${fence}`,
    `${fence}kapisch-decision\n{bad}\n${fence}`,
  ];
  for (const text of examples) {
    const f = fixture([assistantText(text)]);
    assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "continue" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    await f.commands.get("kapisch-decision-dismiss")!("", f.context);
    assert.equal(f.sent.length, 0);
  }
});

test("pending request rejection is explained and dismissal does not grant authorization", async () => {
  const f = fixture([assistant()]);
  assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "handled" });
  assert.match(f.notices[0], /not forwarded[\s\S]*kapisch-decision-dismiss[\s\S]*does not authorize/i);
  await f.commands.get("kapisch-decision-dismiss")!("", f.context);
  assert.equal(f.sent.length, 1);
  assert.equal(f.sent[0].message.customType, "kapisch-decision-dismiss");
  assert.match(f.sent[0].message.content, /does not grant a decision or authorization/i);
  assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "continue" });
});

test("valid pending input is blocked and decision command refuses without prompt or publication", async () => temp(async (cwd) => {
  const f = fixture([assistant()]);
  const inlineFence = fixture([assistant({ ...request, question: "Use ```kapisch-decision only as quoted text." })]);
  assert.deepEqual(await inlineFence.input({ text: "blocked" }, inlineFence.context), { action: "handled" });
  for (const event of [{ text: "changed by prompt" }, { text: "", images: [{}] }, { text: " ", streamingBehavior: "steer" }]) {
    assert.deepEqual(await f.input(event, f.context), { action: "handled" });
  }
  await f.commands.get("kapisch-decision")!("", f.context);
  assert.match(f.notices[0], /cannot establish immutable original-input provenance/);
  assert.equal(f.promptCalls(), 0);
  assert.equal(f.sent.length, 0);
  await assertNoDecisionFiles(cwd);
}));

test("invalid pending request stays blocked and repair remains non-authorizing", async () => temp(async (cwd) => {
  const f = fixture([assistant({ ...request, source_kind: "reviewer" })]);
  assert.deepEqual(await f.input({ text: "injected" }, f.context), { action: "handled" });
  await f.commands.get("kapisch-decision")!("", f.context);
  assert.match(f.notices[0], /cannot establish immutable original-input provenance/);
  await f.commands.get("kapisch-decision-repair")!("", f.context);
  assert.equal(f.sent.length, 1);
  assert.equal(f.sent[0].message.customType, "kapisch-decision-repair");
  assert.match(f.sent[0].message.content, /grants no decision or authorization/);
  assert.equal(f.promptCalls(), 0);
  await assertNoDecisionFiles(cwd);
}));

test("malformed and interrupted markers remain blocked and can only request repair", async () => {
  for (const branch of [[assistant({ question_id: "bad" })], [assistant(request, "error")], [assistant(request, "aborted")]]) {
    const f = fixture(branch);
    assert.deepEqual(await f.input({ text: "no authority" }, f.context), { action: "handled" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    assert.equal(f.sent.length, 1);
    assert.equal(f.sent[0].message.customType, "kapisch-decision-repair");
  }
});

test("valid requests do not use the repair route", async () => {
  const f = fixture([assistant()]);
  await f.commands.get("kapisch-decision-repair")!("", f.context);
  assert.equal(f.sent.length, 0);
});

test("parser rejects malformed, duplicate, missing, unknown, invalid digest, and invalid source markers", async () => temp(async (cwd) => {
  const valid = `\`\`\`kapisch-decision\n${JSON.stringify(request)}\n\`\`\``;
  const cases = [
    `\`\`\`kapisch-decision\n{bad}\n\`\`\``,
    `\`\`\`kapisch-decision\n${JSON.stringify({ question_id: "Q-1" })}\n\`\`\``,
    `\`\`\`kapisch-decision\n${JSON.stringify({ ...request, unexpected: true })}\n\`\`\``,
    `\`\`\`kapisch-decision\n${JSON.stringify({ ...request, source_kind: "reviewer" })}\n\`\`\``,
    `\`\`\`kapisch-decision\n${JSON.stringify({ ...request, governing_inputs: [{ ref: "x", digest: "bad" }] })}\n\`\`\``,
    valid + "\n" + valid,
  ];
  for (const text of cases) {
    const f = fixture([{ type: "message", id: `bad-${Math.random()}`, message: { role: "assistant", stopReason: "stop", content: [{ type: "text", text }] } }]);
    assert.deepEqual(await f.input({ text: "blocked" }, f.context), { action: "handled" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    assert.equal(f.sent.length, 1);
    assert.equal(f.sent[0].message.customType, "kapisch-decision-repair");
    assert.equal(f.promptCalls(), 0);
    await assertNoDecisionFiles(cwd);
  }
}));

test("no HumanDecision record is created from a transformed UI result", async () => temp(async (cwd) => {
  const f = fixture([assistant()]);
  await f.commands.get("kapisch-decision")!("", f.context);
  assert.equal(f.promptCalls(), 0);
  await assertNoDecisionFiles(cwd);
}));
