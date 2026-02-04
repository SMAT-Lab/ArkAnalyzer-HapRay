<template>
  <div class="performance-comparison">
    <!-- 无数据提示 -->
    <div v-if="!hasPerfData" class="no-data-tip">
      <el-empty description="暂无负载分析数据" />
    </div>

    <!-- 负载数据展示（仅当有数据时显示） -->
    <template v-else>
    <div class="info-box">
      负载分类说明：
      <p>APP_ABC => 应用代码 |
        APP_LIB => 应用三方ArkTS库 |
        APP_SO => 应用native库 |
        OS_Runtime => 系统运行时 |
        SYS_SDK => 系统SDK |
        RN => 三方框架React Native |
        Flutter => 三方框架Flutter |
        WEB => 三方框架ArkWeb</p>
    </div>
    
    <el-descriptions :title="performanceData.app_name" :column="1" class="beautified-descriptions">
      <el-descriptions-item label="系统版本：">{{ performanceData.rom_version }}</el-descriptions-item>
      <el-descriptions-item label="应用版本：">{{ performanceData.app_version }}</el-descriptions-item>
      <el-descriptions-item>
        <div class="description-item-content">
          场景名称：{{ performanceData.scene }}
        </div>
      </el-descriptions-item>
    </el-descriptions>
    
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <PieChart :chart-data="scenePieData" :title="pieChartTitle" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <BarChart :chart-data="perfData" />
        </div>
      </el-col>
    </el-row>
    
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chart-data="perfData" :series-type="LeftLineChartSeriesType" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chart-data="perfData" :series-type="RightLineChartSeriesType" />
        </div>
      </el-col>
    </el-row>

    <!-- 测试步骤导航 -->
    <div class="step-nav">
      <div
        :class="[
          'step-item',
          {
            active: currentStepIndex === 0,
          },
        ]" @click="handleStepClick(0)">
        <div class="step-header">
          <span class="step-order">STEP 0</span>
          <span class="step-duration">{{ getTotalTestStepsCount() }}</span>
          <span class="step-duration">{{ formatEnergy(getTotalTestStepsCount()) }}</span>
        </div>
        <div class="step-name">全部步骤</div>
      </div>
      <div
        v-for="(step, index) in testSteps" :key="index" :class="[
          'step-item',
          {
            active: currentStepIndex === step.id,
          },
        ]" @click="handleStepClick(step.id)">
        <div class="step-header">
          <span class="step-order">STEP {{ step.id }}</span>
          <span class="step-duration">{{ formatDuration(getStepPerfData(index).count) }}</span>
          <span class="step-duration">{{ formatEnergy(getStepPerfData(index).count) }}</span>
        </div>
        <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
        <!-- <button
          class="beautiful-btn primary-btn"
          @click="handleDownloadAndRedirect('perf.data', step.id, step.step_name)">
          下载perf
        </button>
        <button
          class="beautiful-btn primary-btn"
          @click="handleDownloadAndRedirect('trace.htrace', step.id, step.step_name)">
          下载trace
        </button> -->
      </div>
    </div>

    <!-- 负载对比区域 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 步骤饼图（左，进程-线程-文件-符号） -->
        <div class="data-panel">
          <!-- 面包屑导航 -->
          <div class="breadcrumb-nav">
            <span v-for="(item, index) in processBreadcrumbItems" :key="index" class="breadcrumb-item">
              <i v-if="index > 0" class="breadcrumb-separator">></i>
              <span @click="handleProcessBreadcrumbClick(index)">
                {{ item }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="currentStepIndex" height="585px" :chart-data="processPieData" :title="pieChartTitle"
            :drilldown-stack="processPieDrilldownStack" :legend-truncate="false" @drilldown="handleProcessPieDrilldown"
            @drillup="handleProcessPieDrillup"
          />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 步骤饼图（右，分类-小分类-文件-符号） -->
        <div class="data-panel">
          <!-- 面包屑导航 -->
          <div class="breadcrumb-nav">
            <span v-for="(item, index) in stepBreadcrumbItems" :key="index" class="breadcrumb-item">
              <i v-if="index > 0" class="breadcrumb-separator">></i>
              <span @click="handleStepBreadcrumbClick(index)">
                {{ item }}
              </span>
            </span>
          </div>
          <PieChart
            :step-id="currentStepIndex" height="585px" :chart-data="stepPieData" :title="pieChartTitle"
            :drilldown-stack="stepPieDrilldownStack" :legend-truncate="false" @drilldown="handleStepPieDrilldown"
            @drillup="handleStepPieDrillup"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 负载表格区域：根据面包屑下钻层级隐藏上层表格 -->
    <!-- 左侧（进程）：0首页 1进程 2线程 3文件 4符号 | 右侧（分类）：0首页 1大分类 2小分类 3文件 4符号 -->
    <el-row v-if="processPieDrilldownStack.length < 2 || stepPieDrilldownStack.length < 2" :gutter="20">
      <el-col :span="12">
        <!-- 线程负载 -->
        <div v-if="processPieDrilldownStack.length < 2" class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">线程负载</span>
          </h3>
          <PerfThreadTable
            :step-id="currentStepIndex" :data="filteredThreadPerformanceDataDrill" :hide-column="isHidden"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 小分类负载 -->
        <div v-if="stepPieDrilldownStack.length < 2" class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">小分类负载</span>
          </h3>
          <PerfThreadTable
            :step-id="currentStepIndex" :data="filteredComponentNamePerformanceDataDrill"
            :hide-column="isHidden" :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <el-row v-if="processPieDrilldownStack.length < 3 || stepPieDrilldownStack.length < 3" :gutter="20">
      <el-col :span="12">
        <!-- 文件负载 -->
        <div v-if="processPieDrilldownStack.length < 3" class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载</span>
          </h3>
          <PerfFileTable
            :step-id="currentStepIndex" :data="filteredFilePerformanceDataDrill" :hide-column="isHidden"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 文件负载（分类） -->
        <div v-if="stepPieDrilldownStack.length < 3" class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载</span>
          </h3>
          <PerfFileTable
            :step-id="currentStepIndex" :data="filteredFilePerformanceData1Drill" :hide-column="isHidden"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <el-row v-if="processPieDrilldownStack.length < 4 || stepPieDrilldownStack.length < 4" :gutter="20">
      <el-col :span="12">
        <!-- 函数负载 -->
        <div v-if="processPieDrilldownStack.length < 4" class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">函数负载</span>
          </h3>
          <PerfSymbolTable
            :step-id="currentStepIndex" :data="filteredSymbolPerformanceDataDrill" :hide-column="isHidden"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 函数负载（分类） -->
        <div v-if="stepPieDrilldownStack.length < 4" class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">函数负载</span>
          </h3>
          <PerfSymbolTable
            :step-id="currentStepIndex" :data="filteredSymbolPerformanceData1Drill" :hide-column="isHidden"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';
import PerfThreadTable from './tables/PerfThreadTable.vue';
import PerfFileTable from './tables/PerfFileTable.vue';
import PerfSymbolTable from './tables/PerfSymbolTable.vue';
import PieChart from '../../../common/charts/PieChart.vue';
import BarChart from '../../../common/charts/BarChart.vue';
import LineChart from '../../../common/charts/LineChart.vue';
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
import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';

const isHidden = true;
const LeftLineChartSeriesType = 'bar';
const RightLineChartSeriesType = 'line';

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const basicInfo = jsonDataStore.basicInfo;
const perfData = jsonDataStore.perfData;

console.log('负载分析组件获取到的 JSON 数据:');

// 检查是否有负载数据
const hasPerfData = computed(() => perfData !== null && perfData !== undefined);

// testSteps 只从 jsonDataStore.steps 生成，与 perfData 解耦
const testSteps = computed(() => {
  const steps = jsonDataStore.steps || [];
  return steps.map((step, index) => ({
    id: step.step_id ?? (index + 1),
    step_name: step.step_name,
  }));
});

// 获取步骤的性能数据（从 perfData 中通过索引获取）
const getStepPerfData = (stepIndex: number) => {
  if (!perfData || !perfData.steps || stepIndex < 0 || stepIndex >= perfData.steps.length) {
    return { count: 0, round: 0, perf_data_path: '' };
  }
  const step = perfData.steps[stepIndex];
  return {
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  };
};

// 获取所有步骤的总计数
const getTotalTestStepsCount = () => {
  if (!perfData || !perfData.steps) return 0;
  return perfData.steps.reduce((total, step) => total + step.count, 0);
};

const performanceData = ref({
  app_name: basicInfo!.app_name,
  rom_version: basicInfo!.rom_version,
  app_version: basicInfo!.app_version,
  scene: basicInfo!.scene,
});

const currentStepIndex = ref(0);

// 动态聚合数据
const mergedThreadPerformanceData = computed(() =>
  calculateThreadData(perfData!, null, currentStepIndex.value === 0)
);
const mergedComponentNamePerformanceData = computed(() =>
  calculateComponentNameData(perfData!, null, currentStepIndex.value === 0)
);
const mergedFilePerformanceData = computed(() =>
  calculateFileData(perfData!, null, currentStepIndex.value === 0)
);
const mergedFilePerformanceData1 = computed(() =>
  calculateFileData1(perfData!, null, currentStepIndex.value === 0)
);
const mergedSymbolsPerformanceData = computed(() =>
  calculateSymbolData(perfData!, null, currentStepIndex.value === 0)
);
const mergedSymbolsPerformanceData1 = computed(() =>
  calculateSymbolData1(perfData!, null, currentStepIndex.value === 0)
);

// 工具函数：安全排序，避免副作用
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// 格式化持续时间的方法
const formatDuration = (milliseconds: number) => {
  return `指令数：${milliseconds}`;
};

// 格式化功耗信息
const formatEnergy = (milliseconds: number) => {
  const energy = calculateEnergyConsumption(milliseconds);
  return `核算功耗（mAs）：${energy}`;
};

const scenePieData = ref();
const processPieDrilldownStack = ref<string[]>([]);
const processPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const processPieData = ref(processJson2ProcessPieChartData(perfData!, currentStepIndex.value));
const pieChartTitle = perfData?.steps[0].data[0].eventType == 0 ? 'cycles' : 'instructions';

const stepPieDrilldownStack = ref<string[]>([]);
const stepPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const stepPieData = ref(processJson2PieChartData(perfData!, currentStepIndex.value));

function getProcessPieDrilldownData(name: string, stack: string[]) {
  // 层级：0-进程 1-线程 2-文件 3-符号
  if (stack.length === 0) {
    // 进程分布
    const data = processJson2ProcessPieChartData(perfData!, currentStepIndex.value);
    // 按 value 降序排序
    const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
    return { legendData: sorted.map(d => d.name), seriesData: sorted };
  } else if (stack.length === 1) {
    // 线程分布
    const processName = name;
    const threadData = calculateThreadData(perfData!, null, false).filter((item: ThreadDataItem) => item.process === processName && (currentStepIndex.value === 0 || item.stepId === currentStepIndex.value));
    const sorted = [...threadData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ThreadDataItem) => d.thread);
    const seriesData = sorted.map((d: ThreadDataItem) => ({ name: d.thread, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    // 文件分布
    const processName = stack[0];
    const threadName = name;
    const fileData = calculateFileData(perfData!, null, false).filter((item: FileDataItem) => item.process === processName && item.thread === threadName && (currentStepIndex.value === 0 || item.stepId === currentStepIndex.value));
    const sorted = [...fileData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: FileDataItem) => d.file);
    const seriesData = sorted.map((d: FileDataItem) => ({ name: d.file, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    // 符号分布
    const processName = stack[0];
    const threadName = stack[1];
    const fileName = name;
    const symbolData = calculateSymbolData(perfData!, null, false).filter((item: SymbolDataItem) => item.process === processName && item.thread === threadName && item.file === fileName && (currentStepIndex.value === 0 || item.stepId === currentStepIndex.value));
    const sorted = [...symbolData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: SymbolDataItem) => d.symbol);
    const seriesData = sorted.map((d: SymbolDataItem) => ({ name: d.symbol, value: d.instructions }));
    return { legendData, seriesData };
  } else {
    // 最底层
    return processPieData.value;
  }
}

function handleProcessPieDrilldown(name: string) {
  const newStack = [...processPieDrilldownStack.value, name];
  const newData = getProcessPieDrilldownData(name, newStack);
  // 只有新数据有内容且与当前数据不同才推进
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
    // 大分类分布
    const categoryData = calculateCategorysData(perfData!, null, currentStepIndex.value === 0);
    const sorted = [...categoryData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ProcessDataItem) => d.category);
    const seriesData = sorted.map((d: ProcessDataItem) => ({ name: d.category, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 1) {
    // 小分类分布
    const category = name;
    const componentData = calculateComponentNameData(perfData!, null, currentStepIndex.value === 0).filter((d: ThreadDataItem) => d.category === category && (currentStepIndex.value === 0 || d.stepId === currentStepIndex.value));
    const sorted = [...componentData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ThreadDataItem) => d.subCategoryName);
    const seriesData = sorted.map((d: ThreadDataItem) => ({ name: d.subCategoryName, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 2) {
    // 文件分布
    const category = stack[0];
    const subCategoryName = name;
    const fileData = calculateFileData1(perfData!, null, currentStepIndex.value === 0).filter((d: FileDataItem) => d.category === category && d.subCategoryName === subCategoryName && (currentStepIndex.value === 0 || d.stepId === currentStepIndex.value));
    const sorted = [...fileData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: FileDataItem) => d.file);
    const seriesData = sorted.map((d: FileDataItem) => ({ name: d.file, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    // 符号分布
    const category = stack[0];
    const subCategoryName = stack[1];
    const file = name;
    const symbolData = calculateSymbolData1(perfData!, null, currentStepIndex.value === 0).filter((d: SymbolDataItem) => d.category === category && d.subCategoryName === subCategoryName && d.file === file && (currentStepIndex.value === 0 || d.stepId === currentStepIndex.value));
    const sorted = [...symbolData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: SymbolDataItem) => d.symbol);
    const seriesData = sorted.map((d: SymbolDataItem) => ({ name: d.symbol, value: d.instructions }));
    return { legendData, seriesData };
  } else {
    // 最底层
    return stepPieData.value;
  }
}

function handleStepPieDrilldown(name: string) {
  const newStack = [...stepPieDrilldownStack.value, name];
  const newData = getDrilldownPieData(name, newStack);
  // 只有新数据有内容且与当前数据不同才推进
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

scenePieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);
processPieData.value = processJson2ProcessPieChartData(perfData!, currentStepIndex.value);
stepPieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);

// 处理步骤点击事件的方法
const handleStepClick = (stepId: number) => {
  currentStepIndex.value = stepId;
  scenePieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);
  processPieData.value = processJson2ProcessPieChartData(perfData!, currentStepIndex.value);
  processPieDrilldownStack.value = [];
  processPieDataStack.value = [];
  stepPieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);
  stepPieDrilldownStack.value = [];
  stepPieDataStack.value = [];
};

// const handleDownloadAndRedirect = (file: string, stepId: number, name: string) => {
//   const link = document.createElement('a');
//   if (file === 'perf.data') {
//     link.href = '../hiperf/step' + stepId + '/' + file;
//     link.download = name + file;
//   } else {
//     link.href = '../htrace/step' + stepId + '/' + file;
//     link.download = name + file;
//   }

//   document.body.appendChild(link);
//   link.click();

//   setTimeout(() => {
//     document.body.removeChild(link);
//   }, 100);

//   setTimeout(() => {
//     window.open('https://localhost:9000/application/', 'trace example');
//   }, 300);
// };

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

// 进程饼图面包屑项（首页 + 下钻层级）
const processBreadcrumbItems = computed(() => {
  const items = ['首页'];
  processPieDrilldownStack.value.forEach((name, index) => {
    items.push(getBreadcrumbLabel('process', index, name));
  });
  return items;
});

// 分类饼图面包屑项（首页 + 下钻层级）
const stepBreadcrumbItems = computed(() => {
  const items = ['首页'];
  stepPieDrilldownStack.value.forEach((name, index) => {
    items.push(getBreadcrumbLabel('category', index, name));
  });
  return items;
});

// 处理进程饼图面包屑点击
function handleProcessBreadcrumbClick(targetIndex: number) {
  if (targetIndex === 0) {
    processPieDrilldownStack.value = [];
    processPieDataStack.value = [];
    processPieData.value = getProcessPieDrilldownData('', []);
    return;
  }
  const targetLevel = targetIndex;
  while (processPieDrilldownStack.value.length > targetLevel) {
    processPieDrilldownStack.value.pop();
    processPieData.value = processPieDataStack.value.pop() || processPieData.value;
  }
}

// 处理步骤饼图面包屑点击
function handleStepBreadcrumbClick(targetIndex: number) {
  if (targetIndex === 0) {
    stepPieDrilldownStack.value = [];
    stepPieDataStack.value = [];
    stepPieData.value = getDrilldownPieData('', []);
    return;
  }
  const targetLevel = targetIndex;
  while (stepPieDrilldownStack.value.length > targetLevel) {
    stepPieDrilldownStack.value.pop();
    stepPieData.value = stepPieDataStack.value.pop() || stepPieData.value;
  }
}

// 计算属性，根据当前步骤 ID 过滤负载数据
const filteredThreadPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedThreadPerformanceData.value);
  }
  return sortByInstructions(
    mergedThreadPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredComponentNamePerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedComponentNamePerformanceData.value);
  }
  return sortByInstructions(
    mergedComponentNamePerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredFilePerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedFilePerformanceData.value);
  }
  return sortByInstructions(
    mergedFilePerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredFilePerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedFilePerformanceData1.value);
  }
  return sortByInstructions(
    mergedFilePerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredSymbolPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedSymbolsPerformanceData.value);
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredSymbolPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedSymbolsPerformanceData1.value);
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

// 左侧 drill 联动
const filteredThreadPerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = filteredThreadPerformanceData.value;
  if (stack.length === 1) {
    // 进程
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
</script>

<style scoped>
.performance-comparison {
  padding: 20px;
  background: #f5f7fa;
}

/* 步骤导航样式 */
.step-nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.step-item {
  background: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }

  &.active {
    border: 2px solid #2196f3;
  }
}

.step-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 0.9em;
}

.step-order {
  color: #2196f3;
  font-weight: bold;
}

.step-duration {
  color: #757575;
}

.step-name {
  font-weight: 500;
  margin-bottom: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.data-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px 0;
}

.version-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  background: #e3f2fd;
  color: #1976d2;
}

.beautified-descriptions {
  background-color: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 10px;
}

.beautified-descriptions .el-descriptions__title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.description-item-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-box {
  background-color: #e7f3fe;
  border-left: 6px solid #2196F3;
  padding: 12px;
  margin-bottom: 9px;
  font-family: Arial, sans-serif;
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.info-box p {
  margin: 0;
  color: #333;
}

.beautiful-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  margin-left: 10px;
}

.primary-btn {
  background-color: #3B82F6;
  color: white;
}

.primary-btn:hover {
  background-color: #2563EB;
  box-shadow: 0 6px 10px rgba(59, 130, 246, 0.25);
  transform: translateY(-2px);
}

.primary-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.25);
}

/* 面包屑导航样式 */
.breadcrumb-nav {
  padding: 8px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 14px;
}

.breadcrumb-item {
  color: #606266;
  cursor: pointer;
  transition: color 0.2s;
}

.breadcrumb-item:hover {
  color: #409eff;
}

.breadcrumb-separator {
  margin: 0 8px;
  color: #c0c4cc;
  font-style: normal;
}

.breadcrumb-item:last-child {
  color: #409eff;
  font-weight: 500;
}
</style>
