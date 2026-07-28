import { useCallback, useEffect, useRef, useState } from 'react'
import type { CreateRunResponse, RunRequest, RunState, WorkflowEvent, WorkflowEventType } from '../types/hapray'

const EVENT_TYPES: WorkflowEventType[] = [
  'run.created', 'run.started', 'run.completed', 'run.failed', 'run.cancelled',
  'stage.started', 'stage.completed', 'stage.skipped', 'stage.failed',
  'artifact.updated', 'finding.discovered', 'agent.event',
]

interface ActiveRun {
  id: string
  projectRoot: string
}

export function useHapRayService() {
  const [run, setRun] = useState<RunState | null>(null)
  const [events, setEvents] = useState<WorkflowEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sourceRef = useRef<EventSource | null>(null)
  const activeRef = useRef<ActiveRun | null>(null)

  const disconnect = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    setConnected(false)
  }, [])

  const refresh = useCallback(async (active = activeRef.current) => {
    if (!active) return null
    const response = await fetch(runUrl(active))
    const body = await readJson<RunState & { error?: string }>(response)
    setRun(body)
    return body
  }, [])

  const connect = useCallback((active: ActiveRun, resetEvents = true) => {
    disconnect()
    activeRef.current = active
    if (resetEvents) setEvents([])
    setError(null)
    const source = new EventSource(`${runUrl(active)}&stream=true`)
    sourceRef.current = source
    source.onopen = () => setConnected(true)
    source.onerror = () => {
      setConnected(false)
      setError('Live event stream disconnected; the browser will retry automatically.')
    }
    for (const type of EVENT_TYPES) {
      source.addEventListener(type, (message) => {
        const event = JSON.parse((message as MessageEvent<string>).data) as WorkflowEvent
        setEvents((current) => appendEvent(current, event))
        setError(null)
        void refresh(active).catch((cause: unknown) => setError(errorMessage(cause)))
        if (type === 'run.completed' || type === 'run.failed' || type === 'run.cancelled') {
          window.setTimeout(disconnect, 0)
        }
      })
    }
  }, [disconnect, refresh])

  const createRun = useCallback(async (request: RunRequest) => {
    disconnect()
    setError(null)
    const response = await fetch('/v1/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    const body = await readJson<CreateRunResponse & { error?: string }>(response)
    setRun(body.run)
    const active = { id: body.run.id, projectRoot: body.run.request.projectRoot }
    connect(active)
    return body.run
  }, [connect, disconnect])

  const openRun = useCallback(async (active: ActiveRun) => {
    disconnect()
    setError(null)
    activeRef.current = active
    setEvents([])
    const state = await refresh(active)
    if (state) connect(active, false)
    return state
  }, [connect, disconnect, refresh])

  const cancelRun = useCallback(async () => {
    const active = activeRef.current
    if (!active) return
    const response = await fetch(runUrl(active), { method: 'DELETE' })
    await readJson(response)
    await refresh(active)
  }, [refresh])

  const clear = useCallback(() => {
    disconnect()
    activeRef.current = null
    setRun(null)
    setEvents([])
    setError(null)
  }, [disconnect])

  useEffect(() => disconnect, [disconnect])

  return { run, events, connected, error, createRun, openRun, cancelRun, clear }
}

export function appendEvent(events: WorkflowEvent[], event: WorkflowEvent): WorkflowEvent[] {
  if (events.some((candidate) => candidate.id === event.id)) return events
  if (!events.length || (events.at(-1)?.id ?? 0) < event.id) return [...events, event]
  return [...events, event].sort((left, right) => left.id - right.id)
}

function runUrl(active: ActiveRun): string {
  return `/v1/runs/${encodeURIComponent(active.id)}?projectRoot=${encodeURIComponent(active.projectRoot)}`
}

async function readJson<T = Record<string, unknown>>(response: Response): Promise<T> {
  const body = await response.json() as T & { error?: string }
  if (!response.ok) throw new Error(body.error ?? `HapRay service request failed with ${response.status}`)
  return body
}

function errorMessage(value: unknown): string {
  return value instanceof Error ? value.message : String(value)
}
