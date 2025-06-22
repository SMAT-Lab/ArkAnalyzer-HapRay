import { defineStore } from 'pinia';


export interface JSONData {
  type: number, // 0 json string, 1 base64 gzip json string, 2 base64 gzip sqlite db。对于web层只能是1
  versionCode: number, // 保留版本号，用于跨版本数据兼容支持
  basicInfo: BasicInfo, // 基本信息, ROM版本，系统版本，步骤等基本信息
  perf: PerfData, // 必选字段，负载分析
  trace?: TraceData, // 可选字段，trace帧分析， trace 无数据时，不用显示帧分析
}

interface BasicInfo {
  rom_version: string;
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
}

// trace 分析数据
interface TraceData {
  frames: FrameData[], // 帧数据，包含卡顿帧
  emptyFrame?: EmptyFrameData, // 空刷帧
  componentReuse: boolean // 组件复用
}

enum PerfEvent {
  CYCLES_EVENT = 0,
  INSTRUCTION_EVENT = 1,
}

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

enum OriginKind {
  UNKNOWN = 0,
  FIRST_PARTY = 1,
  OPEN_SOURCE = 2,
  THIRD_PARTY = 3,
}

export interface PerfData {
  steps: {
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
  }[];
}

interface FrameTypeStats {
  total: number;
  stutter: number;
  stutter_rate: number;
}

interface FrameData {
  runtime: string;
  statistics: {
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
  };
  stutter_details: {
    ui_stutter: {
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
    }[];
    render_stutter: {
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
    }[];
  };
  fps_stats: {
    average_fps: number;
    min_fps: number;
    max_fps: number;
    fps_windows: {
      start_time: number;
      end_time: number;
      start_time_ts: number;
      end_time_ts: number;
      frame_count: number;
      fps: number;
    }[];
    low_fps_window_count: number;
  };
}

interface EmptyFrameData {
  [stepName: string]: {
    status: string;
    summary: {
      total_load: number;
      empty_frame_load: number;
      empty_frame_percentage: number;
      background_thread_load: number;
      background_thread_percentage: number;
      total_empty_frames: number;
      empty_frames_with_load: number;
    };
    top_frames: {
      main_thread_empty_frames: EmptyFrame[];
      background_thread: EmptyFrame[];
    };
  };
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

interface SampleCallchain {
  timestamp: number;
  event_count: number;
  load_percentage: number;
  callchain: CallstackFrame[];
}

interface CallstackFrame {
  depth: number;
  file_id: number;
  path: string;
  symbol_id: number;
  symbol: string;
}

export const defaultFrameDataJson = [
  {
    "runtime": "",
    "statistics": {
      "total_frames": 0,
      "frame_stats": {
        "ui": {
          "total": 0,
          "stutter": 0,
          "stutter_rate": 0
        },
        "render": {
          "total": 0,
          "stutter": 0,
          "stutter_rate": 0
        },
        "sceneboard": {
          "total": 0,
          "stutter": 0,
          "stutter_rate": 0
        }
      },
      "total_stutter_frames": 0,
      "stutter_rate": 0,
      "stutter_levels": {
        "level_1": 0,
        "level_2": 0,
        "level_3": 0
      }
    },
    "stutter_details": {
      "ui_stutter": [
        {
          "vsync": 0,
          "timestamp": 0,
          "actual_duration": 0,
          "expected_duration": 0,
          "exceed_time": 0,
          "exceed_frames": 0,
          "stutter_level": 0,
          "level_description": "",
          "src": "",
          "dst": 0
        }
      ],
      "render_stutter": [
        {
          "vsync": 0,
          "timestamp": 0,
          "actual_duration": 0,
          "expected_duration": 0,
          "exceed_time": 0,
          "exceed_frames": 0,
          "stutter_level": 0,
          "level_description": "",
          "src": "",
          "dst": 0
        }
      ]
    },
    "fps_stats": {
      "average_fps": 0,
      "min_fps": 0,
      "max_fps": 0,
      "fps_windows": [
        {
          "start_time": 0,
          "end_time": 0,
          "start_time_ts": 0,
          "end_time_ts": 0,
          "frame_count": 0,
          "fps": 0
        }
      ],
      "low_fps_window_count": 0
    }
  }
];
export const defaultEmptyJson = {
  "step1": {
    "status": "unknow",
    "summary": {
      "total_load": 0,
      "empty_frame_load": 0,
      "empty_frame_percentage": 0,
      "background_thread_load": 0,
      "background_thread_percentage": 0,
      "total_empty_frames": 0,
      "empty_frames_with_load": 0
    },
    "top_frames": {
      "main_thread_empty_frames": [
        {
          "ts": 0,
          "dur": 0,
          "ipid": 0,
          "itid": 0,
          "pid": 0,
          "tid": 0,
          "callstack_id": 0,
          "process_name": "",
          "thread_name": "",
          "callstack_name": "",
          "frame_load": 0,
          "is_main_thread": 0,
          "sample_callchains": [
            {
              "timestamp": 0,
              "event_count": 0,
              "load_percentage": 0,
              "callchain": [
                {
                  "depth": 0,
                  "file_id": 0,
                  "path": "",
                  "symbol_id": 0,
                  "symbol": ""
                }
              ]
            }
          ]
        },
      ],
      "background_thread": [
        {
          "ts": 0,
          "dur": 0,
          "ipid": 0,
          "itid": 0,
          "pid": 0,
          "tid": 0,
          "callstack_id": 0,
          "process_name": "",
          "thread_name": "",
          "callstack_name": "",
          "frame_load": 0,
          "is_main_thread": 0,
          "sample_callchains": [
            {
              "timestamp": 0,
              "event_count": 0,
              "load_percentage": 0,
              "callchain": [
                {
                  "depth": 0,
                  "file_id": 0,
                  "path": "",
                  "symbol_id": 0,
                  "symbol": ""
                }
              ]
            }
          ]
        },]
    }
  }

};

export const useJsonDataStore = defineStore('config', {
  state: () => ({
    basicInfo: null as BasicInfo | null,
    compareBasicInfo: null as BasicInfo | null,
    perfData: null as PerfData | null,
    frameData: null as FrameData[] | null,
    emptyFrameData: null as EmptyFrameData | null,
    comparePerfData: null as PerfData | null

  }),
  actions: {
    setJsonData(jsonData: JSONData, compareJsonData: JSONData) {
      this.basicInfo = jsonData.basicInfo;
      if (JSON.stringify(compareJsonData) == "\"\/tempCompareJsonData\/\"") {
        this.perfData = jsonData.perf;
        if (jsonData.trace) {
          if (jsonData.trace.frames) {
            this.frameData = jsonData.trace.frames;
          } else {
            this.frameData = defaultFrameDataJson;
          }

          if (jsonData.trace.emptyFrame) {
            this.emptyFrameData = jsonData.trace.emptyFrame;
          } else {
            this.emptyFrameData = defaultEmptyJson;
          }
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
