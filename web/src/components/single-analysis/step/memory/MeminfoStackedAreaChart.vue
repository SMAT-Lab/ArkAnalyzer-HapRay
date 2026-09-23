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
  /** 每行数据所属的步骤 ID（与 data 一一对应，用于区分步骤区段；不传则不标注） */
  stepIds?: number[];
}>(), {
  height: '500px',
  stepIds: () => [],
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

watch(() => [props.data, props.stepIds], () => {
  renderChart();
}, { deep: true });

function handleResize() {
  chartInstance?.resize();
}

/** 将连续的同步骤行合并为区段（返回 [起始索引, 结束索引, stepId] 列表） */
function buildStepSpans(stepIds: number[]): Array<{ stepId: number; startIdx: number; endIdx: number }> {
  const spans: Array<{ stepId: number; startIdx: number; endIdx: number }> = [];
  stepIds.forEach((stepId, idx) => {
    const last = spans[spans.length - 1];
    if (last && last.stepId === stepId) {
      last.endIdx = idx;
    } else {
      spans.push({ stepId, startIdx: idx, endIdx: idx });
    }
  });
  return spans;
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

  // 按照value值（数组总和）排序
  const sortedEntries = Array.from(dataMap.entries()).sort((a, b) => {
    const sumA = a[1].reduce((acc, val) => acc + val, 0);
    const sumB = b[1].reduce((acc, val) => acc + val, 0);
    return sumB - sumA; // 降序排序
  });
  const sortedDataMap = new Map(sortedEntries);

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
  const series: Array<Record<string, unknown>> = Array.from(sortedDataMap.entries()).map(([name, data]) => ({
    name,
    type: 'line',
    stack: 'Total',
    areaStyle: {},
    emphasis: {
      focus: 'series'
    },
    data
  }));

  // 步骤区段标注（汇总模式下区分每个步骤的数据点）
  const hasSteps = props.stepIds.length === props.data.length && props.stepIds.length > 0;
  let markAreaData: Array<Array<Record<string, unknown>>> | undefined;
  if (hasSteps) {
    const spans = buildStepSpans(props.stepIds);
    markAreaData = spans.map((span, index) => [
      {
        name: `步骤${span.stepId}`,
        xAxis: span.startIdx,
        itemStyle: {
          color: index % 2 === 0 ? 'rgba(103, 149, 255, 0.06)' : 'rgba(103, 149, 255, 0.12)',
        },
        label: { position: 'insideTop', color: '#73767a', fontSize: 11 },
      },
      { xAxis: span.endIdx },
    ]);
    series[0].markArea = { silent: true, data: markAreaData };
  }

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
        const first = paramArray[0] as { dataIndex?: number; axisValue?: number } | undefined;
        if (!first || first.dataIndex == null) return '';
        let result = `相对时间: ${first.axisValue}s<br/>`;
        if (hasSteps) {
          result += `所属步骤: 步骤${props.stepIds[first.dataIndex]}<br/>`;
        }
        let total = 0;
        paramArray.forEach((item: { marker?: string; seriesName?: string; value?: number }) => {
          if (item.value == null) return;
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
      data: Array.from(sortedDataMap.keys())
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


