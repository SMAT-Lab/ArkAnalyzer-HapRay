<template>
  <div class="memory-timeline-chart">
    <div style="position: relative; width: 100%;">
      <!-- 模式切换按钮 -->
      <div style="position: absolute; top: 10px; right: 10px; z-index: 100;">
        <el-radio-group v-model="viewMode" size="small" @change="handleViewModeChange">
          <el-radio-button label="category">分类模式</el-radio-button>
          <el-radio-button label="process">进程模式</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 面包屑导航 -->
      <div
        v-if="drillDownLevel !== 'overview'"
        style="margin-bottom: 10px; padding: 10px; background: #f5f5f5; border-radius: 4px;"
      >
        <el-breadcrumb separator="/">
          <el-breadcrumb-item>
            <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="resetDrillDown">
              <i class="el-icon-s-home"></i> 总览
            </a>
          </el-breadcrumb-item>
          <!-- 分类模式面包屑 -->
          <template v-if="viewMode === 'category'">
            <el-breadcrumb-item v-if="drillDownLevel === 'category'">
              <span style="font-weight: 600; color: #333;">{{ selectedCategory }}</span>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'subCategory' || drillDownLevel === 'file'">
              <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="backToCategory">
                {{ selectedCategory }}
              </a>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'subCategory'">
              <span style="font-weight: 600; color: #333;">{{ selectedSubCategory }}</span>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="backToSubCategory">
                {{ selectedSubCategory }}
              </a>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <span style="font-weight: 600; color: #333;">{{ selectedFile }}</span>
            </el-breadcrumb-item>
          </template>
          <!-- 进程模式面包屑 -->
          <template v-else>
            <el-breadcrumb-item v-if="drillDownLevel === 'process'">
              <span style="font-weight: 600; color: #333;">{{ selectedProcess }}</span>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'thread' || drillDownLevel === 'file'">
              <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="backToProcess">
                {{ selectedProcess }}
              </a>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'thread'">
              <span style="font-weight: 600; color: #333;">{{ selectedThread }}</span>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="drillDownLevel === 'file'">
              <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="backToThread">
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
    <MemoryOutstandingFlameGraph
      v-if="shouldShowOutstandingFlameGraph"
      :step-id="props.stepId"
      :selected-time-point="props.selectedTimePoint"
      :drill-level="drillDownLevel"
      :view-mode="viewMode"
      :selected-category="selectedCategory"
      :selected-sub-category="selectedSubCategory"
      :selected-process="selectedProcess"
      :selected-thread="selectedThread"
    />
  </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import type { LineSeriesOption } from 'echarts';
import type { NativeMemoryRecord } from '@/stores/nativeMemory';
import {
  fetchOverviewTimeline,
  fetchCategoryRecords,
  fetchSubCategoryRecords,
  fetchProcessRecords,
  fetchThreadRecords
} from '@/stores/nativeMemory';
import MemoryOutstandingFlameGraph from './MemoryOutstandingFlameGraph.vue';

// 时间线数据处理结果类型
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
      eventCount?: number;  // 聚合的事件数量
      eventDetails?: string;  // 聚合的事件详情
    }>;
  }>;
  maxMemory: number;
  minMemory: number;
  finalMemory: number;
  threshold30: number;
  threshold60: number;
}

interface TimePointStats {
  eventCount: number;
  allocCount: number;
  freeCount: number;
  netMemory: number;
}

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
interface SeriesGroup {
  name: string;
  records: NativeMemoryRecord[];
}

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
  isLargeDataset: boolean;
  isVeryLargeDataset: boolean;
}

const DEFAULT_CHART_HEIGHT = '300px';
const LARGE_DATA_THRESHOLD = 10_000;
const VERY_LARGE_DATA_THRESHOLD = 50_000;
const SERIES_COLORS = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
const HIGHLIGHT_COLORS = ['#333333', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
const MAX_SERIES_IN_CATEGORY_VIEW = 10;
const MAX_SERIES_IN_FILE_VIEW = 15;

interface Props {
  stepId: string; // 步骤 ID，例如 "step1"
  height?: string;
  selectedTimePoint?: number | null; // 当前选中的时间点
}

const props = withDefaults(defineProps<Props>(), {
  height: DEFAULT_CHART_HEIGHT,
  selectedTimePoint: null,
});

// 定义 emit 事件
const emit = defineEmits<{
  'time-point-selected': [timePoint: number | null];
  'time-point-stats-updated': [stats: TimePointStats];
}>();

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const isLoading = ref(false);

// 当前加载的记录数据（按需加载）
const currentRecords = ref<NativeMemoryRecord[]>([]);

// 视图模式：分类模式 vs 进程模式
type ViewMode = 'category' | 'process';
const viewMode = ref<ViewMode>('category');

// 下钻状态管理
type DrillDownLevel = 'overview' | 'category' | 'subCategory' | 'process' | 'thread' | 'file';
const drillDownLevel = ref<DrillDownLevel>('overview');

// 分类模式状态
const selectedCategory = ref<string>('');
const selectedSubCategory = ref<string>('');

// 进程模式状态
const selectedProcess = ref<string>('');
const selectedThread = ref<string>('');
const selectedFile = ref<string>('');

const activeSeriesIndex = ref<number | null>(null);

const shouldShowOutstandingFlameGraph = computed(() => drillDownLevel.value !== 'overview');

// 模式切换处理
function handleViewModeChange() {
  // 切换模式时重置到总览
  resetDrillDown();
}

// 下钻导航函数
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
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToSubCategory(subCategoryName: string) {
  drillDownLevel.value = 'subCategory';
  selectedSubCategory.value = subCategoryName;
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

function drillDownToCategoryFile(fileName: string) {
  drillDownLevel.value = 'file';
  selectedFile.value = fileName;
  emit('time-point-selected', null);
  emit('time-point-stats-updated', createEmptyTimePointStats());
}

// 进程模式导航
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

// 加载状态
const isLoadingData = ref(false);

/**
 * 计算累计内存
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
 * 处理时间线数据（主线程版本）
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
      // 分类模式：按大类分组（排除 UNKNOWN）
      // 数据已经从后端按 categoryName 聚合，直接使用
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
      // 进程模式：按进程分组
      // 数据已经从后端按 process 聚合，直接使用
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

      // 检查前几条记录的文件信息
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

      // 检查前几条记录的文件信息
      const sampleRecords = filteredRecords.slice(0, 5);
      console.log('[MemoryTimelineChart] Sample records:', sampleRecords.map(r => ({
        file: r.file,
        normalized: normalizeFileName(r.file),
        process: r.process,
        thread: r.thread
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

      console.log('[MemoryTimelineChart] Thread level - null/NA files:', nullFileCount);
      console.log('[MemoryTimelineChart] Thread level - unique files:', Array.from(fileMap.keys()));

      const fileSeriesGroups = Array.from(fileMap.entries()).map(([name, records]) => ({ name, records }));
      seriesGroups = selectTopGroupsByFinalMemory(fileSeriesGroups, MAX_SERIES_IN_FILE_VIEW);
      console.log('[MemoryTimelineChart] Thread level - file groups after selection:', seriesGroups.length, 'files');
    } else if (drillDownLevel.value === 'file') {
      // 文件视图：显示单个文件的详细数据
      seriesGroups = [{ name: selectedFile.value, records: filteredRecords }];
    }
  }

  // 收集所有唯一时间点
  const allTimePoints = new Set<number>();
  filteredRecords.forEach(record => allTimePoints.add(record.relativeTs));
  const sortedTimePoints = Array.from(allTimePoints).sort((a, b) => a - b);

  // 为每个系列计算累计内存
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

  // 构建图表数据
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
 * 加载当前层级的数据
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
 * 加载处理后的数据
 */
async function loadProcessedData() {
  if (currentRecords.value.length === 0) {
    processedData.value = createEmptyProcessedData();
    return;
  }

  try {
    isLoadingData.value = true;
    // 使用 setTimeout 让 UI 有机会更新
    await new Promise(resolve => setTimeout(resolve, 10));

    // 在主线程中处理数据
    const result = processTimelineDataSync();

    processedData.value = result;
  } catch (error) {
    console.error('[MemoryTimelineChart] Failed to process timeline data:', error);
    processedData.value = createEmptyProcessedData();
  } finally {
    isLoadingData.value = false;
  }
}

// 格式化字节大小
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

// 格式化时间（秒）
function formatTime(seconds: number): string {
  // relativeTs 在 store 中已经从纳秒转换为秒了
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
    return isLargeDataset ? 2.5 : 3;
  }

  if (isVeryLargeDataset) return 0.8;
  return isLargeDataset ? 1 : 1.5;
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

function getNativeClickDetail(param: unknown): number {
  if (!param || typeof param !== 'object') {
    return 1;
  }
  const candidate = param as { event?: { event?: { detail?: number } } };
  const detail = candidate.event?.event?.detail;
  return typeof detail === 'number' ? detail : 1;
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
  selectedThreadName: string
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
    }
  } else {
    if (drillLevel === 'process') {
      title += ` - ${selectedProcessName} (${seriesCount} 个线程)`;
    } else if (drillLevel === 'thread') {
      title += ` - ${selectedProcessName} / ${selectedThreadName} (${seriesCount} 个文件)`;
    } else if (drillLevel === 'file') {
      title += ` - ${selectedProcessName} / ${selectedThreadName} / 文件详情`;
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
    isLargeDataset,
    isVeryLargeDataset,
  } = params;

  return {
    animation: !isLargeDataset,
    animationDuration: isVeryLargeDataset ? 0 : 300,
    animationDurationUpdate: isVeryLargeDataset ? 0 : 300,
    title: {
      text: buildChartTitle(
        drillLevel,
        seriesData.length,
        viewMode.value,
        selectedCategory,
        selectedSubCategory,
        selectedProcess.value,
        selectedThread.value
      ),
      subtext: buildChartSubtext(
        drillLevel,
        viewMode.value,
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
      orient: 'vertical',
      right: 10,
      top: 'middle',
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
      right: '15%',
      bottom: '8%',
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
        interval: 'auto',
        rotate: 0,
        fontSize: 10,
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
  chartInstance.off('dblclick');

  chartInstance.on('mouseover', { seriesType: 'line' }, (event: { seriesIndex?: number }) => {
    if (event && typeof event.seriesIndex === 'number') {
      activeSeriesIndex.value = event.seriesIndex;
    }
  });

  chartInstance.on('mouseout', { seriesType: 'line' }, () => {
    activeSeriesIndex.value = null;
  });

  chartInstance.off('click');
  chartInstance.on('click', params => handleChartClick(params, seriesData));
  chartInstance.on('dblclick', params => handleChartDoubleClick(params));
}

function handleChartClick(params: unknown, seriesData: TimelineProcessedData['seriesData']) {
  if (!isSeriesClickParam(params) || params.componentType !== 'series') {
    return;
  }

  const clickDetail = getNativeClickDetail(params);
  if (clickDetail > 1) {
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
  } else {
    console.log('[MemoryTimelineChart] Selected time point:', nextSelected);
  }
  emit('time-point-selected', nextSelected);
  emit('time-point-stats-updated', calculateTimePointStats(currentRecords.value, nextSelected));
}

function handleChartDoubleClick(params: unknown) {
  if (!isSeriesClickParam(params) || params.componentType !== 'series') {
    return;
  }

  const seriesName = params.seriesName ?? '';
  console.log('[MemoryTimelineChart] Double click:', {
    drillDownLevel: drillDownLevel.value,
    viewMode: viewMode.value,
    seriesName,
  });

  if (drillDownLevel.value === 'overview') {
    if (seriesName && seriesName !== '总内存') {
      if (viewMode.value === 'category') {
        drillDownToCategory(seriesName);
      } else {
        drillDownToProcess(seriesName);
      }
    }
    return;
  }

  if (viewMode.value === 'category') {
    if (drillDownLevel.value === 'category') {
      if (seriesName) {
        console.log('[MemoryTimelineChart] Drilling down to subCategory:', seriesName);
        drillDownToSubCategory(seriesName);
      }
    } else if (drillDownLevel.value === 'subCategory') {
      if (seriesName) {
        console.log('[MemoryTimelineChart] Drilling down to file:', seriesName);
        drillDownToCategoryFile(seriesName);
      }
    }
  } else {
    if (drillDownLevel.value === 'process') {
      if (seriesName) {
        console.log('[MemoryTimelineChart] Drilling down to thread:', seriesName);
        drillDownToThread(seriesName);
      }
    } else if (drillDownLevel.value === 'thread') {
      if (seriesName) {
        console.log('[MemoryTimelineChart] Drilling down to file:', seriesName);
        drillDownToFile(seriesName);
      }
    }
  }
}

// 初始化图表
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
    console.error('初始化图表失败:', error);
  } finally {
    isLoading.value = false;
  }
}

// 更新标记线
function updateMarkLine(chartData: Array<{ relativeTs: number; cumulativeMemory: number }>) {
  if (!chartInstance || props.selectedTimePoint === null) return;

  // 找到最接近选中时间点的数据索引
  let closestIndex = 0;
  let minDiff = Math.abs(chartData[0].relativeTs - props.selectedTimePoint);

  for (let i = 1; i < chartData.length; i++) {
    const diff = Math.abs(chartData[i].relativeTs - props.selectedTimePoint);
    if (diff < minDiff) {
      minDiff = diff;
      closestIndex = i;
    }
    // 如果时间已经超过选中点，可以提前退出
    if (chartData[i].relativeTs > props.selectedTimePoint) {
      break;
    }
  }

  // 获取当前配置
  const option = chartInstance.getOption() as echarts.EChartsOption;
  if (option && Array.isArray(option.series) && option.series[0]) {
    const series = option.series[0] as echarts.SeriesOption & {
      markLine?: echarts.MarkLineComponentOption;
    };
    const selectedMemory = chartData[closestIndex]?.cumulativeMemory || 0;
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

// 监听 selectedTimePoint 的变化，更新标记线
watch(
  () => props.selectedTimePoint,
  (newValue) => {
    emit(
      'time-point-stats-updated',
      calculateTimePointStats(currentRecords.value, newValue ?? null)
    );
    if (chartInstance && processedData.value.chartData.length > 0) {
      updateMarkLine(processedData.value.chartData);
    }
  }
);

// 监听 stepId 变化，重新加载数据
watch(
  () => props.stepId,
  async () => {
    // 重置下钻状态
    drillDownLevel.value = 'overview';
    selectedCategory.value = '';
    selectedSubCategory.value = '';

    // 加载新步骤的数据
    await loadCurrentLevelData();
    await loadProcessedData();
    if (chartInstance) {
      renderChart();
    }
  }
);

// 监听下钻状态的变化，重新加载数据并初始化图表
watch(
  [viewMode, drillDownLevel, selectedCategory, selectedSubCategory, selectedProcess, selectedThread, selectedFile],
  async () => {
    await loadCurrentLevelData();
    await loadProcessedData();
    if (chartInstance) {
      renderChart();
    }
  }
);

// 监听窗口大小变化（使用防抖）
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
  }, 200); // 200ms 防抖
};

onMounted(async () => {
  // 先加载当前层级的数据
  await loadCurrentLevelData();

  // 然后处理数据
  await loadProcessedData();

  // 使用 requestAnimationFrame 延迟初始化，避免阻塞页面渲染
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

/* 图表容器样式 */
</style>

