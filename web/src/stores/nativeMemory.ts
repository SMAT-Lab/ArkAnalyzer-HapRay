import { getDbApi } from '@/utils/dbApi';
import type { SqlRow } from '@/db/client/dbClient';
import { ComponentCategory } from './jsonDataStore';

const LOG_PREFIX = '[NativeMemory]';

// 内存类型枚举
export enum MemType {
  Process = 0,
  Thread = 1,
  File = 2,
  Symbol = 3,
}

// 事件类型枚举
export enum EventType {
  AllocEvent = 'AllocEvent',
  FreeEvent = 'FreeEvent',
  MmapEvent = 'MmapEvent',
  MunmapEvent = 'MunmapEvent',
}

// Native Memory步骤统计信息
export interface NativeMemoryStepStats {
  peakMemorySize: number;
  peakMemoryDuration: number;
  averageMemorySize: number;
}

// 调用栈帧数据结构
export interface CallchainFrame {
  callchainId: number;
  depth: number;
  ip: number | null;
  symbolId: number | null;
  symbol: string | null;
  fileId: number | null;
  file: string | null;
  offset: number | null;
  symbolOffset: number | null;
  vaddr: number | null;
}

export type CallchainFrameMap = Record<number, CallchainFrame[]>;

/**
 * Native Memory 记录接口
 *
 * 后端生成的平铺记录，每条记录对应一个内存事件
 * 不包含聚合统计信息，所有统计需要在前端实时计算
 */
export interface NativeMemoryRecord {
  // 进程维度信息
  pid: number;
  process: string;
  // 线程维度信息
  tid: number | null;
  thread: string | null;
  // 文件维度信息
  fileId: number | null;
  file: string | null;
  // 符号维度信息
  symbolId: number | null;
  symbol: string | null;
  // 事件信息
  eventType: EventType;
  subEventType: string;
  addr: number; // 内存地址
  callchainId: number; // 调用链 ID
  // 内存大小（单次分配/释放的大小）
  heapSize: number;
  // 相对时间戳（相对于 trace 开始时间，纳秒）
  relativeTs: number;
  // 分类信息
  componentName: string; // 组件名称（小类名称）
  componentCategory: ComponentCategory; // 组件分类（大类编号）
  categoryName: string; // 大类名称（如 'APP_ABC', 'SYS_SDK'）
  subCategoryName: string; // 小类名称（如包名、文件名、线程名）
  // 聚合信息（仅用于 overview 层级）
  eventCount?: number; // 聚合的事件数量
  eventDetails?: string; // 聚合的事件详情（格式：eventType:heapSize|eventType:heapSize|...）
  // 所属步骤（仅汇总模式：跨步骤累计时间线的记录携带，用于火焰图按步骤取调用链）
  stepId?: number;
}

// Native Memory数据类型（包含统计信息和平铺记录）
export interface NativeMemoryStepData {
  peak_time?: number; // 峰值时间点（纳秒）
  peak_value?: number; // 峰值内存值（字节）
  stats?: NativeMemoryStepStats;
  records: NativeMemoryRecord[];
  callchains?: CallchainFrame[] | CallchainFrameMap; // 调用链数据（数组或字典格式）
}

// Native Memory压缩数据类型
export interface CompressedNativeMemoryStepData {
  compressed: true;
  peak_time?: number; // 峰值时间点（纳秒）
  peak_value?: number; // 峰值内存值（字节）
  stats?: NativeMemoryStepStats;
  records: string | string[]; // Base64编码的压缩数据（单块或多块）
  callchains?: CallchainFrame[] | CallchainFrameMap; // 调用链数据（通常不压缩）
  chunked?: boolean; // 是否为分块压缩
  chunk_count?: number; // 块数量
  total_records?: number; // 总记录数
}

export type NativeMemoryData = Record<string, NativeMemoryStepData>;
export type CompressedNativeMemoryData = Record<string, CompressedNativeMemoryStepData | NativeMemoryStepData>;

/** 汇总模式（跨步骤累计时间线）的步骤时间轴区间 */
export interface SummaryStepRange {
  stepId: number;
  /** 该步骤在跨步骤累计时间轴上的起始秒数 */
  startSec: number;
  /** 该步骤在跨步骤累计时间轴上的结束秒数（不含） */
  endSec: number;
  /** 步骤时长（秒） */
  durationSec: number;
}

/** 分类分布行（汇总饼图：大类或小类 .so 级的净内存统计） */
export interface NativeMemoryDistributionRow {
  name: string;
  /** 净内存（字节，申请 - 释放，可能为负） */
  netSize: number;
  eventCount: number;
}

/** 步骤区间缓存（同一份报告的步骤时间轴不变） */
let summaryStepRangesCache: SummaryStepRange[] | null = null;

/**
 * 原生内存相关操作集合
 */
export class NativeMemoryService {
  async loadMetadata(stepId: number): Promise<NativeMemoryStepData | null> {
    const dbApi = getDbApi();
    console.log(`${LOG_PREFIX} Loading memory metadata for step ${stepId}.`);

    let peak_time: number | undefined;
    let peak_value: number | undefined;

    try {
      const results = await dbApi.queryMemoryResults(stepId);
      if (results.length > 0) {
        const result = results[0];
        peak_time = this.toOptionalNumber(result.peak_time);
        peak_value = this.toOptionalNumber(result.peak_value);
      }
    } catch (error) {
      console.warn(`${LOG_PREFIX} Failed to query memory_results for step ${stepId}.`, error);
      return null;
    }

    const stepData: NativeMemoryStepData = {
      peak_time,
      peak_value,
      stats: undefined,
      records: [],
      callchains: undefined,
    };

    console.log(`${LOG_PREFIX} Metadata loaded for step ${stepId}.`);
    return stepData;
  }

  async fetchOverviewTimeline(stepId: number, groupBy: 'category' | 'process' = 'category'): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading overview timeline for step ${stepId}, groupBy: ${groupBy}.`);

    const rows = await getDbApi().queryOverviewTimeline(stepId, groupBy);

    console.log(`${LOG_PREFIX} Overview query returned ${rows.length} aggregated row(s).`);

    const records = rows.map((row) => this.mapOverviewRow(row, groupBy));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Overview timeline ready for step ${stepId} in ${duration}ms.`);

    return records;
  }

  async fetchCategoryRecords(stepId: number, categoryName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading category records for step ${stepId}, category ${categoryName}.`);

    const rows = await getDbApi().queryCategoryRecords(stepId, categoryName);
    const records = rows.map((row) => this.mapCategoryRow(row, categoryName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Category records ready for step ${stepId}/${categoryName} in ${duration}ms.`);

    return records;
  }

  async fetchSubCategoryRecords(stepId: number, categoryName: string, subCategoryName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading subcategory records for step ${stepId}, category ${categoryName}, subcategory ${subCategoryName}.`);

    const rows = await getDbApi().querySubCategoryRecords(stepId, categoryName, subCategoryName);
    const records = rows.map((row) => this.mapSubCategoryRow(row, categoryName, subCategoryName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Subcategory records ready for step ${stepId}/${categoryName}/${subCategoryName} in ${duration}ms.`);

    return records;
  }

  async fetchProcessRecords(stepId: number, processName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading process records for step ${stepId}, process ${processName}.`);

    const rows = await getDbApi().queryProcessRecords(stepId, processName);
    const records = rows.map((row) => this.mapProcessRow(row, processName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Process records ready for step ${stepId}/${processName} in ${duration}ms.`);

    return records;
  }

  async fetchThreadRecords(stepId: number, processName: string, threadName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading thread records for step ${stepId}, process ${processName}, thread ${threadName}.`);

    const rows = await getDbApi().queryThreadRecords(stepId, processName, threadName);
    const records = rows.map((row) => this.mapThreadRow(row, processName, threadName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Thread records ready for step ${stepId}/${processName}/${threadName} in ${duration}ms.`);

    return records;
  }

  async fetchFileRecords(stepId: number, processName: string, threadName: string, fileName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading file records for step ${stepId}, process ${processName}, thread ${threadName}, file ${fileName}.`);

    const rows = await getDbApi().queryFileRecords(stepId, processName, threadName, fileName);
    const records = rows.map((row) => this.mapFileRow(row, processName, threadName, fileName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} File records ready for step ${stepId}/${processName}/${threadName}/${fileName} in ${duration}ms.`);

    return records;
  }

  async fetchFileEventTypeRecords(stepId: number, categoryName: string, subCategoryName: string, fileName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading file event type records for step ${stepId}, category ${categoryName}, subcategory ${subCategoryName}, file ${fileName}.`);

    const rows = await getDbApi().queryFileEventTypeRecords(stepId, categoryName, subCategoryName, fileName);
    const records = rows.map((row) => this.mapFileEventTypeRow(row, categoryName, subCategoryName, fileName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} File event type records ready for step ${stepId}/${categoryName}/${subCategoryName}/${fileName} in ${duration}ms.`);

    return records;
  }

  async fetchFileEventTypeRecordsForProcess(stepId: number, processName: string, threadName: string, fileName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading file event type records for step ${stepId}, process ${processName}, thread ${threadName}, file ${fileName}.`);

    const rows = await getDbApi().queryFileEventTypeRecordsForProcess(stepId, processName, threadName, fileName);
    const records = rows.map((row) => this.mapFileEventTypeRowForProcess(row, processName, threadName, fileName));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} File event type records ready for step ${stepId}/${processName}/${threadName}/${fileName} in ${duration}ms.`);

    return records;
  }

  async fetchRecordsUpToTimeByCategory(
    stepId: number,
    relativeTsSeconds: number,
    categoryName?: string,
    subCategoryName?: string,
    fileName?: string
  ): Promise<NativeMemoryRecord[]> {
    const relativeTsNs = Math.floor(relativeTsSeconds * 1_000_000_000);
    const startTime = performance.now();

    console.log(
      `${LOG_PREFIX} Loading records up to ${relativeTsSeconds.toFixed(3)}s for step ${stepId} (category mode), category ${categoryName ?? 'ALL'}, subCategory ${subCategoryName ?? 'ALL'}, file ${fileName ?? 'ALL'}.`
    );

    const rows = await getDbApi().queryRecordsUpToByCategory(
      stepId,
      relativeTsNs,
      categoryName,
      subCategoryName,
      fileName
    );

    const records = rows.map((row) => this.mapRawRecordRow(row));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(
      `${LOG_PREFIX} Loaded ${records.length} record(s) up to ${relativeTsSeconds.toFixed(3)}s for step ${stepId} in ${duration}ms.`
    );

    return records;
  }

  async fetchRecordsUpToTimeByProcess(
    stepId: number,
    relativeTsSeconds: number,
    processName?: string,
    threadName?: string,
    fileName?: string
  ): Promise<NativeMemoryRecord[]> {
    const relativeTsNs = Math.floor(relativeTsSeconds * 1_000_000_000);
    const startTime = performance.now();

    console.log(
      `${LOG_PREFIX} Loading records up to ${relativeTsSeconds.toFixed(3)}s for step ${stepId} (process mode), process ${processName ?? 'ALL'}, thread ${threadName ?? 'ALL'}, file ${fileName ?? 'ALL'}.`
    );

    const rows = await getDbApi().queryRecordsUpToByProcess(
      stepId,
      relativeTsNs,
      processName,
      threadName,
      fileName
    );

    const records = rows.map((row) => this.mapRawRecordRow(row));

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(
      `${LOG_PREFIX} Loaded ${records.length} record(s) up to ${relativeTsSeconds.toFixed(3)}s for step ${stepId} in ${duration}ms.`
    );

    return records;
  }

  async fetchCallchainFrames(stepId: number, callchainIds: number[]): Promise<CallchainFrameMap> {
    if (callchainIds.length === 0) {
      return {};
    }

    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading ${callchainIds.length} callchain frame set(s) for step ${stepId}.`);

    const rows = await getDbApi().queryCallchainFrames(stepId, callchainIds);
    const map: CallchainFrameMap = {};

    rows.forEach((row) => {
      const callchainId = Number(row.callchainId ?? row.callchainID ?? 0);
      if (!callchainId) {
        return;
      }

      if (!map[callchainId]) {
        map[callchainId] = [];
      }

      map[callchainId].push({
        callchainId,
        depth: Number(row.depth ?? 0),
        ip: this.toNullableNumber(row.ip),
        symbolId: this.toNullableNumber(row.symbolId),
        symbol: this.toOptionalString(row.symbol),
        fileId: this.toNullableNumber(row.fileId),
        file: this.toOptionalString(row.file),
        offset: this.toNullableNumber(row.offset),
        symbolOffset: this.toNullableNumber(row.symbolOffset),
        vaddr: this.toNullableNumber(row.vaddr),
      });
    });

    Object.values(map).forEach((frames) => {
      frames.sort((a, b) => a.depth - b.depth);
    });

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Loaded callchain frames for step ${stepId} in ${duration}ms.`);

    return map;
  }

  private mapOverviewRow(row: SqlRow, groupBy: 'category' | 'process' = 'category', timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const groupName = String(row.groupName ?? '');

    return {
      pid: 0,
      process: groupBy === 'process' ? groupName : '',
      tid: null,
      thread: null,
      fileId: null,
      file: null,
      symbolId: null,
      symbol: null,
      eventType: netSize >= 0 ? EventType.AllocEvent : EventType.FreeEvent,
      subEventType: '',
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName: groupBy === 'category' ? groupName : '',
      subCategoryName: '',
      eventCount: Number(row.eventCount ?? 0),
      eventDetails: String(row.eventDetails ?? ''),
    };
  }

  private mapCategoryRow(row: SqlRow, categoryName: string, timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const subCategory = String(row.subCategoryName ?? '');

    return {
      pid: 0,
      process: '',
      tid: null,
      thread: null,
      fileId: null,
      file: null,
      symbolId: null,
      symbol: null,
      eventType: netSize >= 0 ? EventType.AllocEvent : EventType.FreeEvent,
      subEventType: '',
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName,
      subCategoryName: subCategory,
      eventCount: Number(row.eventCount ?? 0),
      eventDetails: String(row.eventDetails ?? ''),
    };
  }

  private mapSubCategoryRow(row: SqlRow, categoryName: string, subCategoryName: string, timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const file = String(row.file ?? '');

    return {
      pid: 0,
      process: '',
      tid: null,
      thread: null,
      fileId: null,
      file,
      symbolId: null,
      symbol: null,
      eventType: netSize >= 0 ? EventType.AllocEvent : EventType.FreeEvent,
      subEventType: '',
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName,
      subCategoryName,
    };
  }

  private mapProcessRow(row: SqlRow, processName: string, timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const thread = String(row.thread ?? '');

    return {
      pid: 0,
      process: processName,
      tid: null,
      thread,
      fileId: null,
      file: null,
      symbolId: null,
      symbol: null,
      eventType: netSize >= 0 ? EventType.AllocEvent : EventType.FreeEvent,
      subEventType: '',
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName: '',
      subCategoryName: '',
      eventCount: Number(row.eventCount ?? 0),
      eventDetails: String(row.eventDetails ?? ''),
    };
  }

  private mapThreadRow(row: SqlRow, processName: string, threadName: string, timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const file = String(row.file ?? '');

    return {
      pid: 0,
      process: processName,
      tid: null,
      thread: threadName,
      fileId: null,
      file,
      symbolId: null,
      symbol: null,
      eventType: netSize >= 0 ? EventType.AllocEvent : EventType.FreeEvent,
      subEventType: '',
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName: '',
      subCategoryName: '',
    };
  }

  private mapFileRow(row: SqlRow, processName: string, threadName: string, fileName: string): NativeMemoryRecord {
    return this.mapRawRecordRow({
      ...row,
      process: processName,
      thread: threadName,
      file: fileName,
    });
  }

  private mapFileEventTypeRow(row: SqlRow, categoryName: string, subCategoryName: string, fileName: string, timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const eventType = String(row.eventType ?? '');
    const subEventType = String(row.subEventType ?? '');

    return {
      pid: 0,
      process: '',
      tid: null,
      thread: null,
      fileId: null,
      file: fileName,
      symbolId: null,
      symbol: null,
      eventType: eventType as EventType,
      subEventType,
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName,
      subCategoryName,
    };
  }

  private mapFileEventTypeRowForProcess(row: SqlRow, processName: string, threadName: string, fileName: string, timeOffsetSec = 0): NativeMemoryRecord {
    const netSize = Number(row.netSize ?? 0);
    const timePoint10ms = Number(row.timePoint10ms ?? 0);
    const eventType = String(row.eventType ?? '');
    const subEventType = String(row.subEventType ?? '');

    return {
      pid: 0,
      process: processName,
      tid: null,
      thread: threadName,
      fileId: null,
      file: fileName,
      symbolId: null,
      symbol: null,
      eventType: eventType as EventType,
      subEventType,
      addr: 0,
      callchainId: 0,
      heapSize: Math.abs(netSize),
      relativeTs: timeOffsetSec + timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName: '',
      subCategoryName: '',
    };
  }

  private mapRawRecordRow(row: SqlRow): NativeMemoryRecord {
    const pid = Number(row.pid ?? 0);
    const tidValue = row.tid;
    const threadValue = row.thread;
    const fileIdValue = row.fileId;
    const fileValue = row.file;
    const symbolIdValue = row.symbolId;
    const symbolValue = row.symbol;
    const addrValue = row.addr;
    const componentCategoryValue = Number(row.componentCategory ?? ComponentCategory.UNKNOWN);
    const relativeTsValue = Number(row.relativeTs ?? 0);
    const parsedAddr = this.parseAddress(addrValue);
    const categoryName = String(row.categoryName ?? '');
    const subCategoryName = String(row.subCategoryName ?? '');

    return {
      pid,
      process: String(row.process ?? ''),
      tid: this.toNullableNumber(tidValue),
      thread: this.toOptionalString(threadValue),
      fileId: this.toNullableNumber(fileIdValue),
      file: this.toOptionalString(fileValue),
      symbolId: this.toNullableNumber(symbolIdValue),
      symbol: this.toOptionalString(symbolValue),
      eventType: String(row.eventType ?? '') as EventType,
      subEventType: String(row.subEventType ?? ''),
      addr: Number.isFinite(parsedAddr) ? parsedAddr : 0,
      callchainId: Number(row.callchainId ?? 0),
      heapSize: Number(row.heapSize ?? 0),
      relativeTs: relativeTsValue ? relativeTsValue / 1_000_000_000 : 0,
      componentName: String(row.componentName ?? ''),
      componentCategory: Number.isFinite(componentCategoryValue)
        ? (componentCategoryValue as ComponentCategory)
        : ComponentCategory.UNKNOWN,
      categoryName,
      subCategoryName,
    };
  }

  // ==================== 汇总模式（跨步骤累计时间线） ====================

  /**
   * 加载所有步骤的时间轴区间（用于跨步骤累计时间线的偏移拼接与步骤区段标注）
   *
   * 步骤时长 = 步骤内最大事件时间 + 1 个时间桶（10ms），后续步骤的起始偏移为前序步骤时长之和。
   * 结果缓存：同一份报告的步骤区间不变。
   */
  async loadSummaryStepRanges(): Promise<SummaryStepRange[]> {
    if (summaryStepRangesCache) {
      return summaryStepRangesCache;
    }

    const rows = await getDbApi().queryNetMemoryTimelineAll();
    const maxTimePointByStep = new Map<number, number>();
    for (const row of rows || []) {
      const stepId = Number(row.step_id ?? 0);
      const timePoint10ms = Number(row.timePoint10ms ?? 0);
      const current = maxTimePointByStep.get(stepId);
      if (current == null || timePoint10ms > current) {
        maxTimePointByStep.set(stepId, timePoint10ms);
      }
    }

    const ranges: SummaryStepRange[] = [];
    let offsetSec = 0;
    for (const stepId of Array.from(maxTimePointByStep.keys()).sort((a, b) => a - b)) {
      const maxSec = (maxTimePointByStep.get(stepId) ?? 0) * 0.01;
      const durationSec = maxSec + 0.01;
      ranges.push({
        stepId,
        startSec: offsetSec,
        endSec: offsetSec + durationSec,
        durationSec,
      });
      offsetSec += durationSec;
    }

    summaryStepRangesCache = ranges;
    return ranges;
  }

  private async summaryOffsetMap(): Promise<Map<number, number>> {
    const ranges = await this.loadSummaryStepRanges();
    const map = new Map<number, number>();
    ranges.forEach((range) => map.set(range.stepId, range.startSec));
    return map;
  }

  /** 汇总模式：总览层级（按大类/进程聚合所有步骤，时间为跨步骤累计时间轴） */
  async fetchSummaryOverviewTimeline(groupBy: 'category' | 'process' = 'category'): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().queryOverviewTimelineAll(groupBy),
    ]);
    return (rows || []).map((row) =>
      this.mapOverviewRow(row, groupBy, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 汇总模式：大类层级（按小类聚合所有步骤） */
  async fetchSummaryCategoryRecords(categoryName: string): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().queryCategoryRecordsAll(categoryName),
    ]);
    return (rows || []).map((row) =>
      this.mapCategoryRow(row, categoryName, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 汇总模式：小类层级（按文件聚合所有步骤） */
  async fetchSummarySubCategoryRecords(categoryName: string, subCategoryName: string): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().querySubCategoryRecordsAll(categoryName, subCategoryName),
    ]);
    return (rows || []).map((row) =>
      this.mapSubCategoryRow(row, categoryName, subCategoryName, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 汇总模式：进程层级（按线程聚合所有步骤） */
  async fetchSummaryProcessRecords(processName: string): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().queryProcessRecordsAll(processName),
    ]);
    return (rows || []).map((row) =>
      this.mapProcessRow(row, processName, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 汇总模式：线程层级（按文件聚合所有步骤） */
  async fetchSummaryThreadRecords(processName: string, threadName: string): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().queryThreadRecordsAll(processName, threadName),
    ]);
    return (rows || []).map((row) =>
      this.mapThreadRow(row, processName, threadName, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 汇总模式：文件层级事件类型（分类模式） */
  async fetchSummaryFileEventTypeRecords(
    categoryName: string,
    subCategoryName: string,
    fileName: string
  ): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().queryFileEventTypeRecordsAll(categoryName, subCategoryName, fileName),
    ]);
    return (rows || []).map((row) =>
      this.mapFileEventTypeRow(row, categoryName, subCategoryName, fileName, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 汇总模式：文件层级事件类型（进程模式） */
  async fetchSummaryFileEventTypeRecordsForProcess(
    processName: string,
    threadName: string,
    fileName: string
  ): Promise<NativeMemoryRecord[]> {
    const [offsets, rows] = await Promise.all([
      this.summaryOffsetMap(),
      getDbApi().queryFileEventTypeRecordsForProcessAll(processName, threadName, fileName),
    ]);
    return (rows || []).map((row) =>
      this.mapFileEventTypeRowForProcess(row, processName, threadName, fileName, offsets.get(Number(row.step_id ?? 0)) ?? 0)
    );
  }

  /** 将跨步骤累计时间轴上的时间点解析为 (所属步骤ID, 步骤内相对时间秒) */
  private resolveSummaryTimePoint(timeSec: number, ranges: SummaryStepRange[]): { stepId: number; innerSec: number } | null {
    if (!ranges.length) return null;
    const range =
      ranges.find((r) => timeSec >= r.startSec && timeSec < r.endSec) ??
      ranges[ranges.length - 1];
    if (!range) return null;
    return { stepId: range.stepId, innerSec: timeSec - range.startSec };
  }

  /**
   * 汇总模式：查询截至跨步骤累计时间点的所有记录（带 stepId，用于火焰图计算未释放内存）
   *
   * 时间边界：选中时间点所属步骤之前的步骤取全部记录，所属步骤取步骤内相对时间 <= 选中点的记录。
   */
  async fetchSummaryRecordsUpToTime(
    viewMode: 'category' | 'process',
    relativeTsSeconds: number,
    categoryName?: string,
    subCategoryName?: string,
    processName?: string,
    threadName?: string,
    fileName?: string
  ): Promise<NativeMemoryRecord[]> {
    const ranges = await this.loadSummaryStepRanges();
    const resolved = this.resolveSummaryTimePoint(relativeTsSeconds, ranges);
    if (!resolved) return [];

    const innerNs = Math.floor(resolved.innerSec * 1_000_000_000);
    const rows =
      viewMode === 'category'
        ? await getDbApi().queryRecordsUpToByCategoryAll(
            resolved.stepId,
            innerNs,
            categoryName,
            subCategoryName,
            fileName
          )
        : await getDbApi().queryRecordsUpToByProcessAll(
            resolved.stepId,
            innerNs,
            processName,
            threadName,
            fileName
          );

    return (rows || []).map((row) => {
      const record = this.mapRawRecordRow(row);
      record.stepId = Number(row.step_id ?? 0);
      return record;
    });
  }

  /**
   * 汇总模式：按 (stepId, callchainId) 批量取调用链帧
   *
   * callchainId 在各步骤间会重叠（每步独立编号），因此以 `${stepId}:${callchainId}` 复合键返回。
   */
  async fetchSummaryCallchainFrames(
    entries: Array<{ stepId: number; callchainId: number }>
  ): Promise<Record<string, CallchainFrame[]>> {
    const byStep = new Map<number, number[]>();
    for (const entry of entries) {
      if (!entry.callchainId || entry.callchainId < 0) continue;
      if (!byStep.has(entry.stepId)) {
        byStep.set(entry.stepId, []);
      }
      byStep.get(entry.stepId)!.push(entry.callchainId);
    }

    const result: Record<string, CallchainFrame[]> = {};
    await Promise.all(
      Array.from(byStep.entries()).map(async ([stepId, callchainIds]) => {
        const uniqueIds = Array.from(new Set(callchainIds));
        if (!uniqueIds.length) return;
        const framesMap = await this.fetchCallchainFrames(stepId, uniqueIds);
        for (const [callchainId, frames] of Object.entries(framesMap)) {
          result[`${stepId}:${callchainId}`] = frames;
        }
      })
    );
    return result;
  }

  /** 将跨步骤累计时间轴上的时间点解析为 (所属步骤ID, 步骤内相对纳秒)；无时间点时返回 undefined（全场景） */
  private async resolveSummaryBoundary(
    timeSec?: number | null
  ): Promise<{ selectedStepId: number; innerRelativeTs: number } | undefined> {
    if (timeSec == null) return undefined;
    const ranges = await this.loadSummaryStepRanges();
    const resolved = this.resolveSummaryTimePoint(timeSec, ranges);
    if (!resolved) return undefined;
    return {
      selectedStepId: resolved.stepId,
      innerRelativeTs: Math.floor(resolved.innerSec * 1_000_000_000),
    };
  }

  /** 汇总模式：按大类统计净内存分布（timeSec 为空时统计全场景所有步骤） */
  async fetchSummaryCategoryDistribution(timeSec?: number | null): Promise<NativeMemoryDistributionRow[]> {
    const boundary = await this.resolveSummaryBoundary(timeSec);
    const rows = await getDbApi().queryCategoryDistributionAll(boundary?.selectedStepId, boundary?.innerRelativeTs);
    return (rows || []).map((row) => ({
      name: String(row.categoryName ?? ''),
      netSize: Number(row.netSize ?? 0),
      eventCount: Number(row.eventCount ?? 0),
    }));
  }

  /** 汇总模式：按小类（.so / 库文件）统计指定大类下的净内存分布（timeSec 为空时统计全场景所有步骤） */
  async fetchSummarySubCategoryDistribution(
    categoryName: string,
    timeSec?: number | null
  ): Promise<NativeMemoryDistributionRow[]> {
    const boundary = await this.resolveSummaryBoundary(timeSec);
    const rows = await getDbApi().querySubCategoryDistributionAll(
      categoryName,
      boundary?.selectedStepId,
      boundary?.innerRelativeTs
    );
    return (rows || []).map((row) => ({
      name: String(row.subCategoryName ?? ''),
      netSize: Number(row.netSize ?? 0),
      eventCount: Number(row.eventCount ?? 0),
    }));
  }

  private parseAddress(value: unknown): number {
    if (value === null || value === undefined) {
      return 0;
    }
    if (typeof value === 'string') {
      return value.startsWith('0x') ? parseInt(value, 16) : Number(value);
    }
    return Number(value);
  }

  private toOptionalNumber(value: unknown): number | undefined {
    if (value === null || value === undefined || value === '') {
      return undefined;
    }
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : undefined;
  }

  private toNullableNumber(value: unknown): number | null {
    const parsed = this.toOptionalNumber(value);
    return parsed ?? null;
  }

  private toOptionalString(value: unknown): string | null {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return String(value);
  }
}

export const nativeMemoryService = new NativeMemoryService();

export function loadNativeMemoryMetadataFromDb(stepId: number): Promise<NativeMemoryStepData | null> {
  return nativeMemoryService.loadMetadata(stepId);
}

export function fetchOverviewTimeline(stepId: number, groupBy: 'category' | 'process' = 'category'): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchOverviewTimeline(stepId, groupBy);
}

export function fetchCategoryRecords(stepId: number, categoryName: string): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchCategoryRecords(stepId, categoryName);
}

export function fetchSubCategoryRecords(
  stepId: number,
  categoryName: string,
  subCategoryName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSubCategoryRecords(stepId, categoryName, subCategoryName);
}

export function fetchProcessRecords(stepId: number, processName: string): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchProcessRecords(stepId, processName);
}

export function fetchThreadRecords(
  stepId: number,
  processName: string,
  threadName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchThreadRecords(stepId, processName, threadName);
}

export function fetchFileRecords(
  stepId: number,
  processName: string,
  threadName: string,
  fileName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchFileRecords(stepId, processName, threadName, fileName);
}

export function fetchRecordsUpToTimeByCategory(
  stepId: number,
  relativeTsSeconds: number,
  categoryName?: string,
  subCategoryName?: string,
  fileName?: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchRecordsUpToTimeByCategory(
    stepId,
    relativeTsSeconds,
    categoryName,
    subCategoryName,
    fileName
  );
}

export function fetchRecordsUpToTimeByProcess(
  stepId: number,
  relativeTsSeconds: number,
  processName?: string,
  threadName?: string,
  fileName?: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchRecordsUpToTimeByProcess(
    stepId,
    relativeTsSeconds,
    processName,
    threadName,
    fileName
  );
}

export function fetchCallchainFrames(stepId: number, callchainIds: number[]): Promise<CallchainFrameMap> {
  return nativeMemoryService.fetchCallchainFrames(stepId, callchainIds);
}

export function fetchFileEventTypeRecords(
  stepId: number,
  categoryName: string,
  subCategoryName: string,
  fileName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchFileEventTypeRecords(stepId, categoryName, subCategoryName, fileName);
}

export function fetchFileEventTypeRecordsForProcess(
  stepId: number,
  processName: string,
  threadName: string,
  fileName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchFileEventTypeRecordsForProcess(stepId, processName, threadName, fileName);
}

// ==================== 汇总模式（跨步骤累计时间线） ====================

/** 加载所有步骤的时间轴区间（跨步骤累计时间线的偏移拼接基准） */
export function fetchSummaryStepRanges(): Promise<SummaryStepRange[]> {
  return nativeMemoryService.loadSummaryStepRanges();
}

/** 汇总模式：总览层级 */
export function fetchSummaryOverviewTimeline(groupBy: 'category' | 'process' = 'category'): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryOverviewTimeline(groupBy);
}

/** 汇总模式：大类层级 */
export function fetchSummaryCategoryRecords(categoryName: string): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryCategoryRecords(categoryName);
}

/** 汇总模式：小类层级 */
export function fetchSummarySubCategoryRecords(categoryName: string, subCategoryName: string): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummarySubCategoryRecords(categoryName, subCategoryName);
}

/** 汇总模式：进程层级 */
export function fetchSummaryProcessRecords(processName: string): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryProcessRecords(processName);
}

/** 汇总模式：线程层级 */
export function fetchSummaryThreadRecords(processName: string, threadName: string): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryThreadRecords(processName, threadName);
}

/** 汇总模式：文件层级事件类型（分类模式） */
export function fetchSummaryFileEventTypeRecords(
  categoryName: string,
  subCategoryName: string,
  fileName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryFileEventTypeRecords(categoryName, subCategoryName, fileName);
}

/** 汇总模式：文件层级事件类型（进程模式） */
export function fetchSummaryFileEventTypeRecordsForProcess(
  processName: string,
  threadName: string,
  fileName: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryFileEventTypeRecordsForProcess(processName, threadName, fileName);
}

/**
 * 汇总模式：查询截至跨步骤累计时间点的所有记录（带 stepId，用于火焰图计算未释放内存）
 */
export function fetchSummaryRecordsUpToTime(
  viewMode: 'category' | 'process',
  relativeTsSeconds: number,
  categoryName?: string,
  subCategoryName?: string,
  processName?: string,
  threadName?: string,
  fileName?: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchSummaryRecordsUpToTime(
    viewMode,
    relativeTsSeconds,
    categoryName,
    subCategoryName,
    processName,
    threadName,
    fileName
  );
}

/**
 * 汇总模式：按 (stepId, callchainId) 批量取调用链帧，以 `${stepId}:${callchainId}` 复合键返回
 */
export function fetchSummaryCallchainFrames(
  entries: Array<{ stepId: number; callchainId: number }>
): Promise<Record<string, CallchainFrame[]>> {
  return nativeMemoryService.fetchSummaryCallchainFrames(entries);
}

/** 汇总模式：按大类统计净内存分布（timeSec 为空时统计全场景所有步骤） */
export function fetchSummaryCategoryDistribution(timeSec?: number | null): Promise<NativeMemoryDistributionRow[]> {
  return nativeMemoryService.fetchSummaryCategoryDistribution(timeSec);
}

/** 汇总模式：按小类（.so / 库文件）统计指定大类下的净内存分布（timeSec 为空时统计全场景所有步骤） */
export function fetchSummarySubCategoryDistribution(
  categoryName: string,
  timeSec?: number | null
): Promise<NativeMemoryDistributionRow[]> {
  return nativeMemoryService.fetchSummarySubCategoryDistribution(categoryName, timeSec);
}
