<template>
    <div ref="chartRef" style="width: 100%; height: 400px;"></div>
  </template>
  
  <script lang='ts' setup>
  import { ref, onMounted } from 'vue';
  import * as echarts from 'echarts';
  import { useJsonDataStore, type JSONData } from '../stores/jsonDataStore.ts';
  
  // 获取存储实例
  const jsonDataStore = useJsonDataStore();
  // 通过 getter 获取 JSON 数据
  const json = jsonDataStore.jsonData;
  console.log('从元素获取到的 JSON 数据:');
  const chartRef = ref(null);

// 处理 JSON 数据，统计每个步骤下各 category 的 count 值
function processData(data: JSONData|null) {
  if(data === null){
    return {}
  }
    const { steps, categories } = data;
    const xData: string[] = steps.map(step => step.step_name);
    const seriesData: number[][] = Array.from({ length: categories.length }, () => []);

    steps.forEach((step, stepIndex) => {
        step.data.forEach(item => {
            const categoryIndex = item.category;
            seriesData[categoryIndex][stepIndex] = item.count;
        });
    });

    const legendData: string[] = categories;
    const series = seriesData.map((data, index) => ({
        name: legendData[index],
        type: 'bar',
        data
    }));

    return { xData, legendData, series };
}

const { xData, legendData, series } = processData(json);

const option = {
    title: {
        text: '场景负载情况：',
        left: 'left'
    },
    tooltip: {
        trigger: 'axis',
        axisPointer: {
            type: 'cross',
            crossStyle: {
                color: '#999'
            }
        }
    },
    legend: {
        data: legendData
    },
    xAxis: {
        type: 'category',
        data: xData
    },
    yAxis: {
        type: 'value'
    },
    series
};

  
  onMounted(() => {
    const myChart = echarts.init(chartRef.value);
    
    myChart.setOption(option);
  });
  </script>    