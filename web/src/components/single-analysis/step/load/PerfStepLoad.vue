<template>
  <div class="step-load-container">
    <!-- 技术栈占比卡片 -->
    <el-row v-if="techStackData.length > 0" :gutter="20" class="tech-stack-row">
      <el-col :span="24">
        <div class="tech-stack-card">
          <h3 class="card-title">
            <span class="version-tag">技术栈占比</span>
          </h3>
          <div class="tech-stack-content">
            <div v-for="item in techStackData" :key="item.name" class="tech-stack-category">
              <!-- 大分类 -->
              <div class="tech-stack-item category-item" @click="toggleCategory(item.name)">
                <div class="tech-stack-header">
                  <div class="tech-stack-name">
                    <i :class="item.expanded ? 'el-icon-arrow-down' : 'el-icon-arrow-right'" class="expand-icon"></i>
                    {{ item.name }}
                  </div>
                  <div class="tech-stack-stats">
                    <div class="tech-stack-value">{{ item.percentage }}%</div>
                    <div class="tech-stack-instructions">{{ formatNumber(item.instructions) }}</div>
                  </div>
                </div>
              </div>
              <!-- 小分类 -->
              <div v-if="item.expanded && item.subCategories.length > 0" class="sub-categories">
                <div v-for="subItem in item.subCategories" :key="subItem.name" class="tech-stack-item sub-item">
                  <div class="tech-stack-name sub-name">{{ subItem.name }}</div>
                  <div class="tech-stack-stats">
                    <div class="tech-stack-value">{{ subItem.percentage }}%</div>
                    <div class="tech-stack-instructions">{{ formatNumber(subItem.instructions) }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 步骤负载分析 -->
    <el-tabs v-model="activeTab" class="analysis-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="按分类拆解" name="category">
        <el-row :gutter="20">
          <el-col :span="24">
            <!-- 分类负载饼图 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">分类负载分布</span>
              </h3>
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
                :step-id="stepId" height="600px" :chart-data="stepPieData" :title="pieChartTitle"
                :drilldown-stack="stepPieDrilldownStack" :legend-truncate="false"
                @drilldown="handleStepPieDrilldown" @drillup="handleStepPieDrillup"
              />
            </div>
          </el-col>
        </el-row>

        <!-- 详细负载表格：根据分类饼图下钻层级显示（0首页 1大分类 2小分类 3三级分类 4文件 5符号） -->
        <el-row v-if="stepPieDrilldownStack.length < 2" :gutter="20">
          <el-col :span="24">
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

        <el-row v-if="stepPieDrilldownStack.length < 3" :gutter="20">
          <el-col :span="24">
            <!-- 三级分类负载 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">三级分类负载</span>
              </h3>
              <PerfThreadTable
                :step-id="stepId" :data="filteredThirdCategoryPerformanceDataDrill"
                :hide-column="isHidden" :has-category="true" :show-third-category="true" />
            </div>
          </el-col>
        </el-row>

        <el-row v-if="stepPieDrilldownStack.length < 4" :gutter="20">
          <el-col :span="24">
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

        <el-row v-if="stepPieDrilldownStack.length < 5" :gutter="20">
          <el-col :span="24">
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
      </el-tab-pane>

      <el-tab-pane label="按进程拆解" name="process">
        <el-row :gutter="20">
          <el-col :span="24">
            <!-- 进程负载饼图 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">进程负载分布</span>
              </h3>
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
                :step-id="stepId" height="600px" :chart-data="processPieData" :title="pieChartTitle"
                :drilldown-stack="processPieDrilldownStack" :legend-truncate="false"
                @drilldown="handleProcessPieDrilldown" @drillup="handleProcessPieDrillup"
              />
            </div>
          </el-col>
        </el-row>

        <!-- 详细负载表格：进程-线程-大类-小类-三级分类-文件-符号 -->
        <el-row v-if="processPieDrilldownStack.length < 2" :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <h3 class="panel-title"><span class="version-tag">线程负载</span></h3>
              <PerfThreadTable :step-id="stepId" :data="filteredThreadPerformanceDataDrill" :hide-column="isHidden" :has-category="false" :process-drill-path-level="0" />
            </div>
          </el-col>
        </el-row>
        <el-row v-if="processPieDrilldownStack.length < 3" :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <h3 class="panel-title"><span class="version-tag">大类负载</span></h3>
              <PerfThreadTable :step-id="stepId" :data="filteredProcessThreadCategoryDataDrill" :hide-column="isHidden" :has-category="true" :process-drill-path-level="1" />
            </div>
          </el-col>
        </el-row>
        <el-row v-if="processPieDrilldownStack.length < 4" :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <h3 class="panel-title"><span class="version-tag">小类负载</span></h3>
              <PerfThreadTable :step-id="stepId" :data="filteredProcessThreadSubCategoryDataDrill" :hide-column="isHidden" :has-category="true" :process-drill-path-level="2" />
            </div>
          </el-col>
        </el-row>
        <el-row v-if="processPieDrilldownStack.length < 5" :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <h3 class="panel-title"><span class="version-tag">三级分类负载</span></h3>
              <PerfThreadTable :step-id="stepId" :data="filteredProcessThreadThirdCategoryDataDrill" :hide-column="isHidden" :has-category="true" :show-third-category="true" :process-drill-path-level="3" />
            </div>
          </el-col>
        </el-row>
        <el-row v-if="processPieDrilldownStack.length < 6" :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <h3 class="panel-title"><span class="version-tag">文件负载</span></h3>
              <PerfFileTable :step-id="stepId" :data="filteredFilePerformanceDataDrill" :hide-column="isHidden" :has-category="true" :process-drill-path-level="4" />
            </div>
          </el-col>
        </el-row>
        <el-row v-if="processPieDrilldownStack.length < 7" :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <h3 class="panel-title"><span class="version-tag">函数负载</span></h3>
              <PerfSymbolTable :step-id="stepId" :data="filteredSymbolPerformanceDataDrill" :hide-column="isHidden" :has-category="true" :process-drill-path-level="5" />
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch, nextTick } from 'vue';
//import { Download } from '@element-plus/icons-vue';
import PerfThreadTable from './tables/PerfThreadTable.vue';
import PerfFileTable from './tables/PerfFileTable.vue';
import PerfSymbolTable from './tables/PerfSymbolTable.vue';
import PieChart from '../../../common/charts/PieChart.vue';
import { useJsonDataStore, ComponentCategory } from '../../../../stores/jsonDataStore.ts';
import {
  calculateComponentNameData,
  // calculateFileData,
  calculateFileData1,
  // calculateSymbolData,
  calculateSymbolData1,
  calculateThreadData,
  calculateProcessThreadCategoryData,
  calculateProcessThreadSubCategoryData,
  calculateProcessThreadThirdCategoryData,
  calculateProcessThreadFileData,
  calculateProcessThreadSymbolData,
  processJson2PieChartData,
  processJson2ProcessPieChartData,
  calculateCategorysData,
  calculateThirdCategoryData,
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
const activeTab = ref('category');

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
const mergedThirdCategoryPerformanceData = computed(() =>
  calculateThirdCategoryData(perfData!, null, false)
);
// const mergedFilePerformanceData = computed(() =>
//   calculateFileData(perfData!, null, false)
// );
const mergedFilePerformanceData1 = computed(() =>
  calculateFileData1(perfData!, null, false)
);
// const mergedSymbolsPerformanceData = computed(() =>
//   calculateSymbolData(perfData!, null, false)
// );
const mergedSymbolsPerformanceData1 = computed(() =>
  calculateSymbolData1(perfData!, null, false)
);
const mergedProcessThreadCategoryData = computed(() => calculateProcessThreadCategoryData(perfData!, null, false));
const mergedProcessThreadSubCategoryData = computed(() => calculateProcessThreadSubCategoryData(perfData!, null, false));
const mergedProcessThreadThirdCategoryData = computed(() => calculateProcessThreadThirdCategoryData(perfData!, null, false));
const mergedProcessThreadFileData = computed(() => calculateProcessThreadFileData(perfData!, null, false));
const mergedProcessThreadSymbolData = computed(() => calculateProcessThreadSymbolData(perfData!, null, false));

// 工具函数：安全排序，避免副作用
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// 格式化数字
const formatNumber = (num: number) => {
  return num.toLocaleString();
};

// // 格式化功耗信息
// const formatEnergy = (milliseconds: number) => {
//   const energy = calculateEnergyConsumption(milliseconds);
//   return `${energy} mAs`;
// };

const processPieDrilldownStack = ref<string[]>([]);
const processPieDataStack = ref<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }[]>([]);
const processPieData = ref(processJson2ProcessPieChartData(perfData!, props.stepId));
const pieChartTitle = perfData?.steps[0]?.data[0].eventType == 0 ? 'cycles' : 'instructions';

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

// 饼图钻取逻辑（进程-线程-大类-小类-三级分类-文件-符号）
function getProcessPieDrilldownData(name: string, stack: string[]) {
  const stepMatch = (item: { stepId: number }) => item.stepId === props.stepId;
  if (stack.length === 0) {
    const data = processJson2ProcessPieChartData(perfData!, props.stepId);
    const sorted = [...data.seriesData].sort((a, b) => b.value - a.value);
    return { legendData: sorted.map(d => d.name), seriesData: sorted };
  } else if (stack.length === 1) {
    const processName = name;
    const threadData = calculateThreadData(perfData!, null, false).filter((item: ThreadDataItem) => item.process === processName && stepMatch(item));
    const sorted = [...threadData].sort((a, b) => b.instructions - a.instructions);
    return { legendData: sorted.map(d => d.thread), seriesData: sorted.map(d => ({ name: d.thread, value: d.instructions })) };
  } else if (stack.length === 2) {
    const [processName, threadKey] = stack;
    const categoryData = calculateProcessThreadCategoryData(perfData!, null, false).filter((item: ThreadDataItem) => item.process === processName && item.thread === threadKey && stepMatch(item));
    const sorted = [...categoryData].sort((a, b) => b.instructions - a.instructions);
    return { legendData: sorted.map(d => d.category), seriesData: sorted.map(d => ({ name: d.category, value: d.instructions })) };
  } else if (stack.length === 3) {
    const [processName, threadKey, category] = stack;
    const subData = calculateProcessThreadSubCategoryData(perfData!, null, false).filter((item: ThreadDataItem) => item.process === processName && item.thread === threadKey && item.category === category && stepMatch(item));
    const sorted = [...subData].sort((a, b) => b.instructions - a.instructions);
    return { legendData: sorted.map(d => d.subCategoryName), seriesData: sorted.map(d => ({ name: d.subCategoryName, value: d.instructions })) };
  } else if (stack.length === 4) {
    const [processName, threadKey, category, subCategoryName] = stack;
    const thirdData = calculateProcessThreadThirdCategoryData(perfData!, null, false).filter((item: ThreadDataItem) => item.process === processName && item.thread === threadKey && item.category === category && item.subCategoryName === subCategoryName && stepMatch(item));
    const sorted = [...thirdData].sort((a, b) => b.instructions - a.instructions);
    return { legendData: sorted.map(d => d.thirdCategoryName || 'Unknown'), seriesData: sorted.map(d => ({ name: d.thirdCategoryName || 'Unknown', value: d.instructions })) };
  } else if (stack.length === 5) {
    const [processName, threadKey, category, subCategoryName, thirdCategoryName] = stack;
    const fileData = calculateProcessThreadFileData(perfData!, null, false).filter((item: FileDataItem) => item.process === processName && item.thread === threadKey && item.category === category && item.subCategoryName === subCategoryName && (item.thirdCategoryName || '') === (thirdCategoryName || '') && stepMatch(item));
    const sorted = [...fileData].sort((a, b) => b.instructions - a.instructions);
    return { legendData: sorted.map(d => d.file), seriesData: sorted.map(d => ({ name: d.file, value: d.instructions })) };
  } else if (stack.length === 6) {
    const [processName, threadKey, category, subCategoryName, thirdCategoryName, fileName] = stack;
    const symbolData = calculateProcessThreadSymbolData(perfData!, null, false).filter((item: SymbolDataItem) => item.process === processName && item.thread === threadKey && item.category === category && item.subCategoryName === subCategoryName && (item.thirdCategoryName || '') === (thirdCategoryName || '') && item.file === fileName && stepMatch(item));
    const sorted = [...symbolData].sort((a, b) => b.instructions - a.instructions);
    return { legendData: sorted.map(d => d.symbol), seriesData: sorted.map(d => ({ name: d.symbol, value: d.instructions })) };
  } else {
    return processPieData.value;
  }
}

// 进程饼图最大下钻深度：进程-线程-大类-小类-三级分类-文件-符号（共7层）
const PROCESS_PIE_MAX_STACK = 7;
function handleProcessPieDrilldown(name: string) {
  const newStack = [...processPieDrilldownStack.value, name];
  const newData = getProcessPieDrilldownData(name, newStack);
  if (!newData.seriesData || newData.seriesData.length === 0 || newStack.length === PROCESS_PIE_MAX_STACK) {
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
  // 新层级：0-大分类 1-小分类 2-三级分类 3-文件 4-符号
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
    // 三级分类分布
    const category = stack[0];
    const subCategoryName = name;
    const thirdCategoryData = calculateThirdCategoryData(perfData!, null, false).filter((d: ThreadDataItem) =>
      d.category === category && 
      d.subCategoryName === subCategoryName && 
      d.stepId === props.stepId);
    const sorted = [...thirdCategoryData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: ThreadDataItem) => d.thirdCategoryName || 'Unknown');
    const seriesData = sorted.map((d: ThreadDataItem) => ({ name: d.thirdCategoryName || 'Unknown', value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 3) {
    const category = stack[0];
    const subCategoryName = stack[1];
    const thirdCategoryName = name;
    const fileData = calculateFileData1(perfData!, null, false).filter((d: FileDataItem) =>
      d.category === category && 
      d.subCategoryName === subCategoryName && 
      d.thirdCategoryName === thirdCategoryName && 
      d.stepId === props.stepId);
    const sorted = [...fileData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: FileDataItem) => d.file);
    const seriesData = sorted.map((d: FileDataItem) => ({ name: d.file, value: d.instructions }));
    return { legendData, seriesData };
  } else if (stack.length === 4) {
    const category = stack[0];
    const subCategoryName = stack[1];
    const thirdCategoryName = stack[2];
    const file = name;
    const symbolData = calculateSymbolData1(perfData!, null, false).filter((d: SymbolDataItem) =>
      d.category === category && 
      d.subCategoryName === subCategoryName && 
      d.thirdCategoryName === thirdCategoryName && 
      d.file === file && 
      d.stepId === props.stepId);
    const sorted = [...symbolData].sort((a, b) => b.instructions - a.instructions);
    const legendData = sorted.map((d: SymbolDataItem) => d.symbol);
    const seriesData = sorted.map((d: SymbolDataItem) => ({ name: d.symbol, value: d.instructions }));
    return { legendData, seriesData };
  } else {
    return stepPieData.value;
  }
}

// 步骤饼图最大下钻深度：大类-小类-三级分类-文件-符号（共5层）
const STEP_PIE_MAX_STACK = 5;
function handleStepPieDrilldown(name: string) {
  const newStack = [...stepPieDrilldownStack.value, name];
  const newData = getDrilldownPieData(name, newStack);
  if (!newData.seriesData || newData.seriesData.length === 0 || newStack.length === STEP_PIE_MAX_STACK) {
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
    const labels = ['进程', '线程', '大分类', '小分类', '三级分类', '文件', '符号'];
    return `${labels[level]}: ${item}`;
  } else {
    const labels = ['大分类', '小分类', '三级分类', '文件', '符号'];
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

// 处理面包屑点击
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
  return sortByInstructions(
    mergedThreadPerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredComponentNamePerformanceData = computed(() => {
  return sortByInstructions(
    mergedComponentNamePerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

const filteredThirdCategoryPerformanceData = computed(() => {
  return sortByInstructions(
    mergedThirdCategoryPerformanceData.value.filter((item) => item.stepId === props.stepId)
  );
});

// const filteredFilePerformanceData = computed(() => {
//   return sortByInstructions(
//     mergedFilePerformanceData.value.filter((item) => item.stepId === props.stepId)
//   );
// });

const filteredFilePerformanceData1 = computed(() => {
  return sortByInstructions(
    mergedFilePerformanceData1.value.filter((item) => item.stepId === props.stepId)
  );
});

// const filteredSymbolPerformanceData = computed(() => {
//   return sortByInstructions(
//     mergedSymbolsPerformanceData.value.filter((item) => item.stepId === props.stepId)
//   );
// });

const filteredSymbolPerformanceData1 = computed(() => {
  return sortByInstructions(
    mergedSymbolsPerformanceData1.value.filter((item) => item.stepId === props.stepId)
  );
});



// 按联合 key 过滤并聚合：只看当前条件，不跨维汇总，每行保留实际维度值
function filterAndAggregateByStack<T extends { process: string; thread: string; category: string; subCategoryName: string; thirdCategoryName?: string; instructions: number; stepId: number; compareInstructions?: number; increaseInstructions?: number; increasePercentage?: number }>(
  data: T[], stack: string[], groupByKeys: (keyof T)[]): T[] {
  const stepMatch = (d: T) => d.stepId === props.stepId;
  let filtered = data.filter(stepMatch);
  if (stack.length >= 1) filtered = filtered.filter(d => d.process === stack[0]);
  if (stack.length >= 2) filtered = filtered.filter(d => d.thread === stack[1]);
  if (stack.length >= 3) filtered = filtered.filter(d => d.category === stack[2]);
  if (stack.length >= 4) filtered = filtered.filter(d => d.subCategoryName === stack[3]);
  if (stack.length >= 5) filtered = filtered.filter(d => (d.thirdCategoryName || '') === (stack[4] || ''));
  const map = new Map<string, Partial<T> & { instructions: number }>();
  for (const item of filtered) {
    const key = groupByKeys.map(k => item[k] ?? '').join('|');
    const existing = map.get(key);
    if (!existing) {
      map.set(key, { ...item } as Partial<T> & { instructions: number });
    } else {
      existing.instructions += item.instructions;
      if (existing.compareInstructions !== undefined) existing.compareInstructions += item.compareInstructions ?? 0;
    }
  }
  return sortByInstructions(Array.from(map.values()) as T[]);
}

// 左侧 drill 联动（进程-线程-大类-小类-三级分类-文件-符号）
const filteredThreadPerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = filteredThreadPerformanceData.value;
  if (stack.length >= 1) data = data.filter(d => d.process === stack[0]);
  return data;
});
const filteredProcessThreadCategoryDataDrill = computed(() =>
  filterAndAggregateByStack(mergedProcessThreadCategoryData.value, processPieDrilldownStack.value, ['process', 'thread', 'category'])
);
const filteredProcessThreadSubCategoryDataDrill = computed(() =>
  filterAndAggregateByStack(mergedProcessThreadSubCategoryData.value, processPieDrilldownStack.value, ['process', 'thread', 'category', 'subCategoryName'])
);
const filteredProcessThreadThirdCategoryDataDrill = computed(() =>
  filterAndAggregateByStack(mergedProcessThreadThirdCategoryData.value, processPieDrilldownStack.value, ['process', 'thread', 'category', 'subCategoryName', 'thirdCategoryName'])
);
const filteredFilePerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = sortByInstructions(mergedProcessThreadFileData.value.filter(d => d.stepId === props.stepId));
  if (stack.length >= 1) data = data.filter(d => d.process === stack[0]);
  if (stack.length >= 2) data = data.filter(d => d.thread === stack[1]);
  if (stack.length >= 3) data = data.filter(d => d.category === stack[2]);
  if (stack.length >= 4) data = data.filter(d => d.subCategoryName === stack[3]);
  if (stack.length >= 5) data = data.filter(d => (d.thirdCategoryName || '') === (stack[4] || ''));
  return data;
});
const filteredSymbolPerformanceDataDrill = computed(() => {
  const stack = processPieDrilldownStack.value;
  let data = sortByInstructions(mergedProcessThreadSymbolData.value.filter(d => d.stepId === props.stepId));
  if (stack.length >= 1) data = data.filter(d => d.process === stack[0]);
  if (stack.length >= 2) data = data.filter(d => d.thread === stack[1]);
  if (stack.length >= 3) data = data.filter(d => d.category === stack[2]);
  if (stack.length >= 4) data = data.filter(d => d.subCategoryName === stack[3]);
  if (stack.length >= 5) data = data.filter(d => (d.thirdCategoryName || '') === (stack[4] || ''));
  if (stack.length >= 6) data = data.filter(d => d.file === stack[5]);
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

const filteredThirdCategoryPerformanceDataDrill = computed(() => {
  const stack = stepPieDrilldownStack.value;
  let data = filteredThirdCategoryPerformanceData.value;
  if (stack.length === 1) {
    data = data.filter((d: ThreadDataItem) => d.category === stack[0]);
  } else if (stack.length === 2) {
    data = data.filter((d: ThreadDataItem) => d.category === stack[0] && d.subCategoryName === stack[1]);
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
  } else if (stack.length === 3) {
    data = data.filter(d => 
      d.category === stack[0] && 
      d.subCategoryName === stack[1] && 
      d.thirdCategoryName === stack[2]
    );
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
    data = data.filter(d => 
      d.category === stack[0] && 
      d.subCategoryName === stack[1] && 
      d.thirdCategoryName === stack[2]
    );
  } else if (stack.length === 4) {
    data = data.filter(d => 
      d.category === stack[0] && 
      d.subCategoryName === stack[1] && 
      d.thirdCategoryName === stack[2] && 
      d.file === stack[3]
    );
  }
  return data;
});

// 展开/折叠状态（使用 null 表示初始状态，空 Set 表示用户已交互）
const expandedCategories = ref<Set<string> | null>(null);

// 切换分类展开状态
function toggleCategory(categoryName: string) {
  // 首次点击时，初始化为空 Set（表示用户开始交互）
  if (expandedCategories.value === null) {
    expandedCategories.value = new Set();
  }

  if (expandedCategories.value.has(categoryName)) {
    expandedCategories.value.delete(categoryName);
  } else {
    expandedCategories.value.add(categoryName);
  }
}

/**
 * 判断是否应该归类到ArkUI技术栈
 * ArkUI技术栈包含：
 * - kind=1的：APP_ABC, APP_LIB
 * - kind=2的：ArkUI
 * - kind=3的：Ability, ArkTS Runtime, ArkTS System LIB
 */
function shouldClassifyAsArkUI(category: ComponentCategory, categoryName: string, subCategoryName?: string): boolean {
  // kind=2的ArkUI
  if (category === ComponentCategory.ArkUI || categoryName === 'ArkUI') {
    return true;
  }
  
  // kind=1的APP_ABC, APP_LIB
  if (category === ComponentCategory.APP && subCategoryName) {
    if (subCategoryName === 'APP_ABC' || subCategoryName === 'APP_LIB') {
      return true;
    }
  }
  
  // kind=3的Ability, ArkTS Runtime, ArkTS System LIB
  if (category === ComponentCategory.OS_Runtime && subCategoryName) {
    if (subCategoryName === 'Ability' || 
        subCategoryName === 'ArkTS Runtime' || 
        subCategoryName === 'ArkTS System LIB') {
      return true;
    }
  }
  
  return false;
}

// 计算技术栈数据（与后端 saveTechStackXlsx 逻辑一致）
const techStackData = computed(() => {
  if (!perfData) {
    return [];
  }

  // 需要排除的分类名称（对应 kind = 1, 3, 4, -1）
  const excludedCategories = ['APP', 'OS_Runtime', 'SYS_SDK', 'UNKNOWN'];

  // 按技术栈分类和子分类统计指令数
  // Map<技术栈分类, Map<子分类, 指令数>>
  const categoryMap = new Map<string, Map<string, number>>();
  // 统计所有主应用数据的总负载（用于计算应用占比）
  let totalAppInstructions = 0;
  // 统计所有技术栈数据的总负载（用于计算相对占比）
  let totalTechStackInstructions = 0;

  // 遍历所有详细数据，只统计指令数
  for (const step of perfData.steps) {
    for (const item of step.data) {
      // 只统计当前步骤的数据
      if (item.stepIdx !== props.stepId) {
        continue;
      }

      // 只保留主应用的数据（如果数据中有 isMainApp 字段）
      // 注意：前端数据可能没有 isMainApp 字段，这里先不过滤
      // 如果需要过滤，需要确保数据中包含 isMainApp 字段
      // if ((item as any).isMainApp !== true) {
      //   continue;
      // }

      const category = item.componentCategory;
      const categoryName = item.categoryName || ComponentCategory[category] || 'UNKNOWN';
      const subCategoryName = item.subCategoryName || 'Unknown';
      
      // 统计所有主应用数据的总负载（包括被排除的分类）
      // 这个统计应该在判断是否排除之前进行，以包含所有主应用数据
      totalAppInstructions += item.symbolEvents;
      
      // 判断是否应该归类到ArkUI
      const isArkUI = shouldClassifyAsArkUI(category, categoryName, subCategoryName);
      
      // 确定最终的技术栈分类名称和子分类名称
      let finalCategoryName: string;
      let finalSubCategoryName: string;
      
      if (isArkUI) {
        finalCategoryName = 'ArkUI';
        // 对于ArkUI，子分类保持原样（APP_ABC, APP_LIB, Ability等）
        finalSubCategoryName = subCategoryName;
      } else {
        // 排除指定的分类
        if (excludedCategories.includes(categoryName)) {
          continue;
        }
        finalCategoryName = categoryName;
        finalSubCategoryName = subCategoryName;
      }

      // 初始化技术栈分类
      if (!categoryMap.has(finalCategoryName)) {
        categoryMap.set(finalCategoryName, new Map());
      }
      
      // 统计技术栈分类和子分类
      const subCategoryMap = categoryMap.get(finalCategoryName)!;
      const current = subCategoryMap.get(finalSubCategoryName) || 0;
      subCategoryMap.set(finalSubCategoryName, current + item.symbolEvents);
      totalTechStackInstructions += item.symbolEvents;
    }
  }

  // 如果没有技术栈数据，返回空数组
  if (categoryMap.size === 0) {
    return [];
  }

  // 生成技术栈数据
  const techStackItems = Array.from(categoryMap.entries())
    .map(([categoryName, subCategoryMap]) => {
      // 计算技术栈分类的总指令数
      const categoryInstructions = Array.from(subCategoryMap.values())
        .reduce((sum, instructions) => sum + instructions, 0);
      
      // 相对占比：技术栈分类在所有技术栈中的占比
      const relativePercentage = totalTechStackInstructions > 0
        ? ((categoryInstructions / totalTechStackInstructions) * 100).toFixed(1)
        : '0.0';
      
      // 应用占比：技术栈分类在所有主应用数据中的占比（包括被排除的分类）
      const appPercentage = totalAppInstructions > 0
        ? ((categoryInstructions / totalAppInstructions) * 100).toFixed(1)
        : '0.0';

      // 生成子分类数据
      const subCategories = Array.from(subCategoryMap.entries())
        .map(([subCategoryName, instructions]) => {
          // 子分类的相对占比（相对于所有技术栈数据）
          const subRelativePercentage = totalTechStackInstructions > 0
            ? ((instructions / totalTechStackInstructions) * 100).toFixed(1)
            : '0.0';
          
          // 子分类的应用占比（相对于所有主应用数据）
          const subAppPercentage = totalAppInstructions > 0
            ? ((instructions / totalAppInstructions) * 100).toFixed(1)
            : '0.0';

          return {
            name: subCategoryName,
            instructions: instructions,
            percentage: subRelativePercentage, // 使用相对占比
            relativePercentage: subRelativePercentage,
            appPercentage: subAppPercentage
          };
        })
        .sort((a, b) => b.instructions - a.instructions);

      const isExpanded = expandedCategories.value === null ? true : expandedCategories.value.has(categoryName);

      return {
        name: categoryName,
        instructions: categoryInstructions,
        relativePercentage: relativePercentage,
        appPercentage: appPercentage,
        percentage: relativePercentage, // 保持兼容性，使用相对占比
        subCategories: subCategories,
        expanded: isExpanded
      };
    })
    .sort((a, b) => b.instructions - a.instructions);

  return techStackItems;
});

// 处理tab切换
function handleTabChange() {
  nextTick(() => {
    window.dispatchEvent(new Event('resize'));
  });
}

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

/* 技术栈卡片样式 */
.tech-stack-row {
  margin-bottom: 24px;
}

.tech-stack-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.card-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.tech-stack-content {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.tech-stack-category {
  flex: 1;
  min-width: 280px;
  max-width: calc(33.333% - 11px);
}

.tech-stack-item {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  transition: all 0.3s ease;
}

.tech-stack-item.category-item {
  cursor: pointer;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  margin-bottom: 8px;
}

.tech-stack-item.category-item:hover {
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  transform: translateY(-2px);
}

.tech-stack-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tech-stack-name {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.category-item .tech-stack-name {
  color: white;
}

.tech-stack-name .expand-icon {
  font-size: 12px;
  transition: transform 0.3s ease;
}

.tech-stack-stats {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tech-stack-value {
  font-size: 16px;
  font-weight: 700;
  color: #409eff;
}

.category-item .tech-stack-value {
  color: white;
}

.tech-stack-instructions {
  font-size: 11px;
  color: #909399;
  font-weight: 500;
}

.category-item .tech-stack-instructions {
  color: rgba(255, 255, 255, 0.9);
}

.sub-categories {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tech-stack-item.sub-item {
  background: white;
  padding: 8px 12px;
}

.tech-stack-item.sub-item:hover {
  background: #f0f7ff;
  border-color: #409eff;
}

.sub-name {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.sub-item .tech-stack-value {
  font-size: 14px;
}

.sub-item .tech-stack-instructions {
  font-size: 10px;
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

  .tech-stack-card {
    padding: 16px;
  }

  .tech-stack-content {
    gap: 12px;
  }

  .tech-stack-category {
    max-width: calc(50% - 6px);
    min-width: 240px;
  }

  .tech-stack-item {
    padding: 10px;
  }

  .tech-stack-name {
    font-size: 13px;
  }

  .tech-stack-value {
    font-size: 14px;
  }

  .tech-stack-stats {
    gap: 10px;
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

  .tech-stack-category {
    max-width: 100%;
    min-width: 100%;
  }

  .tech-stack-item.category-item {
    padding: 10px;
  }

  .tech-stack-name {
    font-size: 12px;
  }

  .tech-stack-value {
    font-size: 13px;
  }

  .tech-stack-instructions {
    font-size: 10px;
  }
}
</style>
