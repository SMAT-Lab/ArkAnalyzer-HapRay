import type { RunState } from "../domain.js";
import { AgentStage } from "./agent-stage.js";

export class RootCauseStage extends AgentStage {
  readonly id = "root-cause" as const;
  readonly title = "comprehensive root cause";
  readonly documents = ["root-cause/comprehensive.md", "analysis/high-load-analysis.md"];
  protected skip(state: RunState): string | undefined {
    return state.request.mode === "quick" ? "Quick mode omits the comprehensive root-cause stage." : undefined;
  }
  protected instruction(): string {
    return "Run the independent root-cause CLI with the comprehensive checker. Use sourceDir for with_source when present; otherwise apply the documented evidence-only degradation. Then perform the Agent-only supplementary source investigation for signals the CLI does not cover. Every proven cause must be a root-cause finding and cite evidence; include source path and line when proven.";
  }
}
