<template>
  <div class="flex flex-col h-dvh bg-background-base">
    <Titlebar
      :sidebar-open="sidebarOpen"
      :history-sidebar-open="historySidebarOpen"
      @toggle-sidebar="sidebarOpen = !sidebarOpen"
      @toggle-history-sidebar="historySidebarOpen = !historySidebarOpen"
      @open-settings="openSettings"
    />
    <div class="flex flex-1 overflow-hidden">
      <template v-if="sidebarOpen">
        <Sidebar
          :width="sidebarWidth"
          :sidebar-menu="sidebarMenu"
          :selected="selectedTool"
          :page="page"
          @navigate="onNavigate"
        />
        <div
          class="resize-handle shrink-0 cursor-col-resize"
          @mousedown="onResizeStart"
        />
      </template>
      <main class="flex-1 overflow-auto p-4 min-w-0">
        <template v-if="selectedHistoryRecord">
          <HistoryView :record="selectedHistoryRecord" />
        </template>
        <template v-else-if="page === 'settings'">
          <SettingsView />
        </template>
        <template v-else-if="page === 'tool' && selectedTool">
          <div class="tool-workspace-container">
            <ToolWorkspace
              :plugin="getPlugin(selectedTool.pluginId) ?? null"
              :action="selectedTool.action"
              :initial-params="cliInitialParams"
              @execution-finished="onExecutionFinished"
            />
          </div>
        </template>
        <template v-else>
          <div class="py-12 text-center">
            <h1 class="text-xl font-medium">欢迎使用 ArkAnalyzer-HapRay</h1>
            <p class="mt-2 text-muted-foreground">请从左侧选择工具开始使用</p>
            <p v-if="loading" class="mt-4 text-sm text-muted-foreground">正在加载插件...</p>
            <p v-else-if="error" class="mt-4 text-sm text-red-500">{{ error }}</p>
          </div>
        </template>
      </main>
      <template v-if="historySidebarOpen">
        <HistorySidebar
          :width="280"
          :tool-name="selectedTool?.pluginId ?? null"
          :refresh-key="historyRefreshKey"
          :selected-record="selectedHistoryRecord"
          @select="selectedHistoryRecord = $event"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { invoke } from "@tauri-apps/api/core"
import Titlebar from "./components/Titlebar.vue"
import Sidebar from "./components/Sidebar.vue"
import ToolWorkspace from "./components/ToolWorkspace.vue"
import SettingsView from "./components/SettingsView.vue"
import HistorySidebar from "./components/HistorySidebar.vue"
import HistoryView from "./components/HistoryView.vue"
import type { ExecutionRecord } from "./composables/useHistory"
import { usePlugins } from "./composables/usePlugins"
const { sidebarMenu, loading, error, loadPlugins, getPlugin } = usePlugins()

const MIN_WIDTH = 160
const sidebarOpen = ref(true)
const page = ref<"home" | "settings" | "tool">("home")
const selectedTool = ref<{ pluginId: string; action: string } | null>(null)
const MAX_WIDTH = 400
const DEFAULT_WIDTH = 220

const sidebarWidth = ref(DEFAULT_WIDTH)
const historySidebarOpen = ref(true)
const historyRefreshKey = ref(0)
const selectedHistoryRecord = ref<ExecutionRecord | null>(null)
/** 命令行传入的初始参数，用于自动执行 */
const cliInitialParams = ref<Record<string, unknown> | null>(null)

onMounted(async () => {
  await loadPlugins()
  try {
    const payload = await invoke<{ plugin_id: string; action: string; params: Record<string, unknown> } | null>(
      "get_pending_cli_run_command"
    )
    if (payload?.plugin_id && payload?.action) {
      onNavigate({ page: "tool", pluginId: payload.plugin_id, action: payload.action })
      cliInitialParams.value = payload.params ?? {}
    }
  } catch {
    // 非 Tauri 或命令不存在时忽略
  }
})

const openSettings = () => {
  page.value = "settings"
}

const onExecutionFinished = () => {
  historyRefreshKey.value++
  selectedHistoryRecord.value = null
  cliInitialParams.value = null
}

const onNavigate = (payload: { page: "home" | "settings" | "tool"; pluginId?: string; action?: string }) => {
  page.value = payload.page
  selectedHistoryRecord.value = null
  if (payload.page === "tool" && payload.pluginId && payload.action) {
    selectedTool.value = { pluginId: payload.pluginId, action: payload.action }
  } else {
    selectedTool.value = null
    cliInitialParams.value = null
  }
}

const onResizeStart = (e: MouseEvent) => {
  if (e.buttons !== 1) return
  e.preventDefault()

  const onMove = (move: MouseEvent) => {
    const next = sidebarWidth.value + move.movementX
    sidebarWidth.value = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next))
  }

  const onUp = () => {
    document.removeEventListener("mousemove", onMove)
    document.removeEventListener("mouseup", onUp)
    document.body.style.cursor = ""
    document.body.style.userSelect = ""
  }

  document.body.style.cursor = "col-resize"
  document.body.style.userSelect = "none"
  document.addEventListener("mousemove", onMove)
  document.addEventListener("mouseup", onUp)
}
</script>
