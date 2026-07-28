import assert from 'node:assert/strict'
import test from 'node:test'
import { copyText } from '../src/clipboard.ts'

test('copyText writes the complete displayed value to the clipboard', async () => {
  const values: string[] = []
  await copyText('{\n  "result": true\n}', { writeText: async (value) => { values.push(value) } })
  assert.deepEqual(values, ['{\n  "result": true\n}'])
})

test('copyText falls back when the Clipboard API is denied', async () => {
  const values: string[] = []
  await copyText('summary', { writeText: async () => { throw new Error('denied') } }, (value) => {
    values.push(value)
    return true
  })
  assert.deepEqual(values, ['summary'])
})
