<template>
  <div class="new-data-analysis">
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
          v-for="stepItem in testSteps"
          :key="stepItem.id"
          :label="`步骤${stepItem.id}: ${stepItem.step_name}`"
          :value="stepItem.id" />
      </el-select>
    </div>

    <!-- 新增数据统计卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><DataAnalysis /></el-icon>
            <span>新增数据统计概览</span>
          </h3>
          <div class="stats-container">
            <div class="stat-card">
              <div class="stat-icon">📁</div>
              <div class="stat-content">
                <div class="stat-value">{{ newFilesCount }}</div>
                <div class="stat-label">新增文件数量</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">⚡</div>
              <div class="stat-content">
                <div class="stat-value">{{ formatNumber(newFilesLoad) }}</div>
                <div class="stat-label">新增文件总负载</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">🔧</div>
              <div class="stat-content">
                <div class="stat-value">{{ newSymbolsCount }}</div>
                <div class="stat-label">新增符号数量</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">🚀</div>
              <div class="stat-content">
                <div class="stat-value">{{ formatNumber(newSymbolsLoad) }}</div>
                <div class="stat-label">新增符号总负载</div>
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 新增文件负载分析 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><DocumentAdd /></el-icon>
            <span class="analysis-tag new-files">新增文件负载分析</span>
          </h3>
          <div class="analysis-description">
            <p>显示在对比版本中新增的文件及其负载情况</p>
          </div>
          <PerfFileTable
            :step-id="currentStepIndex" 
            :data="increaseFilesPerformanceData" 
            :hide-column="true"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><FolderAdd /></el-icon>
            <span class="analysis-tag new-files-category">新增文件分类负载</span>
          </h3>
          <div class="analysis-description">
            <p>按分类显示新增文件的负载分布</p>
          </div>
          <PerfFileTable
            :step-id="currentStepIndex" 
            :data="increaseFilesPerformanceData1" 
            :hide-column="true"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <!-- 新增符号负载分析 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><CirclePlus /></el-icon>
            <span class="analysis-tag new-symbols">新增符号负载分析</span>
          </h3>
          <div class="analysis-description">
            <p>显示在对比版本中新增的函数符号及其负载</p>
          </div>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="increaseSymbolsPerformanceData" 
            :hide-column="true"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Plus /></el-icon>
            <span class="analysis-tag new-symbols-category">新增符号分类负载</span>
          </h3>
          <div class="analysis-description">
            <p>按分类显示新增符号的负载分布</p>
          </div>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="increaseSymbolsPerformanceData1" 
            :hide-column="true"
            :has-category="true" />
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
  DocumentAdd, FolderAdd, CirclePlus, Plus, DataAnalysis
} from '@element-plus/icons-vue';
import PerfFileTable from '../single-analysis/step/load/tables/PerfFileTable.vue';
import PerfSymbolTable from '../single-analysis/step/load/tables/PerfSymbolTable.vue';
import UploadHtml from '../common/UploadHtml.vue';
import { useJsonDataStore } from '../../stores/jsonDataStore';
import { 
  calculateFileData, 
  calculateFileData1, 
  calculateSymbolData, 
  calculateSymbolData1 
} from '@/utils/jsonUtil';

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

// testSteps 只从 jsonDataStore.steps 生成，与 perfData 解耦
const testSteps = computed(() => {
  const steps = jsonDataStore.steps || [];
  return steps.map((step, index) => ({
    id: step.step_id ?? (index + 1),
    step_name: step.step_name,
  }));
});

// 合并数据
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

// 工具函数：安全排序
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// 新增文件负载数据
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

// 新增符号负载数据
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

// 统计数据
const newFilesCount = computed(() => increaseFilesPerformanceData.value.length);
const newFilesLoad = computed(() => 
  increaseFilesPerformanceData.value.reduce((sum, item) => sum + item.instructions, 0)
);
const newSymbolsCount = computed(() => increaseSymbolsPerformanceData.value.length);
const newSymbolsLoad = computed(() => 
  increaseSymbolsPerformanceData.value.reduce((sum, item) => sum + item.instructions, 0)
);

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
.new-data-analysis {
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

.analysis-tag {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.analysis-tag.new-files {
  background: #e8f5e8;
  color: #2e7d32;
}

.analysis-tag.new-files-category {
  background: #e3f2fd;
  color: #1976d2;
}

.analysis-tag.new-symbols {
  background: #fff3e0;
  color: #f57c00;
}

.analysis-tag.new-symbols-category {
  background: #fce4ec;
  color: #c2185b;
}

.analysis-description {
  margin-bottom: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 4px solid #2196f3;
}

.analysis-description p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.stats-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-icon {
  font-size: 32px;
  opacity: 0.8;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
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
