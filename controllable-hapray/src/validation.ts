import { access, realpath, stat } from "node:fs/promises";
import path from "node:path";
import type { RunRequest } from "./domain.js";

const choices = <T extends string>(value: unknown, allowed: readonly T[], fallback: T, field: string): T => {
  if (value === undefined) return fallback;
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new Error(`${field} must be one of ${allowed.join(", ")}`);
  }
  return value as T;
};

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export function parseRunRequest(value: unknown): RunRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("request body must be a JSON object");
  }
  const input = value as Record<string, unknown>;
  const request = optionalString(input.request);
  const projectRoot = optionalString(input.projectRoot);
  if (!request) throw new Error("request is required");
  if (!projectRoot || !path.isAbsolute(projectRoot)) {
    throw new Error("projectRoot must be an absolute path");
  }

  const opencodeInput = input.opencode;
  let opencode: RunRequest["opencode"];
  if (opencodeInput && typeof opencodeInput === "object" && !Array.isArray(opencodeInput)) {
    const raw = opencodeInput as Record<string, unknown>;
    const baseUrl = optionalString(raw.baseUrl);
    const agent = optionalString(raw.agent);
    const modelInput = raw.model;
    let model: NonNullable<RunRequest["opencode"]>["model"];
    if (modelInput && typeof modelInput === "object" && !Array.isArray(modelInput)) {
      const modelRaw = modelInput as Record<string, unknown>;
      const providerID = optionalString(modelRaw.providerID);
      const modelID = optionalString(modelRaw.modelID);
      if (!providerID || !modelID) throw new Error("opencode.model requires providerID and modelID");
      const variant = optionalString(modelRaw.variant);
      model = { providerID, modelID, ...(variant ? { variant } : {}) };
    }
    if (baseUrl || agent || model) {
      opencode = { ...(baseUrl ? { baseUrl } : {}), ...(agent ? { agent } : {}), ...(model ? { model } : {}) };
    }
  }

  const result: RunRequest = {
    request,
    projectRoot: path.resolve(projectRoot),
    kind: choices(input.kind, ["full", "existing-report"] as const, "full", "kind"),
    mode: choices(input.mode, ["quick", "full"] as const, "full", "mode"),
    runtimeTrack: choices(input.runtimeTrack, ["auto", "binary", "source"] as const, "auto", "runtimeTrack"),
    symbolRecovery: choices(input.symbolRecovery, ["auto", "always", "never"] as const, "auto", "symbolRecovery"),
  };
  for (const key of ["outputDir", "haprayRoot", "reportsPath", "sourceDir", "soDir", "repoRoot", "packageName", "testcase", "device"] as const) {
    const parsed = optionalString(input[key]);
    if (parsed) result[key] = parsed;
  }
  if (opencode) result.opencode = opencode;
  return result;
}

export async function validatePathGate(request: RunRequest): Promise<Record<string, unknown>> {
  const projectRoot = await requireDirectory(request.projectRoot, "projectRoot");
  request.projectRoot = projectRoot;

  if (request.kind === "existing-report" && !request.reportsPath) {
    throw new Error("reportsPath is required when kind is existing-report");
  }
  if (request.kind === "full" && !request.haprayRoot) {
    throw new Error("haprayRoot is required when kind is full");
  }
  if (request.haprayRoot && !path.isAbsolute(request.haprayRoot)) {
    throw new Error("haprayRoot must be an absolute path");
  }
  if (request.kind === "existing-report" && request.haprayRoot) {
    throw new Error("haprayRoot is only valid when kind is full");
  }

  for (const key of ["outputDir", "haprayRoot", "reportsPath", "sourceDir", "soDir", "repoRoot"] as const) {
    const value = request[key];
    if (!value) continue;
    request[key] = await requireDirectory(path.resolve(value), key);
  }

  if (request.reportsPath && !isWithin(projectRoot, request.reportsPath)) {
    throw new Error("reportsPath must be inside projectRoot to preserve the HapRay workspace invariant");
  }

  const serviceRoot = path.join(projectRoot, ".hapray-service");
  if (!isWithin(projectRoot, serviceRoot)) throw new Error("invalid service state path");
  return {
    projectRoot,
    outputDir: request.outputDir ?? path.join(projectRoot, "reports"),
    haprayRoot: request.haprayRoot ?? null,
    sourceDir: request.sourceDir ?? "skipped",
    soDir: request.soDir ?? "skipped",
    reportsPath: request.reportsPath ?? null,
    serviceRoot,
  };
}

async function requireDirectory(filename: string, field: string): Promise<string> {
  await access(filename);
  const info = await stat(filename);
  if (!info.isDirectory()) throw new Error(`${field} must be a directory: ${filename}`);
  return realpath(filename);
}

export function isWithin(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}
