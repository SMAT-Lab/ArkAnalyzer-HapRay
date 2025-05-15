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
  
  // 记录每个category是否有数据
  const categoryHasData = new Set<number>();
  // 初始化seriesData，使用Map存储有数据的category
  const seriesDataMap = new Map<number, number[]>();

  steps.forEach((step, stepIndex) => {
    step.data.forEach((item) => {
      const { category, count } = item;
      categoryHasData.add(category);
      
      // 如果该category还没有对应的数组，则初始化
      if (!seriesDataMap.has(category)) {
        seriesDataMap.set(category, Array(steps.length).fill(0));
      }
      
      // 设置对应位置的数据
      seriesDataMap.get(category)![stepIndex] = count;
    });
  });

  // 生成最终的series和legendData，只包含有数据的category
  const series = Array.from(categoryHasData).sort((a, b) => a - b).map((categoryIndex) => ({
    name: categories[categoryIndex],
    type: seriesType,
    data: seriesDataMap.get(categoryIndex)!,
  }));

  const legendData = series.map((item) => item.name);

  return {
    xData,
    legendData,
    series,
  };
};  

// 更新图表函数
const updateChart = () => {
  if (!myChart) return;

  const { xData, legendData, series } = processData(props.chartData, props.seriesType);

  const option = {
    title: {
      text: '步骤负载：instructions',
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
