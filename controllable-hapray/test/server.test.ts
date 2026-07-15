import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import type { AgentRunner, AgentStageInput } from "../src/agent.js";
import type { StageResult } from "../src/domain.js";
import { WorkflowEventBus } from "../src/event-bus.js";
import type { DevicePreview } from "../src/hdc-preview.js";
import type { RuntimeOptionSource } from "../src/runtime-options.js";
import { PipelineRunner } from "../src/pipeline.js";
import { createHapRayServer } from "../src/server.js";
import { RunStore } from "../src/store.js";

class ApiAgent implements AgentRunner {
  async runStage(input: AgentStageInput): Promise<StageResult> {
    return { status: "completed", summary: input.stage, artifacts: [], findings: [], data: {} };
  }
  async abort(): Promise<void> {}
}

test("HTTP API creates, queries and replays a run over SSE", async (t) => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-api-"));
  const reportsPath = path.join(projectRoot, "reports", "run");
  await mkdir(reportsPath, { recursive: true });
  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const pipeline = new PipelineRunner({ store, agent: new ApiAgent(), skillRoot: "unused" });
  const server = createHapRayServer({ pipeline, store, bus });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => closeServer(server));
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const origin = `http://127.0.0.1:${address.port}`;

  const invalidFullResponse = await fetch(`${origin}/v1/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ request: "collect", projectRoot, kind: "full" }),
  });
  assert.equal(invalidFullResponse.status, 400);
  assert.match((await invalidFullResponse.json() as { error: string }).error, /haprayRoot is required/);

  const createdResponse = await fetch(`${origin}/v1/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      request: "analyze",
      projectRoot,
      kind: "existing-report",
      reportsPath,
      mode: "quick",
      symbolRecovery: "never",
    }),
  });
  assert.equal(createdResponse.status, 202);
  const created = await createdResponse.json() as { location: string; events: string };

  let state: { status: string } | undefined;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const response = await fetch(`${origin}${created.location}`);
    state = await response.json() as { status: string };
    if (state.status === "completed" || state.status === "failed") break;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(state?.status, "completed");

  const streamResponse = await fetch(`${origin}${created.events}`, {
    headers: { accept: "text/event-stream" },
  });
  assert.equal(streamResponse.status, 200);
  const reader = streamResponse.body?.getReader();
  assert.ok(reader);
  let text = "";
  while (!text.includes("event: run.completed")) {
    const chunk = await reader.read();
    if (chunk.done) break;
    text += new TextDecoder().decode(chunk.value);
  }
  await reader.cancel();
  assert.match(text, /event: stage\.started/);
  assert.match(text, /event: run\.completed/);
});

test("HTTP server serves the dashboard SPA without masking API and asset 404s", async (t) => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-web-"));
  const staticDir = path.join(projectRoot, "dashboard");
  await mkdir(path.join(staticDir, "assets"), { recursive: true });
  await writeFile(path.join(staticDir, "index.html"), "<!doctype html><div id=\"root\">HapRay</div>", "utf8");
  await writeFile(path.join(staticDir, "assets", "app.js"), "globalThis.hapray = true;", "utf8");

  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const pipeline = new PipelineRunner({ store, agent: new ApiAgent(), skillRoot: "unused" });
  const devicePreview: DevicePreview = {
    status: () => ({ available: true, connected: true, frameAvailable: true, target: "device-1", updatedAt: "2026-07-15T00:00:00.000Z" }),
    frame: () => Buffer.from("jpeg-frame"),
  };
  const server = createHapRayServer({ pipeline, store, bus }, { staticDir, devicePreview });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => closeServer(server));
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const origin = `http://127.0.0.1:${address.port}`;

  const device = await fetch(`${origin}/v1/device`);
  assert.equal(device.status, 200);
  assert.deepEqual(await device.json(), {
    available: true,
    connected: true,
    frameAvailable: true,
    target: "device-1",
    updatedAt: "2026-07-15T00:00:00.000Z",
  });

  const frame = await fetch(`${origin}/v1/device/frame`);
  assert.equal(frame.status, 200);
  assert.equal(frame.headers.get("content-type"), "image/jpeg");
  assert.equal(Buffer.from(await frame.arrayBuffer()).toString(), "jpeg-frame");

  const index = await fetch(`${origin}/`);
  assert.equal(index.status, 200);
  assert.match(index.headers.get("content-type") ?? "", /^text\/html/);
  assert.match(await index.text(), /HapRay/);

  const clientRoute = await fetch(`${origin}/runs/example`);
  assert.equal(clientRoute.status, 200);
  assert.match(await clientRoute.text(), /HapRay/);

  const asset = await fetch(`${origin}/assets/app.js`);
  assert.equal(asset.status, 200);
  assert.match(asset.headers.get("content-type") ?? "", /^text\/javascript/);
  assert.equal(asset.headers.get("cache-control"), "public, max-age=31536000, immutable");

  const head = await fetch(`${origin}/`, { method: "HEAD" });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), "");

  const missingAsset = await fetch(`${origin}/assets/missing.js`);
  assert.equal(missingAsset.status, 404);
  assert.deepEqual(await missingAsset.json(), { error: "not found" });

  const missingApi = await fetch(`${origin}/v1/missing`);
  assert.equal(missingApi.status, 404);
  assert.deepEqual(await missingApi.json(), { error: "not found" });

  const apiRoot = await fetch(`${origin}/v1`);
  assert.equal(apiRoot.status, 404);
  assert.deepEqual(await apiRoot.json(), { error: "not found" });
});

test("HTTP server exposes directory and runtime option discovery", async (t) => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-options-api-"));
  await mkdir(path.join(projectRoot, "reports"));
  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const pipeline = new PipelineRunner({ store, agent: new ApiAgent(), skillRoot: "unused" });
  let validated = false;
  const runtimeOptions: RuntimeOptionSource = {
    load: async () => ({
      agents: [{ id: "build", label: "build" }], providers: [], models: [],
      devices: [], packages: [], testcases: [], errors: [],
    }),
    validate: async () => { validated = true; },
  };
  const server = createHapRayServer({ pipeline, store, bus }, { runtimeOptions });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => closeServer(server));
  const address = server.address();
  assert.ok(address && typeof address === "object");
  const origin = `http://127.0.0.1:${address.port}`;

  const options = await fetch(`${origin}/v1/options?projectRoot=${encodeURIComponent(projectRoot)}`);
  assert.equal(options.status, 200);
  assert.deepEqual((await options.json() as { agents: Array<{ id: string }> }).agents.map((agent) => agent.id), ["build"]);

  const directories = await fetch(`${origin}/v1/fs/directories?path=${encodeURIComponent(projectRoot)}`);
  assert.equal(directories.status, 200);
  assert.deepEqual((await directories.json() as { directories: Array<{ name: string }> }).directories.map((entry) => entry.name), ["reports"]);

  const reportsPath = path.join(projectRoot, "reports");
  const created = await fetch(`${origin}/v1/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ request: "analyze", projectRoot, kind: "existing-report", reportsPath }),
  });
  assert.equal(created.status, 202);
  assert.equal(validated, true);
});

async function closeServer(server: ReturnType<typeof createHapRayServer>): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
}
