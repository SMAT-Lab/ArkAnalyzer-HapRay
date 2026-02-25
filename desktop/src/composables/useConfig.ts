import { ref } from "vue"
import { invoke } from "@tauri-apps/api/core"
import { isTauriEnv } from "../utils/tauri"

type ConfigValue = Record<string, unknown>

const config = ref<ConfigValue>({})

export function useConfig() {
  const loadConfig = async (): Promise<void> => {
    if (!isTauriEnv()) {
      config.value = {}
      return
    }
    try {
      config.value =
        (await invoke<ConfigValue>("read_config_command")) ?? {}
    } catch {
      config.value = {}
    }
  }

  const saveConfig = async (newConfig: ConfigValue): Promise<void> => {
    if (!isTauriEnv()) return
    try {
      await invoke("write_config_command", { config: newConfig })
      config.value = newConfig
    } catch (e) {
      throw new Error(String(e))
    }
  }

  const getPluginConfig = (pluginId: string): Record<string, unknown> => {
    const plugins =
      (config.value.plugins as Record<string, Record<string, unknown>>) ?? {}
    const pluginEntry = plugins[pluginId] ?? {}
    const nested = pluginEntry.config

    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      return nested as Record<string, unknown>
    }
    return pluginEntry
  }

  /** 全局工作目录（执行工具时子进程 cwd），来自 config.exec_cwd */
  const getExecCwd = (): string => {
    const v = config.value.exec_cwd
    return typeof v === "string" ? v.trim() : ""
  }

  /** 全局日志级别，来自 config.logger_level，默认 INFO */
  const getLoggerLevel = (): string => {
    const v = config.value.logger_level
    if (typeof v !== "string" || !v) return "INFO"
    const u = v.toUpperCase()
    return ["DEBUG", "INFO", "WARNING", "ERROR"].includes(u) ? u : "INFO"
  }

  return {
    config,
    loadConfig,
    saveConfig,
    getPluginConfig,
    getExecCwd,
    getLoggerLevel,
  }
}
