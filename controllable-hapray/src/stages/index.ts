import { AnalysisStage } from "./analysis.js";
import { CollectStage } from "./collect.js";
import { DeliverStage } from "./deliver.js";
import { PathGateStage } from "./path-gate.js";
import { RootCauseStage } from "./root-cause.js";
import { SetupStage } from "./setup.js";
import { SymbolRecoveryStage } from "./symbol-recovery.js";
import type { WorkflowStage } from "./contracts.js";

export type { StageContext, WorkflowStage } from "./contracts.js";

export function defaultStages(): WorkflowStage[] {
  return [
    new PathGateStage(),
    new SetupStage(),
    new CollectStage(),
    new SymbolRecoveryStage(),
    new AnalysisStage(),
    new RootCauseStage(),
    new DeliverStage(),
  ];
}
