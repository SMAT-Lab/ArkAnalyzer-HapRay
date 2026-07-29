import type { StageResult } from "../domain.js";
import { validatePathGate } from "../validation.js";
import type { StageContext, WorkflowStage } from "./contracts.js";

export class PathGateStage implements WorkflowStage {
  readonly id = "path-gate" as const;
  readonly title = "path gate";

  async execute(context: StageContext): Promise<StageResult> {
    const data = await validatePathGate(context.state.request);
    return { status: "completed", summary: "Validated and canonicalized all supplied workflow paths.", artifacts: [], findings: [], data };
  }
}
