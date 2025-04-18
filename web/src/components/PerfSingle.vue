<template>
  <div class="performance-comparison">
    <el-descriptions :title="performanceData.name" :column="1" class="beautified-descriptions">
      <el-descriptions-item label="应用版本：">{{ performanceData.version }}</el-descriptions-item>
      <el-descriptions-item label="场景名称：">{{ performanceData.scene }}</el-descriptions-item>
    </el-descriptions>
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <PieChart />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <BarChart />
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="json" :seriesType="LeftLineChartSeriesType" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <LineChart :chartData="json" :seriesType="RightLineChartSeriesType" />
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
        ]"
        @click="handleStepClick(0)"
      >
        <div class="step-header">
          <span class="step-order">STEP 0</span>
          <span class="step-duration">{{ getTotalTestStepsCount(testSteps) }}</span>
        </div>
        <div class="step-name">全部步骤</div>
      </div>
      <div
        v-for="(step, index) in testSteps"
        :key="index"
        :class="[
          'step-item',
          {
            active: currentStepIndex === step.id,
          },
        ]"
        @click="handleStepClick(step.id)"
      >
        <div class="step-header">
          <span class="step-order">STEP {{ step.id }}</span>
          <span class="step-duration">{{ formatDuration(step.count) }}</span>
        </div>
        <div class="step-name">{{ step.step_name }}</div>
      </div>
    </div>

    <!-- 性能对比区域 -->

    <el-row :gutter="20">
      <el-col :span="8">
        <!-- 步骤饼图 -->
        <div class="data-panel">
          <PieChartStep :stepId="currentStepIndex" :data="stepPieData" />
        </div>
      </el-col>
      <el-col :span="16">
        <!-- 基准版本 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">文件负载</span>
          </h3>
          <PerfTable :stepId="currentStepIndex" :data="filteredPerformanceData" />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import PerfTable from './PerfTable.vue';
import PieChart from './PieChart.vue';
import PieChartStep from './PieChartStep.vue';
import BarChart from './BarChart.vue';
import LineChart from './LineChart.vue';
import { useJsonDataStore, type JSONData } from '../stores/jsonDataStore.ts';

const LeftLineChartSeriesType = 'bar';
const RightLineChartSeriesType = 'line';

// 获取存储实例
const jsonDataStore = useJsonDataStore();
// 通过 getter 获取 JSON 数据
const json = jsonDataStore.jsonData;
console.log('从元素获取到的 JSON 数据:');

const testSteps = ref(
  json!.steps.map((step, index) => ({
    //从1开始
    id: index + 1,
    step_name: step.step_name,
    count: step.count,
  }))
);

const getTotalTestStepsCount = (testSteps: any[]) => {
  let total = 0;

  testSteps.forEach((step) => {
    total += step.count;
  });
  return total;
};

const performanceData = ref({
  id: json!.app_id,
  name: json!.app_name,
  version: json!.app_version,
  scene: json!.scene,
  instructions: json!.steps.flatMap((step) =>
    step.data.flatMap((item) =>
      item.subData.flatMap((subItem) =>
        subItem.files.map((file) => ({
          stepId: step.step_id,
          instructions: file.count,
          name: file.file,
          category: json!.categories[item.category],
        }))
      )
    )
  ),
});

const symbolData = ref({
  instructions: [
    { symbol: 'Symbol1', count: 50 },
    { symbol: 'Symbol2', count: 100 },
  ],
});

const currentStepIndex = ref(0);
const symbolDialogVisible = ref(false);
const selectedFile = ref('');

// 格式化持续时间的方法
const formatDuration = (milliseconds: any) => {
  return `指令数：${milliseconds}`;
};

let stepPieData = processJSONData(json);
// 处理步骤点击事件的方法
const handleStepClick = (stepId: any) => {
  currentStepIndex.value = stepId;
  stepPieData = processJSONData(json);
};

// 计算属性，根据当前步骤 ID 过滤性能数据
const filteredPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return performanceData.value.instructions.sort((a, b) => b.instructions - a.instructions);
  }
  return performanceData.value.instructions
    .filter((item) => item.stepId === currentStepIndex.value)
    .sort((a, b) => b.instructions - a.instructions);
});

// 处理 JSON 数据生成steps饼状图所需数据
function processJSONData(data: JSONData | null) {
  if (data === null) {
    return {};
  }
  const { categories, steps } = data;
  const categoryCountMap = new Map<string, number>();

  // 初始化每个分类的计数为 0
  categories.forEach((category) => {
    categoryCountMap.set(category, 0);
  });

  // 遍历所有步骤中的数据，累加每个分类的计数
  steps.forEach((step) => {
    if (currentStepIndex.value === 0) {
      step.data.forEach((item) => {
        const categoryName = categories[item.category];
        const currentCount = categoryCountMap.get(categoryName) || 0;
        categoryCountMap.set(categoryName, currentCount + item.count);
      });
    } else {
      if (step.step_id === currentStepIndex.value) {
        step.data.forEach((item) => {
          const categoryName = categories[item.category];
          const currentCount = categoryCountMap.get(categoryName) || 0;
          categoryCountMap.set(categoryName, currentCount + item.count);
        });
      }
    }
  });

  const legendData: string[] = [];
  const seriesData: { name: string; value: number }[] = [];

  // 将分类名称和对应的计数转换为饼状图所需的数据格式
  categoryCountMap.forEach((count, category) => {
    legendData.push(category);
    seriesData.push({ name: category, value: count });
  });

  return { legendData, seriesData };
}
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
</style>
