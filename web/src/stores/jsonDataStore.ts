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
    compareJsonData: null as JSONData | null
  }),
  actions: {
    setJsonData(jsonData: JSONData, compareJsonData: JSONData) {
      if (JSON.stringify(compareJsonData) == "\"\/tempCompareJsonData\/\"") {
        this.jsonData = jsonData;
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
