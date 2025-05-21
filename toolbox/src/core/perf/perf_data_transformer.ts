import { PerfSymbolDetailData } from "./perf_analyzer_base";


export interface StepJsonData {
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
}

/**
 * 高性能性能数据转换器
 */
export class PerfDataTransformer {
  private perfData: PerfSymbolDetailData[];
  private stepName: string;
  private stepId: number;
  private round: number;
  private perfDataPath: string;

  constructor(
    perfData: PerfSymbolDetailData[],
    stepName: string,
    stepId: number,
    round: number,
    perfDataPath: string
  ) {
    this.perfData = perfData;
    this.stepName = stepName;
    this.stepId = stepId;
    this.round = round;
    this.perfDataPath = perfDataPath;
  }

  /**
   * 执行数据转换
   */
  transform(): StepJsonData {
    // 构建数据树
    const dataTree = this.buildDataTree();

    // 构建最终的JSON数据
    const jsonData: StepJsonData = {
      step_name: this.stepName,
      step_id: this.stepId,
      count: dataTree.totalEvents,
      round: this.round,
      perf_data_path: this.perfDataPath,
      data: this.buildCategoryItems(dataTree)
    };

    return jsonData;
  }

  /**
   * 构建数据树
   */
  private buildDataTree() {
    const rootData = {
      totalEvents: 0,
      categoryMap: new Map<number, CategoryData>()
    };

    // 单次遍历所有数据，构建完整的树
    for (const item of this.perfData) {
      // 获取或创建类别数据
      let categoryData = rootData.categoryMap.get(item.componentCategory);
      if (!categoryData) {
        categoryData = {
          totalEvents: 0,
          processMap: new Map<string, ProcessData>()
        };
        rootData.categoryMap.set(item.componentCategory, categoryData);
      }

      // 获取或创建进程数据
      let processData = categoryData.processMap.get(item.processName);
      if (!processData) {
        processData = {
          totalEvents: 0,
          threadMap: new Map<string, ThreadData>()
        };
        categoryData.processMap.set(item.processName, processData);
      }

      // 获取或创建线程数据
      let threadData = processData.threadMap.get(item.threadName);
      if (!threadData) {
        threadData = {
          totalEvents: 0,
          fileMap: new Map<string, FileData>()
        };
        processData.threadMap.set(item.threadName, threadData);
      }

      // 获取或创建文件数据
      let fileData = threadData.fileMap.get(item.file);
      if (!fileData) {
        fileData = {
          totalEvents: 0,
          symbolMap: new Map<string, number>()
        };
        threadData.fileMap.set(item.file, fileData);
      }

      // 更新符号事件计数
      const symbolEvents = item.symbolEvents;
      fileData.symbolMap.set(item.symbol, (fileData.symbolMap.get(item.symbol) || 0) + symbolEvents);

      // 逐级更新事件计数
      fileData.totalEvents += symbolEvents;
      threadData.totalEvents += symbolEvents;
      processData.totalEvents += symbolEvents;
      categoryData.totalEvents += symbolEvents;
      rootData.totalEvents += symbolEvents;
    }

    return rootData;
  }

  /**
   * 构建类别项
   */
  private buildCategoryItems(rootData: RootData) {
    return Array.from(rootData.categoryMap.entries()).map(([category, categoryData]) => {
      const processes = Array.from(categoryData.processMap.entries()).map(([processName, processData]) => {
        const threads = Array.from(processData.threadMap.entries()).map(([threadName, threadData]) => {
          const files = Array.from(threadData.fileMap.entries()).map(([fileName, fileData]) => {
            const symbols = Array.from(fileData.symbolMap.entries()).map(([symbol, count]) => ({
              symbol,
              count
            }));
            
            return {
              file: fileName,
              count: fileData.totalEvents,
              symbols
            };
          });
          
          return {
            thread: threadName,
            count: threadData.totalEvents,
            files
          };
        });
        
        return {
          process: processName,
          count: processData.totalEvents,
          threads
        };
      });
      
      return {
        category,
        count: categoryData.totalEvents,
        processes
      };
    });
  }
}

// 辅助数据结构
interface RootData {
  totalEvents: number;
  categoryMap: Map<number, CategoryData>;
}

interface CategoryData {
  totalEvents: number;
  processMap: Map<string, ProcessData>;
}

interface ProcessData {
  totalEvents: number;
  threadMap: Map<string, ThreadData>;
}

interface ThreadData {
  totalEvents: number;
  fileMap: Map<string, FileData>;
}

interface FileData {
  totalEvents: number;
  symbolMap: Map<string, number>;
}