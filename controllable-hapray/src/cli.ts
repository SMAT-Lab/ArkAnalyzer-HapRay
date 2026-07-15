import path from "node:path";
import { access } from "node:fs/promises";
import { OpenCodeAgentRunner } from "./agent.js";
import { CLI_HELP, parseCliArgs } from "./cli-args.js";
import { WorkflowEventBus } from "./event-bus.js";
import { ensureOpenCodeServer } from "./open-code-server.js";
import { PipelineRunner } from "./pipeline.js";
import { RunStore } from "./store.js";
import type { RunState, WorkflowEvent } from "./domain.js";
import { RuntimeOptionsService } from "./runtime-options.js";
import { validatePathGate } from "./validation.js";

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  process.stdout.write(CLI_HELP);
  process.exit(0);
}

let options: ReturnType<typeof parseCliArgs>;
try {
  options = parseCliArgs(process.argv.slice(2));
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n\n${CLI_HELP}`);
  process.exit(2);
}

const configuredSkillRoot = process.env.HAPRAY_SKILL_ROOT;
if (!configuredSkillRoot) {
  throw new Error("HAPRAY_SKILL_ROOT must point to an external HapRay skill directory containing SKILL.md");
}
const skillRoot = path.resolve(configuredSkillRoot);
await access(path.join(skillRoot, "SKILL.md"));
try {
  await validatePathGate(options.request);
} catch (error) {
  process.stderr.write(`Invalid run configuration: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(2);
}
const closeOpenCode = await ensureOpenCodeServer();
try {
  await new RuntimeOptionsService().validate(options.request);
} catch (error) {
  closeOpenCode();
  process.stderr.write(`Invalid run configuration: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(2);
}
const bus = new WorkflowEventBus();
const store = new RunStore(bus);
const agent = new OpenCodeAgentRunner();
const pipeline = new PipelineRunner({ store, agent, skillRoot });
let activeState: RunState | undefined;
let interrupted = false;
let resolveTerminal: (() => void) | undefined;
const terminalRuns = new Set<string>();
const unsubscribe = bus.subscribe("*", (event) => {
  if (options.json) process.stdout.write(`${JSON.stringify(event)}\n`);
  else if (event.type !== "agent.event") {
    const stage = event.stage ? ` [${event.stage}]` : "";
    process.stderr.write(`${event.timestamp} ${event.type}${stage}\n`);
  }
  if (isTerminal(event)) {
    terminalRuns.add(event.runId);
    if (event.runId === activeState?.id) resolveTerminal?.();
  }
});
const cancelActive = (): void => {
  interrupted = true;
  if (activeState) void pipeline.cancel(activeState);
};
process.on("SIGINT", cancelActive);
process.on("SIGTERM", cancelActive);

try {
  activeState = await pipeline.create(options.request);
  if (interrupted) await pipeline.cancel(activeState);
  if (!terminalRuns.has(activeState.id)) {
    await new Promise<void>((resolve) => { resolveTerminal = resolve; });
  }
  const state = await store.load(activeState.request.projectRoot, activeState.id);
  if (!options.json) {
    process.stdout.write(`${JSON.stringify({
      runId: state.id,
      status: state.status,
      artifacts: state.artifacts,
      findings: state.findings,
      statePath: path.join(state.request.projectRoot, ".hapray-service", "runs", state.id, "state.json"),
    }, null, 2)}\n`);
  }
  process.exitCode = state.status === "completed" ? 0 : 1;
} finally {
  process.off("SIGINT", cancelActive);
  process.off("SIGTERM", cancelActive);
  unsubscribe();
  await agent.close();
  closeOpenCode();
}

function isTerminal(event: WorkflowEvent): boolean {
  return event.type === "run.completed" || event.type === "run.failed" || event.type === "run.cancelled";
}
