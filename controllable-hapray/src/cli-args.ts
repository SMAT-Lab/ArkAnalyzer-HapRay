import path from "node:path";
import type { RunKind, RunRequest } from "./domain.js";

export interface CliOptions {
  request: RunRequest;
  json: boolean;
}

const VALUE_OPTIONS = new Set([
  "--agent",
  "--device",
  "--hapray-root",
  "--kind",
  "--mode",
  "--model",
  "--opencode-url",
  "--output-dir",
  "--package-name",
  "--project-root",
  "--repo-root",
  "--reports",
  "--request",
  "--runtime-track",
  "--so",
  "--source",
  "--symbol-recovery",
  "--testcase",
]);

const EXISTING_REPORT_REQUEST = "Mine the performance issues, corresponding evidence, root causes, and actionable suggestions from the supplied HapRay profiling data. Analyze the raw evidence from the beginning and ignore existing agent-authored analysis reports.";
const FULL_RUN_REQUEST = "Collect a HapRay performance profile from the connected device, analyze performance issues and root causes from the raw evidence, and produce actionable recommendations.";

export function parseCliArgs(argv: string[]): CliOptions {
  const values = new Map<string, string>();
  const flags = new Set<string>();
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (!argument?.startsWith("--")) throw new Error(`Unexpected argument: ${argument ?? ""}`);
    if (argument === "--json") {
      flags.add(argument);
      continue;
    }
    if (!VALUE_OPTIONS.has(argument)) throw new Error(`Unknown option: ${argument}`);
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) throw new Error(`Missing value for ${argument}`);
    values.set(argument, value);
    index += 1;
  }

  const projectRoot = required(values, "--project-root");
  const reportsPath = values.get("--reports");
  const haprayRoot = values.get("--hapray-root");
  const kind = choice(values.get("--kind"), ["full", "existing-report"] as const, reportsPath ? "existing-report" : "full");
  validateKindOptions(kind, reportsPath, haprayRoot);
  const prompt = values.get("--request") ?? (kind === "existing-report" ? EXISTING_REPORT_REQUEST : FULL_RUN_REQUEST);
  const mode = choice(values.get("--mode"), ["quick", "full"] as const, "full");
  const runtimeTrack = choice(values.get("--runtime-track"), ["auto", "binary", "source"] as const, "auto");
  const symbolRecovery = choice(values.get("--symbol-recovery"), ["auto", "always", "never"] as const, "auto");
  const model = parseModel(values.get("--model"));
  const baseUrl = values.get("--opencode-url");
  const agent = values.get("--agent");
  const request: RunRequest = {
    request: prompt,
    projectRoot: path.resolve(projectRoot),
    ...(values.get("--output-dir") ? { outputDir: path.resolve(values.get("--output-dir")!) } : {}),
    kind,
    ...(haprayRoot ? { haprayRoot: path.resolve(haprayRoot) } : {}),
    ...(reportsPath ? { reportsPath: path.resolve(reportsPath) } : {}),
    mode,
    runtimeTrack,
    symbolRecovery,
    ...(values.get("--source") ? { sourceDir: path.resolve(values.get("--source")!) } : {}),
    ...(values.get("--so") ? { soDir: path.resolve(values.get("--so")!) } : {}),
    ...(values.get("--repo-root") ? { repoRoot: path.resolve(values.get("--repo-root")!) } : {}),
    ...(values.get("--package-name") ? { packageName: values.get("--package-name")! } : {}),
    ...(values.get("--testcase") ? { testcase: values.get("--testcase")! } : {}),
    ...(values.get("--device") ? { device: values.get("--device")! } : {}),
    ...((baseUrl || agent || model) ? {
      opencode: {
        ...(baseUrl ? { baseUrl } : {}),
        ...(agent ? { agent } : {}),
        ...(model ? { model } : {}),
      },
    } : {}),
  };
  return { request, json: flags.has("--json") };
}

export const CLI_HELP = `Usage:
  npm run analyze -- --project-root <path> --reports <path> [options]
  npm run analyze -- --kind full --project-root <path> --hapray-root <path> [collection options]

Required:
  --project-root <path>        Workspace root for service state and intermediates
  --reports <path>             Existing profiling case directory (existing-report only)
  --hapray-root <path>         HapRay tool/runtime directory (full only)

Options:
  --kind <kind>                full or existing-report (inferred from --reports; otherwise full)
  --package-name <id>          Application bundle/package ID for collection
  --testcase <name>            Preset or requested PerfLoad_* test case
  --device <serial>            HDC target serial (optional with one connected device)
  --runtime-track <track>      auto, binary, or source (default: auto)
  --repo-root <path>           HapRay source repository for the source runtime track
  --source <path>              Application TypeScript/ETS source directory
  --so <path>                  Application SO library directory
  --output-dir <path>          Final report directory (default: <project-root>/reports)
  --request <text>             Analysis request (from-scratch analysis is the default)
  --model <provider/model>     OpenCode model, e.g. deepseek/deepseek-v4-flash
  --agent <name>               OpenCode agent name
  --mode <quick|full>          Analysis mode (default: full)
  --symbol-recovery <policy>   auto, always, or never (default: auto)
  --opencode-url <url>         Attach to an existing OpenCode server
  --json                       Emit workflow events as JSON Lines

Environment:
  HAPRAY_SKILL_ROOT            External HapRay skill directory containing SKILL.md (required)
`;

function required(values: Map<string, string>, name: string): string {
  const value = values.get(name);
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function validateKindOptions(kind: RunKind, reportsPath: string | undefined, haprayRoot: string | undefined): void {
  if (kind === "existing-report" && !reportsPath) {
    throw new Error("--reports is required when --kind is existing-report");
  }
  if (kind === "full" && reportsPath) {
    throw new Error("--reports is only valid when --kind is existing-report");
  }
  if (kind === "full" && !haprayRoot) {
    throw new Error("--hapray-root is required when --kind is full");
  }
  if (kind === "existing-report" && haprayRoot) {
    throw new Error("--hapray-root is only valid when --kind is full");
  }
}

function choice<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  if (!value) return fallback;
  if (!allowed.includes(value as T)) throw new Error(`Expected one of ${allowed.join(", ")}, got ${value}`);
  return value as T;
}

function parseModel(value: string | undefined): { providerID: string; modelID: string } | undefined {
  if (!value) return undefined;
  const slash = value.indexOf("/");
  if (slash <= 0 || slash === value.length - 1) throw new Error("--model must use provider/model format");
  return { providerID: value.slice(0, slash), modelID: value.slice(slash + 1) };
}
