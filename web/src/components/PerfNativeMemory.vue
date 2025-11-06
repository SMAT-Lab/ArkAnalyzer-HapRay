<template>
  <div class="native-memory-container">
    <!-- 无数据提示 -->
    <div v-if="!hasData" class="no-data-tip">
      <el-empty description="暂无内存分析数据" />
    </div>

    <!-- 内存数据展示（仅当有数据时显示） -->
    <template v-if="hasData">
    <!-- 内存时间线图表 -->
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="data-panel">
          <h3 class="panel-title">
            <span class="version-tag">内存时间线</span>
          </h3>
          <MemoryTimelineChart
            :records="currentStepRecords"
            :callchains="currentStepCallchains"
            :selected-time-point="selectedTimePoint"
            height="600px"
            @time-point-selected="handleTimePointSelected"
          />
        </div>
      </el-col>
    </el-row>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';
import MemoryTimelineChart from './MemoryTimelineChart.vue';
import { useJsonDataStore } from '../stores/jsonDataStore.ts';

// Props
const props = defineProps<{
  stepId: number;
}>();

// 获取存储实例
const jsonDataStore = useJsonDataStore();
const nativeMemoryData = jsonDataStore.nativeMemoryData;

// 检查是否有数据
const hasData = computed(() => {
  if (!nativeMemoryData) return false;
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  return stepData && stepData.records && stepData.records.length > 0;
});

// 获取当前步骤的所有记录
const currentStepRecords = computed(() => {
  if (!nativeMemoryData) return [];
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  return stepData?.records || [];
});

// 获取当前步骤的调用链数据
const currentStepCallchains = computed(() => {
  if (!nativeMemoryData) return undefined;
  const stepKey = `step${props.stepId}`;
  const stepData = nativeMemoryData[stepKey];
  return stepData?.callchains;
});

// 时间点选择
const selectedTimePoint = ref<number | null>(null);

// 处理时间点选择
function handleTimePointSelected(timePoint: number | null) {
  selectedTimePoint.value = timePoint;
}
</script>

<style scoped>
.native-memory-container {
  padding: 20px;
}

.data-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.panel-title {
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.no-data-tip {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}
</style>
