import { appendFile, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import type { RunState, WorkflowEvent, WorkflowEventType, StageId } from "./domain.js";
import { WorkflowEventBus } from "./event-bus.js";

const RENAME_RETRY_DELAYS_MS = [10, 20, 40, 80, 160] as const;

export async function renameWithRetry(
  source: string,
  destination: string,
  renameFile: typeof rename = rename,
): Promise<void> {
  for (const retryDelay of RENAME_RETRY_DELAYS_MS) {
    try {
      await renameFile(source, destination);
      return;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EPERM") throw error;
      await delay(retryDelay);
    }
  }
  await renameFile(source, destination);
}

export class RunStore {
  readonly #bus: WorkflowEventBus;
  readonly #locks = new Map<string, Promise<void>>();
  readonly #eventIds = new Map<string, number>();

  constructor(bus: WorkflowEventBus) {
    this.#bus = bus;
  }

  runDir(stateOrRequest: RunState | { projectRoot: string }, runId: string): string {
    const projectRoot = "request" in stateOrRequest
      ? stateOrRequest.request.projectRoot
      : stateOrRequest.projectRoot;
    return path.join(projectRoot, ".hapray-service", "runs", runId);
  }

  async create(state: RunState): Promise<void> {
    const directory = this.runDir(state, state.id);
    await mkdir(directory, { recursive: true });
    await writeFile(path.join(state.request.projectRoot, ".hapray-service", ".gitignore"), "*\n", "utf8");
    await this.#writeState(directory, state);
  }

  async load(projectRoot: string, runId: string): Promise<RunState> {
    const filename = path.join(this.runDir({ projectRoot }, runId), "state.json");
    return JSON.parse(await readFile(filename, "utf8")) as RunState;
  }

  async save(state: RunState): Promise<void> {
    state.updatedAt = new Date().toISOString();
    await this.#serialized(state.id, () => this.#writeState(this.runDir(state, state.id), state));
  }

  async emit(
    state: RunState,
    type: WorkflowEventType,
    data: Record<string, unknown>,
    stage?: StageId,
  ): Promise<WorkflowEvent> {
    return this.#serialized(state.id, async () => {
      const directory = this.runDir(state, state.id);
      await mkdir(directory, { recursive: true });
      let lastEventId = this.#eventIds.get(state.id);
      if (lastEventId === undefined) {
        const events = await this.#readEventsFile(directory);
        lastEventId = events.at(-1)?.id ?? 0;
      }
      const event: WorkflowEvent = {
        id: lastEventId + 1,
        runId: state.id,
        timestamp: new Date().toISOString(),
        type,
        data,
        ...(stage ? { stage } : {}),
      };
      await appendFile(path.join(directory, "events.jsonl"), `${JSON.stringify(event)}\n`, "utf8");
      this.#eventIds.set(state.id, event.id);
      this.#bus.publish(event);
      return event;
    });
  }

  async events(projectRoot: string, runId: string, after = 0): Promise<WorkflowEvent[]> {
    const directory = this.runDir({ projectRoot }, runId);
    return (await this.#readEventsFile(directory)).filter((event) => event.id > after);
  }

  async #writeState(directory: string, state: RunState): Promise<void> {
    await mkdir(directory, { recursive: true });
    const destination = path.join(directory, "state.json");
    const temporary = `${destination}.tmp`;
    await writeFile(temporary, `${JSON.stringify(state, null, 2)}\n`, "utf8");
    await renameWithRetry(temporary, destination);
  }

  async #readEventsFile(directory: string): Promise<WorkflowEvent[]> {
    try {
      return (await readFile(path.join(directory, "events.jsonl"), "utf8"))
        .split("\n")
        .filter(Boolean)
        .map((line) => JSON.parse(line) as WorkflowEvent);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
      throw error;
    }
  }

  async #serialized<T>(runId: string, operation: () => Promise<T>): Promise<T> {
    const previous = this.#locks.get(runId) ?? Promise.resolve();
    let release!: () => void;
    const current = new Promise<void>((resolve) => { release = resolve; });
    const queued = previous.then(() => current);
    this.#locks.set(runId, queued);
    await previous;
    try {
      return await operation();
    } finally {
      release();
      if (this.#locks.get(runId) === queued) this.#locks.delete(runId);
    }
  }
}
