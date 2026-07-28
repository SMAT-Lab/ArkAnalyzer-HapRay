import type { RunState } from "../domain.js";
import { AgentStage } from "./agent-stage.js";

export class CollectStage extends AgentStage {
  readonly id = "collect" as const;
  readonly title = "performance collection";
  readonly documents = ["workflow/perf-collect.md", "scripts/sync-testcases-to-runtime.sh", "schemas/hapray-tool-result.md", "schemas/hapray-tool-result-v1.json"];
  protected skip(state: RunState): string | undefined {
    return state.request.kind === "existing-report" ? "Existing-report run reuses the supplied HapRay reports." : undefined;
  }
  protected instruction(): string {
    return "Discover preset test cases before deciding between perf and prepare. If authoring a test case is necessary, enforce the document's step_verified device-evidence gate one operation at a time. Run perf only after prepare passes. Read hapray-tool-result.json and return outputs.reports_path as an artifact and in data.reportsPath.";
  }
}
