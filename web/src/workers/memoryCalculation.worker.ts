/**
 * Web Worker for Native Memory Calculation
 * 用于在后台线程中执行内存数据的聚合和统计计算，避免阻塞主线程
 */

import type { NativeMemoryRecord } from '@/stores/nativeMemory';
import { ComponentCategory } from '@/stores/jsonDataStore';

// ============ 工具函数 ============

/**
 * 获取大类名称
 */
function getCategoryName(category: number | string): string {
  const categoryNum = typeof category === 'string' ? parseInt(category) : category;
  return ComponentCategory[categoryNum] || `Unknown(${category})`;
}
/**
 * 获取事件类型名称
 */
// function getEventTypeName(eventType: string, subEventType: string): string {
//   if (eventType === 'AllocEvent' || eventType === 'FreeEvent') {
//     return 'AllocEvent';
//   } else if (eventType === 'MmapEvent' || eventType === 'MunmapEvent') {
//     return subEventType && subEventType.trim() !== '' ? subEventType : 'Other MmapEvent';
//   }
//   return eventType || 'Unknown';
// }
/**
 * 按时间点过滤记录
 * 优化：假设数据已按时间排序，使用二分查找快速定位
 */
function filterRecordsByTime(records: NativeMemoryRecord[], timePoint: number | null): NativeMemoryRecord[] {
  if (timePoint === null) {
    return records;
  }

  // 优化：使用二分查找找到第一个 > timePoint 的位置
  // 假设数据已经按 relativeTs 排序
  let left = 0;
  let right = records.length;

  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    if (records[mid].relativeTs <= timePoint) {
      left = mid + 1;
    } else {
      right = mid;
    }
  }

  // left 就是第一个 > timePoint 的位置，返回 [0, left) 的记录
  return records.slice(0, left);
}

// ============ 核心计算函数 ============

interface MemoryStats {
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
  eventNum: number;
  allocEventNum: number;
  freeEventNum: number;
  start_ts: number;
}

/**
 * 计算内存统计信息
 * 优化：假设数据已经按时间排序，避免重复排序
 */
function calculateMemoryStats(records: NativeMemoryRecord[]): MemoryStats {
  if (records.length === 0) {
    return {
      peakMem: 0,
      avgMem: 0,
      totalAllocMem: 0,
      totalFreeMem: 0,
      eventNum: 0,
      allocEventNum: 0,
      freeEventNum: 0,
      start_ts: 0,
    };
  }

  // 优化：不再排序，假设数据已经按时间排序
  // 对于大数据量（如 943734 条记录），排序非常耗时
  // 如果数据确实需要排序，应该在数据加载时排序一次，而不是每次计算都排序

  let currentMem = 0;
  let peakMem = 0;
  let totalAllocMem = 0;
  let totalFreeMem = 0;
  let memSum = 0;
  let eventNum = 0;
  let allocEventNum = 0;
  let freeEventNum = 0;
  let minTs = Infinity;

  for (const record of records) {
    eventNum++;
    // heapSize 存储规则：申请为正数，释放为负数
    const size = record.heapSize || 0;

    // 直接累加 heapSize（申请为正数，释放为负数）
    currentMem += size;

    // 统计分配和释放
    if (size > 0) {
      totalAllocMem += size;
      allocEventNum++;
    } else if (size < 0) {
      totalFreeMem += Math.abs(size);
      freeEventNum++;
    }

    if (currentMem > peakMem) {
      peakMem = currentMem;
    }

    memSum += currentMem;

    // 找到最小时间戳
    if (record.relativeTs < minTs) {
      minTs = record.relativeTs;
    }
  }

  const avgMem = eventNum > 0 ? memSum / eventNum : 0;
  const start_ts = minTs === Infinity ? 0 : minTs;

  return {
    peakMem,
    avgMem,
    totalAllocMem,
    totalFreeMem,
    eventNum,
    allocEventNum,
    freeEventNum,
    start_ts,
  };
}

// ============ 聚合函数 ============

/**
 * 按进程聚合
 */
function aggregateByProcess(records: NativeMemoryRecord[], timePoint: number | null) {
  const filteredRecords = filterRecordsByTime(records, timePoint);
  const processMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const processName = item.process || 'Unknown Process';
    if (!processMap.has(processName)) {
      processMap.set(processName, []);
    }
    processMap.get(processName)!.push(item);
  });

  const result: Array<Record<string, unknown>> = [];
  processMap.forEach((records, processName) => {
    const stats = calculateMemoryStats(records);
    result.push({
      process: processName,
      ...stats,
    });
  });

  return result.sort((a, b) => (b.peakMem as number) - (a.peakMem as number));
}

/**
 * 按线程聚合
 */
function aggregateByThread(records: NativeMemoryRecord[], timePoint: number | null) {
  const filteredRecords = filterRecordsByTime(records, timePoint);
  const threadMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const key = `${item.process || 'Unknown'}|${item.thread || 'Unknown'}`;
    if (!threadMap.has(key)) {
      threadMap.set(key, []);
    }
    threadMap.get(key)!.push(item);
  });

  const result: Array<Record<string, unknown>> = [];
  threadMap.forEach((records, key) => {
    const [processName, threadName] = key.split('|');
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];

    result.push({
      process: processName,
      thread: threadName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: threadName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      ...stats,
    });
  });

  return result.sort((a, b) => (b.peakMem as number) - (a.peakMem as number));
}

/**
 * 按文件聚合
 */
function aggregateByFile(records: NativeMemoryRecord[], timePoint: number | null) {
  const filteredRecords = filterRecordsByTime(records, timePoint);
  const fileMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const key = `${item.process || 'Unknown'}|${item.thread || 'Unknown'}|${item.file || 'Unknown'}`;
    if (!fileMap.has(key)) {
      fileMap.set(key, []);
    }
    fileMap.get(key)!.push(item);
  });

  const result: Array<Record<string, unknown>> = [];
  fileMap.forEach((records, key) => {
    const [processName, threadName, fileName] = key.split('|');
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];

    result.push({
      process: processName,
      thread: threadName,
      file: fileName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: firstRecord.componentName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      ...stats,
    });
  });

  return result.sort((a, b) => (b.peakMem as number) - (a.peakMem as number));
}

/**
 * 按符号聚合
 */
function aggregateBySymbol(records: NativeMemoryRecord[], timePoint: number | null) {
  const filteredRecords = filterRecordsByTime(records, timePoint);
  const symbolMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const key = `${item.process || 'Unknown'}|${item.thread || 'Unknown'}|${item.file || 'Unknown'}|${item.symbol || 'Unknown'}`;
    if (!symbolMap.has(key)) {
      symbolMap.set(key, []);
    }
    symbolMap.get(key)!.push(item);
  });

  const result: Array<Record<string, unknown>> = [];
  symbolMap.forEach((records, key) => {
    const [processName, threadName, fileName, symbolName] = key.split('|');
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];

    result.push({
      process: processName,
      thread: threadName,
      file: fileName,
      symbol: symbolName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: firstRecord.componentName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      ...stats,
    });
  });

  return result.sort((a, b) => (b.peakMem as number) - (a.peakMem as number));
}

/**
 * 计算时间线图表数据
 * 根据下钻级别和过滤条件处理记录，返回图表所需的系列数据
 */
function processTimelineData(
  records: NativeMemoryRecord[],
  drillDownLevel: 'overview' | 'category' | 'subCategory',
  selectedCategory: string,
  selectedSubCategory: string
) {
  // 按时间排序记录
  const sortedRecords = records.slice().sort((a, b) => a.relativeTs - b.relativeTs);

  // 根据下钻层级过滤数据
  let filteredRecords = sortedRecords;
  if (drillDownLevel === 'category') {
    filteredRecords = sortedRecords.filter(r => r.categoryName === selectedCategory);
  } else if (drillDownLevel === 'subCategory') {
    filteredRecords = sortedRecords.filter(
      r => r.categoryName === selectedCategory && r.subCategoryName === selectedSubCategory
    );
  }

  // 根据下钻层级决定如何分组数据
  interface SeriesGroup {
    name: string;
    records: NativeMemoryRecord[];
  }

  let seriesGroups: SeriesGroup[] = [];

  if (drillDownLevel === 'overview') {
    // 总览：先添加总内存线，再添加各大类线
    seriesGroups.push({ name: '总内存', records: filteredRecords });

    // 按大类分组（排除 UNKNOWN）
    const categoryMap = new Map<string, NativeMemoryRecord[]>();
    filteredRecords.forEach(record => {
      if (record.categoryName !== 'UNKNOWN') {
        if (!categoryMap.has(record.categoryName)) {
          categoryMap.set(record.categoryName, []);
        }
        categoryMap.get(record.categoryName)!.push(record);
      }
    });
    seriesGroups.push(...Array.from(categoryMap.entries()).map(([name, records]) => ({ name, records })));
  } else if (drillDownLevel === 'category') {
    // 大类视图：按小类分组
    const subCategoryMap = new Map<string, NativeMemoryRecord[]>();
    filteredRecords.forEach(record => {
      if (!subCategoryMap.has(record.subCategoryName)) {
        subCategoryMap.set(record.subCategoryName, []);
      }
      subCategoryMap.get(record.subCategoryName)!.push(record);
    });

    const allSeriesGroups = Array.from(subCategoryMap.entries()).map(([name, records]) => ({ name, records }));

    // 性能优化：如果小分类数量过多，只显示内存占用最大的前 20 个
    const MAX_SERIES_IN_CATEGORY_VIEW = 20;
    if (allSeriesGroups.length > MAX_SERIES_IN_CATEGORY_VIEW) {
      // 计算每个小分类的最终内存占用
      const seriesWithFinalMemory = allSeriesGroups.map(group => {
        const recordsWithCumulative = calculateCumulativeMemoryInWorker(group.records);
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
    seriesGroups = [{ name: selectedSubCategory, records: filteredRecords }];
  }

  // 收集所有唯一时间点
  const allTimePoints = new Set<number>();
  filteredRecords.forEach(record => allTimePoints.add(record.relativeTs));
  const sortedTimePoints = Array.from(allTimePoints).sort((a, b) => a - b);

  // 为每个系列计算累计内存
  const seriesData: Array<{
    name: string;
    data: Array<{
      index: number;
      relativeTs: number;
      cumulativeMemory: number;
      heapSize: number;
      eventType: string;
    }>;
  }> = [];

  let maxMemory = -Infinity;
  let minMemory = Infinity;

  seriesGroups.forEach(group => {
    const recordsWithCumulative = calculateCumulativeMemoryInWorker(group.records);

    // 创建时间点到记录的映射
    const timeToRecordMap = new Map<number, typeof recordsWithCumulative[0]>();
    recordsWithCumulative.forEach(record => {
      timeToRecordMap.set(record.relativeTs, record);
    });

    // 为每个时间点填充数据
    let lastMemory = 0;
    const data = sortedTimePoints.map((ts, index) => {
      const originalRecord = timeToRecordMap.get(ts);
      const memory = originalRecord?.cumulativeMemory ?? lastMemory;
      lastMemory = memory;

      // 更新最大最小值
      if (memory > maxMemory) maxMemory = memory;
      if (memory < minMemory) minMemory = memory;

      return {
        index,
        relativeTs: ts,
        cumulativeMemory: memory,
        heapSize: originalRecord?.heapSize || 0,
        eventType: originalRecord?.eventType || '',
      };
    });

    seriesData.push({ name: group.name, data });
  });

  // 构建图表数据
  // 在 overview 模式下，chartData 使用第一个系列（总内存）的数据
  // 在其他模式下，chartData 使用所有系列的累计
  const chartData = sortedTimePoints.map((ts, index) => {
    let totalMemory = 0;

    if (drillDownLevel === 'overview' && seriesData.length > 0) {
      // 总览模式：使用第一个系列（总内存）的数据
      totalMemory = seriesData[0].data[index]?.cumulativeMemory || 0;
    } else {
      // 其他模式：累加所有系列
      seriesData.forEach(series => {
        totalMemory += series.data[index]?.cumulativeMemory || 0;
      });
    }

    return {
      index,
      relativeTs: ts,
      cumulativeMemory: totalMemory,
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
}

/**
 * 计算累计内存（Worker 内部版本）
 */
function calculateCumulativeMemoryInWorker(records: NativeMemoryRecord[]) {
  let currentTotal = 0;

  return records.map(record => {
    const eventType = record.eventType;
    const size = record.heapSize || 0;

    if (eventType === 'AllocEvent' || eventType === 'MmapEvent') {
      currentTotal += size;
    } else if (eventType === 'FreeEvent' || eventType === 'MunmapEvent') {
      currentTotal -= size;
    }

    return {
      ...record,
      cumulativeMemory: currentTotal,
    };
  });
}

// ============ Worker 消息处理 ============

self.onmessage = (e: MessageEvent) => {
  const { type, payload, requestId } = e.data;

  try {
    let result: unknown;

    switch (type) {
      case 'aggregateByProcess':
        result = aggregateByProcess(payload.records, payload.timePoint);
        break;
      case 'aggregateByThread':
        result = aggregateByThread(payload.records, payload.timePoint);
        break;
      case 'aggregateByFile':
        result = aggregateByFile(payload.records, payload.timePoint);
        break;
      case 'aggregateBySymbol':
        result = aggregateBySymbol(payload.records, payload.timePoint);
        break;
      case 'processTimelineData':
        result = processTimelineData(
          payload.records,
          payload.drillDownLevel,
          payload.selectedCategory,
          payload.selectedSubCategory
        );
        break;
      default:
        throw new Error(`Unknown worker task type: ${type}`);
    }

    // 发送成功响应
    self.postMessage({
      requestId,
      success: true,
      result,
    });
  } catch (error) {
    // 发送错误响应
    self.postMessage({
      requestId,
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

