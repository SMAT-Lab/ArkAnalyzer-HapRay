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
    return {}
  }
    const { steps } = data;
    const stepCounts = steps.map(step => ({
        stepName: step.step_name,
        count: step.count
    }));

    // 按 count 值降序排序
    stepCounts.sort((a, b) => a.count - b.count);

    const xData = stepCounts.map(item => item.stepName);
    const yData = stepCounts.map(item => item.count);

    return { xData, yData };
}

const { xData, yData } = processData(props.chartData);

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
        }
    },
    xAxis: {
        type: 'value',
        boundaryGap: [0, 0.01]
    },
    yAxis: {
        type: 'category',
        data: xData
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