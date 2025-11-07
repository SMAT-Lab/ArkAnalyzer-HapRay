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
