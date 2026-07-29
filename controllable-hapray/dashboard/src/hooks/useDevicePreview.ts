import { useEffect, useState } from 'react'

export interface DevicePreviewStatus {
  available: boolean
  connected: boolean
  frameAvailable: boolean
  target?: string
  updatedAt?: string
  error?: string
}

const INITIAL_STATUS: DevicePreviewStatus = {
  available: false,
  connected: false,
  frameAvailable: false,
}

export function useDevicePreview() {
  const [status, setStatus] = useState<DevicePreviewStatus>(INITIAL_STATUS)

  useEffect(() => {
    let disposed = false
    let timer: number | undefined

    const refresh = async () => {
      try {
        const response = await fetch('/v1/device')
        const body = await response.json() as DevicePreviewStatus & { error?: string }
        if (!response.ok) throw new Error(body.error ?? `Device preview request failed with ${response.status}`)
        if (!disposed) setStatus(body)
      } catch (error) {
        if (!disposed) setStatus({ ...INITIAL_STATUS, error: error instanceof Error ? error.message : String(error) })
      } finally {
        if (!disposed) timer = window.setTimeout(refresh, 1_000)
      }
    }

    void refresh()
    return () => {
      disposed = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [])

  const frameUrl = status.frameAvailable && status.updatedAt
    ? `/v1/device/frame?v=${encodeURIComponent(status.updatedAt)}`
    : null

  return { status, frameUrl }
}
