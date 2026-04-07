import { ref } from "vue"

export interface ToolState {
  formData: Record<string, unknown>
  output: string
  nargsInputTemp: Record<string, string | number>
  choiceMultiTemp: Record<string, string>
  dynamicChoicesCache: Record<string, string[]>
  outputPanelVisible: boolean
}

const toolStateCache = ref<Record<string, ToolState>>({})

export function toolKey(pluginId: string, action: string): string {
  return `${pluginId}-${action}`
}

export function useToolStateCache() {
  function save(key: string, state: ToolState) {
    toolStateCache.value[key] = {
      formData: { ...state.formData },
      output: state.output,
      nargsInputTemp: { ...state.nargsInputTemp },
      choiceMultiTemp: { ...state.choiceMultiTemp },
      dynamicChoicesCache: { ...state.dynamicChoicesCache },
      outputPanelVisible: state.outputPanelVisible,
    }
  }

  function load(key: string): ToolState | null {
    return toolStateCache.value[key] ?? null
  }

  function updateOutput(key: string, output: string) {
    const cur = toolStateCache.value[key]
    if (cur) {
      toolStateCache.value[key] = { ...cur, output }
    }
  }

  return {
    toolStateCache,
    save,
    load,
    updateOutput,
  }
}
