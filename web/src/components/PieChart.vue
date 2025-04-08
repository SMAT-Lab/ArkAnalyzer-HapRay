<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import { useJsonDataStore, type JSONData } from '../stores/jsonDataStore.ts';
  
  // 获取存储实例
  const jsonDataStore = useJsonDataStore();
  // 通过 getter 获取 JSON 数据
  const json = jsonDataStore.jsonData;
  console.log('从元素获取到的 JSON 数据:');

  // 定义 ECharts 饼状图数据项类型
interface EChartsPieDataItem {
    value: number;
    name: string;
}

const chartRef = ref(null);

// 处理 JSON 数据生成饼状图所需数据
function processJSONData(data: JSONData |null) {
    if(data === null){
      return {}
    }
    const { categories, steps } = data;
    const categoryCountMap = new Map<string, number>();

    // 初始化每个分类的计数为 0
    categories.forEach(category => {
        categoryCountMap.set(category, 0);
    });

    // 遍历所有步骤中的数据，累加每个分类的计数
    steps.forEach(step => {
        step.data.forEach(item => {
            const categoryName = categories[item.category];
            const currentCount = categoryCountMap.get(categoryName) || 0;
            categoryCountMap.set(categoryName, currentCount + item.count);
        });
    });

    const legendData: string[] = [];
    const seriesData: { name: string; value: number }[] = [];

    // 将分类名称和对应的计数转换为饼状图所需的数据格式
    categoryCountMap.forEach((count, category) => {
        legendData.push(category);
        seriesData.push({ name: category, value: count });
    });

    return { legendData, seriesData };
}

const data = processJSONData(json);

const option = {
    title: {
        text: '场景负载：instructions',
        left: 'left'
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
        data: data.legendData
    },
    series: [
        {
            type: 'pie',
            radius: '80%',
            center: ['60%', '50%'],
            data: data.seriesData,
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                }
            }
        }
    ]
};
onMounted(() => {
  const myChart = echarts.init(chartRef.value);

  myChart.setOption(option);

  window.addEventListener('resize', () => {
    myChart.resize(); // 重新计算图表尺寸
  });
});
</script>

<style scoped>
.chart-container {
    width: 100%;
    height: 400px;
    /* 添加弹性容器支持 */
    display: flex;
  }
</style>