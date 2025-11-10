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
    this.sortByTimestamp(records, `step${stepId}`);

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Overview timeline ready for step ${stepId} in ${duration}ms.`);

    return records;
  }

  async fetchCategoryRecords(stepId: number, categoryName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading category records for step ${stepId}, category ${categoryName}.`);

    const rows = await getDbApi().queryCategoryRecords(stepId, categoryName);
    const records = rows.map((row) => this.mapCategoryRow(row, categoryName));
    this.sortByTimestamp(records, `step${stepId}/${categoryName}`);

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Category records ready for step ${stepId}/${categoryName} in ${duration}ms.`);

    return records;
  }

  async fetchSubCategoryRecords(stepId: number, categoryName: string, subCategoryName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading subcategory records for step ${stepId}, category ${categoryName}, subcategory ${subCategoryName}.`);

    const rows = await getDbApi().querySubCategoryRecords(stepId, categoryName, subCategoryName);
    const records = rows.map((row) => this.mapSubCategoryRow(row, categoryName, subCategoryName));
    this.sortByTimestamp(records, `step${stepId}/${categoryName}/${subCategoryName}`);

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Subcategory records ready for step ${stepId}/${categoryName}/${subCategoryName} in ${duration}ms.`);

    return records;
  }

  async fetchProcessRecords(stepId: number, processName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading process records for step ${stepId}, process ${processName}.`);

    const rows = await getDbApi().queryProcessRecords(stepId, processName);
    const records = rows.map((row) => this.mapProcessRow(row, processName));
    this.sortByTimestamp(records, `step${stepId}/${processName}`);

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Process records ready for step ${stepId}/${processName} in ${duration}ms.`);

    return records;
  }

  async fetchThreadRecords(stepId: number, processName: string, threadName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading thread records for step ${stepId}, process ${processName}, thread ${threadName}.`);

    const rows = await getDbApi().queryThreadRecords(stepId, processName, threadName);
    const records = rows.map((row) => this.mapThreadRow(row, processName, threadName));
    this.sortByTimestamp(records, `step${stepId}/${processName}/${threadName}`);

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} Thread records ready for step ${stepId}/${processName}/${threadName} in ${duration}ms.`);

    return records;
  }

  async fetchFileRecords(stepId: number, processName: string, threadName: string, fileName: string): Promise<NativeMemoryRecord[]> {
    const startTime = performance.now();

    console.log(`${LOG_PREFIX} Loading file records for step ${stepId}, process ${processName}, thread ${threadName}, file ${fileName}.`);

    const rows = await getDbApi().queryFileRecords(stepId, processName, threadName, fileName);
    const records = rows.map((row) => this.mapFileRow(row, processName, threadName, fileName));
    this.sortByTimestamp(records, `step${stepId}/${processName}/${threadName}/${fileName}`);

    const duration = (performance.now() - startTime).toFixed(2);
    console.log(`${LOG_PREFIX} File records ready for step ${stepId}/${processName}/${threadName}/${fileName} in ${duration}ms.`);

    return records;
  }

  async fetchRecordsUpToTime(
    stepId: number,
    relativeTsSeconds: number,
    categoryName?: string,
    subCategoryName?: string
  ): Promise<NativeMemoryRecord[]> {
    const relativeTsNs = Math.floor(relativeTsSeconds * 1_000_000_000);
    const startTime = performance.now();

    console.log(
      `${LOG_PREFIX} Loading records up to ${relativeTsSeconds.toFixed(3)}s for step ${stepId}, category ${categoryName ?? 'ALL'}, subCategory ${subCategoryName ?? 'ALL'}.`
    );

    const rows = await getDbApi().queryRecordsUpTo(stepId, relativeTsNs, categoryName, subCategoryName);
    const records = rows.map((row) => this.mapRawRecordRow(row));
    this.sortByTimestamp(records, `step${stepId}/recordsUpTo`);

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

  private sortByTimestamp(records: NativeMemoryRecord[], context: string): void {
    if (records.length <= 1) {
      return;
    }

    const start = performance.now();
    records.sort((a, b) => a.relativeTs - b.relativeTs);
    const duration = (performance.now() - start).toFixed(2);

    console.log(`${LOG_PREFIX} Sorted ${records.length} record(s) for ${context} in ${duration}ms.`);
  }

  private mapOverviewRow(row: SqlRow, groupBy: 'category' | 'process' = 'category'): NativeMemoryRecord {
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
      relativeTs: timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName: groupBy === 'category' ? groupName : '',
      subCategoryName: '',
      eventCount: Number(row.eventCount ?? 0),
      eventDetails: String(row.eventDetails ?? ''),
    };
  }

  private mapCategoryRow(row: SqlRow, categoryName: string): NativeMemoryRecord {
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
      relativeTs: timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName,
      subCategoryName: subCategory,
      eventCount: Number(row.eventCount ?? 0),
      eventDetails: String(row.eventDetails ?? ''),
    };
  }

  private mapSubCategoryRow(row: SqlRow, categoryName: string, subCategoryName: string): NativeMemoryRecord {
    return this.mapRawRecordRow({
      ...row,
      categoryName,
      subCategoryName,
    });
  }

  private mapProcessRow(row: SqlRow, processName: string): NativeMemoryRecord {
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
      relativeTs: timePoint10ms * 0.01,
      componentName: '',
      componentCategory: ComponentCategory.UNKNOWN,
      categoryName: '',
      subCategoryName: '',
      eventCount: Number(row.eventCount ?? 0),
      eventDetails: String(row.eventDetails ?? ''),
    };
  }

  private mapThreadRow(row: SqlRow, processName: string, threadName: string): NativeMemoryRecord {
    return this.mapRawRecordRow({
      ...row,
      process: processName,
      thread: threadName,
    });
  }

  private mapFileRow(row: SqlRow, processName: string, threadName: string, fileName: string): NativeMemoryRecord {
    return this.mapRawRecordRow({
      ...row,
      process: processName,
      thread: threadName,
      file: fileName,
    });
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

export function fetchRecordsUpToTime(
  stepId: number,
  relativeTsSeconds: number,
  categoryName?: string,
  subCategoryName?: string
): Promise<NativeMemoryRecord[]> {
  return nativeMemoryService.fetchRecordsUpToTime(stepId, relativeTsSeconds, categoryName, subCategoryName);
}

export function fetchCallchainFrames(stepId: number, callchainIds: number[]): Promise<CallchainFrameMap> {
  return nativeMemoryService.fetchCallchainFrames(stepId, callchainIds);
}
