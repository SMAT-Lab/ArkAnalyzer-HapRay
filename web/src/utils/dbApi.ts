/**
 * SQLite Worker API - Unified Entry Point
 * Provides convenient API to operate database, integrates Client and DAO layers
 */

import { DbClient, type SqlParam, type SqlRow } from '../db/client/dbClient';
import type { MemoryRecordByComponent } from '../db/dao/memoryDao';

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
   * Query memory_records table, grouped by componentName and relativeTs, aggregated by heapSize
   * New flow: Directly send built-in business message to Worker, Worker calls DAO and executes SQLite
   * @param stepId - Step name (optional, for filtering specific step)
   * @returns Memory records grouped by component
   */
  async queryMemoryRecordsByComponent(stepId?: number): Promise<MemoryRecordByComponent[]> {
    return await this.client.request<MemoryRecordByComponent[]>('memory.queryByComponent', { stepId });
  }

  /**
   * Query all records in memory_records table (optional filtering)
   *
   * @param stepId - Step name (optional, for filtering specific step)
   * @param limit - Limit number of returned records (optional)
   * @returns Query result array
   */
  async queryMemoryRecords(stepId?: number, limit?: number): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryRecords', { stepId, limit });
  }

  /**
   * Query overview level timeline data (aggregated by time point and category)
   * @param stepId - Step id
   * @returns Overview timeline data array
   */
  async queryOverviewTimeline(stepId: number): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryOverviewTimeline', { stepId });
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
   * Query all distinct step names from memory_records table
   * @returns Array of step names
   */
  async queryMemorySteps(): Promise<number[]> {
    const results = await this.query('SELECT DISTINCT step_id FROM memory_records WHERE step_id IS NOT NULL ORDER BY step_id');
    return results.map((row: SqlRow) => Number(row.step_id) || 0);
  }

  /**
   * Query timeline data (aggregated by time point)
   *
   * @param stepId - Step id
   * @param categoryName - Category name filter (optional)
   * @param subCategoryName - Sub-category name filter (optional)
   * @returns Timeline data array
   */
  async queryTimelineData(
    stepId: number,
    categoryName?: string,
    subCategoryName?: string
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryTimelineData', {
      stepId,
      categoryName,
      subCategoryName,
    });
  }

  /**
   * Query records at a specific time point
   *
   * @param stepId - Step id
   * @param relativeTs - Time point (in 10ms units)
   * @returns Records array at the specified time point
   */
  async queryRecordsAtTimePoint(stepId: number, relativeTs: number): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryRecordsAtTimePoint', {
      stepId,
      relativeTs,
    });
  }

  /**
   * Query category statistics
   *
   * @param stepId - Step id
   * @param relativeTs - Time point filter (optional, null means all time)
   * @returns Category statistics array
   */
  async queryCategoryStats(stepId: number, relativeTs?: number | null): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.queryCategoryStats', {
      stepId,
      relativeTs,
    });
  }

  /**
   * Query sub-category statistics
   *
   * @param stepId - Step id
   * @param categoryName - Category name filter
   * @param relativeTs - Time point filter (optional, null means all time)
   * @returns Sub-category statistics array
   */
  async querySubCategoryStats(
    stepId: number,
    categoryName: string,
    relativeTs?: number | null
  ): Promise<SqlRow[]> {
    return await this.client.request<SqlRow[]>('memory.querySubCategoryStats', {
      stepId,
      categoryName,
      relativeTs,
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
