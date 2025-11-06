/**
 * SQLite Service Worker - 在 Worker 线程中提供数据库服务
 * 使用 sql.js 在 Web Worker 中执行数据库操作
 * 
 * 职责：处理来自主线程的消息，执行数据库操作
 */

// 注意：这些 import 会在构建时被 vite 处理
// 在最终的内联版本中，这些库的代码会被内联到 Worker 中
import initSqlJs from 'sql.js';
import type { Database, SqlJsStatic } from 'sql.js';
// 使用命名导入 inflate，确保在 minify 后也能正常工作
import { inflate as pakoInflate } from 'pako';
import * as serviceApi from './serviceApi';

// 为了兼容性和调试，创建一个 pako 对象
const pako = {
  inflate: pakoInflate,
};

/**
 * Worker 消息类型定义
 */
export type WorkerMessageType = 
  | 'init' 
  | 'exec' 
  | 'query' 
  | 'close'
  | 'memory.queryByComponent'
  | 'memory.queryResults'
  | 'memory.queryRecords';

export interface WorkerRequest {
  id: string;
  type: WorkerMessageType;
  payload?: any;
}

export interface WorkerResponse {
  id: string;
  type: 'success' | 'error';
  payload?: any;
  error?: string;
}

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;

// ⚠️ 重要：立即设置 onmessage 处理器，确保不会错过任何消息
// 这必须在所有其他代码之前执行（在 import 之后）
console.log('[dbServiceWorker] ⚡ Worker 脚本开始执行...');
console.log('[dbServiceWorker] ⚡ 立即设置 onmessage 处理器...');

// 初始化 SQL.js
async function initSQL(wasmBase64?: string) {
  console.log('[dbServiceWorker] initSQL 开始，wasmBase64 长度:', wasmBase64?.length || 0);
  
  if (!SQL) {
    console.log('[dbServiceWorker] SQL.js 未初始化，开始初始化...');
    try {
      SQL = await initSqlJs({
        locateFile: (file: string) => {
          console.log('[dbServiceWorker] locateFile 被调用，文件:', file);
          // 如果提供了 WASM base64 数据，使用它
          if (file === 'sql-wasm.wasm' && wasmBase64) {
            console.log('[dbServiceWorker] 使用内联 WASM 数据');
            // 从 base64 创建 Blob URL
            const binaryString = atob(wasmBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            const blobUrl = URL.createObjectURL(new Blob([bytes], { type: 'application/wasm' }));
            console.log('[dbServiceWorker] 创建 Blob URL:', blobUrl);
            return blobUrl;
          }
          // 否则使用 CDN
          const cdnUrl = `https://sql.js.org/dist/${file}`;
          console.log('[dbServiceWorker] 使用 CDN URL:', cdnUrl);
          return cdnUrl;
        },
      });
      console.log('[dbServiceWorker] SQL.js 初始化成功');
    } catch (error) {
      console.error('[dbServiceWorker] SQL.js 初始化失败:', error);
      throw error;
    }
  } else {
    console.log('[dbServiceWorker] SQL.js 已初始化，跳过');
  }
  return SQL;
}

// 处理消息 - 立即设置，确保不会错过消息
self.onmessage = async function (e: MessageEvent<WorkerRequest>) {
  const { id, type, payload } = e.data;
  
  console.log('[dbServiceWorker] 收到消息:', { id, type, payloadKeys: payload ? Object.keys(payload) : [] });

  try {
    switch (type) {
      case 'init': {
        console.log('[dbServiceWorker] 开始处理 init 请求，id:', id);
        // 初始化数据库
        // payload.dbData: base64 编码的 gzip 压缩的数据库文件（可选）
        // payload.wasmBase64: WASM 文件的 base64 编码（可选，用于内联 WASM）
        const { dbData, wasmBase64 } = payload || {};
        console.log('[dbServiceWorker] init 参数 - dbData 长度:', dbData?.length || 0);
        console.log('[dbServiceWorker] init 参数 - wasmBase64 长度:', wasmBase64?.length || 0);
        console.log('[dbServiceWorker] init 参数 - dbData 前100字符:', dbData?.substring(0, 100));
        console.log('[dbServiceWorker] init 参数 - wasmBase64 前100字符:', wasmBase64?.substring(0, 100));
        
        console.log('[dbServiceWorker] 步骤1: 开始初始化 SQL.js...');
        const startTime = performance.now();
        await initSQL(wasmBase64);
        const sqlInitTime = performance.now() - startTime;
        console.log('[dbServiceWorker] SQL.js 初始化完成，耗时:', sqlInitTime.toFixed(2), 'ms');
        
        if (!SQL) {
          console.error('[dbServiceWorker] SQL.js 初始化失败：SQL 为 null');
          throw new Error('SQL.js 初始化失败');
        }
        console.log('[dbServiceWorker] SQL.js 初始化成功，SQL 对象:', typeof SQL);

        if (dbData) {
          console.log('[dbServiceWorker] 步骤2: 开始处理数据库数据...');
          console.log('[dbServiceWorker] dbData 类型:', typeof dbData);
          console.log('[dbServiceWorker] dbData 长度:', dbData.length);
          
          try {
            // dbData 是 base64 编码的 gzip 压缩的数据库文件
            // 1. 解码 base64 字符串
            console.log('[dbServiceWorker] 步骤2.1: 开始解码 base64...');
            const decodeStartTime = performance.now();
            const binaryString = atob(dbData);
            const compressedBytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              compressedBytes[i] = binaryString.charCodeAt(i);
            }
            const decodeTime = performance.now() - decodeStartTime;
            console.log('[dbServiceWorker] base64 解码完成，耗时:', decodeTime.toFixed(2), 'ms');
            console.log('[dbServiceWorker] 压缩数据大小:', compressedBytes.length, 'bytes');

            // 2. 使用 pako 解压 gzip
            console.log('[dbServiceWorker] 步骤2.2: 开始解压 gzip...');
            console.log('[dbServiceWorker] pako 对象:', typeof pako, pako ? Object.keys(pako) : 'null');
            console.log('[dbServiceWorker] pako.inflate 类型:', typeof pako?.inflate);
            console.log('[dbServiceWorker] pakoInflate 类型:', typeof pakoInflate);
            console.log('[dbServiceWorker] 压缩数据前4字节:', Array.from(compressedBytes.slice(0, 4)).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));
            
            const inflateStartTime = performance.now();
            let decompressedBytes: Uint8Array;
            try {
              // 检查是否是有效的 gzip 数据（gzip 文件头：1f 8b）
              if (compressedBytes.length < 2 || compressedBytes[0] !== 0x1f || compressedBytes[1] !== 0x8b) {
                console.error('[dbServiceWorker] ❌ 无效的 gzip 数据！前2字节:', 
                  '0x' + compressedBytes[0]?.toString(16).padStart(2, '0'), 
                  '0x' + compressedBytes[1]?.toString(16).padStart(2, '0'));
                throw new Error('Invalid gzip data: expected 0x1f 0x8b header');
              }
              
              // 直接使用 pakoInflate 函数，避免通过对象访问
              const inflateFn = pakoInflate || pako?.inflate;
              if (!inflateFn || typeof inflateFn !== 'function') {
                throw new Error('pako.inflate is not available or not a function');
              }
              
              console.log('[dbServiceWorker] 调用 inflate 函数...');
              decompressedBytes = inflateFn(compressedBytes);
              const inflateTime = performance.now() - inflateStartTime;
              console.log('[dbServiceWorker] ✅ gzip 解压完成，耗时:', inflateTime.toFixed(2), 'ms');
              console.log('[dbServiceWorker] 解压后数据大小:', decompressedBytes.length, 'bytes');
            } catch (inflateError) {
              const inflateTime = performance.now() - inflateStartTime;
              console.error('[dbServiceWorker] ❌ gzip 解压失败，耗时:', inflateTime.toFixed(2), 'ms');
              console.error('[dbServiceWorker] 解压错误类型:', typeof inflateError);
              console.error('[dbServiceWorker] 解压错误:', inflateError);
              console.error('[dbServiceWorker] 解压错误消息:', inflateError instanceof Error ? inflateError.message : String(inflateError));
              console.error('[dbServiceWorker] 解压错误堆栈:', inflateError instanceof Error ? inflateError.stack : 'No stack');
              console.error('[dbServiceWorker] 压缩数据长度:', compressedBytes.length);
              console.error('[dbServiceWorker] 压缩数据前10字节:', Array.from(compressedBytes.slice(0, 10)).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));
              throw new Error(`Gzip decompression failed: ${inflateError instanceof Error ? inflateError.message : String(inflateError)}`);
            }

            // 3. 创建数据库
            console.log('[dbServiceWorker] 步骤2.3: 开始创建数据库...');
            const dbCreateStartTime = performance.now();
            db = new SQL.Database(decompressedBytes);
            const dbCreateTime = performance.now() - dbCreateStartTime;
            console.log('[dbServiceWorker] 数据库创建完成，耗时:', dbCreateTime.toFixed(2), 'ms');
            console.log('[dbServiceWorker] 数据库对象:', typeof db);
          } catch (dbError) {
            console.error('[dbServiceWorker] ❌ 处理数据库数据时出错');
            console.error('[dbServiceWorker] 错误类型:', typeof dbError);
            console.error('[dbServiceWorker] 错误对象:', dbError);
            console.error('[dbServiceWorker] 错误消息:', dbError instanceof Error ? dbError.message : String(dbError));
            console.error('[dbServiceWorker] 错误堆栈:', dbError instanceof Error ? dbError.stack : 'No stack');
            console.error('[dbServiceWorker] 错误名称:', dbError instanceof Error ? dbError.name : 'Unknown');
            if (dbError instanceof Error && (dbError as any).cause) {
              console.error('[dbServiceWorker] 错误原因:', (dbError as any).cause);
            }
            throw dbError;
          }
        } else {
          console.log('[dbServiceWorker] 步骤2: 创建空数据库...');
          db = new SQL.Database();
          console.log('[dbServiceWorker] 空数据库创建完成');
        }

        console.log('[dbServiceWorker] 步骤3: 发送成功响应...');
        const response: WorkerResponse = {
          id,
          type: 'success',
          payload: { message: '数据库初始化成功' },
        };
        console.log('[dbServiceWorker] 响应内容:', response);
        self.postMessage(response);
        console.log('[dbServiceWorker] 响应已发送，id:', id);
        break;
      }

      // 业务请求：内存数据 - 按组件与时间分组聚合
      case 'memory.queryByComponent': {
        if (!db) {
          throw new Error('数据库未初始化');
        }
        const { stepName } = payload || {};
        const result = await serviceApi.queryMemoryRecordsByComponent(db, stepName);
        self.postMessage({ id, type: 'success', payload: { result } } as WorkerResponse);
        break;
      }

      case 'memory.queryResults': {
        if (!db) {
          throw new Error('数据库未初始化');
        }
        const { stepName } = payload || {};
        const result = await serviceApi.queryMemoryResults(db, stepName);
        self.postMessage({ id, type: 'success', payload: { result } } as WorkerResponse);
        break;
      }

      case 'memory.queryRecords': {
        if (!db) {
          throw new Error('数据库未初始化');
        }
        const { stepName, limit } = payload || {};
        const result = await serviceApi.queryMemoryRecords(db, stepName, limit);
        self.postMessage({ id, type: 'success', payload: { result } } as WorkerResponse);
        break;
      }

      case 'exec': {
        // 执行 SQL 语句（不返回结果）
        if (!db) {
          throw new Error('数据库未初始化');
        }
        db.run(payload.sql, payload.params || []);
        self.postMessage({
          id,
          type: 'success',
          payload: { message: '执行成功' },
        } as WorkerResponse);
        break;
      }

      case 'query': {
        // 查询 SQL 语句（返回结果）
        if (!db) {
          throw new Error('数据库未初始化');
        }
        const stmt = db.prepare(payload.sql);
        if (payload.params) {
          stmt.bind(payload.params);
        }

        const result: any[] = [];
        while (stmt.step()) {
          const row = stmt.getAsObject({});
          result.push(row);
        }
        stmt.free();

        self.postMessage({
          id,
          type: 'success',
          payload: { result },
        } as WorkerResponse);
        break;
      }

      case 'close': {
        // 关闭数据库
        if (db) {
          db.close();
          db = null;
        }
        self.postMessage({
          id,
          type: 'success',
          payload: { message: '数据库已关闭' },
        } as WorkerResponse);
        break;
      }

      default:
        console.error('[dbServiceWorker] 未知的消息类型:', type);
        throw new Error(`未知的消息类型: ${type}`);
    }
  } catch (error) {
    console.error('[dbServiceWorker] 处理消息时出错:', error);
    console.error('[dbServiceWorker] 错误详情:', {
      id,
      type,
      errorMessage: error instanceof Error ? error.message : String(error),
      errorStack: error instanceof Error ? error.stack : undefined,
    });
    const errorResponse: WorkerResponse = {
      id,
      type: 'error',
      error: error instanceof Error ? error.message : String(error),
    };
    console.log('[dbServiceWorker] 发送错误响应:', errorResponse);
    self.postMessage(errorResponse);
    console.log('[dbServiceWorker] 错误响应已发送，id:', id);
  }
};

// Worker 启动日志 - 在文件最顶部执行，确保立即输出
try {
  console.log('[dbServiceWorker] Worker 已启动');
  console.log('[dbServiceWorker] Worker 环境:', {
    self: typeof self,
    importScripts: typeof (self as any).importScripts,
    location: typeof location !== 'undefined' ? location.href : 'undefined',
  });
  
  // 验证 onmessage 是否已设置
  console.log('[dbServiceWorker] onmessage 已设置:', typeof self.onmessage === 'function');
  
  // 添加全局错误处理
  self.onerror = (error) => {
    console.error('[dbServiceWorker] ❌ Worker 全局错误:', error);
    return false;
  };
  
  // 添加未捕获的 Promise 错误处理
  self.addEventListener('unhandledrejection', (event) => {
    console.error('[dbServiceWorker] ❌ 未处理的 Promise 拒绝:', event.reason);
  });
  
  console.log('[dbServiceWorker] ✅ Worker 初始化完成，等待消息...');
} catch (error) {
  console.error('[dbServiceWorker] ❌ Worker 启动时出错:', error);
}

