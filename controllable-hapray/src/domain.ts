export const STAGE_IDS = [
  "path-gate",
  "setup",
  "collect",
  "symbol-recovery",
  "analysis",
  "root-cause",
  "deliver",
] as const;

export type StageId = (typeof STAGE_IDS)[number];
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type StageStatus = "pending" | "running" | "completed" | "skipped" | "failed";
export type AnalysisMode = "quick" | "full";
export type RunKind = "full" | "existing-report";
export type SymbolRecoveryPolicy = "auto" | "always" | "never";
export type RuntimeTrack = "auto" | "binary" | "source";

export interface ModelSelection {
  providerID: string;
  modelID: string;
  variant?: string;
}

export interface RunRequest {
  request: string;
  projectRoot: string;
  outputDir?: string;
  kind?: RunKind;
  haprayRoot?: string;
  reportsPath?: string;
  sourceDir?: string;
  soDir?: string;
  repoRoot?: string;
  packageName?: string;
  testcase?: string;
  device?: string;
  mode?: AnalysisMode;
  runtimeTrack?: RuntimeTrack;
  symbolRecovery?: SymbolRecoveryPolicy;
  opencode?: {
    baseUrl?: string;
    agent?: string;
    model?: ModelSelection;
  };
}

export interface Artifact {
  kind: string;
  path: string;
  description: string;
}

export type FindingKind = "performance-bug" | "root-cause" | "observation";
export type FindingSeverity = "P0" | "P1" | "P2" | "P3" | "info";

export interface Finding {
  id: string;
  kind: FindingKind;
  title: string;
  severity: FindingSeverity;
  evidence: string[];
  recommendation?: string;
  source?: { path: string; line?: number };
}

export interface StageResult {
  status: "completed" | "skipped";
  summary: string;
  decision?: string;
  artifacts: Artifact[];
  findings: Finding[];
  data: Record<string, unknown>;
}

export interface AgentUsage {
  inputTokens: number;
  outputTokens: number;
  reasoningTokens: number;
  cacheReadTokens: number;
  cacheWriteTokens: number;
  totalTokens: number;
  cost: number;
}

export interface StageState {
  id: StageId;
  status: StageStatus;
  startedAt?: string;
  finishedAt?: string;
  opencodeSessionId?: string;
  usage?: AgentUsage;
  result?: StageResult;
  error?: string;
}

export interface RunState {
  id: string;
  status: RunStatus;
  request: RunRequest;
  createdAt: string;
  updatedAt: string;
  stages: StageState[];
  artifacts: Artifact[];
  findings: Finding[];
  error?: string;
}

export type WorkflowEventType =
  | "run.created"
  | "run.started"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | "stage.started"
  | "stage.completed"
  | "stage.skipped"
  | "stage.failed"
  | "artifact.updated"
  | "finding.discovered"
  | "agent.event";

export interface WorkflowEvent {
  id: number;
  runId: string;
  timestamp: string;
  type: WorkflowEventType;
  stage?: StageId;
  data: Record<string, unknown>;
}

export function initialRunState(id: string, request: RunRequest, now = new Date()): RunState {
  const timestamp = now.toISOString();
  return {
    id,
    status: "queued",
    request,
    createdAt: timestamp,
    updatedAt: timestamp,
    stages: STAGE_IDS.map((stageId) => ({ id: stageId, status: "pending" })),
    artifacts: [],
    findings: [],
  };
}
