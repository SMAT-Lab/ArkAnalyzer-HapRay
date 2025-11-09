/**
 * Web Worker Manager
 * 管理 Web Worker 的创建、消息传递和生命周期
 */

import type { NativeMemoryRecord } from '@/stores/nativeMemory';

// Worker 请求类型
export type WorkerRequestType =
  | 'aggregateByProcess'
  | 'aggregateByThread'
  | 'aggregateByFile'
  | 'aggregateBySymbol'
  | 'processTimelineData';

// Worker 请求接口
interface WorkerRequest {
  type: WorkerRequestType;
  payload: Record<string, unknown>;
  requestId: string;
}

// Worker 响应接口
interface WorkerResponse {
  requestId: string;
  success: boolean;
  result?: unknown;
  error?: string;
}

// 时间线数据处理结果
export interface TimelineProcessedData {
  chartData: Array<{
    index: number;
    relativeTs: number;
    cumulativeMemory: number;
  }>;
  seriesData: Array<{
    name: string;
    data: Array<{
      index: number;
      relativeTs: number;
      cumulativeMemory: number;
      heapSize: number;
      eventType: string;
    }>;
  }>;
  maxMemory: number;
  minMemory: number;
  finalMemory: number;
  threshold30: number;
  threshold60: number;
}

/**
 * Memory Calculation Worker Manager
 * 单例模式，管理内存计算 Worker
 */
class MemoryWorkerManager {
  private worker: Worker | null = null;
  private requestIdCounter = 0;
  private pendingRequests = new Map<string, {
    resolve: (value: unknown) => void;
    reject: (reason: Error) => void;
  }>();

  /**
   * 初始化 Worker
   */
  private initWorker() {
    if (this.worker) {
      return;
    }

    // 创建 Worker
    this.worker = new Worker(
      new URL('../workers/memoryCalculation.worker.ts', import.meta.url),
      { type: 'module' }
    );

    // 监听 Worker 消息
    this.worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
      const { requestId, success, result, error } = e.data;

      const pending = this.pendingRequests.get(requestId);
      if (!pending) {
        console.warn(`[WorkerManager] Received response for unknown request: ${requestId}`);
        return;
      }

      this.pendingRequests.delete(requestId);

      if (success) {
        pending.resolve(result);
      } else {
        pending.reject(new Error(error || 'Worker task failed'));
      }
    };

    // 监听 Worker 错误
    this.worker.onerror = (error) => {
      console.error('[WorkerManager] Worker error:', error);
      // 拒绝所有待处理的请求
      this.pendingRequests.forEach(({ reject }) => {
        reject(new Error('Worker encountered an error'));
      });
      this.pendingRequests.clear();
    };

    console.log('[WorkerManager] Memory calculation worker initialized');
  }

  /**
   * 发送请求到 Worker
   */
  private sendRequest<T>(type: WorkerRequestType, payload: Record<string, unknown>): Promise<T> {
    this.initWorker();

    const requestId = `req_${++this.requestIdCounter}_${Date.now()}`;

    return new Promise<T>((resolve, reject) => {
      this.pendingRequests.set(requestId, {
        resolve: resolve as (value: unknown) => void,
        reject,
      });

      const request: WorkerRequest = {
        type,
        payload,
        requestId,
      };

      this.worker!.postMessage(request);
    });
  }

  /**
   * 处理时间线数据
   */
  async processTimelineData(
    records: NativeMemoryRecord[],
    drillDownLevel: 'overview' | 'category' | 'subCategory',
    selectedCategory: string,
    selectedSubCategory: string
  ): Promise<TimelineProcessedData> {
    const startTime = performance.now();
    console.log(`[WorkerManager] Processing timeline data: ${records.length} records, level: ${drillDownLevel}`);

    const result = await this.sendRequest<TimelineProcessedData>('processTimelineData', {
      records,
      drillDownLevel,
      selectedCategory,
      selectedSubCategory,
    });

    const duration = ((performance.now() - startTime) / 1000).toFixed(2);
    console.log(`[WorkerManager] Timeline data processed in ${duration}s`);

    return result;
  }

  /**
   * 按进程聚合
   */
  async aggregateByProcess(
    records: NativeMemoryRecord[],
    timePoint: number | null
  ): Promise<Array<Record<string, unknown>>> {
    return this.sendRequest('aggregateByProcess', { records, timePoint });
  }

  /**
   * 按线程聚合
   */
  async aggregateByThread(
    records: NativeMemoryRecord[],
    timePoint: number | null
  ): Promise<Array<Record<string, unknown>>> {
    return this.sendRequest('aggregateByThread', { records, timePoint });
  }

  /**
   * 按文件聚合
   */
  async aggregateByFile(
    records: NativeMemoryRecord[],
    timePoint: number | null
  ): Promise<Array<Record<string, unknown>>> {
    return this.sendRequest('aggregateByFile', { records, timePoint });
  }

  /**
   * 按符号聚合
   */
  async aggregateBySymbol(
    records: NativeMemoryRecord[],
    timePoint: number | null
  ): Promise<Array<Record<string, unknown>>> {
    return this.sendRequest('aggregateBySymbol', { records, timePoint });
  }

  /**
   * 终止 Worker
   */
  terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
      this.pendingRequests.clear();
      console.log('[WorkerManager] Memory calculation worker terminated');
    }
  }
}

// 导出单例实例
export const memoryWorkerManager = new MemoryWorkerManager();

