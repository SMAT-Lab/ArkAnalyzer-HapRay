<template>
  <div style="position: relative; width: 100%;">
    <!-- 面包屑导航 -->
    <div v-if="drillDownLevel !== 'overview'" style="margin-bottom: 10px; padding: 10px; background: #f5f5f5; border-radius: 4px;">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item>
          <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="resetDrillDown">
            <i class="el-icon-s-home"></i> 总览
          </a>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-if="drillDownLevel === 'category'">
          <span style="font-weight: 600; color: #333;">{{ selectedCategory }}</span>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-if="drillDownLevel === 'subCategory'">
          <a href="#" style="color: #409eff; text-decoration: none;" @click.prevent="backToCategory">
            {{ selectedCategory }}
          </a>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-if="drillDownLevel === 'subCategory'">
          <span style="font-weight: 600; color: #333;">{{ selectedSubCategory }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div ref="chartContainer" :style="{ height, width: '100%' }"></div>
    <div v-if="isLoading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255, 255, 255, 0.9); padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 1000;">
      <div style="text-align: center;">
        <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">正在加载图表...</div>
        <div style="font-size: 12px; color: #666;">数据量较大，请稍候</div>
      </div>
    </div>

    <!-- Tooltip 信息显示区域 -->
    <div v-if="tooltipData" style="margin-top: 20px; padding: 15px; background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 4px;">
      <h4 style="margin: 0 0 10px 0; font-size: 14px; font-weight: 600; color: #333;">
        <i class="el-icon-info" style="margin-right: 5px;"></i>
        时间点详情
      </h4>
      <div style="font-weight: bold; margin-bottom: 10px; color: #409eff;">
        时间: {{ tooltipData.timePoint }}
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 10px;">
        <div
          v-for="(item, index) in tooltipData.items"
          :key="index"
          style="padding: 10px; background: white; border-radius: 4px; border-left: 3px solid;"
          :style="{ borderLeftColor: item.color }"
        >
          <div style="font-weight: 600; margin-bottom: 8px; color: #333;">
            <span :style="{ color: item.color }">●</span> {{ item.seriesName }}
          </div>
          <div style="display: grid; grid-template-columns: auto 1fr; gap: 8px 12px; font-size: 13px;">
            <span style="color: #666;">当前内存:</span>
            <span style="font-weight: 600;">{{ item.cumulativeMemory }}</span>

            <template v-if="item.eventType">
              <span style="color: #666;">事件类型:</span>
              <span>{{ item.eventType }}</span>
            </template>

            <template v-if="item.subEventType">
              <span style="color: #666;">子类型:</span>
              <span>{{ item.subEventType }}</span>
            </template>

            <template v-if="item.heapSize">
              <span style="color: #666;">内存变化:</span>
              <span>{{ item.heapSize }}</span>
            </template>

            <template v-if="item.process">
              <span style="color: #666;">进程:</span>
              <span>{{ item.process }}</span>
            </template>

            <template v-if="item.thread && item.thread !== 'N/A'">
              <span style="color: #666;">线程:</span>
              <span>{{ item.thread }}</span>
            </template>

            <template v-if="item.file && item.file !== 'N/A'">
              <span style="color: #666;">文件:</span>
              <span style="word-break: break-all;">{{ item.file }}</span>
            </template>

            <template v-if="item.symbol && item.symbol !== 'N/A'">
              <span style="color: #666;">符号:</span>
              <span style="word-break: break-all;">{{ item.symbol }}</span>
            </template>
          </div>
        </div>
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

// 下钻状态管理
type DrillDownLevel = 'overview' | 'category' | 'subCategory';
const drillDownLevel = ref<DrillDownLevel>('overview');
const selectedCategory = ref<string>('');
const selectedSubCategory = ref<string>('');

// Tooltip 数据
interface TooltipItem {
  seriesName: string;
  color: string;
  cumulativeMemory: string;
  eventType?: string;
  subEventType?: string;
  heapSize?: string;
  process?: string;
  thread?: string;
  file?: string;
  symbol?: string;
}

interface TooltipData {
  timePoint: string;
  items: TooltipItem[];
}

const tooltipData = ref<TooltipData | null>(null);

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

// 下钻导航函数
function resetDrillDown() {
  drillDownLevel.value = 'overview';
  selectedCategory.value = '';
  selectedSubCategory.value = '';
  emit('time-point-selected', null);
}

function backToCategory() {
  drillDownLevel.value = 'category';
  selectedSubCategory.value = '';
  emit('time-point-selected', null);
}

function drillDownToCategory(categoryName: string) {
  drillDownLevel.value = 'category';
  selectedCategory.value = categoryName;
  selectedSubCategory.value = '';
  emit('time-point-selected', null);
}

function drillDownToSubCategory(subCategoryName: string) {
  drillDownLevel.value = 'subCategory';
  selectedSubCategory.value = subCategoryName;
  emit('time-point-selected', null);
}

// 使用 computed 缓存处理后的数据
const processedData = computed(() => {
  // 如果数据为空，直接返回
  if (!props.records || props.records.length === 0) {
    return {
      chartData: [],
      seriesData: [],
      maxMemory: 0,
      minMemory: 0,
      finalMemory: 0,
      threshold30: 0,
      threshold60: 0,
    };
  }

  // 按时间排序记录（优化：避免不必要的复制）
  const sortedRecords = props.records.slice().sort((a, b) => a.relativeTs - b.relativeTs);

  // 根据下钻层级过滤数据
  let filteredRecords = sortedRecords;
  if (drillDownLevel.value === 'category') {
    // 只保留选中大类的数据
    filteredRecords = sortedRecords.filter(r => r.categoryName === selectedCategory.value);
  } else if (drillDownLevel.value === 'subCategory') {
    // 只保留选中小类的数据
    filteredRecords = sortedRecords.filter(
      r => r.categoryName === selectedCategory.value && r.subCategoryName === selectedSubCategory.value
    );
  }

  // 根据下钻层级决定如何分组数据
  interface SeriesGroup {
    name: string;
    records: typeof sortedRecords;
  }

  let seriesGroups: SeriesGroup[] = [];

  if (drillDownLevel.value === 'overview') {
    // 总览：先添加总内存线，再添加各大类线
    // 1. 总内存线（所有数据）
    seriesGroups.push({ name: '总内存', records: filteredRecords });

    // 2. 按大类分组（排除 UNKNOWN）
    const categoryMap = new Map<string, typeof sortedRecords>();
    filteredRecords.forEach(record => {
      if (record.categoryName !== 'UNKNOWN') {
        if (!categoryMap.has(record.categoryName)) {
          categoryMap.set(record.categoryName, []);
        }
        categoryMap.get(record.categoryName)!.push(record);
      }
    });
    seriesGroups.push(...Array.from(categoryMap.entries()).map(([name, records]) => ({ name, records })));
  } else if (drillDownLevel.value === 'category') {
    // 大类视图：按小类分组
    const subCategoryMap = new Map<string, typeof sortedRecords>();
    filteredRecords.forEach(record => {
      if (!subCategoryMap.has(record.subCategoryName)) {
        subCategoryMap.set(record.subCategoryName, []);
      }
      subCategoryMap.get(record.subCategoryName)!.push(record);
    });

    let allSeriesGroups = Array.from(subCategoryMap.entries()).map(([name, records]) => ({ name, records }));

    // 性能优化：如果小分类数量过多，只显示内存占用最大的前 20 个
    const MAX_SERIES_IN_CATEGORY_VIEW = 20;
    if (allSeriesGroups.length > MAX_SERIES_IN_CATEGORY_VIEW) {
      console.warn(`[MemoryTimeline] 小分类数量过多 (${allSeriesGroups.length})，只显示内存占用最大的前 ${MAX_SERIES_IN_CATEGORY_VIEW} 个`);

      // 计算每个小分类的最终内存占用
      const seriesWithFinalMemory = allSeriesGroups.map(group => {
        const recordsWithCumulative = calculateCumulativeMemory(group.records);
        const finalMemory = recordsWithCumulative[recordsWithCumulative.length - 1]?.cumulativeMemory || 0;
        return { ...group, finalMemory };
      });

      // 按最终内存降序排序，取前 N 个
      seriesWithFinalMemory.sort((a, b) => Math.abs(b.finalMemory) - Math.abs(a.finalMemory));
      seriesGroups = seriesWithFinalMemory.slice(0, MAX_SERIES_IN_CATEGORY_VIEW);
    } else {
      seriesGroups = allSeriesGroups;
    }
  } else {
    // 小类视图：显示单条总线
    seriesGroups = [{ name: selectedSubCategory.value, records: filteredRecords }];
  }

  // 对于超大数据集（> 50000），使用更激进的优化策略
  const isVeryLargeDataset = filteredRecords.length > 50000;

  // 为每个系列计算累计内存
  interface SeriesData {
    name: string;
    data: Array<{
      index: number;
      relativeTs: number;
      cumulativeMemory: number;
      heapSize: number;
      eventType: string;
      subEventType?: string;
      process?: string;
      thread?: string;
      file?: string;
      symbol?: string;
    }>;
  }

  const seriesData: SeriesData[] = [];
  let maxMemory = -Infinity;
  let minMemory = Infinity;

  // 收集所有唯一时间点（不进行采样，使用全部数据）
  const allTimePoints = new Set<number>();
  filteredRecords.forEach(record => allTimePoints.add(record.relativeTs));
  const sortedTimePoints = Array.from(allTimePoints).sort((a, b) => a - b);

  seriesGroups.forEach(group => {
    const recordsWithCumulative = calculateCumulativeMemory(group.records);

    // 创建时间点到记录的映射（优化：避免每次都用 find）
    const timeToRecordMap = new Map<number, typeof recordsWithCumulative[0]>();
    recordsWithCumulative.forEach(record => {
      timeToRecordMap.set(record.relativeTs, record);
    });

    // 为每个时间点填充数据（如果该系列在该时间点没有数据，使用前一个时间点的值）
    let lastMemory = 0;
    const data = sortedTimePoints.map((ts, index) => {
      const originalRecord = timeToRecordMap.get(ts);
      const memory = originalRecord?.cumulativeMemory ?? lastMemory;
      lastMemory = memory;

      // 更新最大最小值
      if (memory > maxMemory) maxMemory = memory;
      if (memory < minMemory) minMemory = memory;

      if (isVeryLargeDataset) {
        return {
          index,
          relativeTs: ts,
          cumulativeMemory: memory,
          heapSize: originalRecord?.heapSize || 0,
          eventType: originalRecord?.eventType || '',
        };
      }

      return {
        index,
        relativeTs: ts,
        cumulativeMemory: memory,
        heapSize: originalRecord?.heapSize || 0,
        eventType: originalRecord?.eventType || '',
        subEventType: originalRecord?.subEventType,
        process: originalRecord?.process,
        thread: originalRecord?.thread || 'N/A',
        file: originalRecord?.file || 'N/A',
        symbol: originalRecord?.symbol || 'N/A',
      };
    });

    seriesData.push({ name: group.name, data });
  });

  // 构建图表数据（用于兼容性）
  const chartData = sortedTimePoints.map((ts, index) => {
    // 计算该时间点所有系列的总内存
    let totalMemory = 0;
    seriesData.forEach(series => {
      totalMemory += series.data[index]?.cumulativeMemory || 0;
    });

    return {
      index,
      relativeTs: ts,
      cumulativeMemory: totalMemory,
      heapSize: 0,
      eventType: '',
    };
  });

  const finalMemory = chartData[chartData.length - 1]?.cumulativeMemory || 0;

  // 预计算颜色映射范围
  const memoryRange = maxMemory - minMemory;
  const threshold30 = minMemory + memoryRange * 0.3;
  const threshold60 = minMemory + memoryRange * 0.6;

  return {
    chartData,
    seriesData,
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
    const { chartData, seriesData, maxMemory, minMemory, finalMemory } = processedData.value;

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
      text: (() => {
        let title = '内存时间线';
        if (drillDownLevel.value === 'overview') {
          title += ` - 总览 (总内存 + ${seriesData.length - 1} 个大类)`;
        } else if (drillDownLevel.value === 'category') {
          title += ` - ${selectedCategory.value} (${seriesData.length} 个小类)`;
        } else {
          title += ` - ${selectedCategory.value} / ${selectedSubCategory.value}`;
        }
        return title;
      })(),
      subtext: (() => {
        let hint = '';
        if (drillDownLevel.value === 'overview') {
          hint = '💡 点击线条查看大类详情 | ';
        } else if (drillDownLevel.value === 'category') {
          hint = '💡 点击线条查看小类详情 | ';
        } else {
          hint = '💡 点击数据点选择时间点 | ';
        }

        if (props.selectedTimePoint !== null) {
          hint += `🔸 选中: ${formatTime(props.selectedTimePoint)} | `;
        }

        hint += `🔴 峰值: ${formatBytes(maxMemory)} | 最低: ${formatBytes(minMemory)} | 最终: ${formatBytes(finalMemory)}`;
        return hint;
      })(),
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 600,
      },
      subtextStyle: {
        fontSize: 12,
        color: props.selectedTimePoint !== null ? '#ff9800' : '#666',
        fontWeight: props.selectedTimePoint !== null ? 'bold' : 'normal',
      },
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 'middle',
      data: seriesData.map(s => s.name),
      textStyle: {
        fontSize: 12,
      },
      pageButtonItemGap: 5,
      pageButtonGap: 20,
      pageIconSize: 12,
      pageTextStyle: {
        fontSize: 12,
      },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
      },
      // 简化tooltip，只显示基本信息
      formatter: (params: CallbackDataParams | CallbackDataParams[]) => {
        const paramsArray = Array.isArray(params) ? params : [params];
        if (!paramsArray || paramsArray.length === 0) {
          tooltipData.value = null;
          return '';
        }

        // 更新 tooltipData 用于下方显示详细信息
        const firstParam = paramsArray[0];
        const dataIndex = firstParam.dataIndex as number;
        const timePoint = seriesData[0]?.data[dataIndex]?.relativeTs;

        if (timePoint !== undefined) {
          const items: TooltipItem[] = [];

          paramsArray.forEach((param) => {
            const seriesIndex = param.seriesIndex ?? 0;
            const seriesName = param.seriesName ?? '';
            const dataItem = seriesData[seriesIndex]?.data[dataIndex];

            if (dataItem) {
              const item: TooltipItem = {
                seriesName,
                color: param.color as string,
                cumulativeMemory: formatBytes(dataItem.cumulativeMemory),
              };

              if (!isVeryLargeDataset) {
                if (dataItem.eventType) item.eventType = dataItem.eventType;
                if (dataItem.subEventType) item.subEventType = dataItem.subEventType;
                if (dataItem.heapSize) item.heapSize = formatBytes(dataItem.heapSize);
                if (dataItem.process) item.process = dataItem.process;
                if (dataItem.thread && dataItem.thread !== 'N/A') item.thread = dataItem.thread;
                if (dataItem.file && dataItem.file !== 'N/A') item.file = dataItem.file;
                if (dataItem.symbol && dataItem.symbol !== 'N/A') item.symbol = dataItem.symbol;
              }

              items.push(item);
            }
          });

          tooltipData.value = {
            timePoint: formatTime(timePoint),
            items,
          };
        }

        // 返回简化的tooltip内容
        return `<div style="padding: 4px;">时间: ${formatTime(timePoint)}<br/>详细信息见下方</div>`;
      },
    },
    grid: {
      left: '3%',
      right: '15%', // 为右侧图例留出空间
      bottom: '8%',
      top: '15%',
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
    series: seriesData.map((series, seriesIndex) => {
      // 判断是否是总内存线（总览视图的第一条线）
      const isTotalMemorySeries = drillDownLevel.value === 'overview' && seriesIndex === 0;

      // 为每个系列分配不同的颜色
      const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
      const seriesColor = isTotalMemorySeries ? '#333333' : colors[seriesIndex % colors.length];

      return {
        name: series.name,
        type: 'line',
        data: series.data.map((item) => {
          // 找到峰值点的索引
          const isPeak = item.cumulativeMemory === maxMemory;
          // 找到选中点的索引（仅在小类视图中显示）
          const isSelected = drillDownLevel.value === 'subCategory' &&
                            props.selectedTimePoint !== null &&
                            item.relativeTs === props.selectedTimePoint;

          // 根据状态返回不同的配置
          if (isPeak) {
            return {
              value: item.cumulativeMemory,
              itemStyle: {
                color: '#ff0000',
                borderColor: '#fff',
                borderWidth: 3,
                shadowBlur: 20,
                shadowColor: 'rgba(255, 0, 0, 0.8)',
              },
              symbolSize: 18,
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
                color: '#FFD700',
                borderColor: '#fff',
                borderWidth: 5,
                shadowBlur: 30,
                shadowColor: 'rgba(255, 215, 0, 1)',
              },
              symbolSize: 24,
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
        symbol: 'circle',
        showSymbol: true,
        lineStyle: {
          // 总内存线更粗，更突出
          width: isTotalMemorySeries
            ? (isVeryLargeDataset ? 2 : (isLargeDataset ? 2.5 : 3))
            : (isVeryLargeDataset ? 0.8 : (isLargeDataset ? 1 : 1.5)),
          color: seriesColor,
          // 总内存线使用实线，分类线可以考虑使用虚线（可选）
          type: isTotalMemorySeries ? 'solid' : 'solid',
        },
        emphasis: {
          disabled: false,
          focus: 'series',
          scale: false,
        },
        progressive: isVeryLargeDataset ? 500 : (isLargeDataset ? 1000 : 0),
        progressiveThreshold: isVeryLargeDataset ? 500 : 1000,
        progressiveChunkMode: 'mod' as const,
        // 总内存线的 z-index 更高，确保在最上层
        z: isTotalMemorySeries ? 10 : 5,
      };
    }),
  };

    chartInstance.setOption(option, {
      replaceMerge: ['series'], // 只替换 series，保留其他配置
      lazyUpdate: isVeryLargeDataset, // 超大数据集时使用延迟更新
      silent: false, // 不静默更新，确保样式正确应用
    });

    // 添加点击事件监听
    chartInstance.off('click'); // 先移除旧的监听器
    chartInstance.on('click', (params: { componentType?: string; dataIndex?: number; seriesIndex?: number; seriesName?: string }) => {
      if (params.componentType === 'series' && typeof params.dataIndex === 'number') {
        const dataIndex = params.dataIndex;
        const seriesIndex = params.seriesIndex ?? 0;
        const seriesName = params.seriesName ?? '';

        // 根据当前层级决定点击行为
        if (drillDownLevel.value === 'overview') {
          // 总览视图：点击线条下钻到大类
          // 过滤掉"总内存"线的点击，因为它不是一个真正的分类
          if (seriesName !== '总内存') {
            drillDownToCategory(seriesName);
          }
        } else if (drillDownLevel.value === 'category') {
          // 大类视图：点击线条下钻到小类
          drillDownToSubCategory(seriesName);
        } else {
          // 小类视图：点击数据点选择时间点
          const dataItem = seriesData[seriesIndex]?.data[dataIndex];
          if (dataItem) {
            // 如果点击的是已选中的点，则取消选择
            if (props.selectedTimePoint === dataItem.relativeTs) {
              emit('time-point-selected', null);
            } else {
              emit('time-point-selected', dataItem.relativeTs);
            }
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

// 监听下钻状态的变化，重新初始化图表
watch(
  [drillDownLevel, selectedCategory, selectedSubCategory],
  () => {
    if (chartInstance) {
      initChart();
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

