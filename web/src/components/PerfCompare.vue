<template>
  <div class="performance-comparison">
    <el-card v-if="loading" class="loading-card">
      <div class="loading-content">
        <el-icon class="el-icon--loading" style="font-size:32px;margin-bottom:10px;"><i class="el-icon-loading"></i></el-icon>
        <div>正在加载版本对比页面，请稍候...</div>
      </div>
    </el-card>
    <div v-else>
      <div v-if="!hasCompareData" style="margin-bottom: 16px;">
        <UploadHtml />
      </div>
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
        <el-row :gutter="20">
          <el-col :span="12">
            <el-descriptions :title="performanceData.app_name" :column="1" class="beautified-descriptions">
              <el-descriptions-item label="系统版本：">{{ performanceData.rom_version }}</el-descriptions-item>
              <el-descriptions-item label="应用版本：">{{ performanceData.app_version }}</el-descriptions-item>
              <el-descriptions-item label="场景名称：">{{ performanceData.scene }}</el-descriptions-item>
              <el-descriptions-item label="自定义版本标识：">{{ baseMark }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
          <el-col :span="12">
            <el-descriptions :title="comparePerformanceData.app_name" :column="1" class="beautified-descriptions">
              <el-descriptions-item label="系统版本：">{{ comparePerformanceData.rom_version }}</el-descriptions-item>
              <el-descriptions-item label="应用版本：">{{ comparePerformanceData.app_version }}</el-descriptions-item>
              <el-descriptions-item label="场景名称：">{{ comparePerformanceData.scene }}</el-descriptions-item>
              <el-descriptions-item label="自定义版本标识：">{{ compareMark }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
        <!--场景负载饼状图 -->
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="data-panel">
              <PieChart :chart-data="scenePieData" :title="pieChartTitle"/>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="data-panel">
              <PieChart :chart-data="compareScenePieData" :title="pieChartTitle"/>
            </div>
          </el-col>
        </el-row>
        <!-- 场景负载增长卡片 -->
        <el-row :gutter="20">
          <el-col :span="24">

            <div class="card-container" style="margin-bottom:10px;">
              <div v-for="item in sceneDiff.values()" :key="item.category" class="category-card">
                <el-card>
                  <template #header>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <span style="font-size: 16px; font-weight: bold;">{{ item.category }}</span>
                      <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">
                        负载占比：{{ item.total_percentage }}
                      </span>
                    </div>
                  </template>
                  <div style="padding: 16px;">
                    <p>
                      负载增长：
                      <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">
                        {{ item.percentage }}
                      </span>
                      <br>
                      <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">{{ item.diff }}</span>
                    </p>

                  </div>
                </el-card>
              </div>
            </div>
          </el-col>
        </el-row>
        <!-- 场景负载迭代折线图 -->
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <LineChart :chart-data="compareSceneLineChartData" :series-type="RightLineChartSeriesType" />
            </div>
          </el-col>
        </el-row>
        <!-- 步骤负载排名横向柱状图 -->
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="data-panel">
              <BarChart :chart-data="perfData" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="data-panel">
              <BarChart :chart-data="comparePerfData" />
            </div>
          </el-col>
        </el-row>
        <!-- 步骤负载柱状图 -->
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="data-panel">
              <LineChart :chart-data="perfData" :series-type="LeftLineChartSeriesType" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="data-panel">
              <LineChart :chart-data="comparePerfData" :series-type="LeftLineChartSeriesType" />
            </div>
          </el-col>
        </el-row>
        <!-- 步骤负载折线图 -->
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="data-panel">
              <LineChart :chart-data="perfData" :series-type="RightLineChartSeriesType" />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="data-panel">
              <LineChart :chart-data="comparePerfData" :series-type="RightLineChartSeriesType" />
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
              <span class="step-duration">{{ getTotalTestStepsCount(testSteps) }}</span>
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
              <span class="step-duration">{{ formatDuration(step.count) }}</span>
            </div>
            <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
            <!-- <div class="step-name">测试轮次：{{ step.round }}</div> -->
            <!-- <div class="step-name" :title="step.perf_data_path">perf文件位置：{{ step.perf_data_path }}</div> -->
          </div>
        </div>

        <!-- 性能迭代区域 -->
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 基准步骤饼图 -->
            <div class="data-panel">
              <PieChart :step-id="currentStepIndex" :chart-data="stepPieData" :title="pieChartTitle"/>
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 迭代步骤饼图 -->
            <div class="data-panel">
              <PieChart :step-id="currentStepIndex" :chart-data="compareStepPieData" :title="pieChartTitle"/>
            </div>
          </el-col>
        </el-row>
        <!-- 步骤负载增长卡片 -->
        <el-row :gutter="20">
          <el-col :span="24">

            <div class="card-container" style="margin-bottom:10px;">
              <div v-for="item in stepDiff.values()" :key="item.category" class="category-card">
                <el-card>
                  <template #header>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <span style="font-size: 16px; font-weight: bold;">{{ item.category }}</span>
                      <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">
                        负载占比：{{ item.total_percentage }}
                      </span>
                    </div>
                  </template>
                  <div style="padding: 16px;">
                    <p>
                      负载增长：
                      <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">
                        {{ item.percentage }}
                      </span><br>
                      <span :style="{ color: item.diff > 0 ? 'red' : 'green' }">{{ item.diff }}</span>
                    </p>
                  </div>
                </el-card>
              </div>
            </div>
          </el-col>
        </el-row>
        <!-- 步骤负载迭代折线图-->
        <el-row :gutter="20">
          <el-col :span="24">
            <div class="data-panel">
              <LineChart
:step-id="currentStepIndex" :chart-data="compareLineChartData"
                :series-type="RightLineChartSeriesType" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 进程负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">进程负载</span>
              </h3>
              <PerfProcessTable
:step-id="currentStepIndex" :data="filteredProcessesPerformanceData" :hide-column="isHidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 进程负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">大分类负载</span>
              </h3>
              <PerfProcessTable
:step-id="currentStepIndex" :data="filteredCategorysPerformanceData" :hide-column="isHidden"
                :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 线程负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">线程负载</span>
              </h3>
              <PerfThreadTable
:step-id="currentStepIndex" :data="filteredThreadsPerformanceData" :hide-column="isHidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 线程负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">小分类负载</span>
              </h3>
              <PerfThreadTable
:step-id="currentStepIndex" :data="filteredComponentNamePerformanceData"
                :hide-column="isHidden" :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 文件负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">文件负载</span>
              </h3>
              <PerfFileTable
:step-id="currentStepIndex" :data="filteredFilesPerformanceData" :hide-column="isHidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 文件负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">文件负载</span>
              </h3>
              <PerfFileTable
:step-id="currentStepIndex" :data="filteredFilesPerformanceData1" :hide-column="isHidden"
                :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 函数负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">函数负载</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="filteredSymbolsPerformanceData" :hide-column="isHidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 函数负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">函数负载</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="filteredSymbolsPerformanceData1" :hide-column="isHidden"
                :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 新增文件负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">新增文件负载表格</span>
              </h3>
              <PerfFileTable
:step-id="currentStepIndex" :data="increaseFilesPerformanceData" :hide-column="hidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 新增文件负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">新增文件负载表格</span>
              </h3>
              <PerfFileTable
:step-id="currentStepIndex" :data="increaseFilesPerformanceData1" :hide-column="hidden"
                :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 新增符号负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">新增符号负载表格</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="increaseSymbolsPerformanceData" :hide-column="hidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 新增符号负载表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">新增符号负载表格</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="increaseSymbolsPerformanceData1" :hide-column="hidden"
                :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 基线函数负载top10表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">基线函数负载top10</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="filteredBaseSymbolsPerformanceData" :hide-column="hidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 基线函数负载top10表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">基线函数负载top10</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="filteredBaseSymbolsPerformanceData1" :hide-column="hidden"
                :has-category="true" />
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <!-- 迭代函数负载top10表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">迭代函数负载top10</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="filteredCompareSymbolsPerformanceData" :hide-column="hidden"
                :has-category="false" />
            </div>
          </el-col>
          <el-col :span="12">
            <!-- 迭代函数负载top10表格 -->
            <div class="data-panel">
              <h3 class="panel-title">
                <span class="version-tag">迭代函数负载top10</span>
              </h3>
              <PerfSymbolTable
:step-id="currentStepIndex" :data="filteredCompareSymbolsPerformanceData1"
                :hide-column="hidden" :has-category="true" />
            </div>
          </el-col>
        </el-row>
      </template>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch, onMounted } from 'vue';
import PerfProcessTable from './PerfProcessTable.vue';
import PerfThreadTable from './PerfThreadTable.vue';
import PerfFileTable from './PerfFileTable.vue';
import PerfSymbolTable from './PerfSymbolTable.vue';
import PieChart from './PieChart.vue';
import BarChart from './BarChart.vue';
import LineChart from './LineChart.vue';
import { ComponentCategory, useJsonDataStore, type PerfData } from '../stores/jsonDataStore.ts';
import { calculateCategorysData, calculateComponentNameData, calculateFileData, calculateFileData1, calculateProcessData, calculateSymbolData, calculateSymbolData1, calculateThreadData, processJson2PieChartData } from '@/utils/jsonUtil.ts';
import UploadHtml from './UploadHtml.vue';

interface SceneLoadDiff {
  category: string;
  diff: number;
  total_percentage: string;
  percentage: string;
}
//初始化数据
const isHidden = false;
const hidden = true;
const LeftLineChartSeriesType = 'bar';
const RightLineChartSeriesType = 'line';
const currentStepIndex = ref(0);
const loading = ref(true);

// 获取存储实例
const jsonDataStore = useJsonDataStore();
// 通过 getter 获取 JSON 数据
const basicInfo = jsonDataStore.basicInfo;
const compareBasicInfo = jsonDataStore.compareBasicInfo;
const perfData = jsonDataStore.perfData || { steps: [] };
const comparePerfData = jsonDataStore.comparePerfData || { steps: [] };
const baseMark = jsonDataStore.baseMark;
const compareMark = jsonDataStore.compareMark;

//thread可能是null，需要处理下。
const performanceData = ref(
  basicInfo
    ? {
        app_name: basicInfo.app_name,
        rom_version: basicInfo.rom_version,
        app_version: basicInfo.app_version,
        scene: basicInfo.scene,
      }
    : {
        app_name: '',
        rom_version: '',
        app_version: '',
        scene: '',
      }
);

const comparePerformanceData = ref(
  compareBasicInfo
    ? {
        app_name: compareBasicInfo.app_name,
        rom_version: compareBasicInfo.rom_version,
        app_version: compareBasicInfo.app_version,
        scene: compareBasicInfo.scene,
      }
    : {
        app_name: '',
        rom_version: '',
        app_version: '',
        scene: '',
      }
);

// 场景负载迭代折线图
const compareSceneLineChartData = ref();
compareSceneLineChartData.value = (perfData.steps.length && comparePerfData.steps.length)
  ? mergeJSONData(perfData, comparePerfData, 0)
  : { steps: [] };

function mergeJSONData(baselineData: PerfData, compareData: PerfData, cur_step_id: number): PerfData {
  if (!baselineData || !compareData || !baselineData.steps.length || !compareData.steps.length) {
    return { steps: [] };
  }

  const mergedData: PerfData = {
    steps: []
  };

  // 合并第一个 JSON 的所有 steps 为"基线"
  const baselineStep = cur_step_id === 0 ? {
    step_name: "基线",
    step_id: 0,
    count: baselineData.steps.reduce((sum, step) => sum + step.count, 0),
    round: baselineData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: baselineData.steps.map(s => s.perf_data_path).join(";"),
    data: baselineData.steps.flatMap(step =>
      step.data.map(item => ({
        ...item
      }))
    )
  } : {
    step_name: "基线",
    step_id: 0,
    count: baselineData.steps.reduce((sum, step) => sum + step.count, 0),
    round: baselineData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: baselineData.steps.map(s => s.perf_data_path).join(";"),
    data: baselineData.steps.filter(step => step.step_id === cur_step_id).flatMap(step =>
      step.data.map(item => ({
        ...item
      }))
    )
  };

  // 合并第二个 JSON 的所有 steps 为"迭代"
  const comparisonStep = cur_step_id === 0 ? {
    step_name: "迭代",
    step_id: 1,
    count: compareData.steps.reduce((sum, step) => sum + step.count, 0),
    round: compareData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: compareData.steps.map(s => s.perf_data_path).join(";"),
    data: compareData.steps.flatMap(step =>
      step.data.map(item => ({
        ...item
      }))
    )
  } : {
    step_name: "迭代",
    step_id: 1,
    count: compareData.steps.reduce((sum, step) => sum + step.count, 0),
    round: compareData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: compareData.steps.map(s => s.perf_data_path).join(";"),
    data: compareData.steps.filter(step => step.step_id === cur_step_id).flatMap(step =>
      step.data.map(item => ({
        ...item
      }))
    )
  };

  // 添加合并后的 steps
  mergedData.steps.push(baselineStep, comparisonStep);
  return mergedData;
}
const pieChartTitle = (perfData.steps[0]?.data?.[0]?.eventType ?? 0) == 0 ? 'cycles' : 'instructions';
// 场景负载饼状图
const scenePieData = ref();
const compareScenePieData = ref();
scenePieData.value = perfData.steps.length ? processJson2PieChartData(perfData, currentStepIndex.value) : { legendData: [], seriesData: [] };
compareScenePieData.value = comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, currentStepIndex.value) : { legendData: [], seriesData: [] };
// 场景负载增长卡片
const sceneDiff = ref();
sceneDiff.value = compareSceneLineChartData.value && compareSceneLineChartData.value.steps.length >= 2
  ? calculateCategoryCountDifference(compareSceneLineChartData.value)
  : [];



//测试步骤导航卡片
const testSteps = ref(
  perfData.steps.map((step, index) => ({
    //从1开始
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }))
);

// 全部步骤负载总数 
const getTotalTestStepsCount = (testSteps: {count: number}[]) => {
  let total = 0;

  testSteps.forEach((step) => {
    total += step.count;
  });
  return total;
};

// 格式化持续时间的方法
const formatDuration = (milliseconds: number) => {
  return `指令数：${milliseconds}`;
};

// 初始化ref
const stepPieData = ref(perfData.steps.length ? processJson2PieChartData(perfData, currentStepIndex.value) : { legendData: [], seriesData: [] });
const compareStepPieData = ref(comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, currentStepIndex.value) : { legendData: [], seriesData: [] });
const compareLineChartData = ref(currentStepIndex.value === 0 ? compareSceneLineChartData.value : (perfData.steps.length && comparePerfData.steps.length ? mergeJSONData(perfData, comparePerfData, currentStepIndex.value) : { steps: [] }));
const stepDiff = ref(compareLineChartData.value && compareLineChartData.value.steps.length >= 2 ? calculateCategoryCountDifference(compareLineChartData.value) : []);

// 响应式更新
watch(currentStepIndex, (stepId) => {
  stepPieData.value = perfData.steps.length ? processJson2PieChartData(perfData, stepId) : { legendData: [], seriesData: [] };
  compareStepPieData.value = comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, stepId) : { legendData: [], seriesData: [] };
  compareLineChartData.value = stepId === 0
    ? compareSceneLineChartData.value
    : (perfData.steps.length && comparePerfData.steps.length ? mergeJSONData(perfData, comparePerfData, stepId) : { steps: [] });
  stepDiff.value = compareLineChartData.value && compareLineChartData.value.steps.length >= 2 ? calculateCategoryCountDifference(compareLineChartData.value) : [];
});

// 处理步骤点击事件的方法，切换步骤，更新数据
const handleStepClick = (stepId: number) => {
  currentStepIndex.value = stepId;
};

// 性能迭代区域
// 基线步骤饼图

stepPieData.value = processJson2PieChartData(perfData, currentStepIndex.value);
// 迭代步骤饼图

compareStepPieData.value = processJson2PieChartData(comparePerfData, currentStepIndex.value);
// 步骤负载迭代折线图

compareLineChartData.value = currentStepIndex.value === 0 ? compareSceneLineChartData.value : mergeJSONData(perfData, comparePerfData, currentStepIndex.value);
//步骤负载增长卡片

stepDiff.value = calculateCategoryCountDifference(compareLineChartData.value);
const mergedProcessPerformanceData = computed(() =>
  calculateProcessData(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedThreadPerformanceData = computed(() =>
  calculateThreadData(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedCategorysPerformanceData = computed(() =>
  calculateCategorysData(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedComponentNamePerformanceData = computed(() =>
  calculateComponentNameData(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedFilePerformanceData = computed(() =>
  calculateFileData(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedFilePerformanceData1 = computed(() =>
  calculateFileData1(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedSymbolsPerformanceData = computed(() =>
  calculateSymbolData(perfData, comparePerfData, currentStepIndex.value === 0)
);

const mergedSymbolsPerformanceData1 = computed(() =>
  calculateSymbolData1(perfData, comparePerfData, currentStepIndex.value === 0)
);

const baseSymbolsPerformanceData = ref(
  calculateSymbolData(perfData, null)
);
const baseSymbolsPerformanceData1 = ref(
  calculateSymbolData1(perfData, null)
);

const compareSymbolsPerformanceData = ref(
  calculateSymbolData(comparePerfData, null)
);
const compareSymbolsPerformanceData1 = ref(
  calculateSymbolData1(comparePerfData, null)
);

// 工具函数：安全排序，避免副作用
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// 进程负载表格
const filteredProcessesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedProcessPerformanceData.value);
  }
  return sortByInstructions(
    mergedProcessPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 线程负载表格
const filteredThreadsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedThreadPerformanceData.value);
  }
  return sortByInstructions(
    mergedThreadPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 大分类负载表格
const filteredCategorysPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedCategorysPerformanceData.value);
  }
  return sortByInstructions(
    mergedCategorysPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 小分类负载表格
const filteredComponentNamePerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedComponentNamePerformanceData.value);
  }
  return sortByInstructions(
    mergedComponentNamePerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 文件负载表格
const filteredFilesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedFilePerformanceData.value);
  }
  return sortByInstructions(
    mergedFilePerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 文件负载表格
const filteredFilesPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedFilePerformanceData1.value);
  }
  return sortByInstructions(
    mergedFilePerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 函数负载表格
const filteredSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedSymbolsPerformanceData.value);
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
// 函数负载表格
const filteredSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedSymbolsPerformanceData1.value);
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});



// 新增文件负载表格
const increaseFilesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(
      mergedFilePerformanceData.value
        .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
        .map(item => ({
          ...item,
          instructions: item.compareInstructions,
          compareInstructions: item.instructions
        }))
    );
  }
  return sortByInstructions(
    mergedFilePerformanceData.value
      .filter((item) => item.stepId === currentStepIndex.value)
      .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
      .map(item => ({
        ...item,
        instructions: item.compareInstructions,
        compareInstructions: item.instructions
      }))
  );
});
// 新增文件负载表格1
const increaseFilesPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(
      mergedFilePerformanceData1.value
        .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
        .map(item => ({
          ...item,
          instructions: item.compareInstructions,
          compareInstructions: item.instructions
        }))
    );
  }
  return sortByInstructions(
    mergedFilePerformanceData1.value
      .filter((item) => item.stepId === currentStepIndex.value)
      .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
      .map(item => ({
        ...item,
        instructions: item.compareInstructions,
        compareInstructions: item.instructions
      }))
  );
});
// 新增函数负载表格
const increaseSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(
      mergedSymbolsPerformanceData.value
        .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
        .map(item => ({
          ...item,
          instructions: item.compareInstructions,
          compareInstructions: item.instructions
        }))
    );
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData.value
      .filter((item) => item.stepId === currentStepIndex.value)
      .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
      .map(item => ({
        ...item,
        instructions: item.compareInstructions,
        compareInstructions: item.instructions
      }))
  );
});
// 新增函数负载表格1
const increaseSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(
      mergedSymbolsPerformanceData1.value
        .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
        .map(item => ({
          ...item,
          instructions: item.compareInstructions,
          compareInstructions: item.instructions
        }))
    );
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData1.value
      .filter((item) => item.stepId === currentStepIndex.value)
      .filter(data => data.instructions === -1 && data.compareInstructions !== -1)
      .map(item => ({
        ...item,
        instructions: item.compareInstructions,
        compareInstructions: item.instructions
      }))
  );
});

// 基线函数负载top10表格
const filteredBaseSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(baseSymbolsPerformanceData.value);
  }
  return sortByInstructions(baseSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value));
});
// 基线函数负载top10表格1
const filteredBaseSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(baseSymbolsPerformanceData1.value);
  }
  return sortByInstructions(baseSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value));
});
// 迭代函数负载top10表格
const filteredCompareSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(compareSymbolsPerformanceData.value);
  }
  return sortByInstructions(compareSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value));
});
// 迭代函数负载top10表格1
const filteredCompareSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(compareSymbolsPerformanceData1.value);
  }
  return sortByInstructions(compareSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value));
});



function calculateCategoryCountDifference(data: PerfData): SceneLoadDiff[] {
  if (!data) return [];
  if (!data.steps || data.steps.length < 2) {
    return [];
  }

  const step1 = data.steps[0];
  const step2 = data.steps[1];

  // 聚合每个步骤的类别计数
  const aggregateCategoryCounts = (step: typeof step1) => {
    const categoryMap = new Map<number, number>();

    step.data.forEach(item => {
      const current = categoryMap.get(item.componentCategory) || 0;
      categoryMap.set(item.componentCategory, current + item.symbolEvents);
    });

    return categoryMap;
  };

  const categoryMap1 = aggregateCategoryCounts(step1);
  const categoryMap2 = aggregateCategoryCounts(step2);

  // 计算总值
  const total1 = Array.from(categoryMap1.values()).reduce((sum, count) => sum + count, 0);
  const total2 = Array.from(categoryMap2.values()).reduce((sum, count) => sum + count, 0);

  const difference: SceneLoadDiff[] = [];

  // 添加总值行
  difference.push({
    category: '总值',
    diff: total2 - total1,
    total_percentage: 100 + '%',
    percentage: calculatePercentageWithFixed(total2 - total1, total1) + '%'
  });

  // 处理每个类别
  const allCategories = new Set([
    ...categoryMap1.keys(),
    ...categoryMap2.keys()
  ]);

  allCategories.forEach(category => {
    const count1 = categoryMap1.get(category) || 0;
    const count2 = categoryMap2.get(category) || 0;

    // 确保类别索引有效
    const categoryName = ComponentCategory[category] || `未知类别(${category})`;

    difference.push({
      category: categoryName,
      diff: count2 - count1,
      total_percentage: calculatePercentageWithFixed(count1, total1) + '%',
      percentage: calculatePercentageWithFixed(count2 - count1, count1) + '%'
    });
  });

  return difference;
}

function calculatePercentageWithFixed(part: number, total: number, decimalPlaces: number = 2): number {
  if (total === 0) {
    //throw new Error('总值不能为零');
    total = 1;
  }
  const percentage = (part / total) * 100;
  return Number.parseFloat(percentage.toFixed(decimalPlaces));
}

const hasCompareData = computed(() => {
  return !!(comparePerformanceData.value && comparePerformanceData.value.app_name);
});

onMounted(() => {
  setTimeout(() => {
    loading.value = false;
  }, 500); // 模拟加载过程，实际可根据数据加载完成时机调整
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
  position: sticky;
  top: 0;
  z-index: 9999;
  /* 固定在页面顶部 */
  background-color: white;
  /* 设置背景颜色，避免内容透过 */
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

/* 迭代区域样式 */
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

/* 设置卡片容器的样式 */
.card-container {
  display: flex;
  flex-wrap: nowrap;
  /* 禁止换行 */
  gap: 16px;
  /* 卡片之间的间距 */
}

/* 设置卡片的样式 */
.category-card {
  flex-basis: 0;
  /* 初始大小为 0 */
  flex-grow: 1;
  /* 允许卡片根据可用空间扩展 */
}

.loading-card {
  margin: 40px auto;
  max-width: 400px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  font-size: 18px;
  color: #2196f3;
}
</style>

