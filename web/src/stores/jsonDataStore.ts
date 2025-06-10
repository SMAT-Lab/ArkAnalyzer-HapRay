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

export const useJsonDataStore = defineStore('config', {
  state: () => ({
    jsonData: null as JSONData | null,
    htraceJsonData: null as HtraceJSONData[] | null,
    compareJsonData: null as JSONData | null
  }),
  actions: {
    setJsonData(jsonData: JSONData[], htraceJsonData: HtraceJSONData[], compareJsonData: JSONData[]) {
      if (JSON.stringify(compareJsonData) == "\"\/tempCompareJsonData\/\"") {
        this.jsonData = jsonData[0];
        this.htraceJsonData = htraceJsonData;
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
