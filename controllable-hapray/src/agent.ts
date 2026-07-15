import { createOpencodeClient, type Event, type OpencodeClient } from "@opencode-ai/sdk/v2";
import path from "node:path";
import { Agent as UndiciAgent, fetch as undiciFetch, type Dispatcher } from "undici";
import type { RunRequest, StageId, StageResult } from "./domain.js";
import { isWithin } from "./validation.js";

export interface AgentStageInput {
  runId: string;
  stage: StageId;
  title: string;
  prompt: string;
  request: RunRequest;
  authorizedRoots: string[];
  onSession(sessionId: string): Promise<void>;
  onEvent(event: Record<string, unknown>): Promise<void>;
}

export interface AgentRunner {
  runStage(input: AgentStageInput): Promise<StageResult>;
  abort(sessionId: string, request: RunRequest): Promise<void>;
  close?(): Promise<void>;
}

const resultSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    status: { type: "string", enum: ["completed", "skipped"] },
    summary: { type: "string" },
    decision: { type: "string" },
    artifacts: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          kind: { type: "string" },
          path: { type: "string" },
          description: { type: "string" },
        },
        required: ["kind", "path", "description"],
      },
    },
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          id: { type: "string" },
          kind: { type: "string", enum: ["performance-bug", "root-cause", "observation"] },
          title: { type: "string" },
          severity: { type: "string", enum: ["P0", "P1", "P2", "P3", "info"] },
          evidence: { type: "array", items: { type: "string" } },
          recommendation: { type: "string" },
          source: {
            type: "object",
            additionalProperties: false,
            properties: { path: { type: "string" }, line: { type: "integer" } },
            required: ["path"],
          },
        },
        required: ["id", "kind", "title", "severity", "evidence"],
      },
    },
    data: { type: "object", additionalProperties: true },
  },
  required: ["status", "summary", "artifacts", "findings", "data"],
} as const;

export class OpenCodeAgentRunner implements AgentRunner {
  readonly #clients = new Map<string, OpencodeClient>();
  readonly #dispatcher: Dispatcher;

  constructor(dispatcher: Dispatcher = new UndiciAgent({
    // OpenCode's synchronous prompt endpoint may legitimately spend many
    // minutes running tools before it sends response headers.
    headersTimeout: 0,
    bodyTimeout: 0,
    connectTimeout: 30_000,
    keepAliveTimeout: 10_000,
    keepAliveMaxTimeout: 60_000,
  })) {
    this.#dispatcher = dispatcher;
  }

  async runStage(input: AgentStageInput): Promise<StageResult> {
    const client = this.#client(input.request);
    const directory = input.request.projectRoot;
    const model = input.request.opencode?.model;
    const created = await client.session.create({
      directory,
      title: `HapRay ${input.runId} / ${input.title}`,
      ...(input.request.opencode?.agent ? { agent: input.request.opencode.agent } : {}),
      ...(model ? { model: { id: model.modelID, providerID: model.providerID, ...(model.variant ? { variant: model.variant } : {}) } } : {}),
      metadata: { haprayRunId: input.runId, haprayStage: input.stage },
      permission: [{ permission: "*", pattern: "*", action: "allow" }],
    }, { throwOnError: true });
    const session = unwrap(created);
    await input.onSession(session.id);

    const streamAbort = new AbortController();
    const eventLoop = this.#forwardEvents(client, directory, session.id, input.authorizedRoots, input.onEvent, streamAbort.signal);
    try {
      const prompted = await client.session.prompt({
        sessionID: session.id,
        directory,
        ...(input.request.opencode?.agent ? { agent: input.request.opencode.agent } : {}),
        ...(model ? { model: { providerID: model.providerID, modelID: model.modelID }, ...(model.variant ? { variant: model.variant } : {}) } : {}),
        format: { type: "json_schema", schema: resultSchema, retryCount: 2 },
        tools: stageTools,
        parts: [{ type: "text", text: input.prompt }],
      }, { throwOnError: true });
      const message = unwrap(prompted);
      if (message.info.error) {
        if (isStructuredToolChoiceUnsupported(message.info.error)) {
          const fallback = await client.session.prompt({
            sessionID: session.id,
            directory,
            ...(input.request.opencode?.agent ? { agent: input.request.opencode.agent } : {}),
            ...(model ? { model: { providerID: model.providerID, modelID: model.modelID }, ...(model.variant ? { variant: model.variant } : {}) } : {}),
            tools: stageTools,
            parts: [{
              type: "text",
              text: [
                "The provider rejected OpenCode's forced structured-output tool choice. Retry the complete stage now using ordinary tools.",
                input.prompt,
                "After all work is finished, emit exactly one JSON object wrapped in <hapray-stage-result> and </hapray-stage-result> tags.",
                `The JSON must match this schema: ${JSON.stringify(resultSchema)}`,
                "Do not put Markdown fences around the tagged JSON.",
              ].join("\n\n"),
            }],
          }, { throwOnError: true });
          const fallbackMessage = unwrap(fallback);
          if (fallbackMessage.info.error) throw stageMessageError(fallbackMessage.info.error);
          try {
            return parseTextStageResult(fallbackMessage.parts);
          } catch (parseError) {
            const correction = await client.session.prompt({
              sessionID: session.id,
              directory,
              ...(input.request.opencode?.agent ? { agent: input.request.opencode.agent } : {}),
              ...(model ? { model: { providerID: model.providerID, modelID: model.modelID }, ...(model.variant ? { variant: model.variant } : {}) } : {}),
              tools: disableAllTools,
              parts: [{
                type: "text",
                text: [
                  "Do not perform more analysis and do not call tools. Convert the stage work you just completed into the required machine result.",
                  "Return exactly one JSON object wrapped in <hapray-stage-result> and </hapray-stage-result> tags, with no prose outside the tags.",
                  `The JSON must match this schema: ${JSON.stringify(resultSchema)}`,
                  `The previous response could not be parsed: ${parseError instanceof Error ? parseError.message : String(parseError)}`,
                ].join("\n\n"),
              }],
            }, { throwOnError: true });
            const correctedMessage = unwrap(correction);
            if (correctedMessage.info.error) throw stageMessageError(correctedMessage.info.error);
            return parseTextStageResult(correctedMessage.parts);
          }
        }
        throw stageMessageError(message.info.error);
      }
      return validateStageResult(message.info.structured);
    } finally {
      streamAbort.abort();
      await eventLoop;
    }
  }

  async abort(sessionId: string, request: RunRequest): Promise<void> {
    const client = this.#client(request);
    await client.session.abort({ sessionID: sessionId, directory: request.projectRoot });
  }

  async close(): Promise<void> {
    await this.#dispatcher.close();
  }

  #client(request: RunRequest): OpencodeClient {
    const baseUrl = request.opencode?.baseUrl ?? process.env.OPENCODE_BASE_URL ?? "http://127.0.0.1:4096";
    const key = `${baseUrl}\0${request.projectRoot}`;
    let client = this.#clients.get(key);
    if (!client) {
      client = createOpencodeClient({
        baseUrl,
        directory: request.projectRoot,
        fetch: createOpenCodeFetch(this.#dispatcher),
      });
      this.#clients.set(key, client);
    }
    return client;
  }

  async #forwardEvents(
    client: OpencodeClient,
    directory: string,
    sessionId: string,
    authorizedRoots: string[],
    publish: (event: Record<string, unknown>) => Promise<void>,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      const subscription = await client.event.subscribe({ directory }, { signal });
      for await (const event of subscription.stream) {
        if (signal.aborted) break;
        if (belongsToSession(event, sessionId)) {
          const permission = permissionRequest(event, authorizedRoots);
          if (permission) {
            await client.permission.reply({
              requestID: permission.requestID,
              directory,
              reply: permission.authorized ? "once" : "reject",
              ...(!permission.authorized ? { message: "Path is outside the validated HapRay workflow roots." } : {}),
            }, { throwOnError: true });
          }
          // Token deltas arrive character-by-character and can produce tens of
          // thousands of durable events. Updated parts retain useful progress
          // snapshots without turning persistence into the bottleneck.
          if (shouldPersistAgentEvent(event)) await publish(summarizeAgentEvent(event));
        }
      }
    } catch (error) {
      if (!signal.aborted) throw error;
    }
  }
}

export function createOpenCodeFetch(dispatcher: Dispatcher): typeof globalThis.fetch {
  return async (input, init) => {
    const request = new Request(input, init);
    const body = request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();
    const response = await undiciFetch(request.url, {
      method: request.method,
      headers: request.headers,
      ...(body ? { body } : {}),
      redirect: request.redirect,
      signal: request.signal,
      dispatcher,
    });
    return response as unknown as Response;
  };
}

export function shouldPersistAgentEvent(event: Event | Record<string, unknown>): boolean {
  return (event as Record<string, unknown>).type !== "message.part.delta";
}

export function permissionRequest(
  event: Event | Record<string, unknown>,
  authorizedRoots: string[],
): { requestID: string; authorized: boolean } | undefined {
  const raw = event as Record<string, unknown>;
  if (raw.type !== "permission.asked") return undefined;
  const properties = raw.properties;
  if (!properties || typeof properties !== "object") return undefined;
  const value = properties as Record<string, unknown>;
  if (value.permission !== "external_directory" || typeof value.id !== "string") return undefined;
  const metadata = value.metadata;
  const filepath = metadata && typeof metadata === "object"
    ? (metadata as Record<string, unknown>).filepath
    : undefined;
  const candidates = typeof filepath === "string"
    ? [filepath]
    : Array.isArray(value.patterns)
      ? value.patterns.filter((candidate): candidate is string => typeof candidate === "string")
        .map((candidate) => candidate.replace(/[/\\][*]+$/, ""))
      : [];
  const roots = authorizedRoots.map((root) => path.resolve(root));
  const authorized = candidates.length > 0 && candidates.every((candidate) => {
    const resolved = path.resolve(candidate);
    return roots.some((root) => isWithin(root, resolved));
  });
  return { requestID: value.id, authorized };
}

const disableAllTools = {
  bash: false,
  edit: false,
  write: false,
  read: false,
  glob: false,
  grep: false,
  todowrite: false,
  task: false,
} as const;

// Each pipeline stage is already an explicit unit of control and persistence.
// Nested OpenCode tasks create unobserved child sessions and can exhaust the
// embedded server while scanning large profiler/source trees.
const stageTools = { task: false } as const;

function isStructuredToolChoiceUnsupported(error: { name: string; data?: unknown }): boolean {
  if (error.name !== "APIError") return false;
  const data = error.data;
  if (!data || typeof data !== "object") return false;
  const message = (data as Record<string, unknown>).message;
  return typeof message === "string" && /tool_choice/i.test(message);
}

function stageMessageError(error: { name: string; data?: unknown }): Error {
  const data = error.data;
  const detail = data && typeof data === "object" && typeof (data as Record<string, unknown>).message === "string"
    ? `: ${(data as Record<string, unknown>).message}`
    : "";
  return new Error(`OpenCode stage failed: ${error.name}${detail}`);
}

function unwrap<T>(response: { data?: T; error?: unknown } | T): T {
  if (response && typeof response === "object" && "data" in response) {
    if (response.data === undefined) throw new Error(`OpenCode SDK returned no data: ${JSON.stringify(response.error)}`);
    return response.data;
  }
  return response as T;
}

function belongsToSession(event: Event, sessionId: string): boolean {
  const serialized = event as unknown as Record<string, unknown>;
  const properties = serialized.properties;
  if (!properties || typeof properties !== "object") return false;
  const candidate = properties as Record<string, unknown>;
  if (candidate.sessionID === sessionId) return true;
  for (const key of ["part", "info"] as const) {
    const nested = candidate[key];
    if (nested && typeof nested === "object" && (nested as Record<string, unknown>).sessionID === sessionId) return true;
  }
  return false;
}

export function summarizeAgentEvent(event: Event): Record<string, unknown> {
  const raw = event as unknown as Record<string, unknown>;
  const type = raw.type;
  const properties = raw.properties;
  if (!properties || typeof properties !== "object") return { type, properties: {} };
  const value = properties as Record<string, unknown>;
  if (type === "message.updated") {
    const info = value.info && typeof value.info === "object"
      ? compactMessageInfo(value.info as Record<string, unknown>)
      : value.info;
    return { type, properties: { sessionID: value.sessionID, info } };
  }
  if (type === "message.part.updated") {
    const part = value.part && typeof value.part === "object"
      ? compactPart(value.part as Record<string, unknown>)
      : value.part;
    return { type, properties: { part, delta: truncate(value.delta, 4_096) } };
  }
  if (type === "message.part.delta") {
    return {
      type,
      properties: {
        sessionID: value.sessionID,
        messageID: value.messageID,
        partID: value.partID,
        field: value.field,
        delta: truncate(value.delta, 4_096),
      },
    };
  }
  return { type, properties: compactValue(value, 16_384) };
}

function compactMessageInfo(info: Record<string, unknown>): Record<string, unknown> {
  const summary = info.summary;
  if (!summary || typeof summary !== "object") return compactValue(info, 16_384) as Record<string, unknown>;
  const summaryObject = summary as Record<string, unknown>;
  const diffs = Array.isArray(summaryObject.diffs)
    ? summaryObject.diffs.map((diff) => {
      if (!diff || typeof diff !== "object") return diff;
      const raw = diff as Record<string, unknown>;
      return {
        file: raw.file,
        additions: raw.additions,
        deletions: raw.deletions,
        status: raw.status,
        patchBytes: typeof raw.patch === "string" ? Buffer.byteLength(raw.patch) : 0,
      };
    })
    : undefined;
  return compactValue({ ...info, summary: { ...summaryObject, ...(diffs ? { diffs } : {}) } }, 32_768) as Record<string, unknown>;
}

function compactPart(part: Record<string, unknown>): Record<string, unknown> {
  const state = part.state;
  if (!state || typeof state !== "object") return compactValue(part, 16_384) as Record<string, unknown>;
  const rawState = state as Record<string, unknown>;
  return compactValue({
    ...part,
    state: {
      ...rawState,
      input: compactValue(rawState.input, 8_192),
      output: truncate(rawState.output, 16_384),
      metadata: compactValue(rawState.metadata, 8_192),
    },
  }, 40_960) as Record<string, unknown>;
}

function compactValue(value: unknown, maxBytes: number): unknown {
  if (value === undefined || value === null || typeof value === "number" || typeof value === "boolean") return value;
  if (typeof value === "string") return truncate(value, maxBytes);
  try {
    const serialized = JSON.stringify(value);
    if (Buffer.byteLength(serialized) <= maxBytes) return value;
    return { truncated: true, originalBytes: Buffer.byteLength(serialized), preview: serialized.slice(0, maxBytes) };
  } catch {
    return { truncated: true, preview: String(value).slice(0, maxBytes) };
  }
}

function truncate(value: unknown, maxBytes: number): unknown {
  if (typeof value !== "string") return compactValue(value, maxBytes);
  if (Buffer.byteLength(value) <= maxBytes) return value;
  return `${value.slice(0, maxBytes)}\n… [truncated, ${Buffer.byteLength(value)} bytes total]`;
}

export function validateStageResult(value: unknown): StageResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Agent returned no structured stage result");
  const raw = value as Record<string, unknown>;
  if (raw.status !== "completed" && raw.status !== "skipped") throw new Error("Agent returned invalid stage status");
  if (typeof raw.summary !== "string") throw new Error("Agent returned invalid stage summary");
  if (!Array.isArray(raw.artifacts) || !Array.isArray(raw.findings)) throw new Error("Agent returned invalid result arrays");
  if (!raw.data || typeof raw.data !== "object" || Array.isArray(raw.data)) throw new Error("Agent returned invalid stage data");
  return value as StageResult;
}

export function parseTextStageResult(parts: Array<{ type: string; text?: string }>): StageResult {
  const text = parts
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("\n");
  const tagged = text.match(/<hapray-stage-result>\s*([\s\S]*?)\s*<\/hapray-stage-result>/i)?.[1];
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1];
  const candidate = tagged ?? fenced ?? text.trim();
  try {
    return validateStageResult(JSON.parse(candidate));
  } catch (error) {
    throw new Error(`Agent did not return a valid stage result: ${error instanceof Error ? error.message : String(error)}`);
  }
}
