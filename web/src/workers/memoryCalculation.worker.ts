/**
 * Web Worker for Native Memory Calculation
 * 用于在后台线程中执行内存数据的聚合和统计计算，避免阻塞主线程
 */

import type { NativeMemoryRecord } from '@/stores/jsonDataStore';
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
function getEventTypeName(eventType: string, subEventType: string): string {
  if (eventType === 'AllocEvent' || eventType === 'FreeEvent') {
    return 'AllocEvent';
  } else if (eventType === 'MmapEvent' || eventType === 'MunmapEvent') {
    return subEventType && subEventType.trim() !== '' ? subEventType : 'Other MmapEvent';
  }
  return eventType || 'Unknown';
}

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
    const eventType = record.eventType;
    const size = record.heapSize || 0;

    if (eventType === 'AllocEvent' || eventType === 'MmapEvent') {
      currentMem += size;
      totalAllocMem += size;
      allocEventNum++;
    } else if (eventType === 'FreeEvent' || eventType === 'MunmapEvent') {
      currentMem -= size;
      totalFreeMem += size;
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

  const result: any[] = [];
  processMap.forEach((records, processName) => {
    const stats = calculateMemoryStats(records);
    result.push({
      process: processName,
      ...stats,
    });
  });

  return result.sort((a, b) => b.peakMem - a.peakMem);
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

  const result: any[] = [];
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

  return result.sort((a, b) => b.peakMem - a.peakMem);
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

  const result: any[] = [];
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

  return result.sort((a, b) => b.peakMem - a.peakMem);
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

  const result: any[] = [];
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

  return result.sort((a, b) => b.peakMem - a.peakMem);
}

// ============ Worker 消息处理 ============

self.onmessage = (e: MessageEvent) => {
  const { type, payload, requestId } = e.data;

  try {
    let result: any;

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

