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
        label: {
          formatter: function(params: { axisDimension: string; value: number }) {
            // 显示完整的版本信息
            if (params.axisDimension === 'x') {
              const fullName = props.chartData.xAxis[params.value];
              return fullName;
            }
            return params.value;
          }
        }
      },
      formatter: function(params: { dataIndex: number; color: string; seriesName: string; value: number }[] | { dataIndex: number; color: string; seriesName: string; value: number }) {
        if (!Array.isArray(params)) params = [params];
        const dataIndex = params[0].dataIndex;
        const fullVersionName = props.chartData.xAxis[dataIndex];
        let html = `<div style="font-weight: bold; margin-bottom: 8px; color: #333;">
          版本: ${fullVersionName}
        </div>`;

        params.forEach((param) => {
          html += `<div style="margin: 4px 0;">
            <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 8px; border-radius: 50%;"></span>
            ${param.seriesName}: <strong>${param.value.toLocaleString()}</strong>
          </div>`;
        });

        return html;
      }
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
        interval: 0, // 强制显示所有标签
        fontSize: 9, // 进一步减小字体
        margin: 8,
        color: '#666',
        fontWeight: 'normal',
        formatter: function(_value: string, index: number) {
          // 只显示版本编号，如 v1, v2
          return `v${index + 1}`;
        },
        rich: {
          // 定义富文本样式
          normal: {
            fontSize: 9,
            color: '#666'
          }
        }
      },
      axisTick: {
        alignWithLabel: true,
        length: 4
      },
      axisLine: {
        lineStyle: {
          color: '#e0e0e0'
        }
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