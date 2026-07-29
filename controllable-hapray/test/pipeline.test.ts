import assert from "node:assert/strict";
import { mkdtemp, mkdir, realpath } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import type { AgentRunner, AgentStageInput } from "../src/agent.js";
import { parseCliArgs } from "../src/cli-args.js";
import { initialRunState, type RunRequest, type StageResult } from "../src/domain.js";
import { WorkflowEventBus } from "../src/event-bus.js";
import { errorMessage, PipelineRunner } from "../src/pipeline.js";
import { RunStore } from "../src/store.js";

class FakeAgent implements AgentRunner {
  calls: string[] = [];
  outsideArtifact = false;
  outputArtifact = false;
  repoArtifact = false;
  haprayArtifact = false;
  skillInputArtifact = false;
  emitUsage = false;

  async runStage(input: AgentStageInput): Promise<StageResult> {
    this.calls.push(input.stage);
    await input.onSession(`session-${input.stage}`);
    await input.onEvent({ type: "message.part.updated", properties: { sessionID: `session-${input.stage}` } });
    if (this.emitUsage) {
      await input.onEvent(usageEvent("message-1", 100, 20, 5, 0.01));
      await input.onEvent(usageEvent("message-1", 100, 40, 5, 0.02));
      await input.onEvent(usageEvent("message-2", 30, 10, 0, 0.005));
    }
    const artifactPath = this.skillInputArtifact
      ? input.authorizedRoots[0] + "/SKILL.md"
      : this.haprayArtifact && input.stage === "setup" && input.request.haprayRoot
      ? path.join(input.request.haprayRoot, "runtime", "hapray")
      : this.repoArtifact && input.stage === "setup" && input.request.repoRoot
      ? path.join(input.request.repoRoot, "dist", "setup-artifact")
      : this.outputArtifact && input.request.outputDir
      ? path.join(input.request.outputDir, `${input.stage}.md`)
      : this.outsideArtifact
      ? path.join(input.request.projectRoot, "..", "escaped.md")
      : path.join(input.request.projectRoot, "reports", `${input.stage}.md`);
    return {
      status: "completed",
      summary: `finished ${input.stage}`,
      artifacts: [{ kind: input.stage, path: artifactPath, description: input.stage }],
      findings: input.stage === "analysis" ? [{
        id: "cpu-hotspot-1",
        kind: "performance-bug",
        title: "CPU hotspot",
        severity: "P1",
        evidence: ["period=42"],
      }] : [],
      data: {},
    };
  }

  async abort(): Promise<void> {}
}

function usageEvent(id: string, input: number, output: number, reasoning: number, cost: number): Record<string, unknown> {
  return {
    type: "message.updated",
    properties: {
      info: {
        id,
        role: "assistant",
        cost,
        tokens: { input, output, reasoning, cache: { read: 7, write: 3 } },
      },
    },
  };
}

async function fixture(overrides: Partial<RunRequest> = {}) {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-pipeline-"));
  const reportsPath = path.join(projectRoot, "reports", "existing");
  await mkdir(reportsPath, { recursive: true });
  const request: RunRequest = {
    request: "analyze the existing report",
    projectRoot,
    kind: "existing-report",
    reportsPath,
    mode: "full",
    symbolRecovery: "never",
    ...overrides,
  };
  const state = initialRunState("test-run", request);
  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const agent = new FakeAgent();
  const pipeline = new PipelineRunner({ store, agent, skillRoot: path.join(projectRoot, "unused") });
  await store.create(state);
  await store.emit(state, "run.created", { request });
  return { projectRoot, state, store, agent, pipeline };
}

test("pipeline exposes fixed stage boundaries, explicit skips, artifacts and findings", async () => {
  const { state, store, agent, pipeline, projectRoot } = await fixture();
  await pipeline.runNow(state);

  assert.equal(state.status, "completed");
  assert.deepEqual(agent.calls, ["analysis", "root-cause", "deliver"]);
  assert.deepEqual(
    state.stages.map((stage) => [stage.id, stage.status]),
    [
      ["path-gate", "completed"],
      ["setup", "skipped"],
      ["collect", "skipped"],
      ["symbol-recovery", "skipped"],
      ["analysis", "completed"],
      ["root-cause", "completed"],
      ["deliver", "completed"],
    ],
  );
  assert.equal(state.findings[0]?.title, "CPU hotspot");
  assert.equal(state.artifacts.length, 3);

  const events = await store.events(projectRoot, state.id);
  assert.equal(events[0]?.type, "run.created");
  assert.equal(events.at(-1)?.type, "run.completed");
  assert.ok(events.some((event) => event.type === "finding.discovered" && event.stage === "analysis"));
  assert.ok(events.some((event) => event.type === "artifact.updated" && event.stage === "deliver"));
  assert.equal((await store.events(projectRoot, state.id, events.at(-2)?.id ?? 0)).length, 1);

  const persisted = await store.load(projectRoot, state.id);
  assert.equal(persisted.status, "completed");
  assert.equal(persisted.stages.find((stage) => stage.id === "analysis")?.opencodeSessionId, "session-analysis");
});

test("quick mode deterministically skips root-cause", async () => {
  const { state, agent, pipeline } = await fixture({ mode: "quick" });
  await pipeline.runNow(state);
  assert.equal(state.status, "completed");
  assert.deepEqual(agent.calls, ["analysis", "deliver"]);
  assert.equal(state.stages.find((stage) => stage.id === "root-cause")?.status, "skipped");
});

test("a full CLI request executes setup and collection before analysis", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-full-cli-"));
  const haprayRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-tool-"));
  const options = parseCliArgs([
    "--kind", "full",
    "--project-root", projectRoot,
    "--hapray-root", haprayRoot,
    "--request", "collect and analyze the connected application",
    "--package-name", "com.example.app",
    "--testcase", "PerfLoad_home",
    "--runtime-track", "binary",
    "--mode", "quick",
    "--symbol-recovery", "never",
  ]);
  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const agent = new FakeAgent();
  const pipeline = new PipelineRunner({ store, agent, skillRoot: path.join(projectRoot, "external-skill") });

  const state = await pipeline.createAndWait(options.request);

  assert.equal(state.status, "completed");
  assert.deepEqual(agent.calls, ["setup", "collect", "analysis", "deliver"]);
  assert.equal(state.stages.find((stage) => stage.id === "setup")?.status, "completed");
  assert.equal(state.stages.find((stage) => stage.id === "collect")?.status, "completed");
  assert.equal(state.request.haprayRoot, await realpath(haprayRoot));
});

test("auto symbol recovery follows the Skill's symbol-level scope gate", async () => {
  const broad = await fixture({ symbolRecovery: "auto" });
  await broad.pipeline.runNow(broad.state);
  assert.equal(broad.state.stages.find((stage) => stage.id === "symbol-recovery")?.status, "skipped");
  assert.match(broad.state.stages.find((stage) => stage.id === "symbol-recovery")?.result?.summary ?? "", /does not require symbol-level/);

  const symbolLevel = await fixture({ request: "recover stripped symbols for symbol-level attribution", symbolRecovery: "auto" });
  await symbolLevel.pipeline.runNow(symbolLevel.state);
  assert.ok(symbolLevel.agent.calls.includes("symbol-recovery"));
});

test("pipeline rejects agent artifacts outside projectRoot", async () => {
  const { state, agent, pipeline } = await fixture({ mode: "quick" });
  agent.outsideArtifact = true;
  await pipeline.runNow(state);
  assert.equal(state.status, "failed");
  assert.match(state.error ?? "", /outside projectRoot/);
  assert.equal(state.stages.find((stage) => stage.id === "analysis")?.status, "failed");
});

test("pipeline accepts artifacts in an explicitly authorized output directory", async () => {
  const outputDir = await mkdtemp(path.join(os.tmpdir(), "hapray-output-"));
  const { state, agent, pipeline } = await fixture({ mode: "quick", outputDir });
  agent.outputArtifact = true;
  await pipeline.runNow(state);
  assert.equal(state.status, "completed");
  const canonicalOutput = await realpath(outputDir);
  assert.ok(state.artifacts.every((artifact) => artifact.path.startsWith(canonicalOutput)));
});

test("source-track setup accepts build artifacts under the explicit repoRoot", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-source-project-"));
  const repoRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-source-repo-"));
  const request: RunRequest = {
    request: "collect and analyze",
    projectRoot,
    haprayRoot: repoRoot,
    repoRoot,
    kind: "full",
    runtimeTrack: "source",
    mode: "quick",
    symbolRecovery: "never",
  };
  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const agent = new FakeAgent();
  agent.repoArtifact = true;
  const pipeline = new PipelineRunner({ store, agent, skillRoot: path.join(projectRoot, "external-skill") });

  const state = await pipeline.createAndWait(request);

  assert.equal(state.status, "completed");
  assert.ok(state.artifacts.some((artifact) => artifact.path === path.join(request.repoRoot!, "dist", "setup-artifact")));
});

test("full setup authorizes the explicit HapRay tool root", async () => {
  const projectRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-tool-project-"));
  const haprayRoot = await mkdtemp(path.join(os.tmpdir(), "hapray-tool-root-"));
  const request: RunRequest = {
    request: "collect and analyze",
    projectRoot,
    haprayRoot,
    kind: "full",
    runtimeTrack: "binary",
    mode: "quick",
    symbolRecovery: "never",
  };
  const bus = new WorkflowEventBus();
  const store = new RunStore(bus);
  const agent = new FakeAgent();
  agent.haprayArtifact = true;
  const pipeline = new PipelineRunner({ store, agent, skillRoot: path.join(projectRoot, "external-skill") });

  const state = await pipeline.createAndWait(request);

  assert.equal(state.status, "completed");
  assert.ok(state.artifacts.some((artifact) => artifact.path === path.join(request.haprayRoot!, "runtime", "hapray")));
});

test("reported read-only Skill inputs are discarded instead of failing the run", async () => {
  const { state, agent, pipeline } = await fixture({ mode: "quick" });
  agent.skillInputArtifact = true;

  await pipeline.runNow(state);

  assert.equal(state.status, "completed");
  assert.ok(state.artifacts.every((artifact) => !artifact.path.endsWith("/SKILL.md")));
});

test("pipeline persists live agent token usage without double-counting message updates", async () => {
  const { state, agent, pipeline, store, projectRoot } = await fixture({ mode: "quick" });
  agent.emitUsage = true;

  await pipeline.runNow(state);

  const usage = state.stages.find((stage) => stage.id === "analysis")?.usage;
  assert.deepEqual(usage, {
    inputTokens: 130,
    outputTokens: 50,
    reasoningTokens: 5,
    cacheReadTokens: 14,
    cacheWriteTokens: 6,
    totalTokens: 185,
    cost: 0.025,
  });
  assert.deepEqual((await store.load(projectRoot, state.id)).stages.find((stage) => stage.id === "analysis")?.usage, usage);
});

test("event ids continue across store instances without rescanning on each append", async () => {
  const { state, store, projectRoot } = await fixture();
  await store.emit(state, "run.started", {});
  await store.emit(state, "stage.started", {}, "path-gate");
  const restartedStore = new RunStore(new WorkflowEventBus());
  await restartedStore.emit(state, "stage.completed", {}, "path-gate");
  assert.deepEqual((await restartedStore.events(projectRoot, state.id)).map((event) => event.id), [1, 2, 3, 4]);
});

test("nested transport errors retain their actionable cause", () => {
  const cause = Object.assign(new Error("Headers Timeout Error"), { code: "UND_ERR_HEADERS_TIMEOUT" });
  assert.equal(
    errorMessage(new TypeError("fetch failed", { cause })),
    "fetch failed (caused by: UND_ERR_HEADERS_TIMEOUT: Headers Timeout Error)",
  );
});
