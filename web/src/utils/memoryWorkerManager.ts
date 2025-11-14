/**
 * Memory Worker Manager
 * 管理 Web Worker 的创建、任务分发和结果缓存
 */

import type { NativeMemoryRecord } from '@/stores/nativeMemory';
// Vite 会处理 ?worker&inline 导入
import MemoryWorker from '@/workers/memoryCalculation.worker.ts?worker&inline';

interface WorkerTask {
  type: string;
  payload: Record<string, unknown>;
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
}

interface CacheKey {
  type: string;
  stepId: number;
  timePoint: number | null;
  extraKey?: string;
}

/**
 * 内存计算 Worker 管理器
 * 
 * 功能：
 * 1. 管理多个 Worker 实例，实现并行计算
 * 2. 缓存计算结果，避免重复计算
 * 3. 自动任务队列管理
 */
export class MemoryWorkerManager {
  private workers: Worker[] = [];
  private workerCount: number;
  private taskQueue: WorkerTask[] = [];
  private pendingTasks = new Map<number, WorkerTask>();
  private requestIdCounter = 0;
  private cache = new Map<string, unknown>();
  private workerBusy: boolean[] = [];

  constructor(workerCount: number = navigator.hardwareConcurrency || 4) {
    // 限制 Worker 数量，避免创建过多
    this.workerCount = Math.min(workerCount, 8);
    this.initWorkers();
  }

  /**
   * 初始化 Worker 池
   */
  private initWorkers() {
    for (let i = 0; i < this.workerCount; i++) {
      const worker = new MemoryWorker();
      worker.onmessage = (e: MessageEvent) => this.handleWorkerMessage(i, e);
      worker.onerror = (e: ErrorEvent) => this.handleWorkerError(i, e);
      this.workers.push(worker);
      this.workerBusy[i] = false;
    }
  }

  /**
   * 处理 Worker 返回的消息
   */
  private handleWorkerMessage(workerIndex: number, e: MessageEvent) {
    const { requestId, success, result, error } = e.data;
    const task = this.pendingTasks.get(requestId);

    if (task) {
      this.pendingTasks.delete(requestId);
      this.workerBusy[workerIndex] = false;

      if (success) {
        task.resolve(result);
      } else {
        task.reject(new Error(error || 'Worker task failed'));
      }

      // 处理队列中的下一个任务
      this.processNextTask();
    }
  }

  /**
   * 处理 Worker 错误
   */
  private handleWorkerError(workerIndex: number, e: ErrorEvent) {
    console.error(`Worker ${workerIndex} error:`, e);
    this.workerBusy[workerIndex] = false;
    
    // 尝试处理队列中的下一个任务
    this.processNextTask();
  }

  /**
   * 处理队列中的下一个任务
   */
  private processNextTask() {
    if (this.taskQueue.length === 0) return;

    // 找到空闲的 Worker
    const workerIndex = this.workerBusy.findIndex(busy => !busy);
    if (workerIndex === -1) return; // 所有 Worker 都在忙

    const task = this.taskQueue.shift();
    if (task) {
      this.executeTask(workerIndex, task);
    }
  }

  /**
   * 序列化数据，确保可以被 Worker 克隆
   */
  private serializePayload(payload: Record<string, unknown>): Record<string, unknown> {
    try {
      // 使用 JSON 序列化/反序列化来清理数据
      // 这会移除不可序列化的属性（如函数、循环引用等）
      return JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
    } catch (error) {
      console.error('Failed to serialize payload:', error);
      throw new Error('Payload contains non-serializable data');
    }
  }

  /**
   * 执行任务
   */
  private executeTask(workerIndex: number, task: WorkerTask) {
    const requestId = this.requestIdCounter++;
    this.pendingTasks.set(requestId, task);
    this.workerBusy[workerIndex] = true;

    try {
      // 序列化 payload 以确保可以被 Worker 克隆
      const serializedPayload = this.serializePayload(task.payload);

      this.workers[workerIndex].postMessage({
        type: task.type,
        payload: serializedPayload,
        requestId,
      });
    } catch (error) {
      // 如果序列化失败，立即拒绝任务
      this.workerBusy[workerIndex] = false;
      this.pendingTasks.delete(requestId);
      task.reject(error as Error);
      this.processNextTask();
    }
  }

  /**
   * 生成缓存键
   */
  private getCacheKey(cacheKey: CacheKey): string {
    const { type, stepId, timePoint, extraKey } = cacheKey;
    return `${type}_${stepId}_${timePoint ?? 'null'}_${extraKey ?? ''}`;
  }

  /**
   * 优化 payload，只传输必要的字段
   */
  private optimizePayload(type: string, payload: Record<string, unknown>): Record<string, unknown> {
    // 如果没有 records，直接返回
    if (!payload.records || !Array.isArray(payload.records)) {
      return payload;
    }

    const recordCount = payload.records.length;
    console.log(`优化前记录数: ${recordCount}`);

    // 根据聚合类型，只提取必要的字段
    const necessaryFields = this.getNecessaryFields(type);

    // 如果没有指定必要字段，说明不需要优化
    if (necessaryFields.length === 0) {
      return payload;
    }

    // 优化记录数组，只保留必要字段
    const optimizedRecords = payload.records.map((record: Record<string, unknown>) => {
      const optimized: Record<string, unknown> = {};
      for (const field of necessaryFields) {
        if (field in record) {
          optimized[field] = record[field];
        }
      }
      return optimized;
    });

    console.log(`优化后字段数: ${necessaryFields.length}`);

    return {
      ...payload,
      records: optimizedRecords,
    };
  }

  /**
   * 获取不同聚合类型需要的字段
   */
  private getNecessaryFields(type: string): string[] {
    // 所有聚合都需要的基础字段
    const baseFields = ['relativeTs', 'eventType', 'heapSize'];

    switch (type) {
      case 'aggregateByThread':
        return [...baseFields, 'process', 'thread', 'tid'];
      case 'aggregateByFile':
        return [...baseFields, 'file', 'category'];
      case 'aggregateBySymbol':
        return [...baseFields, 'symbol', 'category'];
      case 'aggregateByProcess':
        return [...baseFields, 'process', 'pid'];
      default:
        // 未知类型，返回空数组表示不优化
        return [];
    }
  }

  /**
   * 提交任务到 Worker
   */
  private submitTask<T>(type: string, payload: Record<string, unknown>, cacheKey?: CacheKey): Promise<T> {
    // 检查缓存
    if (cacheKey) {
      const key = this.getCacheKey(cacheKey);
      if (this.cache.has(key)) {
        console.log(`缓存命中: ${key}`);
        return Promise.resolve(this.cache.get(key) as T);
      }
    }

    // 优化 payload，减少数据传输量
    const optimizedPayload = this.optimizePayload(type, payload);

    return new Promise<T>((resolve, reject) => {
      const task: WorkerTask = {
        type,
        payload: optimizedPayload,
        resolve: (result) => {
          // 缓存结果
          if (cacheKey) {
            const key = this.getCacheKey(cacheKey);
            this.cache.set(key, result);
          }
          resolve(result as T);
        },
        reject,
      };

      // 尝试立即执行或加入队列
      const workerIndex = this.workerBusy.findIndex(busy => !busy);
      if (workerIndex !== -1) {
        this.executeTask(workerIndex, task);
      } else {
        this.taskQueue.push(task);
      }
    });
  }

  /**
   * 按进程聚合
   */
  async aggregateByProcess(
    records: NativeMemoryRecord[],
    stepId: number,
    timePoint: number | null
  ): Promise<Record<string, unknown>[]> {
    return this.submitTask('aggregateByProcess', { records, timePoint }, {
      type: 'process',
      stepId,
      timePoint,
    });
  }

  /**
   * 按线程聚合
   */
  async aggregateByThread(
    records: NativeMemoryRecord[],
    stepId: number,
    timePoint: number | null
  ): Promise<Record<string, unknown>[]> {
    return this.submitTask('aggregateByThread', { records, timePoint }, {
      type: 'thread',
      stepId,
      timePoint,
    });
  }

  /**
   * 按文件聚合
   */
  async aggregateByFile(
    records: NativeMemoryRecord[],
    stepId: number,
    timePoint: number | null
  ): Promise<Record<string, unknown>[]> {
    return this.submitTask('aggregateByFile', { records, timePoint }, {
      type: 'file',
      stepId,
      timePoint,
    });
  }

  /**
   * 按符号聚合
   */
  async aggregateBySymbol(
    records: NativeMemoryRecord[],
    stepId: number,
    timePoint: number | null
  ): Promise<Record<string, unknown>[]> {
    return this.submitTask('aggregateBySymbol', { records, timePoint }, {
      type: 'symbol',
      stepId,
      timePoint,
    });
  }

  /**
   * 批量执行多个聚合任务（并行）
   */
  async aggregateAll(
    records: NativeMemoryRecord[],
    stepId: number,
    timePoint: number | null
  ): Promise<{
    byProcess: Record<string, unknown>[];
    byThread: Record<string, unknown>[];
    byFile: Record<string, unknown>[];
    bySymbol: Record<string, unknown>[];
  }> {
    const [byProcess, byThread, byFile, bySymbol] = await Promise.all([
      this.aggregateByProcess(records, stepId, timePoint),
      this.aggregateByThread(records, stepId, timePoint),
      this.aggregateByFile(records, stepId, timePoint),
      this.aggregateBySymbol(records, stepId, timePoint),
    ]);

    return { byProcess, byThread, byFile, bySymbol };
  }

  /**
   * 清除缓存
   */
  clearCache(stepId?: number, timePoint?: number | null) {
    if (stepId === undefined) {
      // 清除所有缓存
      this.cache.clear();
    } else {
      // 清除特定 stepId 或 timePoint 的缓存
      const keysToDelete: string[] = [];
      this.cache.forEach((_, key) => {
        const parts = key.split('_');
        const keyStepId = parseInt(parts[1]);
        const keyTimePoint = parts[2] === 'null' ? null : parseInt(parts[2]);
        
        if (keyStepId === stepId && (timePoint === undefined || keyTimePoint === timePoint)) {
          keysToDelete.push(key);
        }
      });
      keysToDelete.forEach(key => this.cache.delete(key));
    }
  }

  /**
   * 销毁所有 Worker
   */
  destroy() {
    this.workers.forEach(worker => worker.terminate());
    this.workers = [];
    this.taskQueue = [];
    this.pendingTasks.clear();
    this.cache.clear();
    this.workerBusy = [];
  }
}

// 创建单例实例
let workerManagerInstance: MemoryWorkerManager | null = null;

/**
 * 获取 Worker 管理器单例
 */
export function getMemoryWorkerManager(): MemoryWorkerManager {
  if (!workerManagerInstance) {
    workerManagerInstance = new MemoryWorkerManager();
  }
  return workerManagerInstance;
}

/**
 * 销毁 Worker 管理器单例
 */
export function destroyMemoryWorkerManager() {
  if (workerManagerInstance) {
    workerManagerInstance.destroy();
    workerManagerInstance = null;
  }
}

