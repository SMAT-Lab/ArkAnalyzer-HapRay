import assert from 'node:assert/strict'
import test from 'node:test'
import { sessionTranscript } from '../src/session-events.ts'
import type { WorkflowEvent } from '../src/types/hapray.ts'

function agentEvent(id: number, data: Record<string, unknown>, stage: 'analysis' | 'deliver' = 'analysis'): WorkflowEvent {
  return { id, runId: 'run-1', timestamp: `2026-07-15T00:00:0${id}.000Z`, type: 'agent.event', stage, data }
}

test('sessionTranscript keeps meaningful latest snapshots for the selected session stage', () => {
  const events = [
    agentEvent(1, { type: 'message.updated', properties: { info: { id: 'user-1', role: 'user' } } }),
    agentEvent(2, { type: 'message.part.updated', properties: { part: { id: 'tool-1', type: 'tool', state: { status: 'running' } } } }),
    agentEvent(3, { type: 'message.part.updated', properties: { part: { id: 'tool-1', type: 'tool', state: { status: 'completed', title: 'Read report' } } } }),
    agentEvent(4, { type: 'message.updated', properties: { info: { id: 'assistant-1', role: 'assistant', tokens: { total: 42 } } } }),
    agentEvent(5, { type: 'message.part.updated', properties: { part: { id: 'noise-1', type: 'snapshot' } } }),
    agentEvent(6, { type: 'message.part.updated', properties: { part: { id: 'other-stage', type: 'text', text: 'ignore' } } }, 'deliver'),
  ]

  assert.deepEqual(sessionTranscript(events, 'analysis').map((event) => event.id), [3, 4])
})
