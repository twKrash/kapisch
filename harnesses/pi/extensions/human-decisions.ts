type SourceKind = "direct_operator" | "operator_reported_external" | "external_artifact";
type DecisionType = "answer" | "correction" | "approval" | "risk_acceptance" | "external_effect_authorization";
type DecisionRequest = {
  question_id: string;
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
  mode: "tui" | "rpc" | "json" | "print";
  hasUI: boolean;
  ui: { notify(message: string, type?: "info" | "warning" | "error"): void };
  sessionManager: { getBranch(): BranchEntry[] };
};
type PiApi = {
  on(event: "input", handler: (event: { text: string; images?: unknown[]; streamingBehavior?: string }, context: Context) => Promise<unknown>): void;
  registerCommand(name: string, options: { description: string; handler(args: string, context: Context): Promise<void> }): void;
  sendMessage(message: { customType: string; content: string; display: boolean }, options: { triggerTurn: true }): void;
};

const sourceKinds = new Set<string>(["direct_operator", "operator_reported_external", "external_artifact"]);
const decisionTypes = new Set<string>(["answer", "correction", "approval", "risk_acceptance", "external_effect_authorization"]);
type MarkdownFence = { character: "`" | "~"; length: number; indent: number; info: string; containerIndent?: number; content: string[] };
type ListContext = { markerIndent: number; contentIndent: number };

const listItemPattern = /^([ \t]*)([-+*]|\d+[.)])([ \t]+)(.*)$/;
const listFenceOpeningPattern = /^([ \t]*)([-+*]|\d+[.)])([ \t]+)(`{3,}|~{3,})(.*)$/;
const fenceOpeningPattern = /^([ \t]*)(`{3,}|~{3,})(.*)$/;
const fenceClosingPattern = /^([ \t]*)(`+|~+)[ \t]*$/;
const requiredFields = ["question_id", "question", "governing_inputs", "subject", "scope", "decision_type", "source_kind"];
const optionalFields = ["source_ref", "approving_party"];

type RequestState = "none" | "invalid" | "valid";

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
  for (const metadata of [value.source_ref, value.approving_party]) {
    if (metadata !== undefined && metadata !== null && !isNonEmptyString(metadata)) return;
  }
  return {
    question_id: value.question_id,
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

function indentationWidth(prefix: string): number {
  let width = 0;
  for (const character of prefix) width += character === "\t" ? 4 - (width % 4) : 1;
  return width;
}

function lineIndentation(line: string): number {
  return indentationWidth(/^[ \t]*/.exec(line)?.[0] ?? "");
}

function listItem(line: string): ListContext | undefined {
  const match = listItemPattern.exec(line);
  if (!match) return;
  const markerIndent = indentationWidth(match[1]);
  const contentIndent = indentationWidth(`${match[1]}${match[2]}${match[3]}`);
  return { markerIndent, contentIndent };
}

function updateListContexts(line: string, contexts: ListContext[]): void {
  if (line.trim() === "") return;
  const indent = lineIndentation(line);
  while (contexts.length > 0 && indent < contexts[contexts.length - 1].contentIndent) contexts.pop();

  const item = listItem(line);
  if (!item || (contexts.length === 0 ? item.markerIndent > 3 : item.markerIndent < contexts[contexts.length - 1].contentIndent || item.markerIndent > contexts[contexts.length - 1].contentIndent + 3)) return;
  while (contexts.length > 0 && item.markerIndent <= contexts[contexts.length - 1].markerIndent) contexts.pop();
  contexts.push(item);
}

function makeFence(marker: string, info: string, indent: number, containerIndent?: number): MarkdownFence | undefined {
  const character = marker[0];
  if ((character !== "`" && character !== "~") || (character === "`" && info.includes("`"))) return;
  return { character, length: marker.length, indent, info: info.trim(), ...(containerIndent !== undefined ? { containerIndent } : {}), content: [] };
}

function parseFenceOpening(line: string, contexts: ListContext[]): MarkdownFence | undefined {
  const listMatch = listFenceOpeningPattern.exec(line);
  const context = contexts[contexts.length - 1];
  if (listMatch && context?.markerIndent === indentationWidth(listMatch[1])) {
    return makeFence(listMatch[4], listMatch[5], 0, context.contentIndent);
  }

  const match = fenceOpeningPattern.exec(line);
  if (!match) return;
  const containerIndent = context?.contentIndent ?? 0;
  const indent = indentationWidth(match[1]) - containerIndent;
  if (indent < 0 || indent > 3) return;
  return makeFence(match[2], match[3], indent, containerIndent > 0 ? containerIndent : undefined);
}

function isFenceClosing(line: string, fence: MarkdownFence): boolean {
  const match = fenceClosingPattern.exec(line);
  if (!match || match[2][0] !== fence.character || match[2].length < fence.length) return false;
  const indent = indentationWidth(match[1]) - (fence.containerIndent ?? 0);
  return indent >= 0 && indent <= 3;
}

function decisionBlocks(text: string): string[] {
  const blocks: string[] = [];
  const contexts: ListContext[] = [];
  let fence: MarkdownFence | undefined;

  for (const line of text.split(/\r?\n/)) {
    if (fence?.containerIndent !== undefined && line.trim() !== "" && lineIndentation(line) < fence.containerIndent) fence = undefined;
    if (fence) {
      if (isFenceClosing(line, fence)) {
        // shortcut: only column-zero, non-list request fences are active; widen if the producer emits indented blocks.
        if (fence.character === "`" && fence.containerIndent === undefined && fence.info === "kapisch-decision" && fence.indent === 0 && fence.length === 3) blocks.push(fence.content.join("\n"));
        fence = undefined;
      } else {
        fence.content.push(line);
      }
      continue;
    }

    updateListContexts(line, contexts);
    fence = parseFenceOpening(line, contexts);
  }

  return blocks;
}

function requestState(text: string, message: BranchEntry & { type: "message" }): RequestState {
  const blocks = decisionBlocks(text);
  if (blocks.length === 0) return "none";
  if (blocks.length > 1 || message.message.stopReason !== "stop" || message.message.errorMessage) return "invalid";
  try { return parseRequest(JSON.parse(blocks[0])) ? "valid" : "invalid"; }
  catch { return "invalid"; }
}

function latestDecisionRequest(context: Context): RequestState {
  const branch = context.sessionManager.getBranch();
  for (let index = branch.length - 1; index >= 0; index -= 1) {
    const entry = branch[index];
    if (entry.type === "custom_message" && entry.customType === "kapisch-decision-dismiss") return "none";
    if (entry.type !== "message" || entry.message.role !== "assistant") continue;
    // A later ordinary assistant message retires older markers.
    return requestState(messageText(entry.message.content), entry);
  }
  return "none";
}

export default function registerHumanDecisions(pi: PiApi): void {
  pi.on("input", async (_event, context) => {
    if (latestDecisionRequest(context) === "none") return { action: "continue" };
    if (context.hasUI) {
      context.ui.notify("Input was not forwarded because a decision request is pending and this Pi host cannot establish immutable original-input provenance. Use /kapisch-decision-dismiss to dismiss it; dismissal does not authorize the gated workflow.", "warning");
    }
    return { action: "handled" };
  });
  pi.registerCommand("kapisch-decision", {
    description: "Explain that this Pi host cannot safely capture a decision",
    handler: async (_args, context) => {
      if (latestDecisionRequest(context) === "none") {
        context.ui.notify("No pending decision request is available.", "warning");
        return;
      }
      context.ui.notify("HumanDecision capture is unavailable: this Pi host cannot establish immutable original-input provenance. No prompt was opened and no decision or authorization was recorded.", "error");
    },
  });
  pi.registerCommand("kapisch-decision-dismiss", {
    description: "Dismiss a pending decision request without granting authorization",
    handler: async (_args, context) => {
      if (latestDecisionRequest(context) === "none") {
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
      if (latestDecisionRequest(context) !== "invalid") {
        context.ui.notify("No invalid decision request needs repair.", "warning");
        return;
      }
      pi.sendMessage({ customType: "kapisch-decision-repair", content: "The previous kapisch-decision request was invalid. Regenerate the request with exactly one valid kapisch-decision JSON block. This is a repair instruction only; it grants no decision or authorization.", display: false }, { triggerTurn: true });
    },
  });
}
