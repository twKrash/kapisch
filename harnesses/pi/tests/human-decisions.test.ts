import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import registerHumanDecisions from "../extensions/human-decisions.ts";

const request = { question_id: "Q-1", question: "May I proceed?", governing_inputs: [{ ref: "context:C0", digest: "a".repeat(64) }], subject: "release", scope: "staging", decision_type: "approval", source_kind: "direct_operator" };
function codeToken(text: string, lang = "kapisch-decision") {
  return { type: "code", lang, text, raw: "```" + lang + "\n" + text + "\n```" };
}
function assistant(value: unknown = request, stopReason = "stop", id = "assistant-1") {
  const text = `Approval needed.\n\n\`\`\`kapisch-decision\n${JSON.stringify(value)}\n\`\`\``;
  return { type: "message", id, testTokens: [codeToken(JSON.stringify(value))], message: { role: "assistant", stopReason, content: [{ type: "text", text }] } };
}
function assistantText(text: string, id = "assistant-text", testTokens: unknown[] = []) {
  return { type: "message", id, testTokens, message: { role: "assistant", stopReason: "stop", content: [{ type: "text", text }] } };
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

async function testAdapterDecision(directory: string, facts: Omit<PortableDecision, "decision_id">): Promise<PortableDecision> {
  const decision = { decision_id: "test-adapter-decision", ...facts };
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, `${decision.decision_id}.json`), `${JSON.stringify(decision, null, 2)}\n`, { flag: "wx" });
  return decision;
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
  } as never, async (text) => {
    const entry = (branch as any[]).find((item) => item.type === "message" && item.message.content?.[0]?.text === text);
    return entry?.testTokens ?? [];
  });
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

test("a later ordinary assistant message retires an older decision request", async () => temp(async (cwd) => {
  const f = fixture([assistant(), assistantText("Ordinary reply")], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "ordinary input" }, f.context), { action: "continue" });
  await assertNoDecisionFiles(cwd);
}));

test("agent or reviewer approval claims do not create a HumanDecision without a user answer request", async () => temp(async (cwd) => {
  const f = fixture([assistantText("The reviewer approved this scope.")], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "The agent says this is approved." }, f.context), { action: "continue" });
  await assertNoDecisionFiles(cwd);
}));

test("local token selection accepts only top-level exact-language code requests", async () => temp(async (cwd) => {
  const text = "local fixture";
  const valid = codeToken(JSON.stringify({ ...request, question_id: "Q-top-level" }), " kapisch-decision ");
  const nested = { type: "blockquote", tokens: [codeToken(JSON.stringify({ ...request, question_id: "Q-nested" }))] };
  const f = fixture([assistantText(text, "token-selection", [codeToken(JSON.stringify({ ...request, question_id: "Q-other" }), "json"), nested, valid])], {
    cwd, sessionFile: join(cwd, "session-token.jsonl"),
  });
  assert.deepEqual(await f.input({ text: "I approve." }, f.context), { action: "continue" });
  const directory = join(cwd, ".kapisch", "runs", "session-token", "decisions");
  const [filename] = await readdir(directory);
  assert.equal(JSON.parse(await readFile(join(directory, filename), "utf8")).question_id, "Q-top-level");
}));

test("unterminated and invalid closing fences do not capture decision answers", async () => temp(async (cwd) => {
  const payload = JSON.stringify(request);
  const cases = [
    ["unterminated", "```kapisch-decision\n" + payload],
    ["short-closer", "````kapisch-decision\n" + payload + "\n```"],
    ["mismatched-closer", "```kapisch-decision\n" + payload + "\n~~~"],
  ] as const;
  for (const [id, raw] of cases) {
    const token = { type: "code", lang: "kapisch-decision", text: payload, raw };
    const f = fixture([assistantText("local fixture", id, [token])], { cwd, sessionFile: join(cwd, `${id}.jsonl`) });
    assert.deepEqual(await f.input({ text: "Show me the release checklist." }, f.context), { action: "handled" });
    await assertNoDecisionFiles(cwd);
  }
}));

test("local token selection ignores nested, HTML, and nonmatching tokens", async () => temp(async (cwd) => {
  const tokens = [
    { type: "html", text: JSON.stringify(request) },
    { type: "list", items: [{ tokens: [codeToken(JSON.stringify(request))] }] },
    { type: "blockquote", tokens: [codeToken(JSON.stringify(request))] },
    codeToken(JSON.stringify(request), "kapisch-decision extra"),
  ];
  const f = fixture([assistantText("local fixture", "ignored-tokens", tokens)], {
    cwd, sessionFile: join(cwd, "session-ignored.jsonl"),
  });
  assert.deepEqual(await f.input({ text: "ordinary input" }, f.context), { action: "continue" });
  await assertNoDecisionFiles(cwd);
  await f.commands.get("kapisch-decision-repair")!("", f.context);
  await f.commands.get("kapisch-decision-dismiss")!("", f.context);
  assert.equal(f.sent.length, 0);
}));

test("local token selection fails closed for invalid and duplicate top-level requests", async () => temp(async (cwd) => {
  const cases = [
    [codeToken("{bad}")],
    [codeToken(JSON.stringify({ question_id: "bad" }))],
    [codeToken(JSON.stringify(request)), codeToken(JSON.stringify(request))],
  ];
  for (const [index, tokens] of cases.entries()) {
    const f = fixture([assistantText("local fixture", `invalid-${index}`, tokens)], { cwd, sessionFile: join(cwd, `invalid-${index}.jsonl`) });
    assert.deepEqual(await f.input({ text: "must not persist" }, f.context), { action: "handled" });
    await f.commands.get("kapisch-decision-repair")!("", f.context);
    assert.equal(f.sent[0]?.message.customType, "kapisch-decision-repair");
    assert.deepEqual(await readdir(join(cwd, ".kapisch", "runs", `invalid-${index}`, "decisions")).catch(() => []), []);
  }
}));

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

test("a persisted decision consumes its request after a session restart", async () => temp(async (cwd) => {
  const branch = [assistant()];
  const sessionFile = join(cwd, "session-1.jsonl");
  const first = fixture(branch, { cwd, sessionFile });
  assert.deepEqual(await first.input({ text: "I approve." }, first.context), { action: "continue" });
  const directory = join(cwd, ".kapisch", "runs", "session-1", "decisions");
  const [filename] = await readdir(directory);
  const original = await readFile(join(directory, filename), "utf8");

  const restarted = fixture(branch, { cwd, sessionFile });
  assert.deepEqual(await restarted.input({ text: "Show me the status" }, restarted.context), { action: "continue" });
  assert.deepEqual(await readdir(directory), [filename]);
  assert.equal(await readFile(join(directory, filename), "utf8"), original);
}));

test("canonical legacy HumanDecision files consume requests without mutation", async () => temp(async (cwd) => {
  const directory = join(cwd, ".kapisch", "runs", "session-1", "decisions");
  await mkdir(directory, { recursive: true });
  const decision = { decision_id: "123e4567-e89b-42d3-a456-426614174000", ...request, answer: "I approve." };
  const path = join(directory, `${decision.decision_id}.json`);
  const original = `${JSON.stringify(decision, null, 2)}\n`;
  await writeFile(path, original, { flag: "wx" });

  const f = fixture([assistant()], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "Show me the status" }, f.context), { action: "continue" });
  assert.deepEqual(await readdir(directory), [`${decision.decision_id}.json`]);
  assert.equal(await readFile(path, "utf8"), original);
}));

test("noncanonical decision filenames fail closed without replacing the request", async () => temp(async (cwd) => {
  const directory = join(cwd, ".kapisch", "runs", "session-1", "decisions");
  await mkdir(directory, { recursive: true });
  const decision = { decision_id: "123e4567-e89b-42d3-a456-426614174000", ...request, answer: "I approve." };
  const path = join(directory, "unrelated-name.json");
  const original = `${JSON.stringify(decision, null, 2)}\n`;
  await writeFile(path, original, { flag: "wx" });

  const f = fixture([assistant()], { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  assert.deepEqual(await f.input({ text: "Show me the status" }, f.context), { action: "handled" });
  assert.deepEqual(await readdir(directory), ["unrelated-name.json"]);
  assert.equal(await readFile(path, "utf8"), original);
}));

test("conflicting or invalid persisted decisions fail closed in either file order", async () => temp(async (cwd) => {
  const directory = join(cwd, ".kapisch", "runs", "session-1", "decisions");
  await mkdir(directory, { recursive: true });
  const id1 = "123e4567-e89b-42d3-a456-426614174001";
  const id2 = "123e4567-e89b-42d3-a456-426614174002";
  const cases = [
    [{ decision_id: id1, ...request, answer: "No, do not deploy." }, { decision_id: id2, ...request, answer: "Yes, deploy." }],
    [{ decision_id: id1, ...request, answer: "Yes, deploy." }, { decision_id: id2, ...request, answer: "No, do not deploy." }],
    [{ decision_id: id1, ...request, answer: "I approve." }, { decision_id: id2, ...request, scope: "production", answer: "I approve." }],
  ];
  for (const [index, records] of cases.entries()) {
    const session = `session-${index + 1}`;
    const caseDirectory = join(cwd, ".kapisch", "runs", session, "decisions");
    await mkdir(caseDirectory, { recursive: true });
    const originals = await Promise.all(records.map(async (record) => {
      const path = join(caseDirectory, `${record.decision_id}.json`);
      const text = `${JSON.stringify(record, null, 2)}\n`;
      await writeFile(path, text, { flag: "wx" });
      return [path, text] as const;
    }));
    const f = fixture([assistant()], { cwd, sessionFile: join(cwd, `${session}.jsonl`) });
    assert.deepEqual(await f.input({ text: "Show me the status" }, f.context), { action: "handled" });
    assert.deepEqual(await Promise.all(originals.map(([path]) => readFile(path, "utf8"))), originals.map(([, text]) => text));
    assert.deepEqual((await readdir(caseDirectory)).sort(), records.map((record) => `${record.decision_id}.json`).sort());
  }
}));

test("repeated and concurrent delivery creates one immutable decision per request", async () => temp(async (cwd) => {
  const branch = [assistant()];
  const f = fixture(branch, { cwd, sessionFile: join(cwd, "session-1.jsonl") });
  const results = await Promise.all([
    f.input({ text: "Answer one" }, f.context),
    f.input({ text: "Answer two" }, f.context),
  ]);
  assert.deepEqual(results, [{ action: "continue" }, { action: "continue" }]);
  const directory = join(cwd, ".kapisch", "runs", "session-1", "decisions");
  const [filename] = await readdir(directory);
  const original = await readFile(join(directory, filename), "utf8");
  assert.deepEqual(await f.input({ text: "Repeated answer" }, f.context), { action: "continue" });
  assert.deepEqual(await readdir(directory), [filename]);
  assert.equal(await readFile(join(directory, filename), "utf8"), original);

  branch.push(assistant({ ...request, question_id: "Q-2", question: "May I continue?" }, "stop", "assistant-2"));
  assert.deepEqual(await f.input({ text: "A new answer" }, f.context), { action: "continue" });
  assert.equal((await readdir(directory)).length, 2);
  assert.equal(await readFile(join(directory, filename), "utf8"), original);
}));

test("decision IDs stay unique across sessions for the same question ID", async () => temp(async (cwd) => {
  for (const session of ["session-1", "session-2"]) {
    const f = fixture([assistant()], { cwd, sessionFile: join(cwd, `${session}.jsonl`) });
    assert.deepEqual(await f.input({ text: "I approve." }, f.context), { action: "continue" });
  }
  const files = await Promise.all(["session-1", "session-2"].map(async (session) => {
    const directory = join(cwd, ".kapisch", "runs", session, "decisions");
    const [filename] = await readdir(directory);
    return JSON.parse(await readFile(join(directory, filename), "utf8"));
  }));
  assert.notEqual(files[0].decision_id, files[1].decision_id);
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
  assert.match(f.notices[0], /could not be read/i);
  assert.deepEqual(await readdir(runDirectory), ["decisions"]);
  await rm(join(runDirectory, "decisions"));
  assert.deepEqual(await f.input({ text: "I approve." }, f.context), { action: "continue" });
  assert.equal((await readdir(join(runDirectory, "decisions"))).length, 1);
}));

test("Pi and host-independent test adapters preserve the same portable decision facts", async () => temp(async (cwd) => {
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
  const piSnapshot = structuredClone(piDecision);
  const testSnapshot = structuredClone(testDecision);

  assert.deepEqual(portableDecisionFacts(piDecision), portableDecisionFacts(testDecision));
  assert.equal("operator_label" in piDecision, false);
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

test("request validation rejects malformed and duplicate selected token content", async () => temp(async (cwd) => {
  const cases = [
    [codeToken("{bad}")],
    [codeToken(JSON.stringify({ question_id: "Q-1" }))],
    [codeToken(JSON.stringify({ ...request, unexpected: true }))],
    [codeToken(JSON.stringify({ ...request, source_kind: "reviewer" }))],
    [codeToken(JSON.stringify({ ...request, governing_inputs: [{ ref: "x", digest: "bad" }] }))],
    [codeToken(JSON.stringify(request)), codeToken(JSON.stringify(request))],
  ];
  for (const [index, tokens] of cases.entries()) {
    const f = fixture([assistantText("local token fixture", `bad-${index}`, tokens)], { cwd, sessionFile: join(cwd, `bad-${index}.jsonl`) });
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
