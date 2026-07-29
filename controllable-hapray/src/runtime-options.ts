import { readdir, realpath, stat } from "node:fs/promises";
import path from "node:path";
import { createOpencodeClient } from "@opencode-ai/sdk/v2";
import type { RunRequest } from "./domain.js";
import { createHdcCommand, type HdcCommand } from "./hdc-preview.js";

export interface RuntimeOption {
  id: string;
  label: string;
  detail?: string;
  providerID?: string;
}

export interface RuntimeOptionCatalog {
  agents: RuntimeOption[];
  providers: RuntimeOption[];
  models: RuntimeOption[];
  devices: RuntimeOption[];
  packages: RuntimeOption[];
  testcases: RuntimeOption[];
  errors: string[];
}

export interface RuntimeOptionQuery {
  projectRoot?: string;
  haprayRoot?: string;
  device?: string;
  opencodeBaseUrl?: string;
}

export interface RuntimeOptionSource {
  load(query?: RuntimeOptionQuery): Promise<RuntimeOptionCatalog>;
  validate(request: RunRequest): Promise<void>;
}

export class RuntimeOptionsService implements RuntimeOptionSource {
  readonly #hdc: HdcCommand;
  readonly #discoverOpenCode: (projectRoot: string, baseUrl?: string) => Promise<Pick<RuntimeOptionCatalog, "agents" | "providers" | "models">>;

  constructor(
    hdc: HdcCommand = createHdcCommand(),
    discoverOpenCode?: (projectRoot: string, baseUrl?: string) => Promise<Pick<RuntimeOptionCatalog, "agents" | "providers" | "models">>,
  ) {
    this.#hdc = hdc;
    this.#discoverOpenCode = discoverOpenCode ?? ((projectRoot, baseUrl) => this.#openCode(projectRoot, baseUrl));
  }

  async load(query: RuntimeOptionQuery = {}): Promise<RuntimeOptionCatalog> {
    const catalog: RuntimeOptionCatalog = {
      agents: [], providers: [], models: [], devices: [], packages: [], testcases: [], errors: [],
    };
    const projectRoot = await existingDirectory(query.projectRoot) ?? process.cwd();
    const [opencode, devices, testcases] = await Promise.allSettled([
      this.#discoverOpenCode(projectRoot, query.opencodeBaseUrl),
      this.#devices(),
      query.haprayRoot ? discoverTestcases(query.haprayRoot) : Promise.resolve([]),
    ]);
    if (opencode.status === "fulfilled") Object.assign(catalog, opencode.value);
    else catalog.errors.push(`OpenCode options: ${errorMessage(opencode.reason)}`);
    if (devices.status === "fulfilled") catalog.devices = devices.value;
    else catalog.errors.push(`HDC devices: ${errorMessage(devices.reason)}`);
    if (testcases.status === "fulfilled") catalog.testcases = testcases.value;
    else catalog.errors.push(`HapRay testcases: ${errorMessage(testcases.reason)}`);

    const target = query.device || (catalog.devices.length === 1 ? catalog.devices[0]?.id : undefined);
    if (target && catalog.devices.some((device) => device.id === target)) {
      try {
        catalog.packages = await this.#packages(target);
      } catch (error) {
        catalog.errors.push(`HDC packages: ${errorMessage(error)}`);
      }
    }
    return catalog;
  }

  async validate(request: RunRequest): Promise<void> {
    const needsOpenCode = Boolean(request.opencode?.baseUrl || request.opencode?.agent || request.opencode?.model);
    const needsRuntime = request.kind === "full" && Boolean(request.device || request.packageName || request.testcase);
    if (!needsOpenCode && !needsRuntime) return;
    const catalog = await this.load({
      projectRoot: request.projectRoot,
      ...(request.haprayRoot ? { haprayRoot: request.haprayRoot } : {}),
      ...(request.device ? { device: request.device } : {}),
      ...(request.opencode?.baseUrl ? { opencodeBaseUrl: request.opencode.baseUrl } : {}),
    });
    const openCodeError = catalog.errors.find((error) => error.startsWith("OpenCode options:"));
    if (needsOpenCode && openCodeError) throw new Error(openCodeError);
    if (request.opencode?.agent && !catalog.agents.some((option) => option.id === request.opencode?.agent)) {
      throw new Error(`opencode.agent is not available: ${request.opencode.agent}`);
    }
    const model = request.opencode?.model;
    if (model && !catalog.models.some((option) => option.id === model.modelID && option.providerID === model.providerID)) {
      throw new Error(`OpenCode model is not available: ${model.providerID}/${model.modelID}`);
    }
    if (request.kind !== "full") return;
    if (request.device && !catalog.devices.some((option) => option.id === request.device)) {
      throw new Error(`device is not connected: ${request.device}`);
    }
    if (request.packageName) {
      if (!request.device && catalog.devices.length !== 1) throw new Error("device is required to validate packageName when multiple devices are connected");
      if (!catalog.packages.some((option) => option.id === request.packageName)) {
        throw new Error(`packageName is not installed on the selected device: ${request.packageName}`);
      }
    }
    if (request.testcase && !catalog.testcases.some((option) => option.id === request.testcase)) {
      throw new Error(`testcase was not discovered under haprayRoot: ${request.testcase}`);
    }
  }

  async #openCode(projectRoot: string, baseUrl = process.env.OPENCODE_BASE_URL ?? "http://127.0.0.1:4096") {
    const client = createOpencodeClient({ baseUrl, directory: projectRoot });
    const [agentResponse, providerResponse] = await Promise.all([
      client.app.agents({ directory: projectRoot }, { throwOnError: true }),
      client.provider.list({ directory: projectRoot }, { throwOnError: true }),
    ]);
    const connected = new Set(providerResponse.data.connected);
    const providers = providerResponse.data.all
      .filter((provider) => connected.has(provider.id))
      .map((provider) => ({ id: provider.id, label: provider.name }));
    const models = providerResponse.data.all
      .filter((provider) => connected.has(provider.id))
      .flatMap((provider) => Object.values(provider.models).map((model) => ({
        id: model.id,
        label: model.name,
        providerID: provider.id,
        ...(model.status !== "active" ? { detail: model.status } : {}),
      })))
      .sort((left, right) => `${left.providerID}/${left.label}`.localeCompare(`${right.providerID}/${right.label}`));
    const agents = agentResponse.data
      .filter((agent) => !agent.hidden && agent.mode !== "subagent")
      .map((agent) => ({ id: agent.name, label: agent.name, ...(agent.description ? { detail: agent.description } : {}) }));
    return { agents, providers, models };
  }

  async #devices(): Promise<RuntimeOption[]> {
    return parseConnectedTargets(await this.#hdc(["list", "targets", "-v"])).map((id) => ({ id, label: id }));
  }

  async #packages(target: string): Promise<RuntimeOption[]> {
    return parsePackageNames(await this.#hdc(["-t", target, "shell", "bm", "dump", "-a"]))
      .map((id) => ({ id, label: id }));
  }
}

export interface DirectoryListing {
  path: string;
  parent?: string;
  directories: Array<{ name: string; path: string }>;
}

export async function listDirectories(filename = process.cwd()): Promise<DirectoryListing> {
  if (!path.isAbsolute(filename)) throw new Error("directory browser path must be absolute");
  const current = await realpath(filename);
  if (!(await stat(current)).isDirectory()) throw new Error(`directory browser path must be a directory: ${filename}`);
  const entries = await readdir(current, { withFileTypes: true });
  const root = path.parse(current).root;
  return {
    path: current,
    ...(current !== root ? { parent: path.dirname(current) } : {}),
    directories: entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => ({ name: entry.name, path: path.join(current, entry.name) }))
      .sort((left, right) => left.name.localeCompare(right.name)),
  };
}

export function parseConnectedTargets(output: string): string[] {
  return output.split(/\r?\n/).flatMap((line) => {
    const columns = line.trim().split(/\s+/);
    return columns.length > 1 && columns.some((column) => column.toLowerCase() === "connected") && columns[0]
      ? [columns[0]]
      : [];
  });
}

export function parsePackageNames(output: string): string[] {
  return [...new Set(output.split(/\r?\n/).map((line) => line.trim()).filter((line) => /^[a-zA-Z][\w]*(?:\.[\w-]+)+$/.test(line)))].sort();
}

export async function discoverTestcases(root: string): Promise<RuntimeOption[]> {
  const canonical = await existingDirectory(root);
  if (!canonical) throw new Error(`haprayRoot must be an existing directory: ${root}`);
  const results = new Map<string, RuntimeOption>();
  await walk(canonical, 0, results);
  return [...results.values()].sort((left, right) => left.id.localeCompare(right.id));
}

async function walk(directory: string, depth: number, results: Map<string, RuntimeOption>): Promise<void> {
  if (depth > 6 || results.size >= 500) return;
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === ".git" || entry.name === "node_modules") continue;
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await walk(filename, depth + 1, results);
      continue;
    }
    const match = entry.name.match(/^(PerfLoad[^.]*)\.(?:js|ts|ets|json)$/i);
    if (match?.[1]) results.set(match[1], { id: match[1], label: match[1], detail: filename });
  }
}

async function existingDirectory(filename: string | undefined): Promise<string | undefined> {
  if (!filename || !path.isAbsolute(filename)) return undefined;
  try {
    const canonical = await realpath(filename);
    return (await stat(canonical)).isDirectory() ? canonical : undefined;
  } catch {
    return undefined;
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
