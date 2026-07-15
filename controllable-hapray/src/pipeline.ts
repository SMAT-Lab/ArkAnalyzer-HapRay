import path from "node:path";
import { randomUUID } from "node:crypto";
import type { AgentRunner } from "./agent.js";
import { initialRunState, type AgentUsage, type Artifact, type RunRequest, type RunState, type StageId, type StageState } from "./domain.js";
import type { RunStore } from "./store.js";
import { defaultStages, type WorkflowStage } from "./stages/index.js";
import { isWithin, validatePathGate } from "./validation.js";

export class PipelineRunner {
  readonly #store: RunStore;
  readonly #agent: AgentRunner;
  readonly #stages: WorkflowStage[];
  readonly #skillRoot: string;
  readonly #abortControllers = new Map<string, AbortController>();

  constructor(options: { store: RunStore; agent: AgentRunner; skillRoot: string; stages?: WorkflowStage[] }) {
    this.#store = options.store;
    this.#agent = options.agent;
    this.#skillRoot = options.skillRoot;
    this.#stages = options.stages ?? defaultStages();
  }

  async create(request: RunRequest): Promise<RunState> {
    const state = await this.#initialize(request);
    const controller = new AbortController();
    this.#abortControllers.set(state.id, controller);
    void this.#execute(state, controller.signal);
    return state;
  }

  async createAndWait(request: RunRequest): Promise<RunState> {
    const state = await this.#initialize(request);
    await this.runNow(state);
    return state;
  }

  async runNow(state: RunState): Promise<RunState> {
    const controller = new AbortController();
    this.#abortControllers.set(state.id, controller);
    await this.#execute(state, controller.signal);
    return state;
  }

  async cancel(state: RunState): Promise<void> {
    this.#abortControllers.get(state.id)?.abort();
    const active = state.stages.find((stage) => stage.status === "running");
    if (active?.opencodeSessionId) await this.#agent.abort(active.opencodeSessionId, state.request);
  }

  async #execute(state: RunState, signal: AbortSignal): Promise<void> {
    try {
      state.status = "running";
      await this.#store.save(state);
      await this.#store.emit(state, "run.started", {});
      for (const stage of this.#stages) {
        if (signal.aborted) throw new CancelledError();
        const stageState = state.stages.find((candidate) => candidate.id === stage.id);
        if (!stageState) throw new Error(`Missing state for stage ${stage.id}`);
        stageState.status = "running";
        stageState.startedAt = new Date().toISOString();
        await this.#store.save(state);
        await this.#store.emit(state, "stage.started", { title: stage.title }, stage.id);
        try {
          const usageByMessage = new Map<string, AgentUsage>();
          const result = await stage.execute({
            state,
            agent: this.#agent,
            skillRoot: this.#skillRoot,
            onSession: async (sessionId) => {
              stageState.opencodeSessionId = sessionId;
              await this.#store.save(state);
            },
            onAgentEvent: async (event) => {
              if (updateAgentUsage(stageState, event, usageByMessage)) await this.#store.save(state);
              await this.#store.emit(state, "agent.event", event, stage.id);
            },
          });
          result.artifacts = this.#validatedArtifacts(state, result.artifacts, stage.id);
          stageState.result = result;
          stageState.status = result.status;
          stageState.finishedAt = new Date().toISOString();
          for (const artifact of result.artifacts) {
            upsertArtifact(state.artifacts, artifact);
            await this.#store.emit(state, "artifact.updated", { artifact }, stage.id);
          }
          for (const finding of result.findings) {
            state.findings.push(finding);
            await this.#store.emit(state, "finding.discovered", { finding }, stage.id);
          }
          await this.#store.save(state);
          await this.#store.emit(state, result.status === "skipped" ? "stage.skipped" : "stage.completed", { result }, stage.id);
        } catch (error) {
          stageState.status = "failed";
          stageState.finishedAt = new Date().toISOString();
          stageState.error = errorMessage(error);
          await this.#store.save(state);
          await this.#store.emit(state, "stage.failed", { error: stageState.error }, stage.id);
          throw error;
        }
      }
      state.status = "completed";
      await this.#store.save(state);
      await this.#store.emit(state, "run.completed", { artifacts: state.artifacts, findings: state.findings });
    } catch (error) {
      if (error instanceof CancelledError || signal.aborted) {
        state.status = "cancelled";
        await this.#store.save(state);
        await this.#store.emit(state, "run.cancelled", {});
      } else {
        state.status = "failed";
        state.error = errorMessage(error);
        await this.#store.save(state);
        await this.#store.emit(state, "run.failed", { error: state.error });
      }
    } finally {
      this.#abortControllers.delete(state.id);
    }
  }

  async #initialize(request: RunRequest): Promise<RunState> {
    // Preflight before persistence so a typo cannot cause the service to create a
    // directory and accidentally make an invalid projectRoot appear valid.
    await validatePathGate(request);
    const state = initialRunState(randomUUID(), request);
    await this.#store.create(state);
    await this.#store.emit(state, "run.created", { request });
    return state;
  }

  #validatedArtifacts(state: RunState, artifacts: Artifact[], stageId: StageId): Artifact[] {
    const validated: Artifact[] = [];
    for (const artifact of artifacts) {
      const filename = path.resolve(state.request.projectRoot, artifact.path);
      const allowed = isWithin(state.request.projectRoot, filename)
        || Boolean(state.request.outputDir && isWithin(state.request.outputDir, filename))
        || Boolean(stageId === "setup" && state.request.haprayRoot && isWithin(state.request.haprayRoot, filename))
        || Boolean(stageId === "setup" && state.request.repoRoot && isWithin(state.request.repoRoot, filename));
      if (allowed) {
        artifact.path = filename;
        validated.push(artifact);
        continue;
      }
      const readOnlyInput = [this.#skillRoot, state.request.sourceDir, state.request.soDir]
        .some((root) => root && isWithin(root, filename));
      if (readOnlyInput) continue;
      throw new Error(`Agent reported an artifact outside projectRoot, outputDir, and the stage-authorized tool roots: ${artifact.path}`);
    }
    return validated;
  }
}

function updateAgentUsage(stage: StageState, event: Record<string, unknown>, usageByMessage: Map<string, AgentUsage>): boolean {
  if (event.type !== "message.updated") return false;
  const properties = record(event.properties);
  const info = record(properties?.info);
  const tokens = record(info?.tokens);
  if (!info || !tokens || typeof info.id !== "string" || info.role !== "assistant") return false;
  const usage: AgentUsage = {
    inputTokens: number(tokens.input),
    outputTokens: number(tokens.output),
    reasoningTokens: number(tokens.reasoning),
    cacheReadTokens: number(record(tokens.cache)?.read),
    cacheWriteTokens: number(record(tokens.cache)?.write),
    totalTokens: number(tokens.total) || number(tokens.input) + number(tokens.output) + number(tokens.reasoning),
    cost: number(info.cost),
  };
  const previous = usageByMessage.get(info.id);
  if (previous && JSON.stringify(previous) === JSON.stringify(usage)) return false;
  usageByMessage.set(info.id, usage);
  stage.usage = [...usageByMessage.values()].reduce<AgentUsage>((total, current) => ({
    inputTokens: total.inputTokens + current.inputTokens,
    outputTokens: total.outputTokens + current.outputTokens,
    reasoningTokens: total.reasoningTokens + current.reasoningTokens,
    cacheReadTokens: total.cacheReadTokens + current.cacheReadTokens,
    cacheWriteTokens: total.cacheWriteTokens + current.cacheWriteTokens,
    totalTokens: total.totalTokens + current.totalTokens,
    cost: total.cost + current.cost,
  }), emptyUsage());
  return true;
}

function emptyUsage(): AgentUsage {
  return { inputTokens: 0, outputTokens: 0, reasoningTokens: 0, cacheReadTokens: 0, cacheWriteTokens: 0, totalTokens: 0, cost: 0 };
}

function record(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function number(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

class CancelledError extends Error {}

function upsertArtifact(artifacts: Artifact[], artifact: Artifact): void {
  const index = artifacts.findIndex((candidate) => candidate.kind === artifact.kind && candidate.path === artifact.path);
  if (index === -1) artifacts.push(artifact);
  else artifacts[index] = artifact;
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof Error)) return String(error);
  const details: string[] = [error.message];
  const seen = new Set<unknown>([error]);
  let cause: unknown = error.cause;
  while (cause !== undefined && cause !== null && !seen.has(cause)) {
    seen.add(cause);
    if (cause instanceof Error) {
      const code = "code" in cause && typeof cause.code === "string" ? `${cause.code}: ` : "";
      details.push(`${code}${cause.message}`);
      cause = cause.cause;
    } else {
      details.push(String(cause));
      break;
    }
  }
  return details.filter((detail, index) => index === 0 || detail !== details[index - 1]).join(" (caused by: ")
    + ")".repeat(Math.max(0, details.length - 1));
}
