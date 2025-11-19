/**
 * Service API - Database query functions
 * Provides high-level database query functions for memory data
 */

import type { Database } from 'sql.js';
import { MemoryDao } from '../dao/memoryDao';

/**
 * SQL query result row type
 */
type SqlRow = Record<string, unknown>;

/**
 * Format SQL with parameters for logging
 * @param sql - SQL query string
 * @param params - Query parameters
 * @returns Formatted SQL string for logging
 */
function formatSqlForLogging(sql: string, params: (string | number | null)[]): string {
  if (!params || params.length === 0) {
    return sql;
  }
  
  let formattedSql = sql;
  let paramIndex = 0;
  formattedSql = sql.replace(/\?/g, () => {
    const param = params[paramIndex++];
    if (param === null || param === undefined) {
      return 'NULL';
    }
    if (typeof param === 'string') {
      // Truncate long strings for logging
      const str = param.length > 100 ? param.substring(0, 100) + '...' : param;
      return `'${str.replace(/'/g, "''")}'`;
    }
    return String(param);
  });
  
  return formattedSql;
}

/**
 * Execute query and return formatted results
 * @param db - Database instance
 * @param buildQuery - Function that builds SQL query with step id parameter
 * @param stepId - Step id (optional, for filtering specific step)
 * @returns Query result rows
 */
async function executeQuery(
  db: Database,
  buildQuery: (stepId?: number) => { sql: string; params: (string | number | null)[] },
  stepId?: number
): Promise<SqlRow[]> {
  const { sql, params } = buildQuery(stepId);
  const startTime = performance.now();
  const formattedSql = formatSqlForLogging(sql, params || []);
  
  try {
    const stmt = db.prepare(sql);
    
    if (params && params.length > 0) {
      stmt.bind(params);
    }
    
    const rows: SqlRow[] = [];
    while (stmt.step()) {
      rows.push(stmt.getAsObject({}));
    }
    
    stmt.free();
    
    const duration = performance.now() - startTime;
    console.log(`[SQL Performance] Query executed in ${duration.toFixed(2)}ms, returned ${rows.length} rows`);
    console.log(`[SQL Performance] SQL: ${formattedSql}`);
    
    return rows;
  } catch (error) {
    const duration = performance.now() - startTime;
    console.error(`[SQL Performance] Query failed after ${duration.toFixed(2)}ms`);
    console.error(`[SQL Performance] SQL: ${formattedSql}`);
    console.error(`[SQL Performance] Error:`, error);
    throw error;
  }
}

/**
 * Query memory results (summary statistics for each step)
 * @param db - Database instance
 * @param stepId - Step id (optional, for filtering specific step)
 * @returns Memory results array containing peak_time, peak_value, records_count, etc.
 */
export async function queryMemoryResults(db: Database, stepId?: number): Promise<SqlRow[]> {
  return executeQuery(db, MemoryDao.buildQueryMemoryResults, stepId);
}

/**
 * Query overview level timeline data (aggregated by time point and category/process)
 * @param db - Database instance
 * @param stepId - Step id
 * @param groupBy - Group by field: 'category' or 'process'
 * @returns Overview timeline data array (timePoint10ms, categoryName, netSize)
 */
export async function queryOverviewTimeline(
  db: Database,
  stepId: number,
  groupBy: 'category' | 'process' = 'category'
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryOverviewTimeline(stepId, groupBy);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query category level records (for specific category)
 * @param db - Database instance
 * @param stepId - Step id
 * @param categoryName - Category name
 * @returns Category records array
 */
export async function queryCategoryRecords(
  db: Database,
  stepId: number,
  categoryName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryCategoryRecords(stepId, categoryName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query subcategory level records (for specific subcategory)
 * @param db - Database instance
 * @param stepId - Step id
 * @param categoryName - Category name
 * @param subCategoryName - Subcategory name
 * @returns Subcategory records array
 */
export async function querySubCategoryRecords(
  db: Database,
  stepId: number,
  categoryName: string,
  subCategoryName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQuerySubCategoryRecords(stepId, categoryName, subCategoryName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query process level records (for specific process)
 * @param db - Database instance
 * @param stepId - Step id
 * @param processName - Process name
 * @returns Process records array
 */
export async function queryProcessRecords(
  db: Database,
  stepId: number,
  processName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryProcessRecords(stepId, processName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query thread level records (for specific thread)
 * @param db - Database instance
 * @param stepId - Step id
 * @param processName - Process name
 * @param threadName - Thread name
 * @returns Thread records array
 */
export async function queryThreadRecords(
  db: Database,
  stepId: number,
  processName: string,
  threadName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryThreadRecords(stepId, processName, threadName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query file level records (for specific file)
 * @param db - Database instance
 * @param stepId - Step id
 * @param processName - Process name
 * @param threadName - Thread name
 * @param fileName - File name
 * @returns File records array
 */
export async function queryFileRecords(
  db: Database,
  stepId: number,
  processName: string,
  threadName: string,
  fileName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryFileRecords(stepId, processName, threadName, fileName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query file level event type records (for category mode)
 * @param db - Database instance
 * @param stepId - Step id
 * @param categoryName - Category name
 * @param subCategoryName - Subcategory name
 * @param fileName - File name
 * @returns File event type records array
 */
export async function queryFileEventTypeRecords(
  db: Database,
  stepId: number,
  categoryName: string,
  subCategoryName: string,
  fileName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryFileEventTypeRecords(stepId, categoryName, subCategoryName, fileName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query file level event type records (for process mode)
 * @param db - Database instance
 * @param stepId - Step id
 * @param processName - Process name
 * @param threadName - Thread name
 * @param fileName - File name
 * @returns File event type records array
 */
export async function queryFileEventTypeRecordsForProcess(
  db: Database,
  stepId: number,
  processName: string,
  threadName: string,
  fileName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryFileEventTypeRecordsForProcess(stepId, processName, threadName, fileName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query all unique categories for a step
 * @param db - Database instance
 * @param stepId - Step id
 * @returns Array of category names
 */
export async function queryCategories(db: Database, stepId: number): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryCategories(stepId);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query all unique subcategories for a category
 * @param db - Database instance
 * @param stepId - Step id
 * @param categoryName - Category name
 * @returns Array of subcategory names
 */
export async function querySubCategories(
  db: Database,
  stepId: number,
  categoryName: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQuerySubCategories(stepId, categoryName);
  return executeQueryWithExec(db, sql, params);
}

/**
 * Execute SQL query with parameters using db.exec (more reliable for column names)
 * @param db - Database instance
 * @param sql - SQL query string
 * @param params - Query parameters
 * @returns Query result rows
 */
function executeQueryWithExec(db: Database, sql: string, params: (string | number | null)[]): SqlRow[] {
  const startTime = performance.now();
  
  // Build SQL with parameters for db.exec
  let execSql = sql;
  if (params && params.length > 0) {
    let paramIndex = 0;
    execSql = sql.replace(/\?/g, () => {
      const param = params[paramIndex++];
      if (param === null || param === undefined) {
        return 'NULL';
      }
      if (typeof param === 'string') {
        // Escape single quotes
        return `'${param.replace(/'/g, "''")}'`;
      }
      return String(param);
    });
  }

  const formattedSql = formatSqlForLogging(sql, params || []);
  
  try {
    const execResult = db.exec(execSql);

    if (execResult && execResult.length > 0) {
      const execRows = execResult[0];
      const execRowCount = execRows.values?.length || 0;
      const columns = execRows.columns || [];

      if (execRowCount === 0) {
        const duration = performance.now() - startTime;
        console.log(`[SQL Performance] Query executed in ${duration.toFixed(2)}ms, returned 0 rows`);
        console.log(`[SQL Performance] SQL: ${formattedSql}`);
        return [];
      }

      // Convert exec result to object array
      const rows: SqlRow[] = [];
      for (let i = 0; i < execRowCount; i++) {
        const row: SqlRow = {};
        const values = execRows.values[i];
        for (let j = 0; j < columns.length; j++) {
          row[columns[j]] = values[j];
        }
        rows.push(row);
      }

      const duration = performance.now() - startTime;
      console.log(`[SQL Performance] Query executed in ${duration.toFixed(2)}ms, returned ${rows.length} rows`);
      console.log(`[SQL Performance] SQL: ${formattedSql}`);

      return rows;
    } else {
      const duration = performance.now() - startTime;
      console.log(`[SQL Performance] Query executed in ${duration.toFixed(2)}ms, returned 0 rows`);
      console.log(`[SQL Performance] SQL: ${formattedSql}`);
      return [];
    }
  } catch (error) {
    const duration = performance.now() - startTime;
    console.error(`[SQL Performance] Query failed after ${duration.toFixed(2)}ms`);
    console.error(`[SQL Performance] SQL: ${formattedSql}`);
    console.error(`[SQL Performance] Error:`, error);
    throw error;
  }
}

/**
 * Query records up to a specified timestamp (inclusive) with category filters
 * Used for category view mode
 * @param db - Database instance
 * @param stepId - Step id
 * @param relativeTsUpperBound - Upper bound for relative timestamp (nanoseconds)
 * @param categoryName - Category filter (optional)
 * @param subCategoryName - Subcategory filter (optional)
 * @param fileName - File name filter (optional, supports LIKE pattern matching)
 * @returns Matching records ordered by relativeTs
 */
export async function queryRecordsUpToTimeByCategory(
  db: Database,
  stepId: number,
  relativeTsUpperBound: number,
  categoryName?: string,
  subCategoryName?: string,
  fileName?: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryRecordsUpToTimeByCategory(
    stepId,
    relativeTsUpperBound,
    categoryName,
    subCategoryName,
    fileName
  );
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query records up to a specified timestamp (inclusive) with process/thread filters
 * Used for process view mode
 * @param db - Database instance
 * @param stepId - Step id
 * @param relativeTsUpperBound - Upper bound for relative timestamp (nanoseconds)
 * @param processName - Process name filter (optional)
 * @param threadName - Thread name filter (optional)
 * @param fileName - File name filter (optional, supports LIKE pattern matching)
 * @returns Matching records ordered by relativeTs
 */
export async function queryRecordsUpToTimeByProcess(
  db: Database,
  stepId: number,
  relativeTsUpperBound: number,
  processName?: string,
  threadName?: string,
  fileName?: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryRecordsUpToTimeByProcess(
    stepId,
    relativeTsUpperBound,
    processName,
    threadName,
    fileName
  );
  return executeQueryWithExec(db, sql, params);
}

/**
 * Query callchain frames for specified callchain ids
 * @param db - Database instance
 * @param stepId - Step id
 * @param callchainIds - List of callchain ids
 * @returns Callchain frame rows ordered by callchainId and depth
 */
export async function queryCallchainFrames(
  db: Database,
  stepId: number,
  callchainIds: number[]
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryCallchainFrames(stepId, callchainIds);
  return executeQueryWithExec(db, sql, params);
}

