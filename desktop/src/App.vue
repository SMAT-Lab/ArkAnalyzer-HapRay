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
          <WelcomeView
            :loading="loading"
            :error="error"
          />
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
import Titlebar from "./components/Titlebar.vue"
import Sidebar from "./components/Sidebar.vue"
import ToolWorkspace from "./components/ToolWorkspace.vue"
import SettingsView from "./components/SettingsView.vue"
import HistorySidebar from "./components/HistorySidebar.vue"
import HistoryView from "./components/HistoryView.vue"
import WelcomeView from "./components/WelcomeView.vue"
import type { ExecutionRecord } from "./types"
import { usePlugins } from "./composables/usePlugins"
import { useSidebarResize } from "./composables/useSidebarResize"

const { sidebarMenu, loading, error, loadPlugins, getPlugin } = usePlugins()
const { sidebarWidth, onResizeStart } = useSidebarResize()

const sidebarOpen = ref(true)
const historySidebarOpen = ref(true)
const page = ref<"home" | "settings" | "tool">("home")
const selectedTool = ref<{ pluginId: string; action: string } | null>(null)
const historyRefreshKey = ref(0)
const selectedHistoryRecord = ref<ExecutionRecord | null>(null)
const cliInitialParams = ref<Record<string, unknown> | null>(null)

onMounted(loadPlugins)

function openSettings(): void {
  page.value = "settings"
}

function onExecutionFinished(): void {
  historyRefreshKey.value++
  selectedHistoryRecord.value = null
  cliInitialParams.value = null
}

function onNavigate(payload: {
  page: "home" | "settings" | "tool"
  pluginId?: string
  action?: string
}): void {
  page.value = payload.page
  selectedHistoryRecord.value = null

  if (payload.page === "tool" && payload.pluginId && payload.action) {
    selectedTool.value = { pluginId: payload.pluginId, action: payload.action }
  } else {
    selectedTool.value = null
    cliInitialParams.value = null
  }
}
</script>
