import type { StageId, WorkflowEvent } from './types/hapray'

export function sessionTranscript(events: WorkflowEvent[], stageId: StageId | undefined): WorkflowEvent[] {
  const latest = new Map<string, WorkflowEvent>()
  for (const event of events) {
    if (event.type !== 'agent.event' || event.stage !== stageId || !visibleAgentEvent(event)) continue
    const data = object(event.data)
    const properties = object(data?.properties)
    const identity = data?.type === 'message.updated'
      ? object(properties?.info)?.id
      : data?.type === 'message.part.updated'
        ? object(properties?.part)?.id
        : undefined
    const key = typeof identity === 'string' ? `${String(data?.type)}:${identity}` : `event:${event.id}`
    latest.delete(key)
    latest.set(key, event)
  }
  return [...latest.values()].slice(-200)
}

function visibleAgentEvent(event: WorkflowEvent): boolean {
  const data = object(event.data)
  const type = data?.type
  const properties = object(data?.properties)
  if (type === 'message.updated') {
    const info = object(properties?.info)
    return info?.role === 'assistant' && Boolean(object(info.tokens))
  }
  if (type === 'message.part.updated') {
    const partType = object(properties?.part)?.type
    return typeof partType === 'string' && ['reasoning', 'text', 'tool', 'step-start', 'step-finish'].includes(partType)
  }
  return typeof type === 'string' && (type.includes('permission') || type.includes('error'))
}

function object(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined
}
