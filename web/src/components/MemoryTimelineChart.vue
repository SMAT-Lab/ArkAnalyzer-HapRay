<template>
  <div class="memory-timeline-chart">
    <div style="position: relative; width: 100%;">
      <div
        style="position: absolute; top: 10px; right: 10px; z-index: 100;"
      >
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

// 分类模式状态
const selectedCategory = ref<string>('');
const selectedSubCategory = ref<string>('');

// 进程模式状态
const selectedProcess = ref<string>('');
const selectedThread = ref<string>('');
const selectedFile = ref<string>('');
const activeSeriesIndex = ref<number | null>(null);
let isLegendSelectionSyncing = false;
let legendDrillDownLock = false;
// 记录点击点所属的系列，便于下游（统计、火焰图）基于正确的系列上下文工作
const selectedSeriesIndex = ref<number | null>(null);
const selectedSeriesName = ref<string>('');

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
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

// 分类模式导航
function backToCategory() {
  drillDownLevel.value = 'category';
  selectedSubCategory.value = '';
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function backToSubCategory() {
  drillDownLevel.value = 'subCategory';
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToCategory(categoryName: string) {
  drillDownLevel.value = 'category';
  selectedCategory.value = categoryName;
  selectedSubCategory.value = '';
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToSubCategory(subCategoryName: string) {
  drillDownLevel.value = 'subCategory';
  selectedSubCategory.value = subCategoryName;
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function backToProcess() {
  drillDownLevel.value = 'process';
  selectedThread.value = '';
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function backToThread() {
  drillDownLevel.value = 'thread';
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToProcess(processName: string) {
  drillDownLevel.value = 'process';
  selectedProcess.value = processName;
  selectedThread.value = '';
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToThread(threadName: string) {
  drillDownLevel.value = 'thread';
  selectedThread.value = threadName;
  selectedFile.value = '';
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToFile(fileName: string) {
  drillDownLevel.value = 'file';
  selectedFile.value = fileName;
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
  const allTimePoints = new Set<number>();
  filteredRecords.forEach(record => allTimePoints.add(record.relativeTs));
  const sortedTimePoints = Array.from(allTimePoints).sort((a, b) => a - b);

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

  const memoryRange = maxMemory - minMemory;
  const threshold30 = minMemory + memoryRange * 0.3;
  const threshold60 = minMemory + memoryRange * 0.6;

  return {
    chartData,
    seriesData,
    maxMemory,
    minMemory,
    finalMemory,
    threshold30,
    threshold60,
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

function createPeakPointConfig(value: number): LineSeriesDataItem {
  return {
    value,
    itemStyle: {
      color: '#ff0000',
      borderColor: '#fff',
      borderWidth: 3,
      shadowBlur: 20,
      shadowColor: 'rgba(255, 0, 0, 0.8)',
    },
    symbolSize: 18,
    label: {
      show: true,
      position: 'top',
      formatter: () => '● 峰值',
      color: '#ff0000',
      fontWeight: 'bold',
      fontSize: 12,
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      padding: [4, 8],
      borderRadius: 4,
      borderColor: '#ff0000',
      borderWidth: 1,
    },
  };
}

function createSelectedPointConfig(value: number): LineSeriesDataItem {
  return {
    value,
    itemStyle: {
      color: '#FFD700',
      borderColor: '#fff',
      borderWidth: 5,
      shadowBlur: 30,
      shadowColor: 'rgba(255, 215, 0, 1)',
    },
    symbolSize: 24,
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

function buildSeriesPoint(
  item: SeriesPoint | undefined,
  itemIndex: number,
  seriesIndex: number,
  params: ChartOptionParams,
  isTotalSeries: boolean
): LineSeriesDataItem {
  if (!item || typeof item.cumulativeMemory !== 'number') {
    return {
      value: 0,
      symbolSize: 0,
    };
  }

  const { maxMemory, selectedTimePoint, drillLevel, isLargeDataset, isVeryLargeDataset } = params;
  const isPeakPoint = item.cumulativeMemory === maxMemory;
  const isSelectedPoint =
    selectedTimePoint !== null &&
    item.relativeTs === selectedTimePoint &&
    (drillLevel !== 'overview' || isTotalSeries);

  if (isPeakPoint) {
    return createPeakPointConfig(item.cumulativeMemory);
  }

  if (isSelectedPoint) {
    return createSelectedPointConfig(item.cumulativeMemory);
  }

  return createNormalPointConfig(
    item.cumulativeMemory,
    isLargeDataset,
    isVeryLargeDataset
  );
}

function buildSeriesOptions(
  seriesData: TimelineProcessedData['seriesData'],
  params: ChartOptionParams
): LineSeriesOption[] {
  const { drillLevel, isLargeDataset, isVeryLargeDataset } = params;

  return seriesData.map((series, seriesIndex) => {
    const isTotalSeries = drillLevel === 'overview' && seriesIndex === 0;
    const seriesColor = getSeriesColor(seriesIndex, isTotalSeries);
    const dataItems = series.data
      .map((item, itemIndex) => buildSeriesPoint(item, itemIndex, seriesIndex, params, isTotalSeries)) as LineSeriesData;

    return {
      name: series.name,
      type: 'line' as const,
      data: dataItems,
      symbol: 'circle',
      showSymbol: true,
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
      hints.push('💡 双击线条查看大类详情');
    } else {
      hints.push('💡 双击线条查看进程详情');
    }
  } else if (mode === 'category') {
    if (drillLevel === 'category') {
      hints.push('💡 双击线条查看小类详情');
    } else {
      hints.push('💡 点击数据点选择时间点');
      hints.push('📁 图例可按文件筛选');
    }
  } else {
    if (drillLevel === 'process') {
      hints.push('💡 双击线条查看线程详情');
    } else {
      hints.push('💡 点击数据点选择时间点');
      hints.push('📁 图例可按文件筛选');
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
      type: 'scroll',
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      data: seriesData.map(series => series.name),
      textStyle: {
        fontSize: 12,
      },
      pageButtonItemGap: 5,
      pageButtonGap: 20,
      pageIconSize: 12,
      pageTextStyle: {
        fontSize: 12,
      },
    },
    // Place the legend hint above the legend area, centered, to avoid overlapping x-axis
    graphic: [
      {
        type: 'text',
        left: 'center',
        bottom: 30,
        style: {
          text: '提示：点击图例可下钻',
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
        // 每隔若干个刻度显示一个标签，配合旋转与自动隐藏，保证可读性
        interval: (index: number) => index % xLabelStep === 0,
        rotate: xLabelRotate,
        fontSize: 10,
        hideOverlap: true,
        margin: 12,
        formatter: (value: string | number) => {
          const index = typeof value === 'string' ? parseInt(value, 10) : value;
          const item = chartData[index];
          return item ? formatTime(item.relativeTs) : '';
        },
      },
    },
    yAxis: {
      type: 'value',
      name: '当前内存',
      nameLocation: 'middle',
      nameGap: 70,
      axisLabel: {
        formatter: (value: number) => formatBytes(value),
      },
    },
    series: buildSeriesOptions(seriesData, params),
  };
}

function registerChartEvents(seriesData: TimelineProcessedData['seriesData']) {
  if (!chartInstance) return;

  chartInstance.off('mouseover');
  chartInstance.off('mouseout');
  chartInstance.off('click');

  chartInstance.on('mouseover', { seriesType: 'line' }, (event: { seriesIndex?: number }) => {
    if (event && typeof event.seriesIndex === 'number') {
      activeSeriesIndex.value = event.seriesIndex;
    }
  });

  chartInstance.on('mouseout', { seriesType: 'line' }, () => {
    activeSeriesIndex.value = null;
  });

  chartInstance.on('click', { seriesType: 'line' }, params => handleChartSingleClick(params, seriesData));
  chartInstance.on('legendselectchanged', params => handleLegendDrillDown(params as LegendClickEvent));
}

function handleChartSingleClick(params: unknown, seriesData: TimelineProcessedData['seriesData']) {
  if (!isSeriesClickParam(params)) {
    return;
  }

  if (params.componentType && params.componentType !== 'series') {
    return;
  }

  const seriesIndex = typeof params.seriesIndex === 'number' ? params.seriesIndex : 0;
  const dataIndex = params.dataIndex;
  if (seriesIndex < 0 || seriesIndex >= seriesData.length) {
    return;
  }

  const seriesEntry = seriesData[seriesIndex];
  const dataItem = seriesEntry?.data?.[dataIndex];
  if (!dataItem) {
    return;
  }

  if (drillDownLevel.value === 'overview') {
    return;
  }

  const nextSelected = props.selectedTimePoint === dataItem.relativeTs ? null : dataItem.relativeTs;

  if (nextSelected === null) {
    console.log('[MemoryTimelineChart] Cleared selected time point');
    selectedSeriesIndex.value = null;
    selectedSeriesName.value = '';
  } else {
    console.log('[MemoryTimelineChart] Selected time point:', nextSelected);
    // Remember the clicked series for downstream context (stats, markLine memory, etc.)
    selectedSeriesIndex.value = seriesIndex;
    selectedSeriesName.value = seriesEntry?.name ?? '';
  }
  emit('time-point-selected', nextSelected);
  // Compute stats based on the clicked series only to reflect the correct "current memory"
  const seriesScopedRecords = getSeriesScopedRecordsForName(seriesEntry?.name ?? '');
  emit('time-point-stats-updated', calculateTimePointStats(seriesScopedRecords, nextSelected));

  // 发射选中点上下文，供外部“已选中时间点”与火焰图使用
  const memoryAtPoint = typeof dataItem.cumulativeMemory === 'number' ? dataItem.cumulativeMemory : 0;
  emit('point-selection-context', {
    timePoint: nextSelected,
    seriesName: seriesEntry?.name ?? '',
    viewMode: viewMode.value,
    drillLevel: drillDownLevel.value,
    selectedCategory: selectedCategory.value,
    selectedSubCategory: selectedSubCategory.value,
    selectedProcess: selectedProcess.value,
    selectedThread: selectedThread.value,
    selectedFile: selectedFile.value,
    memoryAtPoint,
  });
}

type LegendClickEvent = {
  selected: Record<string, boolean>;
  name: string;
};

function handleLegendDrillDown(params: LegendClickEvent) {
  if (!params || typeof params !== 'object' || isLegendSelectionSyncing || legendDrillDownLock) {
    return;
  }

  legendDrillDownLock = true;

  const seriesName = params.name;
  const skip = drillDownBySeriesName(seriesName);

  if (
    chartInstance &&
    seriesName &&
    !skip &&
    params.selected &&
    params.selected[seriesName] === false
  ) {
    try {
      isLegendSelectionSyncing = true;
      chartInstance.dispatchAction({
        type: 'legendSelect',
        name: seriesName,
      });
    } finally {
      isLegendSelectionSyncing = false;
    }
  }

  const releaseLock = () => {
    legendDrillDownLock = false;
  };

  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(releaseLock);
  } else {
    setTimeout(releaseLock, 0);
  }
}

function drillDownBySeriesName(seriesName: string): boolean {
  if (!seriesName) {
    return false;
  }

  if (drillDownLevel.value === 'overview') {
    if (seriesName === '总内存') {
      return false;
    }
    if (viewMode.value === 'category') {
      drillDownToCategory(seriesName);
    } else {
      drillDownToProcess(seriesName);
    }
    return true;
  }

  if (viewMode.value === 'category') {
    if (drillDownLevel.value === 'category') {
      drillDownToSubCategory(seriesName);
      return true;
    }
    if (drillDownLevel.value === 'subCategory') {
      drillDownToFile(seriesName);
      return true;
    }
  } else {
    if (drillDownLevel.value === 'process') {
      drillDownToThread(seriesName);
      return true;
    }
    if (drillDownLevel.value === 'thread') {
      drillDownToFile(seriesName);
      return true;
    }
  }

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
  if (!chartInstance || props.selectedTimePoint === null) return;

  // 找到接近选中时间点的索引位置（用于绘制标线）
  let closestIndex = 0;
  let minDiff = Math.abs(chartData[0].relativeTs - props.selectedTimePoint);

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

  // 读取当前图表配置
  const option = chartInstance.getOption() as echarts.EChartsOption;
  if (option && Array.isArray(option.series) && option.series[0]) {
    const series = option.series[0] as echarts.SeriesOption & {
      markLine?: echarts.MarkLineComponentOption;
    };
    // Prefer displaying the selected series' memory at this index if available; fallback to total
    let selectedMemory = chartData[closestIndex]?.cumulativeMemory || 0;
    if (
      Array.isArray(option.series) &&
      typeof selectedSeriesIndex.value === 'number' &&
      option.series[selectedSeriesIndex.value]
    ) {
      const s = option.series[selectedSeriesIndex.value] as echarts.SeriesOption & {
        data?: Array<number | { value?: number } | LineSeriesDataItem>;
      };
      const point = Array.isArray(s.data) ? (s.data[closestIndex] as unknown) : null;
      let value: number | null = null;
      if (typeof point === 'number') {
        value = point as number;
      } else if (point && typeof point === 'object') {
        const obj = point as { value?: number };
        if (typeof obj.value === 'number') {
          value = obj.value;
        }
      }
      if (typeof value === 'number') {
        selectedMemory = value;
      }
    }
    const markLine: echarts.MarkLineComponentOption = {
      silent: false,
      symbol: ['none', 'arrow'],
      symbolSize: [0, 8],
      label: {
        show: true,
        position: 'end',
        formatter: `选中: ${formatTime(props.selectedTimePoint)}\n内存: ${formatBytes(selectedMemory)}`,
        color: '#333',
        backgroundColor: '#FFD700',
        padding: [6, 10],
        borderRadius: 4,
        fontSize: 12,
        fontWeight: 'bold',
      },
      lineStyle: {
        color: '#FFD700',
        width: 3,
        type: 'solid',
        shadowBlur: 10,
        shadowColor: 'rgba(255, 215, 0, 0.5)',
      },
      data: [
        {
          xAxis: closestIndex,
        },
      ],
    };
    series.markLine = markLine;

    chartInstance.setOption(option);
  }
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

