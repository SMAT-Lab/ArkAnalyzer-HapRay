<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import type { PropType } from 'vue';
import * as echarts from 'echarts';

type ChartData = {
  legendData: string[];
  seriesData: Array<{ name: string; value: number }>;
};

const props = defineProps({
  // 处理后的图表数据
  chartData: {
    type: Object as PropType<ChartData>,
    required: true,
    validator: (data: ChartData) => 
      Array.isArray(data.legendData) && 
      Array.isArray(data.seriesData)
  },
  // 图表标题
  title: {
    type: String,
    default: '负载：instructions!'
  },
  // 容器高度
  height: {
    type: String,
    default: '400px'
  }
});

const chartRef = ref<HTMLElement | null>(null);
let myChart: echarts.ECharts | null = null;

// 统一配置项
const getChartOption = () => ({
  title: {
    text: props.title,
    left: 'left',
    textStyle: { 
      fontSize: 16
    }
  },
  tooltip: {
    trigger: 'item',
    formatter: '{a} <br/>{b} : {c} ({d}%)'
  },
  legend: {
    type: 'scroll',
    orient: 'vertical',
    left: 10,
    top: 30,
    bottom: 20,
    data: props.chartData.legendData
  },
  series: [{
    name: props.title,
    type: 'pie',
    radius: '80%',
    center: ['60%', '50%'],
    data: props.chartData.seriesData,
    emphasis: {
      itemStyle: {
        shadowBlur: 10,
        shadowOffsetX: 0,
        shadowColor: 'rgba(0, 0, 0, 0.5)'
      }
    },
    label: {
      show: true,
      formatter: '{b}: {d}%'
    }
  }]
});

// 更新图表
const updateChart = () => {
  if (!myChart) return;
  myChart.setOption(getChartOption());
};

// 初始化图表
onMounted(() => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value);
    updateChart();
    
    // 响应窗口变化
    const resizeHandler = () => myChart?.resize();
    window.addEventListener('resize', resizeHandler);
    
    // 清理事件监听
    onBeforeUnmount(() => {
      window.removeEventListener('resize', resizeHandler);
    });
  }
});

// 监听数据变化
watch(() => props.chartData, () => {
  updateChart();
}, { deep: true });

// 组件卸载时清理
onBeforeUnmount(() => {
  if (myChart) {
    myChart.dispose();
    myChart = null;
  }
});
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: v-bind(height);
  position: relative;
}
</style>