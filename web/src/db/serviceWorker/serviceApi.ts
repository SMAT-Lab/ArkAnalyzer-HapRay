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
  const stmt = db.prepare(sql);
  
  if (params && params.length > 0) {
    stmt.bind(params);
  }
  
  const rows: SqlRow[] = [];
  while (stmt.step()) {
    rows.push(stmt.getAsObject({}));
  }
  
  stmt.free();
  return rows;
}

/**
 * Query memory records grouped by component and relative timestamp
 * @param db - Database instance
 * @param stepId - Step id (optional, for filtering specific step)
 * @returns Formatted memory records grouped by component
 */
export async function queryMemoryRecordsByComponent(
  db: Database,
  stepId?: number
): Promise<ReturnType<typeof MemoryDao.formatMemoryRecordsByComponent>> {
  const rows = await executeQuery(db, MemoryDao.buildQueryMemoryRecordsByComponent, stepId);
  return MemoryDao.formatMemoryRecordsByComponent(rows);
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
 * Query memory records (detailed event records)
 * @param db - Database instance
 * @param stepId - Step id (optional, for filtering specific step)
 * @param limit - Limit number of returned records (optional)
 * @returns Memory records array containing all event details
 */
export async function queryMemoryRecords(
  db: Database,
  stepId?: number,
  limit?: number
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryMemoryRecords(stepId, limit);
  console.log('[serviceApi] queryMemoryRecords - SQL:', sql);
  console.log('[serviceApi] queryMemoryRecords - Params:', params);
  
  // Build SQL with parameters for db.exec
  // Note: Using db.exec directly because Statement.step() has issues with large datasets
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
  
  console.log('[serviceApi] queryMemoryRecords - Executing query with db.exec...');
  const startTime = performance.now();
  
  try {
    const execResult = db.exec(execSql);
    
    if (execResult && execResult.length > 0) {
      const execRows = execResult[0];
      const execRowCount = execRows.values?.length || 0;
      const columns = execRows.columns || [];
      
      console.log(`[serviceApi] queryMemoryRecords - db.exec returned ${execRowCount} rows, ${columns.length} columns`);
      
      if (execRowCount === 0) {
        console.log('[serviceApi] queryMemoryRecords - No records found');
        return [];
      }
      
      // Convert exec result to object array
      const rows: SqlRow[] = [];
      const conversionStartTime = performance.now();
      
      for (let i = 0; i < execRowCount; i++) {
        const row: SqlRow = {};
        const values = execRows.values[i];
        for (let j = 0; j < columns.length; j++) {
          row[columns[j]] = values[j];
        }
        rows.push(row);
        
        // Output progress every 50000 records (to avoid too many logs)
        if ((i + 1) % 50000 === 0) {
          const elapsed = ((performance.now() - conversionStartTime) / 1000).toFixed(2);
          console.log(`[serviceApi] queryMemoryRecords - Converted ${i + 1}/${execRowCount} records (${elapsed}s elapsed)...`);
        }
      }
      
      const totalTime = ((performance.now() - startTime) / 1000).toFixed(2);
      const conversionTime = ((performance.now() - conversionStartTime) / 1000).toFixed(2);
      console.log(`[serviceApi] queryMemoryRecords - Successfully converted ${rows.length} records (conversion: ${conversionTime}s, total: ${totalTime}s)`);
      
      return rows;
    } else {
      console.log('[serviceApi] queryMemoryRecords - No result from db.exec');
      return [];
    }
  } catch (execError) {
    console.error('[serviceApi] queryMemoryRecords - db.exec failed:', execError);
    throw execError;
  }
}

/**
 * Execute query with parameters (helper function)
 * @param db - Database instance
 * @param sql - SQL query string
 * @param params - Query parameters
 * @returns Query result rows
 */
function executeQueryWithParams(db: Database, sql: string, params: (string | number | null)[]): SqlRow[] {
  const stmt = db.prepare(sql);

  if (params && params.length > 0) {
    stmt.bind(params);
  }

  const rows: SqlRow[] = [];
  while (stmt.step()) {
    rows.push(stmt.getAsObject({}));
  }

  stmt.free();
  return rows;
}

/**
 * Execute SQL query with parameters using db.exec (more reliable for column names)
 * @param db - Database instance
 * @param sql - SQL query string
 * @param params - Query parameters
 * @returns Query result rows
 */
function executeQueryWithExec(db: Database, sql: string, params: (string | number | null)[]): SqlRow[] {
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

  const execResult = db.exec(execSql);

  if (execResult && execResult.length > 0) {
    const execRows = execResult[0];
    const execRowCount = execRows.values?.length || 0;
    const columns = execRows.columns || [];

    if (execRowCount === 0) {
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

    return rows;
  } else {
    return [];
  }
}

/**
 * Query timeline data (aggregated by time point)
 * @param db - Database instance
 * @param stepId - Step id
 * @param categoryName - Category name filter (optional)
 * @param subCategoryName - Sub-category name filter (optional)
 * @returns Timeline data array
 */
export async function queryTimelineData(
  db: Database,
  stepId: number,
  categoryName?: string,
  subCategoryName?: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryTimelineData(stepId, categoryName, subCategoryName);
  return executeQueryWithParams(db, sql, params);
}

/**
 * Query records at a specific time point
 * @param db - Database instance
 * @param stepId - Step id
 * @param relativeTs - Time point (in 10ms units)
 * @returns Records array at the specified time point
 */
export async function queryRecordsAtTimePoint(
  db: Database,
  stepId: number,
  relativeTs: number
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryRecordsAtTimePoint(stepId, relativeTs);
  return executeQueryWithParams(db, sql, params);
}

/**
 * Query records up to a specified timestamp (inclusive) with optional category filters
 * @param db - Database instance
 * @param stepId - Step id
 * @param relativeTsUpperBound - Upper bound for relative timestamp (nanoseconds)
 * @param categoryName - Category filter (optional)
 * @param subCategoryName - Subcategory filter (optional)
 * @returns Matching records ordered by relativeTs
 */
export async function queryRecordsUpToTime(
  db: Database,
  stepId: number,
  relativeTsUpperBound: number,
  categoryName?: string,
  subCategoryName?: string
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryRecordsUpToTime(stepId, relativeTsUpperBound, categoryName, subCategoryName);
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

/**
 * Query category statistics
 * @param db - Database instance
 * @param stepId - Step id
 * @param relativeTs - Time point filter (optional, null means all time)
 * @returns Category statistics array
 */
export async function queryCategoryStats(
  db: Database,
  stepId: number,
  relativeTs?: number | null
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQueryCategoryStats(stepId, relativeTs);
  return executeQueryWithParams(db, sql, params);
}

/**
 * Query sub-category statistics
 * @param db - Database instance
 * @param stepId - Step id
 * @param categoryName - Category name filter
 * @param relativeTs - Time point filter (optional, null means all time)
 * @returns Sub-category statistics array
 */
export async function querySubCategoryStats(
  db: Database,
  stepId: number,
  categoryName: string,
  relativeTs?: number | null
): Promise<SqlRow[]> {
  const { sql, params } = MemoryDao.buildQuerySubCategoryStats(stepId, categoryName, relativeTs);
  return executeQueryWithParams(db, sql, params);
}
