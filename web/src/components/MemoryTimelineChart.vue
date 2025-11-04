<template>
  <div style="position: relative; width: 100%;">
    <div ref="chartContainer" :style="{ height, width: '100%' }"></div>
    <div v-if="isLoading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255, 255, 255, 0.9); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 1000;">
      <div style="text-align: center;">
        <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">正在加载图表...</div>
        <div style="font-size: 12px; color: #666;">数据量较大，请稍候</div>
      </div>
    </div>

    <!-- 调用链信息表格 -->
    <div v-if="hasSelectedTimePoint" style="margin-top: 20px;">
      <h4 style="margin-bottom: 10px; font-size: 14px; font-weight: 600; color: #333;">
        <i class="el-icon-link" style="margin-right: 5px;"></i>
        当前时间点调用链信息
      </h4>

      <!-- 有调用链数据 -->
      <el-table
        v-if="selectedCallchains.length > 0"
        :data="selectedCallchains"
        border
        stripe
        size="small"
        max-height="400"
        style="width: 100%;"
      >
        <el-table-column prop="callchainId" label="调用链ID" width="100" align="center" />
        <el-table-column prop="depth" label="深度" width="80" align="center" />
        <el-table-column prop="file" label="文件" min-width="200" show-overflow-tooltip />
        <el-table-column prop="symbol" label="符号" min-width="200" show-overflow-tooltip />
        <el-table-column prop="is_alloc" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_alloc ? 'success' : 'danger'" size="small">
              {{ row.is_alloc ? '分配' : '释放' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 无调用链数据（callchain_id=-1） -->
      <el-alert
        v-else
        title="该时间点的内存事件没有调用链信息"
        type="info"
        :closable="false"
        show-icon
      >
        <template #default>
          <div style="font-size: 13px; color: #606266;">
            <p style="margin: 0 0 8px 0;">
              <strong>原因：</strong>当前选中的时间点包含的内存事件（通常是释放事件）在数据采集时未记录调用栈信息。
            </p>
            <p style="margin: 0;">
              <strong>事件详情：</strong>{{ selectedRecordsSummary }}
            </p>
          </div>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';
import type { CallbackDataParams } from 'echarts/types/dist/shared';
import type { NativeMemoryRecord, CallchainRecord } from '@/stores/jsonDataStore';
import { calculateCumulativeMemory } from '@/utils/nativeMemoryUtil';

interface Props {
  records: NativeMemoryRecord[];
  height?: string;
  selectedTimePoint?: number | null; // 当前选中的时间点
  callchains?: CallchainRecord[] | Record<number, CallchainRecord[]>; // 调用链数据
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  selectedTimePoint: null,
  callchains: undefined,
});

// 定义 emit 事件
const emit = defineEmits<{
  'time-point-selected': [timePoint: number | null];
}>();

const chartContainer = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const isLoading = ref(false);

// 计算选中时间点的调用链信息
const selectedCallchains = computed(() => {
  if (props.selectedTimePoint === null || !props.callchains) {
    return [];
  }

  // 找到选中时间点的所有记录
  const selectedRecords = props.records.filter(
    (record) => record.relativeTs === props.selectedTimePoint
  );

  // 创建 callchainId -> eventType 的映射，用于判断是分配还是释放
  const callchainEventTypeMap = new Map<number, string>();
  selectedRecords.forEach((record) => {
    if (!callchainEventTypeMap.has(record.callchainId)) {
      callchainEventTypeMap.set(record.callchainId, record.eventType);
    }
  });

  // 收集所有调用链ID
  const callchainIds = new Set(selectedRecords.map((r) => r.callchainId));

  // 获取调用链详细信息
  interface CallchainWithId extends CallchainRecord {
    callchainId: number;
    is_alloc: boolean;
  }
  const result: CallchainWithId[] = [];

  if (Array.isArray(props.callchains)) {
    // 数组格式：直接过滤（这种格式应该已经有 callchainId）
    props.callchains.forEach((c) => {
      if (callchainIds.has(c.callchainId)) {
        const eventType = callchainEventTypeMap.get(c.callchainId) || '';
        const isAlloc = eventType === 'AllocEvent' || eventType === 'MmapEvent';
        result.push({
          ...c,
          callchainId: c.callchainId,
          is_alloc: isAlloc,
        });
      }
    });
  } else {
    // 字典格式：按 callchainId 查找，需要手动添加 callchainId 字段
    callchainIds.forEach((id) => {
      const chains = props.callchains![id];
      if (chains && Array.isArray(chains)) {
        const eventType = callchainEventTypeMap.get(id) || '';
        const isAlloc = eventType === 'AllocEvent' || eventType === 'MmapEvent';
        chains.forEach((chain) => {
          result.push({
            ...chain,
            callchainId: id,
            is_alloc: isAlloc,
          });
        });
      }
    });
  }

  // 按调用链ID和深度排序
  return result.sort((a, b) => {
    if (a.callchainId !== b.callchainId) {
      return a.callchainId - b.callchainId;
    }
    return a.depth - b.depth;
  });
});

// 是否选中了时间点
const hasSelectedTimePoint = computed(() => {
  return props.selectedTimePoint !== null;
});

// 选中时间点的记录摘要（用于无调用链时显示）
const selectedRecordsSummary = computed(() => {
  if (props.selectedTimePoint === null) {
    return '';
  }

  const selectedRecords = props.records.filter(
    (record) => record.relativeTs === props.selectedTimePoint
  );

  if (selectedRecords.length === 0) {
    return '无记录';
  }

  // 统计事件类型
  const eventTypeCounts = new Map<string, number>();
  let totalSize = 0;

  selectedRecords.forEach((record) => {
    const eventType = record.eventType;
    eventTypeCounts.set(eventType, (eventTypeCounts.get(eventType) || 0) + 1);
    totalSize += record.heapSize;
  });

  // 构建摘要字符串
  const eventTypeStr = Array.from(eventTypeCounts.entries())
    .map(([type, count]) => `${type}×${count}`)
    .join(', ');

  const sizeStr = totalSize >= 1024 * 1024
    ? `${(totalSize / (1024 * 1024)).toFixed(2)} MB`
    : totalSize >= 1024
    ? `${(totalSize / 1024).toFixed(2)} KB`
    : `${totalSize} B`;

  return `${eventTypeStr}，总大小 ${sizeStr}`;
});

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

  // 按时间排序记录
  const sortedRecords = [...props.records].sort((a, b) => a.relativeTs - b.relativeTs);

  // 计算当前内存
  const recordsWithCumulative = calculateCumulativeMemory(sortedRecords);

  // 计算最大最小值
  let maxMemory = -Infinity;
  let minMemory = Infinity;

  // 对于超大数据集（> 50000），使用更激进的优化策略
  const isVeryLargeDataset = recordsWithCumulative.length > 50000;

  // 构建图表数据
  const chartData = recordsWithCumulative.map((record, index) => {
    const currentMemory = record.cumulativeMemory;

    // 更新最大最小值
    if (currentMemory > maxMemory) maxMemory = currentMemory;
    if (currentMemory < minMemory) minMemory = currentMemory;

    // 对于超大数据集，只保留必要的字段
    if (isVeryLargeDataset) {
      return {
        index,
        relativeTs: record.relativeTs,
        cumulativeMemory: currentMemory,
        heapSize: record.heapSize,
        eventType: record.eventType,
        // 其他字段在 tooltip 时从原始数据获取
      };
    }

    return {
      index,
      relativeTs: record.relativeTs,
      cumulativeMemory: currentMemory,
      heapSize: record.heapSize,
      eventType: record.eventType,
      subEventType: record.subEventType,
      process: record.process,
      thread: record.thread || 'N/A',
      file: record.file || 'N/A',
      symbol: record.symbol || 'N/A',
    };
  });

  const finalMemory = chartData[chartData.length - 1]?.cumulativeMemory || 0;

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
  // let defaultZoomEnd;
  // if (isVeryLargeDataset) {
  //   defaultZoomEnd = Math.min(100, (100 / chartData.length) * 100); // 只显示 100 个事件
  // } else if (isLargeDataset) {
  //   defaultZoomEnd = Math.min(100, (200 / chartData.length) * 100); // 显示 200 个事件
  // } else {
  //   defaultZoomEnd = Math.min(100, (500 / chartData.length) * 100); // 显示 500 个事件
  // }

  const option: echarts.EChartsOption = {
    animation: !isLargeDataset, // 大数据集时禁用动画
    animationDuration: isVeryLargeDataset ? 0 : 300, // 超大数据集时完全禁用动画
    animationDurationUpdate: isVeryLargeDataset ? 0 : 300,
    title: {
      text: `内存时间线 (共 ${chartData.length.toLocaleString()} 个事件)`,
      subtext: props.selectedTimePoint !== null
        ? `🔸 选中时间点: ${formatTime(props.selectedTimePoint)} | 🔴 峰值: ${formatBytes(maxMemory)} | 最低: ${formatBytes(minMemory)} | 最终: ${formatBytes(finalMemory)}`
        : `🔴 峰值: ${formatBytes(maxMemory)} | 最低: ${formatBytes(minMemory)} | 最终: ${formatBytes(finalMemory)}`,
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 600,
      },
      subtextStyle: {
        fontSize: 13,
        color: props.selectedTimePoint !== null ? '#ff9800' : '#666',
        fontWeight: props.selectedTimePoint !== null ? 'bold' : 'normal',
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
          `<div><strong>当前内存:</strong> ${formatBytes(dataItem.cumulativeMemory)}</div>`,
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
      bottom: '10%',
      top: '20%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: chartData.map((_, index) => index), // 使用索引而不是格式化的时间字符串
      name: '相对时间',
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
      name: '当前内存',
      nameLocation: 'middle',
      nameGap: 60,
      axisLabel: {
        formatter: (value: number) => formatBytes(value),
      },
    },
    series: [
      {
        name: '当前内存',
        type: 'line', // 改用折线图，性能更好
        data: chartData.map((item) => {
          // 找到峰值点的索引
          const isPeak = item.cumulativeMemory === maxMemory;
          // 找到选中点的索引
          const isSelected = props.selectedTimePoint !== null && item.relativeTs === props.selectedTimePoint;

          // 根据状态返回不同的配置
          if (isPeak) {
            return {
              value: item.cumulativeMemory,
              itemStyle: {
                // 峰值点标红 - 更加突出
                color: '#ff0000',
                borderColor: '#fff',
                borderWidth: 3,
                shadowBlur: 20,
                shadowColor: 'rgba(255, 0, 0, 0.8)',
              },
              symbolSize: 18,
              // 添加标签显示
              label: {
                show: true,
                position: 'top',
                formatter: () => '● 峰值',
                color: '#ff0000',
                fontWeight: 'bold',
                fontSize: 12,
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
                padding: [4, 8],
                borderRadius: 4,
                borderColor: '#ff0000',
                borderWidth: 1,
              },
            };
          } else if (isSelected) {
            return {
              value: item.cumulativeMemory,
              itemStyle: {
                // 选中点标黄 - 更加醒目
                color: '#FFD700',
                borderColor: '#fff',
                borderWidth: 5,
                shadowBlur: 30,
                shadowColor: 'rgba(255, 215, 0, 1)',
              },
              symbolSize: 24,
              // 添加标签显示
              label: {
                show: true,
                position: 'top',
                formatter: () => '● 已选中',
                color: '#FFD700',
                fontWeight: 'bold',
                fontSize: 12,
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
                padding: [4, 8],
                borderRadius: 4,
                borderColor: '#FFD700',
                borderWidth: 1,
              },
            };
          } else {
            return {
              value: item.cumulativeMemory,
              symbolSize: isVeryLargeDataset ? 4 : (isLargeDataset ? 6 : 8),
            };
          }
        }),
        // 不使用 sampling，避免丢失自定义样式
        symbol: 'circle', // 显示圆形数据点标记，以便点击
        showSymbol: true, // 始终显示数据点
        lineStyle: {
          width: isVeryLargeDataset ? 0.8 : (isLargeDataset ? 1 : 1.5), // 超大数据集时使用更细的线条
          color: '#3498db',
        },
        // 不使用 areaStyle，避免影响数据点显示
        emphasis: {
          disabled: false, // 启用高亮，以便点击时有视觉反馈
          focus: 'self',
          scale: false, // 禁用缩放，避免影响自定义样式
        },
        // 使用 progressive 渲染优化大数据集性能
        progressive: isVeryLargeDataset ? 500 : (isLargeDataset ? 1000 : 0), // 超大数据集时使用更小的批次
        progressiveThreshold: isVeryLargeDataset ? 500 : 1000, // 超大数据集时降低阈值
        progressiveChunkMode: 'mod' as const, // 使用 mod 渲染模式
      },
    ],
  };

    chartInstance.setOption(option, {
      replaceMerge: ['series'], // 只替换 series，保留其他配置
      lazyUpdate: isVeryLargeDataset, // 超大数据集时使用延迟更新
      silent: false, // 不静默更新，确保样式正确应用
    });

    // 添加点击事件监听
    chartInstance.off('click'); // 先移除旧的监听器
    chartInstance.on('click', (params: { componentType?: string; dataIndex?: number }) => {
      if (params.componentType === 'series' && typeof params.dataIndex === 'number') {
        const dataIndex = params.dataIndex;
        const dataItem = chartData[dataIndex];
        if (dataItem) {
          // 如果点击的是已选中的点，则取消选择
          if (props.selectedTimePoint === dataItem.relativeTs) {
            emit('time-point-selected', null);
          } else {
            emit('time-point-selected', dataItem.relativeTs);
          }
        }
      }
    });

    // 如果有选中的时间点，添加标记线
    if (props.selectedTimePoint !== null) {
      updateMarkLine(chartData);
    }

    // 隐藏加载状态
    isLoading.value = false;
  } catch (error) {
    console.error('初始化图表失败:', error);
    isLoading.value = false;
  }
}

// 更新标记线
function updateMarkLine(chartData: Array<{ relativeTs: number; cumulativeMemory: number }>) {
  if (!chartInstance || props.selectedTimePoint === null) return;

  // 找到最接近选中时间点的数据索引
  let closestIndex = 0;
  let minDiff = Math.abs(chartData[0].relativeTs - props.selectedTimePoint);

  for (let i = 1; i < chartData.length; i++) {
    const diff = Math.abs(chartData[i].relativeTs - props.selectedTimePoint);
    if (diff < minDiff) {
      minDiff = diff;
      closestIndex = i;
    }
    // 如果时间已经超过选中点，可以提前退出
    if (chartData[i].relativeTs > props.selectedTimePoint) {
      break;
    }
  }

  // 获取当前配置
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const option = chartInstance.getOption() as any;
  if (option && option.series && option.series[0]) {
    const series = option.series[0];
    const selectedMemory = chartData[closestIndex]?.cumulativeMemory || 0;
    series.markLine = {
      silent: false,
      symbol: ['none', 'arrow'],
      symbolSize: [0, 8],
      label: {
        show: true,
        position: 'end',
        formatter: `选中: ${formatTime(props.selectedTimePoint)}\n内存: ${formatBytes(selectedMemory)}`,
        color: '#333',
        backgroundColor: '#FFD700',
        padding: [6, 10],
        borderRadius: 4,
        fontSize: 12,
        fontWeight: 'bold',
      },
      lineStyle: {
        color: '#FFD700',
        width: 3,
        type: 'solid',
        shadowBlur: 10,
        shadowColor: 'rgba(255, 215, 0, 0.5)',
      },
      data: [
        {
          xAxis: closestIndex,
        },
      ],
    };

    chartInstance.setOption(option);
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

// 监听 selectedTimePoint 的变化，更新标记线
watch(
  () => props.selectedTimePoint,
  () => {
    if (chartInstance && processedData.value.chartData.length > 0) {
      updateMarkLine(processedData.value.chartData);
    }
  }
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

