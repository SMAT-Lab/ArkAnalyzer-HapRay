<template>
  <div class="container">
    <!-- 标签页导航 -->
    <div class="tab-nav">
      <button class="tab-button" :class="{ active: currentTab === 'tab1' }" @click="currentTab = 'tab1'">
        <i class="fa"></i>负载分析
      </button>
      <button class="tab-button" :class="{ active: currentTab === 'tab2' }" @click="currentTab = 'tab2'">
        <i class="fa"></i>帧分析
      </button>
    </div>
  </div>

  <div v-if="currentTab === 'tab1'" class="performance-comparison">
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
          <UploadHtml />
        </div>
      </el-descriptions-item>
    </el-descriptions>
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <PieChart :chart-data="scenePieData" :title="pieChartTitle"/>
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
          <LineChart :chartData="perfData" :seriesType="LeftLineChartSeriesType" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="perfData" :seriesType="RightLineChartSeriesType" />
        </div>
      </el-col>
    </el-row>

    <!-- 测试步骤导航 -->
    <div class="step-nav">
      <div :class="[
        'step-item',
        {
          active: currentStepIndex === 0,
        },
      ]" @click="handleStepClick(0)">
        <div class="step-header">
          <span class="step-order">STEP 0</span>
          <span class="step-duration">{{ getTotalTestStepsCount(testSteps) }}</span>
        </div>
        <div class="step-name">全部步骤</div>
      </div>
      <div v-for="(step, index) in testSteps" :key="index" :class="[
        'step-item',
        {
          active: currentStepIndex === step.id,
        },
      ]" @click="handleStepClick(step.id)">
        <div class="step-header">
          <span class="step-order">STEP {{ step.id }}</span>
          <span class="step-duration">{{ formatDuration(step.count) }}</span>
        </div>
        <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
        <!-- <div class="step-name">测试轮次：{{ step.round }}</div> -->
        <!-- <div class="step-name" :title="step.perf_data_path">perf文件位置：{{ step.perf_data_path }}</div> -->
        <button class="beautiful-btn primary-btn"
          @click="handleDownloadAndRedirect('perf.data', step.id, step.step_name)">
          下载perf
        </button>
        <button class="beautiful-btn primary-btn"
          @click="handleDownloadAndRedirect('trace.htrace', step.id, step.step_name)">
          下载trace
        </button>
      </div>
    </div>

    <!-- 性能对比区域 -->

    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 步骤饼图 -->
        <div class="data-panel">
          <PieChart :stepId="currentStepIndex" height="585px" :chart-data="processPieData" :title="pieChartTitle"/>
        </div>
        <!-- 进程负载 -->
        <!-- <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">进程负载</span>
          </h3>
          <PerfProcessTable :stepId="currentStepIndex" :data="filteredProcessPerformanceData" :hideColumn="isHidden" :hasCategory="false" />
        </div> -->
      </el-col>
      <el-col :span="12">
        <!-- 步骤饼图 -->
        <div class="data-panel">
          <PieChart :stepId="currentStepIndex" height="585px" :chart-data="stepPieData" :title="pieChartTitle"/>
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="12">
        <!-- 线程负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">线程负载</span>
          </h3>
          <PerfThreadTable :stepId="currentStepIndex" :data="filteredThreadPerformanceData" :hideColumn="isHidden"
            :hasCategory="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 线程负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">小分类负载</span>
          </h3>
          <PerfThreadTable :stepId="currentStepIndex" :data="filteredComponentNamePerformanceData"
            :hideColumn="isHidden" :hasCategory="true" />
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
          <PerfFileTable :stepId="currentStepIndex" :data="filteredFilePerformanceData" :hideColumn="isHidden"
            :hasCategory="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 文件负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载</span>
          </h3>
          <PerfFileTable :stepId="currentStepIndex" :data="filteredFilePerformanceData1" :hideColumn="isHidden"
            :hasCategory="true" />
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
          <PerfSymbolTable :stepId="currentStepIndex" :data="filteredSymbolPerformanceData" :hideColumn="isHidden"
            :hasCategory="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <!-- 函数负载 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">函数负载</span>
          </h3>
          <PerfSymbolTable :stepId="currentStepIndex" :data="filteredSymbolPerformanceData1" :hideColumn="isHidden"
            :hasCategory="true" />
        </div>
      </el-col>
    </el-row>
  </div>
  <div v-if="currentTab === 'tab2'">
    <!-- 测试步骤导航 -->
    <div class="step-nav" style="margin-bottom: 20px;margin-top: 20px;">
      <div v-for="(step, index) in testSteps" :key="index" :class="[
        'step-item',
        {
          active: currentStepIndex === step.id,
        },
      ]" @click="handleStepClick(step.id)">
        <div class="step-header">
          <span class="step-order">STEP {{ step.id }}</span>

        </div>
        <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
      </div>
    </div>
    <FrameAnalysis :step="currentStepIndex" :data="frameData" />
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, toRaw } from 'vue';
import PerfThreadTable from './PerfThreadTable.vue';
import PerfFileTable from './PerfFileTable.vue';
import PerfSymbolTable from './PerfSymbolTable.vue';
import PieChart from './PieChart.vue';
import BarChart from './BarChart.vue';
import LineChart from './LineChart.vue';
import { useJsonDataStore } from '../stores/jsonDataStore.ts';
import UploadHtml from './UploadHtml.vue';
import FrameAnalysis from './FrameAnalysis.vue';
import { calculateComponentNameData, calculateFileData, calculateFileData1, calculateProcessData, calculateSymbolData, calculateSymbolData1, calculateThreadData, processJson2PieChartData, processJson2ProcessPieChartData, type ProcessDataItem, type ThreadDataItem, type FileDataItem, type SymbolDataItem } from '@/utils/jsonUtil.ts';
const isHidden = true;
const LeftLineChartSeriesType = 'bar';
const RightLineChartSeriesType = 'line';
// 当前激活的标签
const currentTab = ref('tab1');

// 获取存储实例
const jsonDataStore = useJsonDataStore();
// 通过 getter 获取 JSON 数据
const basicInfo = jsonDataStore.basicInfo;

const perfData = jsonDataStore.perfData;

const frameData = jsonDataStore.frameData;
console.log('从元素获取到的 JSON 数据:');

const testSteps = ref(
  perfData!.steps.map((step, index) => ({
    //从1开始
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }))
);

const getTotalTestStepsCount = (testSteps: any[]) => {
  let total = 0;

  testSteps.forEach((step) => {
    total += step.count;
  });
  return total;
};

const performanceData = ref(
  {
    app_name: basicInfo!.app_name,
    rom_version: basicInfo!.rom_version,
    app_version: basicInfo!.app_version,
    scene: basicInfo!.scene,
  }
);

const currentStepIndex = ref(0);

// 动态聚合数据（根据步骤是否为0决定是否全局聚合）
const mergedProcessPerformanceData = computed(() =>
  calculateProcessData(perfData!, null, currentStepIndex.value === 0)
);
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

// 格式化持续时间的方法
const formatDuration = (milliseconds: any) => {
  return `指令数：${milliseconds}`;
};

const scenePieData = ref();

const stepPieData = ref();

const processPieData = ref();
const pieChartTitle = perfData?.steps[0].data[0].eventType == 0 ? 'cycles' : 'instructions';
scenePieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);
stepPieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);
processPieData.value = processJson2ProcessPieChartData(perfData!, currentStepIndex.value);
// 处理步骤点击事件的方法
const handleStepClick = (stepId: any) => {
  currentStepIndex.value = stepId;
  stepPieData.value = processJson2PieChartData(perfData!, currentStepIndex.value);
};

// 计算属性，根据当前步骤 ID 过滤性能数据
const filteredProcessPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedProcessPerformanceData.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedProcessPerformanceData.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

const filteredThreadPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedThreadPerformanceData.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedThreadPerformanceData.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

const filteredComponentNamePerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedComponentNamePerformanceData.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedComponentNamePerformanceData.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});


const filteredFilePerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedFilePerformanceData.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedFilePerformanceData.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

const filteredFilePerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedFilePerformanceData1.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedFilePerformanceData1.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

const filteredSymbolPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedSymbolsPerformanceData.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedSymbolsPerformanceData.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

const filteredSymbolPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return mergedSymbolsPerformanceData1.value.sort((a, b) => b.instructions - a.instructions);
  }
  return mergedSymbolsPerformanceData1.value
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

const handleDownloadAndRedirect = (file: string, stepId: number, name: string) => {
  const link = document.createElement('a');
  if (file === 'perf.data') {
    link.href = '../hiperf/step' + stepId + '/' + file;  // 替换为实际文件路径
    link.download = name + file;       // 自定义文件名
  } else {
    link.href = '../htrace/step' + stepId + '/' + file;  // 替换为实际文件路径
    link.download = name + file;       // 自定义文件名
  }

  document.body.appendChild(link);

  link.click();

  setTimeout(() => {
    document.body.removeChild(link);
  }, 100);

  setTimeout(() => {
    window.open('https://localhost:9000/application/', 'trace example');
  }, 300);
};
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

.step-duration-compare {
  color: #d81b60;
}

.step-name {
  font-weight: 500;
  margin-bottom: 12px;
  white-space: nowrap;
  /* 禁止文本换行 */
  overflow: hidden;
  /* 隐藏超出部分 */
  text-overflow: ellipsis;
  /* 显示省略号 */
}

/* 对比区域样式 */
.comparison-container {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 32px;
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

  .data-panel:nth-child(1) & {
    background: #e3f2fd;
    color: #1976d2;
  }

  .data-panel:nth-child(3) & {
    background: #fce4ec;
    color: #d81b60;
  }
}

/* 差异指示器 */
.indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.diff-box {
  width: 120px;
  height: 120px;
  border: 2px solid;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.diff-value {
  font-size: 24px;
  font-weight: bold;
}

.diff-label {
  font-size: 12px;
  color: #757575;
}

.time-diff {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #757575;
}

.beautified-descriptions {
  /* 设置容器的背景颜色和边框 */
  background-color: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin-bottom: 10px;
}

/* 标题样式 */
.beautified-descriptions .el-descriptions__title {
  font-size: 24px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

/* 描述项容器样式 */
.beautified-descriptions .el-descriptions__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 描述项标签样式 */
.beautified-descriptions .el-descriptions__label {
  font-size: 16px;
  font-weight: 500;
  color: #666;
}

/* 描述项内容样式 */
.beautified-descriptions .el-descriptions__content {
  font-size: 16px;
  color: #333;
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
  /* 蓝色 */
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

/* 标签页导航样式 */
.tab-nav {
  display: flex;
  border-bottom: 1px solid #e2e8f0;
}

.tab-button {
  flex: 1;
  padding: 1rem;
  font-size: 1rem;
  font-weight: 500;
  color: #4a5568;
  background-color: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  outline: none;
}

.tab-button:hover {
  color: #2b6cb0;
  background-color: #edf2f7;
}

.tab-button.active {
  color: #2b6cb0;
  border-bottom-color: #2b6cb0;
  font-weight: 600;
}

.tab-pane {
  display: none;
}

.tab-pane.active {
  display: block;
}

/* 图标样式 */
.fa {
  margin-right: 0.5rem;
}

/* 响应式设计 */
@media (max-width: 640px) {
  .tab-button {
    padding: 0.75rem;
    font-size: 0.9rem;
  }
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
</style>
