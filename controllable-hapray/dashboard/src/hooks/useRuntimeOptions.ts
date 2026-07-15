import { useEffect, useState } from 'react'

export interface RuntimeOption {
  id: string
  label: string
  detail?: string
  providerID?: string
}

export interface RuntimeOptionCatalog {
  agents: RuntimeOption[]
  providers: RuntimeOption[]
  models: RuntimeOption[]
  devices: RuntimeOption[]
  packages: RuntimeOption[]
  testcases: RuntimeOption[]
  errors: string[]
}

const EMPTY_OPTIONS: RuntimeOptionCatalog = {
  agents: [], providers: [], models: [], devices: [], packages: [], testcases: [], errors: [],
}

export function useRuntimeOptions(projectRoot: string, haprayRoot: string, device: string) {
  const [options, setOptions] = useState<RuntimeOptionCatalog>(EMPTY_OPTIONS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    let timer: number | undefined
    let firstLoad = true
    const refresh = async () => {
      const query = new URLSearchParams()
      if (projectRoot.trim()) query.set('projectRoot', projectRoot.trim())
      if (haprayRoot.trim()) query.set('haprayRoot', haprayRoot.trim())
      if (device) query.set('device', device)
      try {
        if (firstLoad) setLoading(true)
        const response = await fetch(`/v1/options?${query}`, { signal: controller.signal })
        const body = await response.json() as RuntimeOptionCatalog & { error?: string }
        if (!response.ok) throw new Error(body.error ?? `Option discovery failed with ${response.status}`)
        setOptions(body)
      } catch (error) {
        if (!controller.signal.aborted) setOptions({ ...EMPTY_OPTIONS, errors: [error instanceof Error ? error.message : String(error)] })
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
          firstLoad = false
          timer = window.setTimeout(refresh, 10_000)
        }
      }
    }
    timer = window.setTimeout(refresh, 250)
    return () => {
      if (timer !== undefined) window.clearTimeout(timer)
      controller.abort()
    }
  }, [device, haprayRoot, projectRoot])

  return { options, loading }
}
