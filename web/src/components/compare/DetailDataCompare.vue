<template>
  <div class="detail-data-compare">
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

    <!-- 进程负载对比 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Monitor /></el-icon>
            <span class="version-tag baseline">基线版本进程负载</span>
          </h3>
          <PerfProcessTable
            :step-id="currentStepIndex" 
            :data="filteredProcessesPerformanceData" 
            :hide-column="false"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><DataBoard /></el-icon>
            <span class="version-tag compare">对比版本大分类负载</span>
          </h3>
          <PerfProcessTable
            :step-id="currentStepIndex" 
            :data="filteredCategorysPerformanceData" 
            :hide-column="false"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <!-- 线程负载对比 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Connection /></el-icon>
            <span class="version-tag baseline">基线版本线程负载</span>
          </h3>
          <PerfThreadTable
            :step-id="currentStepIndex" 
            :data="filteredThreadsPerformanceData" 
            :hide-column="false"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Grid /></el-icon>
            <span class="version-tag compare">对比版本小分类负载</span>
          </h3>
          <PerfThreadTable
            :step-id="currentStepIndex" 
            :data="filteredComponentNamePerformanceData"
            :hide-column="false" 
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <!-- 文件负载对比 -->
    <el-row :gutter="20" style="margin-bottom: 20px;">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Document /></el-icon>
            <span class="version-tag baseline">基线版本文件负载</span>
          </h3>
          <PerfFileTable
            :step-id="currentStepIndex" 
            :data="filteredFilesPerformanceData" 
            :hide-column="false"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><FolderOpened /></el-icon>
            <span class="version-tag compare">对比版本文件负载</span>
          </h3>
          <PerfFileTable
            :step-id="currentStepIndex" 
            :data="filteredFilesPerformanceData1" 
            :hide-column="false"
            :has-category="true" />
        </div>
      </el-col>
    </el-row>

    <!-- 函数负载对比 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><Operation /></el-icon>
            <span class="version-tag baseline">基线版本函数负载</span>
          </h3>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="filteredSymbolsPerformanceData" 
            :hide-column="false"
            :has-category="false" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="data-panel">
          <h3 class="panel-title">
            <el-icon><SetUp /></el-icon>
            <span class="version-tag compare">对比版本函数负载</span>
          </h3>
          <PerfSymbolTable
            :step-id="currentStepIndex" 
            :data="filteredSymbolsPerformanceData1" 
            :hide-column="false" 
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
  Monitor, DataBoard, Connection, Grid,
  Document, FolderOpened, Operation, SetUp
} from '@element-plus/icons-vue';
import PerfProcessTable from '../single-analysis/step/load/tables/PerfProcessTable.vue';
import PerfThreadTable from '../single-analysis/step/load/tables/PerfThreadTable.vue';
import PerfFileTable from '../single-analysis/step/load/tables/PerfFileTable.vue';
import PerfSymbolTable from '../single-analysis/step/load/tables/PerfSymbolTable.vue';
import UploadHtml from '../common/UploadHtml.vue';
import { useJsonDataStore } from '../../stores/jsonDataStore';
import { 
  calculateProcessData, 
  calculateThreadData, 
  calculateCategorysData, 
  calculateComponentNameData, 
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

// 合并数据
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

// 工具函数：安全排序
function sortByInstructions<T extends { instructions: number }>(arr: T[]): T[] {
  return [...arr].sort((a, b) => b.instructions - a.instructions);
}

// 过滤数据
const filteredProcessesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedProcessPerformanceData.value);
  }
  return sortByInstructions(
    mergedProcessPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredThreadsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedThreadPerformanceData.value);
  }
  return sortByInstructions(
    mergedThreadPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredCategorysPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedCategorysPerformanceData.value);
  }
  return sortByInstructions(
    mergedCategorysPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
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

const filteredFilesPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedFilePerformanceData.value);
  }
  return sortByInstructions(
    mergedFilePerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredFilesPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedFilePerformanceData1.value);
  }
  return sortByInstructions(
    mergedFilePerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredSymbolsPerformanceData = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedSymbolsPerformanceData.value);
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});

const filteredSymbolsPerformanceData1 = computed(() => {
  if (currentStepIndex.value === 0) {
    return sortByInstructions(mergedSymbolsPerformanceData1.value);
  }
  return sortByInstructions(
    mergedSymbolsPerformanceData1.value.filter((item) => item.stepId === currentStepIndex.value)
  );
});
</script>

<style scoped>
.detail-data-compare {
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
