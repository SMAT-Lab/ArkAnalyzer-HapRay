<template>
  <div class="memory-timeline-chart">
    <div style="position: relative; width: 100%;">
      <div
        style="position: absolute; top: 10px; right: 10px; z-index: 100; display: flex; gap: 15px; align-items: center;"
      >
        <el-radio-group
          v-model="yAxisScaleMode"
          size="small"
        >
          <el-radio-button value="linear">均匀刻度</el-radio-button>
          <el-radio-button value="log">非均匀刻度</el-radio-button>
        </el-radio-group>
        <el-radio-group
          v-model="viewMode"
          size="small"
          @change="handleViewModeChange"
        >
          <el-radio-button value="category">分类模式</el-radio-button>
          <el-radio-button value="process">进程模式</el-radio-button>
        </el-radio-group>
      </div>

      <div
        v-if="drillDownLevel !== 'overview'"
        style="margin-bottom: 10px; padding: 10px; background: #f5f5f5; border-radius: 4px;"
      >
        <el-breadcrumb separator="/">
          <el-breadcrumb-item>
            <a
              href="#"
              style="color: #409eff; text-decoration: none;"
              @click.prevent="resetDrillDown"
            >
              <i class="el-icon-s-home"></i> 总览
            </a>
          </el-breadcrumb-item>

          <template v-if="viewMode === 'category'">
            <el-breadcrumb-item v-if="drillDownLevel === 'category'">
              <span style="font-weight: 600; color: #333;">{{ selectedCategory }}</span>
            </el-breadcrumb-item>

            <el-breadcrumb-item
              v-if="drillDownLevel === 'subCategory' || drillDownLevel === 'file'"
            >
              <a
                href="#"
                style="color: #409eff; text-decoration: none;"
                @click.prevent="backToCategory"
              >
                {{ selectedCategory }}
              </a>
            </el-breadcrumb-item>

            <el-breadcrumb-item v-if="drillDownLevel === 'subCategory'">
              <span style="font-weight: 600; color: #333;">{{ selectedSubCategory }}</span>
            </el-breadcrumb-item>

            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <a
                href="#"
                style="color: #409eff; text-decoration: none;"
                @click.prevent="backToSubCategory"
              >
                {{ selectedSubCategory }}
              </a>
            </el-breadcrumb-item>

            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <span style="font-weight: 600; color: #333;">{{ selectedFile }}</span>
            </el-breadcrumb-item>
          </template>

          <template v-else>
            <el-breadcrumb-item v-if="drillDownLevel === 'process'">
              <span style="font-weight: 600; color: #333;">{{ selectedProcess }}</span>
            </el-breadcrumb-item>

            <el-breadcrumb-item
              v-if="drillDownLevel === 'thread' || drillDownLevel === 'file'"
            >
              <a
                href="#"
                style="color: #409eff; text-decoration: none;"
                @click.prevent="backToProcess"
              >
                {{ selectedProcess }}
              </a>
            </el-breadcrumb-item>

            <el-breadcrumb-item v-if="drillDownLevel === 'thread'">
              <span style="font-weight: 600; color: #333;">{{ selectedThread }}</span>
            </el-breadcrumb-item>

            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <a
                href="#"
                style="color: #409eff; text-decoration: none;"
                @click.prevent="backToThread"
              >
                {{ selectedThread }}
              </a>
            </el-breadcrumb-item>

            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <span style="font-weight: 600; color: #333;">{{ selectedFile }}</span>
            </el-breadcrumb-item>
          </template>
        </el-breadcrumb>
      </div>

      <div ref="chartContainer" :style="{ height, width: '100%' }"></div>
      <div
        v-if="isLoading"
        style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255, 255, 255, 0.9); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 1000;"
      >
        <div style="text-align: center;">
          <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">正在加载图表...</div>
          <div style="font-size: 12px; color: #666;">数据量较大，请稍候</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import type { LineSeriesOption } from 'echarts';
import type { NativeMemoryRecord } from '@/stores/nativeMemory';
import {
  fetchOverviewTimeline,
  fetchCategoryRecords,
  fetchSubCategoryRecords,
  fetchProcessRecords,
  fetchThreadRecords,
} from '@/stores/nativeMemory';

// 时间线处理后的数据结构（供图表渲染使用）
interface TimelineProcessedData {
  chartData: Array<{
    index: number;
    relativeTs: number;
    cumulativeMemory: number;
  }>;
  seriesData: Array<{
    name: string;
    data: Array<{
      index: number;
      relativeTs: number;
      cumulativeMemory: number;
      heapSize: number;
      eventType: string;
      eventCount?: number;  // 事件数量（聚合后）
      eventDetails?: string;  // 事件详情（聚合后）
    }>;
  }>;
  maxMemory: number;
  minMemory: number;
  finalMemory: number;
  threshold30: number;
  threshold60: number;
  // 双Y轴相关数据
  seriesMaxValues: number[];  // 每条系列的最大值
}

// 单个时间点的统计信息
interface TimePointStats {
  eventCount: number;
  allocCount: number;
  freeCount: number;
  netMemory: number;
}

// 提示框参数（ECharts 回调入参与校验）
interface AxisTooltipItem {
  seriesIndex?: number;
  dataIndex?: number;
  seriesName?: string;
  componentType?: string;
  value?: unknown;
  axisValue?: string | number;
  axisIndex?: number;
  [key: string]: unknown;
}

// AxisPointer label formatter 参数类型
interface AxisPointerLabelFormatterParams {
  value: string | number;
  axisDimension?: string;
}

type SeriesDataEntry = TimelineProcessedData['seriesData'][number];
type SeriesPoint = SeriesDataEntry['data'][number];
// 系列分组（用于按大类/小类/进程/线程/文件聚合）
interface SeriesGroup {
  name: string;
  records: NativeMemoryRecord[];
}

// 组装图表配置所需的参数
interface ChartOptionParams {
  chartData: TimelineProcessedData['chartData'];
  seriesData: TimelineProcessedData['seriesData'];
  maxMemory: number;
  minMemory: number;
  finalMemory: number;
  selectedTimePoint: number | null;
  drillLevel: DrillDownLevel;
  selectedCategory: string;
  selectedSubCategory: string;
  selectedProcess: string;
  selectedThread: string;
  selectedFile: string;
  mode: ViewMode;
  isLargeDataset: boolean;
  isVeryLargeDataset: boolean;
  selectedSeriesIndex: number | null;
  seriesMaxValues: number[];
}

const DEFAULT_CHART_HEIGHT = '420px';
const LARGE_DATA_THRESHOLD = 10_000;
const VERY_LARGE_DATA_THRESHOLD = 50_000;
const SERIES_COLORS = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
const HIGHLIGHT_COLORS = ['#333333', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
const MAX_SERIES_IN_CATEGORY_VIEW = 10;
const MAX_SERIES_IN_FILE_VIEW = 10;

interface Props {
  stepId: number; // 步骤 ID，例如 1
  height?: string;
  selectedTimePoint?: number | null; // 已选中的时间点
}

const props = withDefaults(defineProps<Props>(), {
  height: DEFAULT_CHART_HEIGHT,
  selectedTimePoint: null,
});

// 事件发射器（对外通知时间点选择、统计信息更新、下钻状态变化）
const emit = defineEmits<{
  'time-point-selected': [timePoint: number | null];
  'time-point-stats-updated': [stats: TimePointStats];
  'drill-state-change': [state: {
    drillLevel: DrillDownLevel;
    viewMode: ViewMode;
    selectedCategory: string;
    selectedSubCategory: string;
    selectedProcess: string;
    selectedThread: string;
    selectedFile: string;
  }];
  // 选中点的上下文（用于外部显示“已选中时间点”栏与火焰图筛选）
  'point-selection-context': [context: {
    timePoint: number | null;
    seriesName: string;
    viewMode: ViewMode;
    drillLevel: DrillDownLevel;
    selectedCategory: string;
    selectedSubCategory: string;
    selectedProcess: string;
    selectedThread: string;
    selectedFile: string;
    memoryAtPoint: number;
  }];
}>();

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const isLoading = ref(false);

// 当前下钻范围内的记录（按需加载）
const currentRecords = ref<NativeMemoryRecord[]>([]);

// 第一层总内存的峰值时间值（relativeTs，计算一次后保持不变）
let overviewPeakTimeValue: number | null = null;

// Overview 层级的所有时间点（用于确保所有层级的数据点一致）
let overviewTimePoints: number[] = [];

// 视图模式与下钻层级：分类模式 / 进程模式
type ViewMode = 'category' | 'process';
type DrillDownLevel =
  | 'overview'
  | 'category'
  | 'subCategory'
  | 'process'
  | 'thread'
  | 'file';

const viewMode = ref<ViewMode>('category');
const drillDownLevel = ref<DrillDownLevel>('overview');

/**
 * Y轴刻度模式
 * - 'linear': 均匀刻度（Y轴不分段，均匀分布）
 * - 'log': 非均匀刻度（对数刻度，用于显示跨度大的数据）
 */
type YAxisScaleMode = 'linear' | 'log';
const yAxisScaleMode = ref<YAxisScaleMode>('linear');

// 分类模式状态
const selectedCategory = ref<string>('');
const selectedSubCategory = ref<string>('');

// 进程模式状态
const selectedProcess = ref<string>('');
const selectedThread = ref<string>('');
const selectedFile = ref<string>('');
const activeSeriesIndex = ref<number | null>(null);
let isLegendSelectionSyncing = false;
// 记录点击点所属的系列，便于下游（统计、火焰图）基于正确的系列上下文工作
const selectedSeriesIndex = ref<number | null>(null);
const selectedSeriesName = ref<string>('');

// ============================================================================
// 图例事件管理系统
// ============================================================================
// 用于检测双击的状态
interface LegendClickState {
  lastClickTime: number;
  lastClickName: string;
  isProcessing: boolean;
}

const legendClickState: LegendClickState = {
  lastClickTime: 0,
  lastClickName: '',
  isProcessing: false,
};

const DOUBLE_CLICK_THRESHOLD = 300; // 毫秒

// 检测是否为双击
function isLegendDoubleClick(currentName: string, currentTime: number): boolean {
  const isDouble =
    legendClickState.lastClickName === currentName &&
    currentTime - legendClickState.lastClickTime < DOUBLE_CLICK_THRESHOLD;

  // 更新状态
  legendClickState.lastClickTime = currentTime;
  legendClickState.lastClickName = currentName;

  return isDouble;
}

// 设置处理状态
function setLegendProcessing(processing: boolean) {
  legendClickState.isProcessing = processing;
}

// 获取处理状态
function isLegendProcessing(): boolean {
  return legendClickState.isProcessing;
}

const emitDrillStateChange = () => {
  emit('drill-state-change', {
    drillLevel: drillDownLevel.value,
    viewMode: viewMode.value,
    selectedCategory: selectedCategory.value,
    selectedSubCategory: selectedSubCategory.value,
    selectedProcess: selectedProcess.value,
    selectedThread: selectedThread.value,
    selectedFile: selectedFile.value,
  });
};

watch(
  [
    viewMode,
    drillDownLevel,
    selectedCategory,
    selectedSubCategory,
    selectedProcess,
    selectedThread,
    selectedFile,
  ],
  () => {
    emitDrillStateChange();
  },
  { immediate: true },
);

/**
 * 监听Y轴刻度模式变化，重新渲染图表
 * 当用户切换均匀刻度和非均匀刻度时，重新配置Y轴并渲染图表
 */
watch(
  () => yAxisScaleMode.value,
  () => {
    console.log('[MemoryTimelineChart] Y轴刻度模式已切换为:', yAxisScaleMode.value === 'linear' ? '均匀刻度' : '非均匀刻度');
    renderChart();
  }
);

function handleViewModeChange() {
  resetDrillDown();
}

function resetDrillDown() {
  drillDownLevel.value = 'overview';
  selectedCategory.value = '';
  selectedSubCategory.value = '';
  selectedProcess.value = '';
  selectedThread.value = '';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

// 分类模式导航
function backToCategory() {
  drillDownLevel.value = 'category';
  selectedSubCategory.value = '';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function backToSubCategory() {
  drillDownLevel.value = 'subCategory';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToCategory(categoryName: string) {
  drillDownLevel.value = 'category';
  selectedCategory.value = categoryName;
  selectedSubCategory.value = '';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToSubCategory(subCategoryName: string) {
  drillDownLevel.value = 'subCategory';
  selectedSubCategory.value = subCategoryName;
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function backToProcess() {
  drillDownLevel.value = 'process';
  selectedThread.value = '';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function backToThread() {
  drillDownLevel.value = 'thread';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToProcess(processName: string) {
  drillDownLevel.value = 'process';
  selectedProcess.value = processName;
  selectedThread.value = '';
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToThread(threadName: string) {
  drillDownLevel.value = 'thread';
  selectedThread.value = threadName;
  selectedFile.value = '';
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToFile(fileName: string) {
  drillDownLevel.value = 'file';
  selectedFile.value = fileName;
  selectedSeriesIndex.value = null;
  selectedSeriesName.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

// 使用 ref 存储处理后的数据（由 Worker 异步计算）
function createEmptyProcessedData(): TimelineProcessedData {
  return {
    chartData: [],
    seriesData: [],
    maxMemory: 0,
    minMemory: 0,
    finalMemory: 0,
    threshold30: 0,
    threshold60: 0,
    seriesMaxValues: [],
  };
}

const processedData = ref<TimelineProcessedData>(createEmptyProcessedData());

function createEmptyTimePointStats(): TimePointStats {
  return {
    eventCount: 0,
    allocCount: 0,
    freeCount: 0,
    netMemory: 0,
  };
}

function calculateTimePointStats(records: NativeMemoryRecord[], timePoint: number | null): TimePointStats {
  const stats = createEmptyTimePointStats();

  if (timePoint === null || records.length === 0) {
    return stats;
  }

  for (const record of records) {
    if (record.relativeTs > timePoint) {
      break;
    }

    stats.eventCount += 1;

    const heapSize = record.heapSize ?? 0;
    switch (record.eventType) {
      case 'AllocEvent':
      case 'MmapEvent':
        stats.allocCount += 1;
        stats.netMemory += heapSize;
        break;
      case 'FreeEvent':
      case 'MunmapEvent':
        stats.freeCount += 1;
        stats.netMemory -= heapSize;
        break;
      default:
        break;
    }
  }

  return stats;
}

// 数据处理中的加载状态
const isLoadingData = ref(false);

/**
 * 为每条记录计算累计内存（按时间顺序累加/扣减）。
 */
function calculateCumulativeMemory(records: NativeMemoryRecord[]) {
  let currentTotal = 0;
  return records.map(record => {
    const eventType = record.eventType;
    const size = record.heapSize || 0;
    if (eventType === 'AllocEvent' || eventType === 'MmapEvent') {
      currentTotal += size;
    } else if (eventType === 'FreeEvent' || eventType === 'MunmapEvent') {
      currentTotal -= size;
    }
    return {
      ...record,
      cumulativeMemory: currentTotal,
    };
  });
}

function selectTopGroupsByFinalMemory(groups: SeriesGroup[], limit: number): SeriesGroup[] {
  if (groups.length <= limit) {
    return groups;
  }

  return groups
    .map(group => {
      const recordsWithCumulative = calculateCumulativeMemory(group.records);
      const finalMemory = recordsWithCumulative[recordsWithCumulative.length - 1]?.cumulativeMemory || 0;
      return { group, finalMemory };
    })
    .sort((a, b) => Math.abs(b.finalMemory) - Math.abs(a.finalMemory))
    .slice(0, limit)
    .map(item => item.group);
}

/**
 * 在主线程上处理时间线数据（构建图表需要的数据结构）。
 */
function processTimelineDataSync(): TimelineProcessedData {
  if (currentRecords.value.length === 0) {
    return {
      chartData: [],
      seriesData: [],
      maxMemory: 0,
      minMemory: 0,
      finalMemory: 0,
      threshold30: 0,
      threshold60: 0,
      seriesMaxValues: [],
    };
  }

  // 按时间排序记录
  const sortedRecords = currentRecords.value.slice().sort((a, b) => a.relativeTs - b.relativeTs);

  // 根据下钻层级和模式过滤数据
  let filteredRecords = sortedRecords;

  if (viewMode.value === 'category') {
    // 分类模式过滤
    if (drillDownLevel.value === 'category') {
      filteredRecords = sortedRecords.filter(r => r.categoryName === selectedCategory.value);
    } else if (drillDownLevel.value === 'subCategory') {
      filteredRecords = sortedRecords.filter(
        r => r.categoryName === selectedCategory.value && r.subCategoryName === selectedSubCategory.value
      );
    } else if (drillDownLevel.value === 'file') {
      filteredRecords = sortedRecords.filter(
        r => r.categoryName === selectedCategory.value &&
             r.subCategoryName === selectedSubCategory.value &&
             normalizeFileName(r.file) === selectedFile.value
      );
    }
  } else {
    // 进程模式过滤
    if (drillDownLevel.value === 'process') {
      filteredRecords = sortedRecords.filter(r => r.process === selectedProcess.value);
    } else if (drillDownLevel.value === 'thread') {
      filteredRecords = sortedRecords.filter(
        r => r.process === selectedProcess.value && r.thread === selectedThread.value
      );
    } else if (drillDownLevel.value === 'file') {
      filteredRecords = sortedRecords.filter(
        r => r.process === selectedProcess.value &&
             r.thread === selectedThread.value &&
             normalizeFileName(r.file) === selectedFile.value
      );
    }
  }

  // 根据下钻层级和模式决定如何分组数据
  let seriesGroups: SeriesGroup[] = [];

  if (drillDownLevel.value === 'overview') {
    // 总览：先添加总内存线，再根据模式添加分组线
    seriesGroups.push({ name: '总内存', records: filteredRecords });

    if (viewMode.value === 'category') {
      // 分类模式：按大类分组（排除 UNKNOWN）。数据已在后端聚合，这里直接组装。
      const categoryMap = new Map<string, NativeMemoryRecord[]>();
      filteredRecords.forEach(record => {
        const categoryName = record.categoryName;
        if (categoryName && categoryName !== 'UNKNOWN') {
          if (!categoryMap.has(categoryName)) {
            categoryMap.set(categoryName, []);
          }
          categoryMap.get(categoryName)!.push(record);
        }
      });
      seriesGroups.push(...Array.from(categoryMap.entries()).map(([name, records]) => ({ name, records })));
    } else {
      // 进程模式：按进程分组。数据已在后端聚合，这里直接组装。
      const processMap = new Map<string, NativeMemoryRecord[]>();
      filteredRecords.forEach(record => {
        const processName = record.process;
        if (processName) {
          if (!processMap.has(processName)) {
            processMap.set(processName, []);
          }
          processMap.get(processName)!.push(record);
        }
      });
      seriesGroups.push(...Array.from(processMap.entries()).map(([name, records]) => ({ name, records })));
    }
  } else if (viewMode.value === 'category') {
    // 分类模式的下钻
    if (drillDownLevel.value === 'category') {
      // 大类视图：按小类分组
      console.log('[MemoryTimelineChart] Category level - total filtered records:', filteredRecords.length);

      const subCategoryMap = new Map<string, NativeMemoryRecord[]>();
      filteredRecords.forEach(record => {
        if (!subCategoryMap.has(record.subCategoryName)) {
          subCategoryMap.set(record.subCategoryName, []);
        }
        subCategoryMap.get(record.subCategoryName)!.push(record);
      });

      console.log('[MemoryTimelineChart] Category level - unique subCategories:', Array.from(subCategoryMap.keys()));

      const allSeriesGroups = Array.from(subCategoryMap.entries()).map(([name, records]) => ({ name, records }));
      seriesGroups = selectTopGroupsByFinalMemory(allSeriesGroups, MAX_SERIES_IN_CATEGORY_VIEW);
      console.log('[MemoryTimelineChart] Category level - series groups after selection:', seriesGroups.map(g => g.name));
    } else if (drillDownLevel.value === 'subCategory') {
      // 小类视图：按文件分组
      console.log('[MemoryTimelineChart] SubCategory level - total filtered records:', filteredRecords.length);

      // 检查前几条记录的文件信息（用于排查文件名是否为空/异常）
      const sampleRecords = filteredRecords.slice(0, 5);
      console.log('[MemoryTimelineChart] Sample records:', sampleRecords.map(r => ({
        file: r.file,
        normalized: normalizeFileName(r.file),
        category: r.categoryName,
        subCategory: r.subCategoryName
      })));

      const fileMap = new Map<string, NativeMemoryRecord[]>();
      let nullFileCount = 0;

      filteredRecords.forEach(record => {
        const fileName = normalizeFileName(record.file);
        if (!fileName) {
          nullFileCount++;
          return;
        }

        if (!fileMap.has(fileName)) {
          fileMap.set(fileName, []);
        }
        fileMap.get(fileName)!.push(record);
      });

      console.log('[MemoryTimelineChart] SubCategory level - null/NA files:', nullFileCount);
      console.log('[MemoryTimelineChart] SubCategory level - unique files:', Array.from(fileMap.keys()));

      const fileSeriesGroups = Array.from(fileMap.entries()).map(([name, records]) => ({ name, records }));
      seriesGroups = selectTopGroupsByFinalMemory(fileSeriesGroups, MAX_SERIES_IN_FILE_VIEW);
      console.log('[MemoryTimelineChart] SubCategory level - file groups after selection:', seriesGroups.length, 'files');
    } else if (drillDownLevel.value === 'file') {
      // 文件视图：显示单个文件的详细数据
      seriesGroups = [{ name: selectedFile.value, records: filteredRecords }];
    }
  } else {
    // 进程模式的下钻
    if (drillDownLevel.value === 'process') {
      // 进程视图：按线程分组
      const threadMap = new Map<string, NativeMemoryRecord[]>();
      filteredRecords.forEach(record => {
        const threadName = record.thread || 'Unknown Thread';
        if (!threadMap.has(threadName)) {
          threadMap.set(threadName, []);
        }
        threadMap.get(threadName)!.push(record);
      });

      const allSeriesGroups = Array.from(threadMap.entries()).map(([name, records]) => ({ name, records }));
      seriesGroups = selectTopGroupsByFinalMemory(allSeriesGroups, MAX_SERIES_IN_CATEGORY_VIEW);
    } else if (drillDownLevel.value === 'thread') {
      // 线程视图：按文件分组
      console.log('[MemoryTimelineChart] Thread level - total filtered records:', filteredRecords.length);
      const fileMap = new Map<string, NativeMemoryRecord[]>();
      let nullFileCount = 0;

      filteredRecords.forEach(record => {
        const fileName = normalizeFileName(record.file);
        if (!fileName) {
          nullFileCount++;
          return;
        }

        if (!fileMap.has(fileName)) {
          fileMap.set(fileName, []);
        }
        fileMap.get(fileName)!.push(record);
      });

      console.log('[MemoryTimelineChart] Thread level - null/NA files:', nullFileCount);

      const fileSeriesGroups = Array.from(fileMap.entries()).map(([name, records]) => ({ name, records }));
      seriesGroups = selectTopGroupsByFinalMemory(fileSeriesGroups, MAX_SERIES_IN_FILE_VIEW);
      console.log('[MemoryTimelineChart] Thread level - file groups after selection:', seriesGroups.length, 'files');
    } else if (drillDownLevel.value === 'file') {
      // 文件视图：显示单个文件的详细数据
      seriesGroups = [{ name: selectedFile.value, records: filteredRecords }];
    }
  }

  // 收集唯一的时间点并排序
  // 在 overview 层级时，保存所有时间点供下钻层级使用
  // 在下钻层级时，使用 overview 层级保存的时间点，确保数据点一致
  let sortedTimePoints: number[];

  if (drillDownLevel.value === 'overview') {
    const allTimePoints = new Set<number>();
    filteredRecords.forEach(record => allTimePoints.add(record.relativeTs));
    sortedTimePoints = Array.from(allTimePoints).sort((a, b) => a - b);
    // 保存 overview 层级的时间点
    overviewTimePoints = sortedTimePoints;
  } else {
    // 下钻层级：使用 overview 层级保存的时间点
    sortedTimePoints = overviewTimePoints.length > 0 ? overviewTimePoints : (() => {
      const allTimePoints = new Set<number>();
      filteredRecords.forEach(record => allTimePoints.add(record.relativeTs));
      return Array.from(allTimePoints).sort((a, b) => a - b);
    })();
  }

  // 为每条系列计算在各时间点的累计内存
  const seriesData: TimelineProcessedData['seriesData'] = [];
  let maxMemory = -Infinity;
  let minMemory = Infinity;

  seriesGroups.forEach(group => {
    const recordsWithCumulative = calculateCumulativeMemory(group.records);

    const timeToRecordMap = new Map<number, typeof recordsWithCumulative[0]>();
    recordsWithCumulative.forEach(record => {
      timeToRecordMap.set(record.relativeTs, record);
    });

    let lastMemory = 0;
    const data = sortedTimePoints.map((ts, index) => {
      const originalRecord = timeToRecordMap.get(ts);
      const memory = originalRecord?.cumulativeMemory ?? lastMemory;
      lastMemory = memory;

      if (memory > maxMemory) maxMemory = memory;
      if (memory < minMemory) minMemory = memory;

      return {
        index,
        relativeTs: ts,
        cumulativeMemory: memory,
        heapSize: originalRecord?.heapSize || 0,
        eventType: originalRecord?.eventType || '',
        eventCount: originalRecord?.eventCount,
        eventDetails: originalRecord?.eventDetails,
      };
    });

    seriesData.push({ name: group.name, data });
  });

  // 构建总内存曲线（当非总览时为各系列累计之和）
  const chartData = sortedTimePoints.map((ts, index) => {
    let totalMemory = 0;

    if (drillDownLevel.value === 'overview' && seriesData.length > 0) {
      totalMemory = seriesData[0].data[index]?.cumulativeMemory || 0;
    } else {
      seriesData.forEach(series => {
        totalMemory += series.data[index]?.cumulativeMemory || 0;
      });
    }

    return {
      index,
      relativeTs: ts,
      cumulativeMemory: totalMemory,
    };
  });

  const finalMemory = chartData[chartData.length - 1]?.cumulativeMemory || 0;

  // 对系列按照最大值排序（总览层级时，总内存线保持在第一位）
  const sortedSeriesData = [...seriesData];
  if (drillDownLevel.value === 'overview' && sortedSeriesData.length > 0) {
    // 总览层级：总内存线保持在第一位，其他系列按最大值排序
    const totalSeries = sortedSeriesData[0];
    const otherSeries = sortedSeriesData.slice(1);
    
    // 计算每个系列的最大值并排序
    const seriesWithMax = otherSeries.map(series => {
      let maxValue = -Infinity;
      for (const item of series.data) {
        if (typeof item.cumulativeMemory === 'number' && item.cumulativeMemory > maxValue) {
          maxValue = item.cumulativeMemory;
        }
      }
      return { series, maxValue };
    });
    
    seriesWithMax.sort((a, b) => b.maxValue - a.maxValue);
    sortedSeriesData.splice(0, sortedSeriesData.length, totalSeries, ...seriesWithMax.map(item => item.series));
  } else {
    // 其他层级：所有系列按最大值排序
    const seriesWithMax = sortedSeriesData.map(series => {
      let maxValue = -Infinity;
      for (const item of series.data) {
        if (typeof item.cumulativeMemory === 'number' && item.cumulativeMemory > maxValue) {
          maxValue = item.cumulativeMemory;
        }
      }
      return { series, maxValue };
    });
    
    seriesWithMax.sort((a, b) => b.maxValue - a.maxValue);
    sortedSeriesData.splice(0, sortedSeriesData.length, ...seriesWithMax.map(item => item.series));
  }

  const memoryRange = maxMemory - minMemory;
  const threshold30 = minMemory + memoryRange * 0.3;
  const threshold60 = minMemory + memoryRange * 0.6;

  // 计算每条系列的最大值（用于双Y轴判断）
  const seriesMaxValues = sortedSeriesData.map(series => {
    let maxValue = -Infinity;
    for (const item of series.data) {
      if (typeof item.cumulativeMemory === 'number' && item.cumulativeMemory > maxValue) {
        maxValue = item.cumulativeMemory;
      }
    }
    return maxValue === -Infinity ? 0 : maxValue;
  });

  return {
    chartData,
    seriesData: sortedSeriesData,
    maxMemory,
    minMemory,
    finalMemory,
    threshold30,
    threshold60,
    seriesMaxValues,
  };
}

/**
 * 根据当前下钻层级加载数据。
 */
async function loadCurrentLevelData() {
  try {
    isLoading.value = true;
    console.log('[MemoryTimelineChart] Loading data for level:', drillDownLevel.value, 'mode:', viewMode.value);

    // 根据下钻级别加载不同的数据
    if (drillDownLevel.value === 'overview') {
      // 总览层级：根据模式加载不同的聚合数据
      const groupBy = viewMode.value === 'process' ? 'process' : 'category';
      currentRecords.value = await fetchOverviewTimeline(props.stepId, groupBy);
    } else if (viewMode.value === 'category') {
      // 分类模式
      if (drillDownLevel.value === 'category') {
        // 大类层级：加载指定大类的记录
        currentRecords.value = await fetchCategoryRecords(props.stepId, selectedCategory.value);
      } else if (drillDownLevel.value === 'subCategory' || drillDownLevel.value === 'file') {
        // 小类层级和文件层级：加载指定小类的所有记录
        // 文件层级会在 processTimelineDataSync 中通过前端过滤
        console.log('[MemoryTimelineChart] Loading subCategory/file data for:', selectedCategory.value, selectedSubCategory.value);
        currentRecords.value = await fetchSubCategoryRecords(
          props.stepId,
          selectedCategory.value,
          selectedSubCategory.value
        );
        console.log('[MemoryTimelineChart] Loaded records:', currentRecords.value.length);
      }
    } else if (viewMode.value === 'process') {
      // 进程模式
      if (drillDownLevel.value === 'process') {
        // 进程层级：加载指定进程的记录
        currentRecords.value = await fetchProcessRecords(props.stepId, selectedProcess.value);
      } else if (drillDownLevel.value === 'thread' || drillDownLevel.value === 'file') {
        // 线程层级和文件层级：加载指定线程的所有记录
        // 文件层级会在 processTimelineDataSync 中通过前端过滤
        console.log('[MemoryTimelineChart] Loading thread/file data for:', selectedProcess.value, selectedThread.value);
        currentRecords.value = await fetchThreadRecords(
          props.stepId,
          selectedProcess.value,
          selectedThread.value
        );
        console.log('[MemoryTimelineChart] Loaded records:', currentRecords.value.length);
      }
    }

  } catch (error) {
    console.error('[MemoryTimelineChart] Failed to load data:', error);
    currentRecords.value = [];
  } finally {
    isLoading.value = false;
    emit(
      'time-point-stats-updated',
      calculateTimePointStats(currentRecords.value, props.selectedTimePoint ?? null)
    );
  }
}

/**
 * 加载并处理数据，随后渲染图表。
 */
async function loadProcessedData() {
  if (currentRecords.value.length === 0) {
    processedData.value = createEmptyProcessedData();
    return;
  }

  try {
    isLoadingData.value = true;
    // Allow the UI a short window to update before heavy processing
    await new Promise(resolve => setTimeout(resolve, 10));

    // Process data on the main thread
    const result = processTimelineDataSync();

    processedData.value = result;
  } catch (error) {
    console.error('[MemoryTimelineChart] Failed to process timeline data:', error);
    processedData.value = createEmptyProcessedData();
  } finally {
    isLoadingData.value = false;
  }
}

async function refreshTimelineChart(): Promise<void> {
  await loadCurrentLevelData();
  await loadProcessedData();
  await renderChart();
}

// 字节数格式化（用于坐标/提示框展示）
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

// 时间格式化（单位：秒，<1 秒显示为毫秒）
function formatTime(seconds: number): string {
  // relativeTs is already converted from nanoseconds to seconds in the store
  if (seconds < 1) {
    return (seconds * 1000).toFixed(2) + ' ms';
  }
  return seconds.toFixed(2) + ' s';
}

function normalizeFileName(fileName?: string | null): string | null {
  if (!fileName || fileName === 'N/A') {
    return null;
  }
  return fileName;
}

/**
 * 为非均匀刻度（对数刻度）调整数值
 *
 * 对数刻度不能处理0或负数，所以需要转换为最小正数
 *
 * @param value 原始数值
 * @param minPositiveValue 最小正数值（默认为1）
 * @returns 调整后的数值
 */
function adjustValueForLogScale(value: number, minPositiveValue: number = 1): number {
  if (value <= 0) {
    return minPositiveValue;
  }
  return value;
}

function getHighlightColor(seriesIndex: number): string {
  return HIGHLIGHT_COLORS[seriesIndex % HIGHLIGHT_COLORS.length];
}

function getSeriesColor(seriesIndex: number, isTotalSeries: boolean): string {
  return isTotalSeries ? HIGHLIGHT_COLORS[0] : SERIES_COLORS[seriesIndex % SERIES_COLORS.length];
}

function buildTooltipHtml(seriesName: string, seriesIndex: number, cumulativeMemory: number): string {
  const color = getHighlightColor(seriesIndex);
  return [
    '<div style="padding: 8px; min-width: 220px;">',
    '  <div style="margin-bottom: 8px;">',
    '    <div style="display: flex; align-items: center; margin-bottom: 4px;">',
    `      <span style="display: inline-block; width: 10px; height: 10px; background-color: ${color}; margin-right: 6px; border-radius: 2px;"></span>`,
    `      <span style="font-weight: bold;">${seriesName}</span>`,
    '    </div>',
    '    <div style="margin-left: 16px; font-size: 12px;">',
    `      <div>当前内存: <span style="color: ${color}; font-weight: bold;">${formatBytes(cumulativeMemory)}</span></div>`,
    '    </div>',
    '  </div>',
    '</div>',
  ].join('');
}

function getSymbolSize(isLargeDataset: boolean, isVeryLargeDataset: boolean): number {
  if (isVeryLargeDataset) return 4;
  if (isLargeDataset) return 6;
  return 8;
}

function getLineWidth(isTotalSeries: boolean, isLargeDataset: boolean, isVeryLargeDataset: boolean): number {
  if (isTotalSeries) {
    if (isVeryLargeDataset) return 2;
    return isLargeDataset ? 3 : 3.5;
  }

  if (isVeryLargeDataset) return 1;
  return isLargeDataset ? 1.5 : 2;
}

type LineSeriesData = NonNullable<LineSeriesOption['data']>;
type LineSeriesDataItem = LineSeriesData[number];

function createSelectedPointConfig(value: number): LineSeriesDataItem {
  return {
    value,
    symbol: 'circle',
    symbolSize: 24,
    itemStyle: {
      color: '#FFD700',
      borderColor: '#fff',
      borderWidth: 5,
      shadowBlur: 30,
      shadowColor: 'rgba(255, 215, 0, 1)',
    },
    label: {
      show: true,
      position: 'top',
      formatter: () => '● 已选中',
      color: '#FFD700',
      fontWeight: 'bold',
      fontSize: 12,
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      padding: [4, 8],
      borderRadius: 4,
      borderColor: '#FFD700',
      borderWidth: 1,
    },
  };
}

function createNormalPointConfig(
  value: number,
  isLargeDataset: boolean,
  isVeryLargeDataset: boolean
): LineSeriesDataItem {
  return {
    value,
    symbolSize: getSymbolSize(isLargeDataset, isVeryLargeDataset),
  };
}

function isAxisTooltipItem(param: unknown): param is AxisTooltipItem {
  if (!param || typeof param !== 'object') {
    return false;
  }
  const candidate = param as AxisTooltipItem;
  return typeof candidate.dataIndex === 'number';
}

function isSeriesClickParam(
  param: unknown
): param is AxisTooltipItem & Required<Pick<AxisTooltipItem, 'dataIndex'>> {
  if (!isAxisTooltipItem(param)) {
    return false;
  }
  const candidate = param as AxisTooltipItem;
  return (typeof candidate.componentType === 'string' || candidate.componentType === undefined) && typeof candidate.dataIndex === 'number';
}


function resolveTooltipParam(
  params: unknown,
  targetSeriesIndex: number | null
): AxisTooltipItem | null {
  const paramsArray = Array.isArray(params) ? params : [params];
  if (paramsArray.length === 0) {
    return null;
  }

  const tooltipItems = paramsArray.filter(isAxisTooltipItem);
  if (tooltipItems.length === 0) {
    return null;
  }

  if (typeof targetSeriesIndex === 'number') {
    const matched = tooltipItems.find(item => item.seriesIndex === targetSeriesIndex);
    if (matched) {
      return matched;
    }
  }

  return tooltipItems[0] ?? null;
}

// 浮点数近似比较函数（对于大数值使用相对误差）
function isApproximatelyEqual(a: number, b: number, epsilon: number = 0.0001): boolean {
  if (a === b) return true;
  if (a === 0 || b === 0) {
    return Math.abs(a - b) < epsilon;
  }
  // 对于大数值，使用相对误差比较
  const relativeError = Math.abs(a - b) / Math.max(Math.abs(a), Math.abs(b));
  return relativeError < epsilon || Math.abs(a - b) < 1; // 允许1字节的绝对误差
}

function buildSeriesPoint(
  item: SeriesPoint | undefined,
  seriesIndex: number,
  params: ChartOptionParams,
  isTotalSeries: boolean
): LineSeriesDataItem {
  if (!item || typeof item.cumulativeMemory !== 'number') {
    return {
      value: yAxisScaleMode.value === 'linear' ? 0 : 1,
      symbolSize: 0,
    };
  }

  const { selectedTimePoint, drillLevel, isLargeDataset, isVeryLargeDataset, selectedSeriesIndex } = params;

  // 对于非均匀刻度，需要处理0和负数
  const isUniformMode = yAxisScaleMode.value === 'linear';
  const displayValue = !isUniformMode
    ? adjustValueForLogScale(item.cumulativeMemory, 1)
    : item.cumulativeMemory;

  // 使用近似比较来判断选中点（处理浮点数精度问题）
  // 在 overview 层级时，只有选中的系列才显示选中点；其他层级时，总内存线或选中的系列显示选中点
  const isSelectedPoint =
    selectedTimePoint !== null &&
    isApproximatelyEqual(item.relativeTs, selectedTimePoint) &&
    (drillLevel === 'overview'
      ? (selectedSeriesIndex === seriesIndex || (isTotalSeries && selectedSeriesIndex === null))
      : (isTotalSeries || selectedSeriesIndex === seriesIndex));

  if (isSelectedPoint) {
    console.log(`[MemoryTimelineChart] Selected point found: seriesIndex=${seriesIndex}, relativeTs=${item.relativeTs}, selectedTimePoint=${selectedTimePoint}`);
    return createSelectedPointConfig(displayValue);
  }

  return createNormalPointConfig(
    displayValue,
    isLargeDataset,
    isVeryLargeDataset
  );
}

function buildSeriesOptions(
  seriesData: TimelineProcessedData['seriesData'],
  params: ChartOptionParams,
  peakTimeIndex: number
): LineSeriesOption[] {
  const { drillLevel, isLargeDataset, isVeryLargeDataset, seriesMaxValues } = params;

  // 判断是否使用分段Y轴
  // 只有在非均匀刻度模式下且数据跨度大时，才使用分段Y轴
  const isUniformMode = yAxisScaleMode.value === 'linear';
  const canUseSegmentedAxis = shouldUseSegmentedYAxis(seriesMaxValues);
  const useSegmentedAxis = !isUniformMode && canUseSegmentedAxis;

  // 在非均匀刻度模式下，过滤掉 overview 层级的总内存线（seriesIndex === 0）
  const filteredSeriesData = seriesData.filter((_, seriesIndex) => {
    if (!isUniformMode && drillLevel === 'overview' && seriesIndex === 0) {
      return false;
    }
    return true;
  });

  return filteredSeriesData.map((series) => {
    // 计算原始的 seriesIndex（用于颜色和其他配置）
    const originalSeriesIndex = seriesData.indexOf(series);
    const isTotalSeries = drillLevel === 'overview' && originalSeriesIndex === 0;
    const seriesColor = getSeriesColor(originalSeriesIndex, isTotalSeries);

    // 如果使用分段Y轴，对数据进行对数变换
    const dataItems = series.data
      .map((item) => {
        const basePoint = buildSeriesPoint(item, originalSeriesIndex, params, isTotalSeries);
        if (useSegmentedAxis && basePoint && typeof basePoint === 'object' && 'value' in basePoint && typeof basePoint.value === 'number') {
          return {
            ...basePoint,
            value: transformValueForSegmentedAxis(basePoint.value),
          } as LineSeriesDataItem;
        }
        return basePoint;
      }) as LineSeriesData;

    // 在所有系列上添加峰值时间的 markLine（所有系列都显示相同的峰值时间点，来自 overview 层级的总内存线）
    let markLine: echarts.MarkLineComponentOption | undefined = undefined;
    if (peakTimeIndex >= 0) {
      // peakTimeIndex 是基于当前层级的 chartData 计算的，直接使用
      if (peakTimeIndex < series.data.length) {
        markLine = {
          symbol: 'none',
          lineStyle: {
            color: '#ff0000',
            width: 2,
            type: 'dashed',
          },
          label: {
            show: false,
          },
          data: [
            {
              xAxis: peakTimeIndex,
            },
          ],
        };
      }
    }

    return {
      name: series.name,
      type: 'line' as const,
      data: dataItems,
      symbol: 'circle',
      showSymbol: true,
      markLine,
      lineStyle: {
        width: getLineWidth(isTotalSeries, isLargeDataset, isVeryLargeDataset),
        color: seriesColor,
        type: 'solid',
      },
      emphasis: {
        disabled: false,
        focus: 'series',
        scale: false,
      },
      progressive: isVeryLargeDataset ? 500 : isLargeDataset ? 1000 : 0,
      progressiveThreshold: isVeryLargeDataset ? 500 : 1000,
      progressiveChunkMode: 'mod' as const,
      z: isTotalSeries ? 10 : 5,
    };
  });
}

function buildChartTitle(
  drillLevel: DrillDownLevel,
  seriesCount: number,
  mode: ViewMode,
  selectedCategoryName: string,
  selectedSubCategoryName: string,
  selectedProcessName: string,
  selectedThreadName: string,
  selectedFileName: string,
): string {
  let title = '内存时间线';

  if (drillLevel === 'overview') {
    const groupCount = Math.max(seriesCount - 1, 0);
    if (mode === 'category') {
      title += ` - 总览 (总内存 + ${groupCount} 个大类)`;
    } else {
      title += ` - 总览 (总内存 + ${groupCount} 个进程)`;
    }
  } else if (mode === 'category') {
    if (drillLevel === 'category') {
      title += ` - ${selectedCategoryName} (${seriesCount} 个小类)`;
    } else if (drillLevel === 'subCategory') {
      title += ` - ${selectedCategoryName} / ${selectedSubCategoryName} (${seriesCount} 个文件)`;
    } else if (drillLevel === 'file') {
      const fileLabel = selectedFileName || '未选择文件';
      title += ` - ${selectedCategoryName} / ${selectedSubCategoryName} / ${fileLabel}`;
    }
  } else {
    if (drillLevel === 'process') {
      title += ` - ${selectedProcessName} (${seriesCount} 个线程)`;
    } else if (drillLevel === 'thread') {
      title += ` - ${selectedProcessName} / ${selectedThreadName} (${seriesCount} 个文件)`;
    } else if (drillLevel === 'file') {
      const fileLabel = selectedFileName || '文件详情';
      title += ` - ${selectedProcessName} / ${selectedThreadName} / ${fileLabel}`;
    }
  }

  return title;
}

function buildChartSubtext(
  drillLevel: DrillDownLevel,
  mode: ViewMode,
  selectedTimePoint: number | null,
  maxMemory: number,
  minMemory: number,
  finalMemory: number
): string {
  const hints: string[] = [];

  if (drillLevel === 'overview') {
    if (mode === 'category') {
      hints.push('💡 点击线条上的点查看大类火焰图');
    } else {
      hints.push('💡 点击线条上的点查看进程火焰图');
    }
  } else if (mode === 'category') {
    if (drillLevel === 'category') {
      hints.push('💡 点击线条上的点查看火焰图');
    } else {
      hints.push('💡 点击线条上的点查看火焰图');
    }
  } else {
    if (drillLevel === 'process') {
      hints.push('💡 点击线条上的点查看线程火焰图');
    } else {
      hints.push('💡 点击线条上的点查看火焰图');
    }
  }

  if (selectedTimePoint !== null) {
    hints.push(`🔸 选中: ${formatTime(selectedTimePoint)}`);
  }

  hints.push(`🔴 峰值: ${formatBytes(maxMemory)}`);
  hints.push(`最低: ${formatBytes(minMemory)}`);
  hints.push(`最终: ${formatBytes(finalMemory)}`);

  return hints.join(' | ');
}

/**
 * 计算非均匀刻度（对数刻度）的最小值
 *
 * 对数刻度需要找到最小的正数值作为下界
 *
 * @param minMemory 数据的最小值
 * @param maxMemory 数据的最大值
 * @returns 对数刻度的最小值
 */
function calculateLogScaleMin(minMemory: number, maxMemory: number): number {
  // 如果最小值是0或负数，使用最大值的1/10000作为最小值
  if (minMemory <= 0) {
    return Math.max(1, maxMemory / 10000);
  }
  // 否则使用最小值的1/10作为下界，确保有足够的显示空间
  return Math.max(1, minMemory / 10);
}

/**
 * 判断是否应该使用分段Y轴
 * 当数据量级差异大于10倍时，使用分段Y轴
 */
function shouldUseSegmentedYAxis(seriesMaxValues: number[]): boolean {
  if (seriesMaxValues.length <= 1) return false;

  const validValues = seriesMaxValues.filter(v => v > 0);
  if (validValues.length <= 1) return false;

  const maxVal = Math.max(...validValues);
  const minVal = Math.min(...validValues);

  return maxVal / minVal > 10;
}

/**
 * 使用对数变换来处理不同量级的数据
 * 这样可以在同一个Y轴上显示大值和小值
 */
function transformValueForSegmentedAxis(value: number): number {
  if (value <= 0) return 0;
  // 使用对数变换：log10(value)
  // 这样 1B -> 0, 1KB -> 3, 1MB -> 6, 1GB -> 9
  return Math.log10(value);
}

/**
 * 反向变换，用于显示原始值
 */
function inverseTransformValue(logValue: number): number {
  return Math.pow(10, logValue);
}

function buildChartOption(params: ChartOptionParams): echarts.EChartsOption {
  const {
    chartData,
    seriesData,
    maxMemory,
    minMemory,
    finalMemory,
    selectedTimePoint,
    drillLevel,
    selectedCategory,
    selectedSubCategory,
    selectedProcess,
    selectedThread,
    selectedFile,
    mode,
    isLargeDataset,
    isVeryLargeDataset,
  } = params;

  // 根据数据量动态设置 X 轴标签的旋转角度与显示步长，避免拥挤重叠
  const totalPoints = chartData.length;
  const xLabelStep = Math.max(1, Math.ceil(totalPoints / 12));
  const xLabelRotate =
    totalPoints > 120 ? 60 :
    totalPoints > 60 ? 45 :
    totalPoints > 36 ? 30 : 0;

  // 只在第一次加载总览层级时计算峰值时间，之后保持不变
  let peakTimeValue = overviewPeakTimeValue;

  if (drillLevel === 'overview' && overviewPeakTimeValue === null && chartData.length > 0) {
    // 第一次加载总览层级时计算峰值
    let maxValue = -Infinity;
    for (let i = 0; i < chartData.length; i++) {
      const item = chartData[i];
      if (typeof item.cumulativeMemory === 'number' && item.cumulativeMemory > maxValue) {
        maxValue = item.cumulativeMemory;
        overviewPeakTimeValue = item.relativeTs;
      }
    }
    peakTimeValue = overviewPeakTimeValue;
  }

  // 根据峰值时间值找到对应的索引（用于 markLine 的 xAxis）
  let peakTimeIndex = -1;
  if (peakTimeValue !== null) {
    peakTimeIndex = chartData.findIndex(item => item.relativeTs === peakTimeValue);
  }

  // 在非均匀刻度模式下，过滤图例数据（排除 overview 层级的总内存线）
  const isUniformMode = yAxisScaleMode.value === 'linear';
  const legendData = seriesData
    .filter((_, index) => {
      if (!isUniformMode && drillLevel === 'overview' && index === 0) {
        return false;
      }
      return true;
    })
    .map(series => series.name);

  return {
    animation: !isLargeDataset,
    animationDuration: isVeryLargeDataset ? 0 : 300,
    animationDurationUpdate: isVeryLargeDataset ? 0 : 300,
    title: {
      text: buildChartTitle(
        drillLevel,
        seriesData.length,
        mode,
        selectedCategory,
        selectedSubCategory,
        selectedProcess,
        selectedThread,
        selectedFile,
      ),
      subtext: buildChartSubtext(
        drillLevel,
        mode,
        selectedTimePoint,
        maxMemory,
        minMemory,
        finalMemory
      ),
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 600,
      },
      subtextStyle: {
        fontSize: 12,
        color: selectedTimePoint !== null ? '#ff9800' : '#666',
        fontWeight: selectedTimePoint !== null ? 'bold' : 'normal',
      },
    },
    legend: {
      type: 'plain',
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      data: legendData,
      textStyle: {
        fontSize: 12,
      },
      itemWidth: 25,
      itemHeight: 14,
      itemGap: 10,
      // 允许图例自动换行显示，设置合适的宽度让图例自动换行
      width: '90%',
      formatter: (name: string) => {
        // 如果名称太长，可以截断
        return name.length > 15 ? name.substring(0, 15) + '...' : name;
      },
    },
    // Place the legend hint above the legend area, centered, to avoid overlapping x-axis
    graphic: [
      {
        type: 'text',
        left: 'center',
        bottom: 30,
        style: {
          text: '提示：双击图例可下钻',
          fill: '#666',
          fontSize: 12,
          fontWeight: 400,
        },
        silent: true,
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        snap: true,
        label: { show: false },
      },
      confine: true,
      appendToBody: false,
      formatter: (params: AxisTooltipItem | AxisTooltipItem[] | unknown) => {
        try {
          const resolved = resolveTooltipParam(params, activeSeriesIndex.value);
          if (!resolved || typeof resolved.dataIndex !== 'number') {
            return '';
          }

          const seriesIndex = typeof resolved.seriesIndex === 'number' ? resolved.seriesIndex : 0;
          const seriesName = resolved.seriesName ?? '';
          const dataIndex = resolved.dataIndex;
          const dataItem = seriesData[seriesIndex]?.data?.[dataIndex];

          if (!dataItem) {
            return '';
          }

          return buildTooltipHtml(seriesName, seriesIndex, dataItem.cumulativeMemory);
        } catch (error) {
          console.error('[MemoryTimelineChart] Tooltip formatter error:', error);
          return '';
        }
      },
    },
    grid: {
      left: '3%',
      right: '3%',
      bottom: '20%', // 为多行图例留出足够的底部空间
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: chartData.map((_, index) => index),
      name: '相对时间',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: {
        // 使用函数来控制哪些刻度显示标签
        interval: (index: number) => {
          // 峰值索引始终显示
          if (peakTimeIndex >= 0 && peakTimeIndex < chartData.length && index === peakTimeIndex) {
            return true;
          }
          // 其他标签按照 xLabelStep 显示
          return index % xLabelStep === 0;
        },
        rotate: xLabelRotate,
        fontSize: 10,
        hideOverlap: false,
        margin: 12,
        formatter: (value: string | number) => {
          const index = typeof value === 'string' ? parseInt(value, 10) : value;
          const item = chartData[index];
          return item ? formatTime(item.relativeTs) : '';
        },
      },
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: '#999',
          type: 'solid',
          width: 1,
        },
        label: {
          show: true,
          formatter: (params: AxisPointerLabelFormatterParams) => {
            const index = typeof params.value === 'string' ? parseInt(params.value, 10) : params.value;
            const item = chartData[index];
            return item ? formatTime(item.relativeTs) : '';
          },
        },
      } as Record<string, unknown>,
    },
    yAxis: (() => {
      /**
       * Y轴配置逻辑
       *
       * 根据用户选择的刻度模式配置Y轴：
       *
       * 1. 均匀刻度模式（yAxisScaleMode === 'linear'）
       *    - Y轴始终不分段，使用均匀刻度
       *    - 适合数据跨度小的情况
       *
       * 2. 非均匀刻度模式（yAxisScaleMode === 'log'）
       *    - 当数据跨度大时（> 10倍），自动使用分段显示
       *    - 当数据跨度小时，使用对数刻度
       *    - 适合数据跨度大的情况
       */
      const isUniformMode = yAxisScaleMode.value === 'linear';
      const canUseSegmentedAxis = shouldUseSegmentedYAxis(params.seriesMaxValues);
      const useSegmentedAxis = !isUniformMode && canUseSegmentedAxis;

      if (useSegmentedAxis) {
        // ========== 分段Y轴配置（非均匀刻度 + 数据跨度大） ==========
        // 当用户选择非均匀刻度且数据跨度很大时，自动使用分段显示
        const validValues = params.seriesMaxValues.filter(v => v > 0);
        const maxVal = Math.max(...validValues);
        const minVal = Math.min(...validValues);

        // 计算对数范围
        const logMax = Math.log10(maxVal);
        const logMin = Math.log10(minVal);

        return {
          type: 'value',
          name: '当前内存 (分段显示)',
          nameLocation: 'middle',
          nameGap: 70,
          axisLabel: {
            // 将对数值转换回原始值显示
            formatter: (value: number) => {
              const originalValue = inverseTransformValue(value);
              return formatBytes(originalValue);
            },
          },
          min: logMin - 1,
          max: logMax + 1,
          splitLine: {
            show: true,
            lineStyle: {
              color: '#e0e0e0',
              width: 1,
            },
          },
          // 添加分段线来区分不同的量级
          splitArea: {
            show: true,
            areaStyle: {
              color: ['rgba(250, 250, 250, 0.3)', 'rgba(200, 200, 200, 0.1)'],
            },
          },
        };
      } else if (isUniformMode) {
        // ========== 均匀刻度配置（不分段） ==========
        // 用户选择均匀刻度，Y轴始终不分段，使用均匀刻度
        return {
          type: 'value',
          name: '当前内存 (均匀刻度)',
          nameLocation: 'middle',
          nameGap: 70,
          axisLabel: {
            formatter: (value: number) => formatBytes(value),
          },
          splitLine: {
            show: true,
            lineStyle: {
              color: '#e0e0e0',
              width: 1,
            },
          },
        };
      } else {
        // ========== 非均匀刻度配置（不分段） ==========
        // 用户选择非均匀刻度但数据跨度小，使用对数刻度
        return {
          type: 'log',
          name: '当前内存 (非均匀刻度)',
          nameLocation: 'middle',
          nameGap: 70,
          axisLabel: {
            formatter: (value: number) => formatBytes(value),
          },
          logBase: 10,
          min: calculateLogScaleMin(minMemory, maxMemory),
          max: maxMemory > 0 ? maxMemory : 1,
          minorTick: {
            show: true,
          },
          minorSplitLine: {
            show: true,
            lineStyle: {
              color: '#f0f0f0',
              width: 0.5,
            },
          },
          splitLine: {
            show: true,
            lineStyle: {
              color: '#e0e0e0',
              width: 1,
            },
          },
        };
      }
    })() as Record<string, unknown>,
    series: buildSeriesOptions(seriesData, params, peakTimeIndex),
  };
}

/**
 * 注册图表事件处理器
 *
 * 事件类型：
 * 1. 鼠标事件（mouseover/mouseout）
 *    - 用于高亮/取消高亮悬停的系列
 *
 * 2. 点击事件（click）
 *    - 用于选择/取消选择时间点
 *
 * 3. 图例事件（legendselectchanged）
 *    - 单击：隐藏/显示线条（ECharts 默认行为）
 *    - 双击：下钻到该系列的详细数据
 */
function registerChartEvents(seriesData: TimelineProcessedData['seriesData']) {
  if (!chartInstance) return;

  // 清除所有之前的事件监听器，避免重复注册
  chartInstance.off('mouseover');
  chartInstance.off('mouseout');
  chartInstance.off('click');
  chartInstance.off('legendselectchanged');

  // ========== 鼠标悬停事件 ==========
  // 当鼠标悬停在线条上时，高亮该系列
  chartInstance.on('mouseover', { seriesType: 'line' }, (event: { seriesIndex?: number }) => {
    if (event && typeof event.seriesIndex === 'number') {
      activeSeriesIndex.value = event.seriesIndex;
    }
  });

  // 当鼠标离开线条时，取消高亮
  chartInstance.on('mouseout', { seriesType: 'line' }, () => {
    activeSeriesIndex.value = null;
  });

  // ========== 线条点击事件 ==========
  // 点击线条上的数据点，选择该时间点
  // 再次点击同一点可取消选择
  chartInstance.on('click', { seriesType: 'line' }, params => {
    handleChartSingleClick(params, seriesData);
  });

  // ========== 图例点击事件 ==========
  // 单击图例：隐藏/显示对应的线条（ECharts 默认行为）
  // 双击图例：下钻到该系列的详细数据
  chartInstance.on('legendselectchanged', params => {
    handleLegendDrillDown(params as LegendClickEvent);
  });
}

/**
 * 处理图表线条点击事件
 * 功能：选择/取消选择时间点
 * - 首次点击：选择该时间点
 * - 再次点击同一点：取消选择
 */
function handleChartSingleClick(params: unknown, seriesData: TimelineProcessedData['seriesData']) {
  // 参数验证
  if (!isSeriesClickParam(params)) {
    return;
  }

  // 确保点击的是线条系列，而不是其他组件
  if (params.componentType && params.componentType !== 'series') {
    return;
  }

  // 获取点击的系列和数据点信息
  const seriesIndex = typeof params.seriesIndex === 'number' ? params.seriesIndex : 0;
  const dataIndex = params.dataIndex;

  // 验证系列索引有效性
  if (seriesIndex < 0 || seriesIndex >= seriesData.length) {
    return;
  }

  const seriesEntry = seriesData[seriesIndex];
  const dataItem = seriesEntry?.data?.[dataIndex];
  if (!dataItem) {
    return;
  }

  // ========== 更新选中时间点 ==========
  // 如果点击的是已选中的点，则取消选择；否则选择该点
  const nextSelected = props.selectedTimePoint === dataItem.relativeTs ? null : dataItem.relativeTs;

  if (nextSelected === null) {
    console.log('[MemoryTimelineChart] Cleared selected time point');
    selectedSeriesIndex.value = null;
    selectedSeriesName.value = '';
  } else {
    console.log('[MemoryTimelineChart] Selected time point:', nextSelected, 'from series:', seriesEntry?.name);
    // 记录点击的系列，用于下游的统计、标线等功能
    selectedSeriesIndex.value = seriesIndex;
    selectedSeriesName.value = seriesEntry?.name ?? '';
  }

  // 发射时间点选择事件
  emit('time-point-selected', nextSelected);

  // ========== 确定上下文信息 ==========
  // 在总览层级时，根据点击的系列确定分类/进程上下文
  let contextCategory = selectedCategory.value;
  let contextProcess = selectedProcess.value;

  if (drillDownLevel.value === 'overview') {
    const seriesName = seriesEntry?.name ?? '';
    // 如果点击的不是总内存线，则更新上下文
    if (seriesIndex !== 0 && seriesName && seriesName !== '总内存') {
      if (viewMode.value === 'category') {
        // 分类模式：系列名称为大类名称
        contextCategory = seriesName;
      } else {
        // 进程模式：系列名称为进程名称
        contextProcess = seriesName;
      }
    }
  }

  // ========== 计算统计信息 ==========
  // 基于点击的系列计算统计信息（分配、释放、净内存等）
  const seriesScopedRecords = getSeriesScopedRecordsForName(seriesEntry?.name ?? '');
  emit('time-point-stats-updated', calculateTimePointStats(seriesScopedRecords, nextSelected));

  // ========== 发射选中点上下文 ==========
  // 供外部组件（如火焰图）使用
  const memoryAtPoint = typeof dataItem.cumulativeMemory === 'number' ? dataItem.cumulativeMemory : 0;
  emit('point-selection-context', {
    timePoint: nextSelected,
    seriesName: seriesEntry?.name ?? '',
    viewMode: viewMode.value,
    drillLevel: drillDownLevel.value,
    selectedCategory: contextCategory,
    selectedSubCategory: selectedSubCategory.value,
    selectedProcess: contextProcess,
    selectedThread: selectedThread.value,
    selectedFile: selectedFile.value,
    memoryAtPoint,
  });
}

/**
 * 图例点击事件参数类型
 */
type LegendClickEvent = {
  selected: Record<string, boolean>;
  name: string;
};

/**
 * ============================================================================
 * 图例事件处理流程说明
 * ============================================================================
 *
 * 当用户点击图例时，ECharts 触发 'legendselectchanged' 事件，流程如下：
 *
 * 1. handleLegendDrillDown(params)
 *    - 接收 ECharts 的 legendselectchanged 事件
 *    - 检测是否为双击（通过时间间隔判断）
 *    - 单击：直接返回，允许 ECharts 默认行为（隐藏/显示线条）
 *    - 双击：调用 handleLegendDoubleClick()
 *
 * 2. handleLegendDoubleClick(seriesName, params)
 *    - 设置处理状态为 true，防止重复处理
 *    - 调用 drillDownBySeriesName(seriesName) 执行下钻
 *    - 如果下钻成功且该系列被隐藏，则显示它
 *    - 最后释放处理状态
 *
 * 3. drillDownBySeriesName(seriesName)
 *    - 根据当前下钻层级和视图模式，决定下钻目标
 *    - 调用相应的下钻函数（如 drillDownToCategory）
 *    - 返回是否成功执行了下钻
 *
 * 4. 下钻函数（如 drillDownToCategory）
 *    - 更新下钻层级和选中的分类/进程等状态
 *    - 触发 watch 监听器，自动加载新数据并重新渲染图表
 *
 * ============================================================================
 * 关键设计点
 * ============================================================================
 *
 * - 单击和双击分离：单击允许 ECharts 默认行为，双击执行下钻
 * - 处理状态锁：防止在数据加载和渲染期间重复处理事件
 * - 清晰的日志：每个关键步骤都有日志输出，便于调试
 * - 模式和层级感知：下钻逻辑根据当前的视图模式和下钻层级动态调整
 *
 * ============================================================================
 */

/**
 * 验证图例点击事件参数的有效性
 */
function isValidLegendClickEvent(params: unknown): params is LegendClickEvent {
  if (!params || typeof params !== 'object') {
    return false;
  }
  const candidate = params as LegendClickEvent;
  return typeof candidate.name === 'string' && typeof candidate.selected === 'object';
}

/**
 * 处理图例点击事件
 *
 * 事件流程：
 * 1. 验证参数有效性
 * 2. 检查是否正在处理其他事件（防止并发）
 * 3. 检测是否为双击
 * 4. 单击：允许 ECharts 默认行为（隐藏/显示线条）
 * 5. 双击：执行下钻操作
 */
function handleLegendDrillDown(params: LegendClickEvent) {
  // 参数验证
  if (!isValidLegendClickEvent(params)) {
    console.warn('[MemoryTimelineChart] Invalid legend click event params');
    return;
  }

  // 如果正在处理其他事件，则忽略此次点击（防止并发处理）
  if (isLegendProcessing() || isLegendSelectionSyncing) {
    console.log('[MemoryTimelineChart] Legend event is being processed, ignoring this click');
    return;
  }

  const seriesName = params.name;
  const currentTime = Date.now();

  // 检测是否为双击（同一个图例项在短时间内被点击两次）
  const isDoubleClick = isLegendDoubleClick(seriesName, currentTime);

  // 单击时：允许图例的显示/隐藏功能正常工作（ECharts 默认行为）
  if (!isDoubleClick) {
    console.log('[MemoryTimelineChart] Legend single click - show/hide series:', seriesName);
    return;
  }

  // 双击时：执行下钻操作
  console.log('[MemoryTimelineChart] Legend double click - drill down:', seriesName);
  handleLegendDoubleClick(seriesName, params);
}

/**
 * 处理图例双击事件 - 执行下钻操作
 *
 * 流程：
 * 1. 设置处理状态为 true，防止并发处理
 * 2. 根据系列名称执行下钻操作
 * 3. 如果下钻成功且该系列被隐藏，则显示它
 * 4. 使用 requestAnimationFrame 确保 UI 更新完成后再释放处理状态
 */
function handleLegendDoubleClick(seriesName: string, params: LegendClickEvent) {
  // 设置处理状态，防止在数据加载和渲染期间重复处理事件
  setLegendProcessing(true);

  try {
    // 根据系列名称执行下钻操作
    const drillDownSucceeded = drillDownBySeriesName(seriesName);

    // 如果下钻成功且该系列当前被隐藏，则显示它
    // 这样用户可以立即看到下钻后的数据
    if (
      drillDownSucceeded &&
      chartInstance &&
      seriesName &&
      params.selected &&
      params.selected[seriesName] === false
    ) {
      try {
        isLegendSelectionSyncing = true;
        chartInstance.dispatchAction({
          type: 'legendSelect',
          name: seriesName,
        });
        console.log('[MemoryTimelineChart] Restored visibility of series:', seriesName);
      } catch (error) {
        console.error('[MemoryTimelineChart] Failed to restore series visibility:', error);
      } finally {
        isLegendSelectionSyncing = false;
      }
    }
  } catch (error) {
    console.error('[MemoryTimelineChart] Error during legend double click handling:', error);
  } finally {
    // 使用 requestAnimationFrame 确保 UI 更新完成后再释放处理状态
    // 这样可以避免在数据加载和渲染期间处理新的事件
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => {
        setLegendProcessing(false);
      });
    } else {
      setTimeout(() => {
        setLegendProcessing(false);
      }, 0);
    }
  }
}

/**
 * 根据系列名称执行下钻操作
 * @param seriesName 系列名称
 * @returns 是否成功执行了下钻操作
 */
function drillDownBySeriesName(seriesName: string): boolean {
  // 参数验证
  if (!seriesName) {
    console.warn('[MemoryTimelineChart] Cannot drill down: empty series name');
    return false;
  }

  // ========== 总览层级 ==========
  if (drillDownLevel.value === 'overview') {
    // 总内存线不支持下钻
    if (seriesName === '总内存') {
      console.log('[MemoryTimelineChart] Cannot drill down from total memory series');
      return false;
    }

    // 根据视图模式下钻到对应的第一层
    if (viewMode.value === 'category') {
      console.log('[MemoryTimelineChart] Drilling down to category:', seriesName);
      drillDownToCategory(seriesName);
      return true;
    } else {
      console.log('[MemoryTimelineChart] Drilling down to process:', seriesName);
      drillDownToProcess(seriesName);
      return true;
    }
  }

  // ========== 分类模式下钻 ==========
  if (viewMode.value === 'category') {
    if (drillDownLevel.value === 'category') {
      console.log('[MemoryTimelineChart] Drilling down to subCategory:', seriesName);
      drillDownToSubCategory(seriesName);
      return true;
    }
    if (drillDownLevel.value === 'subCategory') {
      console.log('[MemoryTimelineChart] Drilling down to file:', seriesName);
      drillDownToFile(seriesName);
      return true;
    }
  }

  // ========== 进程模式下钻 ==========
  if (viewMode.value === 'process') {
    if (drillDownLevel.value === 'process') {
      console.log('[MemoryTimelineChart] Drilling down to thread:', seriesName);
      drillDownToThread(seriesName);
      return true;
    }
    if (drillDownLevel.value === 'thread') {
      console.log('[MemoryTimelineChart] Drilling down to file:', seriesName);
      drillDownToFile(seriesName);
      return true;
    }
  }

  // 无法下钻（已到达最深层级）
  console.log('[MemoryTimelineChart] Cannot drill down further at level:', drillDownLevel.value);
  return false;
}

// Initialize chart
async function renderChart() {
  if (!chartContainer.value) return;

  isLoading.value = true;

  await new Promise(resolve => setTimeout(resolve, 10));

  try {
    if (!chartInstance) {
      chartInstance = echarts.init(chartContainer.value);
    }

    const { chartData, seriesData, maxMemory, minMemory, finalMemory } = processedData.value;
    if (chartData.length === 0) {
      chartInstance.clear();
      return;
    }

    const isLargeDataset = chartData.length > LARGE_DATA_THRESHOLD;
    const isVeryLargeDataset = chartData.length > VERY_LARGE_DATA_THRESHOLD;
    const option = buildChartOption({
      chartData,
      seriesData,
      maxMemory,
      minMemory,
      finalMemory,
      selectedTimePoint: props.selectedTimePoint,
      drillLevel: drillDownLevel.value,
      selectedCategory: selectedCategory.value,
      selectedSubCategory: selectedSubCategory.value,
      selectedProcess: selectedProcess.value,
      selectedThread: selectedThread.value,
      selectedFile: selectedFile.value,
      mode: viewMode.value,
      isLargeDataset,
      isVeryLargeDataset,
      selectedSeriesIndex: selectedSeriesIndex.value,
      seriesMaxValues: processedData.value.seriesMaxValues,
    });

    activeSeriesIndex.value = null;
    chartInstance.clear();
    chartInstance.setOption(option, {
      lazyUpdate: isVeryLargeDataset,
      silent: false,
    });

    registerChartEvents(seriesData);

    if (props.selectedTimePoint !== null) {
      updateMarkLine(chartData);
    }
  } catch (error) {
    console.error('Failed to initialize chart:', error);
  } finally {
    isLoading.value = false;
  }
}

// Update mark line that highlights the selected point
function updateMarkLine(chartData: Array<{ relativeTs: number; cumulativeMemory: number }>) {
  if (!chartInstance) return;

  // 读取当前图表配置
  const option = chartInstance.getOption() as echarts.EChartsOption;
  if (!option || !Array.isArray(option.series) || option.series.length === 0) return;

  // 找到接近选中时间点的索引位置（用于绘制标线）
  let closestIndex = 0;
  let minDiff = Math.abs(chartData[0].relativeTs - (props.selectedTimePoint ?? 0));

  if (props.selectedTimePoint !== null) {
    for (let i = 1; i < chartData.length; i++) {
      const diff = Math.abs(chartData[i].relativeTs - props.selectedTimePoint);
      if (diff < minDiff) {
        minDiff = diff;
        closestIndex = i;
      }
      // Stop searching once we pass the selected time point
      if (chartData[i].relativeTs > props.selectedTimePoint) {
        break;
      }
    }
  }

  // 确定要添加标线的系列：优先使用选中的系列，否则使用第一个系列
  const targetSeriesIndex = typeof selectedSeriesIndex.value === 'number' && selectedSeriesIndex.value < option.series.length
    ? selectedSeriesIndex.value
    : 0;

  // 更新系列的标线
  const updatedSeries = option.series.map((s, index) => {
    const seriesOption = s as echarts.SeriesOption & {
      markLine?: echarts.MarkLineComponentOption;
    };

    // 第一个系列需要特殊处理：保留峰值时间的 markLine
    if (index === 0) {
      // 获取原有的峰值 markLine
      const existingMarkLine = seriesOption.markLine as echarts.MarkLineComponentOption | undefined;

      if (targetSeriesIndex === 0 && props.selectedTimePoint !== null) {
        // 第一个系列被选中，在峰值 markLine 的基础上添加选中点的 markLine
        if (existingMarkLine && existingMarkLine.data) {
          // 只保留峰值线，添加选中点线
          const peakData = Array.isArray(existingMarkLine.data) ? existingMarkLine.data[0] : existingMarkLine.data;
          seriesOption.markLine = {
            ...existingMarkLine,
            data: [
              peakData,
              {
                xAxis: closestIndex,
                lineStyle: {
                  color: '#FFD700',
                  width: 2,
                  type: 'solid',
                },
              },
            ],
          };
        }
      } else {
        // 第一个系列未被选中，只保留峰值 markLine
        if (existingMarkLine) {
          // 只保留第一条线（峰值线）
          const peakData = Array.isArray(existingMarkLine.data) ? existingMarkLine.data[0] : existingMarkLine.data;
          seriesOption.markLine = {
            ...existingMarkLine,
            data: [peakData],
          };
        }
      }
      return seriesOption;
    }

    if (index === targetSeriesIndex && props.selectedTimePoint !== null) {
      // 其他系列被选中，添加选中点的标线
      const markLine: echarts.MarkLineComponentOption = {
        silent: false,
        symbol: ['none', 'none'],
        symbolSize: [0, 0],
        label: {
          show: false,
        },
        lineStyle: {
          color: '#FFD700',
          width: 2,
          type: 'solid',
        },
        data: [
          {
            xAxis: closestIndex,
          },
        ],
      };
      seriesOption.markLine = markLine;
    } else {
      // 清除其他系列的标线
      if (seriesOption.markLine) {
        seriesOption.markLine = undefined;
      }
    }
    return seriesOption;
  });

  chartInstance.setOption({ series: updatedSeries }, { notMerge: false });
}

// 监听选中时间点变化，同步标线与统计信息
watch(
  () => props.selectedTimePoint,
  (newValue) => {
    emit(
      'time-point-stats-updated',
      calculateTimePointStats(
        getSeriesScopedRecordsForName(selectedSeriesName.value || ''),
        newValue ?? null
      )
    );
    if (chartInstance && processedData.value.chartData.length > 0) {
      updateMarkLine(processedData.value.chartData);
    }
  }
);

/**
 * 根据当前下钻层级与模式，获取与系列名称匹配的数据子集。
 */
function getSeriesScopedRecordsForName(seriesName: string): NativeMemoryRecord[] {
  if (!seriesName) {
    // 系列未知时回退为当前全部记录
    return currentRecords.value;
  }
  const sortedRecords = currentRecords.value.slice().sort((a, b) => a.relativeTs - b.relativeTs);

  if (viewMode.value === 'category') {
    if (drillDownLevel.value === 'category') {
      // 系列为小类
      return sortedRecords.filter(
        r => r.categoryName === selectedCategory.value && r.subCategoryName === seriesName
      );
    }
    if (drillDownLevel.value === 'subCategory' || drillDownLevel.value === 'file') {
      // 系列为文件名
      return sortedRecords.filter(
        r =>
          r.categoryName === selectedCategory.value &&
          r.subCategoryName === selectedSubCategory.value &&
          normalizeFileName(r.file) === seriesName
      );
    }
  } else {
    if (drillDownLevel.value === 'process') {
      // 系列为线程
      return sortedRecords.filter(r => r.process === selectedProcess.value && (r.thread || 'Unknown Thread') === seriesName);
    }
    if (drillDownLevel.value === 'thread' || drillDownLevel.value === 'file') {
      // 系列为文件名
      return sortedRecords.filter(
        r =>
          r.process === selectedProcess.value &&
          r.thread === selectedThread.value &&
          normalizeFileName(r.file) === seriesName
      );
    }
  }
  return sortedRecords;
}

// Reload data when the step id changes
watch(
  () => props.stepId,
  async () => {
    // Reset drill-down state
    drillDownLevel.value = 'overview';
    selectedCategory.value = '';
    selectedSubCategory.value = '';
    selectedFile.value = '';

    await refreshTimelineChart();
  }
);

// Reload data whenever drill-down state changes
watch(
  [viewMode, drillDownLevel, selectedCategory, selectedSubCategory, selectedProcess, selectedThread, selectedFile],
  async () => {
    await refreshTimelineChart();
  }
);

// Debounced window resize handling
let resizeTimer: number | null = null;
const handleResize = () => {
  if (resizeTimer) {
    clearTimeout(resizeTimer);
  }
  resizeTimer = window.setTimeout(() => {
    if (chartInstance) {
      chartInstance.resize();
    }
    resizeTimer = null;
  }, 200); // 200ms debounce
};

onMounted(async () => {
  // Load current-level data first
  await loadCurrentLevelData();

  // Then process the dataset
  await loadProcessedData();

  // Delay initialization slightly to avoid blocking rendering
  requestAnimationFrame(() => {
    renderChart();
  });
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (resizeTimer) {
    clearTimeout(resizeTimer);
    resizeTimer = null;
  }
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.memory-timeline-chart {
  display: flex;
  flex-direction: column;
}

/* Chart container styles */
</style>

