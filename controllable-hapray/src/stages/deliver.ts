import { AgentStage } from "./agent-stage.js";
import type { RunState } from "../domain.js";

export class DeliverStage extends AgentStage {
  readonly id = "deliver" as const;
  readonly title = "analysis deliverable";
  readonly documents = ["report/analysis-deliverable.md", "analysis/high-load-analysis.md", "root-cause/comprehensive.md"];
  protected instruction(state: RunState): string {
    const outputDir = state.request.outputDir ?? `${state.request.projectRoot}/reports`;
    return `Apply every stage-6 gate and create the required hapray-analysis-YYYYMMDD-topic.md deliverable under ${outputDir}. Merge CLI root causes, Agent supplementary root causes, high-load findings, skipped dimensions, confidence, repair advice, and reproduction paths. Do not invent missing metrics. Return the final report as an artifact. Upstream stages already emitted finding events, so the structured result findings array MUST be empty; keep the deduplicated findings in the report.`;
  }
}
