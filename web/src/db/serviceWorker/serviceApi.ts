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
