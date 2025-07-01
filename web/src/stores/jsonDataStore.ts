import { defineStore } from 'pinia';

// ==================== 类型定义 ====================
/** 性能事件类型 */
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
  UNKNOWN = -1,
}

/** 来源类型 */
enum OriginKind {
  UNKNOWN = 0,
  FIRST_PARTY = 1,
  OPEN_SOURCE = 2,
  THIRD_PARTY = 3,
}

interface BasicInfo {
  rom_version: string;
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
}

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
  timestamp: number;
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

interface ComponentResuStepData {
  total_builds: number;
  recycled_builds: number;
  reusability_ratio: number;
  max_component: string;
}

export type ComponentResuData = Record<string, ComponentResuStepData>;

interface TraceData {
  frames: FrameData;
  emptyFrame?: EmptyFrameData;
  componentReuse: ComponentResuData;
  coldStart?: ColdStartData;
}

export interface JSONData {
  type: number;
  versionCode: number;
  basicInfo: BasicInfo;
  perf: PerfData;
  trace?: TraceData;
}

// ==================== 默认值生成函数 ====================
// 辅助函数创建默认对象
function createDefaultStutterDetail(): StutterDetail {
  return {
    vsync: 0,
    timestamp: 0,
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

// ==================== Store 定义 ====================
interface JsonDataState {
  basicInfo: BasicInfo | null;
  compareBasicInfo: BasicInfo | null;
  perfData: PerfData | null;
  frameData: FrameData | null;
  emptyFrameData: EmptyFrameData | null;
  comparePerfData: PerfData | null;
  componentResuData: ComponentResuData | null;
  coldStartData: ColdStartData | null;
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
    basicInfo: null,
    compareBasicInfo: null,
    perfData: null,
    frameData: null,
    emptyFrameData: null,
    comparePerfData: null,
    componentResuData: null,
    coldStartData: null,
  }),

  actions: {
    setJsonData(jsonData: JSONData, compareJsonData: JSONData) {
      this.basicInfo = jsonData.basicInfo;

      if (JSON.stringify(compareJsonData) === "\"\/tempCompareJsonData\/\"") {
        this.perfData = jsonData.perf;

        if (jsonData.trace) {
          // 安全处理所有 trace 相关数据
          this.frameData = safeProcessFrameData(jsonData.trace.frames);
          this.emptyFrameData = safeProcessEmptyFrameData(jsonData.trace.emptyFrame);
          this.componentResuData = safeProcessComponentResuData(jsonData.trace.componentReuse);
          this.coldStartData = safeProcessColdStartData(jsonData.trace.coldStart);
        } else {
          // 当没有 trace 数据时，设置完整的默认结构
          this.frameData = getDefaultFrameData();
          this.emptyFrameData = getDefaultEmptyFrameData();
          this.componentResuData = getDefaultComponentResuData();
        }
        window.initialPage = 'perf';
      } else {
        this.compareBasicInfo = compareJsonData.basicInfo;
        this.perfData = jsonData.perf;
        this.comparePerfData = compareJsonData.perf;
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
