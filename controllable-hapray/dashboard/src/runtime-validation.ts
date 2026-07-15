import type { RuntimeOption, RuntimeOptionCatalog } from './hooks/useRuntimeOptions'

export interface RuntimeSelections {
  kind: 'full' | 'existing-report'
  agent: string
  providerID: string
  modelID: string
  device: string
  packageName: string
  testcase: string
}

export function validateRuntimeSelections(form: RuntimeSelections, options: RuntimeOptionCatalog): void {
  const exact = (value: string, values: RuntimeOption[], label: string) => {
    if (value && !values.some((option) => option.id === value)) throw new Error(`${label} must be selected from the live options`)
  }
  exact(form.agent, options.agents, 'OpenCode agent')
  exact(form.providerID, options.providers, 'Provider')
  exact(form.modelID, options.models.filter((option) => option.providerID === form.providerID), 'Model')
  if (form.kind === 'full') {
    exact(form.device, options.devices, 'Device')
    exact(form.packageName, options.packages, 'Package')
    exact(form.testcase, options.testcases, 'Testcase')
  }
}
