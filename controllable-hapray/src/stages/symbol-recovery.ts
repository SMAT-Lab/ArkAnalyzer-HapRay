import type { RunState } from "../domain.js";
import { AgentStage } from "./agent-stage.js";

export class SymbolRecoveryStage extends AgentStage {
  readonly id = "symbol-recovery" as const;
  readonly title = "optional symbol recovery";
  readonly documents = ["workflow/gen-perf-report.md", "analysis/symbol-recovery-analysis.md", "schemas/hapray-tool-result.md"];
  protected skip(state: RunState): string | undefined {
    if (state.request.symbolRecovery === "never") return "Symbol recovery policy is never.";
    if (state.request.symbolRecovery === "auto" && !requestsSymbolLevelAttribution(state.request.request)) {
      return "Auto skipped symbol recovery: the request does not require symbol-level attribution, and the HapRay Skill specifies that SO-, frame-, thread-, IPC-, and high-load analysis do not depend on inferred symbols.";
    }
    return undefined;
  }
  protected instruction(state: RunState): string {
    if (state.request.symbolRecovery === "always") {
      return "Symbol recovery was explicitly requested. Run update exactly once with the confirmed soDir, or use the documented device-pull fallback. Verify hiperf_report_with_inferred_symbols.html.";
    }
    return "Policy is auto. Inspect the collected/existing report first. Run update exactly once only when symbol-level analysis is needed and hotspots/flamegraphs contain stripped libxxx.so+0x addresses. Otherwise return status=skipped with the evidence-based reason. Do not run symbol-recovery.exe manually.";
  }
}

function requestsSymbolLevelAttribution(request: string): boolean {
  return /symbol(?:s|[- ](?:level|recovery))?|符号(?:恢复|级)/i.test(request);
}
