<template>
  <div class="summary-overview-container">
    <div class="summary-header">
      <div class="summary-title-row">
        <h2>分析总结</h2>
        <el-button
          v-if="hasDbtoolsExcel"
          type="primary"
          size="small"
          :icon="Download"
          @click="downloadDbtoolsExcel"
        >
          下载 instructions/cycles Excel
        </el-button>
      </div>
      <p class="summary-desc">
        汇总各步骤的关键故障类信息，包括组件复用、故障树识别结果、Image 超尺寸统计以及组件树上/未上树节点情况。
      </p>
    </div>

    <!-- 判断规则说明 -->
    <el-card class="rules-card" shadow="never">
      <template #header>
        <div class="rules-header">
          <span>📋 问题判断规则说明</span>
          <el-button text type="primary" size="small" @click="showRules = !showRules">
            {{ showRules ? '收起' : '展开' }}
          </el-button>
        </div>
      </template>
      <div v-show="showRules" class="rules-content">
        <div class="rule-item">
          <strong>空刷帧占比：</strong>
          <span>占比 &gt; 10% 时显示，&gt; 50% 为严重，10-50% 为中等</span>
        </div>

        <div class="rule-section">
          <strong class="rule-section-title">故障树指标：</strong>
          <div class="rule-subsection">
            <div class="rule-subtitle">判断规则：超过预设阈值时显示，超过阈值 2 倍为严重，否则为中等</div>
            
            <div class="rule-category">
              <strong>🎨 ArkUI 故障分析：</strong>
              <ul class="rule-list">
                <li>帧动画数量：阈值 50 个</li>
                <li>区域变化监听：阈值 1000 次</li>
                <li>可见区域变化监听：阈值 1000 次</li>
                <li>屏幕宽高获取：阈值 100 次</li>
                <li>事务数据序列化：阈值 3000 次</li>
                <li>软解码：检测到使用软解码器时显示（中等）</li>
              </ul>
            </div>

            <div class="rule-category">
              <strong>🖼️ RS 渲染服务故障分析：</strong>
              <ul class="rule-list">
                <li>处理节点数：阈值 200 个</li>
                <li>处理时间：阈值 5 秒</li>
                <li>节点跳过次数：阈值 10 次</li>
                <li>反序列化数量：阈值 60 次</li>
                <li>动画节点总大小：阈值 1000（单位：渲染服务内部单位）</li>
                <li>动画总大小：阈值 2000（单位：渲染服务内部单位）</li>
              </ul>
            </div>

            <div class="rule-category">
              <strong>🎬 音视频编解码故障分析：</strong>
              <ul class="rule-list">
                <li>播控指令数：阈值 1,000,000 次</li>
                <li>视频解码输入帧：阈值 300 帧</li>
                <li>视频解码消费帧：阈值 250 帧</li>
              </ul>
            </div>

            <div class="rule-category">
              <strong>🔊 音频故障分析：</strong>
              <ul class="rule-list">
                <li>音频写回调：阈值 5,000,000 次</li>
                <li>音频读回调：阈值 1,000,000 次</li>
                <li>音频播放回调：阈值 1,000,000 次</li>
                <li>音频录制回调：阈值 1,000,000 次</li>
              </ul>
            </div>

            <div class="rule-category">
              <strong>🔗 IPC Binder 进程间通信故障分析：</strong>
              <ul class="rule-list">
                <li>总通信次数：阈值 10,000 次</li>
                <li>高延迟通信次数：阈值 10 次</li>
                <li>平均延迟：阈值 50 ms</li>
                <li>最大延迟：阈值 100 ms</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="rule-item">
          <strong>Image 超尺寸：</strong>
          <span>超尺寸数量 &gt; 0 或额外内存 &gt; 10MB 时显示，额外内存 &gt; 50MB 为严重，否则为中等</span>
        </div>
        <div class="rule-item">
          <strong>组件未上树：</strong>
          <span>未上树占比 &gt; 20% 时显示，&gt; 50% 为严重，20-50% 为中等</span>
        </div>
        <div class="rule-item">
          <strong>组件复用率：</strong>
          <span>复用率 &lt; 30% 且总构建 &gt; 0 时显示，&lt; 10% 为严重，10-30% 为中等</span>
        </div>
        <div class="rule-item">
          <strong>技术栈与日志：</strong>
          <span>不在此页面显示</span>
        </div>
      </div>
    </el-card>

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

    <!-- 每个步骤的表格 -->
    <div
      v-for="item in summaryItems"
      :id="'summary-step-' + getStepIndex(item.step_id)"
      :key="item.step_id"
      class="step-section"
    >
      <div class="step-header">
        <span class="step-tag">步骤 {{ getStepIndex(item.step_id) }}</span>
        <span class="step-name">{{ getStepName(item.step_id) }}</span>
      </div>

      <el-table
        :data="getIssuesForStep(item)"
        stripe
        border
        style="width: 100%"
        :empty-text="'当前步骤未检测到需要关注的问题'"
      >
        <el-table-column prop="issue" label="Issue名称" width="200" />
        <el-table-column prop="detail" label="详情" min-width="300" />
        <el-table-column prop="severity" label="严重程度" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getSeverityType(row.severity)" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { Download } from '@element-plus/icons-vue';
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

interface IssueRow {
  issue: string;
  detail: string;
  severity: '严重' | '中等' | '轻微';
}

const jsonDataStore = useJsonDataStore();

const summaryItems = computed<SummaryItem[]>(() => (jsonDataStore.summary ?? []) as SummaryItem[]);

/** 是否有嵌入的 dbtools Excel 数据 */
const hasDbtoolsExcel = computed(() => !!jsonDataStore.dbtoolsExcel);

const showRules = ref(true);

/** 从 JSON 中的 gzip+base64 数据解压并下载 dbtools Excel */
const downloadDbtoolsExcel = async () => {
  const excel = jsonDataStore.dbtoolsExcel;
  if (!excel?.data || !excel?.filename) return;

  try {
    const binaryStr = atob(excel.data);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: 'application/gzip' });
    const ds = new DecompressionStream('gzip');
    const stream = blob.stream().pipeThrough(ds);
    const decompressed = await new Response(stream).arrayBuffer();
    const outBlob = new Blob([decompressed], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const url = URL.createObjectURL(outBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = excel.filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error('Failed to download dbtools Excel:', e);
  }
};

const stepNameMap = computed(() => {
  const map: Record<string, string> = {};
  const steps = jsonDataStore.steps || [];
  steps.forEach((step) => {
    const key = `step${step.step_id}`;
    map[key] = step.step_name;
  });
  return map;
});

const getStepIndex = (stepId: string) => {
  const match = stepId.match(/step(\d+)/);
  return match ? Number(match[1]) : stepId;
};

const getStepName = (stepId: string) => {
  return stepNameMap.value[stepId] ?? stepId;
};

const scrollToStep = (stepIndex: number) => {
  const el = document.getElementById(`summary-step-${stepIndex}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
};

// 解析百分比字符串为数字
const parsePercentage = (percentageStr?: string): number => {
  if (!percentageStr) return 0;
  const match = percentageStr.match(/(\d+\.?\d*)/);
  return match ? parseFloat(match[1]) : 0;
};

// 故障树阈值（与 FaultTreeAnalysis.vue 保持一致）
const FAULT_THRESHOLDS: Array<{
  path: string[];
  issueName: string; // 清晰的issue名称
  description: string; // 详细说明
  threshold: number;
  format?: (v: number) => string;
}> = [
  {
    path: ['arkui', 'animator'],
    issueName: 'ArkUI 帧动画数量过多',
    description: 'ArkUI 框架中创建的帧动画数量超过阈值，可能导致性能问题',
    threshold: 50,
  },
  {
    path: ['arkui', 'HandleOnAreaChangeEvent'],
    issueName: 'ArkUI 区域变化监听过多',
    description: '区域变化事件监听次数过多，可能影响渲染性能',
    threshold: 1000,
  },
  {
    path: ['arkui', 'HandleVisibleAreaChangeEvent'],
    issueName: 'ArkUI 可见区域变化监听过多',
    description: '可见区域变化事件监听次数过多，可能影响渲染性能',
    threshold: 1000,
  },
  {
    path: ['arkui', 'GetDefaultDisplay'],
    issueName: 'ArkUI 屏幕宽高获取次数过多',
    description: '频繁获取屏幕宽高信息，可能影响性能',
    threshold: 100,
  },
  {
    path: ['arkui', 'MarshRSTransactionData'],
    issueName: 'ArkUI 事务数据序列化次数过多',
    description: 'RS 事务数据序列化次数过多，可能影响渲染性能',
    threshold: 3000,
  },
  {
    path: ['RS', 'ProcessedNodes', 'count'],
    issueName: 'RS 渲染服务处理节点数过多',
    description: 'RS 渲染服务处理的节点数量超过阈值，可能导致渲染性能问题',
    threshold: 200,
  },
  {
    path: ['RS', 'ProcessedNodes', 'ts'],
    issueName: 'RS 渲染服务处理时间过长',
    description: 'RS 渲染服务处理节点的时间超过阈值，可能导致帧率下降',
    threshold: 5,
    format: (v) => v.toFixed(3),
  },
  {
    path: ['RS', 'DisplayNodeSkipTimes'],
    issueName: 'RS 渲染服务节点跳过次数过多',
    description: 'RS 渲染服务跳过节点渲染的次数过多，可能影响显示效果',
    threshold: 10,
  },
  {
    path: ['RS', 'UnMarshRSTransactionData'],
    issueName: 'RS 渲染服务反序列化次数过多',
    description: 'RS 事务数据反序列化次数过多，可能影响渲染性能',
    threshold: 60,
  },
  {
    path: ['RS', 'AnimateSize', 'nodeSizeSum'],
    issueName: 'RS 渲染服务动画节点总大小过大',
    description: 'RS 渲染服务中动画节点的总大小超过阈值，可能影响性能',
    threshold: 1000,
  },
  {
    path: ['RS', 'AnimateSize', 'totalAnimationSizeSum'],
    issueName: 'RS 渲染服务动画总大小过大',
    description: 'RS 渲染服务中所有动画的总大小超过阈值，可能影响性能',
    threshold: 2000,
  },
  {
    path: ['av_codec', 'BroadcastControlInstructions'],
    issueName: '音视频播控指令数过多',
    description: '音视频编解码的播控指令数量过多，可能影响播放性能',
    threshold: 1000000,
  },
  {
    path: ['av_codec', 'VideoDecodingInputFrameCount'],
    issueName: '视频解码输入帧数过多',
    description: '视频解码器接收的输入帧数量过多，可能导致解码性能问题',
    threshold: 300,
  },
  {
    path: ['av_codec', 'VideoDecodingConsumptionFrame'],
    issueName: '视频解码消费帧数过多',
    description: '视频解码器消费的帧数量过多，可能导致解码性能问题',
    threshold: 250,
  },
  {
    path: ['Audio', 'AudioWriteCB'],
    issueName: '音频写回调次数过多',
    description: '音频写回调函数调用次数过多，可能影响音频播放性能',
    threshold: 5000000,
  },
  {
    path: ['Audio', 'AudioReadCB'],
    issueName: '音频读回调次数过多',
    description: '音频读回调函数调用次数过多，可能影响音频录制性能',
    threshold: 1000000,
  },
  {
    path: ['Audio', 'AudioPlayCb'],
    issueName: '音频播放回调次数过多',
    description: '音频播放回调函数调用次数过多，可能影响音频播放性能',
    threshold: 1000000,
  },
  {
    path: ['Audio', 'AudioRecCb'],
    issueName: '音频录制回调次数过多',
    description: '音频录制回调函数调用次数过多，可能影响音频录制性能',
    threshold: 1000000,
  },
  {
    path: ['ipc_binder', 'total_transactions'],
    issueName: 'IPC Binder 进程间通信次数过多',
    description: 'IPC Binder 进程间通信的总次数超过阈值，可能影响应用响应性能',
    threshold: 10000,
  },
  {
    path: ['ipc_binder', 'high_latency_count'],
    issueName: 'IPC Binder 高延迟通信次数过多',
    description: 'IPC Binder 高延迟通信次数过多，可能导致应用卡顿',
    threshold: 10,
  },
  {
    path: ['ipc_binder', 'avg_latency'],
    issueName: 'IPC Binder 平均延迟过高',
    description: 'IPC Binder 进程间通信的平均延迟超过阈值，可能影响应用响应速度',
    threshold: 50,
    format: (v) => v.toFixed(2),
  },
  {
    path: ['ipc_binder', 'max_latency'],
    issueName: 'IPC Binder 最大延迟过高',
    description: 'IPC Binder 进程间通信的最大延迟超过阈值，可能导致应用出现明显卡顿',
    threshold: 100,
    format: (v) => v.toFixed(2),
  },
];

const formatFaultValue = (v: number): string => {
  if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
  if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
  return v.toLocaleString();
};

const getNested = (obj: Record<string, unknown>, path: string[]): unknown => {
  let cur: unknown = obj;
  for (const p of path) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
};

// 获取步骤的所有问题列表
const getIssuesForStep = (item: SummaryItem): IssueRow[] => {
  const issues: IssueRow[] = [];

  // 1. 空刷帧：占比 > 10% 显示，> 50% 严重，10-50% 中等
  if (item.empty_frame) {
    const percentage = parsePercentage(item.empty_frame.percentage);
    if (percentage > 10) {
      const severity: '严重' | '中等' = percentage > 50 ? '严重' : '中等';
      issues.push({
        issue: `空刷帧占比过高 (${item.empty_frame.percentage ?? '0.00%'})`,
        detail: `空刷帧数: ${item.empty_frame.count ?? 0}, 占比: ${item.empty_frame.percentage ?? '0.00%'}`,
        severity,
      });
    }
  }

  // 2. 故障树：超过阈值的显示
  if (item.fault_tree) {
    const ft = item.fault_tree as Record<string, unknown>;

    // 软解码：布尔值单独处理
    const avCodec = ft.av_codec;
    if (
      avCodec &&
      typeof avCodec === 'object' &&
      avCodec !== null &&
      'soft_decoder' in avCodec &&
      (avCodec as Record<string, unknown>).soft_decoder === true
    ) {
      issues.push({
        issue: '音视频使用软解码',
        detail: '检测到使用软解码器进行视频解码，软解码性能较差，建议使用硬解码以提升性能',
        severity: '中等',
      });
    }

    for (const { path, issueName, description, threshold, format } of FAULT_THRESHOLDS) {
      const raw = getNested(ft, path);
      if (typeof raw !== 'number') continue;
      if (raw <= threshold) continue;

      const valueStr = format ? format(raw) : formatFaultValue(raw);
      const thresholdStr = format ? format(threshold) : formatFaultValue(threshold);
      const severity: '严重' | '中等' = raw > threshold * 2 ? '严重' : '中等';
      issues.push({
        issue: `${issueName} (当前值: ${valueStr})`,
        detail: `${description}。当前值: ${valueStr}, 阈值: ${thresholdStr}`,
        severity,
      });
    }
  }

  // 3. Image 超尺寸：超尺寸数量 > 0 或额外内存 > 10MB 显示
  if (item.image_oversize) {
    const exceedCount = item.image_oversize.exceed_count ?? 0;
    const excessMemory = item.image_oversize.total_excess_memory_mb ?? 0;
    if (exceedCount > 0 || excessMemory > 10) {
      const severity: '严重' | '中等' = excessMemory > 50 ? '严重' : '中等';
      issues.push({
        issue: `Image 超尺寸问题 (${exceedCount} 个, ${excessMemory.toFixed(2)} MB)`,
        detail: `超尺寸数量: ${exceedCount}, 额外内存: ${excessMemory.toFixed(2)} MB`,
        severity,
      });
    }
  }

  // 4. 组件树：未上树占比 > 20% 显示
  if (item.component_tree) {
    const offTreeRatio = (item.component_tree.off_tree_ratio ?? 0) * 100;
    if (offTreeRatio > 20) {
      const severity: '严重' | '中等' = offTreeRatio > 50 ? '严重' : '中等';
      issues.push({
        issue: `组件未上树占比过高 (${offTreeRatio.toFixed(2)}%)`,
        detail: `未上树节点: ${item.component_tree.off_tree_nodes ?? 0}, 占比: ${offTreeRatio.toFixed(2)}%`,
        severity,
      });
    }
  }

  // 5. 组件复用：复用率 < 30% 显示
  if (item.component_reuse) {
    const reusabilityRatio = (item.component_reuse.reusability_ratio ?? 0) * 100;
    if (reusabilityRatio < 30 && (item.component_reuse.total_builds ?? 0) > 0) {
      const severity: '严重' | '中等' = reusabilityRatio < 10 ? '严重' : '中等';
      issues.push({
        issue: `组件复用率过低 (${reusabilityRatio.toFixed(2)}%)`,
        detail: `复用率: ${reusabilityRatio.toFixed(2)}%, 总构建: ${item.component_reuse.total_builds ?? 0}, 复用构建: ${item.component_reuse.recycled_builds ?? 0}`,
        severity,
      });
    }
  }

  // 技术栈和日志不显示（已排除）

  return issues;
};

// 获取严重程度的标签类型
const getSeverityType = (severity: string): 'danger' | 'warning' | 'info' => {
  if (severity === '严重') return 'danger';
  if (severity === '中等') return 'warning';
  return 'info';
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

.summary-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.summary-header h2 {
  margin: 0;
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
  margin-bottom: 20px;
}

.step-nav-label {
  font-size: 13px;
  color: #606266;
}

.step-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
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

.summary-empty {
  margin-top: 40px;
}

.rules-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
}

.rules-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #303133;
}

.rules-content {
  padding-top: 8px;
}

.rule-item {
  margin-bottom: 12px;
  font-size: 14px;
  line-height: 1.6;
  color: #606266;
}

.rule-item strong {
  color: #303133;
  margin-right: 8px;
}

.rule-section {
  margin-bottom: 16px;
}

.rule-section-title {
  display: block;
  color: #303133;
  margin-bottom: 8px;
  font-size: 14px;
}

.rule-subsection {
  margin-left: 0;
  padding-left: 0;
}

.rule-subtitle {
  font-size: 13px;
  color: #909399;
  margin-bottom: 12px;
  font-style: italic;
}

.rule-category {
  margin-bottom: 16px;
  padding-left: 16px;
  border-left: 3px solid #e4e7ed;
}

.rule-category strong {
  display: block;
  color: #303133;
  margin-bottom: 8px;
  font-size: 13px;
}

.rule-list {
  margin: 0;
  padding-left: 20px;
  list-style-type: disc;
}

.rule-list li {
  margin-bottom: 6px;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

:deep(.el-table .el-table__row:hover) {
  background-color: #f5f7fa;
}
</style>
