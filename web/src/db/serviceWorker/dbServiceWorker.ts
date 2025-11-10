/**
 * SQLite Service Worker - Provides database service in Worker thread
 * Uses sql.js to execute database operations in Web Worker
 *
 * Responsibilities: Handle messages from main thread, execute database operations
 */

// Note: These imports will be processed by vite during build
// In the final inline version, these library codes will be inlined into the Worker
import initSqlJs from 'sql.js';
import type { Database, SqlJsStatic } from 'sql.js';
import { inflate as pakoInflate } from 'pako';
import * as serviceApi from './serviceApi';

/**
 * Pako object for compatibility and debugging
 */
const pako = {
  inflate: pakoInflate,
};

/**
 * Worker message type definitions
 */
export type WorkerMessageType =
  | 'init'
  | 'exec'
  | 'query'
  | 'close'
  | 'memory.queryByComponent'
  | 'memory.queryResults'
  | 'memory.queryRecords'
  | 'memory.queryOverviewTimeline'
  | 'memory.queryCategoryRecords'
  | 'memory.querySubCategoryRecords'
  | 'memory.queryProcessRecords'
  | 'memory.queryThreadRecords'
  | 'memory.queryFileRecords'
  | 'memory.queryCategories'
  | 'memory.querySubCategories'
  | 'memory.queryTimelineData'
  | 'memory.queryRecordsAtTimePoint'
  | 'memory.queryCategoryStats'
  | 'memory.querySubCategoryStats'
  | 'memory.queryRecordsUpTo'
  | 'memory.queryCallchainFrames';

/**
 * Worker request interface
 */
export interface WorkerRequest {
  id: string;
  type: WorkerMessageType;
  payload?: unknown;
}

/**
 * Worker response interface
 */
export interface WorkerResponse {
  id: string;
  type: 'success' | 'error';
  payload?: unknown;
  error?: string;
}

/**
 * Init payload interface
 */
interface InitPayload {
  dbData?: string;
  wasmBase64?: string;
}

/**
 * SQL parameter value type
 */
type SqlValue = string | number | Uint8Array | null;

/**
 * Exec payload interface
 */
interface ExecPayload {
  sql: string;
  params?: SqlValue[];
}

/**
 * Query payload interface
 */
interface QueryPayload {
  sql: string;
  params?: SqlValue[];
}

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;

/**
 * Initialize SQL.js
 * @param wasmBase64 - Base64 encoded WASM file (optional)
 */
async function initSQL(wasmBase64?: string): Promise<void> {
  if (!SQL) {
    SQL = await initSqlJs({
      locateFile: (file: string) => {
        if (file === 'sql-wasm.wasm' && wasmBase64) {
          return createWasmBlobUrl(wasmBase64);
        }
        return `https://sql.js.org/dist/${file}`;
      },
    });
  }
}

/**
 * Create WASM Blob URL from base64 string
 */
function createWasmBlobUrl(wasmBase64: string): string {
  const binaryString = atob(wasmBase64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return URL.createObjectURL(new Blob([bytes], { type: 'application/wasm' }));
}

/**
 * Decompress database data from base64 gzip
 */
function decompressDatabaseData(dbData: string): Uint8Array {
  const binaryString = atob(dbData);
  const compressedBytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    compressedBytes[i] = binaryString.charCodeAt(i);
  }
  return pako.inflate(compressedBytes);
}

/**
 * Initialize database
 */
async function handleInit(payload: InitPayload): Promise<void> {
  const { dbData, wasmBase64 } = payload || {};

  await initSQL(wasmBase64);

  if (!SQL) {
    throw new Error('SQL.js initialization failed');
  }

  if (dbData) {
    const decompressedBytes = decompressDatabaseData(dbData);
    db = new SQL.Database(decompressedBytes);
  } else {
    db = new SQL.Database();
  }

  return Promise.resolve();
}

/**
 * Handle exec request
 */
function handleExec(payload: ExecPayload): void {
  if (!db) {
    throw new Error('Database not initialized');
  }
  db.run(payload.sql, payload.params || []);
}

/**
 * Handle query request
 */
function handleQuery(payload: QueryPayload): Record<string, unknown>[] {
  if (!db) {
    throw new Error('Database not initialized');
  }

  const stmt = db.prepare(payload.sql);
  if (payload.params) {
    stmt.bind(payload.params);
  }

  const result: Record<string, unknown>[] = [];
  while (stmt.step()) {
    const row = stmt.getAsObject({});
    result.push(row);
  }
  stmt.free();

  return result;
}

/**
 * Handle close request
 */
function handleClose(): void {
  if (db) {
    db.close();
    db = null;
  }
}

/**
 * Send success response
 */
function sendSuccessResponse(id: string, payload?: unknown): void {
  self.postMessage({
    id,
    type: 'success',
    payload,
  } as WorkerResponse);
}

/**
 * Send error response
 */
function sendErrorResponse(id: string, error: unknown): void {
  self.postMessage({
    id,
    type: 'error',
    error: error instanceof Error ? error.message : String(error),
  } as WorkerResponse);
}

/**
 * Handle message - Set up immediately to ensure no messages are missed
 */
self.onmessage = async function (e: MessageEvent<WorkerRequest>): Promise<void> {
  const { id, type, payload } = e.data;

  try {
    switch (type) {
      case 'init': {
        await handleInit(payload as InitPayload);
        sendSuccessResponse(id, { message: 'Database initialized successfully' });
        break;
      }

      case 'memory.queryByComponent': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId } = (payload as { stepId?: number }) || {};
        const result = await serviceApi.queryMemoryRecordsByComponent(db, stepId);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryResults': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId } = (payload as { stepId?: number }) || {};
        const result = await serviceApi.queryMemoryResults(db, stepId);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryRecords': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, limit } = (payload as { stepId?: number; limit?: number }) || {};
        const result = await serviceApi.queryMemoryRecords(db, stepId, limit);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryOverviewTimeline': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, groupBy } = (payload as { stepId: number; groupBy?: 'category' | 'process' }) || {};
        const result = await serviceApi.queryOverviewTimeline(db, stepId, groupBy);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryCategoryRecords': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, categoryName } = (payload as { stepId: number; categoryName: string }) || {};
        const result = await serviceApi.queryCategoryRecords(db, stepId, categoryName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.querySubCategoryRecords': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, categoryName, subCategoryName } = (payload as {
          stepId: number;
          categoryName: string;
          subCategoryName: string;
        }) || {};
        const result = await serviceApi.querySubCategoryRecords(db, stepId, categoryName, subCategoryName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryProcessRecords': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, processName } = (payload as { stepId: number; processName: string }) || {};
        const result = await serviceApi.queryProcessRecords(db, stepId, processName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryThreadRecords': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, processName, threadName } = (payload as {
          stepId: number;
          processName: string;
          threadName: string;
        }) || {};
        const result = await serviceApi.queryThreadRecords(db, stepId, processName, threadName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryFileRecords': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, processName, threadName, fileName } = (payload as {
          stepId: number;
          processName: string;
          threadName: string;
          fileName: string;
        }) || {};
        const result = await serviceApi.queryFileRecords(db, stepId, processName, threadName, fileName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryCategories': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId } = (payload as { stepId: number }) || {};
        const result = await serviceApi.queryCategories(db, stepId);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.querySubCategories': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, categoryName } = (payload as { stepId: number; categoryName: string }) || {};
        const result = await serviceApi.querySubCategories(db, stepId, categoryName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryTimelineData': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, categoryName, subCategoryName } = (payload as {
          stepId: number;
          categoryName?: string;
          subCategoryName?: string;
        }) || {};
        const result = await serviceApi.queryTimelineData(db, stepId, categoryName, subCategoryName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryRecordsAtTimePoint': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, relativeTs } = (payload as { stepId: number; relativeTs: number }) || {};
        const result = await serviceApi.queryRecordsAtTimePoint(db, stepId, relativeTs);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryCategoryStats': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, relativeTs } = (payload as { stepId: number; relativeTs?: number | null }) || {};
        const result = await serviceApi.queryCategoryStats(db, stepId, relativeTs);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.querySubCategoryStats': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, categoryName, relativeTs } = (payload as {
          stepId: number;
          categoryName: string;
          relativeTs?: number | null;
        }) || {};
        const result = await serviceApi.querySubCategoryStats(db, stepId, categoryName, relativeTs);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryRecordsUpTo': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, relativeTs, categoryName, subCategoryName } = (payload as {
          stepId: number;
          relativeTs: number;
          categoryName?: string;
          subCategoryName?: string;
        }) || {};
        const result = await serviceApi.queryRecordsUpToTime(db, stepId, relativeTs, categoryName, subCategoryName);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'memory.queryCallchainFrames': {
        if (!db) {
          throw new Error('Database not initialized');
        }
        const { stepId, callchainIds } = (payload as { stepId: number; callchainIds: number[] }) || {};
        const result = await serviceApi.queryCallchainFrames(db, stepId, Array.isArray(callchainIds) ? callchainIds : []);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'exec': {
        handleExec(payload as ExecPayload);
        sendSuccessResponse(id, { message: 'Execution successful' });
        break;
      }

      case 'query': {
        const result = handleQuery(payload as QueryPayload);
        sendSuccessResponse(id, { result });
        break;
      }

      case 'close': {
        handleClose();
        sendSuccessResponse(id, { message: 'Database closed' });
        break;
      }

      default:
        throw new Error(`Unknown message type: ${type}`);
    }
  } catch (error) {
    sendErrorResponse(id, error);
  }
};
