<template>
  <div class="hilog-analysis-container">
    <div class="hilog-header">
      <h2>日志分析</h2>
      <p class="hilog-desc">展示 hilog 规则匹配统计及详细匹配内容，包含各规则匹配项与未匹配任何规则的「其他」项。</p>
    </div>

    <el-empty
      v-if="!hasLogData"
      description="当前步骤暂无日志分析数据，请确认使用最新版本 hapray 生成报告并启用 hilog 分析。"
      class="hilog-empty"
    />

    <template v-else>
      <!-- 规则统计概览 -->
      <div class="stats-section">
        <h3 class="section-title">规则匹配统计</h3>
        <div class="stats-cards">
          <div
            v-for="(count, ruleName) in logSummary"
            :key="ruleName"
            class="stat-card"
          >
            <span class="stat-label">{{ ruleName }}</span>
            <span class="stat-value">{{ count }}</span>
          </div>
        </div>
      </div>

      <!-- 详情：各规则 matched + 其他（仅当有 _detail 时显示） -->
      <div v-if="hasDetailData" class="detail-section">
        <h3 class="section-title">匹配详情</h3>
        <el-collapse v-model="activeDetailKeys">
          <el-collapse-item
            v-for="(data, ruleName) in logDetail"
            :key="ruleName"
            :name="ruleName"
          >
            <template #title>
              <span class="collapse-title">
                <span class="rule-name">{{ ruleName }}</span>
                <span class="rule-count">({{ getDetailCount(data) }} 条)</span>
              </span>
            </template>
            <div class="detail-content">
              <div
                v-for="(item, idx) in getDetailItems(data)"
                :key="idx"
                class="log-line"
              >
                <code>{{ item }}</code>
              </div>
              <p v-if="!getDetailItems(data).length" class="detail-empty">无匹配项</p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useJsonDataStore } from '@/stores/jsonDataStore.ts';

const props = defineProps<{
  stepId: number;
}>();

const jsonDataStore = useJsonDataStore();

// 获取当前步骤的 log 数据
const stepLogData = computed(() => {
  const summary = jsonDataStore.summary as Array<{ step_id?: string; log?: Record<string, unknown> }> | undefined;
  if (!summary || !Array.isArray(summary)) return null;
  const getStepIndex = (stepIdStr: string) => {
    const match = String(stepIdStr).match(/step(\d+)/);
    return match ? Number(match[1]) : null;
  };
  const item = summary.find((s) => getStepIndex(s.step_id ?? '') === props.stepId);
  return item?.log ?? null;
});

const hasLogData = computed(() => {
  const log = stepLogData.value;
  return !!(log && Object.keys(log).length > 0);
});

// 统计概览：排除 _detail，只显示规则名 -> 数量
const logSummary = computed(() => {
  const log = stepLogData.value;
  if (!log) return {};
  const result: Record<string, number> = {};
  for (const [key, value] of Object.entries(log)) {
    if (key === '_detail') continue;
    result[key] = typeof value === 'number' ? value : Number(value) || 0;
  }
  return result;
});

// 详情数据：来自 _detail
const logDetail = computed(() => {
  const log = stepLogData.value;
  const detail = log && typeof log === 'object' && '_detail' in log ? (log as { _detail?: Record<string, { matched?: string[] } | string[]> })._detail : null;
  if (!detail || typeof detail !== 'object') return {};
  return detail as Record<string, { matched?: string[] } | string[]>;
});

const hasDetailData = computed(() => Object.keys(logDetail.value).length > 0);

// 默认展开第一个详情
const activeDetailKeys = ref<string[]>([]);

// 获取某规则的详情条数
const getDetailCount = (data: { matched?: string[] } | string[]): number => {
  if (Array.isArray(data)) return data.length;
  return (data.matched ?? []).length;
};

// 获取某规则的详情列表
const getDetailItems = (data: { matched?: string[] } | string[]): string[] => {
  if (Array.isArray(data)) return data;
  return data.matched ?? [];
};
</script>

<style scoped>
.hilog-analysis-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 400px;
}

.hilog-header {
  margin-bottom: 24px;
}

.hilog-header h2 {
  margin: 0 0 8px 0;
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.hilog-desc {
  margin: 0;
  font-size: 14px;
  color: #606266;
}

.hilog-empty {
  margin-top: 60px;
}

.stats-section,
.detail-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.stats-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 120px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 10px;
  border: 1px solid #e4e7ed;
}

.stat-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 4px;
  text-align: center;
  word-break: break-all;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-name {
  font-weight: 500;
  color: #303133;
}

.rule-count {
  font-size: 13px;
  color: #909399;
}

.detail-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px 0;
}

.log-line {
  padding: 6px 12px;
  margin-bottom: 4px;
  background: #fafafa;
  border-radius: 6px;
  border-left: 3px solid #667eea;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  word-break: break-all;
}

.log-line code {
  color: #303133;
  background: transparent;
  padding: 0;
}

.detail-empty {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

:deep(.el-collapse-item__header) {
  font-size: 14px;
}

:deep(.el-collapse-item__content) {
  padding-bottom: 12px;
}
</style>
