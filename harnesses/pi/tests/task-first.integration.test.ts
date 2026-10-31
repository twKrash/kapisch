import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { test } from "node:test";
import registerHumanDecisions from "../extensions/human-decisions.ts";

const projectRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "../../..");
const runId = "shared-run";
const runDir = ".kapisch/runs/" + runId;
const runRef = runDir + "/run.json";
const answer = "I authorize the bounded staging change.";
const request = {
  question_id: "question-1",
  run_id: runId,
  question: "Authorize the bounded staging change?",
  governing_inputs: [{ ref: "docs/spec.md", digest: "" }],
  subject: "bounded staging change",
  scope: "staging only",
  decision_type: "approval",
  source_kind: "direct_operator",
};
const digest = (value: Uint8Array | string) => createHash("sha256").update(value).digest("hex");
const fence = String.fromCharCode(96).repeat(3);

function python(root: string, body: string) {
  return execFileSync("python3", ["-c", body, root, runRef], {
    encoding: "utf8",
    env: { ...process.env, PYTHONPATH: resolve(projectRoot, "core") },
  }).trim();
}

// Independent reimplementation of the documented derivation: first 16 bytes of
// sha256(identity + "\0" + question_id) rendered as a version-5-shaped UUID.
function portableDecisionId(identity: string, questionId: string): string {
  const bytes = createHash("sha256").update(identity + "\0" + questionId).digest().subarray(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
}

async function gitProject(root: string) {
  await mkdir(join(root, "docs"), { recursive: true });
  await writeFile(join(root, "docs/spec.md"), "approved staging requirements\n");
  execFileSync("git", ["init", "-q", root]);
  execFileSync("git", ["-C", root, "config", "user.email", "test@example.invalid"]);
  execFileSync("git", ["-C", root, "config", "user.name", "Test"]);
  execFileSync("git", ["-C", root, "add", "docs/spec.md"]);
  execFileSync("git", ["-C", root, "commit", "-qm", "governing input"]);
}

async function save(root: string, ref: string, record: unknown): Promise<string> {
  const path = join(root, ref);
  await mkdir(resolve(path, ".."), { recursive: true });
  const bytes = JSON.stringify(record, null, 2) + "\n";
  await writeFile(path, bytes);
  return digest(bytes);
}

async function acceptWithAdapter(root: string, decision: Record<string, any>) {
  const decisionRef = runDir + "/decisions/" + decision.decision_id + ".json";
  const decisionPath = join(root, decisionRef);
  let decisionDigest: string;
  try {
    decisionDigest = digest(await readFile(decisionPath));
  } catch {
    decisionDigest = await save(root, decisionRef, decision);
  }
  const inputs = [{ ref: "docs/spec.md", digest: digest(await readFile(join(root, "docs/spec.md"))) }];
  const applicabilityRef = runDir + "/applicability.json";
  const applicability = {
    decision_id: decision.decision_id,
    decision_ref: decisionRef,
    decision_digest: decisionDigest,
    answer_digest: digest(decision.answer),
    subject: request.subject,
    scope: request.scope,
    governing_inputs: inputs,
    result: "applicable",
    reason: "The user explicitly authorized this exact bounded scope.",
    host_native_fallback_authorized: true,
    fallback_authorization_reason: "The user authorized the bounded host-native route.",
  };
  const applicabilityDigest = await save(root, applicabilityRef, applicability);
  const workRef = runDir + "/workorder.json";
  const work = {
    workorder_id: "workorder-1",
    decision_id: decision.decision_id,
    decision_ref: decisionRef,
    decision_digest: decisionDigest,
    applicability_ref: applicabilityRef,
    applicability_digest: applicabilityDigest,
    subject: request.subject,
    scope: request.scope,
    task: { task_id: "task-1" },
    acceptance_criteria: ["produced valid evidence for the scoped change"],
    governing_inputs: inputs,
    required_capabilities: ["write"],
    worker_route: "host_native_fallback",
    worker_role: "worker",
    canonical_implementer_available: false,
  };
  const workDigest = await save(root, workRef, work);
  const attemptId = "attempt-1";
  const outputRef = runDir + "/attempts/" + attemptId + "-output.json";
  const run: Record<string, any> = {
    run_id: runId,
    workorder_ref: workRef,
    workorder_digest: workDigest,
    attempt_allocation: { attempt_id: attemptId, output_ref: outputRef },
  };
  await save(root, runRef, run);
  const dispatch = JSON.parse(python(root,
    "import sys; from kapisch_core.task_contract import claim_dispatch; " +
    "print(__import__('json').dumps(claim_dispatch(sys.argv[1], sys.argv[2], " +
    "capabilities={'write': {'status': 'supported', 'reason': 'available'}}, " +
    "canonical_implementer_available=False)['attempt_allocation']))"));
  assert.equal(dispatch.attempt_id, attemptId);
  const outputDigest = await save(root, outputRef, { evidence: "test adapter completed the task" });
  const attemptRef = runDir + "/attempts/" + attemptId + ".json";
  const attempt = {
    attempt_id: attemptId,
    task_id: "task-1",
    workorder_id: work.workorder_id,
    workorder_ref: workRef,
    workorder_digest: workDigest,
    decision_id: decision.decision_id,
    decision_digest: decisionDigest,
    status: "succeeded",
    output_ref: outputRef,
    output_digest: outputDigest,
  };
  const attemptDigest = await save(root, attemptRef, attempt);
  const aggregationRef = runDir + "/aggregation.json";
  const report = {
    coverage: ["task-1"],
    acceptance_criteria: ["produced valid evidence for the scoped change"],
    result: "complete",
    attempt_ref: attemptRef,
    attempt_digest: attemptDigest,
    output_ref: outputRef,
    output_digest: outputDigest,
    attempt_id: attemptId,
    task_id: "task-1",
    workorder_ref: workRef,
    workorder_id: work.workorder_id,
    workorder_digest: workDigest,
    decision_id: decision.decision_id,
    decision_digest: decisionDigest,
    failures: [],
    conflicts: [],
    missing_references: [],
    unresolved_issues: [],
  };
  const aggregationDigest = await save(root, aggregationRef, report);
  Object.assign(run, {
    attempt_ref: attemptRef,
    attempt_digest: attemptDigest,
    aggregation_ref: aggregationRef,
    aggregation_digest: aggregationDigest,
  });
  await save(root, runRef, run);
  const accepted = JSON.parse(python(root,
    "import json, sys; from kapisch_core.task_contract import validate_acceptance; " +
    "print(json.dumps(validate_acceptance(sys.argv[1], sys.argv[2], " +
    "capabilities={'write': {'status': 'supported', 'reason': 'available'}}), sort_keys=True))"));
  const outcomeRef = runDir + "/outcome.json";
  const outcomeDigest = await save(root, outcomeRef, accepted);
  Object.assign(run, { outcome_ref: outcomeRef, outcome_digest: outcomeDigest });
  await save(root, runRef, run);
  return JSON.parse(python(root,
    "import json, sys; from kapisch_core.task_contract import validate_outcome; " +
    "print(json.dumps(validate_outcome(sys.argv[1], sys.argv[2], " +
    "capabilities={'write': {'status': 'supported', 'reason': 'fresh process'}}), sort_keys=True))"));
}

test("Pi decision capture and the deterministic adapter accept the same portable WorkOrder", async () => {
  const root = await mkdtemp(join(tmpdir(), "task-first-pi-"));
  try {
    await gitProject(root);
    request.governing_inputs[0].digest = digest(await readFile(join(root, "docs/spec.md")));
    const payload = JSON.stringify(request);
    const raw = fence + "kapisch-decision\n" + payload + "\n" + fence;
    const branch: any[] = [{
      type: "message",
      id: "decision-request",
      testTokens: [{ type: "code", lang: "kapisch-decision", text: payload, raw }],
      message: { role: "assistant", stopReason: "stop", content: [{ type: "text", text: raw }] },
    }];
    let inputHandler: (event: any, context: any) => Promise<any> = async () => ({ action: "handled" });
    registerHumanDecisions({
      on(_event: string, handler: any) { inputHandler = handler; },
      registerCommand() {},
      sendMessage() {},
    } as never, async () => [{ type: "code", lang: "kapisch-decision", text: payload, raw }]);
    const result = await inputHandler({ text: answer }, {
      cwd: root,
      mode: "tui",
      hasUI: true,
      ui: { notify() {} },
      sessionManager: { getBranch: () => branch, getSessionFile: () => undefined },
    });
    assert.deepEqual(result, { action: "continue" });
    const decisionDirectory = join(root, runDir, "decisions");
    const [filename] = await readdir(decisionDirectory);
    const piDecision = JSON.parse(await readFile(join(decisionDirectory, filename), "utf8"));
    const piOutcome = await acceptWithAdapter(root, piDecision);

    const testRoot = join(root, "test-adapter");
    await mkdir(testRoot);
    await gitProject(testRoot);
    const derivedId = portableDecisionId(runId, request.question_id);
    assert.equal(piDecision.decision_id, derivedId);
    const testDecision = {
      decision_id: derivedId,
      question_id: request.question_id,
      question: request.question,
      governing_inputs: request.governing_inputs,
      subject: request.subject,
      scope: request.scope,
      answer,
      decision_type: request.decision_type,
      source_kind: request.source_kind,
    };
    assert.deepEqual(testDecision, piDecision);
    const testOutcome = await acceptWithAdapter(testRoot, testDecision);
    assert.deepEqual(piOutcome, testOutcome);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
