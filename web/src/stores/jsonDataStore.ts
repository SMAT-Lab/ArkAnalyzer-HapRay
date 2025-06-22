import { defineStore } from 'pinia';

export enum PerfEvent {
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

export enum OriginKind {
  UNKNOWN = 0,
  FIRST_PARTY = 1,
  OPEN_SOURCE = 2,
  THIRD_PARTY = 3,
}

export interface JSONData {
  rom_version: string;
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
  perfDataPath: string[],
  perfDbPath: string[],
  htracePath: string[],
  categories: string[];
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
export interface HtraceJSONData {
  runtime: string;
  statistics: {
    total_frames: number;
    ui_stutter_frames: number;
    render_stutter_frames: number;
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

export interface MergeJSONData {
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
  perfDataPath: string[],
  perfDbPath: string[],
  htracePath: string[],
  categories: string[];
  steps: {
    step_name: string;
    step_id: number;
    count: number;
    compareCount: number;
    round: number;
    perf_data_path: string;
    data: {
      category: number;
      count: number;
      compareCount: number;
      processes: {
        process: string;
        count: number;
        compareCount: number;
        threads: {
          thread: string;
          count: number;
          compareCount: number;
          files: {
            file: string;
            count: number;
            compareCount: number;
            symbols: {
              symbol: string;
              count: number;
              compareCount: number;
            }[];
          }[];
        }[];
      }[];
    }[];
  }[];
}

export interface EmptyFrameJsonData {
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
    jsonData: null as JSONData | null,
    htraceJsonData: null as HtraceJSONData[] | null,
    emptyFrameJsonData: null as EmptyFrameJsonData | null,
    compareJsonData: null as JSONData | null

  }),
  actions: {
    setJsonData(jsonData: JSONData[], htraceJsonData: HtraceJSONData[], emptyFrameJsonData: EmptyFrameJsonData, compareJsonData: JSONData[]) {
      if (JSON.stringify(compareJsonData) == "\"\/tempCompareJsonData\/\"") {
        this.jsonData = jsonData[0];
        this.htraceJsonData = htraceJsonData;
        if (JSON.stringify(emptyFrameJsonData) == "\"EMPTY_FRAME_PLACEHOLDER\"") {
          this.emptyFrameJsonData = defaultEmptyJson;
        } else {
          this.emptyFrameJsonData = emptyFrameJsonData;
        }
        window.initialPage = 'perf';
      } else {
        this.jsonData = jsonData[0];
        this.compareJsonData = compareJsonData[0];
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
