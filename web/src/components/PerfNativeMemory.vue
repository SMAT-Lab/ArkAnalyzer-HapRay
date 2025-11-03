<template>
  <div class="native-memory-container">
    <!-- 无数据提示 -->
    <div v-if="!hasData" class="no-data-tip">
      <el-empty description="暂无内存分析数据" />
    </div>

    <!-- 内存数据展示（仅当有数据时显示） -->
    <template v-else>
    <!-- 内存时间线图表 -->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">内存时间线</span>
          </h3>
          <MemoryTimelineChart :records="currentStepRecords" height="350px" />
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
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 事件类型内存分布饼图 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">事件类型内存分布</span>
          </h3>
          <!-- 面包屑导航 -->
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
        <!-- 事件类型内存详情表格 -->
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
    </el-row>

    <!-- 第二行：进程内存分布(左) + 分类内存分布(右) -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 进程内存分布饼图 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">进程内存分布</span>
          </h3>
          <!-- 面包屑导航 -->
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
        <!-- 分类内存分布饼图 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">分类内存分布</span>
          </h3>
          <!-- 面包屑导航 -->
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
    </el-row>

    <!-- 第三行：进程内存详情(左) + 分类内存详情(右) -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 进程内存详情表格 -->
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
        <!-- 分类内存详情表格 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">分类内存详情</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="categoryTableData"
            :has-category="true" data-type="category" />
        </div>
      </el-col>
    </el-row>

    <!-- 线程/组件表格行 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 线程内存 -->
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
        <!-- 小分类内存 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">小分类内存</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredComponentMemoryDataDrill"
            :has-category="true" data-type="component" />
        </div>
      </el-col>
    </el-row>

    <!-- 文件表格行 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 文件内存 -->
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
        <!-- 文件内存（分类） -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件内存（分类）</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredFileCategoryMemoryDataDrill"
            :has-category="true" data-type="file" />
        </div>
      </el-col>
    </el-row>

    <!-- 符号表格行 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 符号内存 -->
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
        <!-- 符号内存（分类） -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">符号内存（分类）</span>
          </h3>
          <NativeMemoryTable
            :step-id="stepId" :data="filteredSymbolCategoryMemoryDataDrill"
            :has-category="true" data-type="symbol" />
        </div>
      </el-col>
    </el-row>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch } from 'vue';
import NativeMemoryTable from './NativeMemoryTable.vue';
import PieChart from './PieChart.vue';
import MemoryTimelineChart from './MemoryTimelineChart.vue';
import { useJsonDataStore } from '../stores/jsonDataStore.ts';
import {
  nativeMemory2ProcessPieChartData,
  nativeMemory2CategoryPieChartData,
  nativeMemory2EventTypePieChartData,
  aggregateByThread,
  aggregateByFile,
  aggregateBySymbol,
  aggregateByComponent,
  aggregateByFileCategory,
  aggregateBySymbolCategory,
  getEventTypeName,
  getCategoryName,
  calculateMemoryStats,
} from '@/utils/nativeMemoryUtil.ts';

// Props
const props = defineProps<{
  stepId: number;
}>();

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const nativeMemoryData = jsonDataStore.nativeMemoryData;

console.log('Native Memory组件获取到的数据:', props.stepId, nativeMemoryData);

// 检查是否有数据
const hasData = computed(() => {
  if (!nativeMemoryData) return false;
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  return stepData && stepData.records && stepData.records.length > 0;
});

// 获取当前步骤的所有记录
const currentStepRecords = computed(() => {
  if (!nativeMemoryData) return [];
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  return stepData?.records || [];
});

// 聚合数据
const mergedThreadMemoryData = computed(() =>
  aggregateByThread(nativeMemoryData, props.stepId)
);
const mergedFileMemoryData = computed(() =>
  aggregateByFile(nativeMemoryData, props.stepId)
);
const mergedSymbolMemoryData = computed(() =>
  aggregateBySymbol(nativeMemoryData, props.stepId)
);
const mergedComponentMemoryData = computed(() =>
  aggregateByComponent(nativeMemoryData, props.stepId)
);
const mergedFileCategoryMemoryData = computed(() =>
  aggregateByFileCategory(nativeMemoryData, props.stepId)
);
const mergedSymbolCategoryMemoryData = computed(() =>
  aggregateBySymbolCategory(nativeMemoryData, props.stepId)
);

// 工具函数：安全排序（按峰值内存排序）
function sortByMaxMem<T extends { peakMem: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.peakMem - a.peakMem);
}

// 饼图数据和钻取栈
const processPieDrilldownStack = ref<string[]>([]);
const processPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const processPieData = ref(nativeMemory2ProcessPieChartData(nativeMemoryData, props.stepId));

const categoryPieDrilldownStack = ref<string[]>([]);
const categoryPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const categoryPieData = ref(nativeMemory2CategoryPieChartData(nativeMemoryData, props.stepId));

const eventTypePieDrilldownStack = ref<string[]>([]);
const eventTypePieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const eventTypePieData = ref(nativeMemory2EventTypePieChartData(nativeMemoryData, props.stepId));

// 监听stepId变化，重新加载数据
watch(() => props.stepId, (newStepId) => {
  processPieData.value = nativeMemory2ProcessPieChartData(nativeMemoryData, newStepId);
  categoryPieData.value = nativeMemory2CategoryPieChartData(nativeMemoryData, newStepId);
  eventTypePieData.value = nativeMemory2EventTypePieChartData(nativeMemoryData, newStepId);
  processPieDrilldownStack.value = [];
  processPieDataStack.value = [];
  categoryPieDrilldownStack.value = [];
  categoryPieDataStack.value = [];
  eventTypePieDrilldownStack.value = [];
  eventTypePieDataStack.value = [];
}, { immediate: true });

// 进程饼图钻取逻辑（支持多层下钻）
function getProcessPieDrilldownData(name: string, stack: string[]) {
  // 层级：0-进程 1-线程 2-文件 3-符号
  if (stack.length === 0) {
    const data = nativeMemory2ProcessPieChartData(nativeMemoryData, props.stepId);
    const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
    return { legendData: sorted.map(d => d.name), seriesData: sorted };
  } else if (stack.length === 1) {
    // 深度 1：按线程聚合（先按进程过滤原始记录）
    const processName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按进程过滤
    const filteredRecords = stepData.records.filter(item => item.process === processName);

    // 按线程聚合，使用 calculateMemoryStats 计算峰值内存
    const threadMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const threadName = item.thread || 'Unknown Thread';
      if (!threadMap.has(threadName)) {
        threadMap.set(threadName, []);
      }
      threadMap.get(threadName)!.push(item);
    });

    const aggregated = Array.from(threadMap.entries()).map(([threadName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: threadName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    // 深度 2：按文件聚合（先按进程和线程过滤原始记录）
    const processName = stack[0];
    const threadName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按进程和线程过滤
    const filteredRecords = stepData.records.filter(item =>
      item.process === processName && item.thread === threadName
    );

    // 按文件聚合，使用 calculateMemoryStats 计算峰值内存
    const fileMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const fileName = item.file || 'Unknown File';
      if (!fileMap.has(fileName)) {
        fileMap.set(fileName, []);
      }
      fileMap.get(fileName)!.push(item);
    });

    const aggregated = Array.from(fileMap.entries()).map(([fileName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: fileName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    // 深度 3：按符号聚合（先按进程、线程和文件过滤原始记录）
    const processName = stack[0];
    const threadName = stack[1];
    const fileName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按进程、线程和文件过滤
    const filteredRecords = stepData.records.filter(item =>
      item.process === processName && item.thread === threadName && item.file === fileName
    );

    // 按符号聚合，使用 calculateMemoryStats 计算峰值内存
    const symbolMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const symbolName = item.symbol || 'Unknown Symbol';
      if (!symbolMap.has(symbolName)) {
        symbolMap.set(symbolName, []);
      }
      symbolMap.get(symbolName)!.push(item);
    });

    const aggregated = Array.from(symbolMap.entries()).map(([symbolName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: symbolName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else {
    return processPieData.value;
  }
}

function handleProcessPieDrilldown(name: string) {
  const newStack = [...processPieDrilldownStack.value, name];
  const newData = getProcessPieDrilldownData(name, newStack);
  if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(processPieData.value)) {
    return;
  }
  processPieDrilldownStack.value = newStack;
  processPieDataStack.value.push(processPieData.value);
  processPieData.value = newData;
}

function handleProcessPieDrillup() {
  if (processPieDrilldownStack.value.length === 0) return;
  processPieDrilldownStack.value.pop();
  const lastData = processPieDataStack.value.pop();
  if (lastData) {
    processPieData.value = lastData;
  }
}

function handleProcessBreadcrumbClick(index: number) {
  const targetLevel = index + 1;
  const currentLevel = processPieDrilldownStack.value.length;
  if (targetLevel >= currentLevel) return;
  const stepsToGoBack = currentLevel - targetLevel;
  for (let i = 0; i < stepsToGoBack; i++) {
    handleProcessPieDrillup();
  }
}

// 分类饼图钻取逻辑（支持多层下钻）
function getCategoryPieDrilldownData(name: string, stack: string[]) {
  // 层级：0-大类 1-小类 2-文件 3-符号
  if (stack.length === 0) {
    const data = nativeMemory2CategoryPieChartData(nativeMemoryData, props.stepId);
    const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
    return { legendData: sorted.map(d => d.name), seriesData: sorted };
  } else if (stack.length === 1) {
    // 深度 1：按小类聚合（先按大类过滤原始记录）
    const categoryName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按大类过滤
    const filteredRecords = stepData.records.filter(item =>
      getCategoryName(item.componentCategory) === categoryName
    );

    // 按小类聚合，使用 calculateMemoryStats 计算峰值内存
    const componentMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const subCategoryName = item.subCategoryName || 'Unknown Component';
      if (!componentMap.has(subCategoryName)) {
        componentMap.set(subCategoryName, []);
      }
      componentMap.get(subCategoryName)!.push(item);
    });

    const aggregated = Array.from(componentMap.entries()).map(([subCategoryName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: subCategoryName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    // 深度 2：按文件聚合（先按大类和小类过滤原始记录）
    const categoryName = stack[0];
    const subCategoryName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按大类和小类过滤
    const filteredRecords = stepData.records.filter(item =>
      getCategoryName(item.componentCategory) === categoryName &&
      item.subCategoryName === subCategoryName
    );

    // 按文件聚合，使用 calculateMemoryStats 计算峰值内存
    const fileMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const fileName = item.file || 'Unknown File';
      if (!fileMap.has(fileName)) {
        fileMap.set(fileName, []);
      }
      fileMap.get(fileName)!.push(item);
    });

    const aggregated = Array.from(fileMap.entries()).map(([fileName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: fileName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    // 深度 3：按符号聚合（先按大类、小类和文件过滤原始记录）
    const categoryName = stack[0];
    const subCategoryName = stack[1];
    const fileName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按大类、小类和文件过滤
    const filteredRecords = stepData.records.filter(item =>
      getCategoryName(item.componentCategory) === categoryName &&
      item.subCategoryName === subCategoryName &&
      item.file === fileName
    );

    // 按符号聚合，使用 calculateMemoryStats 计算峰值内存
    const symbolMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const symbolName = item.symbol || 'Unknown Symbol';
      if (!symbolMap.has(symbolName)) {
        symbolMap.set(symbolName, []);
      }
      symbolMap.get(symbolName)!.push(item);
    });

    const aggregated = Array.from(symbolMap.entries()).map(([symbolName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: symbolName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else {
    return categoryPieData.value;
  }
}

function handleCategoryPieDrilldown(name: string) {
  const newStack = [...categoryPieDrilldownStack.value, name];
  const newData = getCategoryPieDrilldownData(name, newStack);
  if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(categoryPieData.value)) {
    return;
  }
  categoryPieDrilldownStack.value = newStack;
  categoryPieDataStack.value.push(categoryPieData.value);
  categoryPieData.value = newData;
}

function handleCategoryPieDrillup() {
  if (categoryPieDrilldownStack.value.length === 0) return;
  categoryPieDrilldownStack.value.pop();
  const lastData = categoryPieDataStack.value.pop();
  if (lastData) {
    categoryPieData.value = lastData;
  }
}

function handleCategoryBreadcrumbClick(index: number) {
  const targetLevel = index + 1;
  const currentLevel = categoryPieDrilldownStack.value.length;
  if (targetLevel >= currentLevel) return;
  const stepsToGoBack = currentLevel - targetLevel;
  for (let i = 0; i < stepsToGoBack; i++) {
    handleCategoryPieDrillup();
  }
}

// 饼图钻取逻辑（事件类型维度）
// 使用 totalMem（总分配内存）而不是 curMem
function getEventTypePieDrilldownData(name: string, stack: string[]) {
  // 层级：0-事件类型 1-线程 2-文件 3-符号
  if (stack.length === 0) {
    const data = nativeMemory2EventTypePieChartData(nativeMemoryData, props.stepId);
    const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
    return { legendData: sorted.map(d => d.name), seriesData: sorted };
  } else if (stack.length === 1) {
    // 深度 1：按线程聚合（先按事件类型过滤原始记录）
    const eventTypeName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按事件类型过滤
    const filteredRecords = stepData.records.filter(item => {
      const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
      return itemEventTypeName === eventTypeName;
    });

    // 按线程聚合，使用 calculateMemoryStats 计算峰值内存
    const threadMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const threadName = item.thread || 'Unknown Thread';
      if (!threadMap.has(threadName)) {
        threadMap.set(threadName, []);
      }
      threadMap.get(threadName)!.push(item);
    });

    const aggregated = Array.from(threadMap.entries()).map(([threadName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: threadName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    // 深度 2：按文件聚合（先按事件类型和线程过滤原始记录）
    const eventTypeName = stack[0];
    const threadName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按事件类型和线程过滤
    const filteredRecords = stepData.records.filter(item => {
      const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
      return itemEventTypeName === eventTypeName && item.thread === threadName;
    });

    // 按文件聚合，使用 calculateMemoryStats 计算峰值内存
    const fileMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const fileName = item.file || 'Unknown File';
      if (!fileMap.has(fileName)) {
        fileMap.set(fileName, []);
      }
      fileMap.get(fileName)!.push(item);
    });

    const aggregated = Array.from(fileMap.entries()).map(([fileName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: fileName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    // 深度 3：按符号聚合（先按事件类型、线程和文件过滤原始记录）
    const eventTypeName = stack[0];
    const threadName = stack[1];
    const fileName = name;
    if (!nativeMemoryData) return { legendData: [], seriesData: [] };
    const stepKey = `step${props.stepId}`;
    const stepData = nativeMemoryData[stepKey];
    if (!stepData || !stepData.records) return { legendData: [], seriesData: [] };

    // 先按事件类型、线程和文件过滤
    const filteredRecords = stepData.records.filter(item => {
      const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
      return itemEventTypeName === eventTypeName && item.thread === threadName && item.file === fileName;
    });

    // 按符号聚合，使用 calculateMemoryStats 计算峰值内存
    const symbolMap = new Map<string, typeof filteredRecords>();
    filteredRecords.forEach(item => {
      const symbolName = item.symbol || 'Unknown Symbol';
      if (!symbolMap.has(symbolName)) {
        symbolMap.set(symbolName, []);
      }
      symbolMap.get(symbolName)!.push(item);
    });

    const aggregated = Array.from(symbolMap.entries()).map(([symbolName, records]) => {
      const stats = calculateMemoryStats(records);
      return { name: symbolName, value: stats.peakMem };
    });

    const sorted = aggregated.sort((a, b) => b.value - a.value);
    const legendData = sorted.map(d => d.name);
    const seriesData = sorted;
    return { legendData, seriesData };
  } else {
    return eventTypePieData.value;
  }
}

function handleEventTypePieDrilldown(name: string) {
  const newStack = [...eventTypePieDrilldownStack.value, name];
  const newData = getEventTypePieDrilldownData(name, newStack);
  if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(eventTypePieData.value)) {
    return;
  }
  eventTypePieDrilldownStack.value = newStack;
  eventTypePieDataStack.value.push(eventTypePieData.value);
  eventTypePieData.value = newData;
}

function handleEventTypePieDrillup() {
  if (eventTypePieDrilldownStack.value.length === 0) return;
  eventTypePieDrilldownStack.value.pop();
  const lastData = eventTypePieDataStack.value.pop();
  if (lastData) {
    eventTypePieData.value = lastData;
  }
}

function handleEventTypeBreadcrumbClick(index: number) {
  const targetLevel = index + 1;
  const currentLevel = eventTypePieDrilldownStack.value.length;
  if (targetLevel >= currentLevel) return;
  const stepsToGoBack = currentLevel - targetLevel;
  for (let i = 0; i < stepsToGoBack; i++) {
    handleEventTypePieDrillup();
  }
}

// 面包屑标签
function getBreadcrumbLabel(dimension: 'process' | 'category' | 'eventType', level: number, item?: string): string {
  if (dimension === 'process') {
    const labels = ['进程', '线程', '文件', '符号'];
    return level === 0 ? labels[0] : item || labels[level];
  } else if (dimension === 'eventType') {
    // 事件类型维度：事件类型 > 线程 > 文件 > 符号
    const labels = ['事件类型', '线程', '文件', '符号'];
    return level === 0 ? labels[0] : item || labels[level];
  } else {
    // 分类维度：大类 > 小类 > 文件 > 符号
    const labels = ['大类', '小类', '文件', '符号'];
    if (level === 0) {
      return labels[0];
    } else if (level === 1) {
      // 第一层是大类名称
      return item || labels[1];
    } else {
      // 第二层及以后是小类、文件、符号
      return item || labels[level];
    }
  }
}

// 表格数据过滤（进程维度）- 根据饼图下钻条件添加筛选
const filteredThreadMemoryDataDrill = computed(() => {
  const drilldownLevel = processPieDrilldownStack.value.length;
  if (drilldownLevel === 0) {
    return sortByMaxMem(mergedThreadMemoryData.value);
  }
  // 根据进程过滤
  const processName = processPieDrilldownStack.value[0];
  return sortByMaxMem(mergedThreadMemoryData.value.filter(item => item.process === processName));
});

const filteredFileMemoryDataDrill = computed(() => {
  const drilldownLevel = processPieDrilldownStack.value.length;
  if (drilldownLevel === 0) {
    return sortByMaxMem(mergedFileMemoryData.value);
  }
  // 根据进程过滤
  const processName = processPieDrilldownStack.value[0];
  let filtered = mergedFileMemoryData.value.filter(item => item.process === processName);

  // 如果下钻到线程，再根据线程过滤
  if (drilldownLevel >= 2) {
    const threadName = processPieDrilldownStack.value[1];
    filtered = filtered.filter(item => item.thread === threadName);
  }

  return sortByMaxMem(filtered);
});

const filteredSymbolMemoryDataDrill = computed(() => {
  const drilldownLevel = processPieDrilldownStack.value.length;
  if (drilldownLevel === 0) {
    return sortByMaxMem(mergedSymbolMemoryData.value);
  }
  // 根据进程过滤
  const processName = processPieDrilldownStack.value[0];
  let filtered = mergedSymbolMemoryData.value.filter(item => item.process === processName);

  // 如果下钻到线程，再根据线程过滤
  if (drilldownLevel >= 2) {
    const threadName = processPieDrilldownStack.value[1];
    filtered = filtered.filter(item => item.thread === threadName);
  }

  // 如果下钻到文件，再根据文件过滤
  if (drilldownLevel >= 3) {
    const fileName = processPieDrilldownStack.value[2];
    filtered = filtered.filter(item => item.file === fileName);
  }

  return sortByMaxMem(filtered);
});

// 表格数据过滤（分类维度）- 根据饼图下钻条件添加筛选
const filteredComponentMemoryDataDrill = computed(() => {
  const drilldownLevel = categoryPieDrilldownStack.value.length;
  if (drilldownLevel === 0) {
    return sortByMaxMem(mergedComponentMemoryData.value);
  }
  // 根据大类过滤
  const categoryName = categoryPieDrilldownStack.value[0];
  return sortByMaxMem(mergedComponentMemoryData.value.filter(item => item.category === categoryName));
});

const filteredFileCategoryMemoryDataDrill = computed(() => {
  const drilldownLevel = categoryPieDrilldownStack.value.length;
  if (drilldownLevel === 0) {
    return sortByMaxMem(mergedFileCategoryMemoryData.value);
  }
  // 根据大类过滤
  const categoryName = categoryPieDrilldownStack.value[0];
  let filtered = mergedFileCategoryMemoryData.value.filter(item => item.category === categoryName);

  // 如果下钻到小类，再根据小类过滤
  if (drilldownLevel >= 2) {
    const componentName = categoryPieDrilldownStack.value[1];
    filtered = filtered.filter(item => item.componentName === componentName);
  }

  return sortByMaxMem(filtered);
});

const filteredSymbolCategoryMemoryDataDrill = computed(() => {
  const drilldownLevel = categoryPieDrilldownStack.value.length;
  if (drilldownLevel === 0) {
    return sortByMaxMem(mergedSymbolCategoryMemoryData.value);
  }
  // 根据大类过滤
  const categoryName = categoryPieDrilldownStack.value[0];
  let filtered = mergedSymbolCategoryMemoryData.value.filter(item => item.category === categoryName);

  // 如果下钻到小类，再根据小类过滤
  if (drilldownLevel >= 2) {
    const componentName = categoryPieDrilldownStack.value[1];
    filtered = filtered.filter(item => item.componentName === componentName);
  }

  // 如果下钻到文件，再根据文件过滤
  if (drilldownLevel >= 3) {
    const fileName = categoryPieDrilldownStack.value[2];
    filtered = filtered.filter(item => item.file === fileName);
  }

  return sortByMaxMem(filtered);
});

// 事件类型表格数据（与事件类型饼图联动，支持多层下钻）
const eventTypeTableData = computed(() => {
  if (!nativeMemoryData) return [];
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  let records = stepData.records;
  const drilldownLevel = eventTypePieDrilldownStack.value.length;

  // 根据钻取深度过滤数据
  if (drilldownLevel > 0) {
    const eventTypeName = eventTypePieDrilldownStack.value[0];
    records = records.filter(item => {
      const itemEventTypeName = getEventTypeName(item.eventType, item.subEventType);
      return itemEventTypeName === eventTypeName;
    });
  }

  if (drilldownLevel > 1) {
    const threadName = eventTypePieDrilldownStack.value[1];
    records = records.filter(item => item.thread === threadName);
  }

  if (drilldownLevel > 2) {
    const fileName = eventTypePieDrilldownStack.value[2];
    records = records.filter(item => item.file === fileName);
  }

  // 根据钻取深度决定聚合维度
  if (drilldownLevel === 0) {
    // 深度 0：按事件类型聚合
    const eventTypeMap = new Map<string, typeof records>();

    records.forEach(item => {
      const eventTypeName = getEventTypeName(item.eventType, item.subEventType);
      if (!eventTypeMap.has(eventTypeName)) {
        eventTypeMap.set(eventTypeName, []);
      }
      eventTypeMap.get(eventTypeName)!.push(item);
    });

    return Array.from(eventTypeMap.entries())
      .map(([eventTypeName, records]) => {
        const stats = calculateMemoryStats(records);
        return {
          eventTypeName,
          eventNum: stats.eventNum,
          peakMem: stats.peakMem,
          avgMem: stats.avgMem,
          totalAllocMem: stats.totalAllocMem,
          totalFreeMem: stats.totalFreeMem,
          start_ts: stats.start_ts,
        };
      })
      .sort((a, b) => b.peakMem - a.peakMem);
  } else if (drilldownLevel === 1) {
    // 深度 1：按线程聚合
    const threadMap = new Map<string, typeof records>();

    records.forEach(item => {
      const threadName = item.thread || 'Unknown Thread';
      if (!threadMap.has(threadName)) {
        threadMap.set(threadName, []);
      }
      threadMap.get(threadName)!.push(item);
    });

    return Array.from(threadMap.entries())
      .map(([thread, records]) => {
        const stats = calculateMemoryStats(records);
        return {
          eventTypeName: thread,
          eventNum: stats.eventNum,
          peakMem: stats.peakMem,
          avgMem: stats.avgMem,
          totalAllocMem: stats.totalAllocMem,
          totalFreeMem: stats.totalFreeMem,
          start_ts: stats.start_ts,
        };
      })
      .sort((a, b) => b.peakMem - a.peakMem);
  } else if (drilldownLevel === 2) {
    // 深度 2：按文件聚合
    const fileMap = new Map<string, typeof records>();

    records.forEach(item => {
      const fileName = item.file || 'Unknown File';
      if (!fileMap.has(fileName)) {
        fileMap.set(fileName, []);
      }
      fileMap.get(fileName)!.push(item);
    });

    return Array.from(fileMap.entries())
      .map(([file, records]) => {
        const stats = calculateMemoryStats(records);
        return {
          eventTypeName: file,
          eventNum: stats.eventNum,
          peakMem: stats.peakMem,
          avgMem: stats.avgMem,
          totalAllocMem: stats.totalAllocMem,
          totalFreeMem: stats.totalFreeMem,
          start_ts: stats.start_ts,
        };
      })
      .sort((a, b) => b.peakMem - a.peakMem);
  } else {
    // 深度 3：按符号聚合
    const symbolMap = new Map<string, typeof records>();

    records.forEach(item => {
      const symbolName = item.symbol || 'Unknown Symbol';
      if (!symbolMap.has(symbolName)) {
        symbolMap.set(symbolName, []);
      }
      symbolMap.get(symbolName)!.push(item);
    });

    return Array.from(symbolMap.entries())
      .map(([symbol, records]) => {
        const stats = calculateMemoryStats(records);
        return {
          eventTypeName: symbol,
          eventNum: stats.eventNum,
          peakMem: stats.peakMem,
          avgMem: stats.avgMem,
          totalAllocMem: stats.totalAllocMem,
          totalFreeMem: stats.totalFreeMem,
          start_ts: stats.start_ts,
        };
      })
      .sort((a, b) => b.peakMem - a.peakMem);
  }
});

// 事件类型表头标签（根据下钻层级动态变化）
const eventTypeTableLabel = computed(() => {
  const drilldownLevel = eventTypePieDrilldownStack.value.length;
  const labels = ['事件类型', '线程', '文件', '符号'];
  return labels[drilldownLevel] || '事件类型';
});

// 进程表格数据（只显示进程列表，不支持下钻）
const processTableData = computed(() => {
  if (!nativeMemoryData) return [];
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  const records = stepData.records.filter(item => item.pid !== null && item.pid !== undefined);

  // 按进程聚合
  const processMap = new Map<string, typeof records>();

  records.forEach(item => {
    const processName = item.process || "Unknown Process";
    if (!processMap.has(processName)) {
      processMap.set(processName, []);
    }
    processMap.get(processName)!.push(item);
  });

  return Array.from(processMap.entries())
    .map(([process, records]) => {
      const stats = calculateMemoryStats(records);
      return {
        process,
        eventNum: stats.eventNum,
        peakMem: stats.peakMem,
        avgMem: stats.avgMem,
        totalAllocMem: stats.totalAllocMem,
        totalFreeMem: stats.totalFreeMem,
        start_ts: stats.start_ts,
      };
    })
    .sort((a, b) => b.peakMem - a.peakMem);
});

// 分类表格数据（只显示大类列表，不支持下钻）
const categoryTableData = computed(() => {
  if (!nativeMemoryData) return [];
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  const records = stepData.records;

  // 按大类聚合
  const categoryMap = new Map<number, typeof records>();

  records.forEach(item => {
    const category = item.componentCategory;
    if (!categoryMap.has(category)) {
      categoryMap.set(category, []);
    }
    categoryMap.get(category)!.push(item);
  });

  return Array.from(categoryMap.entries())
    .map(([category, records]) => {
      const stats = calculateMemoryStats(records);
      return {
        componentName: getCategoryName(category),
        eventNum: stats.eventNum,
        peakMem: stats.peakMem,
        avgMem: stats.avgMem,
        totalAllocMem: stats.totalAllocMem,
        totalFreeMem: stats.totalFreeMem,
        start_ts: stats.start_ts,
      };
    })
    .sort((a, b) => b.peakMem - a.peakMem);
});
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

