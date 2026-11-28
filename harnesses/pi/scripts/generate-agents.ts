import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { agentPolicy } from "../policy/agents.ts";

export type CanonicalAgent = {
  name: keyof typeof agentPolicy;
  description: string;
  developer_instructions: string;
  model: string;
  model_reasoning_effort: "low" | "medium" | "high";
};

const names = [
  "kapisch-architect",
  "kapisch-researcher",
  "kapisch-implementer",
  "kapisch-implementer-lite",
  "kapisch-mechanic",
  "kapisch-reviewer",
] as const;
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const outputDir = join(dirname(fileURLToPath(import.meta.url)), "../agents");
const reviewerOutputDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../skills/kapisch/references",
);
const reviewerBaseFiles = [
  "reviewer-baseline.md",
  "review.md",
  "risk.md",
  "severity.md",
];
const pythonParser = [
  "import json, pathlib, sys, tomllib",
  "print(json.dumps([tomllib.loads(pathlib.Path(p).read_text(encoding='utf-8')) for p in sys.argv[1:]], ensure_ascii=False))",
].join("; ");

function parseCanonicalToml(root: string, files: string[]): CanonicalAgent[] {
  const python = process.platform === "win32" ? "python" : "python3";
  const raw = execFileSync(
    python,
    ["-c", pythonParser, ...files.map((file) => join(root, file))],
    {
      cwd: root,
      encoding: "utf8",
    },
  );
  return JSON.parse(raw) as CanonicalAgent[];
}

export async function canonicalAgents(
  root: URL | string = repoRoot,
): Promise<CanonicalAgent[]> {
  const rootPath = root instanceof URL ? fileURLToPath(root) : root;
  const files = names.map((name) => `plugins/kapisch/agents/${name}.toml`);
  const profiles = parseCanonicalToml(rootPath, files);
  if (
    profiles.length !== names.length ||
    profiles.some((profile, index) => profile.name !== names[index])
  ) {
    throw new Error(
      "Canonical KAPISCH agent files do not match the required six-role catalog",
    );
  }
  for (const profile of profiles) {
    if (
      !profile.description ||
      !profile.developer_instructions ||
      !profile.model ||
      !profile.model_reasoning_effort
    ) {
      throw new Error(
        `Canonical KAPISCH agent is missing required fields: ${profile.name}`,
      );
    }
    if (!(profile.model_reasoning_effort in { low: 1, medium: 1, high: 1 })) {
      throw new Error(
        `Unsupported reasoning effort for ${profile.name}: ${profile.model_reasoning_effort}`,
      );
    }
  }
  return profiles;
}

function piModel(model: string): string {
  if (model.startsWith("openai/")) return model;
  if (!/^gpt-[a-zA-Z0-9.-]+$/.test(model))
    throw new Error(`Unsupported canonical model identifier: ${model}`);
  return `openai/${model}`;
}

export function generateAgentMarkdown(profile: CanonicalAgent): string {
  const policy = agentPolicy[profile.name];
  const lines = [
    "---",
    `name: ${JSON.stringify(profile.name)}`,
    `description: ${JSON.stringify(profile.description)}`,
    `model: ${profile.name === "kapisch-reviewer" ? "openai/gpt-6.1-sol" : piModel(profile.model)}`,
    `thinking: ${profile.model_reasoning_effort}`,
    `tools: ${policy.tools.join(", ")}`,
    `acceptanceRole: ${policy.acceptanceRole}`,
    `defaultContext: ${policy.defaultContext}`,
    `inheritProjectContext: ${policy.inheritProjectContext}`,
    `inheritGlobalContext: ${policy.inheritGlobalContext}`,
    `inheritSkills: ${policy.inheritSkills}`,
    `allowNestedSubagents: ${policy.allowNestedSubagents}`,
  ];
  if (policy.excludeTools.length)
    lines.push(`excludeTools: ${policy.excludeTools.join(", ")}`);
  if (policy.permissions) {
    lines.push(
      "permissions:",
      ...Object.entries(policy.permissions).map(
        ([tool, permission]) => `  ${tool}: ${permission}`,
      ),
    );
  }
  return `${lines.join("\n")}\n---\n${profile.developer_instructions}`;
}

export async function expectedAgents(
  root: URL | string = repoRoot,
): Promise<Map<string, string>> {
  const profiles = await canonicalAgents(root);
  return new Map(
    profiles.map((profile) => [profile.name, generateAgentMarkdown(profile)]),
  );
}

export async function expectedReviewerResources(
  root: URL | string = repoRoot,
): Promise<Map<string, string>> {
  const rootPath = root instanceof URL ? fileURLToPath(root) : root;
  const sourceDir = join(
    rootPath,
    "plugins/kapisch/skills/kapisch/references",
  );
  const files = new Map<string, string>();
  for (const name of reviewerBaseFiles)
    files.set(name, readFileSync(join(sourceDir, name), "utf8"));
  const methodologyDir = join(sourceDir, "reviewer-methodologies");
  for (const entry of readdirSync(methodologyDir, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
    const relative = `reviewer-methodologies/${entry.name}`;
    files.set(relative, readFileSync(join(sourceDir, relative), "utf8"));
  }
  return files;
}

function compareNames(left: string, right: string): number {
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

function generatedReviewerResourceFiles(): string[] {
  const base = readdirSync(reviewerOutputDir)
    .filter((file: string) => file.endsWith(".md"))
    .sort(compareNames);
  const methodology = readdirSync(
    join(reviewerOutputDir, "reviewer-methodologies"),
  )
    .filter((file: string) => file.endsWith(".md"))
    .map((file: string) => `reviewer-methodologies/${file}`)
    .sort(compareNames);
  return [...base, ...methodology].sort(compareNames);
}

function generatedAgentFilesAreCurrent(files: Map<string, string>): boolean {
  const actual = readdirSync(outputDir)
    .filter((file: string) => file.endsWith(".md"))
    .sort(compareNames);
  const expected = [...files.keys()]
    .map((name) => `${name}.md`)
    .sort(compareNames);
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.error(
      `Generated agent file set differs. Expected: ${expected.join(", ")}; found: ${actual.join(", ")}`,
    );
    return false;
  }
  for (const [name, content] of files) {
    if (readFileSync(join(outputDir, `${name}.md`), "utf8") !== content) {
      console.error(`Generated Pi agent is stale: ${name}.md`);
      return false;
    }
  }
  return true;
}

function generatedReviewerResourcesAreCurrent(
  resources: Map<string, string>,
): boolean {
  const actual = generatedReviewerResourceFiles();
  const expected = [...resources.keys()].sort(compareNames);
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.error(
      `Generated reviewer resource file set differs. Expected: ${expected.join(", ")}; found: ${actual.join(", ")}`,
    );
    return false;
  }
  for (const [relative, content] of resources) {
    if (readFileSync(join(reviewerOutputDir, relative), "utf8") !== content) {
      console.error(`Generated Pi reviewer resource is stale: ${relative}`);
      return false;
    }
  }
  return true;
}

function writeGeneratedFiles(files: Map<string, string>): void {
  mkdirSync(outputDir, { recursive: true });
  for (const [name, content] of files)
    writeFileSync(join(outputDir, `${name}.md`), content, "utf8");
}

function writeReviewerResources(resources: Map<string, string>): void {
  mkdirSync(reviewerOutputDir, { recursive: true });
  for (const [relative, content] of resources) {
    const target = join(reviewerOutputDir, relative);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, content, "utf8");
  }
}

export async function main(args = process.argv.slice(2)): Promise<number> {
  const check = args.length === 1 && args[0] === "--check";
  if (args.length > 0 && !check)
    throw new Error(
      "Usage: bun harnesses/pi/scripts/generate-agents.ts [--check]",
    );
  const [files, reviewerResources] = await Promise.all([
    expectedAgents(repoRoot),
    expectedReviewerResources(repoRoot),
  ]);
  if (check) {
    if (
      !generatedAgentFilesAreCurrent(files) ||
      !generatedReviewerResourcesAreCurrent(reviewerResources)
    )
      return 1;
    console.log("Pi agents and reviewer resources are current.");
    return 0;
  }
  writeGeneratedFiles(files);
  writeReviewerResources(reviewerResources);
  console.log(
    `Generated ${files.size} Pi agents and ${reviewerResources.size} reviewer resources.`,
  );
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main()
    .then((code) => {
      process.exitCode = code;
    })
    .catch((error: unknown) => {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    });
}
