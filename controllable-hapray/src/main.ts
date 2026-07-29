import path from "node:path";
import { access, stat } from "node:fs/promises";
import { OpenCodeAgentRunner } from "./agent.js";
import { WorkflowEventBus } from "./event-bus.js";
import { PipelineRunner } from "./pipeline.js";
import { createHapRayServer } from "./server.js";
import { RunStore } from "./store.js";
import { ensureOpenCodeServer } from "./open-code-server.js";
import { HdcDevicePreview } from "./hdc-preview.js";
import { RuntimeOptionsService } from "./runtime-options.js";

const host = process.env.HOST ?? "127.0.0.1";
const port = integerEnvironment("PORT", 8787);
const skillRoot = requiredSkillRoot();
await access(path.join(skillRoot, "SKILL.md"));

const closeOpenCode = await ensureOpenCodeServer();
const devicePreview = new HdcDevicePreview({ intervalMs: positiveIntegerEnvironment("HDC_PREVIEW_INTERVAL_MS", 1_000) });
await devicePreview.start();
const runtimeOptions = new RuntimeOptionsService();

const bus = new WorkflowEventBus();
const store = new RunStore(bus);
const agent = new OpenCodeAgentRunner();
const pipeline = new PipelineRunner({ store, agent, skillRoot });
const dashboardDist = await optionalDirectory(
  path.resolve(process.env.DASHBOARD_DIST ?? path.join(process.cwd(), "dashboard", "dist")),
);
const server = createHapRayServer(
  { pipeline, store, bus },
  { ...(dashboardDist ? { staticDir: dashboardDist } : {}), devicePreview, runtimeOptions },
);

server.listen(port, host, () => {
  const address = server.address();
  const actualPort = address && typeof address === "object" ? address.port : port;
  process.stdout.write(`HapRay workflow service listening on http://${host}:${actualPort}\n`);
  process.stdout.write(`OpenCode endpoint: ${process.env.OPENCODE_BASE_URL}\n`);
  process.stdout.write(dashboardDist
    ? `Dashboard: http://${host}:${actualPort}/\n`
    : "Dashboard build not found; serving API only (run npm run build).\n");
});

const shutdown = (): void => {
  server.close(async () => {
    await devicePreview.close();
    await agent.close();
    closeOpenCode();
    process.exit(0);
  });
};
process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);

function integerEnvironment(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 0 || value > 65_535) throw new Error(`${name} must be a valid port`);
  return value;
}

function positiveIntegerEnvironment(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 100) throw new Error(`${name} must be an integer of at least 100 milliseconds`);
  return value;
}

async function optionalDirectory(filename: string): Promise<string | undefined> {
  try {
    return (await stat(filename)).isDirectory() ? filename : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

function requiredSkillRoot(): string {
  const configured = process.env.HAPRAY_SKILL_ROOT;
  if (!configured) throw new Error("HAPRAY_SKILL_ROOT must point to an external HapRay skill directory containing SKILL.md");
  return path.resolve(configured);
}
