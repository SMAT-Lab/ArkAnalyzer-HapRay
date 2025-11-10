<template>
  <div class="native-memory-container">
    <div v-if="!hasData" class="no-data-tip">
      <el-empty description="暂无内存分析数据" />
    </div>

    <template v-else>
      <el-row v-if="selectedTimePoint !== null" :gutter="20" class="time-point-info-panel">
        <el-col :span="24">
          <el-alert type="info" :closable="false" show-icon>
            <template #title>
              <div class="time-point-info-content">
                <div class="time-point-info-meta">
                  <span class="time-point-info-label">
                    <i class="el-icon-time time-point-info-icon"></i>
                    已选中时间点
                  </span>
                  <span>
                    <strong>时间:</strong> {{ formatTime(selectedTimePoint) }}
                  </span>
                  <span>
                    <strong>当前内存:</strong> {{ formatBytes(pointContext.memoryAtPoint || selectedTimePointMemory) }}
                  </span>
                  <span v-if="pointContext.seriesName">
                    <strong>选中系列:</strong> {{ pointContext.seriesName }}
                  </span>
                  <template v-if="drillState.viewMode === 'category'">
                    <span v-if="drillState.selectedCategory">
                      <strong>大类:</strong> {{ drillState.selectedCategory }}
                    </span>
                    <span v-if="drillState.selectedSubCategory">
                      <strong>小类:</strong> {{ drillState.selectedSubCategory }}
                    </span>
                    <span v-if="drillState.selectedFile">
                      <strong>文件:</strong> {{ drillState.selectedFile }}
                    </span>
                  </template>
                  <template v-else>
                    <span v-if="drillState.selectedProcess">
                      <strong>进程:</strong> {{ drillState.selectedProcess }}
                    </span>
                    <span v-if="drillState.selectedThread">
                      <strong>线程:</strong> {{ drillState.selectedThread }}
                    </span>
                    <span v-if="drillState.selectedFile">
                      <strong>文件:</strong> {{ drillState.selectedFile }}
                    </span>
                  </template>
            
                </div>
                <el-button
                  type="danger"
                  size="small"
                  class="time-point-clear-button"
                  @click="clearTimePointSelection"
                >
                  清除选择
                </el-button>
              </div>
            </template>
          </el-alert>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <span class="version-tag">内存时间线</span>
              <span v-if="selectedTimePoint !== null" class="panel-tip">
                <i class="el-icon-info"></i>
                点击图表上的点可选择时间点，所有数据将自动过滤到该时间点
              </span>
            </h3>
            <MemoryTimelineChart
              :step-id="props.stepId"
              :selected-time-point="selectedTimePoint"
              :height="TIMELINE_CHART_HEIGHT"
              @time-point-selected="handleTimePointSelected"
              @time-point-stats-updated="handleTimePointStatsUpdated"
              @drill-state-change="handleDrillStateChange"
              @point-selection-context="handlePointSelectionContext"
            />
          </div>
        </el-col>
      </el-row>

      <el-row v-if="shouldShowOutstandingFlameGraph" :gutter="20">
        <el-col :span="24">
          <MemoryOutstandingFlameGraph
            :step-id="props.stepId"
            :selected-time-point="selectedTimePoint"
            :drill-level="drillState.drillLevel"
            :view-mode="drillState.viewMode"
            :selected-category="drillState.selectedCategory"
            :selected-sub-category="drillState.selectedSubCategory"
            :selected-process="drillState.selectedProcess"
            :selected-thread="drillState.selectedThread"
            :selected-file="drillState.selectedFile"
            :selected-series-name="pointContext.seriesName"
          />
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, ref, watch } from 'vue';
import MemoryTimelineChart from './MemoryTimelineChart.vue';
import MemoryOutstandingFlameGraph from './MemoryOutstandingFlameGraph.vue';
import { loadNativeMemoryMetadataFromDb } from '@/stores/nativeMemory';
import type { NativeMemoryStepData } from '@/stores/nativeMemory';

const TIMELINE_CHART_HEIGHT = '350px';
const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

type DrillDownLevel = 'overview' | 'category' | 'subCategory' | 'process' | 'thread' | 'file';
type ViewMode = 'category' | 'process';

interface TimePointStats {
  eventCount: number;
  allocCount: number;
  freeCount: number;
  netMemory: number;
}

const props = defineProps<{ stepId: number }>();

const nativeMemoryData = ref<NativeMemoryStepData | null>(null);
const isNativeMemoryLoading = ref(false);

const selectedTimePoint = ref<number | null>(null);

const stepData = computed(() => nativeMemoryData.value);
const hasData = computed(() => Boolean(stepData.value));

const selectedTimePointStats = ref<TimePointStats>(createEmptyTimePointStats());

const selectedTimePointMemory = computed(() => selectedTimePointStats.value.netMemory);

interface DrillState {
  drillLevel: DrillDownLevel;
  viewMode: ViewMode;
  selectedCategory: string;
  selectedSubCategory: string;
  selectedProcess: string;
  selectedThread: string;
  selectedFile: string;
}

const DEFAULT_DRILL_STATE: DrillState = Object.freeze({
  drillLevel: 'overview' as DrillDownLevel,
  viewMode: 'category' as ViewMode,
  selectedCategory: '',
  selectedSubCategory: '',
  selectedProcess: '',
  selectedThread: '',
  selectedFile: '',
});

const drillState = ref<DrillState>({ ...DEFAULT_DRILL_STATE });

const shouldShowOutstandingFlameGraph = computed(
  () =>
    drillState.value.drillLevel !== 'overview' &&
    selectedTimePoint.value !== null,
);

// 选中点上下文（来自时间线图表），用于信息栏与火焰图筛选
const pointContext = ref<{
  timePoint: number | null;
  seriesName: string;
  viewMode: ViewMode;
  drillLevel: DrillDownLevel;
  selectedCategory: string;
  selectedSubCategory: string;
  selectedProcess: string;
  selectedThread: string;
  selectedFile: string;
  memoryAtPoint: number;
}>({
  timePoint: null,
  seriesName: '',
  viewMode: 'category',
  drillLevel: 'overview',
  selectedCategory: '',
  selectedSubCategory: '',
  selectedProcess: '',
  selectedThread: '',
  selectedFile: '',
  memoryAtPoint: 0,
});

onMounted(() => {
  void ensureNativeMemoryDataLoaded();
});

watch(
  () => props.stepId,
  () => {
    selectedTimePoint.value = null;
    selectedTimePointStats.value = createEmptyTimePointStats();
    resetDrillState();
    nativeMemoryData.value = null;
    void ensureNativeMemoryDataLoaded();
  }
);

async function ensureNativeMemoryDataLoaded() {
  if (nativeMemoryData.value || isNativeMemoryLoading.value) return;
  try {
    isNativeMemoryLoading.value = true;
    nativeMemoryData.value = await loadNativeMemoryMetadataFromDb(props.stepId);
  } catch (error) {
    nativeMemoryData.value = null;
    console.error('[NativeMemory] Failed to load native memory metadata:', error);
  } finally {
    isNativeMemoryLoading.value = false;
  }
}

function handleTimePointSelected(timePoint: number | null) {
  selectedTimePoint.value = timePoint;
  if (timePoint === null) {
    selectedTimePointStats.value = createEmptyTimePointStats();
    pointContext.value = {
      timePoint: null,
      seriesName: '',
      viewMode: 'category',
      drillLevel: 'overview',
      selectedCategory: '',
      selectedSubCategory: '',
      selectedProcess: '',
      selectedThread: '',
      selectedFile: '',
      memoryAtPoint: 0,
    };
  }
}

function handleTimePointStatsUpdated(stats: TimePointStats) {
  selectedTimePointStats.value = stats;
}

function handleDrillStateChange(state: DrillState) {
  drillState.value = { ...DEFAULT_DRILL_STATE, ...state };
}

function handlePointSelectionContext(ctx: typeof pointContext.value) {
  pointContext.value = { ...ctx };
}

function clearTimePointSelection() {
  selectedTimePoint.value = null;
  selectedTimePointStats.value = createEmptyTimePointStats();
  pointContext.value = {
    timePoint: null,
    seriesName: '',
    viewMode: 'category',
    drillLevel: 'overview',
    selectedCategory: '',
    selectedSubCategory: '',
    selectedProcess: '',
    selectedThread: '',
    selectedFile: '',
    memoryAtPoint: 0,
  };
}

function createEmptyTimePointStats(): TimePointStats {
  return {
    eventCount: 0,
    allocCount: 0,
    freeCount: 0,
    netMemory: 0,
  };
}

function resetDrillState() {
  drillState.value = { ...DEFAULT_DRILL_STATE };
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const absoluteBytes = Math.abs(bytes);
  const unitIndex = Math.min(
    Math.floor(Math.log(absoluteBytes) / Math.log(1024)),
    BYTE_UNITS.length - 1
  );
  const formattedValue = (absoluteBytes / Math.pow(1024, unitIndex)).toFixed(2);
  const sign = bytes < 0 ? '-' : '';

  return `${sign}${formattedValue} ${BYTE_UNITS[unitIndex]}`;
}

function formatTime(seconds: number): string {
  return `${seconds.toFixed(2)} s`;
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
  margin: 0 0 15px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 14px;
}

.panel-tip {
  margin-left: 10px;
  color: #ff6b00;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.time-point-info-panel {
  margin-bottom: 20px;
}

.time-point-info-panel .el-alert {
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(255, 107, 0, 0.15);
}

.time-point-info-panel .el-alert__title {
  width: 100%;
}

.time-point-info-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.time-point-info-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.time-point-info-label {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
}

.time-point-info-icon {
  margin-right: 5px;
}

.time-point-clear-button {
  flex-shrink: 0;
}
</style>
