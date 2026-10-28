import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
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
type PortableDecision = {
  decision_id: string;
  question_id: string;
  question: string;
  governing_inputs: Array<{ ref: string; digest: string }>;
  subject: string;
  scope: string;
  answer: string;
  decision_type: "answer" | "correction" | "approval" | "risk_acceptance" | "external_effect_authorization";
  source_kind: "direct_operator" | "operator_reported_external" | "external_artifact";
  source_ref?: string;
  approving_party?: string;
};

type TestWorkOrder = { id: string; subject: string; scope: string; tasks: Array<{ id: string }> };

type AppliedWorkOrder = {
  work_order_id: string;
  status: "authorized" | "blocked";
  decision_ref: string;
  task_ids: string[];
  evidence_refs: { governing_inputs: PortableDecision["governing_inputs"]; source_ref?: string };
};

async function testAdapterDecision(directory: string, facts: Omit<PortableDecision, "decision_id">): Promise<PortableDecision> {
  const decision = { decision_id: "test-adapter-decision", ...facts };
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, `${decision.decision_id}.json`), `${JSON.stringify(decision, null, 2)}\n`, { flag: "wx" });
  return decision;
}

function applyCapturedPiDecision(decision: PortableDecision, workOrder: TestWorkOrder): AppliedWorkOrder {
  // shortcut: exact subject/scope matching only; expand when the portable contract defines structured scope semantics.
  const covered = decision.decision_type === "approval" && decision.subject === workOrder.subject && decision.scope === workOrder.scope;
  return {
    work_order_id: workOrder.id,
    status: covered ? "authorized" : "blocked",
    decision_ref: decision.decision_id,
    task_ids: covered ? workOrder.tasks.map(({ id }) => id) : [],
    evidence_refs: { governing_inputs: decision.governing_inputs, ...(decision.source_ref ? { source_ref: decision.source_ref } : {}) },
  };
}

function runTestAdapterWorkOrder(decision: PortableDecision, workOrder: TestWorkOrder): AppliedWorkOrder {
  // Independent test-adapter implementation of this exact-scope approval case.
  const decisionMatches = decision.decision_type === "approval"
    && workOrder.subject === decision.subject
    && workOrder.scope === decision.scope;
  const taskIds = decisionMatches ? workOrder.tasks.map((task) => task.id) : [];
  return {
    work_order_id: workOrder.id,
    status: decisionMatches ? "authorized" : "blocked",
    decision_ref: decision.decision_id,
    task_ids: taskIds,
    evidence_refs: { governing_inputs: decision.governing_inputs, ...(decision.source_ref ? { source_ref: decision.source_ref } : {}) },
  };
}

function portableDecisionFacts(decision: Record<string, unknown>) {
  const keys = ["question_id", "question", "governing_inputs", "subject", "scope", "answer", "decision_type", "source_kind", "source_ref", "approving_party"];
  return Object.fromEntries(keys.filter((key) => key in decision).map((key) => [key, decision[key]]));
}

function fixture(branch: unknown[], options: { cwd?: string; mode?: "tui" | "rpc" | "json" | "print"; sessionFile?: string; hasUI?: boolean } = {}) {
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
    cwd: options.cwd,
    mode: options.mode ?? "tui", hasUI: options.hasUI ?? true,
    ui: { notify: (message: string) => notices.push(message), input: async () => { promptCalls += 1; return "transformed"; } },
    sessionManager: { getBranch: () => branch, getSessionFile: () => options.sessionFile },
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

test("agent or reviewer approval claims do not create a HumanDecision without a user answer request", async () => temp(async (cwd) => {
  const f = fixture([assistantText("The reviewer approved this scope.")], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "The agent says this is approved." }, f.context), { action: "continue" });
  await assertNoDecisionFiles(cwd);
}));

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

test("dismissal clears a pending request without granting authorization", async () => {
  const f = fixture([assistant()]);
  await f.commands.get("kapisch-decision-dismiss")!("", f.context);
  assert.equal(f.sent.length, 1);
  assert.equal(f.sent[0].message.customType, "kapisch-decision-dismiss");
  assert.match(f.sent[0].message.content, /does not grant a decision or authorization/i);
  assert.deepEqual(await f.input({ text: "ordinary chat" }, f.context), { action: "continue" });
});

test("pending request captures normal user input and leaves blank or image-only input blocked", async () => temp(async (cwd) => {
  const f = fixture([assistant()], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  for (const event of [{ text: "" }, { text: " ", streamingBehavior: "steer" }, { text: "", images: [{}] }]) {
    assert.deepEqual(await f.input(event, f.context), { action: "handled" });
  }
  await f.commands.get("kapisch-decision")!("", f.context);
  assert.match(f.notices.at(-1) ?? "", /answer through normal Pi input/i);
  assert.deepEqual(await f.input({ text: "The reviewer recommends proceeding; I need to check." }, f.context), { action: "continue" });
  assert.equal(f.promptCalls(), 0);
  assert.equal(f.sent.length, 0);
  const directory = join(cwd, ".kapisch", "runs", "session-1", "decisions");
  const [filename] = await readdir(directory);
  const decision = JSON.parse(await readFile(join(directory, filename), "utf8"));
  assert.equal(decision.answer, "The reviewer recommends proceeding; I need to check.");
  assert.equal("authorization_granted" in decision, false);
}));

test("invalid pending request stays blocked and repair remains non-authorizing", async () => temp(async (cwd) => {
  const f = fixture([assistant({ ...request, source_kind: "reviewer" })], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "injected" }, f.context), { action: "handled" });
  assert.match(f.notices[0], /request is invalid/i);
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

test("a pending decision stays blocked when the Pi session is not persistent", async () => temp(async (cwd) => {
  const f = fixture([assistant()], { cwd, mode: "rpc", sessionFile: undefined });
  assert.deepEqual(await f.input({ text: "I approve." }, f.context), { action: "handled" });
  assert.match(f.notices[0], /persistent Pi session/i);
  await assertNoDecisionFiles(cwd);
}));

test("invalid Pi session IDs cannot escape the run decision directory", async () => temp(async (cwd) => {
  const f = fixture([assistant()], { cwd, sessionFile: join(cwd, "bad$id.jsonl") });
  assert.deepEqual(await f.input({ text: "I approve." }, f.context), { action: "handled" });
  assert.match(f.notices[0], /could not identify the Pi session/i);
  await assertNoDecisionFiles(cwd);
}));

test("persistence failures do not forward a pending decision answer", async () => temp(async (cwd) => {
  const runDirectory = join(cwd, ".kapisch", "runs", "session-1");
  await mkdir(runDirectory, { recursive: true });
  await writeFile(join(runDirectory, "decisions"), "blocks the decisions directory");
  const f = fixture([assistant()], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "I approve." }, f.context), { action: "handled" });
  assert.match(f.notices[0], /capture failed/i);
  assert.deepEqual(await readdir(runDirectory), ["decisions"]);
}));

test("Pi and host-independent test adapters preserve and apply the same external decision", async () => temp(async (cwd) => {
  const facts = {
    ...request,
    subject: "staging deployment",
    scope: "staging only",
    answer: "The release board approved staging in meeting M-42.",
    decision_type: "approval" as const,
    source_kind: "external_artifact" as const,
    source_ref: "wiki:release-decisions/M-42",
    approving_party: "Release Board",
  };
  const testDirectory = join(cwd, ".kapisch", "runs", "test-adapter-run", "decisions");
  const testDecision = await testAdapterDecision(testDirectory, facts);
  assert.deepEqual(JSON.parse(await readFile(join(testDirectory, `${testDecision.decision_id}.json`), "utf8")), testDecision);
  const { answer, ...decisionRequest } = facts;
  const f = fixture([assistant(decisionRequest)], { cwd, sessionFile: join(cwd, "session-pi.jsonl") });
  assert.deepEqual(await f.input({ text: answer }, f.context), { action: "continue" });
  const directory = join(cwd, ".kapisch", "runs", "session-pi", "decisions");
  const [filename] = await readdir(directory);
  const piDecision = JSON.parse(await readFile(join(directory, filename), "utf8")) as PortableDecision;

  assert.deepEqual(portableDecisionFacts(piDecision), portableDecisionFacts(testDecision));
  assert.equal("operator_label" in piDecision, false);
  const workOrder = { id: "WO-1", subject: facts.subject, scope: facts.scope, tasks: [{ id: "T-1" }, { id: "T-2" }] };
  const piSnapshot = structuredClone(piDecision);
  const testSnapshot = structuredClone(testDecision);
  const piOutcome = applyCapturedPiDecision(piDecision, workOrder);
  const testOutcome = runTestAdapterWorkOrder(testDecision, workOrder);
  const normalizeOutcome = (outcome: AppliedWorkOrder) => ({ ...outcome, decision_ref: "<HumanDecision>" });
  const expectedOutcome = {
    work_order_id: "WO-1",
    status: "authorized",
    decision_ref: "<HumanDecision>",
    task_ids: ["T-1", "T-2"],
    evidence_refs: { governing_inputs: facts.governing_inputs, source_ref: facts.source_ref },
  };
  assert.deepEqual(normalizeOutcome(piOutcome), expectedOutcome);
  assert.deepEqual(normalizeOutcome(testOutcome), expectedOutcome);
  assert.equal(piOutcome.decision_ref, piDecision.decision_id);
  assert.equal(testOutcome.decision_ref, testDecision.decision_id);
  const outOfScope = { ...workOrder, scope: "production" };
  assert.equal(applyCapturedPiDecision(piDecision, outOfScope).status, "blocked");
  assert.equal(runTestAdapterWorkOrder(testDecision, outOfScope).status, "blocked");
  assert.deepEqual(piDecision, piSnapshot);
  assert.deepEqual(testDecision, testSnapshot);
}));

test("external-artifact decisions require a stable source reference", async () => temp(async (cwd) => {
  const f = fixture([assistant({ ...request, source_kind: "external_artifact" })], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "The artifact approves this scope." }, f.context), { action: "handled" });
  await assertNoDecisionFiles(cwd);
}));

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

test("captures effective user input across supported Pi modes and preserves decision facts", async () => temp(async (cwd) => {
  const cases = [
    { mode: "tui" as const, source_kind: "direct_operator", answer: "I approve the plan for staging only." },
    { mode: "rpc" as const, source_kind: "operator_reported_external", answer: "The Product Owner approved this scope yesterday.", approving_party: "Product Owner" },
    { mode: "json" as const, source_kind: "external_artifact", answer: "Maybe; I need to check the record.", source_ref: "https://example.invalid/decisions/42" },
  ];

  for (const [index, item] of cases.entries()) {
    const { mode, answer, source_kind, source_ref, approving_party } = item;
    const decisionMetadata = { source_kind, ...(source_ref ? { source_ref } : {}), ...(approving_party ? { approving_party } : {}) };
    const sessionFile = join(cwd, `session-${index}.jsonl`);
    const f = fixture([assistant({ ...request, ...decisionMetadata })], {
      cwd, mode, sessionFile, hasUI: mode !== "json",
    });
    assert.deepEqual(await f.input({ text: answer }, f.context), { action: "continue" });

    const directory = join(cwd, ".kapisch", "runs", `session-${index}`, "decisions");
    const [filename] = await readdir(directory);
    const decision = JSON.parse(await readFile(join(directory, filename), "utf8"));
    assert.match(decision.decision_id, /^[0-9a-f-]{36}$/);
    assert.equal(decision.question_id, request.question_id);
    assert.equal(decision.question, request.question);
    assert.deepEqual(decision.governing_inputs, request.governing_inputs);
    assert.equal(decision.subject, request.subject);
    assert.equal(decision.scope, request.scope);
    assert.equal(decision.answer, item.answer);
    assert.equal(decision.decision_type, request.decision_type);
    assert.equal(decision.source_kind, item.source_kind);
    assert.equal(decision.source_ref, item.source_ref);
    assert.equal(decision.approving_party, item.approving_party);
    assert.equal("authorization_granted" in decision, false);
  }
}));
