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
   * Build SQL query for overview level (aggregated timeline data for total and categories)
   * 查询总览层级数据：返回聚合后的时间线数据（总内存 + 各大类）
   * 包含事件详情用于 tooltip 显示
   *
   * @param stepId - Step id
   * @param groupBy - Group by field: 'category' or 'process'
   * @returns SQL statement and parameters
   */
  static buildQueryOverviewTimeline(stepId: number, groupBy: 'category' | 'process' = 'category'): QueryResult {
    const groupField = groupBy === 'process' ? 'process' : 'categoryName';
    const sql = `
      SELECT
        CAST(relativeTs / 10000000 AS INTEGER) as timePoint10ms,
        ${groupField} as groupName,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE -heapSize END) as netSize,
        COUNT(*) as eventCount,
        GROUP_CONCAT(eventType || ':' || heapSize, '|') as eventDetails
      FROM memory_records
      WHERE step_id = ?
      GROUP BY timePoint10ms, ${groupField}
      ORDER BY timePoint10ms, ${groupField}
    `;
    const params: SqlParam[] = [stepId];
    return { sql, params };
  }

  /**
   * Build SQL query for category level (aggregated by subcategory and time)
   * 查询大类层级数据：按小类和时间聚合
   *
   * @param stepId - Step id
   * @param categoryName - Category name
   * @returns SQL statement and parameters
   */
  static buildQueryCategoryRecords(stepId: number, categoryName: string): QueryResult {
    const sql = `
      SELECT
        CAST(relativeTs / 10000000 AS INTEGER) as timePoint10ms,
        subCategoryName,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE -heapSize END) as netSize,
        COUNT(*) as eventCount,
        GROUP_CONCAT(eventType || ':' || heapSize, '|') as eventDetails
      FROM memory_records
      WHERE step_id = ? AND categoryName = ?
      GROUP BY timePoint10ms, subCategoryName
      ORDER BY timePoint10ms, subCategoryName
    `;
    const params: SqlParam[] = [stepId, categoryName];
    return { sql, params };
  }

  /**
   * Build SQL query for subcategory level (records of a specific subcategory)
   * 查询小类层级数据：返回指定小类的所有记录
   *
   * @param stepId - Step id
   * @param categoryName - Category name
   * @param subCategoryName - Subcategory name
   * @returns SQL statement and parameters
   */
  static buildQuerySubCategoryRecords(
    stepId: number,
    categoryName: string,
    subCategoryName: string
  ): QueryResult {
    const sql = `
      SELECT *
      FROM memory_records
      WHERE step_id = ? AND categoryName = ? AND subCategoryName = ?
      ORDER BY relativeTs
    `;
    const params: SqlParam[] = [stepId, categoryName, subCategoryName];
    return { sql, params };
  }

  /**
   * Build SQL query to get all unique categories for a step
   * 查询步骤的所有大类名称
   *
   * @param stepId - Step id
   * @returns SQL statement and parameters
   */
  static buildQueryCategories(stepId: number): QueryResult {
    const sql = `
      SELECT DISTINCT categoryName
      FROM memory_records
      WHERE step_id = ? AND categoryName != 'UNKNOWN'
      ORDER BY categoryName
    `;
    const params: SqlParam[] = [stepId];
    return { sql, params };
  }

  /**
   * Build SQL query for process level (aggregated by thread and time)
   * 查询进程层级数据：按线程和时间聚合
   *
   * @param stepId - Step id
   * @param processName - Process name
   * @returns SQL statement and parameters
   */
  static buildQueryProcessRecords(stepId: number, processName: string): QueryResult {
    const sql = `
      SELECT
        CAST(relativeTs / 10000000 AS INTEGER) as timePoint10ms,
        thread,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE -heapSize END) as netSize,
        COUNT(*) as eventCount,
        GROUP_CONCAT(eventType || ':' || heapSize, '|') as eventDetails
      FROM memory_records
      WHERE step_id = ? AND process = ?
      GROUP BY timePoint10ms, thread
      ORDER BY timePoint10ms, thread
    `;
    const params: SqlParam[] = [stepId, processName];
    return { sql, params };
  }

  /**
   * Build SQL query for thread level (aggregated by file and time)
   * 查询线程层级数据：按文件和时间聚合
   *
   * @param stepId - Step id
   * @param processName - Process name
   * @param threadName - Thread name
   * @returns SQL statement and parameters
   */
  static buildQueryThreadRecords(
    stepId: number,
    processName: string,
    threadName: string
  ): QueryResult {
    const sql = `
      SELECT *
      FROM memory_records
      WHERE step_id = ? AND process = ? AND thread = ?
      ORDER BY relativeTs
    `;
    const params: SqlParam[] = [stepId, processName, threadName];
    return { sql, params };
  }

  /**
   * Build SQL query for file level (records of a specific file in a thread)
   * 查询文件层级数据：返回指定文件的所有记录
   *
   * @param stepId - Step id
   * @param processName - Process name
   * @param threadName - Thread name
   * @param fileName - File name
   * @returns SQL statement and parameters
   */
  static buildQueryFileRecords(
    stepId: number,
    processName: string,
    threadName: string,
    fileName: string
  ): QueryResult {
    const sql = `
      SELECT *
      FROM memory_records
      WHERE step_id = ? AND process = ? AND thread = ? AND file LIKE ?
      ORDER BY relativeTs
    `;
    const params: SqlParam[] = [stepId, processName, threadName, `%${fileName}`];
    return { sql, params };
  }

  /**
   * Build SQL query to get all unique subcategories for a category
   * 查询大类的所有小类名称
   *
   * @param stepId - Step id
   * @param categoryName - Category name
   * @returns SQL statement and parameters
   */
  static buildQuerySubCategories(stepId: number, categoryName: string): QueryResult {
    const sql = `
      SELECT DISTINCT subCategoryName
      FROM memory_records
      WHERE step_id = ? AND categoryName = ?
      ORDER BY subCategoryName
    `;
    const params: SqlParam[] = [stepId, categoryName];
    return { sql, params };
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

  /**
   * Build SQL query for timeline data (aggregated by time point)
   * Groups records by relativeTs (in 10ms units) and calculates cumulative memory
   *
   * Note: relativeTs in database is in nanoseconds, we convert to 10ms units (0.01 seconds)
   * Conversion: nanoseconds / 10,000,000 = 10ms units
   *
   * @param stepId - Step id
   * @param categoryName - Category name filter (optional)
   * @param subCategoryName - Sub-category name filter (optional)
   * @returns SQL statement and parameters
   */
  static buildQueryTimelineData(
    stepId: number,
    categoryName?: string,
    subCategoryName?: string
  ): QueryResult {
    let sql = `
      SELECT
        CAST(relativeTs / 10000000 AS INTEGER) as timePoint10ms,
        COUNT(*) as eventCount,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN 1 ELSE 0 END) as allocCount,
        SUM(CASE WHEN eventType IN ('FreeEvent', 'MunmapEvent') THEN 1 ELSE 0 END) as freeCount,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE -heapSize END) as netSize
      FROM memory_records
      WHERE step_id = ?
    `;
    const params: SqlParam[] = [stepId];

    if (categoryName) {
      sql += ' AND categoryName = ?';
      params.push(categoryName);
    }

    if (subCategoryName) {
      sql += ' AND subCategoryName = ?';
      params.push(subCategoryName);
    }

    sql += ' GROUP BY timePoint10ms ORDER BY timePoint10ms';

    return { sql, params };
  }

  /**
   * Build SQL query for records at a specific time point
   *
   * @param stepId - Step id
   * @param timePoint10ms - Time point in 10ms units (0.01 seconds)
   * @returns SQL statement and parameters
   */
  static buildQueryRecordsAtTimePoint(stepId: number, timePoint10ms: number): QueryResult {
    // Convert 10ms units back to nanoseconds for database query
    // timePoint10ms * 10,000,000 = nanoseconds
    const minNs = timePoint10ms * 10000000;
    const maxNs = (timePoint10ms + 1) * 10000000;

    const sql = `
      SELECT * FROM memory_records
      WHERE step_id = ? AND relativeTs >= ? AND relativeTs < ?
      ORDER BY relativeTs, eventType, heapSize DESC
    `;
    const params: SqlParam[] = [stepId, minNs, maxNs];

    return { sql, params };
  }

  /**
   * Build SQL query for records up to specific timestamp with optional filters
   *
   * @param stepId - Step id
   * @param relativeTsUpperBound - Upper bound (inclusive) for relative timestamp in nanoseconds
   * @param categoryName - Optional category filter
   * @param subCategoryName - Optional sub-category filter
   * @returns SQL statement and parameters
   */
  static buildQueryRecordsUpToTime(
    stepId: number,
    relativeTsUpperBound: number,
    categoryName?: string,
    subCategoryName?: string
  ): QueryResult {
    let sql = `
      SELECT *
      FROM memory_records
      WHERE step_id = ? AND relativeTs <= ?
    `;
    const params: SqlParam[] = [stepId, relativeTsUpperBound];

    if (categoryName) {
      sql += ' AND categoryName = ?';
      params.push(categoryName);
    }

    if (subCategoryName) {
      sql += ' AND subCategoryName = ?';
      params.push(subCategoryName);
    }

    sql += ' ORDER BY relativeTs';

    return { sql, params };
  }

  /**
   * Build SQL query for callchain frames of specified callchain ids
   *
   * @param stepId - Step id
   * @param callchainIds - List of callchain ids
   * @returns SQL statement and parameters
   */
  static buildQueryCallchainFrames(stepId: number, callchainIds: number[]): QueryResult {
    if (!callchainIds.length) {
      return {
        sql: `
          SELECT callchainId, depth, ip, symbolId, symbol, fileId, file, offset, symbolOffset, vaddr
          FROM memory_callchains
          WHERE 1 = 0
        `,
        params: [],
      };
    }

    const placeholders = callchainIds.map(() => '?').join(', ');
    const sql = `
      SELECT callchainId, depth, ip, symbolId, symbol, fileId, file, offset, symbolOffset, vaddr
      FROM memory_callchains
      WHERE step_id = ? AND callchainId IN (${placeholders})
      ORDER BY callchainId, depth
    `;
    const params: SqlParam[] = [stepId, ...callchainIds];

    return { sql, params };
  }

  /**
   * Build SQL query for category statistics
   *
   * @param stepId - Step id
   * @param relativeTs - Time point filter (optional, null means all time)
   * @returns SQL statement and parameters
   */
  static buildQueryCategoryStats(stepId: number, relativeTs?: number | null): QueryResult {
    let sql = `
      SELECT
        categoryName,
        COUNT(*) as eventCount,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE 0 END) as allocSize,
        SUM(CASE WHEN eventType IN ('FreeEvent', 'MunmapEvent') THEN heapSize ELSE 0 END) as freeSize,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE -heapSize END) as netSize
      FROM memory_records
      WHERE step_id = ?
    `;
    const params: SqlParam[] = [stepId];

    if (relativeTs !== undefined && relativeTs !== null) {
      sql += ' AND relativeTs <= ?';
      params.push(relativeTs);
    }

    sql += ' GROUP BY categoryName ORDER BY netSize DESC';

    return { sql, params };
  }

  /**
   * Build SQL query for sub-category statistics
   *
   * @param stepId - Step id
   * @param categoryName - Category name filter
   * @param relativeTs - Time point filter (optional, null means all time)
   * @returns SQL statement and parameters
   */
  static buildQuerySubCategoryStats(
    stepId: number,
    categoryName: string,
    relativeTs?: number | null
  ): QueryResult {
    let sql = `
      SELECT
        subCategoryName,
        COUNT(*) as eventCount,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE 0 END) as allocSize,
        SUM(CASE WHEN eventType IN ('FreeEvent', 'MunmapEvent') THEN heapSize ELSE 0 END) as freeSize,
        SUM(CASE WHEN eventType IN ('AllocEvent', 'MmapEvent') THEN heapSize ELSE -heapSize END) as netSize
      FROM memory_records
      WHERE step_id = ? AND categoryName = ?
    `;
    const params: SqlParam[] = [stepId, categoryName];

    if (relativeTs !== undefined && relativeTs !== null) {
      sql += ' AND relativeTs <= ?';
      params.push(relativeTs);
    }

    sql += ' GROUP BY subCategoryName ORDER BY netSize DESC';

    return { sql, params };
  }
}
