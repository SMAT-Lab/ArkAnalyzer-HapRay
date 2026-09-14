<template>
  <div class="thermal-step-container">
    <div v-if="!thermalStepData" class="no-data-tip">
      <el-empty description="暂无温度分析数据" />
    </div>

    <template v-else>
      <el-row :gutter="20">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <span class="version-tag">温度变化曲线</span>
              <span class="panel-tip">
                采样 {{ thermalStepData.sample_count }} 次，间隔约 {{ thermalStepData.interval_seconds }}s，
                采集时长 {{ formatDuration(thermalStepData.duration_s) }}
              </span>
            </h3>
            <div ref="chartRef" class="thermal-chart"></div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="24">
          <div class="data-panel">
            <h3 class="panel-title">
              <span class="version-tag">温度统计</span>
              <span class="panel-tip">温升 = 结束温度 - 起始温度（按步骤采集时段计算）</span>
            </h3>
            <el-table :data="statsRows" style="width: 100%" :default-sort="{ prop: 'rise', order: 'descending' }">
              <el-table-column prop="sensor" label="传感器" min-width="140" />
              <el-table-column prop="start" label="起始 (°C)" width="110" />
              <el-table-column prop="end" label="结束 (°C)" width="110" />
              <el-table-column prop="max" label="最高 (°C)" width="110" />
              <el-table-column prop="min" label="最低 (°C)" width="110" />
              <el-table-column prop="avg" label="平均 (°C)" width="110" />
              <el-table-column prop="rise" label="温升 (°C)" width="110" sortable>
                <template #default="scope">
                  <span :class="riseClass(scope.row.rise)">+{{ scope.row.rise.toFixed(2) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { useJsonDataStore } from '@/stores/jsonDataStore.ts';

const props = defineProps<{
  stepId: number;
}>();

const jsonDataStore = useJsonDataStore();
const chartRef = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;

const thermalStepData = computed(() => {
  return jsonDataStore.thermalData?.[`step${props.stepId}`] ?? null;
});

const statsRows = computed(() => {
  const data = thermalStepData.value;
  if (!data) return [];
  return Object.entries(data.statistics || {}).map(([sensor, stats]) => ({
    sensor,
    start: stats.start,
    end: stats.end,
    max: stats.max,
    min: stats.min,
    avg: stats.avg,
    rise: stats.rise,
  }));
});

function riseClass(rise: number): string {
  if (rise >= 5) return 'rise-high';
  if (rise >= 2) return 'rise-medium';
  return 'rise-low';
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '0s';
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m${s}s` : `${m}m`;
}

function renderChart() {
  if (!chartRef.value || !thermalStepData.value) return;

  if (!chart) {
    chart = echarts.init(chartRef.value);
  }

  const seriesData = thermalStepData.value.series;
  const elapsed = seriesData.elapsed_s || [];
  const wallTime = seriesData.wall_time || [];
  const xLabels = elapsed.map((s) => `${s}s`);

  const series = Object.entries(seriesData.sensors || {}).map(([name, data]) => ({
    name,
    type: 'line' as const,
    data,
    smooth: true,
    connectNulls: true,
    symbolSize: 4,
    emphasis: { focus: 'series' as const },
  }));

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter(params: unknown) {
        const list = params as { dataIndex: number; color: string; seriesName: string; value: number | null }[];
        if (!Array.isArray(list) || list.length === 0) return '';
        const dataIndex = list[0].dataIndex;
        let html = `<div style="font-weight: bold; margin-bottom: 8px; color: #333;">${xLabels[dataIndex] ?? ''}`;
        if (wallTime[dataIndex]) {
          html += `（${wallTime[dataIndex]}）`;
        }
        html += '</div>';
        list.forEach((param) => {
          const value = param.value === null || param.value === undefined ? '-' : `${param.value.toFixed(2)} °C`;
          html += `<div style="margin: 4px 0;">
            <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 8px; border-radius: 50%;"></span>
            ${param.seriesName}: <strong>${value}</strong>
          </div>`;
        });
        return html;
      },
    },
    legend: {
      type: 'scroll',
      left: 'center',
      top: 10,
    },
    grid: {
      left: 60,
      right: 40,
      top: 60,
      bottom: 50,
    },
    xAxis: {
      type: 'category',
      data: xLabels,
      name: '时间',
      axisLabel: {
        color: '#666',
        hideOverlap: true,
      },
      axisLine: { lineStyle: { color: '#e0e0e0' } },
    },
    yAxis: {
      type: 'value',
      name: '温度 (°C)',
      scale: true,
      axisLabel: { color: '#666' },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8 },
    ],
    series,
  });
}

function handleResize() {
  chart?.resize();
}

onMounted(async () => {
  await nextTick();
  renderChart();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  if (chart) {
    chart.dispose();
    chart = null;
  }
});

watch(
  () => thermalStepData.value,
  () => {
    nextTick(() => renderChart());
  },
  { deep: true }
);
</script>

<style scoped>
.thermal-step-container {
  padding: 0;
}

.no-data-tip {
  padding: 60px 0;
}

.data-panel {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.version-tag {
  background: #409eff;
  color: #fff;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 4px;
  font-weight: normal;
}

.panel-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.thermal-chart {
  width: 100%;
  height: 420px;
}

.rise-high {
  color: #f56c6c;
  font-weight: 600;
}

.rise-medium {
  color: #e6a23c;
  font-weight: 600;
}

.rise-low {
  color: #67c23a;
}
</style>
