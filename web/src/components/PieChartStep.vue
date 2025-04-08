<template>
  <div ref="chartRef" style="width: 100%; height: 585px;"></div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch} from 'vue';
import * as echarts from 'echarts';
import { useJsonDataStore, type JSONData } from '../stores/jsonDataStore.ts';
  
  // 获取存储实例
  const jsonDataStore = useJsonDataStore();
  // 通过 getter 获取 JSON 数据
  const json = jsonDataStore.jsonData;
  console.log('从元素获取到的 JSON 数据:');

  const props = defineProps({
    data: {
    type: Object,
    required: true,
  },
});


const chartRef = ref(null);



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
        data: props.data.legendData
    },
    series: [
        {
            type: 'pie',
            radius: '80%',
            center: ['60%', '50%'],
            data: props.data.seriesData,
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
   // 监听数据变化
   watch(
      () => props.data,
      (newData) => {
        option.series[0].data = newData.seriesData;
        
        myChart.setOption(option);
      },
      { deep: true }
    );
    window.addEventListener('resize', () => {
    myChart.resize(); // 重新计算图表尺寸
  });
});
</script>