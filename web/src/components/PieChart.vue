<template>
  <div class="piechart-wrapper">
    <div v-if="drilldownStack.length > 0" class="drillup-btn" @click="handleDrillUp">⬅ 返回上一级</div>
    <div ref="chartRef" class="chart-container"></div>
  </div>
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
  },
  // 新增：下钻栈
  drilldownStack: { type: Array as PropType<string[]>, default: () => [] },
  // 是否对legend做截断
  legendTruncate: { type: Boolean, default: false }
});
const emit = defineEmits(['drilldown', 'drillup']);

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
    formatter: (params: { name: string; value: number; percent: number; seriesName: string }) => {
      // 鼠标悬停显示完整 name
      return `${params.seriesName} <br/>${params.name} : ${params.value} (${params.percent}%)`;
    }
  },
  legend: {
    type: 'scroll',
    orient: 'vertical',
    left: 10,
    top: 30,
    bottom: 20,
    data: props.chartData.seriesData.map(d => d.name),
    // legend 显示截断，鼠标悬停显示完整
    formatter: (name: string) => props.legendTruncate && name.length > 10 ? name.slice(0, 10) + '...' : name,
    tooltip: {
      show: true,
      formatter: (name: string) => name
    }
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
      position: 'outside',
      formatter: (params: { name: string }) => {
        const name = params.name;
        return name.length > 10 ? name.slice(0, 10) + '...' : name;
      },
      rich: {},
      // 鼠标悬停时显示完整内容由 tooltip 控制
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
    
    // 下钻事件
    myChart.on('click', (params: { name?: string }) => {
      if (params && params.name) {
        // 判断当前点击项在seriesData中是否有数据且value>0
        const item = props.chartData.seriesData.find(d => d.name === params.name);
        if (item && item.value > 0) {
          emit('drilldown', params.name);
        }
      }
    });
    
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

function handleDrillUp() {
  emit('drillup');
}
</script>

<style scoped>
.piechart-wrapper {
  width: 100%;
  height: v-bind(height);
  position: relative;
}
.chart-container {
  width: 100%;
  height: v-bind(height);
  position: relative;
}
.drillup-btn {
  position: absolute;
  right: 10px;
  top: 10px;
  z-index: 2;
  background: #f3f4f6;
  color: #2563eb;
  border-radius: 6px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: background 0.2s;
}
.drillup-btn:hover {
  background: #e0e7ef;
}
</style>