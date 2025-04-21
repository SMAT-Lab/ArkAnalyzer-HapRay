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
    jsonData: null as JSONData | null,
    compareJsonData: null as JSONData | null
  }),
  actions: {
    setJsonData(jsonData: JSONData,compareJsonData: JSONData) {
      if( JSON.stringify(compareJsonData) == "\"\/tempCompareJsonData\/\""){
        this.jsonData = jsonData;
        window.initialPage = 'perf';
      }else{
        this.jsonData = jsonData;
        this.compareJsonData = compareJsonData;
        window.initialPage = 'perf_compare';
      }
      
    },
  },
});
