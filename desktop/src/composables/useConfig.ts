import { ref } from "vue"
import { invoke } from "@tauri-apps/api/core"

type ConfigValue = Record<string, unknown>

const config = ref<ConfigValue>({})

export function useConfig() {
  const loadConfig = async () => {
    if (!(window as { __TAURI__?: unknown }).__TAURI__) {
      config.value = {}
      return
    }
    try {
      config.value = (await invoke<ConfigValue>("read_config_command")) ?? {}
    } catch {
      config.value = {}
    }
  }

  const saveConfig = async (newConfig: ConfigValue) => {
    if (!(window as { __TAURI__?: unknown }).__TAURI__) return
    try {
      await invoke("write_config_command", { config: newConfig })
      config.value = newConfig
    } catch (e) {
      throw new Error(String(e))
    }
  }

  const getPluginConfig = (pluginId: string): Record<string, unknown> => {
    const plugins = (config.value.plugins as Record<string, Record<string, unknown>>) ?? {}
    const pluginEntry = plugins[pluginId] ?? {}
    const nested = pluginEntry.config
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      return nested as Record<string, unknown>
    }
    return pluginEntry
  }

  return {
    config,
    loadConfig,
    saveConfig,
    getPluginConfig,
  }
}
