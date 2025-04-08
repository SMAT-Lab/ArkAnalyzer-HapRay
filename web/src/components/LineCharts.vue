<template>
    <div ref="chartRef" style="width: 100%; height: 400px;"></div>
  </template>
  
  <script lang="ts" setup>
  import { ref, onMounted } from 'vue';
  import * as echarts from 'echarts';
  import { useJsonDataStore, type JSONData } from '../stores/jsonDataStore.ts';
  
// 获取存储实例
const jsonDataStore = useJsonDataStore();
// 通过 getter 获取 JSON 数据
const json: JSONData|null = jsonDataStore.jsonData;



function processJSONToEchartsBar(json: JSONData) {
    const { categories, steps } = json;
    const stepNames: string[] = [];
    const seriesData: { name: string; data: number[] }[] = categories.map((category) => ({
        name: category,
        data: []
    }));

    steps.forEach((step) => {
        stepNames.push(step.step_name);
        const categoryCountMap = new Map<number, number>();

        step.data.forEach((data) => {
            const category = data.category;
            const count = data.count;
            if (categoryCountMap.has(category)) {
                categoryCountMap.set(category, categoryCountMap.get(category)! + count);
            } else {
                categoryCountMap.set(category, count);
            }
        });

        categories.forEach((_, index) => {
            seriesData[index].data.push(categoryCountMap.get(index) || 0);
        });
    });

    return {
      title: {
    text: '场景负载情况：'
  },
        xAxis: {
            type: 'category',
            data: stepNames
        },
        yAxis: {
            type: 'value'
        },
        legend: {
            data: categories,
            left: 'right'
        },
        series: seriesData,
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: {
                    color: '#999'
                }
            }
        },
        toolbox: {
            feature: {
                saveAsImage: {}
            }
        }
    };
}




function processJSONToEchartsLine(json: JSONData|null) {
  if(json === null){
    return {
      title: {
    text: '场景负载情况：'
  },
        xAxis: {
            type: 'category',
            data: []
        },
        yAxis: {
            type: 'value'
        },
        legend: {
            data: []
        },
        series: [],
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: {
                    color: '#999'
                }
            }
        },
        toolbox: {
            feature: {
                saveAsImage: {}
            }
        }
    };
    }
    const { categories, steps } = json;
    const stepNames: string[] = [];
    const seriesData: { name: string; type: 'line'; data: number[] }[] = categories.map((category) => ({
        name: category,
        type: 'line',
        data: []
    }));

    steps.forEach((step) => {
        stepNames.push(step.step_name);
        const categoryCountMap = new Map<number, number>();

        step.data.forEach((data) => {
            const category = data.category;
            const count = data.count;
            if (categoryCountMap.has(category)) {
                categoryCountMap.set(category, categoryCountMap.get(category)! + count);
            } else {
                categoryCountMap.set(category, count);
            }
        });

        categories.forEach((_, index) => {
            seriesData[index].data.push(categoryCountMap.get(index) || 0);
        });
    });

    return {
      title: {
    text: '场景负载情况：',
    left: 'left', 
        botton: 20,      
        textStyle: { fontSize: 16 } 
  },
        xAxis: {
            type: 'category',
            data: stepNames
        },
        yAxis: {
            type: 'value'
        },
        legend: {
            type: 'scroll',
            left: 'center',           
            top: 20,            
            bottom: 20, 
            data: categories
        },
        series: seriesData,
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: {
                    color: '#999'
                }
            }
        },
        toolbox: {
            feature: {
                saveAsImage: {}
            }
        }
    };
}
  const chartRef = ref(null);

  onMounted(() => {
    const myChart = echarts.init(chartRef.value);

    myChart.setOption(processJSONToEchartsLine(json));

    window.addEventListener('resize', () => {
    myChart.resize(); // 重新计算图表尺寸
  });
  });


  </script>    