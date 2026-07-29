export const STAGE_IDS = [
  'path-gate',
  'setup',
  'collect',
  'symbol-recovery',
  'analysis',
  'root-cause',
  'deliver',
] as const

export type StageId = (typeof STAGE_IDS)[number]
export type RunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type StageStatus = 'pending' | 'running' | 'completed' | 'skipped' | 'failed'

export interface RunRequest {
  request: string
  projectRoot: string
  outputDir?: string
  kind?: 'full' | 'existing-report'
  haprayRoot?: string
  reportsPath?: string
  sourceDir?: string
  soDir?: string
  repoRoot?: string
  packageName?: string
  testcase?: string
  device?: string
  mode?: 'quick' | 'full'
  runtimeTrack?: 'auto' | 'binary' | 'source'
  symbolRecovery?: 'auto' | 'always' | 'never'
  opencode?: {
    baseUrl?: string
    agent?: string
    model?: { providerID: string; modelID: string; variant?: string }
  }
}

export interface Artifact {
  kind: string
  path: string
  description: string
}

export interface Finding {
  id: string
  kind: 'performance-bug' | 'root-cause' | 'observation'
  title: string
  severity: 'P0' | 'P1' | 'P2' | 'P3' | 'info'
  evidence: string[]
  recommendation?: string
  source?: { path: string; line?: number }
}

export interface StageResult {
  status: 'completed' | 'skipped'
  summary: string
  decision?: string
  artifacts: Artifact[]
  findings: Finding[]
  data: Record<string, unknown>
}

export interface AgentUsage {
  inputTokens: number
  outputTokens: number
  reasoningTokens: number
  cacheReadTokens: number
  cacheWriteTokens: number
  totalTokens: number
  cost: number
}

export interface StageState {
  id: StageId
  status: StageStatus
  startedAt?: string
  finishedAt?: string
  opencodeSessionId?: string
  usage?: AgentUsage
  result?: StageResult
  error?: string
}

export interface RunState {
  id: string
  status: RunStatus
  request: RunRequest
  createdAt: string
  updatedAt: string
  stages: StageState[]
  artifacts: Artifact[]
  findings: Finding[]
  error?: string
}

export type WorkflowEventType =
  | 'run.created' | 'run.started' | 'run.completed' | 'run.failed' | 'run.cancelled'
  | 'stage.started' | 'stage.completed' | 'stage.skipped' | 'stage.failed'
  | 'artifact.updated' | 'finding.discovered' | 'agent.event'

export interface WorkflowEvent {
  id: number
  runId: string
  timestamp: string
  type: WorkflowEventType
  stage?: StageId
  data: Record<string, unknown>
}

export interface CreateRunResponse {
  run: RunState
  location: string
  events: string
}
