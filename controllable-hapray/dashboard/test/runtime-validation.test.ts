import assert from 'node:assert/strict'
import test from 'node:test'
import type { RuntimeOptionCatalog } from '../src/hooks/useRuntimeOptions.js'
import { validateRuntimeSelections } from '../src/runtime-validation.js'

const options: RuntimeOptionCatalog = {
  agents: [{ id: 'build', label: 'build' }],
  providers: [{ id: 'deepseek', label: 'DeepSeek' }],
  models: [{ id: 'deepseek-v4', label: 'DeepSeek V4', providerID: 'deepseek' }],
  devices: [{ id: 'device-a', label: 'device-a' }],
  packages: [{ id: 'com.example.app', label: 'com.example.app' }],
  testcases: [{ id: 'PerfLoad0010', label: 'PerfLoad0010' }],
  errors: [],
}

test('runtime selections accept only exact live options for full runs', () => {
  const form = {
    kind: 'full' as const,
    agent: 'build', providerID: 'deepseek', modelID: 'deepseek-v4',
    device: 'device-a', packageName: 'com.example.app', testcase: 'PerfLoad0010',
  }
  assert.doesNotThrow(() => validateRuntimeSelections(form, options))
  assert.throws(() => validateRuntimeSelections({ ...form, packageName: 'typed.freely' }, options), /Package must be selected/)
});

test('existing-report selections do not depend on HDC options', () => {
  assert.doesNotThrow(() => validateRuntimeSelections({
    kind: 'existing-report', agent: '', providerID: '', modelID: '',
    device: 'stale-device', packageName: 'stale-package', testcase: 'stale-case',
  }, options))
});
