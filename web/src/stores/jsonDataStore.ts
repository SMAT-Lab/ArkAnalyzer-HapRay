import { defineStore } from 'pinia';
import pako from 'pako';
import type { NativeMemoryData } from './nativeMemory';

// ==================== 类型定义 ====================

/** 组件分类 */
export enum ComponentCategory {
  APP = 1,
  ArkUI = 2,
  OS_Runtime = 3,
  SYS_SDK = 4,
  RN = 5,
  Flutter = 6,
  WEB = 7,
  KMP = 8,
  UNKNOWN = -1,
}

/** 负载事件类型 */
export enum PerfEvent {
  CYCLES_EVENT = 0,
  INSTRUCTION_EVENT = 1,
}


export interface BasicInfo {
  rom_version: string;
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
}

interface Step {
  step_name: string;
  step_id: number;
}

export interface PerfDataStep {
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
    thirdCategoryName?: string;
    subCategoryName?: string;
    categoryName?: string;
    componentCategory: ComponentCategory;
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
  background_thread_percentage_in_empty_frame: number; // 后台线程占空刷帧的百分比
  main_thread_load?: number; // 主线程负载（可选）
  main_thread_percentage_in_empty_frame?: number; // 主线程占空刷帧的百分比（可选）
  total_empty_frames: number;
  empty_frames_with_load: number;
  severity_level?: string; // 严重程度级别（可选）
  severity_description?: string; // 严重程度描述（可选）
  thread_statistics?: { // 线程统计（可选）
    top_threads: Array<{
      thread_id: number;
      tid: number;
      thread_name: string;
      process_name: string;
      total_load: number;
      percentage: number;
      frame_count: number;
    }>;
  };
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
  value?: number;  // 每个深度的负载值
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

interface WakeupThread {
  itid: number;
  tid: number;
  pid: number;
  thread_name: string;
  process_name: string;
  is_system_thread: boolean;
  wakeup_depth?: number; // 唤醒链深度（可选）
}

interface EmptyFrame {
  ts: number;
  dur: number;
  ipid?: number;
  itid?: number;
  pid?: number; // 进程ID（可选，向后兼容）
  tid?: number; // 线程ID（可选，向后兼容）
  thread_id?: number; // 线程ID（新字段名，与tid相同）
  callstack_id?: number;
  process_name: string;
  thread_name: string;
  callstack_name?: string;
  frame_load: number;
  is_main_thread: number;
  sample_callchains: SampleCallchain[];
  vsync?: number | string; // VSync标识
  flag?: number; // 帧标志
  type?: number; // 帧类型
  wakeup_threads?: WakeupThread[]; // 唤醒链线程（新字段名）
  related_threads?: WakeupThread[]; // 唤醒链线程（旧字段名，向后兼容）
}

interface EmptyFrameStepData {
  status: string;
  summary: EmptyFrameSummary;
  top_frames: EmptyFrame[];  // 统一列表，不再区分主线程和后台线程
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

// IPC Binder 进程统计数据
interface IpcBinderProcessStat {
  caller_proc: string;
  callee_proc: string;
  count: number;
  avg_latency: number;
  max_latency: number;
  qps: number;
}

// IPC Binder 接口统计数据
interface IpcBinderInterfaceStat {
  code: string;
  count: number;
  avg_latency: number;
  max_latency: number;
  qps: number;
  top_caller_proc: string;
  top_callee_proc: string;
}

// IPC Binder 故障树数据
interface FaultTreeIpcBinderData {
  total_transactions: number;        // 总通信次数
  high_latency_count: number;        // 高延迟通信次数 (>100ms)
  avg_latency: number;               // 平均延迟(ms)
  max_latency: number;               // 最大延迟(ms)
  top_processes: IpcBinderProcessStat[];  // Top 5 进程对
  top_interfaces: IpcBinderInterfaceStat[]; // Top 5 接口
}

interface FaultTreeStepData {
  arkui: FaultTreeArkUIData;
  RS: FaultTreeRSData;
  av_codec: FaultTreeAVCodecData;
  Audio: FaultTreeAudioData;
  ipc_binder?: FaultTreeIpcBinderData;  // IPC Binder 数据（可选）
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
  steps: Step[];
  perf?: PerfData; // 负载数据（可选）
  trace?: TraceData;
  more?: MoreData;
  ui?: {
    animate?: UIAnimateData; // UI 动画数据
    raw?: UIRawData; // UI 原始数据（用于前端实时对比）
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
    thread_id: 0,
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
    }],
    vsync: 0,
    flag: 0,
    type: 0,
    wakeup_threads: [],
    related_threads: []
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
      background_thread_percentage_in_empty_frame: 0,
      main_thread_load: 0,
      main_thread_percentage_in_empty_frame: 0,
      total_empty_frames: 0,
      empty_frames_with_load: 0,
      severity_level: "normal",
      severity_description: "正常：未检测到空刷帧",
      thread_statistics: {
        top_threads: []
      }
    },
    top_frames: [createDefaultEmptyFrame()]  // 统一列表，不再区分主线程和后台线程
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

// 超出尺寸Image分析
export interface ExceedingImageInfo {
  path: string;
  id: string;
  bounds_rect: [number, number, number, number];
  frameRect: {
    width: number;
    height: number;
    area: number;
    str: string;
  };
  renderedImageSize: {
    width: number;
    height: number;
    area: number;
    str: string;
  };
  excess: {
    width: number;
    height: number;
    area: number;
    ratio: number;
  };
  memory: {
    raw_memory_bytes: number;
    raw_memory_mb: number;
    frame_memory_bytes: number;
    frame_memory_mb: number;
    excess_memory_bytes: number;
    excess_memory_mb: number;
  };
}

export interface ImageSizeAnalysis {
  total_images: number;
  images_exceeding_framerect: ExceedingImageInfo[];
  total_excess_memory_bytes: number;
  total_excess_memory_mb: number;
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
  image_size_analysis?: ImageSizeAnalysis;
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

// UI原始数据类型（用于对比）
export interface UIRawStepData {
  screenshots: {
    start: string[]; // base64编码的截图数组
    end: string[];
  };
  trees: {
    start: string[]; // 组件树文本数组
    end: string[];
  };
}

export interface UIRawData {
  [stepKey: string]: UIRawStepData; // step1, step2, etc.
}

// ArkUI 组件树节点类型
export interface ArkUITreeNode {
  name: string;
  children: ArkUITreeNode[];
  attributes: Record<string, unknown>;
  depth: number;
}

// UI 对比差异类型
export interface UIAttributeDifference {
  attribute: string;
  value1: unknown;
  value2: unknown;
}

export interface UIComponent {
  type: string;
  id?: string;
  bounds_rect?: number[];
  path?: string;
  attributes?: Record<string, unknown>;
}

export interface UIComponentDifference {
  component_path: string;
  component?: UIComponent;
  comparison_result: UIAttributeDifference[];
  is_animation?: boolean;
  animate_type?: string;
}

// UI 对比数据类型
export interface UIComparePairResult {
  phase: 'start' | 'end';
  index: number;
  base_screenshot: string;
  compare_screenshot: string;
  diff_count: number;
  total_differences: number;
  filtered_count: number;
  differences: UIComponentDifference[];
  marked_images_base64: string[];
}

export interface UICompareResult {
  pairs: UIComparePairResult[];
}

// 压缩后的 UI 动画数据类型
export interface CompressedUIAnimateStepData {
  compressed: true;
  data: string; // base64 编码的压缩数据
}

export interface CompressedUIAnimateData {
  [stepKey: string]: CompressedUIAnimateStepData | UIAnimateStepData;
}

// 压缩后的 UI 原始数据类型
export interface CompressedUIRawStepData {
  compressed: true;
  data: string; // base64 编码的压缩数据
}

export interface CompressedUIRawData {
  [stepKey: string]: CompressedUIRawStepData | UIRawStepData;
}

// ==================== Store 定义 ====================
interface JsonDataState {
  version: string | null;
  basicInfo: BasicInfo | null;
  steps: Step[] | null;
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
  uiAnimateData: UIAnimateData | null; // UI 动画数据
  uiCompareData: Record<string, UICompareResult> | null; // UI 对比数据
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
    steps: null,
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
    uiAnimateData: null,
    uiCompareData: null,
  }),

  actions: {
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
     * 解压缩 UI 原始数据
     * 与 UI 动画数据使用相同的压缩格式
     */
    decompressUIRawData(uiRawData: CompressedUIRawData): UIRawData {
      if (!uiRawData || typeof uiRawData !== 'object') {
        return uiRawData as UIRawData;
      }

      const decompressed: UIRawData = {};

      for (const [stepKey, stepData] of Object.entries(uiRawData)) {
        if (typeof stepData === 'object' && stepData !== null && 'compressed' in stepData && stepData.compressed) {
          // 解压缩步骤数据
          const compressedStepData = stepData as CompressedUIRawStepData;
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
            const stepDataParsed = JSON.parse(decompressedStr) as UIRawStepData;

            decompressed[stepKey] = stepDataParsed;

            console.log(`解压缩UI原始数据 ${stepKey}: ${compressedData.length} -> ${decompressedBytes.length} 字节`);
          } catch (error) {
            console.error(`解压缩UI原始数据失败 ${stepKey}:`, error);
            // 解压缩失败时，返回空数据
            decompressed[stepKey] = {
              screenshots: { start: [], end: [] },
              trees: { start: [], end: [] },
            };
          }
        } else {
          // 未压缩的数据直接使用
          decompressed[stepKey] = stepData as UIRawStepData;
        }
      }

      return decompressed;
    },

    /**
     * Decompress trace data fields (e.g., frames, emptyFrame, etc.)
     * These fields may be compressed in the format { compressed: true, data: "base64..." }
     */
    decompressTraceField<T>(fieldData: T | { compressed: boolean; data: string }): T {
      // Check if data is in compressed format
      if (typeof fieldData === 'object' && fieldData !== null && 'compressed' in fieldData && fieldData.compressed) {
        try {
          const compressedData = (fieldData as { compressed: boolean; data: string }).data;

          // Decode base64
          const binaryString = atob(compressedData);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }

          // Decompress using pako
          const decompressedBytes = pako.inflate(bytes);

          // Decode using TextDecoder
          const decoder = new TextDecoder('utf-8');
          const decompressedStr = decoder.decode(decompressedBytes);

          // Parse JSON
          const decompressedData = JSON.parse(decompressedStr) as T;

          console.log(`[JsonDataStore] Decompressed trace data: ${compressedData.length} -> ${decompressedBytes.length} bytes`);

          return decompressedData;
        } catch (error) {
          console.error('[JsonDataStore] Failed to decompress trace data:', error);
          // Return original data if decompression fails
          return fieldData as T;
        }
      }

      // Return uncompressed data directly
      return fieldData as T;
    },

    setJsonData(jsonData: JSONData, compareJsonData: JSONData) {
      this.version = jsonData.version;
      this.basicInfo = jsonData.basicInfo;
      this.steps = jsonData.steps;
      this.perfData = jsonData.perf || null;
      this.baseMark = window.baseMark;
      this.compareMark = window.compareMark;

      if (jsonData.trace) {
        // Decompress potentially compressed trace data fields
        const decompressedTrace = {
          frames: this.decompressTraceField(jsonData.trace.frames),
          emptyFrame: this.decompressTraceField(jsonData.trace.emptyFrame),
          componentReuse: jsonData.trace.componentReuse, // This field is usually small, no compression needed
          coldStart: jsonData.trace.coldStart,
          gc_thread: jsonData.trace.gc_thread,
          frameLoads: this.decompressTraceField(jsonData.trace.frameLoads),
          vsyncAnomaly: this.decompressTraceField(jsonData.trace.vsyncAnomaly),
          faultTree: jsonData.trace.faultTree,
        };

        // Safely process all trace-related data
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
        // Flame graph - Data organized by step, each step is separately compressed
        this.flameGraph = jsonData.more.flame_graph || null;
      } else {
        this.flameGraph = null;
      }

      // Load UI animation data
      if (jsonData.ui && jsonData.ui.animate) {
        // May need decompression
        this.uiAnimateData = this.decompressUIAnimateData(jsonData.ui.animate as CompressedUIAnimateData);
        console.log('[setJsonData] 基准报告UI动画数据已加载:', Object.keys(this.uiAnimateData || {}));
      } else {
        this.uiAnimateData = null;
        console.log('[setJsonData] 基准报告无UI动画数据');
      }

      if (JSON.stringify(compareJsonData) === "\"/tempCompareJsonData/\"") {
        window.initialPage = 'perf';
        this.compareFaultTreeData = null;
        this.uiCompareData = null;
      } else {
        this.compareBasicInfo = compareJsonData.basicInfo;
        this.comparePerfData = compareJsonData.perf || null;

        // 处理对比版本的故障树数据
        if (compareJsonData.trace && compareJsonData.trace.faultTree) {
          this.compareFaultTreeData = safeProcessFaultTreeData(compareJsonData.trace.faultTree);
        } else {
          this.compareFaultTreeData = getDefaultFaultTreeData();
        }

        // 前端实时对比UI数据（逻辑已与后端完全一致）
        if (jsonData.ui?.raw && compareJsonData.ui?.raw) {
          // 解压缩 UI 原始数据
          const baseUIRaw = this.decompressUIRawData(jsonData.ui.raw as CompressedUIRawData);
          const compareUIRaw = this.decompressUIRawData(compareJsonData.ui.raw as CompressedUIRawData);

          this.uiCompareData = this.compareUIData(baseUIRaw, compareUIRaw);
          console.log('[setJsonData] 前端实时对比UI数据:', Object.keys(this.uiCompareData || {}));
        } else {
          this.uiCompareData = null;
          console.log('[setJsonData] 无法进行UI对比：缺少UI原始数据');
        }

        window.initialPage = 'perf_compare';
      }
    },

    /**
     * 对比两个报告的UI数据
     */
    compareUIData(baseUIRaw: UIRawData, compareUIRaw: UIRawData): Record<string, UICompareResult> | null {
      console.log('[compareUIData] 开始对比UI数据');

      const result: Record<string, UICompareResult> = {};

      // 遍历所有共同的step
      for (const stepKey in baseUIRaw) {
        if (compareUIRaw[stepKey]) {
          const baseStep = baseUIRaw[stepKey];
          const compareStep = compareUIRaw[stepKey];

          // 检查是否有截图和组件树
          if (!baseStep.screenshots?.end?.length || !baseStep.trees?.end?.length ||
              !compareStep.screenshots?.end?.length || !compareStep.trees?.end?.length) {
            console.log(`[compareUIData] ${stepKey}: 缺少截图或组件树数据`);
            continue;
          }

          // 对比start和end两个阶段的组件树（按截图对分组）
          const pairResults: UIComparePairResult[] = [];

          // 对比start阶段和end阶段
          for (const phase of ['start', 'end'] as const) {
            const baseTrees = baseStep.trees[phase] || [];
            const compareTrees = compareStep.trees[phase] || [];
            const baseScreenshots = baseStep.screenshots[phase] || [];
            const compareScreenshots = compareStep.screenshots[phase] || [];
            const maxPairs = Math.min(baseTrees.length, compareTrees.length);

            for (let i = 0; i < maxPairs; i++) {
              const baseTree = this.parseArkUITree(baseTrees[i]);
              const compareTree = this.parseArkUITree(compareTrees[i]);

              let allDifferences: UIComponentDifference[] = [];
              let filteredDifferences: UIComponentDifference[] = [];

              if (baseTree && compareTree) {
                // 先获取所有差异（不过滤）
                allDifferences = this.compareArkUITreesWithoutFilter(baseTree, compareTree);
                // 再应用过滤（后端逻辑：不返回过滤原因）
                filteredDifferences = this.filterDifferences(allDifferences);
              }

              pairResults.push({
                index: i + 1,
                phase: phase,
                base_screenshot: baseScreenshots[i] || '',
                compare_screenshot: compareScreenshots[i] || '',
                diff_count: filteredDifferences.length,
                total_differences: allDifferences.length,
                filtered_count: allDifferences.length - filteredDifferences.length,
                differences: filteredDifferences,
                marked_images_base64: [baseScreenshots[i] || '', compareScreenshots[i] || '']
              });
            }
          }

          const stepResult = {
            pairs: pairResults,  // 所有截图对的对比结果
            total_diff_count: pairResults.reduce((sum, p) => sum + p.diff_count, 0)
          };

          result[stepKey] = stepResult;
          console.log(`[compareUIData] ${stepKey}: ${pairResults.length} 对截图，共发现 ${stepResult.total_diff_count} 处差异`);
        }
      }

      console.log(`[compareUIData] 对比完成，共 ${Object.keys(result).length} 个步骤`);
      return Object.keys(result).length > 0 ? result : null;
    },

    /**
     * 解析ArkUI组件树文本
     */
    parseArkUITree(treeText: string): ArkUITreeNode | null {
      const lines = treeText.split('\n');
      const root: ArkUITreeNode = { name: 'Root', children: [], attributes: {}, depth: 0 };
      const stack: ArkUITreeNode[] = [root];
      let currentNode: ArkUITreeNode | null = null;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // 匹配组件行：|-> ComponentName childSize:N
        const componentMatch = line.match(/^(\s*)\|->\s*(\w+)\s+childSize:(\d+)/);
        if (componentMatch) {
          const indent = componentMatch[1];
          const componentName = componentMatch[2];
          const depth = (indent.length / 2) + 1;

          currentNode = {
            name: componentName,
            depth,
            children: [],
            attributes: { type: componentName }
          };

          // 找到父节点
          while (stack.length > 0 && stack[stack.length - 1].depth >= depth) {
            stack.pop();
          }

          if (stack.length > 0) {
            stack[stack.length - 1].children.push(currentNode);
          }

          stack.push(currentNode);
          continue;
        }

        // 解析属性行
        if (currentNode && line.includes('|')) {
          const cleanLine = line.trim().replace(/^\|/, '').trim();

          // ID
          const idMatch = cleanLine.match(/ID:\s*(\d+)/);
          if (idMatch) {
            currentNode.attributes.id = idMatch[1];
          }

          // FrameRect: RectT (x, y) - [width x height]
          const frameMatch = cleanLine.match(/FrameRect:\s*RectT\s*\(([^,]+),\s*([^)]+)\)\s*-\s*\[([^\sx]+)\s*x\s*([^\]]+)\]/);
          if (frameMatch) {
            const left = parseFloat(frameMatch[1]);
            const top = parseFloat(frameMatch[2]);
            const width = parseFloat(frameMatch[3]);
            const height = parseFloat(frameMatch[4]);
            currentNode.attributes.left = left;
            currentNode.attributes.top = top;
            currentNode.attributes.width = width;
            currentNode.attributes.height = height;
            currentNode.attributes.bounds_rect = [
              Math.floor(left),
              Math.floor(top),
              Math.floor(left + width),
              Math.floor(top + height)
            ];
          }

          // top: xxx left: xxx
          const topLeftMatch = cleanLine.match(/top:\s*([\d.]+)\s+left:\s*([\d.]+)/);
          if (topLeftMatch && !currentNode.attributes.top) {
            currentNode.attributes.top = parseFloat(topLeftMatch[1]);
            currentNode.attributes.left = parseFloat(topLeftMatch[2]);
          }

          // BackgroundColor
          const bgMatch = cleanLine.match(/BackgroundColor:\s*(#[0-9A-F]+)/i);
          if (bgMatch) {
            currentNode.attributes.backgroundColor = bgMatch[1];
          }

          // zIndex
          const zIndexMatch = cleanLine.match(/zIndex:\s*([\d-]+)/);
          if (zIndexMatch) {
            currentNode.attributes.zIndex = parseInt(zIndexMatch[1]);
          }

          // 其他通用属性（key: value格式）
          const attrMatch = cleanLine.match(/^(\w+):\s*(.+)$/);
          if (attrMatch) {
            const key = attrMatch[1];
            const value = attrMatch[2].trim();
            // 首字母小写
            const normalizedKey = key.charAt(0).toLowerCase() + key.slice(1);
            if (!currentNode.attributes[normalizedKey]) {
              currentNode.attributes[normalizedKey] = value;
            }
          }
        }
      }

      // 最终计算bounds_rect（如果还没有）
      const finalizeBounds = (node: ArkUITreeNode) => {
        if (node.attributes && !node.attributes.bounds_rect) {
          const { left, top, width, height } = node.attributes as Record<string, number>;
          if (left !== undefined && top !== undefined && width !== undefined && height !== undefined) {
            node.attributes.bounds_rect = [
              Math.floor(left),
              Math.floor(top),
              Math.floor(left + width),
              Math.floor(top + height)
            ];
          }
        }
        if (node.children) {
          node.children.forEach(finalizeBounds);
        }
      };
      finalizeBounds(root);

      return root.children.length > 0 ? root.children[0] : root;
    },

    /**
     * 对比两个ArkUI组件树（不过滤，返回所有差异）- 完全复制后端逻辑
     * 后端代码位置: perf_testing/hapray/ui_detector/arkui_tree_parser.py ArkUITreeComparator._compare_components
     */
    compareArkUITreesWithoutFilter(tree1: ArkUITreeNode, tree2: ArkUITreeNode): UIComponentDifference[] {
      const differences: UIComponentDifference[] = [];

      const compareNodes = (comp1: ArkUITreeNode, comp2: ArkUITreeNode, path: string = '') => {
        if (!comp1 || !comp2) return;

        // 构建当前组件路径（后端第538-539行）
        const compName = comp1.name || (comp1.attributes?.type as string) || 'Unknown';
        const currentPath = path ? `${path}/${compName}` : compName;

        // 比较当前组件的attributes（后端第542-557行）
        const attrsDiff = this.compareAttributes(comp1, comp2);
        if (attrsDiff.length > 0) {
          differences.push({
            component: {
              type: compName,
              bounds_rect: comp1.attributes?.bounds_rect as number[] | undefined,
              path: currentPath,
              attributes: comp1.attributes || {},
              id: comp1.attributes?.id as string | undefined
            },
            is_animation: true,
            comparison_result: attrsDiff,
            animate_type: 'attribute_animate',
            component_path: currentPath
          });
        }

        // 递归比较子组件（后端第559-566行）
        const children1 = comp1.children || [];
        const children2 = comp2.children || [];
        const minChildren = Math.min(children1.length, children2.length);

        for (let i = 0; i < minChildren; i++) {
          compareNodes(children1[i], children2[i], currentPath);
        }

        // 处理多余的子组件（后端第568-605行）
        // 注意：后端在第583和602行使用了父组件的attrs_diff，这是一个bug，但前端必须复制这个行为
        if (children1.length > children2.length) {
          for (let i = children2.length; i < children1.length; i++) {
            const comp = children1[i];
            const name = (comp.name || comp.attributes?.type || 'Unknown') as string;
            const childPath = `${currentPath}/${name}`;
            differences.push({
              component: {
                type: name,
                bounds_rect: comp.attributes?.bounds_rect as number[] | undefined,
                path: childPath,
                attributes: comp.attributes || {},
                id: comp.attributes?.id as string | undefined
              },
              is_animation: true,
              comparison_result: attrsDiff,  // 使用父组件的attrsDiff（复制后端bug）
              animate_type: 'attribute_animate',
              component_path: childPath
            });
          }
        } else if (children2.length > children1.length) {
          for (let i = children1.length; i < children2.length; i++) {
            const comp = children2[i];
            const name = (comp.name || comp.attributes?.type || 'Unknown') as string;
            const childPath = `${currentPath}/${name}`;
            differences.push({
              component: {
                type: name,
                bounds_rect: comp.attributes?.bounds_rect as number[] | undefined,
                path: childPath,
                attributes: comp.attributes || {},
                id: comp.attributes?.id as string | undefined
              },
              is_animation: true,
              comparison_result: attrsDiff,  // 使用父组件的attrsDiff（复制后端bug）
              animate_type: 'attribute_animate',
              component_path: childPath
            });
          }
        }
      };

      compareNodes(tree1, tree2);
      return differences;
    },

    /**
     * 对比两个组件的attributes（后端逻辑）
     * 后端代码位置: perf_testing/hapray/ui_detector/arkui_tree_parser.py ArkUITreeComparator._compare_attributes
     *
     * 注意：Python的 != 运算符对列表和字典进行内容比较，而JavaScript的 !== 是引用比较
     * 因此需要添加深度比较逻辑以保持与后端一致
     */
    compareAttributes(comp1: ArkUITreeNode, comp2: ArkUITreeNode): UIAttributeDifference[] {
      const differences: UIAttributeDifference[] = [];
      const attrs1 = comp1.attributes || {};
      const attrs2 = comp2.attributes || {};

      // 获取所有attributes键（后端第624行）
      const allKeys = new Set([...Object.keys(attrs1), ...Object.keys(attrs2)]);

      for (const key of allKeys) {
        const value1 = attrs1[key];
        const value2 = attrs2[key];

        // 检查是否存在差异（后端第631行）
        // Python的 != 对列表/字典进行内容比较，JavaScript需要特殊处理
        if (!this.deepEqual(value1, value2)) {
          differences.push({ attribute: key, value1: value1, value2: value2 });
        }
      }

      return differences;
    },

    /**
     * 深度比较两个值是否相等（模拟Python的 == 运算符）
     * Python中列表和字典的比较是内容比较，JavaScript需要手动实现
     */
    deepEqual(value1: unknown, value2: unknown): boolean {
      // 严格相等（包括 undefined === undefined, null === null）
      if (value1 === value2) {
        return true;
      }

      // 一个是null/undefined，另一个不是
      if (value1 == null || value2 == null) {
        return false;
      }

      // 类型不同
      if (typeof value1 !== typeof value2) {
        return false;
      }

      // 数组比较（内容比较）
      if (Array.isArray(value1) && Array.isArray(value2)) {
        if (value1.length !== value2.length) {
          return false;
        }
        for (let i = 0; i < value1.length; i++) {
          if (!this.deepEqual(value1[i], value2[i])) {
            return false;
          }
        }
        return true;
      }

      // 对象比较（内容比较）
      if (typeof value1 === 'object' && typeof value2 === 'object' && value1 !== null && value2 !== null) {
        const obj1 = value1 as Record<string, unknown>;
        const obj2 = value2 as Record<string, unknown>;
        const keys1 = Object.keys(obj1);
        const keys2 = Object.keys(obj2);

        if (keys1.length !== keys2.length) {
          return false;
        }

        for (const key of keys1) {
          if (!keys2.includes(key)) {
            return false;
          }
          if (!this.deepEqual(obj1[key], obj2[key])) {
            return false;
          }
        }
        return true;
      }

      // 其他类型（数字、字符串、布尔值等）已经在第一个if中处理
      return false;
    },

    /**
     * 过滤差异（完全复制后端逻辑）
     * 后端代码位置: perf_testing/hapray/ui_detector/ui_tree_comparator.py UITreeComparator._filter_differences
     * 注意：后端不返回过滤原因，只返回过滤后的列表
     */
    filterDifferences(allDifferences: UIComponentDifference[]): UIComponentDifference[] {
      // 后端默认忽略的属性（第28-32行）
      const DEFAULT_IGNORE_ATTRS = new Set([
        'id', 'accessibilityId',  // 系统自动生成的ID
        'rsNode', 'frameProxy', 'frameRecord',  // 渲染引擎内部状态
        'contentConstraint', 'parentLayoutConstraint', 'user defined constraint'  // 布局约束
      ]);

      const filtered: UIComponentDifference[] = [];

      // 后端第99-120行的逻辑
      for (const diff of allDifferences) {
        const filteredAttrs: UIAttributeDifference[] = [];

        for (const attrDiff of diff.comparison_result || []) {
          const attrName = attrDiff.attribute;

          // 跳过忽略的属性（后端第106-107行）
          if (DEFAULT_IGNORE_ATTRS.has(attrName)) {
            continue;
          }

          // 过滤微小变化（后端第110-111行）
          // filter_minor_changes 在后端默认为 True（ui_compare_action.py 第150行）
          if (this.isMinorChange(attrName, attrDiff)) {
            continue;
          }

          filteredAttrs.push(attrDiff);
        }

        // 如果还有差异，保留该组件（后端第116-119行）
        if (filteredAttrs.length > 0) {
          const diffCopy = { ...diff };
          diffCopy.comparison_result = filteredAttrs;
          filtered.push(diffCopy);
        }
      }

      return filtered;
    },

    /**
     * 判断是否为微小变化（完全复制后端逻辑）
     * 后端代码位置: perf_testing/hapray/ui_detector/ui_tree_comparator.py UITreeComparator._is_minor_change
     */
    isMinorChange(attrName: string, attrDiff: UIAttributeDifference): boolean {
      // 位置和尺寸的微小变化（<5px）（后端第126-132行）
      if (['top', 'left', 'width', 'height'].includes(attrName)) {
        try {
          const v1 = parseFloat(String(attrDiff.value1 || '0'));
          const v2 = parseFloat(String(attrDiff.value2 || '0'));
          return Math.abs(v1 - v2) < 5;
        } catch {
          return false;
        }
      }
      return false;
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
    subCategoryNameQuery: '' as string,
  })
});

export const useThirdCategoryNameQueryStore = defineStore('thirdCategoryNameQuery', {
  state: () => ({
    thirdCategoryNameQuery: '' as string,
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
