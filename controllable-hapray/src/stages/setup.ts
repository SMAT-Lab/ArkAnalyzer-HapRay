import type { RunState } from "../domain.js";
import { AgentStage } from "./agent-stage.js";

export class SetupStage extends AgentStage {
  readonly id = "setup" as const;
  readonly title = "environment setup";
  readonly documents = ["workflow/setup-binary.md", "workflow/setup-source.md", "scripts/ensure-workspace-layout.sh"];
  protected skip(state: RunState): string | undefined {
    return state.request.kind === "existing-report" ? "Existing-report run does not require environment setup." : undefined;
  }
  protected instruction(state: RunState): string {
    return `Run ensure-workspace-layout first. Inspect the validated HapRay tool root ${state.request.haprayRoot} and select the ${state.request.runtimeTrack ?? "auto"} runtime track using the Skill rules. Prefer the binary track when auto; fall back to the source track only as documented. Complete and verify the selected setup track, and execute HapRay from that explicit tool root.`;
  }
}
