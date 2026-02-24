<template>
  <div class="history-view">
    <!-- 模式：仅详情（record 由外部传入，用于主内容区展示） -->
    <template v-if="record">
      <header class="history-view__header history-view__header--detail">
        <h1 class="history-view__title">执行记录详情</h1>
      </header>
      <div class="history-view__detail-content history-view__detail-content--standalone">
        <div v-if="record.command" class="history-view__section">
          <h3 class="history-view__label">执行命令</h3>
          <pre class="history-view__pre">{{ record.command }}</pre>
        </div>
        <div v-if="record.output_path" class="history-view__section">
          <h3 class="history-view__label">输出路径</h3>
          <p class="history-view__path">{{ record.output_path }}</p>
          <button
            type="button"
            class="history-view__btn history-view__btn--primary"
            @click="openPath(record.output_path as string)"
          >
            打开输出路径
          </button>
        </div>
        <div v-if="record.result_dir" class="history-view__section">
          <h3 class="history-view__label">记录目录</h3>
          <button
            type="button"
            class="history-view__btn history-view__btn--secondary"
            @click="openPath(record.result_dir as string)"
          >
            打开记录目录
          </button>
        </div>
        <div v-if="record.output" class="history-view__section">
          <h3 class="history-view__label">执行日志</h3>
          <pre class="history-view__pre history-view__output">{{ record.output }}</pre>
        </div>
      </div>
    </template>

    <!-- 模式：完整页面（列表 + 详情） -->
    <template v-else>
      <header class="history-view__header">
        <h1 class="history-view__title">执行记录</h1>
        <button
          type="button"
          class="history-view__refresh"
          :disabled="loading"
          @click="loadHistory()"
        >
          {{ loading ? "..." : "刷新" }}
        </button>
      </header>
      <div class="history-view__body">
        <aside class="history-view__list">
          <template v-if="loading && history.length === 0">
            <div class="history-view__empty">加载中...</div>
          </template>
          <template v-else-if="history.length === 0">
            <div class="history-view__empty">暂无执行记录</div>
          </template>
          <template v-else>
            <div
              v-for="(item, idx) in history"
              :key="`${item.plugin_id}-${item.timestamp}-${idx}`"
              class="history-view__item"
              :class="{
                'history-view__item--success': item.success,
                'history-view__item--fail': !item.success,
                'history-view__item--selected':
                  selectedRecord?.plugin_id === item.plugin_id &&
                  selectedRecord?.timestamp === item.timestamp,
              }"
              role="button"
              tabindex="0"
              @click="selectedRecord = item"
              @keydown.enter="selectedRecord = item"
            >
              <div class="history-view__item-header">
                <span class="history-view__item-icon">{{ item.success ? "✓" : "✗" }}</span>
                <span class="history-view__item-name">{{ item.tool_name || item.plugin_id || "未知" }}</span>
              </div>
              <div class="history-view__item-meta">
                <span class="history-view__item-action">{{ item.action_name || item.action || "" }}</span>
                <span class="history-view__item-time">{{ formatTimestamp(item.timestamp) }}</span>
              </div>
              <p v-if="item.message" class="history-view__item-msg">{{ item.message }}</p>
            </div>
          </template>
        </aside>
        <section v-if="selectedRecord" class="history-view__detail">
          <h2 class="history-view__detail-title">执行记录详情</h2>
          <div class="history-view__detail-content">
            <div v-if="selectedRecord.command" class="history-view__section">
              <h3 class="history-view__label">执行命令</h3>
              <pre class="history-view__pre">{{ selectedRecord.command }}</pre>
            </div>
            <div v-if="selectedRecord.output_path" class="history-view__section">
              <h3 class="history-view__label">输出路径</h3>
              <p class="history-view__path">{{ selectedRecord.output_path }}</p>
              <button
                type="button"
                class="history-view__btn history-view__btn--primary"
                @click="openPath(selectedRecord.output_path as string)"
              >
                打开输出路径
              </button>
            </div>
            <div v-if="selectedRecord.result_dir" class="history-view__section">
              <h3 class="history-view__label">记录目录</h3>
              <button
                type="button"
                class="history-view__btn history-view__btn--secondary"
                @click="openPath(selectedRecord.result_dir as string)"
              >
                打开记录目录
              </button>
            </div>
            <div v-if="selectedRecord.output" class="history-view__section">
              <h3 class="history-view__label">执行日志</h3>
              <pre class="history-view__pre history-view__output">{{ selectedRecord.output }}</pre>
            </div>
          </div>
        </section>
        <div v-else class="history-view__placeholder">
          <p class="history-view__placeholder-text">点击左侧记录查看详情</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useHistory } from "../composables/useHistory"
import type { ExecutionRecord } from "../types"
import { formatTimestamp } from "../utils/format"
import { openPath } from "../utils/tauri"

const props = defineProps<{ record?: ExecutionRecord | null }>()

const { history, loading, loadHistory } = useHistory()
const selectedRecord = ref<ExecutionRecord | null>(null)

onMounted(() => {
  if (!props.record) {
    loadHistory()
  }
})
</script>
