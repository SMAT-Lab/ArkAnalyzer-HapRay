<template>
  <div class="compare-overview">
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

      <!-- 版本信息对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
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

      <!-- 场景负载饼状图对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><PieChartIcon /></el-icon>
              <span class="version-tag baseline">基线版本场景负载</span>
            </h3>
            <PieChart :chart-data="scenePieData" :title="pieChartTitle"/>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><PieChartIcon /></el-icon>
              <span class="version-tag compare">对比版本场景负载</span>
            </h3>
            <PieChart :chart-data="compareScenePieData" :title="pieChartTitle"/>
          </div>
        </el-col>
      </el-row>

      <!-- 场景负载变化分析 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><TrendCharts /></el-icon>
              <span>场景负载变化分析</span>
            </h3>
            <div class="card-container">
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
          </div>
        </el-col>
      </el-row>

      <!-- 场景负载趋势对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><DataLine /></el-icon>
              <span>场景负载趋势对比</span>
            </h3>
            <LineChart :chart-data="compareSceneLineChartData" :series-type="'line'" />
          </div>
        </el-col>
      </el-row>

      <!-- 步骤负载排名对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><Histogram /></el-icon>
              <span class="version-tag baseline">基线版本步骤负载排名</span>
            </h3>
            <BarChart :chart-data="perfData" />
          </div>
        </el-col>
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><Histogram /></el-icon>
              <span class="version-tag compare">对比版本步骤负载排名</span>
            </h3>
            <BarChart :chart-data="comparePerfData" />
          </div>
        </el-col>
      </el-row>

      <!-- 快速导航 -->
      <el-row :gutter="20">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><Guide /></el-icon>
              <span>快速导航</span>
            </h3>
            <div class="quick-nav">
              <div class="nav-section">
                <h4>按步骤对比分析</h4>
                <div class="nav-cards">
                  <div v-for="step in testSteps" :key="step.id" class="nav-card" @click="navigateToStep(step.id)">
                    <div class="nav-card-header">
                      <span class="step-number">步骤{{ step.id }}</span>
                      <span class="step-count">{{ formatNumber(step.count) }}</span>
                    </div>
                    <div class="nav-card-title" :title="step.step_name">{{ step.step_name }}</div>
                    <div class="nav-card-actions">
                      <el-button size="small" @click.stop="navigateToStepLoad(step.id)">负载对比</el-button>
                      <el-button size="small" @click.stop="navigateToStepDetail(step.id)">详细对比</el-button>
                      <el-button size="small" @click.stop="navigateToStepFaultTree(step.id)">故障树对比</el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { TrendCharts, DataLine, Histogram, Guide, PieChart as PieChartIcon } from '@element-plus/icons-vue';
import PieChart from '../common/charts/PieChart.vue';
import BarChart from '../common/charts/BarChart.vue';
import LineChart from '../common/charts/LineChart.vue';
import UploadHtml from '../common/UploadHtml.vue';
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
const basicInfo = jsonDataStore.basicInfo;
const compareBasicInfo = jsonDataStore.compareBasicInfo;
const perfData = jsonDataStore.perfData || { steps: [] };
const comparePerfData = jsonDataStore.comparePerfData || { steps: [] };
const baseMark = jsonDataStore.baseMark;
const compareMark = jsonDataStore.compareMark;

// 检查是否有对比数据
const hasCompareData = computed(() => {
  return jsonDataStore.comparePerfData && jsonDataStore.comparePerfData.steps.length > 0;
});

// 版本信息
const performanceData = computed(() => 
  basicInfo ? {
    app_name: basicInfo.app_name,
    rom_version: basicInfo.rom_version,
    app_version: basicInfo.app_version,
    scene: basicInfo.scene,
  } : {
    app_name: '',
    rom_version: '',
    app_version: '',
    scene: '',
  }
);

const comparePerformanceData = computed(() =>
  compareBasicInfo ? {
    app_name: compareBasicInfo.app_name,
    rom_version: compareBasicInfo.rom_version,
    app_version: compareBasicInfo.app_version,
    scene: compareBasicInfo.scene,
  } : {
    app_name: '',
    rom_version: '',
    app_version: '',
    scene: '',
  }
);

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

const scenePieData = computed(() => 
  perfData.steps.length ? processJson2PieChartData(perfData, 0) : { legendData: [], seriesData: [] }
);

const compareScenePieData = computed(() => 
  comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, 0) : { legendData: [], seriesData: [] }
);

// 合并数据用于对比
const compareSceneLineChartData = computed(() => {
  if (!perfData.steps.length || !comparePerfData.steps.length) {
    return { steps: [] };
  }
  return mergeJSONData(perfData, comparePerfData);
});

// 场景负载差异
const sceneDiff = computed(() => 
  compareSceneLineChartData.value && compareSceneLineChartData.value.steps.length >= 2
    ? calculateCategoryCountDifference(compareSceneLineChartData.value)
    : []
);

// 导航方法
const emit = defineEmits(['navigate']);

const navigateToStep = (stepId: number) => {
  emit('navigate', `compare_step_load_${stepId}`);
};

const navigateToStepLoad = (stepId: number) => {
  emit('navigate', `compare_step_load_${stepId}`);
};

const navigateToStepDetail = (stepId: number) => {
  emit('navigate', `compare_step_detail_${stepId}`);
};

const navigateToStepFaultTree = (stepId: number) => {
  emit('navigate', `compare_step_fault_tree_${stepId}`);
};

// 格式化数字
const formatNumber = (num: number) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
};

// 合并数据函数
function mergeJSONData(baselineData: PerfData, compareData: PerfData): PerfData {
  if (!baselineData || !compareData || !baselineData.steps.length || !compareData.steps.length) {
    return { steps: [] };
  }

  const mergedData: PerfData = { steps: [] };

  // 合并基线数据
  const baselineStep = {
    step_name: "基线",
    step_id: 0,
    count: baselineData.steps.reduce((sum, step) => sum + step.count, 0),
    round: baselineData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: baselineData.steps.map(s => s.perf_data_path).join(";"),
    data: baselineData.steps.flatMap(step =>
      step.data.map(item => ({ ...item }))
    )
  };

  // 合并对比数据
  const comparisonStep = {
    step_name: "迭代",
    step_id: 1,
    count: compareData.steps.reduce((sum, step) => sum + step.count, 0),
    round: compareData.steps.reduce((sum, step) => sum + step.round, 0),
    perf_data_path: compareData.steps.map(s => s.perf_data_path).join(";"),
    data: compareData.steps.flatMap(step =>
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
    total_percentage: '100%',
    percentage: calculatePercentageWithFixed(total2 - total1, total1) + '%'
  });

  // 处理每个类别
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
.compare-overview {
  padding: 20px;
  background: #f5f7fa;
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

.beautified-descriptions {
  background-color: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
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

.quick-nav {
  padding: 16px 0;
}

.nav-section h4 {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 16px;
}

.nav-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.nav-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e9ecef;
}

.nav-card:hover {
  background: #e9ecef;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.nav-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.step-number {
  font-weight: 600;
  color: #2196f3;
}

.step-count {
  font-size: 12px;
  color: #666;
}

.nav-card-title {
  font-size: 14px;
  margin-bottom: 12px;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-card-actions {
  display: flex;
  gap: 8px;
}
</style>
