<template>
  <div ref="chartRef" style="width: 100%; height: 400px"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import type { PropType } from 'vue';
import * as echarts from 'echarts';
import type { JSONData } from '../stores/jsonDataStore.ts';

const props = defineProps({
  chartData: {
    type: Object as PropType<JSONData | null>,
    required: true,
  },
  seriesType: {
    type: String,
    required: true,
  },
});

const chartRef = ref<HTMLElement | null>(null);
let myChart: echarts.ECharts | null = null;

// 处理数据函数
const processData = (data: JSONData | null, seriesType: string) => {
  if (!data) {
    return {
      xData: [],
      legendData: [],
      series: [],
    };
  }

  const { steps, categories } = data;
  const xData = steps.map((step) => step.step_name);
  const seriesData: number[][] = Array.from({ length: categories.length }, () => []);

  steps.forEach((step, stepIndex) => {
    step.data.forEach((item) => {
      const categoryIndex = item.category;
      seriesData[categoryIndex][stepIndex] = item.count;
    });
  });

  return {
    xData,
    legendData: categories,
    series: seriesData.map((data, index) => ({
      name: categories[index],
      type: seriesType,
      data,
    })),
  };
};

// 更新图表函数
const updateChart = () => {
  if (!myChart) return;

  const { xData, legendData, series } = processData(props.chartData, props.seriesType);

  const option = {
    title: {
      text: '场景负载：instructions',
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
      data: legendData,
    },
    xAxis: {
      type: 'category',
      data: xData,
    },
    yAxis: {
      type: 'value',
    },
    series,
  };

  myChart.setOption(option);
};

// 初始化图表
onMounted(() => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value);
    updateChart();

    // 响应窗口变化
    window.addEventListener('resize', () => {
      myChart?.resize();
    });
  }
});

// 监听数据变化
watch(
  () => props.chartData,
  () => {
    updateChart();
  }
);

// 清理资源
onBeforeUnmount(() => {
  if (myChart) {
    myChart.dispose();
    myChart = null;
  }
  window.removeEventListener('resize', () => {
    myChart?.resize();
  });
});
</script>
