<template>
  <div class="page-canvas-trend">
    <div ref="chartRef" style="width: 100%; height: 320px;"></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import type { UIPageTreePageStat } from '@/stores/jsonDataStore';

interface Props {
  stats: UIPageTreePageStat[];
}

const props = defineProps<Props>();

const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const buildOption = () => {
  const stats = props.stats || [];
  const xAxisData = stats.map((item) => `Page${item.pageIdx}`);
  const fullLabels = stats.map(
    (item) =>
      `Page${item.pageIdx}` +
      (item.description ? ` - ${item.description}` : ''),
  );
  const yData = stats.map((item) => item.canvasNodeCount ?? 0);

  return {
    title: {
      text: '页面 CanvasNode 数量变化',
      left: 'left',
      textStyle: { fontSize: 14 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
      },
      formatter(params: any) {
        const p = Array.isArray(params) ? params[0] : params;
        const idx = p.dataIndex ?? 0;
        const label = fullLabels[idx] || '';
        return `<div style="font-weight: 500; margin-bottom: 6px;">${label}</div>
                <div>CanvasNode 数量: <strong>${p.data}</strong></div>`;
      },
    },
    grid: {
      left: 40,
      right: 20,
      top: 50,
      bottom: 40,
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLabel: {
        interval: 0,
        fontSize: 10,
      },
    },
    yAxis: {
      type: 'value',
      name: 'CanvasNode 数量',
    },
    series: [
      {
        name: 'CanvasNode 数量',
        type: 'line',
        smooth: true,
        data: yData,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 2,
        },
        areaStyle: {
          opacity: 0.1,
        },
      },
    ],
  } as echarts.EChartsOption;
};

const renderChart = () => {
  if (!chartRef.value) return;
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }
  const option = buildOption();
  chartInstance.setOption(option, true);
};

onMounted(() => {
  renderChart();
  const resizeHandler = () => {
    chartInstance?.resize();
  };
  window.addEventListener('resize', resizeHandler);
  (chartInstance as any).__resizeHandler = resizeHandler;
});

watch(
  () => props.stats,
  () => {
    if (chartInstance) {
      renderChart();
    }
  },
  { deep: true },
);

onBeforeUnmount(() => {
  if (chartInstance) {
    const handler = (chartInstance as any).__resizeHandler as
      | (() => void)
      | undefined;
    if (handler) {
      window.removeEventListener('resize', handler);
    }
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.page-canvas-trend {
  width: 100%;
}
</style>


