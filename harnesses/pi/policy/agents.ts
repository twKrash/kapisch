export type PiAgentPolicy = {
  readonly capabilityClass: "read-only" | "writer";
  readonly tools: readonly string[];
  readonly excludeTools: readonly string[];
  readonly permissions?: Readonly<Record<string, "allow" | "ask" | "deny">>;
  readonly acceptanceRole: "read-only" | "writer";
  readonly defaultContext: "fresh";
  readonly inheritProjectContext: true;
  readonly inheritGlobalContext: false;
  readonly inheritSkills: false;
  readonly allowNestedSubagents: false;
};

const readOnlyTools = ["read", "grep", "find", "ls"] as const;
const gitEvidenceTools = [...readOnlyTools, "bash"] as const;
const writerTools = [...readOnlyTools, "bash", "edit", "write"] as const;
const readOnlyPermissions = { edit: "deny", write: "deny" } as const;

export const agentPolicy = {
  "kapisch-architect": {
    capabilityClass: "read-only", tools: readOnlyTools, excludeTools: ["edit", "write"],
    permissions: readOnlyPermissions, acceptanceRole: "read-only", defaultContext: "fresh",
    inheritProjectContext: true, inheritGlobalContext: false, inheritSkills: false,
    allowNestedSubagents: false,
  },
  "kapisch-researcher": {
    capabilityClass: "read-only", tools: gitEvidenceTools, excludeTools: ["edit", "write"],
    permissions: readOnlyPermissions, acceptanceRole: "read-only", defaultContext: "fresh",
    inheritProjectContext: true, inheritGlobalContext: false, inheritSkills: false,
    allowNestedSubagents: false,
  },
  "kapisch-reviewer": {
    capabilityClass: "read-only", tools: gitEvidenceTools, excludeTools: ["edit", "write"],
    permissions: readOnlyPermissions, acceptanceRole: "read-only", defaultContext: "fresh",
    inheritProjectContext: true, inheritGlobalContext: false, inheritSkills: false,
    allowNestedSubagents: false,
  },
  "kapisch-implementer": {
    capabilityClass: "writer", tools: writerTools, excludeTools: [],
    acceptanceRole: "writer", defaultContext: "fresh", inheritProjectContext: true,
    inheritGlobalContext: false, inheritSkills: false, allowNestedSubagents: false,
  },
  "kapisch-implementer-lite": {
    capabilityClass: "writer", tools: writerTools, excludeTools: [],
    acceptanceRole: "writer", defaultContext: "fresh", inheritProjectContext: true,
    inheritGlobalContext: false, inheritSkills: false, allowNestedSubagents: false,
  },
  "kapisch-mechanic": {
    capabilityClass: "writer", tools: writerTools, excludeTools: [],
    acceptanceRole: "writer", defaultContext: "fresh", inheritProjectContext: true,
    inheritGlobalContext: false, inheritSkills: false, allowNestedSubagents: false,
  },
} as const satisfies Record<string, PiAgentPolicy>;
