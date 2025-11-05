/**
 * SQLite Worker - 在 Worker 线程中提供 SQLite API
 * 使用 sql.js 在 Web Worker 中执行数据库操作
 */

// 注意：这些 import 会在构建时被 vite 处理
// 在最终的内联版本中，这些库的代码会被内联到 Worker 中
import initSqlJs, { Database, SqlJsStatic } from 'sql.js';
import pako from 'pako';

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

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;

// 初始化 SQL.js
async function initSQL(wasmBase64?: string) {
  if (!SQL) {
    SQL = await initSqlJs({
      locateFile: (file: string) => {
        // 如果提供了 WASM base64 数据，使用它
        if (file === 'sql-wasm.wasm' && wasmBase64) {
          // 从 base64 创建 Blob URL
          const binaryString = atob(wasmBase64);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          return URL.createObjectURL(new Blob([bytes], { type: 'application/wasm' }));
        }
        // 否则使用 CDN
        return `https://sql.js.org/dist/${file}`;
      },
    });
  }
  return SQL;
}

// 处理消息
self.onmessage = async function (e: MessageEvent<WorkerRequest>) {
  const { id, type, payload } = e.data;

  try {
    switch (type) {
      case 'init': {
        // 初始化数据库
        // payload.dbData: base64 编码的 gzip 压缩的数据库文件（可选）
        // payload.wasmBase64: WASM 文件的 base64 编码（可选，用于内联 WASM）
        const { dbData, wasmBase64 } = payload || {};
        
        await initSQL(wasmBase64);
        
        if (!SQL) {
          throw new Error('SQL.js 初始化失败');
        }

        if (dbData) {
          // dbData 是 base64 编码的 gzip 压缩的数据库文件
          // 1. 解码 base64 字符串
          const binaryString = atob(dbData);
          const compressedBytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            compressedBytes[i] = binaryString.charCodeAt(i);
          }

          // 2. 使用 pako 解压 gzip
          const decompressedBytes = pako.inflate(compressedBytes);

          // 3. 创建数据库
          db = new SQL.Database(decompressedBytes);
        } else {
          // 创建空数据库
          db = new SQL.Database();
        }

        self.postMessage({
          id,
          type: 'success',
          payload: { message: '数据库初始化成功' },
        } as WorkerResponse);
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
        throw new Error(`未知的消息类型: ${type}`);
    }
  } catch (error) {
    self.postMessage({
      id,
      type: 'error',
      error: error instanceof Error ? error.message : String(error),
    } as WorkerResponse);
  }
};

