<template>
  <div class="native-memory-container">
    <!-- 无数据提示 -->
    <div v-if="!hasData" class="no-data-tip">
      <el-empty description="暂无内存分析数据" />
    </div>

    <!-- 内存数据展示（仅当有数据时显示） -->
    <template v-else>
    <!-- 时间点信息面板 -->
    <el-row v-if="selectedTimePoint !== null" :gutter="20" class="time-point-info-panel">
      <el-col :span="24">
        <el-alert
          type="info"
          :closable="false"
          show-icon
        >
          <template #title>
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div style="display: flex; align-items: center; gap: 20px; flex-wrap: wrap;">
                <span style="font-weight: bold; font-size: 14px;">
                  <i class="el-icon-time" style="margin-right: 5px;"></i>
                  已选中时间点
                </span>
                <span>
                  <strong>时间:</strong> {{ formatTime(selectedTimePoint) }}
                </span>
                <span>
                  <strong>当前内存:</strong> {{ formatBytes(selectedTimePointMemory) }}
                </span>
                <span>
                  <strong>事件数:</strong> {{ selectedTimePointEventCount }}
                </span>
                <span>
                  <strong>分配事件:</strong> {{ selectedTimePointAllocCount }}
                </span>
                <span>
                  <strong>释放事件:</strong> {{ selectedTimePointFreeCount }}
                </span>
              </div>
              <el-button
                type="danger"
                size="small"
                @click="clearTimePointSelection"
              >
                清除选择
              </el-button>
            </div>
          </template>
        </el-alert>
      </el-col>
    </el-row>

    <!-- 内存时间线图表 -->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">内存时间线</span>
            <span v-if="selectedTimePoint !== null" style="margin-left: 10px; color: #ff6b00; font-size: 12px;">
              <i class="el-icon-info"></i> 点击图表上的点可选择时间点，所有数据将自动过滤到该时间点
            </span>
          </h3>
          <MemoryTimelineChart
            :step-id="`step${props.stepId}`"
            :callchains="currentStepCallchains"
            :selected-time-point="selectedTimePoint"
            height="350px"
            @time-point-selected="handleTimePointSelected"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 内存统计信息行 -->
    <!-- <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">内存峰值</div>
          <div class="stat-value">{{ formatBytes(peakMemorySize) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">平均内存</div>
          <div class="stat-value">{{ formatBytes(averageMemorySize) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">峰值持续时间</div>
          <div class="stat-value">{{ peakMemoryDuration }} ms</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
          <div class="stat-label">净内存</div>
          <div class="stat-value">{{ formatBytes(totalNetMemory) }}</div>
        </div>
      </el-col>
    </el-row> -->

    <!-- 第一行：事件类型内存分布(左) + 事件类型内存详情(右) -->
    <!-- <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">事件类型内存分布</span>
          </h3>
          <div v-if="eventTypePieDrilldownStack.length > 0" class="breadcrumb-nav">
            <span class="breadcrumb-item" @click="handleEventTypePieDrillup">
              {{ getBreadcrumbLabel('eventType', 0) }}
            </span>
            <span v-for="(item, index) in eventTypePieDrilldownStack" :key="index" class="breadcrumb-item">
              <i class="breadcrumb-separator">></i>
              <span @click="handleEventTypeBreadcrumbClick(index)">
                {{ getBreadcrumbLabel('eventType', index + 1, item) }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="stepId" height="400px" :chart-data="eventTypePieData" title="净内存(Bytes)"
            :drilldown-stack="eventTypePieDrilldownStack" :legend-truncate="false"
            @drilldown="handleEventTypePieDrilldown" @drillup="handleEventTypePieDrillup"
          />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">事件类型内存详情</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="eventTypeTableData"
            :has-category="false" data-type="eventType"
            :event-type-label="eventTypeTableLabel" />
        </div>
      </el-col>
    </el-row> -->

    <!-- 第二行：进程内存分布(左) + 分类内存分布(右) -->
    <!-- <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">进程内存分布</span>
          </h3>
          <div v-if="processPieDrilldownStack.length > 0" class="breadcrumb-nav">
            <span class="breadcrumb-item" @click="handleProcessPieDrillup">
              {{ getBreadcrumbLabel('process', 0) }}
            </span>
            <span v-for="(item, index) in processPieDrilldownStack" :key="index" class="breadcrumb-item">
              <i class="breadcrumb-separator">></i>
              <span @click="handleProcessBreadcrumbClick(index)">
                {{ getBreadcrumbLabel('process', index + 1, item) }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="stepId" height="400px" :chart-data="processPieData" title="净内存(Bytes)"
            :drilldown-stack="processPieDrilldownStack" :legend-truncate="false"
            @drilldown="handleProcessPieDrilldown" @drillup="handleProcessPieDrillup"
          />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">分类内存分布</span>
          </h3>
          <div v-if="categoryPieDrilldownStack.length > 0" class="breadcrumb-nav">
            <span class="breadcrumb-item" @click="handleCategoryPieDrillup">
              {{ getBreadcrumbLabel('category', 0) }}
            </span>
            <span v-for="(item, index) in categoryPieDrilldownStack" :key="index" class="breadcrumb-item">
              <i class="breadcrumb-separator">></i>
              <span @click="handleCategoryBreadcrumbClick(index)">
                {{ getBreadcrumbLabel('category', index + 1, item) }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="stepId" height="400px" :chart-data="categoryPieData" title="净内存(Bytes)"
            :drilldown-stack="categoryPieDrilldownStack" :legend-truncate="false"
            @drilldown="handleCategoryPieDrilldown" @drillup="handleCategoryPieDrillup"
          />
        </div>
      </el-col>
    </el-row> -->

    <!-- 第三行：进程内存详情(左) + 分类内存详情(右) -->
    <!-- <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">进程内存详情</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="processTableData"
            :has-category="false" data-type="process" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">分类内存详情</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="categoryTableData"
            :has-category="true" data-type="category" />
        </div>
      </el-col>
    </el-row> -->

    <!-- 线程/组件表格行 -->
    <!-- <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">线程内存</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredThreadMemoryDataDrill"
            :has-category="false" data-type="thread" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">小分类内存</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredComponentMemoryDataDrill"
            :has-category="true" data-type="component" />
        </div>
      </el-col>
    </el-row> -->

    <!-- 文件表格行 -->
    <!-- <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件内存</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredFileMemoryDataDrill"
            :has-category="false" data-type="file" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件内存（分类）</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredFileCategoryMemoryDataDrill"
            :has-category="true" data-type="file" />
        </div>
      </el-col>
    </el-row> -->

    <!-- 符号表格行 -->
    <!-- <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">符号内存</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredSymbolMemoryDataDrill"
            :has-category="false" data-type="symbol" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">符号内存（分类）</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredSymbolCategoryMemoryDataDrill"
            :has-category="true" data-type="symbol" />
        </div>
      </el-col>
    </el-row> -->
    </template>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch, onMounted } from 'vue';
// import NativeMemoryTable from './NativeMemoryTable.vue';
// import PieChart from './PieChart.vue';
import MemoryTimelineChart from './MemoryTimelineChart.vue';
import { loadNativeMemoryMetadataFromDb } from '@/stores/nativeMemory';
import type { NativeMemoryData, NativeMemoryRecord } from '@/stores/nativeMemory';
import {
  // nativeMemory2ProcessPieChartData,
  // nativeMemory2CategoryPieChartData,
  // nativeMemory2EventTypePieChartData,
  // aggregateByThread,
  // aggregateByFile,
  // aggregateBySymbol,
  // aggregateByComponent,
  // aggregateByFileCategory,
  // aggregateBySymbolCategory,
  // getEventTypeName,
  // getCategoryName,
  // calculateMemoryStats,
} from '@/utils/nativeMemoryUtil.ts';

// Props
const props = defineProps<{
  stepId: number;
}>();


const nativeMemoryData = ref<NativeMemoryData | null>(null);
const nativeMemoryError = ref<unknown>(null);
const isNativeMemoryLoading = ref(false);

async function ensureNativeMemoryDataLoaded() {
  if (nativeMemoryData.value || isNativeMemoryLoading.value) return;
  try {
    isNativeMemoryLoading.value = true;
    nativeMemoryData.value = await loadNativeMemoryMetadataFromDb();
  } catch (error) {
    nativeMemoryError.value = error;
    nativeMemoryData.value = null;
    console.error('[PerfNativeMemory] Failed to load native memory metadata:', error);
  } finally {
    isNativeMemoryLoading.value = false;
  }
}

onMounted(() => {
  void ensureNativeMemoryDataLoaded();
});

// 检查是否有数据（只需要检查 stepData 是否存在，不检查 records 长度）
const hasData = computed(() => {
  const data = nativeMemoryData.value;
  if (!data) return false;
  const stepKey = `step${props.stepId}`;
  const stepData = data[stepKey];
  return stepData !== undefined;
});

// 获取当前步骤的所有记录
const currentStepRecords = computed(() => {
  const data = nativeMemoryData.value;
  if (!data) return [];
  const stepKey = `step${props.stepId}`;
  const stepData = data[stepKey];
  return stepData?.records || [];
});

// 获取当前步骤的调用链数据
const currentStepCallchains = computed(() => {
  const data = nativeMemoryData.value;
  if (!data) return undefined;
  const stepKey = `step${props.stepId}`;
  const stepData = data[stepKey];
  return stepData?.callchains;
});

// 聚合数据（支持时间点过滤）
// const mergedThreadMemoryData = computed(() =>
//   aggregateByThread(nativeMemoryData, props.stepId, selectedTimePoint.value)
// );
// const mergedFileMemoryData = computed(() =>
//   aggregateByFile(nativeMemoryData, props.stepId, selectedTimePoint.value)
// );
// const mergedSymbolMemoryData = computed(() =>
//   aggregateBySymbol(nativeMemoryData, props.stepId, selectedTimePoint.value)
// );
// const mergedComponentMemoryData = computed(() =>
//   aggregateByComponent(nativeMemoryData, props.stepId, selectedTimePoint.value)
// );
// const mergedFileCategoryMemoryData = computed(() =>
//   aggregateByFileCategory(nativeMemoryData, props.stepId, selectedTimePoint.value)
// );
// const mergedSymbolCategoryMemoryData = computed(() =>
//   aggregateBySymbolCategory(nativeMemoryData, props.stepId, selectedTimePoint.value)
// );

// 工具函数：安全排序（按峰值内存排序）
// function sortByMaxMem<T extends { peakMem: number }>(arr: T[]): T[] {
//   return [...arr].sort((a, b) => b.peakMem - a.peakMem);
// }

// 选中的时间点（用于过滤数据）
const selectedTimePoint = ref<number | null>(null);

// 处理时间点选择
function handleTimePointSelected(timePoint: number | null) {
  selectedTimePoint.value = timePoint;
}

// 清除时间点选择
function clearTimePointSelection() {
  selectedTimePoint.value = null;
}

// 监听 stepId 变化，清除时间点选择
watch(() => props.stepId, () => {
  selectedTimePoint.value = null; // 切换步骤时清除时间点选择
});

// 计算选中时间点的统计信息
const selectedTimePointMemory = computed(() => {
  if (selectedTimePoint.value === null || !currentStepRecords.value.length) return 0;

  // 实时计算当前内存：遍历所有时间点 <= 选中时间点的记录
  const records = currentStepRecords.value;
  let cumulativeMemory = 0;

  for (const record of records) {
    if (record.relativeTs > selectedTimePoint.value) {
      break;
    }

    // 根据事件类型累加/减少内存
    const eventType = record.eventType;
    const size = record.heapSize || 0;

    if (eventType === 'AllocEvent' || eventType === 'MmapEvent') {
      cumulativeMemory += size;
    } else if (eventType === 'FreeEvent' || eventType === 'MunmapEvent') {
      cumulativeMemory -= size;
    }
  }

  return cumulativeMemory;
});

const selectedTimePointEventCount = computed(() => {
  if (selectedTimePoint.value === null || !currentStepRecords.value.length) return 0;
  return currentStepRecords.value.filter((r: NativeMemoryRecord) => r.relativeTs <= selectedTimePoint.value!).length;
});

const selectedTimePointAllocCount = computed(() => {
  if (selectedTimePoint.value === null || !currentStepRecords.value.length) return 0;
  return currentStepRecords.value.filter((r: NativeMemoryRecord) =>
    r.relativeTs <= selectedTimePoint.value! &&
    (r.eventType === 'AllocEvent' || r.eventType === 'MmapEvent')
  ).length;
});

const selectedTimePointFreeCount = computed(() => {
  if (selectedTimePoint.value === null || !currentStepRecords.value.length) return 0;
  return currentStepRecords.value.filter((r: NativeMemoryRecord) =>
    r.relativeTs <= selectedTimePoint.value! &&
    (r.eventType === 'FreeEvent' || r.eventType === 'MunmapEvent')
  ).length;
});

// 工具函数：格式化字节数
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

// 工具函数：格式化时间（纳秒转为可读格式）
function formatTime(ns: number): string {
  if (ns < 1000) return `${ns} ns`;
  if (ns < 1000000) return `${(ns / 1000).toFixed(2)} μs`;
  if (ns < 1000000000) return `${(ns / 1000000).toFixed(2)} ms`;
  return `${(ns / 1000000000).toFixed(2)} s`;
}

// 监听时间点变化，重新计算钻取数据和加载饼图数据
// watch(selectedTimePoint, async () => {
//   // 重新加载顶层饼图数据
//   await loadPieChartData();

//   // 重新计算进程饼图钻取数据
//   if (processPieDrilldownStack.value.length > 0) {
//     processPieDataStack.value = [];
//     for (let i = 0; i < processPieDrilldownStack.value.length; i++) {
//       const name = processPieDrilldownStack.value[i];
//       const stack = processPieDrilldownStack.value.slice(0, i + 1);
//       const data = await getProcessPieDrilldownData(name, stack);
//       processPieDataStack.value.push(data);
//     }
//     // 更新当前显示的饼图数据
//     processPieData.value = processPieDataStack.value[processPieDataStack.value.length - 1] || { legendData: [], seriesData: [] };
//   }

//   // 重新计算分类饼图钻取数据
//   if (categoryPieDrilldownStack.value.length > 0) {
//     categoryPieDataStack.value = [];
//     for (let i = 0; i < categoryPieDrilldownStack.value.length; i++) {
//       const name = categoryPieDrilldownStack.value[i];
//       const stack = categoryPieDrilldownStack.value.slice(0, i + 1);
//       const data = await getCategoryPieDrilldownData(name, stack);
//       categoryPieDataStack.value.push(data);
//     }
//     // 更新当前显示的饼图数据
//     categoryPieData.value = categoryPieDataStack.value[categoryPieDataStack.value.length - 1] || { legendData: [], seriesData: [] };
//   }

//   // 重新计算事件类型饼图钻取数据
//   if (eventTypePieDrilldownStack.value.length > 0) {
//     eventTypePieDataStack.value = [];
//     for (let i = 0; i < eventTypePieDrilldownStack.value.length; i++) {
//       const name = eventTypePieDrilldownStack.value[i];
//       const stack = eventTypePieDrilldownStack.value.slice(0, i + 1);
//       const data = await getEventTypePieDrilldownData(name, stack);
//       eventTypePieDataStack.value.push(data);
//     }
//     // 更新当前显示的饼图数据
//     eventTypePieData.value = eventTypePieDataStack.value[eventTypePieDataStack.value.length - 1] || { legendData: [], seriesData: [] };
//   }
// });

// 饼图数据和钻取栈
// const processPieDrilldownStack = ref<string[]>([]);
// const processPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);

// const categoryPieDrilldownStack = ref<string[]>([]);
// const categoryPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);

// const eventTypePieDrilldownStack = ref<string[]>([]);
// const eventTypePieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);

// 饼图数据使用 ref 存储，因为数据获取函数是异步的
// const processPieData = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }>({ legendData: [], seriesData: [] });
// const categoryPieData = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }>({ legendData: [], seriesData: [] });
// const eventTypePieData = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }>({ legendData: [], seriesData: [] });

// 异步加载饼图数据
// async function loadPieChartData() {
//   // 加载进程饼图数据（如果没有钻取，则加载顶层数据）
//   if (processPieDrilldownStack.value.length === 0) {
//     processPieData.value = await nativeMemory2ProcessPieChartData(nativeMemoryData, props.stepId, selectedTimePoint.value);
//   }

//   // 加载分类饼图数据（如果没有钻取，则加载顶层数据）
//   if (categoryPieDrilldownStack.value.length === 0) {
//     categoryPieData.value = await nativeMemory2CategoryPieChartData(nativeMemoryData, props.stepId, selectedTimePoint.value);
//   }

//   // 加载事件类型饼图数据（如果没有钻取，则加载顶层数据）
//   if (eventTypePieDrilldownStack.value.length === 0) {
//     eventTypePieData.value = await nativeMemory2EventTypePieChartData(nativeMemoryData, props.stepId, selectedTimePoint.value);
//   }
// }

// 监听stepId变化，重新加载数据
// watch(() => props.stepId, async () => {
//   selectedTimePoint.value = null; // 切换步骤时清除时间点选择
//   // 清除钻取栈
//   processPieDrilldownStack.value = [];
//   processPieDataStack.value = [];
//   categoryPieDrilldownStack.value = [];
//   categoryPieDataStack.value = [];
//   eventTypePieDrilldownStack.value = [];
//   eventTypePieDataStack.value = [];
//   // 重新加载饼图数据
//   await loadPieChartData();
// }, { immediate: true });

// 进程饼图钻取逻辑（支持多层下钻）
// async function getProcessPieDrilldownData(name: string, stack: string[]) {
//   // 层级：0-进程 1-线程 2-文件 3-符号
//   if (stack.length === 0) {
//     const data = await nativeMemory2ProcessPieChartData(nativeMemoryData, props.stepId, selectedTimePoint.value);
//     const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
//     return { legendData: sorted.map(d => d.name), seriesData: sorted };
//   } else if (stack.length === 1) {
//     // 深度 1：按线程聚合（先按进程过滤原始记录）
//     const processName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按进程过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item => item.process === processName);

//     // 按线程聚合，使用 calculateMemoryStats 计算峰值内存
//     const threadMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const threadName = item.thread || 'Unknown Thread';
//       if (!threadMap.has(threadName)) {
//         threadMap.set(threadName, []);
//       }
//       threadMap.get(threadName)!.push(item);
//     });

//     const aggregated = Array.from(threadMap.entries()).map(([threadName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: threadName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else if (stack.length === 2) {
//     // 深度 2：按文件聚合（先按进程和线程过滤原始记录）
//     const processName = stack[0];
//     const threadName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按进程和线程过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item =>
//       item.process === processName && item.thread === threadName
//     );

//     // 按文件聚合，使用 calculateMemoryStats 计算峰值内存
//     const fileMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const fileName = item.file || 'Unknown File';
//       if (!fileMap.has(fileName)) {
//         fileMap.set(fileName, []);
//       }
//       fileMap.get(fileName)!.push(item);
//     });

//     const aggregated = Array.from(fileMap.entries()).map(([fileName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: fileName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else if (stack.length === 3) {
//     // 深度 3：按符号聚合（先按进程、线程和文件过滤原始记录）
//     const processName = stack[0];
//     const threadName = stack[1];
//     const fileName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按进程、线程和文件过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item =>
//       item.process === processName && item.thread === threadName && item.file === fileName
//     );

//     // 按符号聚合，使用 calculateMemoryStats 计算峰值内存
//     const symbolMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const symbolName = item.symbol || 'Unknown Symbol';
//       if (!symbolMap.has(symbolName)) {
//         symbolMap.set(symbolName, []);
//       }
//       symbolMap.get(symbolName)!.push(item);
//     });

//     const aggregated = Array.from(symbolMap.entries()).map(([symbolName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: symbolName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else {
//     return processPieData.value;
//   }
// }

// async function handleProcessPieDrilldown(name: string) {
//   const newStack = [...processPieDrilldownStack.value, name];
//   const newData = await getProcessPieDrilldownData(name, newStack);
//   if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(processPieData.value)) {
//     return;
//   }
//   processPieDrilldownStack.value = newStack;
//   processPieDataStack.value.push(newData);
//   // 更新饼图数据
//   processPieData.value = newData;
// }

// function handleProcessPieDrillup() {
//   if (processPieDrilldownStack.value.length === 0) return;
//   processPieDrilldownStack.value.pop();
//   processPieDataStack.value.pop();
// }

// function handleProcessBreadcrumbClick(index: number) {
//   const targetLevel = index + 1;
//   const currentLevel = processPieDrilldownStack.value.length;
//   if (targetLevel >= currentLevel) return;
//   const stepsToGoBack = currentLevel - targetLevel;
//   for (let i = 0; i < stepsToGoBack; i++) {
//     handleProcessPieDrillup();
//   }
// }

// 分类饼图钻取逻辑（支持多层下钻）
// async function getCategoryPieDrilldownData(name: string, stack: string[]) {
//   // 层级：0-大类 1-小类 2-文件 3-符号
//   if (stack.length === 0) {
//     const data = await nativeMemory2CategoryPieChartData(nativeMemoryData, props.stepId, selectedTimePoint.value);
//     const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
//     return { legendData: sorted.map(d => d.name), seriesData: sorted };
//   } else if (stack.length === 1) {
//     // 深度 1：按小类聚合（先按大类过滤原始记录）
//     const categoryName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按大类过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item =>
//       getCategoryName(item.componentCategory) === categoryName
//     );

//     // 按小类聚合，使用 calculateMemoryStats 计算峰值内存
//     const componentMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const subCategoryName = item.subCategoryName || 'Unknown Component';
//       if (!componentMap.has(subCategoryName)) {
//         componentMap.set(subCategoryName, []);
//       }
//       componentMap.get(subCategoryName)!.push(item);
//     });

//     const aggregated = Array.from(componentMap.entries()).map(([subCategoryName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: subCategoryName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else if (stack.length === 2) {
//     // 深度 2：按文件聚合（先按大类和小类过滤原始记录）
//     const categoryName = stack[0];
//     const subCategoryName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按大类和小类过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item =>
//       getCategoryName(item.componentCategory) === categoryName &&
//       item.subCategoryName === subCategoryName
//     );

//     // 按文件聚合，使用 calculateMemoryStats 计算峰值内存
//     const fileMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const fileName = item.file || 'Unknown File';
//       if (!fileMap.has(fileName)) {
//         fileMap.set(fileName, []);
//       }
//       fileMap.get(fileName)!.push(item);
//     });

//     const aggregated = Array.from(fileMap.entries()).map(([fileName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: fileName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else if (stack.length === 3) {
//     // 深度 3：按符号聚合（先按大类、小类和文件过滤原始记录）
//     const categoryName = stack[0];
//     const subCategoryName = stack[1];
//     const fileName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按大类、小类和文件过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item =>
//       getCategoryName(item.componentCategory) === categoryName &&
//       item.subCategoryName === subCategoryName &&
//       item.file === fileName
//     );

//     // 按符号聚合，使用 calculateMemoryStats 计算峰值内存
//     const symbolMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const symbolName = item.symbol || 'Unknown Symbol';
//       if (!symbolMap.has(symbolName)) {
//         symbolMap.set(symbolName, []);
//       }
//       symbolMap.get(symbolName)!.push(item);
//     });

//     const aggregated = Array.from(symbolMap.entries()).map(([symbolName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: symbolName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else {
//     return categoryPieData.value;
//   }
// }

// async function handleCategoryPieDrilldown(name: string) {
//   const newStack = [...categoryPieDrilldownStack.value, name];
//   const newData = await getCategoryPieDrilldownData(name, newStack);
//   if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(categoryPieData.value)) {
//     return;
//   }
//   categoryPieDrilldownStack.value = newStack;
//   categoryPieDataStack.value.push(newData);
//   // 更新饼图数据
//   categoryPieData.value = newData;
// }

// function handleCategoryPieDrillup() {
//   if (categoryPieDrilldownStack.value.length === 0) return;
//   categoryPieDrilldownStack.value.pop();
//   categoryPieDataStack.value.pop();
// }

// function handleCategoryBreadcrumbClick(index: number) {
//   const targetLevel = index + 1;
//   const currentLevel = categoryPieDrilldownStack.value.length;
//   if (targetLevel >= currentLevel) return;
//   const stepsToGoBack = currentLevel - targetLevel;
//   for (let i = 0; i < stepsToGoBack; i++) {
//     handleCategoryPieDrillup();
//   }
// }

// 饼图钻取逻辑（事件类型维度）
// 使用 totalMem（总分配内存）而不是 curMem
// async function getEventTypePieDrilldownData(name: string, stack: string[]) {
//   // 层级：0-事件类型 1-线程 2-文件 3-符号
//   if (stack.length === 0) {
//     const data = await nativeMemory2EventTypePieChartData(nativeMemoryData, props.stepId, selectedTimePoint.value);
//     const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
//     return { legendData: sorted.map(d => d.name), seriesData: sorted };
//   } else if (stack.length === 1) {
//     // 深度 1：按线程聚合（先按事件类型过滤原始记录）
//     const eventTypeName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按事件类型过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item => {
//       const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
//       return itemEventTypeName === eventTypeName;
//     });

//     // 按线程聚合，使用 calculateMemoryStats 计算峰值内存
//     const threadMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const threadName = item.thread || 'Unknown Thread';
//       if (!threadMap.has(threadName)) {
//         threadMap.set(threadName, []);
//       }
//       threadMap.get(threadName)!.push(item);
//     });

//     const aggregated = Array.from(threadMap.entries()).map(([threadName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: threadName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else if (stack.length === 2) {
//     // 深度 2：按文件聚合（先按事件类型和线程过滤原始记录）
//     const eventTypeName = stack[0];
//     const threadName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按事件类型和线程过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item => {
//       const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
//       return itemEventTypeName === eventTypeName && item.thread === threadName;
//     });

//     // 按文件聚合，使用 calculateMemoryStats 计算峰值内存
//     const fileMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const fileName = item.file || 'Unknown File';
//       if (!fileMap.has(fileName)) {
//         fileMap.set(fileName, []);
//       }
//       fileMap.get(fileName)!.push(item);
//     });

//     const aggregated = Array.from(fileMap.entries()).map(([fileName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: fileName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else if (stack.length === 3) {
//     // 深度 3：按符号聚合（先按事件类型、线程和文件过滤原始记录）
//     const eventTypeName = stack[0];
//     const threadName = stack[1];
//     const fileName = name;
//     if (!nativeMemoryData) return { legendData: [], seriesData: [] };
//     const stepKey = `step${props.stepId}`;
//     const stepData = nativeMemoryData[stepKey];
//     if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

//     // 先按时间点过滤，再按事件类型、线程和文件过滤
//     const timeFilteredRecords = selectedTimePoint.value !== null
//       ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//       : stepData.records;
//     const filteredRecords = timeFilteredRecords.filter(item => {
//       const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
//       return itemEventTypeName === eventTypeName && item.thread === threadName && item.file === fileName;
//     });

//     // 按符号聚合，使用 calculateMemoryStats 计算峰值内存
//     const symbolMap = new Map<string, typeof filteredRecords>();
//     filteredRecords.forEach(item => {
//       const symbolName = item.symbol || 'Unknown Symbol';
//       if (!symbolMap.has(symbolName)) {
//         symbolMap.set(symbolName, []);
//       }
//       symbolMap.get(symbolName)!.push(item);
//     });

//     const aggregated = Array.from(symbolMap.entries()).map(([symbolName, records]) => {
//       const stats = calculateMemoryStats(records);
//       return { name: symbolName, value: stats.peakMem };
//     });

//     const sorted = aggregated.sort((a, b) => b.value - a.value);
//     const legendData = sorted.map(d => d.name);
//     const seriesData = sorted;
//     return { legendData, seriesData };
//   } else {
//     return eventTypePieData.value;
//   }
// }

// async function handleEventTypePieDrilldown(name: string) {
//   const newStack = [...eventTypePieDrilldownStack.value, name];
//   const newData = await getEventTypePieDrilldownData(name, newStack);
//   if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(eventTypePieData.value)) {
//     return;
//   }
//   eventTypePieDrilldownStack.value = newStack;
//   eventTypePieDataStack.value.push(newData);
//   // 更新饼图数据
//   eventTypePieData.value = newData;
// }

// function handleEventTypePieDrillup() {
//   if (eventTypePieDrilldownStack.value.length === 0) return;
//   eventTypePieDrilldownStack.value.pop();
//   eventTypePieDataStack.value.pop();
// }

// function handleEventTypeBreadcrumbClick(index: number) {
//   const targetLevel = index + 1;
//   const currentLevel = eventTypePieDrilldownStack.value.length;
//   if (targetLevel >= currentLevel) return;
//   const stepsToGoBack = currentLevel - targetLevel;
//   for (let i = 0; i < stepsToGoBack; i++) {
//     handleEventTypePieDrillup();
//   }
// }

// 面包屑标签
// function getBreadcrumbLabel(dimension: 'process' | 'category' | 'eventType', level: number, item?: string): string {
//   if (dimension === 'process') {
//     const labels = ['进程', '线程', '文件', '符号'];
//     return level === 0 ? labels[0] : item || labels[level];
//   } else if (dimension === 'eventType') {
//     // 事件类型维度：事件类型 > 线程 > 文件 > 符号
//     const labels = ['事件类型', '线程', '文件', '符号'];
//     return level === 0 ? labels[0] : item || labels[level];
//   } else {
//     // 分类维度：大类 > 小类 > 文件 > 符号
//     const labels = ['大类', '小类', '文件', '符号'];
//     if (level === 0) {
//       return labels[0];
//     } else if (level === 1) {
//       // 第一层是大类名称
//       return item || labels[1];
//     } else {
//       // 第二层及以后是小类、文件、符号
//       return item || labels[level];
//     }
//   }
// }

// 表格数据过滤（进程维度）- 根据饼图下钻条件添加筛选
// const filteredThreadMemoryDataDrill = computed(() => {
//   const drilldownLevel = processPieDrilldownStack.value.length;
//   if (drilldownLevel === 0) {
//     return sortByMaxMem(mergedThreadMemoryData.value);
//   }
//   // 根据进程过滤
//   const processName = processPieDrilldownStack.value[0];
//   return sortByMaxMem(mergedThreadMemoryData.value.filter(item => item.process === processName));
// });

// const filteredFileMemoryDataDrill = computed(() => {
//   const drilldownLevel = processPieDrilldownStack.value.length;
//   if (drilldownLevel === 0) {
//     return sortByMaxMem(mergedFileMemoryData.value);
//   }
//   // 根据进程过滤
//   const processName = processPieDrilldownStack.value[0];
//   let filtered = mergedFileMemoryData.value.filter(item => item.process === processName);

//   // 如果下钻到线程，再根据线程过滤
//   if (drilldownLevel >= 2) {
//     const threadName = processPieDrilldownStack.value[1];
//     filtered = filtered.filter(item => item.thread === threadName);
//   }

//   return sortByMaxMem(filtered);
// });

// const filteredSymbolMemoryDataDrill = computed(() => {
//   const drilldownLevel = processPieDrilldownStack.value.length;
//   if (drilldownLevel === 0) {
//     return sortByMaxMem(mergedSymbolMemoryData.value);
//   }
//   // 根据进程过滤
//   const processName = processPieDrilldownStack.value[0];
//   let filtered = mergedSymbolMemoryData.value.filter(item => item.process === processName);

//   // 如果下钻到线程，再根据线程过滤
//   if (drilldownLevel >= 2) {
//     const threadName = processPieDrilldownStack.value[1];
//     filtered = filtered.filter(item => item.thread === threadName);
//   }

//   // 如果下钻到文件，再根据文件过滤
//   if (drilldownLevel >= 3) {
//     const fileName = processPieDrilldownStack.value[2];
//     filtered = filtered.filter(item => item.file === fileName);
//   }

//   return sortByMaxMem(filtered);
// });

// 表格数据过滤（分类维度）- 根据饼图下钻条件添加筛选
// const filteredComponentMemoryDataDrill = computed(() => {
//   const drilldownLevel = categoryPieDrilldownStack.value.length;
//   if (drilldownLevel === 0) {
//     return sortByMaxMem(mergedComponentMemoryData.value);
//   }
//   // 根据大类过滤
//   const categoryName = categoryPieDrilldownStack.value[0];
//   return sortByMaxMem(mergedComponentMemoryData.value.filter(item => item.category === categoryName));
// });

// const filteredFileCategoryMemoryDataDrill = computed(() => {
//   const drilldownLevel = categoryPieDrilldownStack.value.length;
//   if (drilldownLevel === 0) {
//     return sortByMaxMem(mergedFileCategoryMemoryData.value);
//   }
//   // 根据大类过滤
//   const categoryName = categoryPieDrilldownStack.value[0];
//   let filtered = mergedFileCategoryMemoryData.value.filter(item => item.category === categoryName);

//   // 如果下钻到小类，再根据小类过滤
//   if (drilldownLevel >= 2) {
//     const componentName = categoryPieDrilldownStack.value[1];
//     filtered = filtered.filter(item => item.componentName === componentName);
//   }

//   return sortByMaxMem(filtered);
// });

// const filteredSymbolCategoryMemoryDataDrill = computed(() => {
//   const drilldownLevel = categoryPieDrilldownStack.value.length;
//   if (drilldownLevel === 0) {
//     return sortByMaxMem(mergedSymbolCategoryMemoryData.value);
//   }
//   // 根据大类过滤
//   const categoryName = categoryPieDrilldownStack.value[0];
//   let filtered = mergedSymbolCategoryMemoryData.value.filter(item => item.category === categoryName);

//   // 如果下钻到小类，再根据小类过滤
//   if (drilldownLevel >= 2) {
//     const componentName = categoryPieDrilldownStack.value[1];
//     filtered = filtered.filter(item => item.componentName === componentName);
//   }

//   // 如果下钻到文件，再根据文件过滤
//   if (drilldownLevel >= 3) {
//     const fileName = categoryPieDrilldownStack.value[2];
//     filtered = filtered.filter(item => item.file === fileName);
//   }

//   return sortByMaxMem(filtered);
// });

// 事件类型表格数据（与事件类型饼图联动，支持多层下钻）
// const eventTypeTableData = computed(() => {
//   if (!nativeMemoryData) return [];
//   const stepKey = `step${props.stepId}`;
//   const stepData = nativeMemoryData[stepKey];
//   if (!stepData || !stepData.records) return [];

//   // 先按时间点过滤
//   let records = selectedTimePoint.value !== null
//     ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//     : stepData.records;

//   const drilldownLevel = eventTypePieDrilldownStack.value.length;

//   // 根据钻取深度过滤数据
//   if (drilldownLevel > 0) {
//     const eventTypeName = eventTypePieDrilldownStack.value[0];
//     records = records.filter(item => {
//       const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
//       return itemEventTypeName === eventTypeName;
//     });
//   }

//   if (drilldownLevel > 1) {
//     const threadName = eventTypePieDrilldownStack.value[1];
//     records = records.filter(item => item.thread === threadName);
//   }

//   if (drilldownLevel > 2) {
//     const fileName = eventTypePieDrilldownStack.value[2];
//     records = records.filter(item => item.file === fileName);
//   }

//   // 根据钻取深度决定聚合维度
//   if (drilldownLevel === 0) {
//     // 深度 0：按事件类型聚合
//     const eventTypeMap = new Map<string, typeof records>();

//     records.forEach(item => {
//       const eventTypeName = getEventTypeName(item.eventType, item.subEventType);
//       if (!eventTypeMap.has(eventTypeName)) {
//         eventTypeMap.set(eventTypeName, []);
//       }
//       eventTypeMap.get(eventTypeName)!.push(item);
//     });

//     return Array.from(eventTypeMap.entries())
//       .map(([eventTypeName, records]) => {
//         const stats = calculateMemoryStats(records);
//         return {
//           eventTypeName,
//           eventNum: stats.eventNum,
//           allocEventNum: stats.allocEventNum,
//           freeEventNum: stats.freeEventNum,
//           peakMem: stats.peakMem,
//           avgMem: stats.avgMem,
//           totalAllocMem: stats.totalAllocMem,
//           totalFreeMem: stats.totalFreeMem,
//           start_ts: stats.start_ts,
//         };
//       })
//       .sort((a, b) => b.peakMem - a.peakMem);
//   } else if (drilldownLevel === 1) {
//     // 深度 1：按线程聚合
//     const threadMap = new Map<string, typeof records>();

//     records.forEach(item => {
//       const threadName = item.thread || 'Unknown Thread';
//       if (!threadMap.has(threadName)) {
//         threadMap.set(threadName, []);
//       }
//       threadMap.get(threadName)!.push(item);
//     });

//     return Array.from(threadMap.entries())
//       .map(([thread, records]) => {
//         const stats = calculateMemoryStats(records);
//         return {
//           eventTypeName: thread,
//           eventNum: stats.eventNum,
//           allocEventNum: stats.allocEventNum,
//           freeEventNum: stats.freeEventNum,
//           peakMem: stats.peakMem,
//           avgMem: stats.avgMem,
//           totalAllocMem: stats.totalAllocMem,
//           totalFreeMem: stats.totalFreeMem,
//           start_ts: stats.start_ts,
//         };
//       })
//       .sort((a, b) => b.peakMem - a.peakMem);
//   } else if (drilldownLevel === 2) {
//     // 深度 2：按文件聚合
//     const fileMap = new Map<string, typeof records>();

//     records.forEach(item => {
//       const fileName = item.file || 'Unknown File';
//       if (!fileMap.has(fileName)) {
//         fileMap.set(fileName, []);
//       }
//       fileMap.get(fileName)!.push(item);
//     });

//     return Array.from(fileMap.entries())
//       .map(([file, records]) => {
//         const stats = calculateMemoryStats(records);
//         return {
//           eventTypeName: file,
//           eventNum: stats.eventNum,
//           allocEventNum: stats.allocEventNum,
//           freeEventNum: stats.freeEventNum,
//           peakMem: stats.peakMem,
//           avgMem: stats.avgMem,
//           totalAllocMem: stats.totalAllocMem,
//           totalFreeMem: stats.totalFreeMem,
//           start_ts: stats.start_ts,
//         };
//       })
//       .sort((a, b) => b.peakMem - a.peakMem);
//   } else {
//     // 深度 3：按符号聚合
//     const symbolMap = new Map<string, typeof records>();

//     records.forEach(item => {
//       const symbolName = item.symbol || 'Unknown Symbol';
//       if (!symbolMap.has(symbolName)) {
//         symbolMap.set(symbolName, []);
//       }
//       symbolMap.get(symbolName)!.push(item);
//     });

//     return Array.from(symbolMap.entries())
//       .map(([symbol, records]) => {
//         const stats = calculateMemoryStats(records);
//         return {
//           eventTypeName: symbol,
//           eventNum: stats.eventNum,
//           allocEventNum: stats.allocEventNum,
//           freeEventNum: stats.freeEventNum,
//           peakMem: stats.peakMem,
//           avgMem: stats.avgMem,
//           totalAllocMem: stats.totalAllocMem,
//           totalFreeMem: stats.totalFreeMem,
//           start_ts: stats.start_ts,
//         };
//       })
//       .sort((a, b) => b.peakMem - a.peakMem);
//   }
// });

// 事件类型表头标签（根据下钻层级动态变化）
// const eventTypeTableLabel = computed(() => {
//   const drilldownLevel = eventTypePieDrilldownStack.value.length;
//   const labels = ['事件类型', '线程', '文件', '符号'];
//   return labels[drilldownLevel] || '事件类型';
// });

// 进程表格数据（只显示进程列表，不支持下钻）
// const processTableData = computed(() => {
//   if (!nativeMemoryData) return [];
//   const stepKey = `step${props.stepId}`;
//   const stepData = nativeMemoryData[stepKey];
//   if (!stepData || !stepData.records) return [];

//   // 先按时间点过滤
//   const timeFilteredRecords = selectedTimePoint.value !== null
//     ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//     : stepData.records;

//   const records = timeFilteredRecords.filter(item => item.pid !== null && item.pid !== undefined);

//   // 按进程聚合
//   const processMap = new Map<string, typeof records>();

//   records.forEach(item => {
//     const processName = item.process || "Unknown Process";
//     if (!processMap.has(processName)) {
//       processMap.set(processName, []);
//     }
//     processMap.get(processName)!.push(item);
//   });

//   return Array.from(processMap.entries())
//     .map(([process, records]) => {
//       const stats = calculateMemoryStats(records);
//       return {
//         process,
//         eventNum: stats.eventNum,
//         allocEventNum: stats.allocEventNum,
//         freeEventNum: stats.freeEventNum,
//         peakMem: stats.peakMem,
//         avgMem: stats.avgMem,
//         totalAllocMem: stats.totalAllocMem,
//         totalFreeMem: stats.totalFreeMem,
//         start_ts: stats.start_ts,
//       };
//     })
//     .sort((a, b) => b.peakMem - a.peakMem);
// });

// 分类表格数据（只显示大类列表，不支持下钻）
// const categoryTableData = computed(() => {
//   if (!nativeMemoryData) return [];
//   const stepKey = `step${props.stepId}`;
//   const stepData = nativeMemoryData[stepKey];
//   if (!stepData || !stepData.records) return [];

//   // 先按时间点过滤
//   const records = selectedTimePoint.value !== null
//     ? stepData.records.filter(item => item.relativeTs <= selectedTimePoint.value!)
//     : stepData.records;

//   // 按大类聚合
//   const categoryMap = new Map<number, typeof records>();

//   records.forEach(item => {
//     const category = item.componentCategory;
//     if (!categoryMap.has(category)) {
//       categoryMap.set(category, []);
//     }
//     categoryMap.get(category)!.push(item);
//   });

//   return Array.from(categoryMap.entries())
//     .map(([category, records]) => {
//       const stats = calculateMemoryStats(records);
//       return {
//         componentName: getCategoryName(category),
//         eventNum: stats.eventNum,
//         allocEventNum: stats.allocEventNum,
//         freeEventNum: stats.freeEventNum,
//         peakMem: stats.peakMem,
//         avgMem: stats.avgMem,
//         totalAllocMem: stats.totalAllocMem,
//         totalFreeMem: stats.totalFreeMem,
//         start_ts: stats.start_ts,
//       };
//     })
//     .sort((a, b) => b.peakMem - a.peakMem);
// });
</script>

<style scoped>
.native-memory-container {
  padding: 20px;
}

.data-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.panel-title {
  margin: 0 0 15px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 14px;
}

/* 面包屑导航样式 */
.breadcrumb-nav {
  margin-bottom: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 14px;
}

.breadcrumb-item {
  cursor: pointer;
  color: #409eff;
  transition: all 0.3s;
}

.breadcrumb-item:hover {
  color: #66b1ff;
  text-decoration: underline;
}

.breadcrumb-separator {
  margin: 0 8px;
  color: #909399;
  font-style: normal;
}

/* 时间点信息面板样式 */
.time-point-info-panel {
  margin-bottom: 20px;
}

.time-point-info-panel .el-alert {
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(255, 107, 0, 0.15);
}

.time-point-info-panel .el-alert__title {
  width: 100%;
}

/* 统计信息行样式 */
.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  text-align: center;
  border-left: 4px solid #667eea;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 10px;
  font-weight: 500;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  word-break: break-all;
}
</style>

