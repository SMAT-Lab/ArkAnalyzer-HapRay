import { ref } from "vue"
import { invoke } from "@tauri-apps/api/core"
import { isTauriEnv } from "../utils/tauri"
import type {
  PluginMetadata,
  SidebarMenu,
  LoadPluginsResult,
} from "../types"

const MOCK_MENU: SidebarMenu[] = [
  {
    category: "应用分析",
    icon: "🔍",
    order: 2,
    items: [
      {
        plugin_id: "opt",
        action: "opt",
        display_name: "优化检测",
        icon: "⚡",
        order: 1,
        menu_category: "应用分析",
      },
      {
        plugin_id: "sa",
        action: "static",
        display_name: "静态分析",
        icon: "📱",
        order: 2,
        menu_category: "应用分析",
      },
    ],
  },
]

const BROWSER_MODE_LOG = [
  "[INFO] 当前为浏览器模式，未连接 Tauri 后端",
  "[INFO] 请使用 npm run tauri dev 或运行打包后的应用以加载真实插件",
]

const plugins = ref<PluginMetadata[]>([])
const sidebarMenu = ref<SidebarMenu[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const loadLog = ref<string[]>([])

export function usePlugins() {
  const loadPlugins = async (): Promise<void> => {
    if (!isTauriEnv()) {
      loadLog.value = BROWSER_MODE_LOG
      sidebarMenu.value = MOCK_MENU
      plugins.value = []
      return
    }

    loading.value = true
    error.value = null
    loadLog.value = []

    try {
      const result = await invoke<LoadPluginsResult>("load_plugins_command")
      plugins.value = result.plugins
      sidebarMenu.value = result.menu
      loadLog.value = result.load_log ?? []
    } catch (e) {
      const message = String(e)
      error.value = message
      plugins.value = []
      sidebarMenu.value = []
      loadLog.value = [message]
    } finally {
      loading.value = false
    }
  }

  const getPlugin = (pluginId: string): PluginMetadata | undefined =>
    plugins.value.find((p) => p.id === pluginId)

  return {
    plugins,
    sidebarMenu,
    loading,
    error,
    loadLog,
    loadPlugins,
    getPlugin,
  }
}
