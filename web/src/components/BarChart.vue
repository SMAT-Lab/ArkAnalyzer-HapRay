<template>
  <div ref="chartRef" style="width: 100%; height: 400px;"></div>
</template>

<script lang='ts' setup>
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import type { PropType } from 'vue';
import { type PerfData } from '../stores/jsonDataStore.ts';

const props = defineProps({
  chartData: {
    type: Object as PropType<PerfData | null>,
    required: true,
  },
});

// 处理 JSON 数据，统计每个步骤的 count 值并降序排序
function processData(data: PerfData|null) {
  if(data === null){
    return { xData: [], yData: [], fullNames: [] }
  }
    const { steps } = data;
    const stepCounts = steps.map((step, index) => ({
        stepName: step.step_name,
        count: step.count,
        originalIndex: index // 保存原始索引
    }));

    // 按 count 值降序排序
    stepCounts.sort((a, b) => a.count - b.count);

    const xData = stepCounts.map(item => `step${item.originalIndex + 1}`); // 使用step编号
    const yData = stepCounts.map(item => item.count);
    const fullNames = stepCounts.map(item => item.stepName); // 保存完整名称用于tooltip

    return { xData, yData, fullNames };
}

const processedData = processData(props.chartData);
const { xData, yData, fullNames } = processedData;

const title = props.chartData?.steps[0].data[0].eventType==0?'cycles':'instructions';

const option = {
    title: {
        text: '步骤负载排名：'+title,
        left: 'left'
    },
    tooltip: {
        trigger: 'axis',
        axisPointer: {
            type: 'shadow'
        },
        formatter: function(params: { dataIndex: number; color: string; value: number }[] | { dataIndex: number; color: string; value: number }) {
            if (!Array.isArray(params)) params = [params];
            const param = params[0];
            const fullName = fullNames[param.dataIndex];
            const stepLabel = xData[param.dataIndex];

            return `<div style="font-weight: bold; margin-bottom: 8px; color: #333;">
                步骤: ${stepLabel}
            </div>
            <div style="margin: 4px 0; color: #666;">
                完整名称: ${fullName}
            </div>
            <div style="margin: 4px 0;">
                <span style="display: inline-block; width: 10px; height: 10px; background: ${param.color}; margin-right: 8px; border-radius: 50%;"></span>
                负载值: <strong>${param.value.toLocaleString()}</strong>
            </div>`;
        }
    },
    xAxis: {
        type: 'value',
        boundaryGap: [0, 0.01]
    },
    yAxis: {
        type: 'category',
        data: xData,
        axisLabel: {
            interval: 0, // 强制显示所有标签
            fontSize: 9, // 进一步减小字体
            margin: 8,
            color: '#666',
            fontWeight: 'normal',
            formatter: function(value: string) {
                // 根据字符长度动态截断
                const maxLength = 16;
                return value.length > maxLength ? value.substring(0, maxLength) + '...' : value;
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
    series: [
        {
            type: 'bar',
            data: yData
        }
    ]
};

const chartRef = ref(null);
onMounted(() => {
  const myChart = echarts.init(chartRef.value);
  myChart.setOption(option);

  window.addEventListener('resize', () => {
    myChart.resize(); // 重新计算图表尺寸
  });
});




</script>    