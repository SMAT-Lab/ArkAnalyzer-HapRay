/**
 * SQLite Worker API - 主线程 API 封装
 * 提供便捷的 API 来与 dbWorker 通信
 */

// Worker 消息类型定义
interface WorkerRequest {
  id: string;
  type: 'init' | 'exec' | 'query' | 'close';
  payload?: any;
}

interface WorkerResponse {
  id: string;
  type: 'success' | 'error';
  payload?: any;
  error?: string;
}

export class DbApi {
  private worker: Worker | null = null;
  private pendingRequests: Map<string, { resolve: (value: any) => void; reject: (reason: any) => void }> = new Map();
  private requestIdCounter = 0;

  /**
   * 初始化 Worker
   * @param dbDataBase64 - base64 编码的 gzip 压缩的数据库文件（可选，从 window.dbData 读取）
   * @param wasmBase64 - WASM 文件的 base64 编码（可选，从 window.__sqlWasmBase64 读取）
   */
  async init(dbDataBase64?: string, wasmBase64?: string): Promise<void> {
    // 从内联的代码创建 Worker
    if (typeof window !== 'undefined' && (window as any).__dbWorkerCode) {
      const workerCode = (window as any).__dbWorkerCode;
      const blob = new Blob([workerCode], { type: 'application/javascript' });
      const workerUrl = URL.createObjectURL(blob);
      this.worker = new Worker(workerUrl);
    } else {
      // 开发环境或回退方案：使用外部文件
      this.worker = new Worker(new URL('../dbWorker.ts', import.meta.url), { type: 'module' });
    }

    // 设置消息处理器
    this.worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
      const { id, type, payload, error } = e.data;
      const request = this.pendingRequests.get(id);
      
      if (request) {
        this.pendingRequests.delete(id);
        if (type === 'success') {
          request.resolve(payload);
        } else {
          request.reject(new Error(error || 'Unknown error'));
        }
      }
    };

    this.worker.onerror = (error) => {
      console.error('Worker error:', error);
      // 清理所有 pending 请求
      for (const [id, request] of this.pendingRequests.entries()) {
        this.pendingRequests.delete(id);
        request.reject(error);
      }
    };

    // 如果没有提供 dbDataBase64，尝试从 window.dbData 读取
    if (!dbDataBase64 && typeof window !== 'undefined' && (window as any).dbData) {
      dbDataBase64 = (window as any).dbData;
    }

    // 如果没有提供 wasmBase64，尝试从 window.__sqlWasmBase64 读取
    if (!wasmBase64 && typeof window !== 'undefined' && (window as any).__sqlWasmBase64) {
      wasmBase64 = (window as any).__sqlWasmBase64;
    }

    // 初始化数据库
    await this.sendRequest('init', { dbData: dbDataBase64, wasmBase64 });
  }

  /**
   * 执行 SQL 语句（不返回结果）
   * @param sql - SQL 语句
   * @param params - 参数数组（可选）
   */
  async exec(sql: string, params?: any[]): Promise<void> {
    await this.sendRequest('exec', { sql, params });
  }

  /**
   * 查询 SQL 语句（返回结果）
   * @param sql - SQL 查询语句
   * @param params - 参数数组（可选）
   * @returns 查询结果数组
   */
  async query(sql: string, params?: any[]): Promise<any[]> {
    const response = await this.sendRequest('query', { sql, params });
    return response.result || [];
  }

  /**
   * 关闭数据库和 Worker
   */
  async close(): Promise<void> {
    if (this.worker) {
      await this.sendRequest('close');
      this.worker.terminate();
      this.worker = null;
    }
  }

  /**
   * 发送请求到 Worker
   */
  private sendRequest(type: WorkerRequest['type'], payload?: any): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.worker) {
        reject(new Error('Worker not initialized'));
        return;
      }

      const id = `req_${this.requestIdCounter++}`;
      this.pendingRequests.set(id, { resolve, reject });

      const request: WorkerRequest = { id, type, payload };
      this.worker.postMessage(request);

      // 设置超时
      setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error('Request timeout'));
        }
      }, 30000); // 30 秒超时
    });
  }
}

// 导出单例实例
let dbApiInstance: DbApi | null = null;

/**
 * 获取 DbApi 实例（单例模式）
 */
export function getDbApi(): DbApi {
  if (!dbApiInstance) {
    dbApiInstance = new DbApi();
  }
  return dbApiInstance;
}

/**
 * 初始化数据库（便捷函数）
 * @param dbDataBase64 - base64 编码的 gzip 压缩的数据库文件（可选）
 * @param wasmBase64 - WASM 文件的 base64 编码（可选）
 */
export async function initDb(dbDataBase64?: string, wasmBase64?: string): Promise<DbApi> {
  const api = getDbApi();
  await api.init(dbDataBase64, wasmBase64);
  return api;
}

