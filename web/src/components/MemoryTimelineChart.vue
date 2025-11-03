<template>
  <div style="position: relative; width: 100%;">
    <div ref="chartContainer" :style="{ height, width: '100%' }"></div>
    <div v-if="isLoading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255, 255, 255, 0.9); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 1000;">
      <div style="text-align: center;">
        <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">正在加载图表...</div>
        <div style="font-size: 12px; color: #666;">数据量较大，请稍候</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { CallbackDataParams } from 'echarts/types/dist/shared';
import type { NativeMemoryRecord } from '@/stores/jsonDataStore';

interface Props {
  records: NativeMemoryRecord[];
  height?: string;
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
});

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const isLoading = ref(false);

// 使用 computed 缓存处理后的数据
const processedData = computed(() => {
  // 如果数据为空，直接返回
  if (!props.records || props.records.length === 0) {
    return {
      chartData: [],
      maxMemory: 0,
      minMemory: 0,
      finalMemory: 0,
      threshold30: 0,
      threshold60: 0,
    };
  }

  // 按时间排序记录（使用更快的排序算法）
  const sortedRecords = [...props.records].sort((a, b) => a.relativeTs - b.relativeTs);

  // 直接使用 record.allHeapSize（后端已经计算好的累积内存值）
  let maxMemory = -Infinity;
  let minMemory = Infinity;

  // 对于超大数据集（> 50000），使用更激进的优化策略
  const isVeryLargeDataset = sortedRecords.length > 50000;

  // 如果数据量超大，只保留关键字段以减少内存占用
  const chartData = sortedRecords.map((record, index) => {
    // 使用后端提供的 allHeapSize
    const currentMemory = record.allHeapSize;

    // 更新最大最小值
    if (currentMemory > maxMemory) maxMemory = currentMemory;
    if (currentMemory < minMemory) minMemory = currentMemory;

    // 对于超大数据集，只保留必要的字段
    if (isVeryLargeDataset) {
      return {
        index,
        relativeTs: record.relativeTs,
        allHeapSize: currentMemory,
        heapSize: record.heapSize,
        eventType: record.eventType,
        // 其他字段在 tooltip 时从原始数据获取
      };
    }

    return {
      index,
      relativeTs: record.relativeTs,
      allHeapSize: currentMemory,
      heapSize: record.heapSize,
      eventType: record.eventType,
      subEventType: record.subEventType,
      process: record.process,
      thread: record.thread || 'N/A',
      file: record.file || 'N/A',
      symbol: record.symbol || 'N/A',
    };
  });

  const finalMemory = chartData[chartData.length - 1]?.allHeapSize || 0;

  // 预计算颜色映射范围
  const memoryRange = maxMemory - minMemory;
  const threshold30 = minMemory + memoryRange * 0.3;
  const threshold60 = minMemory + memoryRange * 0.6;

  return {
    chartData,
    maxMemory,
    minMemory,
    finalMemory,
    threshold30,
    threshold60,
  };
});

// 格式化字节大小
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

// 格式化时间（毫秒转秒）
function formatTime(ns: number): string {
  const ms = ns / 1000000; // 纳秒转毫秒
  if (ms < 1000) {
    return ms.toFixed(2) + ' ms';
  }
  return (ms / 1000).toFixed(2) + ' s';
}

// 初始化图表
async function initChart() {
  if (!chartContainer.value) return;

  // 显示加载状态
  isLoading.value = true;

  // 使用 setTimeout 让加载提示有机会显示
  await new Promise(resolve => setTimeout(resolve, 10));

  try {
    if (!chartInstance) {
      chartInstance = echarts.init(chartContainer.value);
    }

    // 使用缓存的处理数据
    const { chartData, maxMemory, minMemory, finalMemory } = processedData.value;

    // 如果没有数据，不初始化图表
    if (chartData.length === 0) {
      isLoading.value = false;
      return;
    }

  // 根据数据量动态调整性能策略
  const isLargeDataset = chartData.length > 10000;
  const isVeryLargeDataset = chartData.length > 50000;

  // 超大数据集时，默认只显示更少的数据
  let defaultZoomEnd;
  if (isVeryLargeDataset) {
    defaultZoomEnd = Math.min(100, (100 / chartData.length) * 100); // 只显示 100 个事件
  } else if (isLargeDataset) {
    defaultZoomEnd = Math.min(100, (200 / chartData.length) * 100); // 显示 200 个事件
  } else {
    defaultZoomEnd = Math.min(100, (500 / chartData.length) * 100); // 显示 500 个事件
  }

  const option: echarts.EChartsOption = {
    animation: !isLargeDataset, // 大数据集时禁用动画
    animationDuration: isVeryLargeDataset ? 0 : 300, // 超大数据集时完全禁用动画
    animationDurationUpdate: isVeryLargeDataset ? 0 : 300,
    title: {
      text: `内存时间线 (共 ${chartData.length.toLocaleString()} 个事件)`,
      subtext: `峰值: ${formatBytes(maxMemory)} | 最低: ${formatBytes(minMemory)} | 最终: ${formatBytes(finalMemory)}`,
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 600,
      },
      subtextStyle: {
        fontSize: 12,
        color: '#666',
      },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
      },
      formatter: (params: CallbackDataParams | CallbackDataParams[]) => {
        const paramsArray = Array.isArray(params) ? params : [params];
        if (!paramsArray || paramsArray.length === 0) return '';
        const data = paramsArray[0];
        const dataItem = chartData[data.dataIndex as number];
        if (!dataItem) return '';

        // 使用数组拼接而不是字符串拼接，性能更好
        const lines = [
          '<div style="padding: 8px; max-width: 300px;">',
          `<div style="font-weight: bold; margin-bottom: 8px;">事件 #${dataItem.index + 1}</div>`,
          `<div><strong>时间:</strong> ${formatTime(dataItem.relativeTs)}</div>`,
          `<div><strong>累积内存:</strong> ${formatBytes(dataItem.allHeapSize)}</div>`,
          `<div><strong>事件类型:</strong> ${dataItem.eventType}</div>`,
        ];

        // 对于超大数据集，简化 tooltip 内容
        if (!isVeryLargeDataset) {
          // 只在有值时才添加可选字段
          if (dataItem.subEventType) {
            lines.push(`<div><strong>子类型:</strong> ${dataItem.subEventType}</div>`);
          }

          lines.push(
            `<div><strong>内存变化:</strong> ${formatBytes(dataItem.heapSize)}</div>`,
          );

          if (dataItem.process) {
            lines.push(`<div><strong>进程:</strong> ${dataItem.process}</div>`);
          }
          if (dataItem.thread && dataItem.thread !== 'N/A') {
            lines.push(`<div><strong>线程:</strong> ${dataItem.thread}</div>`);
          }
          if (dataItem.file && dataItem.file !== 'N/A') {
            lines.push(`<div><strong>文件:</strong> ${dataItem.file}</div>`);
          }
          if (dataItem.symbol && dataItem.symbol !== 'N/A') {
            lines.push(`<div><strong>符号:</strong> ${dataItem.symbol}</div>`);
          }
        } else {
          // 超大数据集时只显示基本信息
          lines.push(`<div><strong>内存变化:</strong> ${formatBytes(dataItem.heapSize)}</div>`);
        }

        lines.push('</div>');
        return lines.join('');
      },
      confine: true, // 限制在图表区域内
      appendToBody: true, // 添加到 body，避免被裁剪
      // 超大数据集时增加 tooltip 延迟，减少频繁触发
      showDelay: isVeryLargeDataset ? 100 : 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '20%',
      containLabel: true,
    },
    dataZoom: [
      {
        type: 'slider',
        show: true,
        xAxisIndex: [0],
        start: 0,
        end: defaultZoomEnd,
        bottom: '5%',
        height: 20,
        filterMode: 'filter', // 过滤数据以提高性能
        throttle: isVeryLargeDataset ? 300 : (isLargeDataset ? 200 : 100), // 超大数据集时进一步增加节流时间
        minValueSpan: isVeryLargeDataset ? 50 : 10, // 超大数据集时限制最小缩放范围
      },
      {
        type: 'inside',
        xAxisIndex: [0],
        start: 0,
        end: defaultZoomEnd,
        filterMode: 'filter',
        throttle: isVeryLargeDataset ? 300 : (isLargeDataset ? 200 : 100),
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        minValueSpan: isVeryLargeDataset ? 50 : 10,
      },
    ],
    xAxis: {
      type: 'category',
      data: chartData.map((_, index) => index), // 使用索引而不是格式化的时间字符串
      name: '事件序号',
      nameLocation: 'middle',
      nameGap: 30,
      axisLabel: {
        interval: 'auto',
        rotate: 0,
        fontSize: 10,
        formatter: (value: string | number) => {
          // 只在需要显示时才格式化
          const index = typeof value === 'string' ? parseInt(value) : value;
          const item = chartData[index];
          return item ? formatTime(item.relativeTs) : '';
        },
      },
    },
    yAxis: {
      type: 'value',
      name: '累积内存',
      nameLocation: 'middle',
      nameGap: 60,
      axisLabel: {
        formatter: (value: number) => formatBytes(value),
      },
    },
    series: [
      {
        name: '累积内存',
        type: 'line', // 改用折线图，性能更好
        data: chartData.map(item => item.allHeapSize),
        sampling: 'lttb', // 使用 LTTB 采样算法，大幅提升性能
        symbol: 'none', // 不显示数据点标记
        lineStyle: {
          width: isVeryLargeDataset ? 0.8 : (isLargeDataset ? 1 : 1.5), // 超大数据集时使用更细的线条
          color: '#3498db',
        },
        areaStyle: isLargeDataset ? undefined : { // 大数据集时不显示区域填充
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(52, 152, 219, 0.3)' },
              { offset: 1, color: 'rgba(52, 152, 219, 0.05)' },
            ],
          },
        },
        emphasis: {
          disabled: isLargeDataset, // 大数据集时禁用高亮
        },
        // large 属性在 line 系列中不支持，使用 sampling 和 progressive 代替
        progressive: isVeryLargeDataset ? 500 : (isLargeDataset ? 1000 : 0), // 超大数据集时使用更小的批次
        progressiveThreshold: isVeryLargeDataset ? 500 : 1000, // 超大数据集时降低阈值
        progressiveChunkMode: 'mod' as const, // 使用 mod 渲染模式
      },
    ],
  };

    chartInstance.setOption(option, {
      notMerge: true, // 不合并，直接替换
      lazyUpdate: isVeryLargeDataset, // 超大数据集时使用延迟更新
      silent: isVeryLargeDataset, // 超大数据集时静默更新，不触发事件
    });

    // 隐藏加载状态
    isLoading.value = false;
  } catch (error) {
    console.error('初始化图表失败:', error);
    isLoading.value = false;
  }
}

// 监听 processedData 的变化，而不是直接监听 records
// 由于 computed 已经做了缓存，这里不需要额外的防抖
watch(
  processedData,
  () => {
    if (chartInstance) {
      // 使用 requestIdleCallback 在浏览器空闲时更新，避免阻塞主线程
      if ('requestIdleCallback' in window) {
        requestIdleCallback(() => {
          initChart();
        }, { timeout: 1000 });
      } else {
        // 降级方案
        requestAnimationFrame(() => {
          initChart();
        });
      }
    }
  },
  { deep: false }
);

// 监听窗口大小变化（使用防抖）
let resizeTimer: number | null = null;
const handleResize = () => {
  if (resizeTimer) {
    clearTimeout(resizeTimer);
  }
  resizeTimer = window.setTimeout(() => {
    if (chartInstance) {
      chartInstance.resize();
    }
    resizeTimer = null;
  }, 200); // 200ms 防抖
};

onMounted(() => {
  // 使用 requestAnimationFrame 延迟初始化，避免阻塞页面渲染
  requestAnimationFrame(() => {
    initChart();
  });
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (resizeTimer) {
    clearTimeout(resizeTimer);
    resizeTimer = null;
  }
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
/* 图表容器样式 */
</style>

