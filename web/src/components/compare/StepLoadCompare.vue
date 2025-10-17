<template>
  <div class="step-load-compare">
    <!-- 上传组件 -->
    <div v-if="!hasCompareData" style="margin-bottom: 16px;">
      <UploadHtml />
    </div>

    <template v-else>
      <!-- 负载分类说明 -->
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

      <!-- 步骤导航 -->
    <div class="step-nav">
      <div
        :class="['step-item', { active: currentStepIndex === 0 }]" 
        @click="handleStepClick(0)">
        <div class="step-header">
          <span class="step-order">STEP 0</span>
          <span class="step-duration">{{ getTotalTestStepsCount(testSteps) }}</span>
        </div>
        <div class="step-name">全部步骤</div>
      </div>
      <div
        v-for="(step, index) in testSteps" 
        :key="index" 
        :class="['step-item', { active: currentStepIndex === step.id }]" 
        @click="handleStepClick(step.id)">
        <div class="step-header">
          <span class="step-order">STEP {{ step.id }}</span>
          <span class="step-duration">{{ formatDuration(step.count) }}</span>
        </div>
        <div class="step-name" :title="step.step_name">{{ step.step_name }}</div>
      </div>
    </div>

    <!-- 步骤负载排名横向柱状图 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag baseline">基线版本步骤负载排名</span>
          </h3>
          <BarChart :chart-data="perfData" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag compare">对比版本步骤负载排名</span>
          </h3>
          <BarChart :chart-data="comparePerfData" />
        </div>
      </el-col>
    </el-row>

    <!-- 步骤负载柱状图 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag baseline">基线版本步骤负载分布</span>
          </h3>
          <LineChart :chart-data="perfData" :series-type="'bar'" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag compare">对比版本步骤负载分布</span>
          </h3>
          <LineChart :chart-data="comparePerfData" :series-type="'bar'" />
        </div>
      </el-col>
    </el-row>

    <!-- 步骤负载折线图 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag baseline">基线版本步骤负载趋势</span>
          </h3>
          <LineChart :chart-data="perfData" :series-type="'line'" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag compare">对比版本步骤负载趋势</span>
          </h3>
          <LineChart :chart-data="comparePerfData" :series-type="'line'" />
        </div>
      </el-col>
    </el-row>

    <!-- 当前步骤负载对比 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag baseline">基线版本当前步骤负载</span>
          </h3>
          <PieChart :step-id="currentStepIndex" :chart-data="stepPieData" :title="pieChartTitle"/>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag compare">对比版本当前步骤负载</span>
          </h3>
          <PieChart :step-id="currentStepIndex" :chart-data="compareStepPieData" :title="pieChartTitle"/>
        </div>
      </el-col>
    </el-row>

    <!-- 步骤负载增长卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><TrendCharts /></el-icon>
            <span>当前步骤负载变化分析</span>
          </h3>
          <div class="card-container">
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
        </div>
      </el-col>
    </el-row>

    <!-- 步骤负载迭代折线图-->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><DataLine /></el-icon>
            <span>当前步骤负载趋势对比</span>
          </h3>
          <LineChart
            :step-id="currentStepIndex" 
            :chart-data="compareLineChartData"
            :series-type="'line'" />
        </div>
      </el-col>
    </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { TrendCharts, DataLine } from '@element-plus/icons-vue';
import PieChart from '../PieChart.vue';
import BarChart from '../BarChart.vue';
import LineChart from '../LineChart.vue';
import UploadHtml from '../UploadHtml.vue';
import { useJsonDataStore, ComponentCategory, type PerfData } from '../../stores/jsonDataStore';
import { processJson2PieChartData } from '@/utils/jsonUtil';

interface SceneLoadDiff {
  category: string;
  diff: number;
  total_percentage: string;
  percentage: string;
}

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData || { steps: [] };
const comparePerfData = jsonDataStore.comparePerfData || { steps: [] };

// 检查是否有对比数据
const hasCompareData = computed(() => {
  return jsonDataStore.comparePerfData && jsonDataStore.comparePerfData.steps.length > 0;
});

// 当前步骤索引
const currentStepIndex = ref(0);

// 测试步骤数据
const testSteps = computed(() =>
  perfData.steps.map((step, index) => ({
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
    round: step.round,
    perf_data_path: step.perf_data_path,
  }))
);

// 图表数据
const pieChartTitle = computed(() => 
  (perfData.steps[0]?.data?.[0]?.eventType ?? 0) == 0 ? 'cycles' : 'instructions'
);

// 响应式数据
const stepPieData = ref(perfData.steps.length ? processJson2PieChartData(perfData, currentStepIndex.value) : { legendData: [], seriesData: [] });
const compareStepPieData = ref(comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, currentStepIndex.value) : { legendData: [], seriesData: [] });
const compareLineChartData = ref(currentStepIndex.value === 0 ? mergeJSONData(perfData, comparePerfData, 0) : (perfData.steps.length && comparePerfData.steps.length ? mergeJSONData(perfData, comparePerfData, currentStepIndex.value) : { steps: [] }));
const stepDiff = ref(compareLineChartData.value && compareLineChartData.value.steps.length >= 2 ? calculateCategoryCountDifference(compareLineChartData.value) : []);

// 响应式更新
watch(currentStepIndex, (stepId) => {
  stepPieData.value = perfData.steps.length ? processJson2PieChartData(perfData, stepId) : { legendData: [], seriesData: [] };
  compareStepPieData.value = comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, stepId) : { legendData: [], seriesData: [] };
  compareLineChartData.value = stepId === 0
    ? mergeJSONData(perfData, comparePerfData, 0)
    : (perfData.steps.length && comparePerfData.steps.length ? mergeJSONData(perfData, comparePerfData, stepId) : { steps: [] });
  stepDiff.value = compareLineChartData.value && compareLineChartData.value.steps.length >= 2 ? calculateCategoryCountDifference(compareLineChartData.value) : [];
});

// 工具函数
const getTotalTestStepsCount = (testSteps: {count: number}[]) => {
  return testSteps.reduce((total, step) => total + step.count, 0);
};

const formatDuration = (milliseconds: number) => {
  return `指令数：${milliseconds}`;
};

const handleStepClick = (stepId: number) => {
  currentStepIndex.value = stepId;
};

// 合并数据函数
function mergeJSONData(baselineData: PerfData, compareData: PerfData, cur_step_id: number): PerfData {
  if (!baselineData || !compareData || !baselineData.steps.length || !compareData.steps.length) {
    return { steps: [] };
  }

  const mergedData: PerfData = { steps: [] };

  // 合并基线数据
  const baselineStep = cur_step_id === 0 ? {
    step_name: "基线",
    step_id: 0,
    count: baselineData.steps.reduce((sum, step) => sum + step.count, 0),
    round: baselineData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: baselineData.steps.map(s => s.perf_data_path).join(";"),
    data: baselineData.steps.flatMap(step =>
      step.data.map(item => ({ ...item }))
    )
  } : {
    step_name: "基线",
    step_id: 0,
    count: baselineData.steps.reduce((sum, step) => sum + step.count, 0),
    round: baselineData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: baselineData.steps.map(s => s.perf_data_path).join(";"),
    data: baselineData.steps.filter(step => step.step_id === cur_step_id).flatMap(step =>
      step.data.map(item => ({ ...item }))
    )
  };

  // 合并对比数据
  const comparisonStep = cur_step_id === 0 ? {
    step_name: "迭代",
    step_id: 1,
    count: compareData.steps.reduce((sum, step) => sum + step.count, 0),
    round: compareData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: compareData.steps.map(s => s.perf_data_path).join(";"),
    data: compareData.steps.flatMap(step =>
      step.data.map(item => ({ ...item }))
    )
  } : {
    step_name: "迭代",
    step_id: 1,
    count: compareData.steps.reduce((sum, step) => sum + step.count, 0),
    round: compareData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: compareData.steps.map(s => s.perf_data_path).join(";"),
    data: compareData.steps.filter(step => step.step_id === cur_step_id).flatMap(step =>
      step.data.map(item => ({ ...item }))
    )
  };

  mergedData.steps.push(baselineStep, comparisonStep);
  return mergedData;
}

// 计算类别差异
function calculateCategoryCountDifference(data: PerfData): SceneLoadDiff[] {
  if (!data || !data.steps || data.steps.length < 2) {
    return [];
  }

  const step1 = data.steps[0];
  const step2 = data.steps[1];

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

  const total1 = Array.from(categoryMap1.values()).reduce((sum, count) => sum + count, 0);
  const total2 = Array.from(categoryMap2.values()).reduce((sum, count) => sum + count, 0);

  const difference: SceneLoadDiff[] = [];

  difference.push({
    category: '总值',
    diff: total2 - total1,
    total_percentage: '100%',
    percentage: calculatePercentageWithFixed(total2 - total1, total1) + '%'
  });

  const allCategories = new Set([...categoryMap1.keys(), ...categoryMap2.keys()]);
  allCategories.forEach(category => {
    const count1 = categoryMap1.get(category) || 0;
    const count2 = categoryMap2.get(category) || 0;
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
    total = 1;
  }
  const percentage = (part / total) * 100;
  return Number.parseFloat(percentage.toFixed(decimalPlaces));
}
</script>

<style scoped>
.step-load-compare {
  padding: 20px;
  background: #f5f7fa;
}

.step-nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
  position: sticky;
  top: 0;
  z-index: 9999;
  background-color: white;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.step-item {
  background: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s;
}

.step-item:hover {
  transform: translateY(-2px);
}

.step-item.active {
  border: 2px solid #2196f3;
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
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.version-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.version-tag.baseline {
  background: #e3f2fd;
  color: #1976d2;
}

.version-tag.compare {
  background: #fce4ec;
  color: #d81b60;
}

.card-container {
  display: flex;
  flex-wrap: nowrap;
  gap: 16px;
}

.category-card {
  flex-basis: 0;
  flex-grow: 1;
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
</style>
