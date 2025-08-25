<template>
  <div class="top10-data-compare">
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

      <!-- 步骤选择器 -->
    <div class="step-selector">
      <el-select v-model="currentStepIndex" placeholder="选择步骤" style="width: 200px;">
        <el-option label="全部步骤" :value="0" />
        <el-option 
          v-for="step in testSteps" 
          :key="step.id"
          :label="`步骤${step.id}: ${step.step_name}`" 
          :value="step.id" />
      </el-select>
    </div>

    <!-- 基线函数负载Top10 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Trophy /></el-icon>
            <span class="top-tag baseline">基线版本函数负载Top10</span>
          </h3>
          <div class="top-description">
            <p>显示基线版本中负载最高的10个函数</p>
          </div>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="filteredBaseSymbolsPerformanceData" 
            :hide-column="true"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Medal /></el-icon>
            <span class="top-tag baseline-category">基线版本分类负载Top10</span>
          </h3>
          <div class="top-description">
            <p>按分类显示基线版本的函数负载排名</p>
          </div>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="filteredBaseSymbolsPerformanceData1" 
            :hide-column="true"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <!-- 对比版本函数负载Top10 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Star /></el-icon>
            <span class="top-tag compare">对比版本函数负载Top10</span>
          </h3>
          <div class="top-description">
            <p>显示对比版本中负载最高的10个函数</p>
          </div>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="filteredCompareSymbolsPerformanceData" 
            :hide-column="true"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Star /></el-icon>
            <span class="top-tag compare-category">对比版本分类负载Top10</span>
          </h3>
          <div class="top-description">
            <p>按分类显示对比版本的函数负载排名</p>
          </div>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="filteredCompareSymbolsPerformanceData1"
            :hide-column="true" 
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <!-- Top10 对比统计 -->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><DataAnalysis /></el-icon>
            <span>Top10 负载对比分析</span>
          </h3>
          <div class="comparison-stats">
            <div class="comparison-section">
              <h4>基线版本 Top10 统计</h4>
              <div class="stats-grid">
                <div class="stat-item">
                  <span class="stat-label">Top10 总负载:</span>
                  <span class="stat-value baseline-color">{{ formatNumber(baselineTop10Total) }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">平均负载:</span>
                  <span class="stat-value baseline-color">{{ formatNumber(baselineTop10Average) }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">最高负载:</span>
                  <span class="stat-value baseline-color">{{ formatNumber(baselineTop10Max) }}</span>
                </div>
              </div>
            </div>
            
            <div class="comparison-section">
              <h4>对比版本 Top10 统计</h4>
              <div class="stats-grid">
                <div class="stat-item">
                  <span class="stat-label">Top10 总负载:</span>
                  <span class="stat-value compare-color">{{ formatNumber(compareTop10Total) }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">平均负载:</span>
                  <span class="stat-value compare-color">{{ formatNumber(compareTop10Average) }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">最高负载:</span>
                  <span class="stat-value compare-color">{{ formatNumber(compareTop10Max) }}</span>
                </div>
              </div>
            </div>

            <div class="comparison-section">
              <h4>变化分析</h4>
              <div class="stats-grid">
                <div class="stat-item">
                  <span class="stat-label">总负载变化:</span>
                  <span class="stat-value" :class="totalLoadChange >= 0 ? 'increase' : 'decrease'">
                    {{ totalLoadChange >= 0 ? '+' : '' }}{{ formatNumber(totalLoadChange) }}
                  </span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">平均负载变化:</span>
                  <span class="stat-value" :class="averageLoadChange >= 0 ? 'increase' : 'decrease'">
                    {{ averageLoadChange >= 0 ? '+' : '' }}{{ formatNumber(averageLoadChange) }}
                  </span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">最高负载变化:</span>
                  <span class="stat-value" :class="maxLoadChange >= 0 ? 'increase' : 'decrease'">
                    {{ maxLoadChange >= 0 ? '+' : '' }}{{ formatNumber(maxLoadChange) }}
                  </span>
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
import { ref, computed, watch } from 'vue';

const props = defineProps({
  step: {
    type: Number,
    default: 0
  }
});
import {
  Trophy, Medal, Star, DataAnalysis
} from '@element-plus/icons-vue';
import PerfSymbolTable from '../PerfSymbolTable.vue';
import UploadHtml from '../UploadHtml.vue';
import { useJsonDataStore } from '../../stores/jsonDataStore';
import { calculateSymbolData, calculateSymbolData1 } from '@/utils/jsonUtil';

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const perfData = jsonDataStore.perfData || { steps: [] };
const comparePerfData = jsonDataStore.comparePerfData || { steps: [] };

// 检查是否有对比数据
const hasCompareData = computed(() => {
  return jsonDataStore.comparePerfData && jsonDataStore.comparePerfData.steps.length > 0;
});

// 当前步骤索引
const currentStepIndex = ref(props.step || 0);

// 监听 props.step 变化，同步更新 currentStepIndex
watch(() => props.step, (newStep) => {
  currentStepIndex.value = newStep || 0;
}, { immediate: true });

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

// 基线和对比数据 - 使用空的对比数据来获取单独的数据
const emptyPerfData = { steps: [] };
const baseSymbolsPerformanceData = computed(() => calculateSymbolData(perfData, emptyPerfData, false));
const baseSymbolsPerformanceData1 = computed(() => calculateSymbolData1(perfData, emptyPerfData, false));
const compareSymbolsPerformanceData = computed(() => calculateSymbolData(comparePerfData, emptyPerfData, false));
const compareSymbolsPerformanceData1 = computed(() => calculateSymbolData1(comparePerfData, emptyPerfData, false));

// 工具函数：安全排序
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// 过滤Top10数据
const filteredBaseSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(baseSymbolsPerformanceData.value).slice(0, 10);
  }
  return sortByInstructions(
    baseSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  ).slice(0, 10);
});

const filteredBaseSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(baseSymbolsPerformanceData1.value).slice(0, 10);
  }
  return sortByInstructions(
    baseSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  ).slice(0, 10);
});

const filteredCompareSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(compareSymbolsPerformanceData.value).slice(0, 10);
  }
  return sortByInstructions(
    compareSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  ).slice(0, 10);
});

const filteredCompareSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(compareSymbolsPerformanceData1.value).slice(0, 10);
  }
  return sortByInstructions(
    compareSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  ).slice(0, 10);
});

// 统计数据
const baselineTop10Total = computed(() => 
  filteredBaseSymbolsPerformanceData.value.reduce((sum, item) => sum + item.instructions, 0)
);

const baselineTop10Average = computed(() => 
  filteredBaseSymbolsPerformanceData.value.length > 0 
    ? baselineTop10Total.value / filteredBaseSymbolsPerformanceData.value.length 
    : 0
);

const baselineTop10Max = computed(() => 
  filteredBaseSymbolsPerformanceData.value.length > 0 
    ? filteredBaseSymbolsPerformanceData.value[0].instructions 
    : 0
);

const compareTop10Total = computed(() => 
  filteredCompareSymbolsPerformanceData.value.reduce((sum, item) => sum + item.instructions, 0)
);

const compareTop10Average = computed(() => 
  filteredCompareSymbolsPerformanceData.value.length > 0 
    ? compareTop10Total.value / filteredCompareSymbolsPerformanceData.value.length 
    : 0
);

const compareTop10Max = computed(() => 
  filteredCompareSymbolsPerformanceData.value.length > 0 
    ? filteredCompareSymbolsPerformanceData.value[0].instructions 
    : 0
);

// 变化分析
const totalLoadChange = computed(() => compareTop10Total.value - baselineTop10Total.value);
const averageLoadChange = computed(() => compareTop10Average.value - baselineTop10Average.value);
const maxLoadChange = computed(() => compareTop10Max.value - baselineTop10Max.value);

// 格式化数字
const formatNumber = (num: number) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
};
</script>

<style scoped>
.top10-data-compare {
  padding: 20px;
  background: #f5f7fa;
}

.step-selector {
  margin-bottom: 20px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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

.top-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.top-tag.baseline {
  background: #e8f5e8;
  color: #2e7d32;
}

.top-tag.baseline-category {
  background: #e3f2fd;
  color: #1976d2;
}

.top-tag.compare {
  background: #fff3e0;
  color: #f57c00;
}

.top-tag.compare-category {
  background: #fce4ec;
  color: #c2185b;
}

.top-description {
  margin-bottom: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 4px solid #2196f3;
}

.top-description p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.comparison-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.comparison-section {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #2196f3;
}

.comparison-section h4 {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 16px;
}

.stats-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #e0e0e0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.stat-value {
  font-weight: 600;
  font-size: 16px;
}

.baseline-color {
  color: #1976d2;
}

.compare-color {
  color: #d81b60;
}

.increase {
  color: #d32f2f;
}

.decrease {
  color: #388e3c;
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
