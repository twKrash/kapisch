import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import registerHumanDecisions from "../extensions/human-decisions.ts";

const request = {
  question_id: "Q-1",
  question: "May I proceed to staging?",
  governing_inputs: [{ ref: "context:C0", digest: "a".repeat(64) }],
  subject: "release plan",
  scope: "staging only",
  decision_type: "approval",
  source_kind: "direct_operator",
};

function setup() {
  const handlers: Array<(event: unknown, context: unknown) => Promise<unknown>> = [];
  registerHumanDecisions({
    on(event: string, handler: (event: unknown, context: unknown) => Promise<unknown>) {
      assert.equal(event, "input");
      handlers.push(handler);
    },
  } as never);
  return handlers[0];
}

function context(
  cwd: string,
  branch: unknown[],
  hasUI = true,
  sessionFile: string | null = "/tmp/session-1.jsonl",
  mode: "tui" | "rpc" | "json" | "print" = "tui",
) {
  const notifications: string[] = [];
  return {
    cwd,
    mode,
    hasUI,
    notifications,
    ui: { notify(message: string) { notifications.push(message); } },
    sessionManager: {
      getSessionFile: () => sessionFile ?? undefined,
      getBranch: () => branch,
    },
  };
}

function assistantText(text: string) {
  return {
    type: "message",
    message: { role: "assistant", content: [{ type: "text", text }] },
  };
}

function assistantRequest(value = request) {
  return assistantText(`Approval needed.\n\n\`\`\`kapisch-decision\n${JSON.stringify(value)}\n\`\`\``);
}

async function withTempDir(run: (cwd: string) => Promise<void>) {
  const cwd = await mkdtemp(join(tmpdir(), "kapisch-decision-"));
  try {
    await run(cwd);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
}

test("records a decision only from a real user input after a decision request", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const result = await handleInput(
      { text: "Proceed to staging, not production.", source: "interactive" },
      context(cwd, [assistantRequest()]),
    );
    const dir = join(cwd, ".kapisch", "runs", "session-1", "decisions");
    const [filename] = await readdir(dir);
    const record = JSON.parse(await readFile(join(dir, filename), "utf8"));

    assert.deepEqual(result, { action: "continue" });
    assert.equal(record.question_id, "Q-1");
    assert.equal(record.answer, "Proceed to staging, not production.");
    assert.equal(record.source_kind, "direct_operator");
    assert.equal("source_ref" in record, false);
    assert.equal("approving_party" in record, false);
    assert.equal(record.operator_label.length > 0, true);
  });
});

test("blocks extension-injected and headless input while a decision is pending", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const branch = [assistantRequest()];
    const injected = await handleInput(
      { text: "Agent recommendation: approve.", source: "extension" },
      context(cwd, branch),
    );
    const headless = await handleInput(
      { text: "Reviewer: approve.", source: "interactive" },
      context(cwd, branch, false),
    );

    assert.deepEqual(injected, { action: "handled" });
    assert.deepEqual(headless, { action: "handled" });
    await assert.rejects(readdir(join(cwd, ".kapisch", "runs", "session-1", "decisions")));
  });
});

test("blocks RPC input while a decision is pending because locality is unproven", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const ctx = context(cwd, [assistantRequest()], true, "/tmp/session-1.jsonl", "rpc");
    const result = await handleInput({ text: "Proceed.", source: "rpc" }, ctx);

    assert.deepEqual(result, { action: "handled" });
    assert.deepEqual(ctx.notifications, [
      "Decision answers are accepted only from visible TUI input; this input was not processed.",
    ]);
    await assert.rejects(readdir(join(cwd, ".kapisch", "runs", "session-1", "decisions")));
  });
});

test("preserves external-source attribution and permits absent optional metadata", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const externalRequest = {
      ...request,
      source_kind: "external_artifact",
      source_ref: "https://tracker.example/decision/42",
      approving_party: "Product Owner",
    };
    await handleInput(
      { text: "The linked approval covers staging only.", source: "interactive" },
      context(cwd, [assistantRequest(externalRequest)]),
    );
    const dir = join(cwd, ".kapisch", "runs", "session-1", "decisions");
    const [filename] = await readdir(dir);
    const record = JSON.parse(await readFile(join(dir, filename), "utf8"));

    assert.equal(record.source_kind, "external_artifact");
    assert.equal(record.source_ref, externalRequest.source_ref);
    assert.equal(record.approving_party, "Product Owner");
  });
});

test("blocks malformed or duplicate marked decision requests without processing the answer", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const validBlock = `\`\`\`kapisch-decision\n${JSON.stringify(request)}\n\`\`\``;
    const malformedMessages = [
      `\`\`\`kapisch-decision\n{not json}\n\`\`\``,
      `\`\`\`kapisch-decision\n${JSON.stringify({ ...request, governing_inputs: [{ ref: "context:C0", digest: "bad" }] })}\n\`\`\``,
      `\`\`\`kapisch-decision\n${JSON.stringify({ question_id: "Q-1" })}\n\`\`\``,
      `${validBlock}\n${validBlock}`,
      "```kapisch-decision\n{\"question_id\":\"Q-1\"}",
    ];

    for (const text of malformedMessages) {
      const ctx = context(
        cwd,
        [assistantText(`Approval needed.\n\n${text}`)],
      );
      const result = await handleInput({ text: "AUTHORIZE", source: "interactive" }, ctx);

      assert.deepEqual(result, { action: "handled" });
      assert.deepEqual(ctx.notifications, [
        "The decision request is invalid; input was not processed. Correct the request before proceeding.",
      ]);
    }

    await assert.rejects(readdir(join(cwd, ".kapisch", "runs", "session-1", "decisions")));
  });
});

test("does not create a decision for an ordinary assistant message", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const branch = [{ type: "message", message: { role: "assistant", content: [{ type: "text", text: "Here is my recommendation." }] } }];
    await handleInput({ text: "Thanks.", source: "interactive" }, context(cwd, branch));

    await assert.rejects(readdir(join(cwd, ".kapisch", "runs", "session-1", "decisions")));
  });
});

test("reports when a persistent session is required", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const ctx = context(cwd, [assistantRequest()], true, null);
    const result = await handleInput({ text: "Proceed.", source: "interactive" }, ctx);

    assert.deepEqual(result, { action: "handled" });
    assert.deepEqual(ctx.notifications, [
      "HumanDecision capture requires a persistent Pi session; input was not processed.",
    ]);
  });
});

test("blocks the answer when durable capture fails", async () => {
  await withTempDir(async (cwd) => {
    await writeFile(join(cwd, ".kapisch"), "not a directory");
    const handleInput = setup();
    const ctx = context(cwd, [assistantRequest()]);
    const result = await handleInput(
      { text: "Proceed to staging.", source: "interactive" },
      ctx,
    );

    assert.deepEqual(result, { action: "handled" });
    assert.deepEqual(ctx.notifications, [
      "HumanDecision capture failed; no decision was recorded or processed. Retry the answer after storage is available.",
    ]);
  });
});

test("rejects agent/reviewer as a decision source", async () => {
  await withTempDir(async (cwd) => {
    const handleInput = setup();
    const invalid = { ...request, source_kind: "reviewer" };
    await handleInput(
      { text: "Approve.", source: "interactive" },
      context(cwd, [assistantRequest(invalid)]),
    );

    await assert.rejects(readdir(join(cwd, ".kapisch", "runs", "session-1", "decisions")));
  });
});
