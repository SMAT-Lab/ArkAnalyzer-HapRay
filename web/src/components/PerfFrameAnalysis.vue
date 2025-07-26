<template>
  <div class="frame-analysis-container">
    <!-- 当前步骤信息卡片 -->
    <!-- <div v-if="currentStepInfo" class="step-info-card">
      <div class="step-header">
        <div class="step-badge">STEP {{ currentStepIndex }}</div>
        <div class="step-details">
          <h2 class="step-title">{{ currentStepInfo.step_name }}</h2>
          <div class="step-metrics">
            <div class="metric-item">
              <span class="metric-label">指令数：</span>
              <span class="metric-value">{{ formatDuration(currentStepInfo.count) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">功耗估算：</span>
              <span class="metric-value">{{ formatEnergy(currentStepInfo.count) }}</span>
            </div>
           <div class="metric-item">
              <span class="metric-label">轮次：</span>
              <span class="metric-value">{{ currentStepInfo.round }}</span>
            </div> 
          </div>
        </div>
      </div>
    </div> -->

    <!-- 帧分析组件 -->
    <FrameAnalysis :step="currentStepIndex" :data="frameData" />
  </div>
</template>

<script lang="ts" setup>
import { ref, watch } from 'vue';
import FrameAnalysis from './FrameAnalysis.vue';
import { useJsonDataStore } from '../stores/jsonDataStore.ts';
//import { calculateEnergyConsumption } from '@/utils/calculateUtil.ts';

// 定义props
const props = defineProps<{
  step?: number;
}>();

// 获取存储实例
const jsonDataStore = useJsonDataStore();
//const perfData = jsonDataStore.perfData;
const frameData = jsonDataStore.frameData;

console.log('帧分析组件获取到的 JSON 数据:', props.step);

// const testSteps = ref(
//   perfData!.steps.map((step, index) => ({
//     id: index + 1,
//     step_name: step.step_name,
//     count: step.count,
//     round: step.round,
//     perf_data_path: step.perf_data_path,
//   }))
// );

// interface TestStep {
//   id: number;
//   step_name: string;
//   count: number;
//   round: number;
//   perf_data_path: string;
// }

// 当前步骤索引，如果传入了step参数则使用，否则默认为1
const currentStepIndex = ref(props.step || 1);

// 当前步骤信息
// const currentStepInfo = computed(() => {
//   return testSteps.value.find(step => step.id === currentStepIndex.value);
// });

// 监听props.step变化
watch(() => props.step, (newStep) => {
  if (newStep) {
    currentStepIndex.value = newStep;
  }
}, { immediate: true });

// // 格式化持续时间的方法
// const formatDuration = (milliseconds: number) => {
//   return `指令数：${milliseconds}`;
// };

// // 格式化功耗信息
// const formatEnergy = (milliseconds: number) => {
//   const energy = calculateEnergyConsumption(milliseconds);
//   return `核算功耗（mAs）：${energy}`;
// };


</script>

<style scoped>
.frame-analysis-container {
  padding: 20px;
  background: #f5f7fa;
}

/* 步骤信息卡片样式 */
.step-info-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 24px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 24px;
}

.step-badge {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 20px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 16px;
  min-width: 100px;
  text-align: center;
}

.step-details {
  flex: 1;
}

.step-title {
  margin: 0 0 12px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.step-metrics {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-label {
  color: #606266;
  font-size: 14px;
}

.metric-value {
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .frame-analysis-container {
    padding: 16px;
  }

  .step-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .step-metrics {
    flex-direction: column;
    gap: 12px;
  }
}

@media (max-width: 480px) {
  .step-info-card {
    padding: 16px;
  }

  .step-title {
    font-size: 20px;
  }

  .step-badge {
    padding: 8px 16px;
    font-size: 14px;
  }
}
</style>
