import { createHash, randomUUID } from "node:crypto";
import { link, mkdir, readFile, readdir, realpath, unlink, writeFile } from "node:fs/promises";
import { basename, dirname, extname, isAbsolute, join, relative } from "node:path";

type SourceKind = "direct_operator" | "operator_reported_external" | "external_artifact";
type DecisionType = "answer" | "correction" | "approval" | "risk_acceptance" | "external_effect_authorization";
type DecisionRequest = {
  question_id: string;
  run_id?: string;
  question: string;
  governing_inputs: Array<{ ref: string; digest: string }>;
  subject: string;
  scope: string;
  decision_type: DecisionType;
  source_kind: SourceKind;
  source_ref?: string;
  approving_party?: string;
};
type BranchEntry =
  | { type: "message"; id: string; message: { role?: string; content?: unknown; stopReason?: string; errorMessage?: string } }
  | { type: "custom_message"; id: string; parentId?: string; customType: string; content: unknown; details?: unknown };
type Context = {
  cwd: string;
  mode: "tui" | "rpc" | "json" | "print";
  hasUI: boolean;
  ui: { notify(message: string, type?: "info" | "warning" | "error"): void };
  sessionManager: { getBranch(): BranchEntry[]; getSessionFile(): string | undefined };
};
type PiApi = {
  on(event: "input", handler: (event: { text: string; images?: unknown[]; streamingBehavior?: string }, context: Context) => Promise<unknown>): void;
  registerCommand(name: string, options: { description: string; handler(args: string, context: Context): Promise<void> }): void;
  sendMessage(message: { customType: string; content: string; display: boolean }, options: { triggerTurn: true }): void;
};

const sourceKinds = new Set<string>(["direct_operator", "operator_reported_external", "external_artifact"]);
const decisionTypes = new Set<string>(["answer", "correction", "approval", "risk_acceptance", "external_effect_authorization"]);
type MarkdownToken = { type: string; lang?: string; text?: string; raw?: string };
type DecisionLexer = (text: string) => Promise<MarkdownToken[]>;

let markedInstance: Promise<{ lexer(text: string): MarkdownToken[] }> | undefined;
const markedLexer: DecisionLexer = async (text) => {
  markedInstance ??= import("@earendil-works/pi-tui").then(({ Marked }) => new Marked());
  return (await markedInstance).lexer(text);
};
const requiredFields = ["question_id", "question", "governing_inputs", "subject", "scope", "decision_type", "source_kind"];
const optionalFields = ["source_ref", "approving_party", "run_id"];

type DecisionRequestLookup =
  | { kind: "none" }
  | { kind: "invalid" }
  | { kind: "valid"; request: DecisionRequest };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseRequest(value: unknown): DecisionRequest | undefined {
  if (!isRecord(value)) return;
  const keys = Object.keys(value);
  if (requiredFields.some((field) => !(field in value)) || keys.some((field) => !requiredFields.includes(field) && !optionalFields.includes(field))) return;
  if (!isNonEmptyString(value.question_id) || !isNonEmptyString(value.question) || !isNonEmptyString(value.subject) || !isNonEmptyString(value.scope) || typeof value.decision_type !== "string" || !decisionTypes.has(value.decision_type) || typeof value.source_kind !== "string" || !sourceKinds.has(value.source_kind) || !Array.isArray(value.governing_inputs)) return;
  const governingInputs: DecisionRequest["governing_inputs"] = [];
  for (const input of value.governing_inputs) {
    if (!isRecord(input) || Object.keys(input).length !== 2 || !isNonEmptyString(input.ref) || typeof input.digest !== "string" || !/^[0-9a-f]{64}$/.test(input.digest)) return;
    governingInputs.push({ ref: input.ref, digest: input.digest });
  }
  if (value.run_id !== undefined && (typeof value.run_id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(value.run_id))) return;
  for (const metadata of [value.source_ref, value.approving_party]) {
    if (metadata !== undefined && metadata !== null && !isNonEmptyString(metadata)) return;
  }
  if (value.source_kind === "external_artifact" && !isNonEmptyString(value.source_ref)) return;
  return {
    question_id: value.question_id,
    ...(typeof value.run_id === "string" ? { run_id: value.run_id } : {}),
    question: value.question,
    governing_inputs: governingInputs,
    subject: value.subject,
    scope: value.scope,
    decision_type: value.decision_type as DecisionType,
    source_kind: value.source_kind as SourceKind,
    ...(isNonEmptyString(value.source_ref) ? { source_ref: value.source_ref } : {}),
    ...(isNonEmptyString(value.approving_party) ? { approving_party: value.approving_party } : {}),
  };
}

function messageText(content: unknown): string {
  if (!Array.isArray(content)) return "";
  return content.flatMap((part) => isRecord(part) && part.type === "text" && typeof part.text === "string" ? [part.text] : []).join("\n");
}

async function decisionBlocks(text: string, lexer: DecisionLexer): Promise<MarkdownToken[]> {
  return (await lexer(text)).filter((token) => token.type === "code" && token.lang?.trim() === "kapisch-decision");
}

function hasClosedDecisionFence(raw: string | undefined, language: string): boolean {
  if (!raw) return false;
  const lines = raw.split(/\r?\n/);
  const opening = lines[0]?.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
  if (!opening || opening[2].trim() !== language) return false;
  const fence = opening[1];
  return lines.slice(1).some((line) => {
    const closing = line.match(/^ {0,3}(`+|~+)[\t ]*$/);
    return closing !== null && closing[1][0] === fence[0] && closing[1].length >= fence.length;
  });
}

async function requestState(text: string, message: BranchEntry & { type: "message" }, lexer: DecisionLexer): Promise<DecisionRequestLookup> {
  const blocks = await decisionBlocks(text, lexer);
  if (blocks.length === 0) return { kind: "none" };
  if (blocks.length > 1 || message.message.stopReason !== "stop" || message.message.errorMessage) return { kind: "invalid" };
  if (blocks.some((token) => !hasClosedDecisionFence(token.raw, token.lang?.trim() ?? ""))) return { kind: "invalid" };
  try {
    const request = parseRequest(JSON.parse(blocks[0].text ?? ""));
    return request ? { kind: "valid", request } : { kind: "invalid" };
  } catch {
    return { kind: "invalid" };
  }
}

async function latestDecisionRequest(context: Context, lexer: DecisionLexer): Promise<DecisionRequestLookup> {
  const branch = context.sessionManager.getBranch();
  for (let index = branch.length - 1; index >= 0; index -= 1) {
    const entry = branch[index];
    if (entry.type === "custom_message" && entry.customType === "kapisch-decision-dismiss") return { kind: "none" };
    if (entry.type !== "message" || entry.message.role !== "assistant") continue;
    // A later ordinary assistant message retires older markers.
    return requestState(messageText(entry.message.content), entry, lexer);
  }
  return { kind: "none" };
}

function matchesRequest(value: unknown, request: DecisionRequest): value is Record<string, unknown> & { decision_id: string; answer: string } {
  if (!isRecord(value) || typeof value.decision_id !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value.decision_id) || !isNonEmptyString(value.answer)) return false;
  if (value.question_id !== request.question_id || value.question !== request.question || value.subject !== request.subject || value.scope !== request.scope || value.decision_type !== request.decision_type || value.source_kind !== request.source_kind || value.source_ref !== request.source_ref || value.approving_party !== request.approving_party) return false;
  return Array.isArray(value.governing_inputs) && value.governing_inputs.length === request.governing_inputs.length && value.governing_inputs.every((input, index) => isRecord(input) && input.ref === request.governing_inputs[index].ref && input.digest === request.governing_inputs[index].digest);
}

async function existingDecision(directory: string, request: DecisionRequest): Promise<boolean | undefined> {
  let filenames: string[];
  try {
    filenames = await readdir(directory);
  } catch (error) {
    if (isRecord(error) && error.code === "ENOENT") return false;
    return;
  }
  const answers = new Set<string>();
  try {
    for (const filename of filenames.filter((name) => name.endsWith(".json")).sort()) {
      const value: unknown = JSON.parse(await readFile(join(directory, filename), "utf8"));
      if (!isRecord(value) || value.question_id !== request.question_id) continue;
      if (!matchesRequest(value, request) || filename !== `${value.decision_id}.json`) return;
      answers.add(value.answer);
    }
  } catch {
    return;
  }
  if (answers.size > 1) return;
  return answers.size === 1;
}


function decisionId(identity: string, questionId: string): string {
  const bytes = createHash("sha256").update(identity + "\0" + questionId).digest().subarray(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
}
// Sole HumanDecision producer at the Pi human input boundary; the controller binds, but does not recreate, this record.
function decisionIdentity(request: DecisionRequest, context: Context): string | undefined {
  if (request.run_id) return request.run_id;
  const sessionFile = context.sessionManager.getSessionFile();
  if (!sessionFile) {
    if (context.hasUI) context.ui.notify("HumanDecision capture requires a persistent Pi session; input was not processed.", "warning");
    return;
  }
  const sessionId = basename(sessionFile, extname(sessionFile));
  if (!/^[A-Za-z0-9_-]+$/.test(sessionId)) {
    if (context.hasUI) context.ui.notify("HumanDecision capture could not identify the Pi session; input was not processed.", "error");
    return;
  }
  return sessionId;
}

function isWithin(root: string, path: string): boolean {
  const pathFromRoot = relative(root, path);
  return pathFromRoot === "" || (!pathFromRoot.startsWith("..") && !isAbsolute(pathFromRoot));
}

async function decisionDirectory(cwd: string, identity: string): Promise<string> {
  const root = await realpath(cwd);
  const directory = join(root, ".kapisch", "runs", identity, "decisions");
  let ancestor = directory;
  while (true) {
    try {
      ancestor = await realpath(ancestor);
      break;
    } catch (error) {
      if (!isRecord(error) || error.code !== "ENOENT") throw error;
      const parent = dirname(ancestor);
      if (parent === ancestor) throw error;
      ancestor = parent;
    }
  }
  if (!isWithin(root, ancestor)) throw new Error("decision directory escapes project root");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const resolved = await realpath(directory);
  if (!isWithin(root, resolved)) throw new Error("decision directory escapes project root");
  return resolved;
}

async function recordDecision(text: string, request: DecisionRequest, identity: string, directory: string): Promise<boolean> {
  const consumed = await existingDecision(directory, request);
  if (consumed !== false) return consumed === true;

  const decision = {
    decision_id: decisionId(identity, request.question_id),
    question_id: request.question_id,
    question: request.question,
    governing_inputs: request.governing_inputs,
    subject: request.subject,
    scope: request.scope,
    answer: text,
    decision_type: request.decision_type,
    source_kind: request.source_kind,
    ...(request.source_ref ? { source_ref: request.source_ref } : {}),
    ...(request.approving_party ? { approving_party: request.approving_party } : {}),
  };
  const temporaryPath = join(directory, "." + randomUUID() + ".tmp");
  try {
    await writeFile(temporaryPath, JSON.stringify(decision, null, 2) + "\n", { flag: "wx", mode: 0o600 });
    await link(temporaryPath, join(directory, decision.decision_id + ".json"));
    await unlink(temporaryPath).catch(() => {});
    return true;
  } catch (error) {
    await unlink(temporaryPath).catch(() => {});
    if (isRecord(error) && error.code === "EEXIST") return await existingDecision(directory, request) === true;
    return false;
  }
}

export default function registerHumanDecisions(pi: PiApi, lexer: DecisionLexer = markedLexer): void {
  pi.on("input", async (event, context) => {
    const pending = await latestDecisionRequest(context, lexer);
    if (pending.kind === "none") return { action: "continue" };
    if (pending.kind === "invalid") {
      if (context.hasUI) context.ui.notify("The decision request is invalid; input was not processed. Repair the request before proceeding.", "warning");
      return { action: "handled" };
    }
    const identity = decisionIdentity(pending.request, context);
    if (!identity) return { action: "handled" };
    let directory: string;
    try {
      directory = await decisionDirectory(context.cwd, identity);
    } catch {
      if (context.hasUI) context.ui.notify("HumanDecision state could not be read or safely written; input was not processed.", "error");
      return { action: "handled" };
    }
    const consumed = await existingDecision(directory, pending.request);
    if (consumed === true) return { action: "continue" };
    if (consumed === undefined) {
      if (context.hasUI) context.ui.notify("HumanDecision state could not be read; input was not processed.", "error");
      return { action: "handled" };
    }
    if (!event.text.trim()) {
      if (context.hasUI) context.ui.notify("A text answer is required for this pending decision request.", "warning");
      return { action: "handled" };
    }
    const stored = await recordDecision(event.text, pending.request, identity, directory);
    if (!stored) {
      if (context.hasUI) context.ui.notify("HumanDecision capture failed; no decision was recorded or processed. Retry after storage is available.", "error");
      return { action: "handled" };
    }
    return { action: "continue" };
  });
  pi.registerCommand("kapisch-decision", {
    description: "Show how to answer the pending decision request",
    handler: async (_args, context) => {
      const pending = await latestDecisionRequest(context, lexer);
      if (pending.kind === "none") {
        if (context.hasUI) context.ui.notify("No pending decision request is available.", "warning");
        return;
      }
      if (context.hasUI) context.ui.notify(pending.kind === "valid"
        ? "Answer through normal Pi input. The effective user message is recorded verbatim before it is forwarded."
        : "The decision request is invalid. Use /kapisch-decision-repair to ask the agent to regenerate it.", pending.kind === "valid" ? "info" : "warning");
    },
  });
  pi.registerCommand("kapisch-decision-dismiss", {
    description: "Dismiss a pending decision request without granting authorization",
    handler: async (_args, context) => {
      if ((await latestDecisionRequest(context, lexer)).kind === "none") {
        if (context.hasUI) context.ui.notify("No pending decision request is available.", "warning");
        return;
      }
      pi.sendMessage({
        customType: "kapisch-decision-dismiss",
        content: "The user dismissed the pending decision request without supplying a decision. This dismissal does not grant a decision or authorization. Keep the gated workflow blocked and report the unresolved decision requirement.",
        display: false,
      }, { triggerTurn: true });
      if (context.hasUI) context.ui.notify("The pending request was dismissed without authorization. Gated work remains blocked.", "info");
    },
  });
  pi.registerCommand("kapisch-decision-repair", {
    description: "Ask the agent to regenerate an invalid decision request",
    handler: async (_args, context) => {
      if ((await latestDecisionRequest(context, lexer)).kind !== "invalid") {
        if (context.hasUI) context.ui.notify("No invalid decision request needs repair.", "warning");
        return;
      }
      pi.sendMessage({ customType: "kapisch-decision-repair", content: "The previous kapisch-decision request was invalid. Regenerate the request with exactly one valid kapisch-decision JSON block. This is a repair instruction only; it grants no decision or authorization.", display: false }, { triggerTurn: true });
    },
  });
}
