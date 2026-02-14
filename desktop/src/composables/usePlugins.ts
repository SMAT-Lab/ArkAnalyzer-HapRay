import { ref } from "vue"
import { invoke } from "@tauri-apps/api/core"

export interface MenuItem {
  plugin_id: string
  action: string
  display_name: string
  icon: string
  order: number
  menu_category: string
}

export interface SidebarMenu {
  category: string
  icon: string
  order: number
  items: MenuItem[]
}

export interface ParameterDef {
  type: string
  label: string
  required?: boolean
  default?: unknown
  choices?: unknown
  multi_select?: boolean
  help?: string
  nargs?: string
}

export interface ActionConfig {
  name: string
  description?: string
  menu?: { menu1?: string; menu2?: string; order?: number; icon?: string }
  parameters?: Record<string, ParameterDef>
}

export interface ConfigItemDef {
  type: string
  label: string
  default?: unknown
  help?: string
  choices?: unknown
  required?: boolean
}

export interface ConfigSchema {
  description?: string
  items?: Record<string, ConfigItemDef>
}

export interface PluginMetadata {
  id: string
  name: string
  description: string
  version: string
  actions?: Record<string, ActionConfig>
  config?: ConfigSchema
}

export interface LoadPluginsResult {
  plugins: PluginMetadata[]
  menu: SidebarMenu[]
  load_log?: string[]
}

const plugins = ref<PluginMetadata[]>([])
const sidebarMenu = ref<SidebarMenu[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const loadLog = ref<string[]>([])

export function usePlugins() {
  const loadPlugins = async () => {
    if (!(window as { __TAURI__?: unknown }).__TAURI__) {
      // 非 Tauri 环境，使用 mock 数据
      loadLog.value = [
        "[INFO] 当前为浏览器模式，未连接 Tauri 后端",
        "[INFO] 请使用 npm run tauri dev 或运行打包后的应用以加载真实插件",
      ]
      sidebarMenu.value = [
        {
          category: "应用分析",
          icon: "🔍",
          order: 2,
          items: [
            { plugin_id: "opt", action: "opt", display_name: "优化检测", icon: "⚡", order: 1, menu_category: "应用分析" },
            { plugin_id: "sa", action: "static", display_name: "静态分析", icon: "📱", order: 2, menu_category: "应用分析" },
          ],
        },
      ]
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
      error.value = String(e)
      plugins.value = []
      sidebarMenu.value = []
      loadLog.value = [String(e)]
    } finally {
      loading.value = false
    }
  }

  const getPlugin = (pluginId: string) => plugins.value.find((p) => p.id === pluginId)

  return { plugins, sidebarMenu, loading, error, loadLog, loadPlugins, getPlugin }
}
