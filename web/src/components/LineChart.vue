<template>
  <div ref="chartRef" style="width: 100%; height: 400px"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import type { PropType } from 'vue';
import * as echarts from 'echarts';
import { ComponentCategory, type PerfData } from '../stores/jsonDataStore.ts';

const props = defineProps({
  chartData: {
    type: Object as PropType<PerfData | null>,
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
const processData = (data: PerfData | null, seriesType: string) => {
  if (!data) {
    return {
      xData: [],
      legendData: [],
      series: [],
    };
  }

  const { steps } = data;
  const xData = steps.map((step) => step.step_name);
  const categoryMap = new Map<ComponentCategory, number[]>();

  // 初始化categoryMap，为每个x轴位置创建一个数组
  xData.forEach(() => {
    Object.values(ComponentCategory).forEach((category) => {
      if (typeof category === 'number') {
        if (!categoryMap.has(category)) {
          categoryMap.set(category, Array(xData.length).fill(0));
        }
      }
    });
  });

  // 遍历所有步骤中的数据条目
  steps.forEach((step, stepIndex) => {
    step.data.forEach(item => {
      const category = item.componentCategory;
      const events = item.symbolEvents;
      const values = categoryMap.get(category) || Array(xData.length).fill(0);
      values[stepIndex] = (values[stepIndex] || 0) + events;
      categoryMap.set(category, values);
    });
  });

  // 构建series数据
  const legendData: string[] = [];
  const series: {}[] = [];

  categoryMap.forEach((values, category) => {
    // 检查该类别在所有步骤中是否都为0
    if (values.every(value => value === 0)) return;

    const categoryName = ComponentCategory[category];
    legendData.push(categoryName);

    // 确保seriesType有效
    const validTypes = ['bar', 'line'];
    const type = validTypes.includes(seriesType) ? seriesType : 'bar';

    series.push({
      name: categoryName,
      type: type,
      data: values,
    });
  });

  return {
    xData,
    legendData,
    series,
  };
};

// 更新图表函数
const updateChart = () => {
  if (!myChart || !chartRef.value) return;

  const { xData, legendData, series } = processData(props.chartData, props.seriesType);
  const title = props.chartData?.steps[0].data[0].eventType == 0 ? 'cycles' : 'instructions';
  const option = {
    title: {
      text: '步骤负载：' + title,
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
    series: series,
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
    (myChart as any).__resizeHandler = resizeHandler;
  }
});

// 监听数据变化
watch(
  () => props.chartData,
  () => {
    updateChart();
  },
  { deep: true } // 深度监听对象变化
);

// 清理资源
onBeforeUnmount(() => {
  if (myChart) {
    // 获取并移除resize监听器
    const resizeHandler = (myChart as any).__resizeHandler;
    window.removeEventListener('resize', resizeHandler);

    myChart.dispose();
    myChart = null;
  }
});
</script>