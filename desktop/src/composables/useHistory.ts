import { ref } from "vue"
import { invoke } from "@tauri-apps/api/core"
import { isTauriEnv } from "../utils/tauri"
import type { ExecutionRecord } from "../types"

export type { ExecutionRecord }

export function useHistory() {
  const history = ref<ExecutionRecord[]>([])
  const loading = ref(false)

  const loadHistory = async (toolName?: string): Promise<void> => {
    if (!isTauriEnv()) {
      history.value = []
      return
    }

    loading.value = true
    try {
      history.value =
        (await invoke<ExecutionRecord[]>("get_execution_history_command", {
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
