/**
 * Memory Data Access Object (DAO)
 * Defines memory-related database query methods and SQL construction logic
 *
 * Responsibilities: Define SQL query strings, provide data access interfaces
 */

/**
 * SQL query parameter type
 */
type SqlParam = string | number | null;

/**
 * SQL query result row type
 */
type SqlRow = Record<string, unknown>;

/**
 * Memory record query result grouped by component
 */
export interface MemoryRecordByComponent {
  componentName: string | null;
  relativeTs: number;
  totalHeapSize: number;
}

/**
 * Query result with SQL and parameters
 */
interface QueryResult {
  sql: string;
  params: SqlParam[];
}

/**
 * Memory DAO class
 * Defines memory-related data access methods
 */
export class MemoryDao {
  /**
   * Build SQL query for memory_records table (grouped by componentName and relativeTs, aggregated by heapSize)
   *
   * @param stepId - Step id (optional, for filtering specific step)
   * @returns SQL statement and parameters
   */
  static buildQueryMemoryRecordsByComponent(stepId?: number): QueryResult {
    let sql = `
      SELECT 
        componentName,
        relativeTs,
        SUM(heapSize) as totalHeapSize
      FROM memory_records
    `;
    const params: SqlParam[] = [];

    if (stepId) {
      sql += ' WHERE step_id = ?';
      params.push(stepId);
    }

    sql += ' GROUP BY componentName, relativeTs ORDER BY relativeTs, componentName';

    return { sql, params };
  }

  /**
   * Format query result data
   *
   * @param results - Raw query results
   * @returns Formatted data
   */
  static formatMemoryRecordsByComponent(results: SqlRow[]): MemoryRecordByComponent[] {
    return results.map((row: SqlRow) => ({
      componentName: (typeof row.componentName === 'string' ? row.componentName : null),
      relativeTs: Number(row.relativeTs) || 0,
      totalHeapSize: Number(row.totalHeapSize) || 0,
    }));
  }

  /**
   * Build SQL query for all records in memory_records table
   *
   * @param stepId - Step id (optional, for filtering specific step)
   * @param limit - Limit number of returned records (optional)
   * @returns SQL statement and parameters
   */
  static buildQueryMemoryRecords(stepId?: number, limit?: number): QueryResult {
    let sql = 'SELECT * FROM memory_records';
    const params: SqlParam[] = [];

    if (stepId !== undefined && stepId !== null) {
      sql += ' WHERE step_id = ?';
      params.push(stepId);
    }

    sql += ' ORDER BY relativeTs';

    if (limit !== undefined && limit !== null) {
      sql += ' LIMIT ?';
      params.push(limit);
    }

    return { sql, params };
  }

  /**
   * Build SQL query for memory_results table
   *
   * @param stepId - Step id (optional, for filtering specific step)
   * @returns SQL statement and parameters
   */
  static buildQueryMemoryResults(stepId?: number): QueryResult {
    let sql = 'SELECT * FROM memory_results';
    const params: SqlParam[] = [];

    if (stepId !== undefined && stepId !== null) {
      sql += ' WHERE step_id = ?';
      params.push(stepId);
    }

    sql += ' ORDER BY step_id';

    return { sql, params };
  }
}
