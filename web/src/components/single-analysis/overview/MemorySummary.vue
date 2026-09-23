<template>
  <div v-if="hasAnyData" class="memory-summary">
    <div class="summary-header">
      <h3 class="summary-title">
        <span class="title-tag">内存汇总</span>
      </h3>
      <p class="summary-desc">
        汇总所有步骤累计的内存信息。一级内存为进程级内存采样（PSS 各分类合计），Native 内存为 malloc/free/mmap 事件追踪的净内存（自第一个步骤起跨步骤累加）。
      </p>
    </div>

    <div v-if="globalMeminfo" class="metric-group">
      <div class="group-title">一级内存 · 全场景汇总</div>
      <div class="metric-cards">
        <div class="metric-card">
          <span class="metric-label">起始内存</span>
          <span class="metric-value">{{ fmtMb(globalMeminfo.startMb) }}</span>
          <span class="metric-sub">{{ shortStepLabel(globalMeminfo.startStepId) }} · 起始采样</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">结束内存</span>
          <span class="metric-value">{{ fmtMb(globalMeminfo.endMb) }}</span>
          <span class="metric-sub">{{ shortStepLabel(globalMeminfo.endStepId) }} · 结束采样</span>
        </div>
        <div class="metric-card metric-card-highlight">
          <span class="metric-label">峰值内存</span>
          <span class="metric-value">{{ fmtMb(globalMeminfo.peakMb) }}</span>
          <span class="metric-sub">出现于 {{ shortStepLabel(globalMeminfo.peakStepId) }}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">平均内存</span>
          <span class="metric-value">{{ fmtMb(globalMeminfo.avgMb) }}</span>
          <span class="metric-sub">共 {{ meminfoSamples.length }} 个采样点</span>
        </div>
        <div class="metric-card" :class="growthCardClass(globalMeminfo.growthMb)">
          <span class="metric-label">整体增长</span>
          <span class="metric-value" :class="growthTextClass(globalMeminfo.growthMb)">
            {{ fmtGrowth(globalMeminfo.growthMb) }}
          </span>
          <span class="metric-sub">结束内存 - 起始内存</span>
        </div>
      </div>
    </div>

    <div v-if="globalNative" class="metric-group">
      <div class="group-title">Native 内存 · 全场景汇总</div>
      <div class="metric-cards">
        <div class="metric-card metric-card-highlight">
          <span class="metric-label">峰值净内存</span>
          <span class="metric-value">{{ fmtMb(globalNative.peakMb) }}</span>
          <span class="metric-sub">出现于 {{ shortStepLabel(globalNative.peakStepId) }}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">结束未释放</span>
          <span class="metric-value">{{ fmtMb(globalNative.lastUnreleasedMb) }}</span>
          <span class="metric-sub">全场景累计 · 截至最后一步结束</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">事件总数</span>
          <span class="metric-value">{{ globalNative.totalEvents.toLocaleString() }}</span>
          <span class="metric-sub">所有步骤累计</span>
        </div>
      </div>
    </div>

    <div v-if="hasMeminfoData && meminfoRows.length" class="data-card">
      <div class="card-title">全场景一级内存时间线</div>
      <p class="chart-desc">
        所有步骤的一级内存采样按真实时间拼接，各分类堆叠展示；悬浮查看各分类明细与总量，背景区块区分步骤的数据点。
      </p>
      <MeminfoStackedAreaChart
        :data="meminfoRows"
        :step-ids="meminfoRowStepIds"
        :height="MEMINFO_CHART_HEIGHT"
      />
    </div>

    <div v-if="hasNativeData && nativeTimeline.hasData" class="data-card">
      <div class="card-title">全场景 Native 内存时间线（跨步骤累计）</div>
      <p class="chart-desc">
        自第一个步骤起持续累加 Native 内存事件（申请为正、释放为负），各步骤时段首尾拼接为累计时间轴，累计值跨步骤延续。
        支持分类/进程双模式与逐级下钻（总览→大类→小类→文件→事件 / 总览→进程→线程→文件→事件），双击图例下钻、单击图例隐藏，与步骤内内存时间线操作一致；背景区块区分每个步骤的数据点。
      </p>

      <el-alert
        v-if="summarySelectedTimePoint !== null"
        type="info"
        :closable="false"
        show-icon
        class="time-point-info-panel"
      >
        <template #title>
          <div class="time-point-info-content">
            <div class="time-point-info-meta">
              <span class="time-point-info-label">已选中时间点</span>
              <span><strong>累计时间:</strong> {{ formatSeconds(summarySelectedTimePoint) }}</span>
              <span v-if="summaryPointContext.stepLabel">
                <strong>所属步骤:</strong> {{ summaryPointContext.stepLabel }}
              </span>
              <span>
                <strong>当前累计内存:</strong> {{ fmtBytes(summaryTimePointStats.netMemory) }}
              </span>
              <span v-if="summaryPointContext.seriesName">
                <strong>选中系列:</strong> {{ summaryPointContext.seriesName }}
              </span>
              <span>
                <strong>事件统计:</strong>
                共 {{ summaryTimePointStats.eventCount.toLocaleString() }} 个
                （分配 {{ summaryTimePointStats.allocCount.toLocaleString() }} /
                释放 {{ summaryTimePointStats.freeCount.toLocaleString() }}）
              </span>
            </div>
            <el-button type="danger" size="small" class="time-point-clear-button" @click="clearSummarySelection">
              清除选择
            </el-button>
          </div>
        </template>
      </el-alert>

      <MemoryTimelineChart
        summary-mode
        :height="NATIVE_CHART_HEIGHT"
        :selected-time-point="summarySelectedTimePoint"
        @time-point-selected="handleSummaryTimePointSelected"
        @time-point-stats-updated="handleSummaryStatsUpdated"
        @drill-state-change="handleSummaryDrillStateChange"
        @point-selection-context="handleSummaryPointContext"
      />

      <MemoryOutstandingFlameGraph
        v-if="shouldShowSummaryFlameGraph"
        summary-mode
        :selected-time-point="summarySelectedTimePoint"
        :drill-level="summaryDrillState.drillLevel"
        :view-mode="summaryDrillState.viewMode"
        :selected-category="summaryDrillState.selectedCategory"
        :selected-sub-category="summaryDrillState.selectedSubCategory"
        :selected-process="summaryDrillState.selectedProcess"
        :selected-thread="summaryDrillState.selectedThread"
        :selected-file="summaryDrillState.selectedFile"
        :selected-series-name="summaryPointContext.seriesName"
      />
    </div>

    <MemoryCategoryPie
      v-if="hasNativeData && nativeTimeline.hasData"
      :selected-time-point="summarySelectedTimePoint"
    />

    <div class="data-card">
      <div class="card-title">各步骤内存统计</div>
      <el-table
        :data="stepRows"
        stripe
        border
        style="width: 100%"
        show-summary
        :summary-method="getSummaryRow"
        :empty-text="'暂无内存统计数据'"
      >
        <el-table-column label="步骤" width="160" align="left">
          <template #default="{ row }">
            <span class="step-tag">步骤{{ row.stepId }}</span>
            <span v-if="row.stepName" class="step-name" :title="row.stepName">{{ row.stepName }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="hasMeminfoData" label="一级内存 (MB)" align="center">
          <el-table-column prop="memStart" label="起始" width="90" align="right">
            <template #default="{ row }">{{ fmtMb(row.memStart) }}</template>
          </el-table-column>
          <el-table-column prop="memPeak" label="峰值" width="90" align="right">
            <template #default="{ row }">
              <span :class="{ 'peak-value': row.stepId === globalMeminfo?.peakStepId }">
                {{ fmtMb(row.memPeak) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="memEnd" label="结束" width="90" align="right">
            <template #default="{ row }">{{ fmtMb(row.memEnd) }}</template>
          </el-table-column>
          <el-table-column prop="memAvg" label="平均" width="90" align="right">
            <template #default="{ row }">{{ fmtMb(row.memAvg) }}</template>
          </el-table-column>
          <el-table-column prop="memGrowth" label="增长" width="110" align="right">
            <template #default="{ row }">
              <span :class="growthTextClass(row.memGrowth)">{{ fmtGrowth(row.memGrowth) }}</span>
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column v-if="hasNativeData" label="Native 内存" align="center">
          <el-table-column prop="nativePeak" label="步骤内峰值 (MB)" min-width="125" align="right">
            <template #default="{ row }">{{ fmtMb(row.nativePeak) }}</template>
          </el-table-column>
          <el-table-column prop="nativeUnreleased" label="步骤净增长 (MB)" min-width="135" align="right">
            <template #default="{ row }">{{ fmtGrowth(row.nativeUnreleased) }}</template>
          </el-table-column>
          <el-table-column prop="nativeEvents" label="事件数" width="100" align="right">
            <template #default="{ row }">
              {{ row.nativeEvents != null ? row.nativeEvents.toLocaleString() : '—' }}
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="goToStepMemory(row.stepId)">
              Memory分析
            </el-link>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { getDbApi } from '@/utils/dbApi';
import { useJsonDataStore } from '@/stores/jsonDataStore';
import MemoryTimelineChart from '../step/memory/MemoryTimelineChart.vue';
import MemoryOutstandingFlameGraph from '../step/memory/MemoryOutstandingFlameGraph.vue';
import MeminfoStackedAreaChart from '../step/memory/MeminfoStackedAreaChart.vue';
import MemoryCategoryPie from './MemoryCategoryPie.vue';

const emit = defineEmits<{ (e: 'page-change', page: string): void }>();

const MB = 1024 * 1024;
const NATIVE_CHART_HEIGHT = '420px';
const MEMINFO_CHART_HEIGHT = '500px';

interface MeminfoSample {
  stepId: number;
  timeMs: number;
  totalBytes: number;
}

interface StepMeminfoStats {
  stepId: number;
  startMb: number;
  endMb: number;
  peakMb: number;
  avgMb: number;
  growthMb: number;
}

interface StepNativeStats {
  stepId: number;
  peakMb: number;
  unreleasedMb: number;
  events: number;
}

/** 单个时间桶（10ms）的 Native 内存净变化 */
interface NativeBucket {
  stepId: number;
  /** 步骤内相对时间（秒） */
  timeSec: number;
  /** 净变化字节数（申请为正、释放为负） */
  netSize: number;
  eventCount: number;
}

type DrillDownLevel = 'overview' | 'category' | 'subCategory' | 'process' | 'thread' | 'file' | 'event';
type ViewMode = 'category' | 'process';

const jsonDataStore = useJsonDataStore();

const meminfoSamples = ref<MeminfoSample[]>([]);
/** 堆叠面积图原始行（timestamp / timestamp_epoch / data），与 meminfoRowStepIds 一一对应 */
const meminfoRows = ref<Record<string, unknown>[]>([]);
const meminfoRowStepIds = ref<number[]>([]);
const stepMeminfoMap = ref<Map<number, StepMeminfoStats>>(new Map());
const stepNativeMap = ref<Map<number, StepNativeStats>>(new Map());
const nativeBuckets = ref<Map<number, NativeBucket[]>>(new Map());

const hasMeminfoData = computed(() => meminfoSamples.value.length > 0);
const hasNativeData = computed(() => stepNativeMap.value.size > 0);
const hasAnyData = computed(() => hasMeminfoData.value || hasNativeData.value);

const stepNameMap = computed(() => {
  const map: Record<number, string> = {};
  (jsonDataStore.steps || []).forEach((step) => {
    map[Number(step.step_id)] = step.step_name;
  });
  return map;
});

function shortStepLabel(stepId: number): string {
  return `步骤${stepId}`;
}

const globalMeminfo = computed(() => {
  const samples = meminfoSamples.value;
  if (!samples.length) return null;

  const first = samples[0];
  const last = samples[samples.length - 1];
  let peak = first;
  for (const sample of samples) {
    if (sample.totalBytes > peak.totalBytes) peak = sample;
  }
  const avgBytes = samples.reduce((acc, s) => acc + s.totalBytes, 0) / samples.length;

  return {
    startMb: first.totalBytes / MB,
    startStepId: first.stepId,
    endMb: last.totalBytes / MB,
    endStepId: last.stepId,
    peakMb: peak.totalBytes / MB,
    peakStepId: peak.stepId,
    avgMb: avgBytes / MB,
    growthMb: (last.totalBytes - first.totalBytes) / MB,
  };
});

/**
 * 跨步骤累计 Native 内存汇总指标
 *
 * 自第一个步骤起持续累加内存事件（步骤间累计值延续），用于全局指标卡片：
 * - 峰值 = 全场景累计净内存的最大值（并记录所在步骤）
 * - 结束未释放 = 最后一个步骤结束时的累计净内存
 */
const nativeTimeline = computed<{
  hasData: boolean;
  peak: { stepId: number; valueBytes: number };
  finalBytes: number;
  totalEvents: number;
}>(() => {
  let carryBytes = 0;
  let totalEvents = 0;
  let peak = { stepId: 0, valueBytes: Number.NEGATIVE_INFINITY };
  let hasData = false;

  const stepIds = Array.from(nativeBuckets.value.keys()).sort((a, b) => a - b);
  for (const stepId of stepIds) {
    const buckets = nativeBuckets.value.get(stepId) ?? [];
    if (!buckets.length) continue;
    hasData = true;

    let cumBytes = carryBytes;
    for (const bucket of buckets) {
      cumBytes += bucket.netSize;
      totalEvents += bucket.eventCount;
      if (cumBytes > peak.valueBytes) {
        peak = { stepId, valueBytes: cumBytes };
      }
    }
    carryBytes = cumBytes;
  }

  return { hasData, peak, finalBytes: carryBytes, totalEvents };
});

const globalNative = computed(() => {
  const tl = nativeTimeline.value;
  if (!tl.hasData) return null;

  return {
    peakMb: tl.peak.valueBytes / MB,
    peakStepId: tl.peak.stepId,
    lastUnreleasedMb: tl.finalBytes / MB,
    totalEvents: tl.totalEvents,
  };
});

interface StepRow {
  stepId: number;
  stepName: string;
  memStart?: number;
  memPeak?: number;
  memEnd?: number;
  memAvg?: number;
  memGrowth?: number;
  nativePeak?: number;
  nativeUnreleased?: number;
  nativeEvents?: number;
}

const stepRows = computed<StepRow[]>(() => {
  const ids = new Set<number>([...stepMeminfoMap.value.keys(), ...stepNativeMap.value.keys()]);
  return Array.from(ids)
    .sort((a, b) => a - b)
    .map((stepId) => {
      const mem = stepMeminfoMap.value.get(stepId);
      const native = stepNativeMap.value.get(stepId);
      return {
        stepId,
        stepName: stepNameMap.value[stepId] ?? '',
        memStart: mem?.startMb,
        memPeak: mem?.peakMb,
        memEnd: mem?.endMb,
        memAvg: mem?.avgMb,
        memGrowth: mem?.growthMb,
        nativePeak: native?.peakMb,
        nativeUnreleased: native?.unreleasedMb,
        nativeEvents: native?.events,
      };
    });
});

function getSummaryRow({ columns }: { columns: { property?: string }[] }): string[] {
  return columns.map((col, index) => {
    if (index === 0) return '汇总';
    if (!col.property) return '';
    switch (col.property) {
      case 'memStart':
        return fmtMb(globalMeminfo.value?.startMb);
      case 'memPeak':
        return fmtMb(globalMeminfo.value?.peakMb);
      case 'memEnd':
        return fmtMb(globalMeminfo.value?.endMb);
      case 'memAvg':
        return fmtMb(globalMeminfo.value?.avgMb);
      case 'memGrowth':
        return fmtGrowth(globalMeminfo.value?.growthMb);
      case 'nativePeak':
        return fmtMb(globalNative.value?.peakMb);
      case 'nativeUnreleased':
        return fmtMb(globalNative.value?.lastUnreleasedMb);
      case 'nativeEvents':
        return globalNative.value ? globalNative.value.totalEvents.toLocaleString() : '—';
      default:
        return '';
    }
  });
}

function fmtMb(value?: number): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value.toFixed(2)} MB`;
}

function fmtGrowth(value?: number): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)} MB`;
}

function growthTextClass(value?: number): string {
  if (value == null || !Number.isFinite(value) || Math.abs(value) < 0.005) return '';
  return value > 0 ? 'growth-up' : 'growth-down';
}

function growthCardClass(value?: number): Record<string, boolean> {
  return { 'metric-card-growth': growthTextClass(value) !== '' };
}

// ==================== 汇总时间线：选中时间点状态与火焰图 ====================

interface SummaryTimePointStats {
  eventCount: number;
  allocCount: number;
  freeCount: number;
  netMemory: number;
}

interface SummaryPointContext {
  timePoint: number | null;
  seriesName: string;
  stepLabel: string;
  memoryAtPoint: number;
}

interface SummaryDrillState {
  drillLevel: DrillDownLevel;
  viewMode: ViewMode;
  selectedCategory: string;
  selectedSubCategory: string;
  selectedProcess: string;
  selectedThread: string;
  selectedFile: string;
}

const DEFAULT_DRILL_STATE: SummaryDrillState = {
  drillLevel: 'overview',
  viewMode: 'category',
  selectedCategory: '',
  selectedSubCategory: '',
  selectedProcess: '',
  selectedThread: '',
  selectedFile: '',
};

const summarySelectedTimePoint = ref<number | null>(null);
const summaryTimePointStats = ref<SummaryTimePointStats>(createEmptySummaryStats());
const summaryPointContext = ref<SummaryPointContext>({
  timePoint: null,
  seriesName: '',
  stepLabel: '',
  memoryAtPoint: 0,
});
const summaryDrillState = ref<SummaryDrillState>({ ...DEFAULT_DRILL_STATE });

/** 与步骤内 Memory 分析一致：选中时间点且（非总览层级 或 选中了具体系列）时显示火焰图 */
const shouldShowSummaryFlameGraph = computed(
  () =>
    summarySelectedTimePoint.value !== null &&
    (summaryDrillState.value.drillLevel !== 'overview' ||
      summaryPointContext.value.seriesName !== ''),
);

function createEmptySummaryStats(): SummaryTimePointStats {
  return { eventCount: 0, allocCount: 0, freeCount: 0, netMemory: 0 };
}

function handleSummaryTimePointSelected(timePoint: number | null) {
  summarySelectedTimePoint.value = timePoint;
  if (timePoint === null) {
    summaryTimePointStats.value = createEmptySummaryStats();
    summaryPointContext.value = { timePoint: null, seriesName: '', stepLabel: '', memoryAtPoint: 0 };
  }
}

function handleSummaryStatsUpdated(stats: SummaryTimePointStats) {
  summaryTimePointStats.value = stats;
}

function handleSummaryDrillStateChange(state: Omit<SummaryDrillState, never>) {
  summaryDrillState.value = { ...DEFAULT_DRILL_STATE, ...state };
}

function handleSummaryPointContext(ctx: {
  timePoint: number | null;
  seriesName: string;
  memoryAtPoint: number;
}) {
  const stepLabel = ctx.timePoint != null ? getStepLabelForTimeSec(ctx.timePoint) : '';
  summaryPointContext.value = {
    timePoint: ctx.timePoint,
    seriesName: ctx.seriesName,
    stepLabel,
    memoryAtPoint: ctx.memoryAtPoint,
  };
}

function clearSummarySelection() {
  summarySelectedTimePoint.value = null;
  summaryTimePointStats.value = createEmptySummaryStats();
  summaryPointContext.value = { timePoint: null, seriesName: '', stepLabel: '', memoryAtPoint: 0 };
}

/** 根据累计时间轴上的时间点计算所属步骤（步骤时长 = 步骤内最大时间桶 + 10ms，与 store 的拼接规则一致） */
function getStepLabelForTimeSec(timeSec: number): string {
  const ranges: Array<{ stepId: number; startSec: number; endSec: number }> = [];
  let offsetSec = 0;
  for (const stepId of Array.from(nativeBuckets.value.keys()).sort((a, b) => a - b)) {
    const buckets = nativeBuckets.value.get(stepId) ?? [];
    if (!buckets.length) continue;
    const maxSec = buckets.reduce((acc, b) => Math.max(acc, b.timeSec), 0);
    const durationSec = maxSec + 0.01;
    ranges.push({ stepId, startSec: offsetSec, endSec: offsetSec + durationSec });
    offsetSec += durationSec;
  }
  const range = ranges.find((r) => timeSec >= r.startSec && timeSec < r.endSec) ?? ranges[ranges.length - 1];
  return range ? `步骤${range.stepId}` : '';
}

function formatSeconds(seconds: number): string {
  return seconds < 1 ? `${(seconds * 1000).toFixed(2)} ms` : `${seconds.toFixed(2)} s`;
}

function fmtBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const abs = Math.abs(bytes);
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const idx = Math.min(Math.floor(Math.log(abs) / Math.log(1024)), units.length - 1);
  const sign = bytes < 0 ? '-' : '';
  return `${sign}${(abs / Math.pow(1024, idx)).toFixed(2)} ${units[idx]}`;
}

function goToStepMemory(stepId: number) {
  emit('page-change', `memory_step_${stepId}`);
}

onMounted(() => {
  void loadData();
});

onUnmounted(() => {
  // 图表实例由子组件（MeminfoStackedAreaChart / MemoryTimelineChart）自行管理
});

async function loadData() {
  await Promise.all([loadMeminfoData(), loadNativeData()]);
}

async function loadMeminfoData() {
  let rows;
  try {
    rows = await getDbApi().queryMemoryMeminfoAll();
  } catch (error) {
    console.warn('[MemorySummary] Failed to query meminfo data:', error);
    return;
  }

  const samples: MeminfoSample[] = [];
  const chartRows: Record<string, unknown>[] = [];
  const chartStepIds: number[] = [];
  for (const row of (rows || []).slice().sort((a, b) => {
    const stepDiff = Number(a.step_id ?? 0) - Number(b.step_id ?? 0);
    if (stepDiff !== 0) return stepDiff;
    return Number(a.timestamp_epoch ?? 0) - Number(b.timestamp_epoch ?? 0);
  })) {
    try {
      const data = JSON.parse(String(row.data ?? '{}')) as Record<string, unknown>;
      let totalBytes = 0;
      for (const value of Object.values(data)) {
        if (typeof value === 'number' && Number.isFinite(value)) totalBytes += value;
      }
      const epoch = Number(row.timestamp_epoch ?? 0);
      const timeMs = epoch > 0 ? epoch * 1000 : parseTimestampToMs(String(row.timestamp ?? ''));
      if (timeMs <= 0) continue;
      const stepId = Number(row.step_id ?? 0);
      samples.push({ stepId, timeMs, totalBytes });
      // 堆叠面积图原始行（与单步骤 MemoryMeminfo 一致的输入结构）
      chartRows.push({
        timestamp: row.timestamp,
        timestamp_epoch: row.timestamp_epoch,
        data: row.data,
      });
      chartStepIds.push(stepId);
    } catch {
      continue;
    }
  }

  meminfoSamples.value = samples;
  meminfoRows.value = chartRows;
  meminfoRowStepIds.value = chartStepIds;

  const map = new Map<number, StepMeminfoStats>();
  const stepIds = Array.from(new Set(samples.map((s) => s.stepId)));
  for (const stepId of stepIds) {
    const stepSamples = samples.filter((s) => s.stepId === stepId);
    if (!stepSamples.length) continue;
    const first = stepSamples[0];
    const last = stepSamples[stepSamples.length - 1];
    let peak = first;
    for (const sample of stepSamples) {
      if (sample.totalBytes > peak.totalBytes) peak = sample;
    }
    const avgBytes = stepSamples.reduce((acc, s) => acc + s.totalBytes, 0) / stepSamples.length;
    map.set(stepId, {
      stepId,
      startMb: first.totalBytes / MB,
      endMb: last.totalBytes / MB,
      peakMb: peak.totalBytes / MB,
      avgMb: avgBytes / MB,
      growthMb: (last.totalBytes - first.totalBytes) / MB,
    });
  }
  stepMeminfoMap.value = map;
}

async function loadNativeData() {
  let rows;
  try {
    rows = await getDbApi().queryNetMemoryTimelineAll();
  } catch (error) {
    console.warn('[MemorySummary] Failed to query native memory timeline:', error);
    return;
  }

  // 按步骤收集时间桶（SQL 已按 step_id, timePoint10ms 排序，此处再排序兜底）
  const bucketsMap = new Map<number, NativeBucket[]>();
  for (const row of rows || []) {
    const stepId = Number(row.step_id ?? 0);
    const bucket: NativeBucket = {
      stepId,
      timeSec: Number(row.timePoint10ms ?? 0) * 0.01,
      netSize: Number(row.netSize ?? 0),
      eventCount: Number(row.eventCount ?? 0),
    };
    if (!bucketsMap.has(stepId)) {
      bucketsMap.set(stepId, []);
    }
    bucketsMap.get(stepId)!.push(bucket);
  }

  // 步骤内统计（峰值/净增长/事件数，均为步骤内独立口径）
  const statsMap = new Map<number, StepNativeStats>();
  for (const [stepId, buckets] of bucketsMap) {
    buckets.sort((a, b) => a.timeSec - b.timeSec);
    let cumBytes = 0;
    let peakBytes = 0;
    let events = 0;
    for (const bucket of buckets) {
      cumBytes += bucket.netSize;
      if (cumBytes > peakBytes) peakBytes = cumBytes;
      events += bucket.eventCount;
    }
    statsMap.set(stepId, {
      stepId,
      peakMb: peakBytes / MB,
      unreleasedMb: cumBytes / MB,
      events,
    });
  }

  nativeBuckets.value = bucketsMap;
  stepNativeMap.value = statsMap;
}

function parseTimestampToMs(timestamp: string): number {
  if (typeof timestamp !== 'string' || timestamp.length < 15) return 0;
  const year = parseInt(timestamp.substring(0, 4));
  const month = parseInt(timestamp.substring(4, 6)) - 1;
  const day = parseInt(timestamp.substring(6, 8));
  const hour = parseInt(timestamp.substring(9, 11));
  const minute = parseInt(timestamp.substring(11, 13));
  const second = parseInt(timestamp.substring(13, 15));
  const parsed = new Date(year, month, day, hour, minute, second).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

// 一级内存时间线由 MeminfoStackedAreaChart 渲染（与单步骤一致）
// 跨步骤累计 Native 内存时间线由 MemoryTimelineChart（summary-mode）渲染
</script>

<style scoped>
.memory-summary {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
}

.summary-title {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.title-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 14px;
}

.summary-desc {
  margin: 0;
  color: #606266;
  font-size: 13px;
}

.chart-desc {
  margin: 0 0 10px 0;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}

.time-point-info-panel {
  margin-bottom: 16px;
  border-radius: 8px;
}

.time-point-info-panel :deep(.el-alert__title) {
  width: 100%;
}

.time-point-info-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.time-point-info-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.time-point-info-label {
  font-weight: 600;
  font-size: 14px;
}

.time-point-clear-button {
  flex-shrink: 0;
}

.metric-group {
  margin-top: 16px;
}

.group-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
}

.metric-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: #f5f7fa;
  border-radius: 8px;
}

.metric-card-highlight {
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
}

.metric-card-growth {
  border: 1px solid #fde2e2;
}

.metric-label {
  color: #909399;
  font-size: 12px;
}

.metric-value {
  color: #303133;
  font-weight: 600;
  font-size: 16px;
}

.metric-sub {
  color: #a8abb2;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.growth-up {
  color: #f56c6c;
}

.growth-down {
  color: #67c23a;
}

.data-card {
  margin-top: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.timeline-chart {
  width: 100%;
  height: 320px;
}

.step-tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4c6fff;
  font-size: 12px;
  font-weight: 600;
  margin-right: 6px;
  white-space: nowrap;
}

.step-name {
  font-size: 12px;
  color: #909399;
  max-width: 120px;
  display: inline-block;
  vertical-align: bottom;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.peak-value {
  color: #e6a23c;
  font-weight: 600;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

:deep(.el-table .el-table__row:hover) {
  background-color: #f5f7fa;
}
</style>
