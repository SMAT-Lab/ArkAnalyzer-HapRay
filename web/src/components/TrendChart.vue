<template>
  <div ref="chartRef" style="width: 100%; height: 400px"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import type { PropType } from 'vue';
import * as echarts from 'echarts';

interface TrendChartData {
  xAxis: string[];
  series: Array<{
    name: string;
    data: number[];
  }>;
}

const props = defineProps({
  chartData: {
    type: Object as PropType<TrendChartData>,
    required: true,
  },
  title: {
    type: String,
    default: '趋势图'
  },
  seriesType: {
    type: String,
    default: 'line'
  }
});

const chartRef = ref<HTMLElement | null>(null);
let myChart: echarts.ECharts | null = null;

// 更新图表函数
const updateChart = () => {
  if (!myChart || !chartRef.value || !props.chartData) return;

  const option = {
    title: {
      text: props.title,
      left: 'left',
      textStyle: { fontSize: 16 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#999',
        },
      },
    },
    legend: {
      type: 'scroll',
      left: 'center',
      top: 20,
      data: props.chartData.series.map(s => s.name),
    },
    xAxis: {
      type: 'category',
      data: props.chartData.xAxis,
      axisLabel: {
        rotate: 45,
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
    },
    series: props.chartData.series.map(s => ({
      name: s.name,
      type: props.seriesType,
      data: s.data,
      smooth: true
    })),
  };

  myChart.setOption(option);
};

// 初始化图表
onMounted(() => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value);
    updateChart();

    // 响应窗口变化
    const resizeHandler = () => {
      myChart?.resize();
    };

    window.addEventListener('resize', resizeHandler);

    // 保存引用以便正确移除监听器
    (myChart as unknown as { __resizeHandler?: () => void }).__resizeHandler = resizeHandler;
  }
});

// 监听数据变化
watch(
  () => props.chartData,
  () => {
    updateChart();
  },
  { deep: true }
);

// 清理资源
onBeforeUnmount(() => {
  if (myChart) {
    // 获取并移除resize监听器
    const resizeHandler = (myChart as unknown as { __resizeHandler?: () => void }).__resizeHandler;
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler);
    }

    myChart.dispose();
    myChart = null;
  }
});
</script> 