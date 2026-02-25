/**
 * 共享类型定义
 */

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

/** 全局配置单项描述（用于设置页「通用」表单） */
export interface GeneralConfigItemDef {
  key: string
  type: "str" | "dir" | "choice"
  label: string
  help?: string
  placeholder?: string
  default?: string
  choices?: string[]
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

export type PageType = "home" | "settings" | "tool"

export interface NavigatePayload {
  page: PageType
  pluginId?: string
  action?: string
}
