import { defineStore } from 'pinia';

export interface JSONData {
  app_id: string;
  app_name: string;
  app_version: string;
  scene: string;
  timestamp: number;
  perfPath: string[];
  categories: string[];
  steps: {
      step_name: string;
      step_id: number;
      count: number;
      data: {
          category: number;
          count: number;
          subData: {
              name: string;
              count: number;
              files: {
                  file: string;
                  count: number;
              }[];
          }[];
      }[];
  }[];
}

export const useJsonDataStore = defineStore('config', {
  state: () => ({
      jsonData: null as JSONData | null
  }),
  actions: {
      setJsonData(data: JSONData) {
          this.jsonData = data;
      }
  }
});

// 定义一个存储
// export const useJsonDataStore = defineStore('jsonData', {
//   state: () => ({
//     // 定义 JSON 数据
//     jsonData: json
//   }),
//   getters: {
//     // 定义获取 JSON 数据的 getter
//     getJsonData: (state) => state.jsonData
//   }
// });