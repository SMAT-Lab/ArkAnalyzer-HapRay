<template>
  <div class="perf-ui-animate">
    <el-card v-if="!hasData" shadow="never">
      <el-empty description="暂无 UI 动画分析数据" />
    </el-card>

    <template v-else>
      <!-- 当前步骤数据 -->
      <div v-if="currentStepData">
        <!-- 摘要信息 -->
        <el-card shadow="never" style="margin-bottom: 16px;">
          <template #header>
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span style="font-weight: 600; font-size: 16px;">
                <i class="el-icon-data-analysis" style="margin-right: 8px;"></i>
                动画分析摘要
              </span>
            </div>
          </template>

          <el-row :gutter="16">
            <el-col :span="6">
              <el-statistic title="总动画数" :value="summary.total_animations">
                <template #suffix>
                  <span style="font-size: 14px;">个</span>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="开始阶段动画" :value="summary.start_phase_animations">
                <template #suffix>
                  <span style="font-size: 14px;">个</span>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="结束阶段动画" :value="summary.end_phase_animations">
                <template #suffix>
                  <span style="font-size: 14px;">个</span>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="元素树变化" :value="summary.start_phase_tree_changes + summary.end_phase_tree_changes">
                <template #suffix>
                  <span style="font-size: 14px;">处</span>
                </template>
              </el-statistic>
            </el-col>
          </el-row>
        </el-card>

        <!-- 阶段选择 -->
        <el-tabs v-model="activePhase" type="border-card">
          <!-- 开始阶段 -->
          <el-tab-pane label="开始阶段 (Start Phase)" name="start">
            <PhaseAnalysis
              v-if="currentStepData.start_phase"
              :phase-data="currentStepData.start_phase"
              phase-name="开始阶段"
            />
          </el-tab-pane>

          <!-- 结束阶段 -->
          <el-tab-pane label="结束阶段 (End Phase)" name="end">
            <PhaseAnalysis
              v-if="currentStepData.end_phase"
              :phase-data="currentStepData.end_phase"
              phase-name="结束阶段"
            />
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 错误信息 -->
      <el-card v-else-if="hasError" shadow="never">
        <el-alert
          title="分析失败"
          type="error"
          :description="errorMessage"
          show-icon
          :closable="false"
        />
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useJsonDataStore, type UIAnimateStepData } from '../stores/jsonDataStore';
import PhaseAnalysis from './UIAnimatePhaseAnalysis.vue';

interface Props {
  stepId?: number;
}

const props = withDefaults(defineProps<Props>(), {
  stepId: 1,
});

const jsonDataStore = useJsonDataStore();
const uiAnimateData = computed(() => jsonDataStore.uiAnimateData);

// 检查是否有数据
const hasData = computed(() => {
  return uiAnimateData.value && Object.keys(uiAnimateData.value).length > 0;
});

// 根据 stepId 计算当前步骤的 key
const currentStepKey = computed(() => {
  return `step${props.stepId}`;
});

// 当前步骤数据
const currentStepData = computed((): UIAnimateStepData | null => {
  if (!uiAnimateData.value) return null;
  return uiAnimateData.value[currentStepKey.value] || null;
});

// 摘要信息
const summary = computed(() => {
  if (!currentStepData.value || !currentStepData.value.summary) {
    return {
      total_animations: 0,
      start_phase_animations: 0,
      end_phase_animations: 0,
      start_phase_tree_changes: 0,
      end_phase_tree_changes: 0,
      has_animations: false,
    };
  }
  return currentStepData.value.summary;
});

// 是否有错误
const hasError = computed(() => {
  return currentStepData.value && 'error' in currentStepData.value && currentStepData.value.error;
});

// 错误信息
const errorMessage = computed(() => {
  if (!hasError.value || !currentStepData.value) return '';
  return currentStepData.value.error || '';
});

// 当前激活的阶段
const activePhase = ref('start');
</script>

<style scoped>
.perf-ui-animate {
  padding: 16px;
}

:deep(.el-statistic__head) {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

:deep(.el-statistic__content) {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
</style>

