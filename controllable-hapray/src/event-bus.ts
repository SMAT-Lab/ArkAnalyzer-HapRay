import { EventEmitter } from "node:events";
import type { WorkflowEvent } from "./domain.js";

export class WorkflowEventBus {
  readonly #emitter = new EventEmitter();

  publish(event: WorkflowEvent): void {
    this.#emitter.emit(event.runId, event);
    this.#emitter.emit("*", event);
  }

  subscribe(runId: string, listener: (event: WorkflowEvent) => void): () => void {
    this.#emitter.on(runId, listener);
    return () => this.#emitter.off(runId, listener);
  }
}
