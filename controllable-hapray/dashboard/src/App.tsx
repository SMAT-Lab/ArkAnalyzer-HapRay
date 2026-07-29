import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, AlertTriangle, Archive, ArrowRight, BarChart3, Braces, Check, CheckCheck, ChevronDown,
  ChevronRight, Circle, FileText, FolderOpen, GitBranch,
  HardDriveDownload, LockKeyhole, Play,
  PlayCircle, Plus, Copy, Radar, Radio, ShieldCheck,
  Smartphone, SquareTerminal, StopCircle, Target, X, XCircle,
} from 'lucide-react'
import './App.css'
import { copyText } from './clipboard'
import { useHapRayService } from './hooks/useHapRayService'
import { useDevicePreview } from './hooks/useDevicePreview'
import { useRuntimeOptions } from './hooks/useRuntimeOptions'
import type { RuntimeOption } from './hooks/useRuntimeOptions'
import { validateRuntimeSelections } from './runtime-validation'
import { sessionTranscript } from './session-events'
import type { RunRequest, RunState, StageId, StageState, WorkflowEvent } from './types/hapray'

type PanelTab = 'events' | 'sessions' | 'artifacts'

type FormState = Required<Pick<RunRequest, 'request' | 'projectRoot'>> & {
  kind: 'full' | 'existing-report'
  haprayRoot: string
  reportsPath: string
  sourceDir: string
  soDir: string
  outputDir: string
  packageName: string
  testcase: string
  device: string
  mode: 'quick' | 'full'
  runtimeTrack: 'auto' | 'binary' | 'source'
  symbolRecovery: 'auto' | 'always' | 'never'
  agent: string
  providerID: string
  modelID: string
}

interface RecentRun {
  id: string
  projectRoot: string
  request: string
  createdAt: string
}

interface StageDefinition {
  id: StageId
  number: number
  title: string
  summary: string
  action: string
  icon: typeof Activity
  optional?: boolean
}

type PathFieldKey = 'projectRoot' | 'haprayRoot' | 'reportsPath' | 'sourceDir' | 'soDir' | 'outputDir'

const EMPTY_FORM: FormState = {
  request: '', projectRoot: '', kind: 'full', haprayRoot: '', reportsPath: '', sourceDir: '', soDir: '',
  outputDir: '', packageName: '', testcase: '', device: '', mode: 'full', runtimeTrack: 'auto',
  symbolRecovery: 'auto', agent: 'build', providerID: '', modelID: '',
}

const STAGES: StageDefinition[] = [
  { id: 'path-gate', number: 0, title: 'Path Gate', summary: 'Canonicalize and validate filesystem boundaries.', action: 'validate request contract', icon: LockKeyhole },
  { id: 'setup', number: 1, title: 'Setup', summary: 'Prepare the selected runtime or source workspace.', action: 'prepare workspace', icon: HardDriveDownload },
  { id: 'collect', number: 2, title: 'Collect', summary: 'Capture and materialize performance reports.', action: 'prepare → perf', icon: PlayCircle },
  { id: 'symbol-recovery', number: 3, title: 'Symbol Recovery', summary: 'Recover stripped symbols when policy requires it.', action: 'update --so_dir', icon: Braces, optional: true },
  { id: 'analysis', number: 4, title: 'Analysis', summary: 'Find frame, thread, IPC, CPU, and memory hotspots.', action: 'analyze report signals', icon: BarChart3 },
  { id: 'root-cause', number: 5, title: 'Root Cause', summary: 'Correlate evidence with source-level causes.', action: 'synthesize root cause', icon: Radar, optional: true },
  { id: 'deliver', number: 6, title: 'Deliver', summary: 'Write the final evidence-backed analysis report.', action: 'publish deliverable', icon: FileText },
]

export default function App() {
  const service = useHapRayService()
  const devicePreview = useDevicePreview()
  const [form, setForm] = useState<FormState>(() => loadDraft())
  const runtime = useRuntimeOptions(form.projectRoot, form.haprayRoot, form.device)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>(() => loadRecentRuns())
  const [serviceOnline, setServiceOnline] = useState<boolean | null>(null)
  const [panelTab, setPanelTab] = useState<PanelTab>('events')
  const [showDevicePreview, setShowDevicePreview] = useState(false)
  const [pathPicker, setPathPicker] = useState<{ key: PathFieldKey; label: string } | null>(null)

  useEffect(() => {
    localStorage.setItem('hapray.dashboard.draft', JSON.stringify(form))
  }, [form])

  useEffect(() => {
    fetch('/health').then((response) => setServiceOnline(response.ok)).catch(() => setServiceOnline(false))
  }, [])

  const patchForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const startRun = async (event: React.FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setFormError(null)
    try {
      validateRuntimeSelections(form, runtime.options)
      const run = await service.createRun(toRunRequest(form))
      const recent = { id: run.id, projectRoot: run.request.projectRoot, request: run.request.request, createdAt: run.createdAt }
      setRecentRuns((current) => saveRecentRuns([recent, ...current.filter((item) => item.id !== run.id)].slice(0, 8)))
    } catch (cause) {
      setFormError(errorMessage(cause))
    } finally {
      setSubmitting(false)
    }
  }

  const openRecent = async (recent: RecentRun) => {
    setFormError(null)
    try {
      await service.openRun(recent)
    } catch (cause) {
      setFormError(errorMessage(cause))
    }
  }

  const removeRecent = (id: string) => {
    setRecentRuns((current) => saveRecentRuns(current.filter((item) => item.id !== id)))
  }

  const newRun = () => {
    service.clear()
    setForm((current) => ({ ...EMPTY_FORM, projectRoot: current.projectRoot, haprayRoot: current.haprayRoot, sourceDir: current.sourceDir, soDir: current.soDir }))
  }

  const busy = service.run?.status === 'running' || service.run?.status === 'queued'
  const connectionLabel = serviceOnline ? 'HapRay service' : serviceOnline === false ? 'Service offline' : 'Connecting…'

  return (
    <div className="vscode-shell">
      <TitleBar serviceOnline={serviceOnline} onNewRun={newRun} hasRun={Boolean(service.run)} />

      <div className={`vscode-workbench ${showDevicePreview ? 'has-device-preview' : ''}`}>
        <PrimarySidebar
          form={form}
          patchForm={patchForm}
          showAdvanced={showAdvanced}
          setShowAdvanced={setShowAdvanced}
          startRun={startRun}
          submitting={submitting}
          busy={busy}
          error={formError ?? service.error}
          recentRuns={recentRuns}
          openRecent={openRecent}
          removeRecent={removeRecent}
          activeRunId={service.run?.id}
          runtime={runtime}
          browsePath={(key, label) => setPathPicker({ key, label })}
        />

        <main className="editor-group">
          <EditorTabs run={service.run} />
          <Breadcrumbs run={service.run} />
          <WorkflowEditor run={service.run} events={service.events} connected={service.connected} onCancel={service.cancelRun} />
          <BottomPanel tab={panelTab} setTab={setPanelTab} run={service.run} events={service.events} />
        </main>

        <FindingsSidebar
          run={service.run}
          device={devicePreview.status}
          previewOpen={showDevicePreview}
          togglePreview={() => setShowDevicePreview((current) => !current)}
        />
        {showDevicePreview && <DevicePreviewPane status={devicePreview.status} frameUrl={devicePreview.frameUrl} onClose={() => setShowDevicePreview(false)} />}
      </div>

      <StatusBar
        label={connectionLabel}
        serviceOnline={serviceOnline}
        run={service.run}
        connected={service.connected}
        eventCount={service.events.length}
      />
      {pathPicker && (
        <DirectoryPicker
          label={pathPicker.label}
          initialPath={form[pathPicker.key] || form.projectRoot}
          onCancel={() => setPathPicker(null)}
          onSelect={(value) => {
            patchForm(pathPicker.key, value)
            setPathPicker(null)
          }}
        />
      )}
    </div>
  )
}

function TitleBar({ serviceOnline, onNewRun, hasRun }: { serviceOnline: boolean | null; onNewRun: () => void; hasRun: boolean }) {
  return (
    <header className="titlebar">
      <div className="titlebar-brand">
        <span className="brand-mark">H</span>
        <span className="brand-name">ArkAnalyzer-HapRay</span>
      </div>
      <div className="titlebar-actions">
        <span className={`service-dot ${serviceOnline ? 'is-online' : serviceOnline === false ? 'is-offline' : ''}`} />
        <span className="service-label">{serviceOnline ? 'Service online' : serviceOnline === false ? 'Service offline' : 'Connecting…'}</span>
        {hasRun && <button className="ghost-button" onClick={onNewRun} title="New run"><Plus size={15} /> New run</button>}
      </div>
    </header>
  )
}

function PrimarySidebar({
  form, patchForm, showAdvanced, setShowAdvanced, startRun, submitting, busy, error,
  recentRuns, openRecent, removeRecent, activeRunId,
  runtime, browsePath,
}: {
  form: FormState
  patchForm: <K extends keyof FormState>(key: K, value: FormState[K]) => void
  showAdvanced: boolean
  setShowAdvanced: React.Dispatch<React.SetStateAction<boolean>>
  startRun: (event: React.FormEvent) => Promise<void>
  submitting: boolean
  busy: boolean
  error: string | null
  recentRuns: RecentRun[]
  openRecent: (recent: RecentRun) => Promise<void>
  removeRecent: (id: string) => void
  activeRunId?: string
  runtime: ReturnType<typeof useRuntimeOptions>
  browsePath: (key: PathFieldKey, label: string) => void
}) {
  return (
    <aside className="primary-sidebar">
      <div className="sidebar-title"><span>EXPLORER</span></div>
      <div className="sidebar-scroll">
        <section className="sidebar-section is-open">
          <div className="section-header"><ChevronDown size={15} /><span>HAPRAY RUN</span></div>
          <form className="run-form" onSubmit={startRun}>
            <Field label="Analysis request" required>
              <textarea
                className="vscode-input request-input"
                rows={3}
                value={form.request}
                onChange={(event) => patchForm('request', event.target.value)}
                onKeyDown={(event) => {
                  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') event.currentTarget.form?.requestSubmit()
                }}
                placeholder="Describe the performance analysis…"
                required
              />
            </Field>
            <Field label="Project root" required><PathInput value={form.projectRoot} onBrowse={() => browsePath('projectRoot', 'Project root')} placeholder="Choose workspace directory" required /></Field>
            <div className="form-grid">
              <Field label="Kind"><Select value={form.kind} onChange={(value) => patchForm('kind', value as FormState['kind'])} options={['full', 'existing-report']} /></Field>
              <Field label="Mode"><Select value={form.mode} onChange={(value) => patchForm('mode', value as FormState['mode'])} options={['full', 'quick']} /></Field>
            </div>
            {form.kind === 'full' && (
              <div className="conditional-field" role="group" aria-label="Full run tool input">
                <div className="conditional-field-heading"><HardDriveDownload size={13} /><span>Required for full run</span></div>
                <p>Choose the existing HapRay tool or runtime directory that agents should execute.</p>
                <Field label="HapRay tool root" required><PathInput value={form.haprayRoot} onBrowse={() => browsePath('haprayRoot', 'HapRay tool root')} placeholder="Choose HapRay directory" required /></Field>
              </div>
            )}
            {form.kind === 'existing-report' && (
              <div className="conditional-field" role="group" aria-label="Existing report input">
                <div className="conditional-field-heading"><FileText size={13} /><span>Required for existing-report</span></div>
                <p>Point to the profiler report directory that this run should analyze.</p>
                <Field label="Reports path" required><PathInput value={form.reportsPath} onBrowse={() => browsePath('reportsPath', 'Reports path')} placeholder="Choose report directory" required /></Field>
              </div>
            )}
            <Field label="Source directory"><PathInput value={form.sourceDir} onBrowse={() => browsePath('sourceDir', 'Source directory')} onClear={() => patchForm('sourceDir', '')} placeholder="Optional" /></Field>
            <Field label="SO directory"><PathInput value={form.soDir} onBrowse={() => browsePath('soDir', 'SO directory')} onClear={() => patchForm('soDir', '')} placeholder="Optional" /></Field>
            <button type="button" className="advanced-toggle" onClick={() => setShowAdvanced((current) => !current)}>
              {showAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />} Advanced
            </button>
            {showAdvanced && <AdvancedFields form={form} patchForm={patchForm} runtime={runtime} browsePath={browsePath} />}
            {error && <div className="form-error" role="alert"><XCircle size={14} /> <span>{error}</span></div>}
            <button className="primary-button" disabled={submitting || busy || runtime.loading}><Play size={13} fill="currentColor" />{submitting ? 'Creating Run…' : busy ? 'Run in Progress' : runtime.loading ? 'Loading Options…' : 'Start Analysis'}<span className="shortcut">⌘↵</span></button>
          </form>
        </section>

        <section className="sidebar-section is-open recent-section">
          <div className="section-header"><ChevronDown size={15} /><span>RECENT RUNS</span><span className="section-count">{recentRuns.length}</span></div>
          <div className="tree-list">
            {recentRuns.length === 0 && <div className="tree-empty">No recent runs</div>}
            {recentRuns.map((recent) => (
              <div key={recent.id} className={`tree-item ${recent.id === activeRunId ? 'is-selected' : ''}`} role="button" tabIndex={0} onClick={() => void openRecent(recent)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void openRecent(recent) } }} title={recent.request}>
                <FileText size={15} className="file-icon" />
                <span className="tree-item-copy"><span>{recent.request}</span><small>{formatRelativeDate(recent.createdAt)}</small></span>
                <button type="button" className="tree-item-delete" title="Remove from recent" aria-label={`Remove ${recent.request} from recent`} onClick={(event) => { event.stopPropagation(); removeRecent(recent.id) }}><X size={13} /></button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </aside>
  )
}

function EditorTabs({ run }: { run: RunState | null }) {
  return (
    <div className="editor-tabs" role="tablist">
      <div className="editor-tab is-active" role="tab" aria-selected="true">
        <GitBranch size={14} className="tab-icon" />
        <span>{run ? `${shortId(run.id)}.hapray` : 'workflow.hapray'}</span>
        <span className={`tab-dirty ${run?.status === 'running' ? 'is-live' : ''}`} />
      </div>
    </div>
  )
}

function Breadcrumbs({ run }: { run: RunState | null }) {
  return (
    <div className="breadcrumbs">
      <span>controllable-hapray</span><ChevronRight size={13} />
      <span>.hapray-service</span><ChevronRight size={13} />
      <span>runs</span><ChevronRight size={13} />
      <GitBranch size={12} /><span>{run ? shortId(run.id) : 'new'}</span>
    </div>
  )
}

function WorkflowEditor({ run, events, connected, onCancel }: { run: RunState | null; events: WorkflowEvent[]; connected: boolean; onCancel: () => Promise<void> }) {
  const [now, setNow] = useState(Date.now())
  const stageMap = useMemo(() => new Map(run?.stages.map((stage) => [stage.id, stage]) ?? []), [run?.stages])
  const completed = run?.stages.filter((stage) => stage.status === 'completed' || stage.status === 'skipped').length ?? 0
  const progress = run ? Math.round(completed / run.stages.length * 100) : 0
  const activeStage = run?.stages.find((stage) => stage.status === 'running')
  const activeStageId = activeStage?.id

  useEffect(() => {
    if (!activeStageId) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [activeStageId])

  return (
    <div className="editor-canvas">
      <div className="editor-document">
        <header className="document-header">
          <div className="document-heading">
            <span className="document-kicker"><Radio size={13} /> WORKFLOW</span>
            <h1>{activeStage ? STAGES.find((stage) => stage.id === activeStage.id)?.title : run ? statusTitle(run.status) : 'HapRay Analysis'}</h1>
            <p>{run ? run.request.request : 'Configure a run in Explorer to begin performance analysis.'}</p>
          </div>
          <div className="document-actions">
            {run && (run.status === 'running' || run.status === 'queued') && <button className="secondary-button danger" onClick={() => void onCancel()}><StopCircle size={14} /> Stop</button>}
            <div className={`run-state state-${run?.status ?? 'none'}`}><span className="state-dot" />{run?.status ?? 'not started'}</div>
          </div>
        </header>

        <div className="overview-grid">
          <OverviewCell label="Progress" value={`${progress}%`} detail={`${completed} / ${run?.stages.length ?? 7} stages`} />
          <OverviewCell label="Event Stream" value={connected ? 'Connected' : 'Idle'} detail={`${events.length} persisted events`} />
          <OverviewCell label="Mode" value={run?.request.mode ?? 'full'} detail={run?.request.kind ?? 'full run'} />
          <OverviewCell label="Symbols" value={run?.request.symbolRecovery ?? 'auto'} detail={run?.request.runtimeTrack ?? 'auto runtime'} />
        </div>
        <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>

        <section className="document-section">
          <div className="document-section-title"><ChevronDown size={15} /><span>STAGES</span><small>pipeline.workflow</small></div>
          <div className="stage-list">
            {STAGES.map((definition) => <StageRow key={definition.id} definition={definition} state={stageMap.get(definition.id)} run={run} now={now} />)}
          </div>
        </section>

        <div className="document-split">
          <section className="document-section">
            <div className="document-section-title"><ChevronDown size={15} /><span>REQUEST ROUTE</span></div>
            <PropertyTable rows={[
              ['kind', run?.request.kind ?? 'full'],
              ['mode', run?.request.mode ?? 'full'],
              ['runtimeTrack', run?.request.runtimeTrack ?? 'auto'],
              ['symbolRecovery', run?.request.symbolRecovery ?? 'auto'],
            ]} />
          </section>
          <section className="document-section">
            <div className="document-section-title"><ChevronDown size={15} /><span>PATH BOUNDARIES</span><ShieldCheck size={13} /></div>
            <PropertyTable rows={[
              ['projectRoot', run?.request.projectRoot ?? 'not configured'],
              ['haprayRoot', run?.request.haprayRoot ?? 'not required'],
              ['sourceDir', run?.request.sourceDir ?? 'skipped'],
              ['soDir', run?.request.soDir ?? 'skipped'],
            ]} paths />
          </section>
        </div>
      </div>
    </div>
  )
}

function StageRow({ definition, state, run, now }: { definition: StageDefinition; state?: StageState; run: RunState | null; now: number }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = definition.icon
  const status = state?.status ?? 'pending'
  const summary = state?.result?.summary ?? state?.error ?? definition.summary
  const started = Boolean(state?.startedAt)
  const detailsId = `stage-details-${definition.id}`
  return (
    <article className={`stage-row stage-${status}`}>
      <button className="stage-row-toggle" type="button" disabled={!started} aria-expanded={started ? expanded : undefined} aria-controls={started ? detailsId : undefined} onClick={() => started && setExpanded((current) => !current)}>
        <span className="line-number">{String(definition.number + 1).padStart(2, '0')}</span>
        <span className="fold-marker">{started ? expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} /> : <span />}</span>
        <span className="stage-connector"><span /></span>
        <span className="stage-icon"><Icon size={16} /></span>
        <div className="stage-main">
          <div className="stage-title-line"><strong>{definition.title}</strong><code>{definition.id}</code>{definition.optional && <span className="inline-label">optional</span>}</div>
          {state?.opencodeSessionId && <code className="stage-session" title={state.opencodeSessionId}>session {state.opencodeSessionId}</code>}
        </div>
        <div className="stage-telemetry">
          <span>{started ? formatDuration(state, now) : '—'}</span>
          <span>{started ? `${formatTokens(state?.usage?.totalTokens ?? 0)} tokens` : '—'}</span>
        </div>
        <StatusGlyph status={status} />
      </button>
      {started && expanded && (
        <StageDetails detailsId={detailsId} run={run} definition={definition} state={state} summary={summary} />
      )}
    </article>
  )
}

function StageDetails({ detailsId, run, definition, state, summary }: {
  detailsId: string
  run: RunState | null
  definition: StageDefinition
  state?: StageState
  summary: string
}) {
  const [view, setView] = useState<'interactive' | 'complete'>('interactive')
  const input = stageInputs(run, definition.id)
  const output = state?.result ?? (state?.error ? { error: state.error } : null)
  const inputJson = JSON.stringify(input, null, 2) ?? 'null'
  const outputJson = JSON.stringify(output, null, 2) ?? 'null'
  return (
    <div className="stage-details" id={detailsId}>
      <div className="stage-io-bar">
        <div className="stage-io-toggle" role="tablist" aria-label="Stage input and output view">
          <button type="button" role="tab" aria-selected={view === 'interactive'} className={view === 'interactive' ? 'is-active' : ''} onClick={() => setView('interactive')}>Interactive</button>
          <button type="button" role="tab" aria-selected={view === 'complete'} className={view === 'complete' ? 'is-active' : ''} onClick={() => setView('complete')}>Complete</button>
        </div>
      </div>
      {view === 'interactive' ? (
        <div className="stage-io-pair is-interactive">
          <IoBlock label="Input parameters" value={input} json={inputJson} tone="input" />
          <div className="io-arrow" aria-hidden="true"><ArrowRight size={16} /></div>
          <IoBlock label="Output result" value={output} json={outputJson} tone="output" />
        </div>
      ) : (
        <div className="stage-io-pair is-complete">
          <StageDetail label="Input parameters" value={input} />
          <StageDetail label="Output result" value={output} />
        </div>
      )}
      <div className="stage-result-summary"><div className="stage-detail-heading"><span>Execution summary</span><CopyButton label="execution summary" value={summary} /></div><p>{summary}</p></div>
    </div>
  )
}

function IoBlock({ label, value, json, tone }: { label: string; value: unknown; json: string; tone: 'input' | 'output' }) {
  return (
    <div className={`io-block io-${tone}`}>
      <div className="stage-detail-heading"><span>{label}</span><CopyButton label={label} value={json} /></div>
      <div className="io-tree">{value == null ? <span className="json-empty">null</span> : <JsonNode value={value} depth={0} />}</div>
    </div>
  )
}

function JsonNode({ name, value, depth }: { name?: string; value: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 1)
  const isContainer = value !== null && typeof value === 'object'
  if (!isContainer) {
    return (
      <div className="json-row json-leaf">
        {name !== undefined && <span className="json-key">{name}:</span>}
        <span className={`json-value json-${primitiveType(value)}`}>{formatPrimitive(value)}</span>
      </div>
    )
  }
  const entries: Array<readonly [string, unknown]> = Array.isArray(value)
    ? value.map((item, index) => [String(index), item] as const)
    : Object.entries(value as Record<string, unknown>)
  const preview = Array.isArray(value) ? `Array(${value.length})` : `{${entries.length} keys}`
  return (
    <div className="json-node">
      <button type="button" className="json-toggle" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        {name !== undefined && <span className="json-key">{name}:</span>}
        <span className="json-preview">{preview}</span>
      </button>
      {open && (
        <div className="json-children">
          {entries.length === 0
            ? <span className="json-empty">{Array.isArray(value) ? '[ ]' : '{ }'}</span>
            : entries.map(([key, child]) => <JsonNode key={key} name={key} value={child} depth={depth + 1} />)}
        </div>
      )}
    </div>
  )
}

function primitiveType(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return 'string'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  return 'literal'
}

function formatPrimitive(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return JSON.stringify(value)
  return String(value)
}

function StageDetail({ label, value }: { label: string; value: unknown }) {
  const content = JSON.stringify(value, null, 2) ?? 'null'
  return <div className="stage-detail"><div className="stage-detail-heading"><span>{label}</span><CopyButton label={label} value={content} /></div><pre>{content}</pre></div>
}

function CopyButton({ label, value }: { label: string; value: string }) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle')
  const handleCopy = async () => {
    try {
      await copyText(value)
      setCopyState('copied')
    } catch {
      setCopyState('failed')
    }
    window.setTimeout(() => setCopyState('idle'), 1_500)
  }
  const message = copyState === 'copied' ? `${label} copied` : copyState === 'failed' ? `Could not copy ${label}` : `Copy ${label}`
  return <button type="button" className={`copy-button state-${copyState}`} onClick={() => void handleCopy()} aria-label={message} title={message}>{copyState === 'copied' ? <CheckCheck size={12} /> : copyState === 'failed' ? <XCircle size={12} /> : <Copy size={12} />}<span className="sr-only" aria-live="polite">{copyState === 'idle' ? '' : message}</span></button>
}

function StatusGlyph({ status }: { status: StageState['status'] | 'pending' }) {
  if (status === 'completed') return <span className="status-glyph is-completed" title="Completed"><Check size={14} /></span>
  if (status === 'running') return <span className="status-glyph is-running" title="Running"><Play size={12} fill="currentColor" /></span>
  if (status === 'failed') return <span className="status-glyph is-failed" title="Failed"><XCircle size={14} /></span>
  if (status === 'skipped') return <span className="status-glyph is-skipped" title="Skipped">—</span>
  return <span className="status-glyph is-pending" title="Pending"><Circle size={11} /></span>
}

function FindingsSidebar({ run, device, previewOpen, togglePreview }: {
  run: RunState | null
  device: ReturnType<typeof useDevicePreview>['status']
  previewOpen: boolean
  togglePreview: () => void
}) {
  const findings = run?.findings ?? []
  const problems = findings.filter((finding) => finding.kind !== 'observation').length
  return (
    <aside className="secondary-sidebar">
      <div className="device-toolbar">
        <span className={`device-connection ${device.connected ? 'is-connected' : ''}`} title={device.target ?? device.error ?? 'No connected device'}>
          <Smartphone size={13} /><span>{device.connected ? `${device.target ?? 'Device'} connected` : 'No device connected'}</span>
        </span>
        <button type="button" onClick={togglePreview} disabled={!device.connected} aria-pressed={previewOpen}>
          {previewOpen ? 'Hide' : 'Monitor'}
        </button>
      </div>
      <div className="secondary-tabs"><button className="is-active">FINDINGS</button></div>
      <div className="secondary-toolbar"><span>{problems} Problems</span><span>{findings.length - problems} Observations</span></div>
      <div className="findings-list">
        {findings.length === 0 && <div className="welcome-placeholder"><Target size={28} /><strong>No findings yet</strong><p>Structured findings appear here as analysis stages complete.</p></div>}
        {findings.map((finding) => (
          <article className="finding-row" key={finding.id}>
            <div className="finding-heading"><AlertTriangle size={15} className={`severity-${finding.severity}`} /><strong>{finding.title}</strong><span className={`severity-tag severity-${finding.severity}`}>{finding.severity}</span></div>
            <div className="finding-meta">{finding.kind} · {finding.id}</div>
            {finding.evidence[0] && <p>{finding.evidence[0]}</p>}
            {finding.recommendation && <div className="finding-fix"><span>Quick Fix</span>{finding.recommendation}</div>}
            {finding.source && <button className="source-link"><FileText size={12} />{finding.source.path}{finding.source.line ? `:${finding.source.line}` : ''}</button>}
          </article>
        ))}
      </div>
    </aside>
  )
}

function DevicePreviewPane({ status, frameUrl, onClose }: {
  status: ReturnType<typeof useDevicePreview>['status']
  frameUrl: string | null
  onClose: () => void
}) {
  return (
    <aside className="device-preview" aria-label="Connected device preview">
      <div className="device-preview-header">
        <span><Smartphone size={14} />DEVICE PREVIEW</span>
        <button type="button" onClick={onClose}>Hide</button>
      </div>
      <div className="device-preview-meta">
        <span className={`device-dot ${status.connected ? 'is-connected' : ''}`} />
        <code>{status.target ?? 'Waiting for device'}</code>
      </div>
      <div className="device-screen-frame">
        {frameUrl
          ? <img src={frameUrl} alt={`Live screen of connected device ${status.target ?? ''}`} />
          : <div className="device-preview-empty"><Smartphone size={30} /><span>{status.error ?? 'Waiting for the first screenshot…'}</span></div>}
      </div>
      {status.updatedAt && <div className="device-preview-time">Updated {formatTime(status.updatedAt)}</div>}
    </aside>
  )
}

function BottomPanel({ tab, setTab, run, events }: { tab: PanelTab; setTab: (tab: PanelTab) => void; run: RunState | null; events: WorkflowEvent[] }) {
  const sessionCount = run?.stages.filter((stage) => stage.opencodeSessionId).length ?? 0
  return (
    <section className="bottom-panel">
      <div className="panel-tabs">
        <button className={tab === 'events' ? 'is-active' : ''} onClick={() => setTab('events')}>EVENTS <span>{events.length}</span></button>
        <button className={tab === 'sessions' ? 'is-active' : ''} onClick={() => setTab('sessions')}>SESSIONS <span>{sessionCount}</span></button>
        <button className={tab === 'artifacts' ? 'is-active' : ''} onClick={() => setTab('artifacts')}>ARTIFACTS <span>{run?.artifacts.length ?? 0}</span></button>
      </div>
      {tab === 'events' ? <EventTable events={events} running={run?.status === 'running'} /> : tab === 'sessions' ? <SessionTerminal run={run} events={events} /> : <ArtifactTable run={run} />}
    </section>
  )
}

function SessionTerminal({ run, events }: { run: RunState | null; events: WorkflowEvent[] }) {
  const sessions = run?.stages.filter((stage) => stage.opencodeSessionId) ?? []
  const [selected, setSelected] = useState<string | null>(null)
  const active = sessions.find((stage) => stage.status === 'running') ?? sessions.at(-1)
  const selectedStage = sessions.find((stage) => stage.opencodeSessionId === selected) ?? active
  const transcript = sessionTranscript(events, selectedStage?.id)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [selectedStage?.id, transcript.length])
  return (
    <div className="session-terminal">
      <div className="session-list">
        {sessions.length === 0 && <div className="tree-empty">No agent sessions yet</div>}
        {sessions.map((stage) => (
          <button key={stage.id} className={stage.id === selectedStage?.id ? 'is-selected' : ''} onClick={() => setSelected(stage.opencodeSessionId ?? null)}>
            <span className={`session-status stage-${stage.status}`} /><span>{stage.id}</span><small>{shortId(stage.opencodeSessionId ?? '')}</small>
          </button>
        ))}
      </div>
      <div className="terminal-output" ref={ref}>
        {!selectedStage && <PanelEmpty icon={SquareTerminal} text="Session activity will appear when an agent stage starts." />}
        {selectedStage && <div className="terminal-banner"><span>opencode</span><code>{selectedStage.opencodeSessionId}</code><span>{formatTokens(selectedStage.usage?.totalTokens ?? 0)} tokens</span></div>}
        {selectedStage && transcript.length === 0 && <div className="terminal-line is-muted">Waiting for persisted session activity…</div>}
        {transcript.map((event) => <div className="terminal-line" key={event.id}><span>{formatTime(event.timestamp)}</span><code>{agentEventLabel(event)}</code><pre>{agentEventText(event)}</pre></div>)}
      </div>
    </div>
  )
}

function EventTable({ events, running }: { events: WorkflowEvent[]; running: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const visibleEvents = events.slice(-500)
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [events.length])
  return (
    <div className="panel-content event-table" ref={ref}>
      <div className="table-header"><span>Time</span><span>Event</span><span>Stage</span><span>Message</span></div>
      {events.length === 0 && <PanelEmpty icon={SquareTerminal} text="No events have been emitted." />}
      {events.length > visibleEvents.length && <div className="event-history-note">Showing the latest {visibleEvents.length} of {events.length} events. Session transcripts retain the complete replay.</div>}
      {visibleEvents.map((event) => (
        <div className="event-row" key={event.id}>
          <span className="event-time">{formatTime(event.timestamp)}</span>
          <span className={`event-type type-${eventTone(event.type)}`}><Activity size={12} />{event.type}</span>
          <span className="event-stage">{event.stage ?? '—'}</span>
          <span className="event-message">{eventSummary(event)}</span>
        </div>
      ))}
      {running && <div className="event-row is-waiting"><span className="event-time">now</span><span className="event-type"><Radio size={12} />stream</span><span className="event-stage">—</span><span className="event-message">Waiting for the next service event…</span></div>}
    </div>
  )
}

function ArtifactTable({ run }: { run: RunState | null }) {
  return (
    <div className="panel-content artifact-table">
      <div className="table-header"><span>Type</span><span>Path</span><span>Description</span></div>
      {!run?.artifacts.length && <PanelEmpty icon={Archive} text="No artifacts have been materialized." />}
      {run?.artifacts.map((artifact) => (
        <div className="artifact-row" key={`${artifact.kind}-${artifact.path}`}>
          <span><Archive size={13} />{artifact.kind}</span><code>{artifact.path}</code><span>{artifact.description}</span>
        </div>
      ))}
    </div>
  )
}

function StatusBar({ label, serviceOnline, run, connected, eventCount }: { label: string; serviceOnline: boolean | null; run: RunState | null; connected: boolean; eventCount: number }) {
  return (
    <footer className="statusbar">
      <div className="statusbar-left">
        <span><GitBranch size={13} />main*</span>
        <span><Circle size={10} fill="currentColor" />{label}</span>
        <span><XCircle size={13} />{run?.status === 'failed' ? 1 : 0}</span>
        <span><AlertTriangle size={13} />{run?.findings.filter((finding) => finding.severity === 'P0' || finding.severity === 'P1').length ?? 0}</span>
      </div>
      <div className="statusbar-right">
        <span>{connected ? 'SSE connected' : 'SSE idle'}</span><span>{eventCount} events</span><span>HapRay</span>
        <span className="sr-only">Service status: {serviceOnline === null ? 'checking' : serviceOnline ? 'online' : 'offline'}</span>
      </div>
    </footer>
  )
}

function AdvancedFields({ form, patchForm, runtime, browsePath }: {
  form: FormState
  patchForm: <K extends keyof FormState>(key: K, value: FormState[K]) => void
  runtime: ReturnType<typeof useRuntimeOptions>
  browsePath: (key: PathFieldKey, label: string) => void
}) {
  const models = runtime.options.models.filter((option) => option.providerID === form.providerID)
  return (
    <div className="advanced-fields">
      <Field label="Output directory"><PathInput value={form.outputDir} onBrowse={() => browsePath('outputDir', 'Output directory')} onClear={() => patchForm('outputDir', '')} placeholder="Optional" /></Field>
      <div className="form-grid"><Field label="Runtime"><Select value={form.runtimeTrack} onChange={(value) => patchForm('runtimeTrack', value as FormState['runtimeTrack'])} options={['auto', 'binary', 'source']} /></Field><Field label="Symbols"><Select value={form.symbolRecovery} onChange={(value) => patchForm('symbolRecovery', value as FormState['symbolRecovery'])} options={['auto', 'always', 'never']} /></Field></div>
      {form.kind === 'full' && <>
        <Field label="Device"><OptionSelect value={form.device} options={runtime.options.devices} onChange={(value) => { patchForm('device', value); patchForm('packageName', '') }} emptyLabel={runtime.loading ? 'Loading devices…' : 'Auto (single device)'} /></Field>
        <Field label="Package"><ChoiceInput value={form.packageName} options={runtime.options.packages} onChange={(value) => patchForm('packageName', value)} placeholder={form.device || runtime.options.devices.length === 1 ? 'Search installed packages' : 'Select a device first'} /></Field>
        <Field label="Testcase"><OptionSelect value={form.testcase} options={runtime.options.testcases} onChange={(value) => patchForm('testcase', value)} emptyLabel={runtime.loading ? 'Discovering testcases…' : 'No testcase'} /></Field>
      </>}
      <Field label="OpenCode agent"><OptionSelect value={form.agent} options={runtime.options.agents} onChange={(value) => patchForm('agent', value)} emptyLabel="Default agent" /></Field>
      <div className="form-grid">
        <Field label="Provider"><OptionSelect value={form.providerID} options={runtime.options.providers} onChange={(value) => { patchForm('providerID', value); patchForm('modelID', '') }} emptyLabel="Default provider" /></Field>
        <Field label="Model"><OptionSelect value={form.modelID} options={models} onChange={(value) => patchForm('modelID', value)} emptyLabel={form.providerID ? 'Default model' : 'Select provider first'} /></Field>
      </div>
      {runtime.options.errors.length > 0 && <div className="option-warning" title={runtime.options.errors.join('\n')}><AlertTriangle size={12} />Some live options are unavailable</div>}
    </div>
  )
}

function PathInput({ value, placeholder, required, onBrowse, onClear }: { value: string; placeholder: string; required?: boolean; onBrowse: () => void; onClear?: () => void }) {
  return (
    <div className="path-input">
      <input className="vscode-input code-input" value={value} placeholder={placeholder} required={required} readOnly onClick={onBrowse} />
      {value && onClear && <button type="button" onClick={onClear} title="Clear path"><XCircle size={13} /></button>}
      <button type="button" onClick={onBrowse} title="Browse directories"><FolderOpen size={14} /></button>
    </div>
  )
}

function OptionSelect({ value, options, onChange, emptyLabel }: { value: string; options: RuntimeOption[]; onChange: (value: string) => void; emptyLabel: string }) {
  const unavailable = value && !options.some((option) => option.id === value)
  return (
    <select className="vscode-input" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{emptyLabel}</option>
      {unavailable && <option value={value} disabled>Unavailable: {value}</option>}
      {options.map((option) => <option key={`${option.providerID ?? ''}-${option.id}`} value={option.id} title={option.detail}>{option.label}</option>)}
    </select>
  )
}

function ChoiceInput({ value, options, onChange, placeholder }: { value: string; options: RuntimeOption[]; onChange: (value: string) => void; placeholder: string }) {
  const id = 'package-options'
  return <><input className="vscode-input" list={id} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} disabled={options.length === 0} /><datalist id={id}>{options.map((option) => <option key={option.id} value={option.id} />)}</datalist></>
}

interface DirectoryListing {
  path: string
  parent?: string
  directories: Array<{ name: string; path: string }>
}

function DirectoryPicker({ label, initialPath, onSelect, onCancel }: { label: string; initialPath: string; onSelect: (path: string) => void; onCancel: () => void }) {
  const [listing, setListing] = useState<DirectoryListing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (filename?: string): Promise<boolean> => {
    setLoading(true)
    setError(null)
    try {
      const query = filename ? `?path=${encodeURIComponent(filename)}` : ''
      const response = await fetch(`/v1/fs/directories${query}`)
      const body = await response.json() as DirectoryListing & { error?: string }
      if (!response.ok) throw new Error(body.error ?? `Directory browser failed with ${response.status}`)
      setListing(body)
      return true
    } catch (cause) {
      setError(errorMessage(cause))
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      if (!await load(initialPath || undefined)) await load()
    })()
  }, [initialPath, load])

  return (
    <div className="picker-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
      <section className="directory-picker" role="dialog" aria-modal="true" aria-label={`Choose ${label}`}>
        <header><FolderOpen size={16} /><strong>Choose {label}</strong><button type="button" onClick={onCancel} aria-label="Close"><XCircle size={15} /></button></header>
        <div className="picker-location"><button type="button" disabled={!listing?.parent || loading} onClick={() => void load(listing?.parent)} title="Parent directory">↑</button><code>{listing?.path ?? 'Loading…'}</code></div>
        <div className="picker-list">
          {loading && <div className="picker-message">Loading directories…</div>}
          {error && <div className="picker-message is-error">{error}</div>}
          {!loading && !error && listing?.directories.length === 0 && <div className="picker-message">No subdirectories</div>}
          {!loading && listing?.directories.map((directory) => <button type="button" key={directory.path} onDoubleClick={() => void load(directory.path)} onClick={() => void load(directory.path)}><FolderOpen size={14} /><span>{directory.name}</span></button>)}
        </div>
        <footer><button type="button" onClick={onCancel}>Cancel</button><button type="button" className="primary-button" disabled={!listing || loading} onClick={() => listing && onSelect(listing.path)}>Select Current Directory</button></footer>
      </section>
    </div>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return <label className="form-field"><span>{label}{required && <b aria-label="required">*</b>}</span>{children}</label>
}

function Select({ value, options, onChange }: { value: string; options: string[]; onChange: (value: string) => void }) {
  return <select className="vscode-input" value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select>
}

function OverviewCell({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="overview-cell"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
}

function PropertyTable({ rows, paths = false }: { rows: Array<[string, string]>; paths?: boolean }) {
  return <div className="property-table">{rows.map(([key, value]) => <div className="property-row" key={key}><span>{key}</span><code className={paths ? 'is-path' : ''}>{value}</code></div>)}</div>
}

function PanelEmpty({ icon: Icon, text }: { icon: typeof Activity; text: string }) {
  return <div className="panel-empty"><Icon size={18} /><span>{text}</span></div>
}

function toRunRequest(form: FormState): RunRequest {
  const optional = (value: string) => value.trim() || undefined
  const model = form.providerID.trim() && form.modelID.trim() ? { providerID: form.providerID.trim(), modelID: form.modelID.trim() } : undefined
  return { request: form.request.trim(), projectRoot: form.projectRoot.trim(), kind: form.kind, mode: form.mode, runtimeTrack: form.runtimeTrack, symbolRecovery: form.symbolRecovery, haprayRoot: form.kind === 'full' ? optional(form.haprayRoot) : undefined, reportsPath: form.kind === 'existing-report' ? optional(form.reportsPath) : undefined, sourceDir: optional(form.sourceDir), soDir: optional(form.soDir), outputDir: optional(form.outputDir), packageName: form.kind === 'full' ? optional(form.packageName) : undefined, testcase: form.kind === 'full' ? optional(form.testcase) : undefined, device: form.kind === 'full' ? optional(form.device) : undefined, opencode: form.agent.trim() || model ? { agent: optional(form.agent), model } : undefined }
}

function eventSummary(event: WorkflowEvent): string {
  const data = event.data
  if (typeof data.error === 'string') return data.error
  if (typeof data.title === 'string') return data.title
  const result = data.result as { summary?: unknown } | undefined
  if (typeof result?.summary === 'string') return result.summary
  const finding = data.finding as { title?: unknown } | undefined
  if (typeof finding?.title === 'string') return finding.title
  const artifact = data.artifact as { path?: unknown } | undefined
  if (typeof artifact?.path === 'string') return artifact.path
  const encoded = JSON.stringify(data)
  return encoded === '{}' ? 'State updated' : encoded
}

function eventTone(type: WorkflowEvent['type']): string {
  if (type.includes('failed') || type.includes('cancelled')) return 'error'
  if (type.includes('completed')) return 'success'
  if (type === 'finding.discovered') return 'warning'
  return 'info'
}

function stageInputs(run: RunState | null, stageId: StageId): unknown {
  if (!run) return null
  const upstream: Record<string, unknown> = {}
  for (const stage of run.stages) {
    if (stage.id === stageId) break
    if (stage.result) upstream[stage.id] = stage.result
  }
  return stageId === 'path-gate' ? { request: run.request } : { request: run.request, upstreamResults: upstream }
}

function formatDuration(stage: StageState | undefined, now: number): string {
  if (!stage?.startedAt) return '—'
  const end = stage.finishedAt ? new Date(stage.finishedAt).getTime() : now
  const seconds = Math.max(0, Math.floor((end - new Date(stage.startedAt).getTime()) / 1_000))
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return minutes ? `${minutes}m ${String(remainder).padStart(2, '0')}s` : `${remainder}s`
}

function formatTokens(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: value >= 10_000 ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(value)
}

function agentEventLabel(event: WorkflowEvent): string {
  const data = object(event.data)
  const properties = object(data?.properties)
  const part = object(properties?.part)
  if (typeof part?.type === 'string') return part.type
  return typeof data?.type === 'string' ? data.type : 'agent'
}

function agentEventText(event: WorkflowEvent): string {
  const data = object(event.data)
  const properties = object(data?.properties)
  const part = object(properties?.part)
  const state = object(part?.state)
  for (const value of [state?.title, state?.output, part?.text, part?.reason, properties?.delta]) {
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  const info = object(properties?.info)
  const tokens = object(info?.tokens)
  if (tokens) return `usage ${formatTokens(numeric(tokens.total) || numeric(tokens.input) + numeric(tokens.output) + numeric(tokens.reasoning))} tokens`
  if (typeof part?.type === 'string') return `${part.type} updated`
  return eventSummary(event)
}

function object(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined
}

function numeric(value: unknown): number { return typeof value === 'number' && Number.isFinite(value) ? value : 0 }

function statusTitle(status: RunState['status']): string {
  return status === 'completed' ? 'Analysis Complete' : status === 'failed' ? 'Analysis Failed' : status === 'cancelled' ? 'Run Cancelled' : status === 'queued' ? 'Run Queued' : 'Analysis Running'
}

function shortId(value: string): string { return value.slice(0, 8) }
function formatTime(value: string): string { return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
function formatRelativeDate(value: string): string { return new Date(value).toLocaleDateString([], { month: 'short', day: 'numeric' }) }
function errorMessage(value: unknown): string { return value instanceof Error ? value.message : String(value) }
function loadDraft(): FormState { try { return { ...EMPTY_FORM, ...JSON.parse(localStorage.getItem('hapray.dashboard.draft') ?? '{}') as Partial<FormState> } } catch { return EMPTY_FORM } }
function loadRecentRuns(): RecentRun[] { try { const value = JSON.parse(localStorage.getItem('hapray.dashboard.recent') ?? '[]') as unknown; return Array.isArray(value) ? value as RecentRun[] : [] } catch { return [] } }
function saveRecentRuns(value: RecentRun[]): RecentRun[] { localStorage.setItem('hapray.dashboard.recent', JSON.stringify(value)); return value }
