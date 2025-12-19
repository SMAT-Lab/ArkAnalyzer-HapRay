<template>
  <div ref="chartRef" style="width: 100%; height: 400px"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import type { PropType } from 'vue';
import * as echarts from 'echarts';
import { ComponentCategory, type PerfData } from '../../../stores/jsonDataStore.ts';

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
  // step_name 已移到 jsonDataStore.steps 中，这里使用默认值
  const xData = steps.map((step, index) => `步骤${index + 1}`);
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
  const series: object[] = [];

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
  const title = props.chartData?.steps[0]?.data[0]?.eventType == 0 ? 'cycles' : 'instructions';
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
        label: {
          formatter: function(params: { axisDimension: string; value: number }) {
            // 显示完整的步骤名称
            if (params.axisDimension === 'x') {
              const fullName = xData[params.value];
              return fullName;
            }
            return params.value;
          }
        }
      },
      formatter: function(params: { dataIndex: number; color: string; seriesName: string; value: number }[] | { dataIndex: number; color: string; seriesName: string; value: number }) {
        if (!Array.isArray(params)) params = [params];
        const dataIndex = params[0].dataIndex;
        const fullStepName = xData[dataIndex];
        let html = `<div style="font-weight: bold; margin-bottom: 8px; color: #333;">
          步骤: ${fullStepName}
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
      data: legendData,
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: {
        interval: 0, // 强制显示所有标签
        fontSize: 9, // 进一步减小字体
        margin: 8,
        color: '#666',
        fontWeight: 'normal',
        formatter: function(_value: string, index: number) {
          // 只显示步骤编号，如 step1, step2
          return `step${index + 1}`;
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
    (myChart as unknown as { __resizeHandler?: () => void }).__resizeHandler = resizeHandler;
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
    const resizeHandler = (myChart as unknown as { __resizeHandler?: () => void }).__resizeHandler;
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler);
    }

    myChart.dispose();
    myChart = null;
  }
});
</script>