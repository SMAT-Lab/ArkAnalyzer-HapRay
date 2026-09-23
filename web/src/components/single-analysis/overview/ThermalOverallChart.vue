<template>
  <div v-if="hasThermalData" class="thermal-overall-panel">
    <div class="data-panel">
      <h3 class="panel-title">
        <span class="version-tag">温度总览</span>
        <span class="panel-tip">所有步骤连续采样的温度曲线，背景色块为步骤区间，点击图例可切换传感器</span>
      </h3>
      <div ref="chartRef" class="thermal-overall-chart"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { useJsonDataStore } from '@/stores/jsonDataStore.ts';
import type { ThermalStepData } from '@/stores/jsonDataStore.ts';

const jsonDataStore = useJsonDataStore();
const chartRef = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;

/** 步骤名映射（step1 -> 步骤名） */
const stepNameMap = computed(() => {
  const map: Record<string, string> = {};
  const steps = jsonDataStore.steps || [];
  steps.forEach((step) => {
    map[`step${step.step_id}`] = step.step_name;
  });
  return map;
});

interface StepRange {
  key: string;
  name: string;
  start: number;
  end: number;
}

/** 拼接后的绘图数据 */
const chartData = computed(() => {
  const thermal = jsonDataStore.thermalData;
  const steps = jsonDataStore.steps || [];
  if (!thermal) return null;

  const ranges: StepRange[] = [];
  const points: Array<{ x: number; values: Record<string, number | null> }> = [];
  const sensorNames: string[] = [];
  const seenSensors = new Set<string>();
  let offset = 0;

  for (const step of steps) {
    const key = `step${step.step_id}`;
    const data: ThermalStepData | undefined = thermal[key];
    if (!data?.series || !data.series.elapsed_s?.length) continue;

    const elapsed = data.series.elapsed_s;
    const sensors = data.series.sensors || {};

    for (const name of Object.keys(sensors)) {
      if (!seenSensors.has(name)) {
        seenSensors.add(name);
        sensorNames.push(name);
      }
    }

    for (let i = 0; i < elapsed.length; i++) {
      const values: Record<string, number | null> = {};
      for (const name of sensorNames) {
        values[name] = sensors[name]?.[i] ?? null;
      }
      points.push({ x: offset + elapsed[i], values });
    }

    const start = offset;
    offset += elapsed[elapsed.length - 1] || 0;
    ranges.push({
      key,
      name: stepNameMap.value[key] || `步骤${step.step_id}`,
      start,
      end: offset,
    });
  }

  if (!points.length) return null;
  return { ranges, points, sensorNames };
});

const hasThermalData = computed(() => !!chartData.value);

function renderChart() {
  if (!chartRef.value || !chartData.value) return;

  if (!chart) {
    chart = echarts.init(chartRef.value);
  }

  const { ranges, points, sensorNames } = chartData.value;

  const series: Array<echarts.SeriesOption> = sensorNames.map((name) => ({
    name,
    type: 'line',
    data: points.map((p) => [p.x, p.values[name]]),
    smooth: true,
    connectNulls: true,
    symbolSize: 3,
    emphasis: { focus: 'series' },
    // 第一个系列上标注步骤区间背景
    markArea:
      name === sensorNames[0]
        ? {
            silent: true,
            itemStyle: { color: 'rgba(64, 158, 255, 0.05)' },
            label: { position: 'insideTop', color: '#909399', fontSize: 11 },
            data: ranges.map((r) => [
              { xAxis: r.start, name: `步骤${r.key.replace('step', '')}: ${r.name}` },
              { xAxis: r.end },
            ]),
          }
        : undefined,
  }));

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: unknown) => (value == null ? '-' : `${Number(value).toFixed(2)} °C`),
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
      bottom: 45,
    },
    xAxis: {
      type: 'value',
      name: '累计时间 (s)',
      axisLabel: { color: '#666' },
      splitLine: { show: false },
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
  () => chartData.value,
  () => {
    nextTick(() => renderChart());
  },
  { deep: true }
);
</script>

<style scoped>
.thermal-overall-panel {
  margin-bottom: 20px;
}

.data-panel {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
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

.thermal-overall-chart {
  width: 100%;
  height: 420px;
}
</style>
