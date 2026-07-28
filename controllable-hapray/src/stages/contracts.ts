import type { AgentRunner } from "../agent.js";
import type { RunState, StageId, StageResult } from "../domain.js";

export interface StageContext {
  state: RunState;
  agent: AgentRunner;
  skillRoot: string;
  onSession(sessionId: string): Promise<void>;
  onAgentEvent(event: Record<string, unknown>): Promise<void>;
}

export interface WorkflowStage {
  id: StageId;
  title: string;
  execute(context: StageContext): Promise<StageResult>;
}
