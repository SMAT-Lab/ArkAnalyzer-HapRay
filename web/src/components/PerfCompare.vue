<template>
  <div class="performance-comparison">
    <!-- 测试步骤导航 -->
    <div class="step-nav">
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
          <span class="step-order">STEP {{ step.id + 1 }}</span>
          <span class="step-duration">{{ formatDuration(step.baseDuration) }}</span>
          <span class="step-duration-compare">{{ formatDuration(step.compareDuration) }}</span>
        </div>
        <div class="step-name">{{ step.name }}</div>
      </div>
    </div>

    <!-- 性能对比区域 -->
    <div class="comparison-container">
      <!-- 基准版本 -->
      <div class="data-panel">
        <h3 class="panel-title">
          <span class="version-tag">Base</span>
          {{ performanceData.base.version }}
        </h3>
        <PerfTable
          :stepId="currentStepIndex"
          :data="performanceData.base.instructions"
          @custom-event="handleCustomEvent"
        />
      </div>

      <!-- 对比指示器 -->
      <div class="indicator">
        <div class="diff-box" :style="diffStyle">
          <div class="diff-value">{{ instructionsDiff }}%</div>
          <div class="diff-label">指令数差异</div>
        </div>
      </div>

      <!-- 对比版本 -->
      <div class="data-panel">
        <h3 class="panel-title">
          <span class="version-tag">Compare</span>
          {{ performanceData.compare.version }}
        </h3>
        <PerfTable
          :stepId="currentStepIndex"
          :data="performanceData.compare.instructions"
          @custom-event="handleCustomEvent"
        />
      </div>
    </div>

    <el-dialog v-model="symbolDialogVisible" :title="selectedFile" width="100%">
      <div class="comparison-container">
        <!-- 基准版本 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">Base</span>
            {{ performanceData.base.version }}
          </h3>
          <PerfSymbolTable :data="symbolData.base.instructions" />
        </div>

        <!-- 对比指示器 -->
        <div class="indicator">
          <div class="diff-box" :style="diffStyle">
            <div class="diff-value">{{ fileDiff }}%</div>
            <div class="diff-label">指令数差异</div>
          </div>
        </div>

        <!-- 对比版本 -->
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">Compare</span>
            {{ performanceData.compare.version }}
          </h3>
          <PerfSymbolTable :data="symbolData.compare.instructions" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import { Timer } from '@element-plus/icons-vue';
import PerfTable from './PerfTable.vue';
import PerfSymbolTable from './PerfSymbolTable.vue';
import { getCurrentInstance } from 'vue';

const vscode = getCurrentInstance()!.appContext.config.globalProperties.$vscode;

interface TestStep {
  id: number;
  name: string;
  baseDuration: number;
  compareDuration: number;
}

interface Instruction {
  name: string;
  instructions: number;
}

let testSteps = ref<Array<TestStep>>([]);

const performanceData = ref({
  base: {
    version: '',
    instructions: [],
  },
  compare: {
    version: '',
    instructions: [],
  },
});

const symbolData = ref({
  base: {
    version: '',
    instructions: [],
  },
  compare: {
    version: '',
    instructions: [],
  },
});
const currentStepIndex = ref(-1);
const symbolDialogVisible = ref(false);
const selectedFile = ref('');

// 指令数差异计算
const instructionsDiff = computed(() => {
  const baseTotal = performanceData.value.base.instructions.reduce(
    (sum: number, item: Instruction) => sum + item.instructions,
    0
  );
  const compareTotal = performanceData.value.compare.instructions.reduce(
    (sum: number, item: Instruction) => sum + item.instructions,
    0
  );
  return Number((((compareTotal - baseTotal) / baseTotal) * 100).toFixed(2));
});

const fileDiff = computed(() => {
  const baseTotal = symbolData.value.base.instructions.reduce(
    (sum: number, item: Instruction) => sum + item.instructions,
    0
  );
  const compareTotal = symbolData.value.compare.instructions.reduce(
    (sum: number, item: Instruction) => sum + item.instructions,
    0
  );
  return Number((((compareTotal - baseTotal) / baseTotal) * 100).toFixed(2));
});

const diffStyle = computed(() => ({
  backgroundColor: instructionsDiff.value < 0 ? '#e8f5e9' : '#ffebee',
  borderColor: instructionsDiff.value < 0 ? '#4caf50' : '#ef5350',
}));

// 格式化工时显示
const formatDuration = (ns: number) => {
  let ms = ns / 1000000;
  return `${(ms / 1000).toFixed(2)}s`;
};

// 步骤点击处理
const handleStepClick = (index: number) => {
  currentStepIndex.value = index;
  getData(index);
};

window.addEventListener('message', (event) => {
  const message = event.data;
  console.log(message);

  switch (message.command) {
    case '/api/v1/perf/steps':
      testSteps.value = message.data;
      break;

    case '/api/v1/perf/compare':
      performanceData.value = message.data;
      break;

    case '/api/v1/perf/compare_file':
      symbolData.value = message.data;
      symbolDialogVisible.value = true;
      break;
  }
});

const getData = (stepId: number) => {
  console.log(stepId);
  vscode.postMessage({
    command: '/api/v1/perf/compare',
    query: { stepId: stepId },
  });
};

onMounted(() => {
  vscode.postMessage({ command: '/api/v1/perf/steps' });
  getData(-1);
});

const handleCustomEvent = (data: string) => {
  selectedFile.value = data;
  vscode.postMessage({
    command: '/api/v1/perf/compare_file',
    query: { stepId: currentStepIndex.value, file: data },
  });
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
</style>
