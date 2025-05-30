import { defineStore } from 'pinia';

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
      category: number;
      count: number;
      processes: {
        process: string;
        count: number;
        threads: {
          thread: string;
          count: number;
          files: {
            file: string;
            count: number;
            symbols: {
              symbol: string;
              count: number;
            }[];
          }[];
        }[];
      }[];
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
    ui_stutter:{
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
    setJsonData(jsonData: JSONData, htraceJsonData: HtraceJSONData[], compareJsonData: JSONData) {
      if (JSON.stringify(compareJsonData) == "\"\/tempCompareJsonData\/\"") {
        this.jsonData = jsonData;
        this.htraceJsonData = htraceJsonData;
        window.initialPage = 'perf';
      } else {
        this.jsonData = jsonData;
        this.compareJsonData = compareJsonData;
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
