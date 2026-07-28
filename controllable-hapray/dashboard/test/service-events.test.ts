import assert from 'node:assert/strict'
import test from 'node:test'
import { appendEvent } from '../src/hooks/useHapRayService.ts'
import type { WorkflowEvent } from '../src/types/hapray.ts'

const event = (id: number): WorkflowEvent => ({
  id,
  runId: 'run-1',
  timestamp: '2026-07-15T00:00:00.000Z',
  type: 'run.started',
  data: {},
})

test('appendEvent deduplicates replayed events and preserves service order', () => {
  const result = appendEvent([event(2)], event(1))
  assert.deepEqual(result.map((item) => item.id), [1, 2])
  assert.equal(appendEvent(result, event(2)), result)
})

test('appendEvent retains complete replay history for per-session transcripts', () => {
  let events: WorkflowEvent[] = []
  for (let id = 1; id <= 600; id += 1) events = appendEvent(events, event(id))
  assert.equal(events.length, 600)
  assert.equal(events[0]?.id, 1)
  assert.equal(events.at(-1)?.id, 600)
})
