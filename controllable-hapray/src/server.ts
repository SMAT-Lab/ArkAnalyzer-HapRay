import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { URL } from "node:url";
import type { PipelineRunner } from "./pipeline.js";
import type { RunStore } from "./store.js";
import type { WorkflowEventBus } from "./event-bus.js";
import type { DevicePreview } from "./hdc-preview.js";
import { listDirectories, type RuntimeOptionSource } from "./runtime-options.js";
import { parseRunRequest, validatePathGate } from "./validation.js";

export interface ServiceDependencies {
  pipeline: PipelineRunner;
  store: RunStore;
  bus: WorkflowEventBus;
}

export interface HapRayServerOptions {
  staticDir?: string;
  devicePreview?: DevicePreview;
  runtimeOptions?: RuntimeOptionSource;
}

export function createHapRayServer(dependencies: ServiceDependencies, options: HapRayServerOptions = {}) {
  return createServer(async (request, response) => {
    try {
      await route(request, response, dependencies, options);
    } catch (error) {
      if (response.headersSent) {
        response.end();
        return;
      }
      const status = (error as NodeJS.ErrnoException).code === "ENOENT" ? 404 : 400;
      json(response, status, { error: error instanceof Error ? error.message : String(error) });
    }
  });
}

async function route(
  request: IncomingMessage,
  response: ServerResponse,
  dependencies: ServiceDependencies,
  options: HapRayServerOptions,
): Promise<void> {
  const url = new URL(request.url ?? "/", "http://localhost");
  if (request.method === "GET" && url.pathname === "/health") {
    json(response, 200, { status: "ok" });
    return;
  }
  if (request.method === "GET" && url.pathname === "/v1/device") {
    if (!options.devicePreview) {
      json(response, 503, { error: "device preview is unavailable" });
      return;
    }
    json(response, 200, options.devicePreview.status());
    return;
  }
  if ((request.method === "GET" || request.method === "HEAD") && url.pathname === "/v1/device/frame") {
    const frame = options.devicePreview?.frame();
    if (!frame) {
      json(response, 503, { error: "device preview frame is not available" });
      return;
    }
    const updatedAt = options.devicePreview?.status().updatedAt ?? "pending";
    response.writeHead(200, {
      "Content-Type": "image/jpeg",
      "Content-Length": frame.byteLength,
      "Cache-Control": "no-store",
      ETag: `\"${updatedAt}\"`,
    });
    response.end(request.method === "HEAD" ? undefined : frame);
    return;
  }
  if (request.method === "GET" && url.pathname === "/v1/options") {
    if (!options.runtimeOptions) {
      json(response, 503, { error: "runtime option discovery is unavailable" });
      return;
    }
    const projectRoot = url.searchParams.get("projectRoot");
    const haprayRoot = url.searchParams.get("haprayRoot");
    const device = url.searchParams.get("device");
    json(response, 200, await options.runtimeOptions.load({
      ...(projectRoot ? { projectRoot } : {}),
      ...(haprayRoot ? { haprayRoot } : {}),
      ...(device ? { device } : {}),
    }));
    return;
  }
  if (request.method === "GET" && url.pathname === "/v1/fs/directories") {
    json(response, 200, await listDirectories(url.searchParams.get("path") ?? undefined));
    return;
  }
  if (request.method === "POST" && url.pathname === "/v1/runs") {
    const runRequest = parseRunRequest(await readJson(request));
    await validatePathGate(runRequest);
    await options.runtimeOptions?.validate(runRequest);
    const state = await dependencies.pipeline.create(runRequest);
    const location = `/v1/runs/${state.id}?projectRoot=${encodeURIComponent(runRequest.projectRoot)}`;
    response.setHeader("Location", location);
    json(response, 202, { run: state, location, events: `${location}&stream=true` });
    return;
  }

  const match = url.pathname.match(/^\/v1\/runs\/([^/]+)$/);
  if (!match?.[1]) {
    const apiPath = url.pathname === "/v1" || url.pathname.startsWith("/v1/");
    if ((request.method === "GET" || request.method === "HEAD") && options.staticDir && !apiPath) {
      await serveDashboard(response, request.method, options.staticDir, url.pathname);
      return;
    }
    json(response, 404, { error: "not found" });
    return;
  }
  const runId = decodeURIComponent(match[1]);
  const projectRoot = url.searchParams.get("projectRoot");
  if (!projectRoot) throw new Error("projectRoot query parameter is required");

  if (request.method === "GET" && (url.searchParams.get("stream") === "true" || acceptsSse(request))) {
    await streamEvents(request, response, dependencies, projectRoot, runId, url);
    return;
  }
  if (request.method === "GET") {
    json(response, 200, await dependencies.store.load(projectRoot, runId));
    return;
  }
  if (request.method === "DELETE") {
    const state = await dependencies.store.load(projectRoot, runId);
    if (state.status === "running" || state.status === "queued") await dependencies.pipeline.cancel(state);
    json(response, 202, { id: runId, status: "cancelling" });
    return;
  }
  json(response, 405, { error: "method not allowed" });
}

async function serveDashboard(
  response: ServerResponse,
  method: string,
  staticDir: string,
  pathname: string,
): Promise<void> {
  const root = path.resolve(staticDir);
  const decoded = decodeURIComponent(pathname);
  const requested = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const candidate = path.resolve(root, requested);
  if (!isInside(root, candidate)) {
    json(response, 404, { error: "not found" });
    return;
  }

  let filename = candidate;
  try {
    if (!(await stat(filename)).isFile()) throw Object.assign(new Error("not a file"), { code: "ENOENT" });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    // Client-side routes are served by the SPA shell. Missing asset requests keep
    // their 404 so a typo cannot silently return HTML to a script or stylesheet.
    if (path.extname(requested)) {
      json(response, 404, { error: "not found" });
      return;
    }
    filename = path.join(root, "index.html");
  }

  const body = await readFile(filename);
  const contentType = CONTENT_TYPES[path.extname(filename).toLowerCase()] ?? "application/octet-stream";
  const immutable = path.relative(root, filename).split(path.sep)[0] === "assets";
  response.writeHead(200, {
    "Content-Type": contentType,
    "Content-Length": body.byteLength,
    "Cache-Control": immutable ? "public, max-age=31536000, immutable" : "no-cache",
  });
  response.end(method === "HEAD" ? undefined : body);
}

function isInside(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

const CONTENT_TYPES: Record<string, string> = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

async function streamEvents(
  request: IncomingMessage,
  response: ServerResponse,
  dependencies: ServiceDependencies,
  projectRoot: string,
  runId: string,
  url: URL,
): Promise<void> {
  await dependencies.store.load(projectRoot, runId);
  response.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  response.write("retry: 2000\n\n");
  let lastSent = Number(request.headers["last-event-id"] ?? url.searchParams.get("after") ?? 0);
  if (!Number.isSafeInteger(lastSent) || lastSent < 0) lastSent = 0;
  const send = (event: Awaited<ReturnType<RunStore["events"]>>[number]) => {
    if (event.id <= lastSent) return;
    lastSent = event.id;
    response.write(`id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
  };
  const unsubscribe = dependencies.bus.subscribe(runId, send);
  for (const event of await dependencies.store.events(projectRoot, runId, lastSent)) send(event);
  const heartbeat = setInterval(() => response.write(": heartbeat\n\n"), 15_000);
  const close = () => {
    clearInterval(heartbeat);
    unsubscribe();
    response.end();
  };
  request.once("close", close);
}

function acceptsSse(request: IncomingMessage): boolean {
  return request.headers.accept?.includes("text/event-stream") ?? false;
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > 1_048_576) throw new Error("request body exceeds 1 MiB");
    chunks.push(buffer);
  }
  if (!chunks.length) throw new Error("request body is required");
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new Error("request body must be valid JSON");
  }
}

function json(response: ServerResponse, status: number, body: unknown): void {
  const payload = `${JSON.stringify(body)}\n`;
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Content-Length": Buffer.byteLength(payload) });
  response.end(payload);
}
