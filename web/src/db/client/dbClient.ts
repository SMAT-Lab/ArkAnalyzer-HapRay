/**
 * 数据库客户端 - 主线程通信层
 * 负责与 Worker 进行消息通信，提供数据库操作接口
 * 
 * 职责：封装 Worker 通信，提供 exec、query 等基础方法
 */

import type { WorkerRequest, WorkerResponse, WorkerMessageType } from '../serviceWorker/dbServiceWorker';

/**
 * 数据库客户端类
 * 负责与 dbServiceWorker 进行消息通信
 */
export class DbClient {
  private worker: Worker | null = null;
  private pendingRequests: Map<string, { resolve: (value: any) => void; reject: (reason: any) => void }> = new Map();
  private requestIdCounter = 0;

  /**
   * 初始化 Worker
   * @param dbDataBase64 - base64 编码的 gzip 压缩的数据库文件（可选，从 window.dbData 读取）
   * @param wasmBase64 - WASM 文件的 base64 编码（可选，从 window.__sqlWasmBase64 读取）
   */
  async init(dbDataBase64?: string, wasmBase64?: string): Promise<void> {
    console.log('[DbClient] init 开始');
    console.log('[DbClient] window.__dbWorkerCode 存在:', typeof window !== 'undefined' && !!(window as any).__dbWorkerCode);
    console.log('[DbClient] window.__dbWorkerCode 类型:', typeof (window as any).__dbWorkerCode);
    console.log('[DbClient] window.__dbWorkerCode 长度:', (window as any).__dbWorkerCode?.length || 0);
    console.log('[DbClient] window.__dbWorkerCode 前200字符:', (window as any).__dbWorkerCode?.substring(0, 200));
    
    // 从内联的代码创建 Worker
    if (typeof window !== 'undefined' && (window as any).__dbWorkerCode) {
      const workerCode = (window as any).__dbWorkerCode;
      console.log('[DbClient] 使用内联 Worker 代码，代码长度:', workerCode.length);
            
      try {
        // 检查 Worker 代码是否是 ES 模块（包含 import/export）
        const isESModule = workerCode.includes('import ') || workerCode.includes('export ') || workerCode.includes('import{') || workerCode.includes('export{');
        console.log('[DbClient] Worker 代码是 ES 模块:', isESModule);
        
        const blob = new Blob([workerCode], { type: 'application/javascript' });
        const workerUrl = URL.createObjectURL(blob);
        console.log('[DbClient] 创建 Blob URL:', workerUrl);
        
        console.log('[DbClient] 创建 Worker...');
        // 如果 Worker 代码是 ES 模块，需要指定 type: 'module'
        if (isESModule) {
          console.log('[DbClient] 使用 ES 模块 Worker');
          this.worker = new Worker(workerUrl, { type: 'module' });
        } else {
          console.log('[DbClient] 使用经典 Worker');
          this.worker = new Worker(workerUrl);
        }
        console.log('[DbClient] ✅ Worker 创建成功');
      } catch (error) {
        console.error('[DbClient] ❌ Worker 创建失败:', error);
        throw error;
      }
    } else {
      console.log('[DbClient] 使用外部 Worker 文件（开发模式）');
      // 开发环境或回退方案：使用外部文件
      try {
        this.worker = new Worker(new URL('../serviceWorker/dbServiceWorker.ts', import.meta.url), { type: 'module' });
        console.log('[DbClient] ✅ Worker 创建成功（外部文件）');
      } catch (error) {
        console.error('[DbClient] ❌ Worker 创建失败（外部文件）:', error);
        throw error;
      }
    }

    // 设置消息处理器
    this.worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
      console.log('[DbClient] 收到 Worker 响应:', { id: e.data.id, type: e.data.type });
      const { id, type, payload, error } = e.data;
      const request = this.pendingRequests.get(id);
      
      if (request) {
        this.pendingRequests.delete(id);
        if (type === 'success') {
          console.log('[DbClient] 请求成功，id:', id);
          request.resolve(payload);
        } else {
          console.error('[DbClient] 请求失败，id:', id, 'error:', error);
          request.reject(new Error(error || 'Unknown error'));
        }
      } else {
        console.warn('[DbClient] ⚠️ 收到未知请求的响应，id:', id);
      }
    };

    this.worker.onerror = (error) => {
      console.error('[DbClient] ❌ Worker 错误:', error);
      console.error('[DbClient] Worker 错误详情:', {
        message: error.message,
        filename: error.filename,
        lineno: error.lineno,
        colno: error.colno,
        error: error.error,
      });
      // 清理所有 pending 请求
      for (const [id, request] of this.pendingRequests.entries()) {
        this.pendingRequests.delete(id);
        request.reject(error);
      }
    };
    
    // 监听 Worker 消息错误
    this.worker.onmessageerror = (error) => {
      console.error('[DbClient] ❌ Worker 消息错误:', error);
    };

    // 如果没有提供 dbDataBase64，尝试从 window.dbData 读取
    if (!dbDataBase64 && typeof window !== 'undefined' && (window as any).dbData) {
      dbDataBase64 = (window as any).dbData;
      console.log('[DbClient] 从 window.dbData 读取数据，长度:', dbDataBase64?.length || 0);
    }

    // 如果没有提供 wasmBase64，尝试从 window.__sqlWasmBase64 读取
    if (!wasmBase64 && typeof window !== 'undefined' && (window as any).__sqlWasmBase64) {
      wasmBase64 = (window as any).__sqlWasmBase64;
      console.log('[DbClient] 从 window.__sqlWasmBase64 读取数据，长度:', wasmBase64?.length || 0);
    }

    console.log('[DbClient] 准备发送 init 请求...');
    console.log('[DbClient] init 参数 - dbData 长度:', dbDataBase64?.length || 0);
    console.log('[DbClient] init 参数 - wasmBase64 长度:', wasmBase64?.length || 0);
    
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
   * 发送自定义类型请求（用于业务 API 调用）
   */
  async request<T = any>(type: WorkerMessageType, payload?: any): Promise<T> {
    // 复用发送逻辑
    const response = await this.sendRequest(type, payload);
    return (response?.result ?? response) as T;
  }

  /**
   * 发送请求到 Worker
   */
  private sendRequest(type: WorkerMessageType, payload?: any): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.worker) {
        console.error('[DbClient] ❌ Worker 未初始化，无法发送请求');
        reject(new Error('Worker not initialized'));
        return;
      }

      const id = `req_${this.requestIdCounter++}`;
      
      // 设置超时
      const timeoutId = setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          console.error('[DbClient] ❌ 请求超时，id:', id, 'type:', type);
          this.pendingRequests.delete(id);
          reject(new Error('Request timeout'));
        }
      }, 30000); // 30 秒超时
      
      // 包装 resolve 和 reject 以清除超时
      const wrappedResolve = (value: any) => {
        clearTimeout(timeoutId);
        resolve(value);
      };
      const wrappedReject = (reason: any) => {
        clearTimeout(timeoutId);
        reject(reason);
      };
      
      this.pendingRequests.set(id, { resolve: wrappedResolve, reject: wrappedReject });

      const request: WorkerRequest = { id, type, payload };
      console.log('[DbClient] 发送请求到 Worker:', { id, type, payloadKeys: payload ? Object.keys(payload) : [] });
      
      try {
        this.worker.postMessage(request);
        console.log('[DbClient] ✅ 请求已发送，id:', id);
      } catch (error) {
        console.error('[DbClient] ❌ 发送请求失败:', error);
        clearTimeout(timeoutId);
        this.pendingRequests.delete(id);
        reject(error);
        return;
      }
    });
  }
}

