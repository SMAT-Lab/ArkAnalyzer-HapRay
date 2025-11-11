import type { NativeMemoryData, NativeMemoryRecord } from '@/stores/nativeMemory';
import { MemType } from '@/stores/nativeMemory';
import { ComponentCategory } from '@/stores/jsonDataStore';

/**
 * 计算当前内存数据
 *
 * 根据记录的 heapSize 和 eventType 实时计算每个时间点的当前内存值
 *
 * @param records - 内存记录数组（必须已按 relativeTs 排序）
 * @returns 包含当前内存值的记录数组
 */
export interface RecordWithCumulativeMemory extends NativeMemoryRecord {
  cumulativeMemory: number;  // 当前内存值（字节）
}

export function calculateCumulativeMemory(records: NativeMemoryRecord[]): RecordWithCumulativeMemory[] {
  let currentTotal = 0;

  return records.map(record => {
    // 根据事件类型更新当前内存
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

/**
 * 获取大类名称
 * 参考 PerfAnalyzerBase 的分类逻辑，但针对 Native Memory 数据进行优化
 */
export function getCategoryName(category: number | string): string {
  const categoryNum = typeof category === 'string' ? parseInt(category) : category;
  return ComponentCategory[categoryNum] || `Unknown(${category})`;
}

/**
 * 获取小类名称
 * 根据文件路径和组件名称推断小类
 * 参考 PerfAnalyzerBase 的分类逻辑
 */
export function getSubCategoryName(file: string | null | undefined, componentName: string | null | undefined, category: number): string {
  // 如果没有文件信息，使用组件名称作为小类
  if (!file) {
    return componentName || 'Unknown';
  }

  // 对于应用相关的分类，提取更细致的小类信息
  if (category === ComponentCategory.APP_ABC || category === ComponentCategory.APP_LIB) {
    // 从文件路径中提取包名或模块名
    const match = file.match(/\/([^/]+)\/([^/]+)\/([^/]+)/);
    if (match) {
      return match[2]; // 返回中间部分作为小类
    }
  }

  // 对于系统库，使用文件名作为小类
  if (category === ComponentCategory.SYS_SDK) {
    const fileName = file.split('/').pop() || file;
    return fileName;
  }

  // 默认使用组件名称
  return componentName || 'Unknown';
}

export function getMemTypeName(memType: MemType): string {
  switch (memType) {
    case MemType.Process:
      return '进程';
    case MemType.Thread:
      return '线程';
    case MemType.File:
      return '文件';
    case MemType.Symbol:
      return '符号';
    default:
      return 'Unknown';
  }
}

/**
 * 获取事件类型名称
 * 根据 eventType 和 subEventType 确定事件类型名称
 * - AllocEvent/FreeEvent: 'AllocEvent' (FreeEvent 归属到 AllocEvent)
 * - MmapEvent/MunmapEvent: 如果 subEventType 不为空则使用 subEventType，否则使用 'Other MmapEvent'
 */
export function getEventTypeName(eventType: string, subEventType: string): string {
  if (eventType === 'AllocEvent' || eventType === 'FreeEvent') {
    return 'AllocEvent';
  } else if (eventType === 'MmapEvent' || eventType === 'MunmapEvent') {
    return subEventType && subEventType.trim() !== '' ? subEventType : 'Other MmapEvent';
  }
  return eventType || 'Unknown';
}

/**
 * 核心计算函数：按时间顺序计算内存统计
 *
 * @param records 原始事件记录数组
 * @returns 计算结果：峰值内存、平均内存、总分配内存、总释放内存、事件数量、分配事件数、释放事件数、最早时间戳
 */
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

export function calculateMemoryStats(records: NativeMemoryRecord[]): MemoryStats {
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

  // 按时间排序
  const sortedRecords = [...records].sort((a, b) => a.relativeTs - b.relativeTs);

  let currentMem = 0;
  let peakMem = 0;
  let totalAllocMem = 0;
  let totalFreeMem = 0;
  let memSum = 0;
  let eventNum = 0;
  let allocEventNum = 0;
  let freeEventNum = 0;

  for (const record of sortedRecords) {
    eventNum++;

    // 根据事件类型更新当前内存
    // 分配事件：heapSize 为正数，增加内存
    // 释放事件：heapSize 为正数，减少内存
    if (record.eventType === 'AllocEvent' || record.eventType === 'MmapEvent') {
      currentMem += record.heapSize;
      totalAllocMem += record.heapSize;
      allocEventNum++;
    } else if (record.eventType === 'FreeEvent' || record.eventType === 'MunmapEvent') {
      currentMem -= record.heapSize;
      totalFreeMem += record.heapSize;
      freeEventNum++;
    }

    // 确保当前内存不为负数
    if (currentMem < 0) {
      currentMem = 0;
    }

    // 更新峰值
    peakMem = Math.max(peakMem, currentMem);

    // 累加用于计算平均值
    memSum += currentMem;
  }

  const avgMem = eventNum > 0 ? memSum / eventNum : 0;
  const start_ts = sortedRecords[0].relativeTs;

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

// 定义Native Memory数据类型接口
// 新的计算逻辑：
// - peakMem: 峰值内存（按时间顺序计算的最大净内存）
// - avgMem: 平均内存（所有时间点净内存的平均值）
// - totalAllocMem: 总分配内存（所有 Alloc/Mmap 事件的累加）
// - totalFreeMem: 总释放内存（所有 Free/Munmap 事件的累加）

export interface ProcessMemoryItem {
  [key: string]: string | number | undefined;
  stepId: number;
  process: string;
  category: string;
  componentName: string;
  categoryName: string;      // 大类名称（如 'APP_ABC', 'SYS_SDK'）
  subCategoryName: string;   // 小类名称（如包名、文件名、线程名）
  eventNum: number;
  allocEventNum: number;
  freeEventNum: number;
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
  start_ts: number;
}

export interface ThreadMemoryItem {
  [key: string]: string | number | undefined;
  stepId: number;
  process: string;
  thread: string;
  category: string;
  componentName: string;
  categoryName: string;      // 大类名称（如 'APP_ABC', 'SYS_SDK'）
  subCategoryName: string;   // 小类名称（如包名、文件名、线程名）
  eventNum: number;
  allocEventNum: number;
  freeEventNum: number;
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
  start_ts: number;
}

export interface FileMemoryItem {
  [key: string]: string | number | undefined;
  stepId: number;
  process: string;
  thread: string;
  file: string;
  category: string;
  componentName: string;
  categoryName: string;      // 大类名称（如 'APP_ABC', 'SYS_SDK'）
  subCategoryName: string;   // 小类名称（如包名、文件名、线程名）
  eventNum: number;
  allocEventNum: number;
  freeEventNum: number;
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
  start_ts: number;
}

export interface SymbolMemoryItem {
  [key: string]: string | number | undefined;
  stepId: number;
  process: string;
  thread: string;
  file: string;
  symbol: string;
  category: string;
  componentName: string;
  categoryName: string;      // 大类名称（如 'APP_ABC', 'SYS_SDK'）
  subCategoryName: string;   // 小类名称（如包名、文件名、线程名）
  eventNum: number;
  allocEventNum: number;
  freeEventNum: number;
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
  start_ts: number;
}

// 事件类型维度的内存数据
export interface EventTypeMemoryItem {
  [key: string]: string | number | undefined;
  stepId: number;
  eventTypeName: string;      // 事件类型名称（AllocEvent/FreeEvent/subEventType/Other MmapEvent）
  eventNum: number;
  allocEventNum: number;
  freeEventNum: number;
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
}

/**
 * 根据时间点过滤记录
 * 优化：使用二分查找快速定位，假设数据已按时间排序
 * @param records 原始记录数组（必须已按 relativeTs 排序）
 * @param timePoint 时间点（纳秒），如果为null则返回所有记录
 * @returns 过滤后的记录数组
 */
export function filterRecordsByTime(records: NativeMemoryRecord[], timePoint: number | null): NativeMemoryRecord[] {
  if (timePoint === null) {
    return records;
  }

  // 优化：使用二分查找找到第一个 > timePoint 的位置
  // 假设数据已经按 relativeTs 排序（在 jsonDataStore 加载时已排序）
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

/**
 * 使用二分查找找到时间点对应的记录索引
 * @param records 原始记录数组（必须已按 relativeTs 排序）
 * @param timePoint 时间点（纳秒），如果为null则返回数组长度
 * @returns 第一个 > timePoint 的位置索引
 */
export function findTimePointIndex(records: NativeMemoryRecord[], timePoint: number | null): number {
  if (timePoint === null) {
    return records.length;
  }

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

  return left;
}

// 处理Native Memory数据生成进程负载饼状图所需数据
// 按进程维度计算峰值内存，用于饼图展示
// 优化：使用分片处理，避免一次性遍历大量数据导致主线程阻塞
export async function nativeMemory2ProcessPieChartData(
  nativeMemoryData: NativeMemoryData | null,
  currentStepIndex: number,
  timePoint: number | null = null
): Promise<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }> {
  if (!nativeMemoryData) {
    return { legendData: [], seriesData: [] };
  }

  const stepKey = `step${currentStepIndex}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) {
    return { legendData: [], seriesData: [] };
  }

  const records = stepData.records;

  // 优化：使用二分查找找到时间点对应的索引
  const endIndex = findTimePointIndex(records, timePoint);

  // 按进程分组，直接计算每个进程的内存统计
  const processStatsMap = new Map<string, { currentMem: number; peakMem: number }>();

  // 分片处理：每次处理 1000 条记录，避免阻塞主线程
  const CHUNK_SIZE = 1000;
  const totalChunks = Math.ceil(endIndex / CHUNK_SIZE);

  console.log(`[进程饼图] 开始分片处理: ${endIndex} 条记录，分为 ${totalChunks} 片`);

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const start = chunkIndex * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, endIndex);

    // 处理当前分片
    for (let i = start; i < end; i++) {
      const item = records[i];
      const processName = item.process || "Unknown Process";

      if (!processStatsMap.has(processName)) {
        processStatsMap.set(processName, { currentMem: 0, peakMem: 0 });
      }

      const stats = processStatsMap.get(processName)!;

      // 根据事件类型更新当前内存
      if (item.eventType === 'AllocEvent' || item.eventType === 'MmapEvent') {
        stats.currentMem += item.heapSize;
      } else if (item.eventType === 'FreeEvent' || item.eventType === 'MunmapEvent') {
        stats.currentMem -= item.heapSize;
      }

      // 更新峰值
      if (stats.currentMem > stats.peakMem) {
        stats.peakMem = stats.currentMem;
      }
    }

    // 每处理完一个分片，让出主线程给浏览器渲染
    // 每 50 片输出一次进度
    if ((chunkIndex + 1) % 50 === 0 || chunkIndex === totalChunks - 1) {
      console.log(`[进程饼图] 进度: ${chunkIndex + 1}/${totalChunks} (${((chunkIndex + 1) / totalChunks * 100).toFixed(1)}%)`);
    }

    if (chunkIndex < totalChunks - 1) {
      // 使用 setTimeout 让出主线程，给浏览器更多时间响应
      await new Promise(resolve => setTimeout(resolve, 5));
    }
  }

  console.log(`[进程饼图] 分片处理完成`);


  // 构建结果数组
  const processEntries: [string, number][] = [];
  processStatsMap.forEach((stats, processName) => {
    if (stats.peakMem > 0) {
      processEntries.push([processName, stats.peakMem]);
    }
  });

  // 排序
  processEntries.sort((a, b) => b[1] - a[1]);

  const legendData = processEntries.map(([name]) => name);
  const seriesData = processEntries.map(([name, value]) => ({ name, value }));

  return { legendData, seriesData };
}

// 处理Native Memory数据生成分类负载饼状图所需数据（按大类聚合）
// 按大分类维度计算峰值内存，用于饼图展示
// 优化：使用分片处理，避免一次性遍历大量数据导致主线程阻塞
export async function nativeMemory2CategoryPieChartData(
  nativeMemoryData: NativeMemoryData | null,
  currentStepIndex: number,
  timePoint: number | null = null
): Promise<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }> {
  if (!nativeMemoryData) {
    return { legendData: [], seriesData: [] };
  }

  const stepKey = `step${currentStepIndex}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) {
    return { legendData: [], seriesData: [] };
  }

  const records = stepData.records;

  // 优化：使用二分查找找到时间点对应的索引
  const endIndex = findTimePointIndex(records, timePoint);

  // 按大分类分组，直接计算每个分类的内存统计
  const categoryStatsMap = new Map<number, { currentMem: number; peakMem: number }>();

  // 分片处理：每次处理 1000 条记录，避免阻塞主线程
  const CHUNK_SIZE = 1000;
  const totalChunks = Math.ceil(endIndex / CHUNK_SIZE);

  console.log(`[分类饼图] 开始分片处理: ${endIndex} 条记录，分为 ${totalChunks} 片`);

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const start = chunkIndex * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, endIndex);

    // 处理当前分片
    for (let i = start; i < end; i++) {
      const item = records[i];
      const category = item.componentCategory;

      if (!categoryStatsMap.has(category)) {
        categoryStatsMap.set(category, { currentMem: 0, peakMem: 0 });
      }

      const stats = categoryStatsMap.get(category)!;

      // 根据事件类型更新当前内存
      if (item.eventType === 'AllocEvent' || item.eventType === 'MmapEvent') {
        stats.currentMem += item.heapSize;
      } else if (item.eventType === 'FreeEvent' || item.eventType === 'MunmapEvent') {
        stats.currentMem -= item.heapSize;
      }

      // 更新峰值
      if (stats.currentMem > stats.peakMem) {
        stats.peakMem = stats.currentMem;
      }
    }

    // 每处理完一个分片，让出主线程给浏览器渲染
    // 每 50 片输出一次进度
    if ((chunkIndex + 1) % 50 === 0 || chunkIndex === totalChunks - 1) {
      console.log(`[分类饼图] 进度: ${chunkIndex + 1}/${totalChunks} (${((chunkIndex + 1) / totalChunks * 100).toFixed(1)}%)`);
    }

    if (chunkIndex < totalChunks - 1) {
      await new Promise(resolve => setTimeout(resolve, 5));
    }
  }

  console.log(`[分类饼图] 分片处理完成`);

  // 构建结果数组
  const categoryEntries: [string, number][] = [];
  categoryStatsMap.forEach((stats, category) => {
    if (stats.peakMem > 0) {
      categoryEntries.push([getCategoryName(category), stats.peakMem]);
    }
  });

  // 排序
  categoryEntries.sort((a, b) => b[1] - a[1]);

  const legendData = categoryEntries.map(([name]) => name);
  const seriesData = categoryEntries.map(([name, value]) => ({ name, value }));

  return { legendData, seriesData };
}

// 处理Native Memory数据生成事件类型负载饼状图所需数据
// 按事件类型维度计算峰值内存，用于饼图展示
// 优化：使用分片处理，避免一次性遍历大量数据导致主线程阻塞
export async function nativeMemory2EventTypePieChartData(
  nativeMemoryData: NativeMemoryData | null,
  currentStepIndex: number,
  timePoint: number | null = null
): Promise<{ legendData: string[]; seriesData: Array<{ name: string; value: number }> }> {
  if (!nativeMemoryData) {
    return { legendData: [], seriesData: [] };
  }

  const stepKey = `step${currentStepIndex}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) {
    return { legendData: [], seriesData: [] };
  }

  const records = stepData.records;

  // 优化：使用二分查找找到时间点对应的索引
  const endIndex = findTimePointIndex(records, timePoint);

  // 按事件类型分组，直接计算每个事件类型的内存统计
  const eventTypeStatsMap = new Map<string, { currentMem: number; peakMem: number }>();

  // 分片处理：每次处理 1000 条记录，避免阻塞主线程
  const CHUNK_SIZE = 1000;
  const totalChunks = Math.ceil(endIndex / CHUNK_SIZE);

  console.log(`[事件类型饼图] 开始分片处理: ${endIndex} 条记录，分为 ${totalChunks} 片`);

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const start = chunkIndex * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, endIndex);

    // 处理当前分片
    for (let i = start; i < end; i++) {
      const item = records[i];
      const eventTypeName = getEventTypeName(item.eventType, item.subEventType);

      if (!eventTypeStatsMap.has(eventTypeName)) {
        eventTypeStatsMap.set(eventTypeName, { currentMem: 0, peakMem: 0 });
      }

      const stats = eventTypeStatsMap.get(eventTypeName)!;

      // 根据事件类型更新当前内存
      if (item.eventType === 'AllocEvent' || item.eventType === 'MmapEvent') {
        stats.currentMem += item.heapSize;
      } else if (item.eventType === 'FreeEvent' || item.eventType === 'MunmapEvent') {
        stats.currentMem -= item.heapSize;
      }

      // 更新峰值
      if (stats.currentMem > stats.peakMem) {
        stats.peakMem = stats.currentMem;
      }
    }

    // 每处理完一个分片，让出主线程给浏览器渲染
    // 每 50 片输出一次进度
    if ((chunkIndex + 1) % 50 === 0 || chunkIndex === totalChunks - 1) {
      console.log(`[事件类型饼图] 进度: ${chunkIndex + 1}/${totalChunks} (${((chunkIndex + 1) / totalChunks * 100).toFixed(1)}%)`);
    }

    if (chunkIndex < totalChunks - 1) {
      await new Promise(resolve => setTimeout(resolve, 5));
    }
  }

  console.log(`[事件类型饼图] 分片处理完成`);

  // 构建结果数组
  const eventTypeEntries: [string, number][] = [];
  eventTypeStatsMap.forEach((stats, eventTypeName) => {
    if (stats.peakMem > 0) {
      eventTypeEntries.push([eventTypeName, stats.peakMem]);
    }
  });

  // 排序
  eventTypeEntries.sort((a, b) => b[1] - a[1]);

  const legendData = eventTypeEntries.map(([name]) => name);
  const seriesData = eventTypeEntries.map(([name, value]) => ({ name, value }));

  return { legendData, seriesData };
}

// 聚合函数：按进程聚合
// 进程维度的 key 是：process
// 支持时间点过滤，实时计算统计信息
export function aggregateByProcess(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): ProcessMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按进程分组
  const processRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const processName = item.process || "Unknown Process";
    if (!processRecordsMap.has(processName)) {
      processRecordsMap.set(processName, []);
    }
    processRecordsMap.get(processName)!.push(item);
  });

  // 计算每个进程的统计信息
  const result: ProcessMemoryItem[] = [];
  processRecordsMap.forEach((records, processName) => {
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];

    result.push({
      stepId,
      process: processName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: processName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按线程聚合
// 线程维度的 key 是：process|thread
// 支持时间点过滤，实时计算统计信息
export function aggregateByThread(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): ThreadMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按进程+线程分组
  const threadRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    // 只处理有 tid 的记录
    if (item.tid === null || item.tid === undefined) return;

    const processName = item.process || "Unknown Process";
    const threadName = item.thread || "Unknown Thread";
    const key = `${processName}|${threadName}`;

    if (!threadRecordsMap.has(key)) {
      threadRecordsMap.set(key, []);
    }
    threadRecordsMap.get(key)!.push(item);
  });

  // 计算每个线程的统计信息
  const result: ThreadMemoryItem[] = [];
  threadRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];
    const [processName, threadName] = key.split('|');

    result.push({
      stepId,
      process: processName,
      thread: threadName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: threadName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按文件聚合
// 文件维度的 key 是：process|thread|file
// 支持时间点过滤，实时计算统计信息
export function aggregateByFile(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): FileMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按进程+线程+文件分组
  const fileRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    // 只处理有 fileId 的记录
    if (item.fileId === null || item.fileId === undefined) return;

    const processName = item.process || "Unknown Process";
    const threadName = item.thread || "Unknown Thread";
    const fileName = item.file || "Unknown File";
    const key = `${processName}|${threadName}|${fileName}`;

    if (!fileRecordsMap.has(key)) {
      fileRecordsMap.set(key, []);
    }
    fileRecordsMap.get(key)!.push(item);
  });

  // 计算每个文件的统计信息
  const result: FileMemoryItem[] = [];
  fileRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];
    const [processName, threadName, fileName] = key.split('|');

    result.push({
      stepId,
      process: processName,
      thread: threadName,
      file: fileName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: fileName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按符号聚合
// 符号维度的 key 是：process|thread|file|symbol
// 支持时间点过滤，实时计算统计信息
export function aggregateBySymbol(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): SymbolMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按进程+线程+文件+符号分组
  const symbolRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    // 只处理有 symbolId 的记录
    if (item.symbolId === null || item.symbolId === undefined) return;

    const processName = item.process || "Unknown Process";
    const threadName = item.thread || "Unknown Thread";
    const fileName = item.file || "Unknown File";
    const symbolName = item.symbol || "Unknown Symbol";
    const key = `${processName}|${threadName}|${fileName}|${symbolName}`;

    if (!symbolRecordsMap.has(key)) {
      symbolRecordsMap.set(key, []);
    }
    symbolRecordsMap.get(key)!.push(item);
  });

  // 计算每个符号的统计信息
  const result: SymbolMemoryItem[] = [];
  symbolRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];
    const [processName, threadName, fileName, symbolName] = key.split('|');

    result.push({
      stepId,
      process: processName,
      thread: threadName,
      file: fileName,
      symbol: symbolName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: symbolName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按大类聚合
// 大分类维度的 key 是：categoryName
// 支持时间点过滤，实时计算统计信息
export function aggregateByCategory(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): ThreadMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按大分类分组
  const categoryRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const categoryName = item.categoryName;
    if (!categoryRecordsMap.has(categoryName)) {
      categoryRecordsMap.set(categoryName, []);
    }
    categoryRecordsMap.get(categoryName)!.push(item);
  });

  // 计算每个大分类的统计信息
  const result: ThreadMemoryItem[] = [];
  categoryRecordsMap.forEach((records, categoryName) => {
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];

    result.push({
      stepId,
      process: categoryName,
      thread: categoryName,
      category: categoryName,
      componentName: '',
      categoryName: categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按小类（子分类）聚合
// 小分类维度的 key 是：categoryName|subCategoryName
// 支持时间点过滤，实时计算统计信息
export function aggregateByComponent(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): ThreadMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按大分类+小分类分组
  const componentRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const key = `${item.categoryName}|${item.subCategoryName}`;
    if (!componentRecordsMap.has(key)) {
      componentRecordsMap.set(key, []);
    }
    componentRecordsMap.get(key)!.push(item);
  });

  // 计算每个小分类的统计信息
  const result: ThreadMemoryItem[] = [];
  componentRecordsMap.forEach((records) => {
    const stats = calculateMemoryStats(records);
    const firstRecord = records[0];

    result.push({
      stepId,
      process: firstRecord.subCategoryName,
      thread: firstRecord.subCategoryName,
      category: firstRecord.categoryName,
      componentName: firstRecord.subCategoryName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按文件聚合（分类维度）
// 文件维度的 key 是：categoryName|subCategoryName|file
// 支持时间点过滤，实时计算统计信息
export function aggregateByFileCategory(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): FileMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按大分类+小分类+文件分组原始事件记录
  const fileRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    // 只处理有 fileId 的记录
    if (item.fileId === null || item.fileId === undefined) return;

    const fileName = item.file || "Unknown File";
    const key = `${item.categoryName}|${item.subCategoryName}|${fileName}`;

    if (!fileRecordsMap.has(key)) {
      fileRecordsMap.set(key, []);
    }
    fileRecordsMap.get(key)!.push(item);
  });

  // 计算每个文件的内存统计
  const result: FileMemoryItem[] = [];
  fileRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
    const [categoryName, subCategoryName, fileName] = key.split('|');

    result.push({
      stepId,
      process: subCategoryName,
      thread: subCategoryName,
      file: fileName,
      category: categoryName,
      componentName: subCategoryName,
      categoryName: categoryName,
      subCategoryName: subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按符号聚合（分类维度）
// 符号维度的 key 是：categoryName|subCategoryName|file|symbol
// 支持时间点过滤，实时计算统计信息
export function aggregateBySymbolCategory(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): SymbolMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按大分类+小分类+文件+符号分组原始事件记录
  const symbolRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    // 只处理有 symbolId 的记录
    if (item.symbolId === null || item.symbolId === undefined) return;

    const fileName = item.file || "Unknown File";
    const symbolName = item.symbol || "Unknown Symbol";
    const key = `${item.categoryName}|${item.subCategoryName}|${fileName}|${symbolName}`;

    if (!symbolRecordsMap.has(key)) {
      symbolRecordsMap.set(key, []);
    }
    symbolRecordsMap.get(key)!.push(item);
  });

  // 计算每个符号的内存统计
  const result: SymbolMemoryItem[] = [];
  symbolRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
    const [categoryName, subCategoryName, fileName, symbolName] = key.split('|');

    result.push({
      stepId,
      process: subCategoryName,
      thread: subCategoryName,
      file: fileName,
      symbol: symbolName,
      category: categoryName,
      componentName: subCategoryName,
      categoryName: categoryName,
      subCategoryName: subCategoryName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
      start_ts: stats.start_ts,
    });
  });

  return result;
}

// 聚合函数：按事件类型聚合
// 事件类型维度的 key 是：eventTypeName
// 支持时间点过滤，实时计算统计信息
export function aggregateByEventType(
  nativeMemoryData: NativeMemoryData | null,
  stepId: number,
  timePoint: number | null = null
): EventTypeMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 根据时间点过滤记录
  const filteredRecords = filterRecordsByTime(stepData.records, timePoint);

  // 按事件类型分组
  const eventTypeRecordsMap = new Map<string, NativeMemoryRecord[]>();

  filteredRecords.forEach(item => {
    const eventTypeName = getEventTypeName(item.eventType, item.subEventType);
    if (!eventTypeRecordsMap.has(eventTypeName)) {
      eventTypeRecordsMap.set(eventTypeName, []);
    }
    eventTypeRecordsMap.get(eventTypeName)!.push(item);
  });

  // 计算每个事件类型的统计信息
  const result: EventTypeMemoryItem[] = [];
  eventTypeRecordsMap.forEach((records, eventTypeName) => {
    const stats = calculateMemoryStats(records);

    result.push({
      stepId,
      eventTypeName,
      eventNum: stats.eventNum,
      allocEventNum: stats.allocEventNum,
      freeEventNum: stats.freeEventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
    });
  });

  return result.sort((a, b) => b.peakMem - a.peakMem);
}

