/**
 * SQLite Worker API - Unified Entry Point
 * Provides convenient API to operate database, integrates Client and DAO layers
 */

import { DbClient, type SqlParam, type SqlRow } from '../db/client/dbClient';

/**
 * Database API class
 * Integrates database client and data access objects
 */
export class DbApi {
  private client: DbClient;

  constructor() {
    this.client = new DbClient();
  }

  /**
   * Initialize Worker
   * @param dbDataBase64 - Base64 encoded gzip compressed database file (optional, reads from window.dbData)
   * @param wasmBase64 - Base64 encoded WASM file (optional, reads from window.__sqlWasmBase64)
   */
  async init(dbDataBase64?: string, wasmBase64?: string): Promise<void> {
    await this.client.init(dbDataBase64, wasmBase64);
  }

  /**
   * Execute SQL statement (no return value)
   * @param sql - SQL statement
   * @param params - Parameter array (optional)
   */
  async exec(sql: string, params?: SqlParam[]): Promise<void> {
    await this.client.exec(sql, params);
  }

  /**
   * Query SQL statement (returns results)
   * @param sql - SQL query statement
   * @param params - Parameter array (optional)
   * @returns Query result array
   */
  async query(sql: string, params?: SqlParam[]): Promise<SqlRow[]> {
    return await this.client.query(sql, params);
  }

  /**
   * Query overview level timeline data (aggregated by time point and category/process)
   * @param stepId - Step id
   * @param groupBy - Group by field: 'category' or 'process'
   * @returns Overview timeline data array
   */
  async queryOverviewTimeline(stepId: number, groupBy: 'category' | 'process' = 'category'): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryOverviewTimeline', { stepId, groupBy });
  }

  /**
   * Query category level records (for specific category)
   * @param stepId - Step id
   * @param categoryName - Category name
   * @returns Category records array
   */
  async queryCategoryRecords(stepId: number, categoryName: string): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryCategoryRecords', { stepId, categoryName });
  }

  /**
   * Query subcategory level records (for specific subcategory)
   * @param stepId - Step id
   * @param categoryName - Category name
   * @param subCategoryName - Subcategory name
   * @returns Subcategory records array
   */
  async querySubCategoryRecords(
    stepId: number,
    categoryName: string,
    subCategoryName: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.querySubCategoryRecords', {
      stepId,
      categoryName,
      subCategoryName,
    });
  }

  /**
   * Query process level records (for specific process)
   * @param stepId - Step id
   * @param processName - Process name
   * @returns Process records array
   */
  async queryProcessRecords(stepId: number, processName: string): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryProcessRecords', { stepId, processName });
  }

  /**
   * Query thread level records (for specific thread)
   * @param stepId - Step id
   * @param processName - Process name
   * @param threadName - Thread name
   * @returns Thread records array
   */
  async queryThreadRecords(
    stepId: number,
    processName: string,
    threadName: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryThreadRecords', {
      stepId,
      processName,
      threadName,
    });
  }

  /**
   * Query file level records (for specific file)
   * @param stepId - Step id
   * @param processName - Process name
   * @param threadName - Thread name
   * @param fileName - File name
   * @returns File records array
   */
  async queryFileRecords(
    stepId: number,
    processName: string,
    threadName: string,
    fileName: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryFileRecords', {
      stepId,
      processName,
      threadName,
      fileName,
    });
  }

  /**
   * Query file level event type records (for category mode)
   * @param stepId - Step id
   * @param categoryName - Category name
   * @param subCategoryName - Subcategory name
   * @param fileName - File name
   * @returns File event type records array
   */
  async queryFileEventTypeRecords(
    stepId: number,
    categoryName: string,
    subCategoryName: string,
    fileName: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryFileEventTypeRecords', {
      stepId,
      categoryName,
      subCategoryName,
      fileName,
    });
  }

  /**
   * Query file level event type records (for process mode)
   * @param stepId - Step id
   * @param processName - Process name
   * @param threadName - Thread name
   * @param fileName - File name
   * @returns File event type records array
   */
  async queryFileEventTypeRecordsForProcess(
    stepId: number,
    processName: string,
    threadName: string,
    fileName: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryFileEventTypeRecordsForProcess', {
      stepId,
      processName,
      threadName,
      fileName,
    });
  }

  /**
   * Query all unique categories for a step
   * @param stepId - Step id
   * @returns Array of category names
   */
  async queryCategories(stepId: number): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryCategories', { stepId });
  }

  /**
   * Query all unique subcategories for a category
   * @param stepId - Step id
   * @param categoryName - Category name
   * @returns Array of subcategory names
   */
  async querySubCategories(stepId: number, categoryName: string): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.querySubCategories', { stepId, categoryName });
  }

  /**
   * Query summary information from memory_results table
   *
   * @param stepId - Step name (optional, for filtering specific step)
   * @returns Query result array
   */
  async queryMemoryResults(stepId?: number): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryResults', { stepId });
  }

  /**
   * Query memory meminfo data
   *
   * @param stepId - Step id
   * @returns Query result array
   */
  async queryMemoryMeminfo(stepId: number): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryMeminfo', { stepId });
  }

  /**
   * Query records up to a specific timestamp (inclusive) with category filters
   * Used for category view mode
   *
   * @param stepId - Step id
   * @param relativeTs - Timestamp upper bound in nanoseconds
   * @param categoryName - Optional category name filter
   * @param subCategoryName - Optional subcategory name filter
   * @param fileName - Optional file name filter (supports LIKE pattern matching)
   * @returns Matching records ordered by relativeTs
   */
  async queryRecordsUpToByCategory(
    stepId: number,
    relativeTs: number,
    categoryName?: string,
    subCategoryName?: string,
    fileName?: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryRecordsUpToByCategory', {
      stepId,
      relativeTs,
      categoryName,
      subCategoryName,
      fileName,
    });
  }

  /**
   * Query records up to a specific timestamp (inclusive) with process/thread filters
   * Used for process view mode
   *
   * @param stepId - Step id
   * @param relativeTs - Timestamp upper bound in nanoseconds
   * @param processName - Optional process name filter
   * @param threadName - Optional thread name filter
   * @param fileName - Optional file name filter (supports LIKE pattern matching)
   * @returns Matching records ordered by relativeTs
   */
  async queryRecordsUpToByProcess(
    stepId: number,
    relativeTs: number,
    processName?: string,
    threadName?: string,
    fileName?: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryRecordsUpToByProcess', {
      stepId,
      relativeTs,
      processName,
      threadName,
      fileName,
    });
  }

  /**
   * Query callchain frames for specified callchain ids
   *
   * @param stepId - Step id
   * @param callchainIds - Callchain id list
   * @returns Callchain frame rows ordered by callchainId and depth
   */
  async queryCallchainFrames(stepId: number, callchainIds: number[]): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryCallchainFrames', {
      stepId,
      callchainIds,
    });
  }

  /**
   * Close database and Worker
   */
  async close(): Promise<void> {
    await this.client.close();
  }
}

/**
 * Singleton instance
 */
let dbApiInstance: DbApi | null = null;

/**
 * Get DbApi instance (singleton pattern)
 * @returns DbApi instance
 */
export function getDbApi(): DbApi {
  if (!dbApiInstance) {
    dbApiInstance = new DbApi();
  }
  return dbApiInstance;
}

/**
 * Initialize database (convenience function)
 * @param dbDataBase64 - Base64 encoded gzip compressed database file (optional)
 * @param wasmBase64 - Base64 encoded WASM file (optional)
 * @returns Initialized DbApi instance
 */
export async function initDb(dbDataBase64?: string, wasmBase64?: string): Promise<DbApi> {
  const api = getDbApi();
  await api.init(dbDataBase64, wasmBase64);
  return api;
}
