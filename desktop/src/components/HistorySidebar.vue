<template>
  <aside class="history-sidebar shrink-0 border-l border-border bg-sidebar flex flex-col overflow-hidden" :style="{ width: `${width}px` }">
    <div class="history-sidebar__header">
      <h2 class="history-sidebar__title">执行记录</h2>
      <button
        type="button"
        class="history-sidebar__refresh"
        :disabled="loading"
        @click="() => loadHistory()"
      >
        {{ loading ? "..." : "刷新" }}
      </button>
    </div>
    <div class="history-sidebar__list flex-1 min-h-0 overflow-y-auto">
      <template v-if="loading && history.length === 0">
        <div class="history-sidebar__empty">加载中...</div>
      </template>
      <template v-else-if="history.length === 0">
        <div class="history-sidebar__empty">暂无执行记录</div>
      </template>
      <template v-else>
        <div
          v-for="(record, idx) in sortedHistory"
          :key="`${record.plugin_id}-${record.timestamp}-${idx}`"
          class="history-sidebar__item"
          :class="{
            'history-sidebar__item--success': record.success,
            'history-sidebar__item--fail': !record.success,
            'history-sidebar__item--selected': localSelectedRecord?.plugin_id === record.plugin_id && localSelectedRecord?.timestamp === record.timestamp,
          }"
          role="button"
          tabindex="0"
          @click="selectRecord(record)"
          @keydown.enter="selectRecord(record)"
        >
          <div class="history-sidebar__item-header">
            <span class="history-sidebar__item-icon">{{ record.success ? "✓" : "✗" }}</span>
            <span class="history-sidebar__item-name">{{ record.tool_name || record.plugin_id || "未知" }}</span>
          </div>
          <div class="history-sidebar__item-meta">
            <span class="history-sidebar__item-action">{{ record.action_name || record.action || "" }}</span>
            <span class="history-sidebar__item-time">{{ formatTimestamp(record.timestamp) }}</span>
          </div>
          <p v-if="record.message" class="history-sidebar__item-msg">{{ record.message }}</p>
        </div>
      </template>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue"
import { useHistory } from "../composables/useHistory"
import type { ExecutionRecord } from "../types"
import { formatTimestamp } from "../utils/format"

const props = withDefaults(
  defineProps<{
    width?: number
    toolName?: string | null
    refreshKey?: number
    selectedRecord?: { plugin_id?: string; timestamp?: string } | null
  }>(),
  { width: 280, toolName: null, refreshKey: 0, selectedRecord: null }
)

const emit = defineEmits<{
  select: [record: ExecutionRecord]
}>()

const { history, loading, loadHistory } = useHistory()
const localSelectedRecord = ref<ExecutionRecord | null>(null)

const sortedHistory = computed(() =>
  [...history.value].sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? ""))
)

function selectRecord(record: ExecutionRecord) {
  localSelectedRecord.value = record
  emit("select", record)
}

onMounted(() => {
  loadHistory(props.toolName ?? undefined)
})

watch(
  () => [props.toolName, props.refreshKey],
  () => {
    loadHistory(props.toolName ?? undefined)
  }
)

watch(
  () => props.selectedRecord,
  (v) => {
    localSelectedRecord.value = v ?? null
  },
  { immediate: true }
)
</script>
