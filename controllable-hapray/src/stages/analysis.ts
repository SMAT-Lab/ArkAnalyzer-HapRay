import { AgentStage } from "./agent-stage.js";

export class AnalysisStage extends AgentStage {
  readonly id = "analysis" as const;
  readonly title = "high-load analysis";
  readonly documents = ["analysis/README.md", "analysis/high-load-analysis.md", "analysis/scroll-jank-trace-analysis.md", "analysis/symbol-recovery-analysis.md", "schemas/hapray-tool-result.md"];
  protected instruction(): string {
    return "Analyze report/ and perf.db directly. Execute the high-load minimum checklist, evaluate scroll-jank and symbol-level routes in the documented order, and explicitly record skipped analyses with reasons. Persist analysis evidence under the run's report directory. Each proven performance problem must be a performance-bug finding with quantitative evidence.";
  }
}
