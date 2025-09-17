<template>
  <div class="compare-step-load">
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

      <!-- 当前步骤负载饼图对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><PieChartIcon /></el-icon>
              <span class="version-tag baseline">基线版本步骤{{ stepId }}负载</span>
            </h3>
            <PieChart :step-id="stepId" :chart-data="stepPieData" :title="pieChartTitle"/>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><PieChartIcon /></el-icon>
              <span class="version-tag compare">对比版本步骤{{ stepId }}负载</span>
            </h3>
            <PieChart :step-id="stepId" :chart-data="compareStepPieData" :title="pieChartTitle"/>
          </div>
        </el-col>
      </el-row>

      <!-- 步骤负载变化分析 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><TrendCharts /></el-icon>
              <span>步骤{{ stepId }}负载变化分析</span>
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

      <!-- 步骤负载趋势对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><DataLine /></el-icon>
              <span>步骤{{ stepId }}负载趋势对比</span>
            </h3>
            <LineChart :step-id="stepId" :chart-data="compareLineChartData" :series-type="'line'" />
          </div>
        </el-col>
      </el-row>

      <!-- 步骤负载柱状图对比 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><Histogram /></el-icon>
              <span class="version-tag baseline">基线版本步骤{{ stepId }}负载分布</span>
            </h3>
            <LineChart :step-id="stepId" :chart-data="perfData" :series-type="'bar'" />
          </div>
        </el-col>
        <el-col :span="12">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><Histogram /></el-icon>
              <span class="version-tag compare">对比版本步骤{{ stepId }}负载分布</span>
            </h3>
            <LineChart :step-id="stepId" :chart-data="comparePerfData" :series-type="'bar'" />
          </div>
        </el-col>
      </el-row>

      <!-- 快速导航 -->
      <el-row :gutter="20">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <el-icon><Guide /></el-icon>
              <span>相关分析</span>
            </h3>
            <div class="quick-actions">
              <el-button type="primary" @click="navigateToDetail">
                <el-icon><DataBoard /></el-icon>
                查看详细对比
              </el-button>
              <el-button type="success" @click="navigateToNew">
                <el-icon><CirclePlus /></el-icon>
                查看新增分析
              </el-button>
              <el-button type="warning" @click="navigateToTop10">
                <el-icon><Trophy /></el-icon>
                查看Top10对比
              </el-button>
              <el-button @click="navigateToOverview">
                <el-icon><ArrowLeft /></el-icon>
                返回总览
              </el-button>
            </div>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { TrendCharts, DataLine, PieChart as PieChartIcon, Histogram, Guide, DataBoard, CirclePlus, Trophy, ArrowLeft } from '@element-plus/icons-vue';
import PieChart from '../PieChart.vue';
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

const props = defineProps({
  step: {
    type: Number,
    required: true
  }
});

const emit = defineEmits(['navigate']);

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData || { steps: [] };
const comparePerfData = jsonDataStore.comparePerfData || { steps: [] };

// 检查是否有对比数据
const hasCompareData = computed(() => {
  return jsonDataStore.comparePerfData && jsonDataStore.comparePerfData.steps.length > 0;
});

// 当前步骤ID
const stepId = computed(() => props.step);



// 图表数据
const pieChartTitle = computed(() => 
  (perfData.steps[0]?.data?.[0]?.eventType ?? 0) == 0 ? 'cycles' : 'instructions'
);

const stepPieData = computed(() => 
  perfData.steps.length ? processJson2PieChartData(perfData, stepId.value) : { legendData: [], seriesData: [] }
);

const compareStepPieData = computed(() => 
  comparePerfData.steps.length ? processJson2PieChartData(comparePerfData, stepId.value) : { legendData: [], seriesData: [] }
);

// 合并数据用于对比
const compareLineChartData = computed(() => {
  if (!perfData.steps.length || !comparePerfData.steps.length) {
    return { steps: [] };
  }
  return mergeJSONData(perfData, comparePerfData, stepId.value);
});

// 步骤负载差异
const stepDiff = computed(() => 
  compareLineChartData.value && compareLineChartData.value.steps.length >= 2
    ? calculateCategoryCountDifference(compareLineChartData.value)
    : []
);

// 导航方法
const navigateToDetail = () => {
  emit('navigate', `compare_step_detail_${stepId.value}`);
};

const navigateToNew = () => {
  emit('navigate', `compare_step_new_${stepId.value}`);
};

const navigateToTop10 = () => {
  emit('navigate', `compare_step_top10_${stepId.value}`);
};

const navigateToOverview = () => {
  emit('navigate', 'compare_overview');
};



// 合并数据函数
function mergeJSONData(baselineData: PerfData, compareData: PerfData, cur_step_id: number): PerfData {
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
    data: baselineData.steps.filter(step => step.step_id === cur_step_id).flatMap(step =>
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
.compare-step-load {
  padding: 20px;
  background: #f5f7fa;
}

.step-info {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.step-header h2 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 24px;
}

.step-details {
  display: flex;
  gap: 20px;
  align-items: center;
}

.step-name {
  font-size: 16px;
  color: #666;
}

.step-count {
  font-size: 14px;
  color: #999;
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

.quick-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
