import { ref } from "vue"
import { invoke } from "@tauri-apps/api/core"

export interface ExecutionRecord {
  tool_name?: string
  plugin_id?: string
  action?: string
  action_name?: string
  menu_category?: string
  timestamp?: string
  success?: boolean
  message?: string
  params?: Record<string, unknown>
  command?: string
  output_path?: string | null
  output?: string
  result_dir?: string
}

export function useHistory() {
  const history = ref<ExecutionRecord[]>([])
  const loading = ref(false)

  const loadHistory = async (toolName?: string) => {
    if (!(window as { __TAURI__?: unknown }).__TAURI__) {
      history.value = []
      return
    }
    loading.value = true
    try {
      history.value = (await invoke<ExecutionRecord[]>("get_execution_history_command", {
        tool_name: toolName ?? null,
      })) ?? []
    } catch {
      history.value = []
    } finally {
      loading.value = false
    }
  }

  return {
    history,
    loading,
    loadHistory,
  }
}
