<template>
  <div class="step-load-container">
    <!-- 步骤负载分析 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 进程负载饼图 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">进程负载分布</span>
          </h3>
          <!-- 面包屑导航 -->
          <div v-if="processPieDrilldownStack.length > 0" class="breadcrumb-nav">
            <span v-for="(item, index) in processPieDrilldownStack" :key="index" class="breadcrumb-item">
              <i v-if="index > 0" class="breadcrumb-separator">></i>
              <span @click="handleProcessBreadcrumbClick(index)">
                {{ getBreadcrumbLabel('process', index, item) }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="stepId" height="400px" :chart-data="processPieData" :title="pieChartTitle"
            :drilldown-stack="processPieDrilldownStack" :legend-truncate="false" 
            @drilldown="handleProcessPieDrilldown" @drillup="handleProcessPieDrillup"
          />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 分类负载饼图 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">分类负载分布</span>
          </h3>
          <!-- 面包屑导航 -->
          <div v-if="stepPieDrilldownStack.length > 0" class="breadcrumb-nav">
            <span v-for="(item, index) in stepPieDrilldownStack" :key="index" class="breadcrumb-item">
              <i v-if="index > 0" class="breadcrumb-separator">></i>
              <span @click="handleStepBreadcrumbClick(index)">
                {{ getBreadcrumbLabel('category', index, item) }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="stepId" height="400px" :chart-data="stepPieData" :title="pieChartTitle"
            :drilldown-stack="stepPieDrilldownStack" :legend-truncate="false" 
            @drilldown="handleStepPieDrilldown" @drillup="handleStepPieDrillup"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 详细负载表格 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 线程负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">线程负载</span>
          </h3>
          <PerfThreadTable
            :step-id="stepId" :data="filteredThreadPerformanceDataDrill" :hide-column="isHidden"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 小分类负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">小分类负载</span>
          </h3>
          <PerfThreadTable
            :step-id="stepId" :data="filteredComponentNamePerformanceDataDrill"
            :hide-column="isHidden" :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 文件负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载</span>
          </h3>
          <PerfFileTable
            :step-id="stepId" :data="filteredFilePerformanceDataDrill" :hide-column="isHidden"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 文件负载（分类） -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载（分类）</span>
          </h3>
          <PerfFileTable
            :step-id="stepId" :data="filteredFilePerformanceData1Drill" :hide-column="isHidden"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 函数负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">函数负载</span>
          </h3>
          <PerfSymbolTable
            :step-id="stepId" :data="filteredSymbolPerformanceDataDrill" :hide-column="isHidden"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 函数负载（分类） -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">函数负载（分类）</span>
          </h3>
          <PerfSymbolTable
            :step-id="stepId" :data="filteredSymbolPerformanceData1Drill" :hide-column="isHidden"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch } from 'vue';
//import { Download } from '@element-plus/icons-vue';
import PerfThreadTable from './tables/PerfThreadTable.vue';
import PerfFileTable from './tables/PerfFileTable.vue';
import PerfSymbolTable from './tables/PerfSymbolTable.vue';
import PieChart from '../../../common/charts/PieChart.vue';
import { useJsonDataStore } from '../../../../stores/jsonDataStore.ts';
import { 
  calculateComponentNameData, 
  calculateFileData, 
  calculateFileData1, 
  calculateSymbolData, 
  calculateSymbolData1, 
  calculateThreadData, 
  processJson2PieChartData, 
  processJson2ProcessPieChartData, 
  calculateCategorysData, 
  type ProcessDataItem, 
  type ThreadDataItem, 
  type FileDataItem, 
  type SymbolDataItem 
} from '@/utils/jsonUtil.ts';
//import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';

const props = defineProps<{
  stepId: number;
}>();

const isHidden = true;

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData;

console.log('步骤负载组件获取到的 JSON 数据:', props.stepId);

// const testSteps = ref(
//   perfData!.steps.map((step, index) => ({
//     id: index + 1,
//     step_name: step.step_name,
//     count: step.count,
//     round: step.round,
//     perf_data_path: step.perf_data_path,
//   }))
// );

// interface TestStep {
//   id: number;
//   step_name: string;
//   count: number;
//   round: number;
//   perf_data_path: string;
// }

// 获取当前步骤信息
// const stepInfo = computed(() => {
//   return testSteps.value.find(step => step.id === props.stepId);
// });

// 动态聚合数据
const mergedThreadPerformanceData = computed(() =>
  calculateThreadData(perfData!, null, false)
);
const mergedComponentNamePerformanceData = computed(() =>
  calculateComponentNameData(perfData!, null, false)
);
const mergedFilePerformanceData = computed(() =>
  calculateFileData(perfData!, null, false)
);
const mergedFilePerformanceData1 = computed(() =>
  calculateFileData1(perfData!, null, false)
);
const mergedSymbolsPerformanceData = computed(() =>
  calculateSymbolData(perfData!, null, false)
);
const mergedSymbolsPerformanceData1 = computed(() =>
  calculateSymbolData1(perfData!, null, false)
);

// 工具函数：安全排序，避免副作用
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// // 格式化数字
// const formatNumber = (num: number) => {
//   return num.toLocaleString();
// };

// // 格式化功耗信息
// const formatEnergy = (milliseconds: number) => {
//   const energy = calculateEnergyConsumption(milliseconds);
//   return `${energy} mAs`;
// };

const processPieDrilldownStack = ref<string[]>([]);
const processPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const processPieData = ref(processJson2ProcessPieChartData(perfData!, props.stepId));
const pieChartTitle = perfData?.steps[0].data[0].eventType == 0 ? 'cycles' : 'instructions';

const stepPieDrilldownStack = ref<string[]>([]);
const stepPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const stepPieData = ref(processJson2PieChartData(perfData!, props.stepId));

// 监听stepId变化，重新加载数据
watch(() => props.stepId, (newStepId) => {
  processPieData.value = processJson2ProcessPieChartData(perfData!, newStepId);
  stepPieData.value = processJson2PieChartData(perfData!, newStepId);
  processPieDrilldownStack.value = [];
  processPieDataStack.value = [];
  stepPieDrilldownStack.value = [];
  stepPieDataStack.value = [];
}, { immediate: true });

// 饼图钻取逻辑
function getProcessPieDrilldownData(name: string, stack: string[]) {
  // 层级：0-进程 1-线程 2-文件 3-符号
  if (stack.length === 0) {
    const data = processJson2ProcessPieChartData(perfData!, props.stepId);
    const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
    return { legendData: sorted.map(d => d.name), seriesData: sorted };
  } else if (stack.length === 1) {
    const processName = name;
    const threadData = calculateThreadData(perfData!, null, false).filter((item: ThreadDataItem) =>
      item.process === processName && item.stepId === props.stepId);
    const sorted = [...threadData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ThreadDataItem) => d.thread);
    const seriesData = sorted.map((d: ThreadDataItem) => ({ name: d.thread, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    const processName = stack[0];
    const threadName = name;
    const fileData = calculateFileData(perfData!, null, false).filter((item: FileDataItem) =>
      item.process === processName && item.thread === threadName && item.stepId === props.stepId);
    const sorted = [...fileData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: FileDataItem) => d.file);
    const seriesData = sorted.map((d: FileDataItem) => ({ name: d.file, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    const processName = stack[0];
    const threadName = stack[1];
    const fileName = name;
    const symbolData = calculateSymbolData(perfData!, null, false).filter((item: SymbolDataItem) =>
      item.process === processName && item.thread === threadName && item.file === fileName && item.stepId === props.stepId);
    const sorted = [...symbolData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: SymbolDataItem) => d.symbol);
    const seriesData = sorted.map((d: SymbolDataItem) => ({ name: d.symbol, value: d.instructions }));
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
  if (processPieDrilldownStack.value.length > 0) {
    processPieDrilldownStack.value.pop();
    processPieData.value = processPieDataStack.value.pop() || processPieData.value;
  }
}

function getDrilldownPieData(name: string, stack: string[]) {
  // 新层级：0-大分类 1-小分类 2-文件 3-符号
  if (stack.length === 0) {
    const categoryData = calculateCategorysData(perfData!, null, false);
    const sorted = [...categoryData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ProcessDataItem) => d.category);
    const seriesData = sorted.map((d: ProcessDataItem) => ({ name: d.category, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 1) {
    const category = name;
    const componentData = calculateComponentNameData(perfData!, null, false).filter((d: ThreadDataItem) =>
      d.category === category && d.stepId === props.stepId);
    const sorted = [...componentData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ThreadDataItem) => d.subCategoryName);
    const seriesData = sorted.map((d: ThreadDataItem) => ({ name: d.subCategoryName, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    const category = stack[0];
    const subCategoryName = name;
    const fileData = calculateFileData1(perfData!, null, false).filter((d: FileDataItem) =>
      d.category === category && d.subCategoryName === subCategoryName && d.stepId === props.stepId);
    const sorted = [...fileData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: FileDataItem) => d.file);
    const seriesData = sorted.map((d: FileDataItem) => ({ name: d.file, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    const category = stack[0];
    const subCategoryName = stack[1];
    const file = name;
    const symbolData = calculateSymbolData1(perfData!, null, false).filter((d: SymbolDataItem) =>
      d.category === category && d.subCategoryName === subCategoryName && d.file === file && d.stepId === props.stepId);
    const sorted = [...symbolData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: SymbolDataItem) => d.symbol);
    const seriesData = sorted.map((d: SymbolDataItem) => ({ name: d.symbol, value: d.instructions }));
    return { legendData, seriesData };
  } else {
    return stepPieData.value;
  }
}

function handleStepPieDrilldown(name: string) {
  const newStack = [...stepPieDrilldownStack.value, name];
  const newData = getDrilldownPieData(name, newStack);
  if (!newData.seriesData || newData.seriesData.length === 0 || JSON.stringify(newData) === JSON.stringify(stepPieData.value)) {
    return;
  }
  stepPieDrilldownStack.value = newStack;
  stepPieDataStack.value.push(stepPieData.value);
  stepPieData.value = newData;
}

function handleStepPieDrillup() {
  if (stepPieDrilldownStack.value.length > 0) {
    stepPieDrilldownStack.value.pop();
    stepPieData.value = stepPieDataStack.value.pop() || stepPieData.value;
  }
}

// 获取面包屑标签
function getBreadcrumbLabel(type: 'process' | 'category', level: number, item: string): string {
  if (type === 'process') {
    const labels = ['进程', '线程', '文件', '符号'];
    return `${labels[level]}: ${item}`;
  } else {
    const labels = ['大分类', '小分类', '文件', '符号'];
    return `${labels[level]}: ${item}`;
  }
}

// 处理面包屑点击
function handleProcessBreadcrumbClick(targetIndex: number) {
  const targetLevel = targetIndex + 1;
  while (processPieDrilldownStack.value.length > targetLevel) {
    processPieDrilldownStack.value.pop();
    processPieData.value = processPieDataStack.value.pop() || processPieData.value;
  }
}

function handleStepBreadcrumbClick(targetIndex: number) {
  const targetLevel = targetIndex + 1;
  while (stepPieDrilldownStack.value.length > targetLevel) {
    stepPieDrilldownStack.value.pop();
    stepPieData.value = stepPieDataStack.value.pop() || stepPieData.value;
  }
}

// 计算属性，根据当前步骤 ID 过滤负载数据
const filteredThreadPerformanceData = computed(() => {
  return sortByInstructions(
    mergedThreadPerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredComponentNamePerformanceData = computed(() => {
  return sortByInstructions(
    mergedComponentNamePerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredFilePerformanceData = computed(() => {
  return sortByInstructions(
    mergedFilePerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredFilePerformanceData1 = computed(() => {
  return sortByInstructions(
    mergedFilePerformanceData1.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredSymbolPerformanceData = computed(() => {
  return sortByInstructions(
    mergedSymbolsPerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredSymbolPerformanceData1 = computed(() => {
  return sortByInstructions(
    mergedSymbolsPerformanceData1.value.filter((item) => item.stepId === props.stepId)
  );
});



// 左侧 drill 联动
const filteredThreadPerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = filteredThreadPerformanceData.value;
  if (stack.length === 1) {
    data = data.filter(d => d.process === stack[0]);
  }
  return data;
});

const filteredFilePerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = filteredFilePerformanceData.value;
  if (stack.length === 1) {
    data = data.filter(d => d.process === stack[0]);
  } else if (stack.length === 2) {
    data = data.filter(d => d.process === stack[0] && d.thread === stack[1]);
  }
  return data;
});

const filteredSymbolPerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = filteredSymbolPerformanceData.value;
  if (stack.length === 1) {
    data = data.filter(d => d.process === stack[0]);
  } else if (stack.length === 2) {
    data = data.filter(d => d.process === stack[0] && d.thread === stack[1]);
  } else if (stack.length === 3) {
    data = data.filter(d => d.process === stack[0] && d.thread === stack[1] && d.file === stack[2]);
  }
  return data;
});

// 右侧 drill 联动
const filteredComponentNamePerformanceDataDrill = computed(() => {
  const stack = stepPieDrilldownStack.value;
  let data = filteredComponentNamePerformanceData.value;
  if (stack.length === 1) {
    data = data.filter(d => d.category === stack[0]);
  }
  return data;
});

const filteredFilePerformanceData1Drill = computed(() => {
  const stack = stepPieDrilldownStack.value;
  let data = filteredFilePerformanceData1.value;
  if (stack.length === 1) {
    data = data.filter(d => d.category === stack[0]);
  } else if (stack.length === 2) {
    data = data.filter(d => d.category === stack[0] && d.subCategoryName === stack[1]);
  }
  return data;
});

const filteredSymbolPerformanceData1Drill = computed(() => {
  const stack = stepPieDrilldownStack.value;
  let data = filteredSymbolPerformanceData1.value;
  if (stack.length === 1) {
    data = data.filter(d => d.category === stack[0]);
  } else if (stack.length === 2) {
    data = data.filter(d => d.category === stack[0] && d.subCategoryName === stack[1]);
  } else if (stack.length === 3) {
    data = data.filter(d => d.category === stack[0] && d.subCategoryName === stack[1] && d.file === stack[2]);
  }
  return data;
});

// 下载功能
// const downloadPerfData = () => {
//   if (!stepInfo.value) return;
//   const link = document.createElement('a');
//   link.href = '../hiperf/step' + props.stepId + '/perf.data';
//   link.download = stepInfo.value.step_name + 'perf.data';
//   document.body.appendChild(link);
//   link.click();
//   setTimeout(() => {
//     document.body.removeChild(link);
//   }, 100);
// };

// const downloadTraceData = () => {
//   if (!stepInfo.value) return;
//   const link = document.createElement('a');
//   link.href = '../htrace/step' + props.stepId + '/trace.htrace';
//   link.download = stepInfo.value.step_name + 'trace.htrace';
//   document.body.appendChild(link);
//   link.click();
//   setTimeout(() => {
//     document.body.removeChild(link);
//   }, 100);
//   setTimeout(() => {
//     window.open('https://localhost:9000/application/', 'trace example');
//   }, 300);
// };
</script>

<style scoped>
.step-load-container {
  padding: 20px;
  background: #f5f7fa;
}

.step-info-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 24px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 24px;
}

.step-badge {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 20px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 16px;
  min-width: 100px;
  text-align: center;
}

.step-details {
  flex: 1;
}

.step-title {
  margin: 0 0 12px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.step-metrics {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-label {
  color: #606266;
  font-size: 14px;
}

.metric-value {
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.step-actions {
  display: flex;
  gap: 12px;
}

.data-panel {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.version-tag {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 500;
}

/* 面包屑导航样式 */
.breadcrumb-nav {
  padding: 8px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.breadcrumb-item {
  color: #606266;
  cursor: pointer;
  transition: color 0.2s;
}

.breadcrumb-item:hover {
  color: #667eea;
}

.breadcrumb-separator {
  margin: 0 8px;
  color: #c0c4cc;
  font-style: normal;
}

.breadcrumb-item:last-child {
  color: #667eea;
  font-weight: 500;
}

/* Tab样式 */
.analysis-tabs {
  margin-top: 20px;
}

.analysis-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

.analysis-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 500;
}

/* Native Memory 样式 */
.memory-summary {
  margin-left: 20px;
  font-size: 14px;
  color: #606266;
  font-weight: normal;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .step-load-container {
    padding: 16px;
  }

  .step-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .step-metrics {
    flex-direction: column;
    gap: 12px;
  }

  .step-actions {
    width: 100%;
    justify-content: stretch;
  }

  .step-actions .el-button {
    flex: 1;
  }
}

@media (max-width: 480px) {
  .step-info-card {
    padding: 16px;
  }

  .step-title {
    font-size: 20px;
  }

  .step-badge {
    padding: 8px 16px;
    font-size: 14px;
  }
}
</style>
