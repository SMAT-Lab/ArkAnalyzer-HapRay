<template>
  <div ref="chartRef" class="meminfo-chart" :style="{ height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as echarts from 'echarts';
import type { ECharts } from 'echarts';

const props = withDefaults(defineProps<{
  data: Record<string, unknown>[];
  height?: string;
}>(), {
  height: '500px'
});

const chartRef = ref<HTMLElement>();
let chartInstance: ECharts | null = null;

onMounted(() => {
  if (chartRef.value) {
    renderChart();
  }
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});

watch(() => props.data, () => {
  renderChart();
}, { deep: true });

function handleResize() {
  chartInstance?.resize();
}

function renderChart() {
  if (!chartRef.value || !props.data.length) return;

  if (chartInstance) {
    chartInstance.dispose();
  }

  chartInstance = echarts.init(chartRef.value);

  // 解析数据
  const timestamps: string[] = [];
  const allKeys = new Set<string>();
  const rowDataList: Record<string, number>[] = [];

  props.data.forEach((row) => {
    timestamps.push(row.timestamp as string);
    const data = JSON.parse(row.data as string);
    rowDataList.push(data);
    Object.keys(data).forEach(key => allKeys.add(key));
  });

  // 为每个key构建完整的数据数组
  const dataMap = new Map<string, number[]>();
  
  allKeys.forEach(key => {
    const values: number[] = [];
    rowDataList.forEach(rowData => {
      const value = rowData[key] || 0;
      values.push(value / (1024 * 1024)); // 转换为MB
    });
    dataMap.set(key, values);
  });

  // 计算相对时间（秒）
  const parsedTimestamps = timestamps.map(ts => {
    if (typeof ts === 'string') {
      const year = parseInt(ts.substring(0, 4));
      const month = parseInt(ts.substring(4, 6)) - 1;
      const day = parseInt(ts.substring(6, 8));
      const hour = parseInt(ts.substring(9, 11));
      const minute = parseInt(ts.substring(11, 13));
      const second = parseInt(ts.substring(13, 15));
      return new Date(year, month, day, hour, minute, second).getTime();
    }
    return ts as number;
  });
  
  const baseTimestamp = parsedTimestamps[0];
  const relativeTime = parsedTimestamps.map(ts => (ts - baseTimestamp) / 1000);

  // 构建series
  const series = Array.from(dataMap.entries()).map(([name, data]) => ({
    name,
    type: 'line',
    stack: 'Total',
    areaStyle: {},
    emphasis: {
      focus: 'series'
    },
    data
  }));

  const option = {
    title: {
      text: '一级内存使用情况',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      },
      formatter: (params: unknown) => {
        const paramArray = Array.isArray(params) ? params : [params];
        let result = `相对时间: ${paramArray[0]?.axisValue}s<br/>`;
        let total = 0;
        paramArray.forEach((item: { marker?: string; seriesName?: string; value?: number }) => {
          result += `${item.marker}${item.seriesName}: ${item.value?.toFixed(2)} MB<br/>`;
          total += item.value || 0;
        });
        result += `<strong>总计: ${total.toFixed(2)} MB</strong>`;
        return result;
      }
    },
    legend: {
      type: 'scroll',
      top: 30,
      data: Array.from(dataMap.keys())
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 80,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: relativeTime,
      name: '相对时间 (秒)',
      nameLocation: 'middle',
      nameGap: 30
    },
    yAxis: {
      type: 'value',
      name: '内存 (MB)',
      axisLabel: {
        formatter: '{value}'
      }
    },
    series
  };

  chartInstance.setOption(option);
}
</script>

<style scoped>
.meminfo-chart {
  width: 100%;
}
</style>

