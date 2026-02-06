<template>
  <div class="summary-overview-container">
      <div class="summary-header">
        <h2>分析总结</h2>
        <p class="summary-desc">
          汇总各步骤的关键故障类信息，包括组件复用、故障树识别结果、Image 超尺寸统计以及组件树上/未上树节点情况。
        </p>
      </div>

      <!-- 步骤导航 -->
      <div v-if="summaryItems.length" class="step-nav">
        <span class="step-nav-label">步骤导航：</span>
        <el-button
          v-for="item in summaryItems"
          :key="item.step_id"
          size="small"
          round
          @click="scrollToStep(getStepIndex(item.step_id) as number)"
        >
          步骤 {{ getStepIndex(item.step_id) }}
        </el-button>
      </div>

      <!-- 无数据提示 -->
      <el-empty
        v-if="!summaryItems.length"
        description="当前报告未包含分析总结数据，请确认使用最新版本的 hapray 生成报告。"
        class="summary-empty"
      />

      <!-- 每个步骤的详细总结 -->
      <div
        v-for="item in summaryItems"
        :key="item.step_id"
        class="step-card"
        :id="'summary-step-' + getStepIndex(item.step_id)"
      >
        <div class="step-card-header">
          <div class="step-title">
            <span class="step-tag">步骤 {{ getStepIndex(item.step_id) }}</span>
            <span class="step-name">{{ getStepName(item.step_id) }}</span>
          </div>
          <div class="step-actions">
            <el-button
              text
              type="primary"
              size="small"
              @click="toggleCollapsed(item.step_id)"
            >
              {{ isCollapsed(item.step_id) ? '展开' : '折叠' }}
            </el-button>
          </div>
        </div>

        <div v-show="!isCollapsed(item.step_id)">
        <el-row :gutter="20">
          <!-- 组件复用 -->
          <el-col :span="6" v-if="item.component_reuse">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">组件复用</span>
              </h3>
              <el-descriptions :column="1" size="small">
                <el-descriptions-item label="总构建次数">
                  {{ formatNumber(item.component_reuse.total_builds ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="复用构建次数">
                  {{ formatNumber(item.component_reuse.recycled_builds ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="复用率">
                  {{ formatPercentage(item.component_reuse.reusability_ratio) }}
                </el-descriptions-item>
                <el-descriptions-item v-if="item.component_reuse.max_component" label="复用热点组件">
                  {{ item.component_reuse.max_component }}
                </el-descriptions-item>
              </el-descriptions>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('frame_step', getStepIndex(item.step_id) as number)"
                >
                  查看帧分析详情
                </el-button>
              </div>
            </div>
          </el-col>

          <!-- 空刷帧概要 -->
          <el-col :span="6" v-if="item.empty_frame">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag subtle">空刷帧</span>
              </h3>
              <el-descriptions :column="1" size="small">
                <el-descriptions-item label="空刷帧数">
                  {{ formatNumber(item.empty_frame.count ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="空刷帧占比">
                  {{ item.empty_frame.percentage ?? '0.00%' }}
                </el-descriptions-item>
              </el-descriptions>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('frame_step', getStepIndex(item.step_id) as number)"
                >
                  查看帧分析详情
                </el-button>
              </div>
            </div>
          </el-col>

          <!-- 技术栈占比 -->
          <el-col :span="6" v-if="item.tech_stack">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag info">技术栈负载</span>
              </h3>
              <el-descriptions :column="1" size="small">
                <el-descriptions-item
                  v-for="(value, key) in item.tech_stack || {}"
                  :key="key"
                  :label="key"
                >
                  {{ formatNumber(value as number) }}
                </el-descriptions-item>
              </el-descriptions>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('perf_step', getStepIndex(item.step_id) as number)"
                >
                  查看负载分析详情
                </el-button>
              </div>
            </div>
          </el-col>

          <!-- Image 超尺寸 -->
          <el-col :span="6" v-if="item.image_oversize">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag warning">Image 超尺寸</span>
              </h3>
              <el-descriptions :column="1" size="small">
                <el-descriptions-item label="总 Image 数量">
                  {{ formatNumber(item.image_oversize.total_images ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="超尺寸数量">
                  {{ formatNumber(item.image_oversize.exceed_count ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="额外内存 (MB)">
                  {{ (item.image_oversize.total_excess_memory_mb ?? 0).toFixed(2) }}
                </el-descriptions-item>
              </el-descriptions>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('ui_animate_step', getStepIndex(item.step_id) as number)"
                >
                  查看 UI 分析详情
                </el-button>
              </div>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-top: 12px">
          <!-- 组件树上/未上树 -->
          <el-col :span="8" v-if="item.component_tree">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag info">组件树上/未上树</span>
              </h3>
              <el-descriptions :column="2" size="small">
                <el-descriptions-item label="总节点数">
                  {{ formatNumber(item.component_tree.total_nodes ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="上树节点数">
                  {{ formatNumber(item.component_tree.on_tree_nodes ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="未上树节点数">
                  {{ formatNumber(item.component_tree.off_tree_nodes ?? 0) }}
                </el-descriptions-item>
                <el-descriptions-item label="未上树占比">
                  {{ formatPercentage(item.component_tree.off_tree_ratio) }}
                </el-descriptions-item>
              </el-descriptions>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('ui_animate_step', getStepIndex(item.step_id) as number)"
                >
                  查看 UI 分析详情
                </el-button>
              </div>
            </div>
          </el-col>

          <!-- 故障树 -->
          <el-col :span="8" v-if="item.fault_tree">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag danger">故障树</span>
              </h3>
              <div class="fault-items">
                <div
                  v-for="fault in getFaultItems(item.fault_tree)"
                  :key="fault.label"
                  class="fault-item"
                  :class="'fault-' + fault.severity"
                >
                  <span class="fault-label">{{ fault.label }}</span>
                  <span class="fault-value">{{ fault.value }}</span>
                </div>
              </div>
              <p v-if="!getFaultItems(item.fault_tree).length" class="panel-empty">
                当前步骤未检测到明显故障。
              </p>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('fault_tree_step', getStepIndex(item.step_id) as number)"
                >
                  查看故障树分析详情
                </el-button>
              </div>
            </div>
          </el-col>

          <!-- Hilog / 日志模式统计 -->
          <el-col :span="8" v-if="item.log && Object.keys(item.log).length">
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag subtle">日志模式汇总</span>
              </h3>
              <el-descriptions :column="1" size="small">
                <el-descriptions-item
                  v-for="(value, key) in getLogSummary(item.log)"
                  :key="key"
                  :label="String(key)"
                >
                  {{ String(value) }}
                </el-descriptions-item>
              </el-descriptions>
              <div class="panel-actions">
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="gotoPage('hilog_step', getStepIndex(item.step_id) as number)"
                >
                  查看日志分析详情
                </el-button>
              </div>
            </div>
          </el-col>
        </el-row>
        </div>
      </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useJsonDataStore } from '@/stores/jsonDataStore.ts';

interface SummaryItem {
  step_id: string;
  report_html_path?: string;
  empty_frame?: {
    count?: number;
    percentage?: string;
  };
  tech_stack?: Record<string, number>;
  log?: Record<string, unknown>;
  component_reuse?: {
    total_builds?: number;
    recycled_builds?: number;
    reusability_ratio?: number;
    max_component?: string;
  };
  fault_tree?: Record<string, unknown>;
  image_oversize?: {
    total_images?: number;
    exceed_count?: number;
    total_excess_memory_mb?: number;
  };
  component_tree?: {
    total_nodes?: number;
    on_tree_nodes?: number;
    off_tree_nodes?: number;
    off_tree_ratio?: number;
  };
}

const jsonDataStore = useJsonDataStore();

const summaryItems = computed<SummaryItem[]>(() => (jsonDataStore.summary ?? []) as SummaryItem[]);

const collapsedSteps = ref<Record<string, boolean>>({});

const emit = defineEmits<{
  pageChange: [page: string];
}>();

const stepNameMap = computed(() => {
  const map: Record<string, string> = {};
  const steps = jsonDataStore.steps || [];
  steps.forEach((step) => {
    const key = `step${step.step_id}`;
    map[key] = step.step_name;
  });
  return map;
});

const formatNumber = (num: number) => num.toLocaleString();

const formatPercentage = (value?: number) => {
  if (value == null || Number.isNaN(value)) {
    return '0.00%';
  }
  return `${(value * 100).toFixed(2)}%`;
};

const getStepIndex = (stepId: string) => {
  const match = stepId.match(/step(\d+)/);
  return match ? Number(match[1]) : stepId;
};

const getStepName = (stepId: string) => {
  return stepNameMap.value[stepId] ?? stepId;
};

const isCollapsed = (stepId: string) => !!collapsedSteps.value[stepId];

const toggleCollapsed = (stepId: string) => {
  collapsedSteps.value[stepId] = !collapsedSteps.value[stepId];
};

const scrollToStep = (stepIndex: number) => {
  const el = document.getElementById(`summary-step-${stepIndex}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
};

const gotoPage = (pagePrefix: string, stepIndex: number) => {
  const pageId = `${pagePrefix}_${stepIndex}`;
  emit('pageChange', pageId);
};

// 获取日志统计（排除 _detail 内部数据）
const getLogSummary = (log?: Record<string, unknown>) => {
  if (!log || typeof log !== 'object') return {};
  return Object.fromEntries(Object.entries(log).filter(([k]) => k !== '_detail'));
};

// 故障树阈值（与 FaultTreeAnalysis.vue 保持一致）
const FAULT_THRESHOLDS: Array<{
  path: string[];
  label: string;
  threshold: number;
  format?: (v: number) => string;
}> = [
  { path: ['arkui', 'animator'], label: '帧动画数量', threshold: 50 },
  { path: ['arkui', 'HandleOnAreaChangeEvent'], label: '区域变化监听', threshold: 1000 },
  { path: ['arkui', 'HandleVisibleAreaChangeEvent'], label: '可见区域变化', threshold: 1000 },
  { path: ['arkui', 'GetDefaultDisplay'], label: '屏幕宽高获取', threshold: 100 },
  { path: ['arkui', 'MarshRSTransactionData'], label: '事务数据序列化', threshold: 3000 },
  { path: ['RS', 'ProcessedNodes', 'count'], label: '处理节点数', threshold: 200 },
  { path: ['RS', 'ProcessedNodes', 'ts'], label: '处理时间(s)', threshold: 5, format: (v) => v.toFixed(3) },
  { path: ['RS', 'DisplayNodeSkipTimes'], label: '跳过次数', threshold: 10 },
  { path: ['RS', 'UnMarshRSTransactionData'], label: '反序列化数量', threshold: 60 },
  { path: ['RS', 'AnimateSize', 'nodeSizeSum'], label: '动画节点总大小', threshold: 1000 },
  { path: ['RS', 'AnimateSize', 'totalAnimationSizeSum'], label: '动画总大小', threshold: 2000 },
  { path: ['av_codec', 'BroadcastControlInstructions'], label: '播控指令数', threshold: 1000000 },
  { path: ['av_codec', 'VideoDecodingInputFrameCount'], label: '视频解码输入帧', threshold: 300 },
  { path: ['av_codec', 'VideoDecodingConsumptionFrame'], label: '视频解码消费帧', threshold: 250 },
  { path: ['Audio', 'AudioWriteCB'], label: '音频写回调', threshold: 5000000 },
  { path: ['Audio', 'AudioReadCB'], label: '音频读回调', threshold: 1000000 },
  { path: ['Audio', 'AudioPlayCb'], label: '音频播放回调', threshold: 1000000 },
  { path: ['Audio', 'AudioRecCb'], label: '音频录制回调', threshold: 1000000 },
  { path: ['ipc_binder', 'total_transactions'], label: 'IPC 总通信次数', threshold: 10000 },
  { path: ['ipc_binder', 'high_latency_count'], label: 'IPC 高延迟次数', threshold: 10 },
  { path: ['ipc_binder', 'avg_latency'], label: 'IPC 平均延迟(ms)', threshold: 50, format: (v) => v.toFixed(2) },
  { path: ['ipc_binder', 'max_latency'], label: 'IPC 最大延迟(ms)', threshold: 100, format: (v) => v.toFixed(2) },
];

const formatFaultValue = (v: number): string => {
  if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
  if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
  return v.toLocaleString();
};

const getNested = (obj: any, path: string[]): unknown => {
  let cur = obj;
  for (const p of path) {
    if (cur == null) return undefined;
    cur = cur[p];
  }
  return cur;
};

// 提取有明显问题的关键数据（超过阈值的指标，并展示数值）
const getFaultItems = (faultTree?: Record<string, unknown>) => {
  if (!faultTree) return [] as { label: string; value: string; severity: 'critical' | 'warning' }[];

  const items: { label: string; value: string; severity: 'critical' | 'warning' }[] = [];
  const ft = faultTree as any;

  // 软解码：布尔值单独处理
  const avCodec = ft.av_codec;
  if (avCodec && avCodec.soft_decoder === true) {
    items.push({ label: '使用软解码', value: '是', severity: 'warning' });
  }

  for (const { path, label, threshold, format } of FAULT_THRESHOLDS) {
    const raw = getNested(ft, path);
    if (typeof raw !== 'number') continue;
    if (raw <= threshold) continue;

    const valueStr = format ? format(raw) : formatFaultValue(raw);
    const severity = raw > threshold * 2 ? 'critical' : 'warning';
    items.push({ label, value: valueStr, severity });
  }

  return items;
};
</script>

<style scoped>
.summary-overview-container {
  padding: 20px;
  background: #f5f7fa;
}

.summary-header {
  margin-bottom: 20px;
}

.summary-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.summary-desc {
  margin: 0;
  color: #606266;
  font-size: 14px;
}

.step-nav {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.step-nav-label {
  font-size: 13px;
  color: #606266;
}

.step-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 18px;
}

.step-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.step-tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4c6fff;
  font-size: 12px;
  font-weight: 600;
}

.step-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.data-panel {
  background: #fafafa;
  border-radius: 10px;
  padding: 16px;
  border: 1px solid #ebeef5;
  height: 100%;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.version-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 500;
}

.version-tag.danger {
  background: linear-gradient(135deg, #f56c6c 0%, #f78989 100%);
}

.version-tag.warning {
  background: linear-gradient(135deg, #e6a23c 0%, #f3d19e 100%);
}

.version-tag.info {
  background: linear-gradient(135deg, #409eff 0%, #79bbff 100%);
}

.version-tag.subtle {
  background: linear-gradient(135deg, #909399 0%, #c0c4cc 100%);
}

.fault-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fault-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
}

.fault-item.fault-warning {
  background: rgba(230, 162, 60, 0.12);
  border-left: 3px solid #e6a23c;
}

.fault-item.fault-critical {
  background: rgba(245, 108, 108, 0.12);
  border-left: 3px solid #f56c6c;
}

.fault-label {
  color: #606266;
}

.fault-value {
  font-weight: 600;
  color: #303133;
}

.fault-critical .fault-value {
  color: #f56c6c;
}

.fault-warning .fault-value {
  color: #e6a23c;
}

.panel-empty {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.panel-actions {
  margin-top: 8px;
  text-align: right;
}

.summary-empty {
  margin-top: 40px;
}

@media (max-width: 768px) {
  .summary-overview-container {
    padding: 16px;
  }

  .step-card {
    padding: 16px;
  }
}
</style>

