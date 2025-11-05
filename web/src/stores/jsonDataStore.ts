import { defineStore } from 'pinia';
import { transformNativeMemoryData } from '@/utils/jsonUtil';
import pako from 'pako';

// ==================== 类型定义 ====================
/** 负载事件类型 */
export enum PerfEvent {
  CYCLES_EVENT = 0,
  INSTRUCTION_EVENT = 1,
}

/** 组件分类 */
export enum ComponentCategory {
  APP_ABC = 0,
  APP_SO = 1,
  APP_LIB = 2,
  OS_Runtime = 3,
  SYS_SDK = 4,
  RN = 5,
  Flutter = 6,
  WEB = 7,
  KMP = 8,
  UNKNOWN = -1,
}

/** 来源类型 */
enum OriginKind {
  UNKNOWN = 0,
  FIRST_PARTY = 1,
  OPEN_SOURCE = 2,
  THIRD_PARTY = 3,
}

export interface BasicInfo {
  rom_version: string;
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
}

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

/**
 * Native Memory 数据记录
 * 每条记录代表一个维度的内存统计信息
 *
 * 字段说明：
 * - stepIdx: 步骤ID
 * - pid: 进程ID（如果该维度包含进程信息，否则为null）
 * - process: 进程名称（如果该维度包含进程信息，否则为null）
 * - tid: 线程ID（如果该维度包含线程信息，否则为null）
 * - thread: 线程名称（如果该维度包含线程信息，否则为null）
 * - fileId: 文件ID（如果该维度包含文件信息，否则为null）
 * - file: 文件路径（如果该维度包含文件信息，否则为null）
 * - symbolId: 符号ID（如果该维度包含符号信息，否则为null）
 * - symbol: 符号名称（如果该维度包含符号信息，否则为null）
 * - eventType: 事件类型（AllocEvent/FreeEvent/MmapEvent/MunmapEvent）
 * - subEventType: 子事件类型（从data_dict表查询）
 * - eventNum: 满足该维度条件的数据条目数
 * - maxMem: 峰值内存
 * - curMem: 当前heap_size累加的结果值
 * - avgMem: 平均值 = (totalMem - transientMem) / eventNum
 * - totalMem: 所有加eventType的合
 * - transientMem: 所有减eventType的合
 * - start_ts: 第一个事件的时间戳
 * - componentName: 组件名称
 * - componentCategory: 组件分类
 */
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
  addr: number;  // 内存地址
  callchainId: number;  // 调用链 ID
  // 内存大小（单次分配/释放的大小）
  heapSize: number;
  // 相对时间戳（相对于 trace 开始时间，纳秒）
  relativeTs: number;
  // 分类信息
  componentName: string;  // 组件名称（小类名称）
  componentCategory: ComponentCategory;  // 组件分类（大类编号）
  categoryName: string;  // 大类名称（如 'APP_ABC', 'SYS_SDK'）
  subCategoryName: string;  // 小类名称（如包名、文件名、线程名）
}

// Native Memory步骤统计信息
export interface NativeMemoryStepStats {
  peakMemorySize: number;
  peakMemoryDuration: number;
  averageMemorySize: number;
}

// 后端返回的统计信息（使用下划线命名）
interface BackendNativeMemoryStepStats {
  peak_memory_size?: number;
  peak_memory_duration?: number;
  average_memory_size?: number;
}

// Callchain 数据结构
export interface CallchainRecord {
  callchainId: number;
  depth: number;
  file: string;
  symbol: string;
  is_alloc: boolean;
}

// Native Memory数据类型（包含统计信息和平铺记录）
export interface NativeMemoryStepData {
  peak_time?: number; // 峰值时间点（纳秒）
  peak_value?: number; // 峰值内存值（字节）
  stats?: NativeMemoryStepStats;
  records: NativeMemoryRecord[];
  callchains?: CallchainRecord[] | Record<number, CallchainRecord[]>; // 调用链数据（数组或字典格式）
}

// Native Memory压缩数据类型
export interface CompressedNativeMemoryStepData {
  compressed: true;
  peak_time?: number; // 峰值时间点（纳秒）
  peak_value?: number; // 峰值内存值（字节）
  stats?: NativeMemoryStepStats;
  records: string | string[]; // Base64编码的压缩数据（单块或多块）
  callchains?: CallchainRecord[] | Record<number, CallchainRecord[]>; // 调用链数据（通常不压缩）
  chunked?: boolean; // 是否为分块压缩
  chunk_count?: number; // 块数量
  total_records?: number; // 总记录数
}

export type NativeMemoryData = Record<string, NativeMemoryStepData>;
export type CompressedNativeMemoryData = Record<string, CompressedNativeMemoryStepData | NativeMemoryStepData>;

interface PerfDataStep {
  step_name: string;
  step_id: number;
  count: number;
  round: number;
  perf_data_path: string;
  data: {
    stepIdx: number;
    eventType: PerfEvent;
    pid: number;
    processName: string;
    processEvents: number;
    tid: number;
    threadName: string;
    threadEvents: number;
    file: string;
    fileEvents: number;
    symbol: string;
    symbolEvents: number;
    symbolTotalEvents: number;
    componentName?: string;
    componentCategory: ComponentCategory;
    originKind?: OriginKind;
  }[];
}

export interface PerfData {
  steps: PerfDataStep[];
}

interface FrameTypeStats {
  total: number;
  stutter: number;
  stutter_rate: number;
}

interface FrameStatistics {
  total_frames: number;
  frame_stats: {
    ui: FrameTypeStats;
    render: FrameTypeStats;
    sceneboard: FrameTypeStats;
  };
  total_stutter_frames: number;
  stutter_rate: number;
  stutter_levels: {
    level_1: number;
    level_2: number;
    level_3: number;
  };
}

interface StutterDetail {
  vsync: number;
  ts: number;
  actual_duration: number;
  expected_duration: number;
  exceed_time: number;
  exceed_frames: number;
  stutter_level: number;
  level_description: string;
  src: string;
  dst: number;
}

interface FpsWindow {
  start_time: number;
  end_time: number;
  start_time_ts: number;
  end_time_ts: number;
  frame_count: number;
  fps: number;
}

interface FpsStats {
  average_fps: number;
  min_fps: number;
  max_fps: number;
  fps_windows: FpsWindow[];
  low_fps_window_count: number;
}

interface FrameStepData {
  runtime: string;
  statistics: FrameStatistics;
  stutter_details: {
    ui_stutter: StutterDetail[];
    render_stutter: StutterDetail[];
  };
  fps_stats: FpsStats;
}

export type FrameData = Record<string, FrameStepData>;

interface EmptyFrameSummary {
  total_load: number;
  empty_frame_load: number;
  empty_frame_percentage: number;
  background_thread_load: number;
  background_thread_percentage: number;
  total_empty_frames: number;
  empty_frames_with_load: number;
}

interface ColdStartSummary {
  total_file_number: number;
  total_time_ms: number;
  used_file_count: number;
  used_file_time_ms: number;
  unused_file_count: number;
  unused_file_time_ms: number;
}

interface CallstackFrame {
  depth: number;
  file_id: number;
  path: string;
  symbol_id: number;
  symbol: string;
}

interface SampleCallchain {
  timestamp: number;
  event_count: number;
  load_percentage: number;
  callchain: CallstackFrame[];
}

interface FileInfo {
  rank: number;
  file_name: string;
  cost_time_ms: number;
  parent_module: string;  // 注意：实际数据中包含多行文本
}

interface EmptyFrame {
  ts: number;
  dur: number;
  ipid: number;
  itid: number;
  pid: number;
  tid: number;
  callstack_id: number;
  process_name: string;
  thread_name: string;
  callstack_name: string;
  frame_load: number;
  is_main_thread: number;
  sample_callchains: SampleCallchain[];
}

interface EmptyFrameStepData {
  status: string;
  summary: EmptyFrameSummary;
  top_frames: {
    main_thread_empty_frames: EmptyFrame[];
    background_thread: EmptyFrame[];
  };
}

export type EmptyFrameData = Record<string, EmptyFrameStepData>;

interface ColdStartStepData {
  summary: ColdStartSummary;
  used_files_top10: FileInfo[];
  unused_files_top10: FileInfo[];
}

export type ColdStartData = Record<string, ColdStartStepData>;

interface GcThreadStepData {
  FullGC: number;
  SharedFullGC: number;
  SharedGC: number;
  PartialGC: number;
  GCStatus: string;
  perf_percentage: number;
}

export type GcThreadData = Record<string, GcThreadStepData>;

interface ComponentResuStepData {
  total_builds: number;
  recycled_builds: number;
  reusability_ratio: number;
  max_component: string;
}

export type ComponentResuData = Record<string, ComponentResuStepData>;

interface FrameLoad {
  ts: number;
  dur: number;
  ipid?: number;
  itid?: number;
  pid?: number;
  tid: number;
  callstack_id?: number;
  process_name: string;
  thread_name: string;
  callstack_name?: string;
  frame_load: number;
  is_main_thread?: number;
  vsync?: number | string;
  flag?: number;
  type?: number;
  sample_callchains?: SampleCallchain[];
}

interface FrameLoadsStepData {
  status?: string;
  summary?: {
    total_frames: number;
    total_load: number;
    average_load: number;
    max_load: number;
    min_load: number;
  };
  top_frames: FrameLoad[];
}

export type FrameLoadsData = Record<string, FrameLoadsStepData>;

interface VSyncFrequencyAnomaly {
  type: string;
  start_vsync: number;
  end_vsync: number;
  start_ts: number;
  end_ts: number;
  duration: number;
  interval_count: number;
  avg_interval: number;
  avg_frequency: number;
  min_frequency: number;
  max_frequency: number;
  severity: string;
  description: string;
}

interface VSyncFrameMismatch {
  type: string;
  vsync: number;
  expect_frames?: number;
  actual_frames?: number;
  description: string;
  ts: number;
  thread_name: string;
  process_name: string;
}

interface VSyncAnomalyStepData {
  status?: string;
  statistics?: {
    total_vsync_signals: number;
    frequency_anomalies_count: number;
    frame_mismatch_count: number;
    anomaly_rate: number;
  };
  frequency_anomalies: VSyncFrequencyAnomaly[];
  frame_mismatches: VSyncFrameMismatch[];
}

export type VSyncAnomalyData = Record<string, VSyncAnomalyStepData>;

// 故障树分析数据结构
interface FaultTreeArkUIData {
  animator: number;
  HandleOnAreaChangeEvent: number;
  HandleVisibleAreaChangeEvent: number;
  GetDefaultDisplay: number;
  MarshRSTransactionData: number;
}

interface FaultTreeRSData {
  ProcessedNodes: {
    ts: number;
    count: number;
  };
  DisplayNodeSkipTimes: number;
  UnMarshRSTransactionData: number;
  AnimateSize: {
    nodeSizeSum: number;
    totalAnimationSizeSum: number;
  };
}

interface FaultTreeAVCodecData {
  soft_decoder: boolean;
  BroadcastControlInstructions: number;
  VideoDecodingInputFrameCount: number;
  VideoDecodingConsumptionFrame: number;
}

interface FaultTreeAudioData {
  AudioWriteCB: number;
  AudioReadCB: number;
  AudioPlayCb: number;
  AudioRecCb: number;
}

interface FaultTreeStepData {
  arkui: FaultTreeArkUIData;
  RS: FaultTreeRSData;
  av_codec: FaultTreeAVCodecData;
  Audio: FaultTreeAudioData;
}

export type FaultTreeData = Record<string, FaultTreeStepData>;

interface TraceData {
  frames: FrameData;
  emptyFrame?: EmptyFrameData;
  componentReuse: ComponentResuData;
  coldStart?: ColdStartData;
  gc_thread?: GcThreadData;
  frameLoads?: FrameLoadsData;
  vsyncAnomaly?: VSyncAnomalyData;
  faultTree?: FaultTreeData;
}

interface MoreData {
  flame_graph?: Record<string, string>; // 按步骤组织的火焰图数据，每个步骤的数据已单独压缩
  native_memory?: NativeMemoryData; // Native Memory数据（类似trace_frames.json的格式）
}

/**
 * 数据类型标记
 * 'perf': 仅包含负载分析数据
 * 'memory': 仅包含内存分析数据
 * 'both': 同时包含负载和内存分析数据
 */
export type DataType = 'perf' | 'memory' | 'both';

export interface JSONData {
  version: string;
  type: number;
  versionCode: number;
  basicInfo: BasicInfo;
  perf?: PerfData; // 负载数据（可选）
  trace?: TraceData;
  more?: MoreData;
  ui?: {
    animate?: UIAnimateData; // UI 动画数据
  };
  dataType?: DataType; // 数据类型标记，用于前台判断显示哪些页面
}

// ==================== 默认值生成函数 ====================
// 辅助函数创建默认对象
function createDefaultStutterDetail(): StutterDetail {
  return {
    vsync: 0,
    ts: 0,
    actual_duration: 0,
    expected_duration: 0,
    exceed_time: 0,
    exceed_frames: 0,
    stutter_level: 0,
    level_description: "",
    src: "",
    dst: 0
  };
}

function createDefaultFpsWindow(): FpsWindow {
  return {
    start_time: 0,
    end_time: 0,
    start_time_ts: 0,
    end_time_ts: 0,
    frame_count: 0,
    fps: 0
  };
}

function createDefaultCallstackFrame(): CallstackFrame {
  return {
    depth: 0,
    file_id: 0,
    path: "",
    symbol_id: 0,
    symbol: ""
  };
}

function createDefaultEmptyFrame(): EmptyFrame {
  return {
    ts: 0,
    dur: 0,
    ipid: 0,
    itid: 0,
    pid: 0,
    tid: 0,
    callstack_id: 0,
    process_name: "",
    thread_name: "",
    callstack_name: "",
    frame_load: 0,
    is_main_thread: 0,
    sample_callchains: [{
      timestamp: 0,
      event_count: 0,
      load_percentage: 0,
      callchain: [createDefaultCallstackFrame()]
    }]
  };
}

function createDefaultFrameLoad(): FrameLoad {
  return {
    ts: 0,
    dur: 0,
    tid: 0,
    process_name: "",
    thread_name: "",
    frame_load: 0,
    sample_callchains: [{
      timestamp: 0,
      event_count: 0,
      load_percentage: 0,
      callchain: [createDefaultCallstackFrame()]
    }]
  };
}

function createDefaultVSyncFrequencyAnomaly(): VSyncFrequencyAnomaly {
  return {
    type: "",
    start_vsync: 0,
    end_vsync: 0,
    start_ts: 0,
    end_ts: 0,
    duration: 0,
    interval_count: 0,
    avg_interval: 0,
    avg_frequency: 0,
    min_frequency: 0,
    max_frequency: 0,
    severity: "",
    description: ""
  };
}

function createDefaultVSyncFrameMismatch(): VSyncFrameMismatch {
  return {
    type: "",
    vsync: 0,
    expect_frames: 0,
    actual_frames: 0,
    description: "",
    ts: 0,
    thread_name: "",
    process_name: ""
  };
}

/** 获取默认的帧步骤数据 */
export function getDefaultFrameStepData(): FrameStepData {
  return {
    runtime: "",
    statistics: {
      total_frames: 0,
      frame_stats: {
        ui: { total: 0, stutter: 0, stutter_rate: 0 },
        render: { total: 0, stutter: 0, stutter_rate: 0 },
        sceneboard: { total: 0, stutter: 0, stutter_rate: 0 }
      },
      total_stutter_frames: 0,
      stutter_rate: 0,
      stutter_levels: { level_1: 0, level_2: 0, level_3: 0 }
    },
    stutter_details: {
      ui_stutter: [createDefaultStutterDetail()],
      render_stutter: [createDefaultStutterDetail()]
    },
    fps_stats: {
      average_fps: 0,
      min_fps: 0,
      max_fps: 0,
      fps_windows: [createDefaultFpsWindow()],
      low_fps_window_count: 0
    }
  };
}

/** 获取默认的空帧步骤数据 */
export function getDefaultEmptyFrameStepData(): EmptyFrameStepData {
  return {
    status: "unknow",
    summary: {
      total_load: 0,
      empty_frame_load: 0,
      empty_frame_percentage: 0,
      background_thread_load: 0,
      background_thread_percentage: 0,
      total_empty_frames: 0,
      empty_frames_with_load: 0
    },
    top_frames: {
      main_thread_empty_frames: [createDefaultEmptyFrame()],
      background_thread: [createDefaultEmptyFrame()]
    }
  };
}

/** 获取默认的组件复用步骤数据 */
export function getDefaultComponentResuStepData(): ComponentResuStepData {
  return {
    total_builds: 0,
    recycled_builds: 0,
    reusability_ratio: 0,
    max_component: ""
  };
}

/** 获取默认的帧数据（包含一个默认步骤） */
export function getDefaultFrameData(): FrameData {
  return {
    step1: getDefaultFrameStepData()
  };
}

/** 获取默认的空帧数据（包含一个默认步骤） */
export function getDefaultEmptyFrameData(): EmptyFrameData {
  return {
    step1: getDefaultEmptyFrameStepData()
  };
}

/** 获取默认的组件复用数据（包含一个默认步骤） */
export function getDefaultComponentResuData(): ComponentResuData {
  return {
    step1: getDefaultComponentResuStepData()
  };
}

/** 获取默认的帧负载步骤数据 */
export function getDefaultFrameLoadsStepData(): FrameLoadsStepData {
  return {
    status: "unknown",
    summary: {
      total_frames: 0,
      total_load: 0,
      average_load: 0,
      max_load: 0,
      min_load: 0
    },
    top_frames: [createDefaultFrameLoad()]
  };
}

/** 获取默认的帧负载数据（包含一个默认步骤） */
export function getDefaultFrameLoadsData(): FrameLoadsData {
  return {
    step1: getDefaultFrameLoadsStepData()
  };
}

/** 获取默认的VSync异常步骤数据 */
export function getDefaultVSyncAnomalyStepData(): VSyncAnomalyStepData {
  return {
    status: "unknown",
    statistics: {
      total_vsync_signals: 0,
      frequency_anomalies_count: 0,
      frame_mismatch_count: 0,
      anomaly_rate: 0
    },
    frequency_anomalies: [createDefaultVSyncFrequencyAnomaly()],
    frame_mismatches: [createDefaultVSyncFrameMismatch()]
  };
}

/** 获取默认的VSync异常数据（包含一个默认步骤） */
export function getDefaultVSyncAnomalyData(): VSyncAnomalyData {
  return {
    step1: getDefaultVSyncAnomalyStepData()
  };
}

export function getDefaultColdStartStepData(): ColdStartStepData {
  return {
    summary: {
      total_file_number: 0,
      total_time_ms: 0,
      used_file_count: 0,
      used_file_time_ms: 0,
      unused_file_count: 0,
      unused_file_time_ms: 0
    },
    used_files_top10: [],
    unused_files_top10: []
  };
}

export function getDefaultColdStartData(): ColdStartData {
  return {
    step1: getDefaultColdStartStepData()
  };
}

/**
 * 安全处理冷启动数据 - 替换无效值为默认结构
 * @param data 原始冷启动数据
 * @returns 处理后的有效冷启动数据
 */
export function safeProcessColdStartData(data: ColdStartData | null | undefined): ColdStartData {
  if (!data) return getDefaultColdStartData();

  const result: ColdStartData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultColdStartStepData();
  }

  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultColdStartStepData();
  }

  return result;
}

/**
 * 安全处理帧负载数据 - 替换无效值为默认结构
 * @param data 原始帧负载数据
 * @returns 处理后的有效帧负载数据
 */
export function safeProcessFrameLoadsData(data: FrameLoadsData | null | undefined): FrameLoadsData {
  if (!data) return getDefaultFrameLoadsData();

  const result: FrameLoadsData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultFrameLoadsStepData();
  }

  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultFrameLoadsStepData();
  }

  return result;
}

/**
 * 安全处理VSync异常数据 - 替换无效值为默认结构
 * @param data 原始VSync异常数据
 * @returns 处理后的有效VSync异常数据
 */
export function safeProcessVSyncAnomalyData(data: VSyncAnomalyData | null | undefined): VSyncAnomalyData {
  if (!data) return getDefaultVSyncAnomalyData();

  const result: VSyncAnomalyData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultVSyncAnomalyStepData();
  }

  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultVSyncAnomalyStepData();
  }

  return result;
}

/** 获取默认的故障树步骤数据 */
export function getDefaultFaultTreeStepData(): FaultTreeStepData {
  return {
    arkui: {
      animator: 0,
      HandleOnAreaChangeEvent: 0,
      HandleVisibleAreaChangeEvent: 0,
      GetDefaultDisplay: 0,
      MarshRSTransactionData: 0
    },
    RS: {
      ProcessedNodes: {
        ts: 0.0,
        count: 0
      },
      DisplayNodeSkipTimes: 0,
      UnMarshRSTransactionData: 0,
      AnimateSize: {
        nodeSizeSum: 0,
        totalAnimationSizeSum: 0
      }
    },
    av_codec: {
      soft_decoder: false,
      BroadcastControlInstructions: 0,
      VideoDecodingInputFrameCount: 0,
      VideoDecodingConsumptionFrame: 0
    },
    Audio: {
      AudioWriteCB: 0,
      AudioReadCB: 0,
      AudioPlayCb: 0,
      AudioRecCb: 0
    }
  };
}

/** 获取默认的故障树数据（包含一个默认步骤） */
export function getDefaultFaultTreeData(): FaultTreeData {
  return {
    step1: getDefaultFaultTreeStepData()
  };
}

/**
 * 安全处理故障树数据 - 替换无效值为默认结构
 * @param data 原始故障树数据
 * @returns 处理后的有效故障树数据
 */
export function safeProcessFaultTreeData(data: FaultTreeData | null | undefined): FaultTreeData {
  if (!data) return getDefaultFaultTreeData();

  const result: FaultTreeData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultFaultTreeStepData();
  }

  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultFaultTreeStepData();
  }

  return result;
}

// ==================== UI 动画数据类型 ====================

// 图像动画区域
export interface ImageAnimationRegion {
  component: {
    type: string;
    bounds_rect: [number, number, number, number];
    path: string;
    attributes: Record<string, unknown>;
    id: string;
  };
  comparison_result?: {
    similarity_percentage: number;
    hash_distance: number;
  };
  is_animation: boolean;
  animation_type?: string;
  region?: [number, number, number, number];
  similarity?: number;
}

// 元素树动画区域
export interface TreeAnimationRegion {
  component: {
    type: string;
    bounds_rect: [number, number, number, number];
    path: string;
    attributes: Record<string, unknown>;
    id: string;
  };
  is_animation: boolean;
  comparison_result?: Array<{
    attribute: string;
    value1: string;
    value2: string;
  }>;
  animate_type?: string;
}

export interface UIAnimatePhaseData {
  image_animations?: {
    animation_regions: ImageAnimationRegion[];
    animation_count: number;
  };
  tree_animations?: {
    animation_regions: TreeAnimationRegion[];
    animation_count: number;
  };
  marked_images_base64?: string[]; // base64 编码的图片
  marked_images_paths?: string[]; // 原始图片路径（调试用）
  error?: string;
}

export interface UIAnimateStepData {
  start_phase?: UIAnimatePhaseData;
  end_phase?: UIAnimatePhaseData;
  summary?: {
    total_animations: number;
    start_phase_animations: number;
    end_phase_animations: number;
    start_phase_tree_changes: number;
    end_phase_tree_changes: number;
    has_animations: boolean;
  };
  error?: string;
}

export interface UIAnimateData {
  [stepKey: string]: UIAnimateStepData; // step1, step2, etc.
}

// 压缩后的 UI 动画数据类型
export interface CompressedUIAnimateStepData {
  compressed: true;
  data: string; // base64 编码的压缩数据
}

export interface CompressedUIAnimateData {
  [stepKey: string]: CompressedUIAnimateStepData | UIAnimateStepData;
}

// ==================== Store 定义 ====================
interface JsonDataState {
  version: string | null;
  basicInfo: BasicInfo | null;
  compareBasicInfo: BasicInfo | null;
  perfData: PerfData | null;
  frameData: FrameData | null;
  emptyFrameData: EmptyFrameData | null;
  comparePerfData: PerfData | null;
  componentResuData: ComponentResuData | null;
  coldStartData: ColdStartData | null;
  gcThreadData: GcThreadData | null;
  frameLoadsData: FrameLoadsData | null;
  vsyncAnomalyData: VSyncAnomalyData | null;
  faultTreeData: FaultTreeData | null;
  compareFaultTreeData: FaultTreeData | null;
  baseMark: string | null;
  compareMark: string | null;
  flameGraph: Record<string, string> | null; // 按步骤组织的火焰图数据，每个步骤已单独压缩
  nativeMemoryData: NativeMemoryData | null; // Native Memory数据
  uiAnimateData: UIAnimateData | null; // UI 动画数据
}

/**
 * 安全处理帧数据 - 替换无效值为默认结构
 * @param data 原始帧数据
 * @returns 处理后的有效帧数据
 */
function safeProcessFrameData(data: FrameData | null | undefined): FrameData {
  if (!data) return getDefaultFrameData();

  const result: FrameData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultFrameStepData();
  }
  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultFrameStepData();
  }
  return result;
}

/**
 * 安全处理空帧数据 - 替换无效值为默认结构
 * @param data 原始空帧数据
 * @returns 处理后的有效空帧数据
 */
function safeProcessEmptyFrameData(data: EmptyFrameData | null | undefined): EmptyFrameData {
  if (!data) return getDefaultEmptyFrameData();

  const result: EmptyFrameData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultEmptyFrameStepData();
  }
  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultEmptyFrameStepData();
  }
  return result;
}

/**
 * 安全处理组件复用数据 - 替换无效值为默认结构
 * @param data 原始组件复用数据
 * @returns 处理后的有效组件复用数据
 */
function safeProcessComponentResuData(data: ComponentResuData | null | undefined): ComponentResuData {
  if (!data) return getDefaultComponentResuData();

  const result: ComponentResuData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultComponentResuStepData();
  }
  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultComponentResuStepData();
  }
  return result;
}

export const useJsonDataStore = defineStore('config', {
  state: (): JsonDataState => ({
    version: null,
    basicInfo: null,
    compareBasicInfo: null,
    perfData: null,
    frameData: null,
    emptyFrameData: null,
    comparePerfData: null,
    componentResuData: null,
    coldStartData: null,
    gcThreadData: null,
    frameLoadsData: null,
    vsyncAnomalyData: null,
    faultTreeData: null,
    compareFaultTreeData: null,
    baseMark: null,
    compareMark: null,
    flameGraph: null,
    nativeMemoryData: null,
    uiAnimateData: null,
  }),

  actions: {
    /**
     * 解压缩内存数据
     * 参考火焰图的解压缩逻辑
     */
    decompressNativeMemoryData(nativeMemData: CompressedNativeMemoryData): NativeMemoryData {
      if (!nativeMemData || typeof nativeMemData !== 'object') {
        return nativeMemData as NativeMemoryData;
      }

      const decompressed: NativeMemoryData = {};

      for (const [stepKey, stepData] of Object.entries(nativeMemData)) {
        if (typeof stepData === 'object' && stepData !== null && 'compressed' in stepData && stepData.compressed) {
          // 解压缩记录数据
          const compressedStepData = stepData as CompressedNativeMemoryStepData;
          try {
            const compressedRecords = compressedStepData.records;

            // 检查是否为分块压缩
            const isChunked = 'chunked' in compressedStepData && compressedStepData.chunked;

            let records: NativeMemoryRecord[] = [];

            if (isChunked && Array.isArray(compressedRecords)) {
              // 分块解压缩
              console.log(`解压缩分块内存数据 ${stepKey}: ${compressedStepData.chunk_count} 个块, ${compressedStepData.total_records} 条记录`);

              for (let i = 0; i < compressedRecords.length; i++) {
                const compressedChunk = compressedRecords[i];

                try {
                  // Base64解码
                  const binaryString = atob(compressedChunk);
                  const bytes = new Uint8Array(binaryString.length);
                  for (let j = 0; j < binaryString.length; j++) {
                    bytes[j] = binaryString.charCodeAt(j);
                  }

                  // 使用pako解压缩为 Uint8Array（避免字符串长度限制）
                  const decompressedBytes = pako.inflate(bytes);

                  // 使用 TextDecoder 进行流式解码（支持大数据）
                  const decoder = new TextDecoder('utf-8');
                  const decompressedStr = decoder.decode(decompressedBytes);

                  // 解析 JSON
                  const chunkRecords = JSON.parse(decompressedStr) as NativeMemoryRecord[];
                  records = records.concat(chunkRecords);

                  console.log(`  解压缩块 ${i + 1}/${compressedRecords.length}: ${compressedChunk.length} -> ${decompressedBytes.length} 字节, ${chunkRecords.length} 条记录`);
                } catch (chunkError) {
                  console.error(`解压缩块 ${i + 1}/${compressedRecords.length} 失败:`, chunkError);
                  // 继续处理下一个块
                }
              }

              console.log(`分块解压缩完成 ${stepKey}: 总共 ${records.length} 条记录`);
            } else if (typeof compressedRecords === 'string') {
              // 单块解压缩（原有逻辑）
              // Base64解码
              const binaryString = atob(compressedRecords);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }

              // 使用pako解压缩为 Uint8Array（避免字符串长度限制）
              const decompressedBytes = pako.inflate(bytes);

              // 使用 TextDecoder 进行流式解码（支持大数据）
              const decoder = new TextDecoder('utf-8');
              const decompressedStr = decoder.decode(decompressedBytes);

              // 解析 JSON
              records = JSON.parse(decompressedStr) as NativeMemoryRecord[];

              console.log(`解压缩内存数据 ${stepKey}: ${compressedRecords.length} -> ${decompressedBytes.length} 字节`);
            }

            // 恢复原始格式，转换 stats 字段名（后端使用下划线，前端使用驼峰）
            const rawStats = (compressedStepData.stats || {}) as BackendNativeMemoryStepStats & NativeMemoryStepStats;
            const stats: NativeMemoryStepStats = {
              peakMemorySize: rawStats.peak_memory_size || rawStats.peakMemorySize || 0,
              peakMemoryDuration: rawStats.peak_memory_duration || rawStats.peakMemoryDuration || 0,
              averageMemorySize: rawStats.average_memory_size || rawStats.averageMemorySize || 0,
            };

            // 优化：对记录按时间排序，以便后续使用二分查找
            console.log(`对 ${stepKey} 的 ${records.length} 条记录按时间排序...`);
            const sortStartTime = performance.now();
            records.sort((a, b) => a.relativeTs - b.relativeTs);
            const sortEndTime = performance.now();
            console.log(`排序完成，耗时: ${(sortEndTime - sortStartTime).toFixed(2)}ms`);

            decompressed[stepKey] = {
              peak_time: compressedStepData.peak_time,
              peak_value: compressedStepData.peak_value,
              stats: stats,
              records: records,
              callchains: compressedStepData.callchains,
            };
          } catch (error) {
            console.error(`解压缩内存数据失败 ${stepKey}:`, error);
            // 解压缩失败时返回空数据
            const rawStats = (compressedStepData.stats || {}) as BackendNativeMemoryStepStats & NativeMemoryStepStats;
            const stats: NativeMemoryStepStats = {
              peakMemorySize: rawStats.peak_memory_size || rawStats.peakMemorySize || 0,
              peakMemoryDuration: rawStats.peak_memory_duration || rawStats.peakMemoryDuration || 0,
              averageMemorySize: rawStats.average_memory_size || rawStats.averageMemorySize || 0,
            };

            decompressed[stepKey] = {
              peak_time: compressedStepData.peak_time,
              peak_value: compressedStepData.peak_value,
              stats: stats,
              records: [],
              callchains: compressedStepData.callchains,
            };
          }
        } else {
          // 未压缩的数据，需要转换 stats 字段名
          const rawStepData = stepData as NativeMemoryStepData & { stats?: BackendNativeMemoryStepStats & NativeMemoryStepStats };
          const rawStats = (rawStepData.stats || {}) as BackendNativeMemoryStepStats & NativeMemoryStepStats;
          const stats: NativeMemoryStepStats = {
            peakMemorySize: rawStats.peak_memory_size || rawStats.peakMemorySize || 0,
            peakMemoryDuration: rawStats.peak_memory_duration || rawStats.peakMemoryDuration || 0,
            averageMemorySize: rawStats.average_memory_size || rawStats.averageMemorySize || 0,
          };

          // 优化：对记录按时间排序，以便后续使用二分查找
          const records = rawStepData.records || [];
          if (records.length > 0) {
            console.log(`对 ${stepKey} 的 ${records.length} 条记录按时间排序...`);
            const sortStartTime = performance.now();
            records.sort((a, b) => a.relativeTs - b.relativeTs);
            const sortEndTime = performance.now();
            console.log(`排序完成，耗时: ${(sortEndTime - sortStartTime).toFixed(2)}ms`);
          }

          decompressed[stepKey] = {
            peak_time: rawStepData.peak_time,
            peak_value: rawStepData.peak_value,
            stats: stats,
            records: records,
            callchains: rawStepData.callchains,
          };
        }
      }

      return decompressed;
    },

    /**
     * 解压缩 UI 动画数据
     * 参考内存数据的解压缩逻辑
     */
    decompressUIAnimateData(uiAnimateData: CompressedUIAnimateData): UIAnimateData {
      if (!uiAnimateData || typeof uiAnimateData !== 'object') {
        return uiAnimateData as UIAnimateData;
      }

      const decompressed: UIAnimateData = {};

      for (const [stepKey, stepData] of Object.entries(uiAnimateData)) {
        if (typeof stepData === 'object' && stepData !== null && 'compressed' in stepData && stepData.compressed) {
          // 解压缩步骤数据
          const compressedStepData = stepData as CompressedUIAnimateStepData;
          try {
            const compressedData = compressedStepData.data;

            // Base64解码
            const binaryString = atob(compressedData);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }

            // 使用pako解压缩
            const decompressedBytes = pako.inflate(bytes);

            // 使用 TextDecoder 进行解码
            const decoder = new TextDecoder('utf-8');
            const decompressedStr = decoder.decode(decompressedBytes);

            // 解析 JSON
            const stepDataParsed = JSON.parse(decompressedStr) as UIAnimateStepData;

            decompressed[stepKey] = stepDataParsed;

            console.log(`解压缩UI动画数据 ${stepKey}: ${compressedData.length} -> ${decompressedBytes.length} 字节`);
          } catch (error) {
            console.error(`解压缩UI动画数据失败 ${stepKey}:`, error);
            // 解压缩失败时，返回空数据
            decompressed[stepKey] = {
              error: `解压缩失败: ${error}`,
            };
          }
        } else {
          // 未压缩的数据直接使用
          decompressed[stepKey] = stepData as UIAnimateStepData;
        }
      }

      return decompressed;
    },

    /**
     * 解压缩 trace 数据字段（如 frames、emptyFrame 等）
     * 这些字段可能被压缩为 { compressed: true, data: "base64..." } 格式
     */
    decompressTraceField(fieldData: any): any {
      // 检查是否是压缩格式
      if (typeof fieldData === 'object' && fieldData !== null && 'compressed' in fieldData && fieldData.compressed) {
        try {
          const compressedData = fieldData.data;

          // Base64解码
          const binaryString = atob(compressedData);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }

          // 使用pako解压缩
          const decompressedBytes = pako.inflate(bytes);

          // 使用 TextDecoder 进行解码
          const decoder = new TextDecoder('utf-8');
          const decompressedStr = decoder.decode(decompressedBytes);

          // 解析 JSON
          const decompressedData = JSON.parse(decompressedStr);

          console.log(`解压缩 trace 数据: ${compressedData.length} -> ${decompressedBytes.length} 字节`);

          return decompressedData;
        } catch (error) {
          console.error('解压缩 trace 数据失败:', error);
          // 解压缩失败时，返回原数据
          return fieldData;
        }
      }

      // 未压缩的数据直接返回
      return fieldData;
    },

    setJsonData(jsonData: JSONData, compareJsonData: JSONData) {
      this.version = jsonData.version;
      this.basicInfo = jsonData.basicInfo;

      this.perfData = jsonData.perf || null;
      this.baseMark = window.baseMark;
      this.compareMark = window.compareMark;

      if (jsonData.trace) {
        // 解压缩可能被压缩的 trace 数据字段
        const decompressedTrace = {
          frames: this.decompressTraceField(jsonData.trace.frames),
          emptyFrame: this.decompressTraceField(jsonData.trace.emptyFrame),
          componentReuse: jsonData.trace.componentReuse, // 这个字段通常不大，不需要压缩
          coldStart: jsonData.trace.coldStart,
          gc_thread: jsonData.trace.gc_thread,
          frameLoads: this.decompressTraceField(jsonData.trace.frameLoads),
          vsyncAnomaly: this.decompressTraceField(jsonData.trace.vsyncAnomaly),
          faultTree: jsonData.trace.faultTree,
        };

        // 安全处理所有 trace 相关数据
        this.frameData = safeProcessFrameData(decompressedTrace.frames);
        this.emptyFrameData = safeProcessEmptyFrameData(decompressedTrace.emptyFrame);
        this.componentResuData = safeProcessComponentResuData(decompressedTrace.componentReuse);
        this.coldStartData = safeProcessColdStartData(decompressedTrace.coldStart);
        this.gcThreadData = safeProcessGcThreadData(decompressedTrace.gc_thread);
        this.frameLoadsData = safeProcessFrameLoadsData(decompressedTrace.frameLoads);
        this.vsyncAnomalyData = safeProcessVSyncAnomalyData(decompressedTrace.vsyncAnomaly);
        this.faultTreeData = safeProcessFaultTreeData(decompressedTrace.faultTree);
      } else {
        // 当没有 trace 数据时，设置完整的默认结构
        this.frameData = getDefaultFrameData();
        this.emptyFrameData = getDefaultEmptyFrameData();
        this.componentResuData = getDefaultComponentResuData();
        this.coldStartData = getDefaultColdStartData();
        this.gcThreadData = getDefaultGcThreadData();
        this.frameLoadsData = getDefaultFrameLoadsData();
        this.vsyncAnomalyData = getDefaultVSyncAnomalyData();
        this.faultTreeData = getDefaultFaultTreeData();
      }
      if (jsonData.more) {
        // 火焰图 - 按步骤组织的数据，每个步骤已单独压缩
        this.flameGraph = jsonData.more.flame_graph || null;
        // Native Memory数据 - 按步骤组织的数据（类似trace_frames.json）
        // 如果是原始的分层格式，需要转换为平铺格式
        if (jsonData.more.native_memory) {
          const nativeMemData = jsonData.more.native_memory;
          // 检查是否是分层格式（有process_dimension字段）
          if (typeof nativeMemData === 'object' && 'process_dimension' in nativeMemData) {
            this.nativeMemoryData = transformNativeMemoryData(nativeMemData);
          } else {
            // 已经是平铺格式，但可能需要解压缩
            this.nativeMemoryData = this.decompressNativeMemoryData(nativeMemData);
          }
        } else {
          this.nativeMemoryData = null;
        }
      }

      // 加载 UI 动画数据
      if (jsonData.ui && jsonData.ui.animate) {
        // 可能需要解压缩
        this.uiAnimateData = this.decompressUIAnimateData(jsonData.ui.animate as CompressedUIAnimateData);
      } else {
        this.uiAnimateData = null;
      }

      if (JSON.stringify(compareJsonData) === "\"/tempCompareJsonData/\"") {
        window.initialPage = 'perf';
        this.compareFaultTreeData = null;
      } else {
        this.compareBasicInfo = compareJsonData.basicInfo;
        this.comparePerfData = compareJsonData.perf || null;

        // 处理对比版本的故障树数据
        if (compareJsonData.trace && compareJsonData.trace.faultTree) {
          this.compareFaultTreeData = safeProcessFaultTreeData(compareJsonData.trace.faultTree);
        } else {
          this.compareFaultTreeData = getDefaultFaultTreeData();
        }

        window.initialPage = 'perf_compare';
      }
    },
  },
});

export const useFilterModeStore = defineStore('filterMode', {
  state: () => ({
    filterMode: 'string' as string,
  })
});

export const useProcessNameQueryStore = defineStore('processNameQuery', {
  state: () => ({
    processNameQuery: '' as string,
  })
});

export const useThreadNameQueryStore = defineStore('threadNameQuery', {
  state: () => ({
    threadNameQuery: '' as string,
  })
});

export const useFileNameQueryStore = defineStore('fileNameQuery', {
  state: () => ({
    fileNameQuery: '' as string,
  })
});

export const useSymbolNameQueryStore = defineStore('symbolNameQuery', {
  state: () => ({
    symbolNameQuery: '' as string,
  })
});


export const useCategoryStore = defineStore('categoryNameQuery', {
  state: () => ({
    categoriesQuery: '' as string,
  })
});

export const useComponentNameStore = defineStore('componentNameQuery', {
  state: () => ({
    componentNameQuery: '' as string,
  })
});

/** 获取默认的GC线程步骤数据 */
export function getDefaultGcThreadStepData(): GcThreadStepData {
  return {
    FullGC: 0,
    SharedFullGC: 0,
    SharedGC: 0,
    PartialGC: 0,
    GCStatus: "OK",
    perf_percentage: 0.0
  };
}

export function getDefaultGcThreadData(): GcThreadData {
  return {
    step1: getDefaultGcThreadStepData()
  };
}

/**
 * 安全处理GC线程数据 - 替换无效值为默认结构
 * @param data 原始GC线程数据
 * @returns 处理后的有效GC线程数据
 */
export function safeProcessGcThreadData(data: GcThreadData | null | undefined): GcThreadData {
  if (!data) return getDefaultGcThreadData();

  const result: GcThreadData = {};

  // 遍历所有步骤，确保每个步骤都有有效数据
  for (const [stepName, stepData] of Object.entries(data)) {
    // 如果步骤数据无效，使用默认结构替换
    result[stepName] = stepData ?? getDefaultGcThreadStepData();
  }

  // 确保至少有一个步骤
  if (Object.keys(result).length === 0) {
    result.step1 = getDefaultGcThreadStepData();
  }

  return result;
}
