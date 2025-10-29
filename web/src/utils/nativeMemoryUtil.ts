import type { NativeMemoryData, NativeMemoryRecord } from '@/stores/jsonDataStore';
import { ComponentCategory, MemType } from '@/stores/jsonDataStore';

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
 * @returns 计算结果：峰值内存、平均内存、总分配内存、总释放内存、事件数量、最早时间戳
 */
interface MemoryStats {
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
  eventNum: number;
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

  for (const record of sortedRecords) {
    eventNum++;

    // 根据事件类型更新当前内存
    if (record.eventType === 'AllocEvent' || record.eventType === 'MmapEvent') {
      currentMem += record.heapSize;
      totalAllocMem += record.heapSize;
    } else if (record.eventType === 'FreeEvent' || record.eventType === 'MunmapEvent') {
      currentMem -= record.heapSize;
      totalFreeMem += record.heapSize;
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
  peakMem: number;
  avgMem: number;
  totalAllocMem: number;
  totalFreeMem: number;
}

// 处理Native Memory数据生成进程负载饼状图所需数据
// 按进程维度计算峰值内存，用于饼图展示
export function nativeMemory2ProcessPieChartData(nativeMemoryData: NativeMemoryData | null, currentStepIndex: number) {
  if (!nativeMemoryData) {
    return { legendData: [], seriesData: [] };
  }

  const stepKey = `step${currentStepIndex}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) {
    return { legendData: [], seriesData: [] };
  }

  // 按进程分组
  const processRecordsMap = new Map<string, NativeMemoryRecord[]>();

  stepData.records.forEach(item => {
    const processName = item.process || "Unknown Process";
    if (!processRecordsMap.has(processName)) {
      processRecordsMap.set(processName, []);
    }
    processRecordsMap.get(processName)!.push(item);
  });

  // 计算每个进程的峰值内存
  const processEntries: [string, number][] = [];
  processRecordsMap.forEach((records, processName) => {
    const stats = calculateMemoryStats(records);
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
export function nativeMemory2CategoryPieChartData(nativeMemoryData: NativeMemoryData | null, currentStepIndex: number) {
  if (!nativeMemoryData) {
    return { legendData: [], seriesData: [] };
  }

  const stepKey = `step${currentStepIndex}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) {
    return { legendData: [], seriesData: [] };
  }

  // 按大分类分组
  const categoryRecordsMap = new Map<number, NativeMemoryRecord[]>();

  stepData.records.forEach(item => {
    const category = item.componentCategory;
    if (!categoryRecordsMap.has(category)) {
      categoryRecordsMap.set(category, []);
    }
    categoryRecordsMap.get(category)!.push(item);
  });

  // 计算每个大分类的峰值内存
  const categoryEntries: [string, number][] = [];
  categoryRecordsMap.forEach((records, category) => {
    const stats = calculateMemoryStats(records);
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
export function nativeMemory2EventTypePieChartData(nativeMemoryData: NativeMemoryData | null, currentStepIndex: number) {
  if (!nativeMemoryData) {
    return { legendData: [], seriesData: [] };
  }

  const stepKey = `step${currentStepIndex}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) {
    return { legendData: [], seriesData: [] };
  }

  // 按事件类型分组
  const eventTypeRecordsMap = new Map<string, NativeMemoryRecord[]>();

  stepData.records.forEach(item => {
    const eventTypeName = getEventTypeName(item.eventType, item.subEventType);
    if (!eventTypeRecordsMap.has(eventTypeName)) {
      eventTypeRecordsMap.set(eventTypeName, []);
    }
    eventTypeRecordsMap.get(eventTypeName)!.push(item);
  });

  // 计算每个事件类型的峰值内存
  const eventTypeEntries: [string, number][] = [];
  eventTypeRecordsMap.forEach((records, eventTypeName) => {
    const stats = calculateMemoryStats(records);
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
// 从原始事件记录中独立计算每个进程的内存统计
export function aggregateByProcess(nativeMemoryData: NativeMemoryData | null, stepId: number): ProcessMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按进程分组原始事件记录
  const processRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    const processName = item.process || "Unknown Process";
    if (!processRecordsMap.has(processName)) {
      processRecordsMap.set(processName, []);
    }
    processRecordsMap.get(processName)!.push(item);
  }

  // 计算每个进程的内存统计
  const result: ProcessMemoryItem[] = [];
  processRecordsMap.forEach((records, processName) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的分类信息
    const firstRecord = records[0];

    result.push({
      stepId,
      process: processName,
      category: getCategoryName(firstRecord.componentCategory),
      componentName: processName,
      categoryName: firstRecord.categoryName,
      subCategoryName: firstRecord.subCategoryName,
      eventNum: stats.eventNum,
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
// 从原始事件记录中独立计算每个线程的内存统计
export function aggregateByThread(nativeMemoryData: NativeMemoryData | null, stepId: number): ThreadMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按进程+线程分组原始事件记录
  const threadRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    // 只处理有 tid 的记录
    if (item.tid === null || item.tid === undefined) continue;

    const processName = item.process || "Unknown Process";
    const threadName = item.thread || "Unknown Thread";
    const key = `${processName}|${threadName}`;

    if (!threadRecordsMap.has(key)) {
      threadRecordsMap.set(key, []);
    }
    threadRecordsMap.get(key)!.push(item);
  }

  // 计算每个线程的内存统计
  const result: ThreadMemoryItem[] = [];
  threadRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
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
// 从原始事件记录中独立计算每个文件的内存统计
export function aggregateByFile(nativeMemoryData: NativeMemoryData | null, stepId: number): FileMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按进程+线程+文件分组原始事件记录
  const fileRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    // 只处理有 fileId 的记录
    if (item.fileId === null || item.fileId === undefined) continue;

    const processName = item.process || "Unknown Process";
    const threadName = item.thread || "Unknown Thread";
    const fileName = item.file || "Unknown File";
    const key = `${processName}|${threadName}|${fileName}`;

    if (!fileRecordsMap.has(key)) {
      fileRecordsMap.set(key, []);
    }
    fileRecordsMap.get(key)!.push(item);
  }

  // 计算每个文件的内存统计
  const result: FileMemoryItem[] = [];
  fileRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
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
// 从原始事件记录中独立计算每个符号的内存统计
export function aggregateBySymbol(nativeMemoryData: NativeMemoryData | null, stepId: number): SymbolMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按进程+线程+文件+符号分组原始事件记录
  const symbolRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    // 只处理有 symbolId 的记录
    if (item.symbolId === null || item.symbolId === undefined) continue;

    const processName = item.process || "Unknown Process";
    const threadName = item.thread || "Unknown Thread";
    const fileName = item.file || "Unknown File";
    const symbolName = item.symbol || "Unknown Symbol";
    const key = `${processName}|${threadName}|${fileName}|${symbolName}`;

    if (!symbolRecordsMap.has(key)) {
      symbolRecordsMap.set(key, []);
    }
    symbolRecordsMap.get(key)!.push(item);
  }

  // 计算每个符号的内存统计
  const result: SymbolMemoryItem[] = [];
  symbolRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
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
// 从原始事件记录中独立计算每个大分类的内存统计
export function aggregateByCategory(nativeMemoryData: NativeMemoryData | null, stepId: number): ThreadMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按大分类分组原始事件记录
  const categoryRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    const categoryName = item.categoryName;
    if (!categoryRecordsMap.has(categoryName)) {
      categoryRecordsMap.set(categoryName, []);
    }
    categoryRecordsMap.get(categoryName)!.push(item);
  }

  // 计算每个大分类的内存统计
  const result: ThreadMemoryItem[] = [];
  categoryRecordsMap.forEach((records, categoryName) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
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
// 从原始事件记录中独立计算每个小分类的内存统计
export function aggregateByComponent(nativeMemoryData: NativeMemoryData | null, stepId: number): ThreadMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按大分类+小分类分组原始事件记录
  const componentRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    const key = `${item.categoryName}|${item.subCategoryName}`;
    if (!componentRecordsMap.has(key)) {
      componentRecordsMap.set(key, []);
    }
    componentRecordsMap.get(key)!.push(item);
  }

  // 计算每个小分类的内存统计
  const result: ThreadMemoryItem[] = [];
  componentRecordsMap.forEach((records, key) => {
    const stats = calculateMemoryStats(records);

    // 获取第一条记录的信息
    const [categoryName, subCategoryName] = key.split('|');

    result.push({
      stepId,
      process: subCategoryName,
      thread: subCategoryName,
      category: categoryName,
      componentName: subCategoryName,
      categoryName: categoryName,
      subCategoryName: subCategoryName,
      eventNum: stats.eventNum,
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
// 从原始事件记录中独立计算每个文件的内存统计
export function aggregateByFileCategory(nativeMemoryData: NativeMemoryData | null, stepId: number): FileMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按大分类+小分类+文件分组原始事件记录
  const fileRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    // 只处理有 fileId 的记录
    if (item.fileId === null || item.fileId === undefined) continue;

    const fileName = item.file || "Unknown File";
    const key = `${item.categoryName}|${item.subCategoryName}|${fileName}`;

    if (!fileRecordsMap.has(key)) {
      fileRecordsMap.set(key, []);
    }
    fileRecordsMap.get(key)!.push(item);
  }

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
// 从原始事件记录中独立计算每个符号的内存统计
export function aggregateBySymbolCategory(nativeMemoryData: NativeMemoryData | null, stepId: number): SymbolMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按大分类+小分类+文件+符号分组原始事件记录
  const symbolRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    // 只处理有 symbolId 的记录
    if (item.symbolId === null || item.symbolId === undefined) continue;

    const fileName = item.file || "Unknown File";
    const symbolName = item.symbol || "Unknown Symbol";
    const key = `${item.categoryName}|${item.subCategoryName}|${fileName}|${symbolName}`;

    if (!symbolRecordsMap.has(key)) {
      symbolRecordsMap.set(key, []);
    }
    symbolRecordsMap.get(key)!.push(item);
  }

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
// 从原始事件记录中独立计算每个事件类型的内存统计
export function aggregateByEventType(nativeMemoryData: NativeMemoryData | null, stepId: number): EventTypeMemoryItem[] {
  if (!nativeMemoryData) return [];

  const stepKey = `step${stepId}`;
  const stepData = nativeMemoryData[stepKey];
  if (!stepData || !stepData.records) return [];

  // 按事件类型分组原始事件记录
  const eventTypeRecordsMap = new Map<string, NativeMemoryRecord[]>();

  for (const item of stepData.records) {
    const eventTypeName = getEventTypeName(item.eventType, item.subEventType);
    if (!eventTypeRecordsMap.has(eventTypeName)) {
      eventTypeRecordsMap.set(eventTypeName, []);
    }
    eventTypeRecordsMap.get(eventTypeName)!.push(item);
  }

  // 计算每个事件类型的内存统计
  const result: EventTypeMemoryItem[] = [];
  eventTypeRecordsMap.forEach((records, eventTypeName) => {
    const stats = calculateMemoryStats(records);

    result.push({
      stepId,
      eventTypeName,
      eventNum: stats.eventNum,
      peakMem: stats.peakMem,
      avgMem: stats.avgMem,
      totalAllocMem: stats.totalAllocMem,
      totalFreeMem: stats.totalFreeMem,
    });
  });

  return result.sort((a, b) => b.peakMem - a.peakMem);
}

