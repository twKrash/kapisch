import { randomUUID } from "node:crypto";
import { mkdir, rename, unlink, writeFile } from "node:fs/promises";
import { userInfo } from "node:os";
import { basename, extname, join } from "node:path";

type SourceKind = "direct_operator" | "operator_reported_external" | "external_artifact";
type DecisionType =
  | "answer"
  | "correction"
  | "approval"
  | "risk_acceptance"
  | "external_effect_authorization";
type GoverningInput = { ref: string; digest: string };
type DecisionRequest = {
  question_id: string;
  question: string;
  governing_inputs: GoverningInput[];
  subject: string;
  scope: string;
  decision_type: DecisionType;
  source_kind: SourceKind;
  source_ref?: string;
  approving_party?: string;
};
type InputEvent = { text: string; source: string };
type Context = {
  cwd: string;
  mode: "tui" | "rpc" | "json" | "print";
  hasUI: boolean;
  ui: { notify(message: string): void };
  sessionManager: {
    getSessionFile(): string | undefined;
    getBranch(): Array<{ type?: string; message?: { role?: string; content?: unknown } }>;
  };
};
type PiApi = {
  on(event: "input", handler: (event: InputEvent, context: Context) => Promise<unknown>): void;
};

const sourceKinds = new Set<string>([
  "direct_operator",
  "operator_reported_external",
  "external_artifact",
]);
const decisionTypes = new Set<string>([
  "answer",
  "correction",
  "approval",
  "risk_acceptance",
  "external_effect_authorization",
]);
const markerPattern = /```kapisch-decision\s*\n([\s\S]*?)\n```/g;
const requiredFields = [
  "question_id",
  "question",
  "governing_inputs",
  "subject",
  "scope",
  "decision_type",
  "source_kind",
];
const optionalFields = ["source_ref", "approving_party"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isSourceKind(value: unknown): value is SourceKind {
  return typeof value === "string" && sourceKinds.has(value);
}

function isDecisionType(value: unknown): value is DecisionType {
  return typeof value === "string" && decisionTypes.has(value);
}

function isGoverningInput(value: unknown): value is GoverningInput {
  if (!isRecord(value)) return false;
  const keys = Object.keys(value);
  return (
    keys.length === 2 &&
    keys.includes("ref") &&
    keys.includes("digest") &&
    isNonEmptyString(value.ref) &&
    typeof value.digest === "string" &&
    /^[0-9a-f]{64}$/.test(value.digest)
  );
}

function messageText(content: unknown): string {
  if (!Array.isArray(content)) return "";
  const texts: string[] = [];
  for (const part of content) {
    if (
      typeof part === "object" &&
      part !== null &&
      "type" in part &&
      part.type === "text" &&
      "text" in part &&
      typeof part.text === "string"
    ) {
      texts.push(part.text);
    }
  }
  return texts.join("\n");
}

function parseRequest(value: unknown): DecisionRequest | undefined {
  if (!isRecord(value)) return;
  const keys = Object.keys(value);
  if (
    requiredFields.some((field) => !(field in value)) ||
    keys.some((field) => !requiredFields.includes(field) && !optionalFields.includes(field))
  ) {
    return;
  }
  const questionId = value.question_id;
  const question = value.question;
  const subject = value.subject;
  const scope = value.scope;
  const decisionType = value.decision_type;
  const sourceKind = value.source_kind;
  if (
    !isNonEmptyString(questionId) ||
    !isNonEmptyString(question) ||
    !isNonEmptyString(subject) ||
    !isNonEmptyString(scope) ||
    !isDecisionType(decisionType) ||
    !isSourceKind(sourceKind) ||
    !Array.isArray(value.governing_inputs)
  ) {
    return;
  }
  const governingInputs: GoverningInput[] = [];
  for (const input of value.governing_inputs) {
    if (!isGoverningInput(input)) return;
    governingInputs.push(input);
  }
  const sourceRef = value.source_ref;
  const approvingParty = value.approving_party;
  for (const metadata of [sourceRef, approvingParty]) {
    if (metadata !== undefined && metadata !== null && !isNonEmptyString(metadata)) return;
  }
  return {
    question_id: questionId,
    question,
    governing_inputs: governingInputs,
    subject,
    scope,
    decision_type: decisionType,
    source_kind: sourceKind,
    ...(isNonEmptyString(sourceRef) ? { source_ref: sourceRef } : {}),
    ...(isNonEmptyString(approvingParty) ? { approving_party: approvingParty } : {}),
  };
}

type DecisionRequestLookup =
  | { kind: "none" }
  | { kind: "invalid" }
  | { kind: "valid"; request: DecisionRequest };

function latestDecisionRequest(context: Context): DecisionRequestLookup {
  const branch = context.sessionManager.getBranch();
  let lastMessage: (typeof branch)[number] | undefined;
  for (let index = branch.length - 1; index >= 0; index -= 1) {
    const entry = branch[index];
    if (entry.type === "message" && entry.message) {
      lastMessage = entry;
      break;
    }
  }
  if (lastMessage?.message?.role !== "assistant") return { kind: "none" };
  const text = messageText(lastMessage.message.content);
  const starts = text.split("```kapisch-decision").length - 1;
  if (starts === 0) return { kind: "none" };
  const matches = [...text.matchAll(markerPattern)];
  if (starts !== 1 || matches.length !== 1) return { kind: "invalid" };
  try {
    const request = parseRequest(JSON.parse(matches[0][1]));
    return request ? { kind: "valid", request } : { kind: "invalid" };
  } catch {
    return { kind: "invalid" };
  }
}

function operatorLabel(): string | undefined {
  try {
    return userInfo().username || undefined;
  } catch {
    return;
  }
}

async function recordInput(event: InputEvent, context: Context): Promise<boolean> {
  const requestState = latestDecisionRequest(context);
  if (requestState.kind === "none" || !event.text.trim()) return true;
  if (requestState.kind === "invalid") {
    if (context.hasUI) {
      context.ui.notify("The decision request is invalid; input was not processed. Correct the request before proceeding.");
    }
    return false;
  }
  // shortcut: Pi cannot prove RPC locality, so only visible TUI input can answer a decision; upgrade when host provenance is available.
  if (!context.hasUI || context.mode !== "tui" || event.source !== "interactive") {
    if (context.hasUI) {
      context.ui.notify("Decision answers are accepted only from visible TUI input; this input was not processed.");
    }
    return false;
  }
  const request = requestState.request;

  const sessionFile = context.sessionManager.getSessionFile();
  if (!sessionFile) {
    context.ui.notify("HumanDecision capture requires a persistent Pi session; input was not processed.");
    return false;
  }
  const sessionId = basename(sessionFile, extname(sessionFile));
  if (!/^[A-Za-z0-9_-]+$/.test(sessionId)) {
    context.ui.notify("HumanDecision capture could not identify the Pi session; input was not processed.");
    return false;
  }
  const label = operatorLabel();
  const decision = {
    decision_id: randomUUID(),
    question_id: request.question_id,
    question: request.question,
    governing_inputs: request.governing_inputs,
    subject: request.subject,
    scope: request.scope,
    answer: event.text,
    decision_type: request.decision_type,
    source_kind: request.source_kind,
    ...(request.source_ref ? { source_ref: request.source_ref } : {}),
    ...(request.approving_party ? { approving_party: request.approving_party } : {}),
    ...(label ? { operator_label: label } : {}),
  };
  const directory = join(context.cwd, ".kapisch", "runs", sessionId, "decisions");
  const temporaryPath = join(directory, `.${decision.decision_id}.tmp`);
  try {
    await mkdir(directory, { recursive: true, mode: 0o700 });
    await writeFile(
      temporaryPath,
      `${JSON.stringify(decision, null, 2)}\n`,
      { flag: "wx", mode: 0o600 },
    );
    await rename(temporaryPath, join(directory, `${decision.decision_id}.json`));
    return true;
  } catch {
    await unlink(temporaryPath).catch(() => {});
    context.ui.notify("HumanDecision capture failed; no decision was recorded or processed. Retry the answer after storage is available.");
    return false;
  }
}

export default function registerHumanDecisions(pi: PiApi): void {
  pi.on("input", async (event, context) => ({
    action: (await recordInput(event, context)) ? "continue" : "handled",
  }));
}
