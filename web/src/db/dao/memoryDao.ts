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
   * Build SQL query for overview level (aggregated timeline data for total and categories)
   * 查询总览层级数据：返回聚合后的时间线数据（总内存 + 各大类）
   * 包含事件详情用于 tooltip 显示
   *
   * @param stepId - Step id
   * @param groupBy - Group by field: 'category' or 'process'
   * @returns SQL statement and parameters
   */
  static buildQueryOverviewTimeline(stepId: number, groupBy: 'category' | 'process' = 'category'): QueryResult {
    const isProcessGroup = groupBy === 'process';
    const groupFieldId = isProcessGroup ? 'processId' : 'categoryNameId';
    const groupDictAlias = isProcessGroup ? 'proc_dict' : 'category_dict';
    
    const sql = `
      SELECT
        (raw.relativeTs / 10000000) as timePoint10ms,
        ${groupDictAlias}.value as groupName,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS ${groupDictAlias}
        ON raw.${groupFieldId} = ${groupDictAlias}.dictId AND ${groupDictAlias}.step_id = raw.step_id
      WHERE raw.step_id = ?
      GROUP BY timePoint10ms, ${groupDictAlias}.value
      ORDER BY timePoint10ms, ${groupDictAlias}.value
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
        (raw.relativeTs / 10000000) as timePoint10ms,
        sub_category_dict.value as subCategoryName,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND category_dict.value = ?
      GROUP BY timePoint10ms, sub_category_dict.value
      ORDER BY timePoint10ms, sub_category_dict.value
    `;
    const params: SqlParam[] = [stepId, categoryName];
    return { sql, params };
  }

  /**
   * Build SQL query for subcategory level (aggregated by component and time)
   * 查询小类层级数据：按组件和时间聚合，返回指定小类下所有组件的记录
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
      SELECT
        (raw.relativeTs / 10000000) as timePoint10ms,
        file_dict.value as file,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND category_dict.value = ? AND sub_category_dict.value = ?
      GROUP BY timePoint10ms, file_dict.value
      ORDER BY timePoint10ms, file_dict.value
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
      SELECT DISTINCT category_dict.value AS categoryName
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND category_dict.value != 'UNKNOWN'
      ORDER BY category_dict.value
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
        (raw.relativeTs / 10000000) as timePoint10ms,
        thread_dict.value as thread,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS proc_dict
        ON raw.processId = proc_dict.dictId AND proc_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS thread_dict
        ON raw.threadId = thread_dict.dictId AND thread_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND proc_dict.value = ?
      GROUP BY timePoint10ms, thread_dict.value
      ORDER BY timePoint10ms, thread_dict.value
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
      SELECT
        (raw.relativeTs / 10000000) as timePoint10ms,
        file_dict.value as file,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS proc_dict
        ON raw.processId = proc_dict.dictId AND proc_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS thread_dict
        ON raw.threadId = thread_dict.dictId AND thread_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND proc_dict.value = ? AND thread_dict.value = ?
      GROUP BY timePoint10ms, file_dict.value
      ORDER BY timePoint10ms, file_dict.value
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
      SELECT
        (raw.relativeTs / 10000000) as timePoint10ms,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS proc_dict
        ON raw.processId = proc_dict.dictId AND proc_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS thread_dict
        ON raw.threadId = thread_dict.dictId AND thread_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND proc_dict.value = ? AND thread_dict.value = ? AND file_dict.value LIKE ?
      GROUP BY timePoint10ms
      ORDER BY timePoint10ms
    `;
    const params: SqlParam[] = [stepId, processName, threadName, `%${fileName}`];
    return { sql, params };
  }

  /**
   * Build SQL query for file level event type aggregation (category mode)
   * 查询文件层级事件类型数据：按事件类型和时间聚合（分类模式）
   *
   * @param stepId - Step id
   * @param categoryName - Category name
   * @param subCategoryName - Subcategory name
   * @param fileName - File name
   * @returns SQL statement and parameters
   */
  static buildQueryFileEventTypeRecords(
    stepId: number,
    categoryName: string,
    subCategoryName: string,
    fileName: string
  ): QueryResult {
    const sql = `
      SELECT
        (raw.relativeTs / 10000000) as timePoint10ms,
        event_dict.value as eventType,
        sub_event_dict.value as subEventType,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS event_dict
        ON raw.eventTypeId = event_dict.dictId AND event_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_event_dict
        ON raw.subEventTypeId = sub_event_dict.dictId AND sub_event_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND category_dict.value = ? AND sub_category_dict.value = ? AND file_dict.value LIKE ?
      GROUP BY timePoint10ms, event_dict.value, sub_event_dict.value
      ORDER BY timePoint10ms, event_dict.value, sub_event_dict.value
    `;
    const params: SqlParam[] = [stepId, categoryName, subCategoryName, `%${fileName}`];
    return { sql, params };
  }

  /**
   * Build SQL query for file level event type aggregation (process mode)
   * 查询文件层级事件类型数据：按事件类型和时间聚合（进程模式）
   *
   * @param stepId - Step id
   * @param processName - Process name
   * @param threadName - Thread name
   * @param fileName - File name
   * @returns SQL statement and parameters
   */
  static buildQueryFileEventTypeRecordsForProcess(
    stepId: number,
    processName: string,
    threadName: string,
    fileName: string
  ): QueryResult {
    const sql = `
      SELECT
        (raw.relativeTs / 10000000) as timePoint10ms,
        event_dict.value as eventType,
        sub_event_dict.value as subEventType,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS proc_dict
        ON raw.processId = proc_dict.dictId AND proc_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS thread_dict
        ON raw.threadId = thread_dict.dictId AND thread_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS event_dict
        ON raw.eventTypeId = event_dict.dictId AND event_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_event_dict
        ON raw.subEventTypeId = sub_event_dict.dictId AND sub_event_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND proc_dict.value = ? AND thread_dict.value = ? AND file_dict.value LIKE ?
      GROUP BY timePoint10ms, event_dict.value, sub_event_dict.value
      ORDER BY timePoint10ms, event_dict.value, sub_event_dict.value
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
      SELECT DISTINCT sub_category_dict.value AS subCategoryName
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND category_dict.value = ?
      ORDER BY sub_category_dict.value
    `;
    const params: SqlParam[] = [stepId, categoryName];
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
   * Build SQL query for records up to specific timestamp with category filters
   * Used for category view mode
   *
   * @param stepId - Step id
   * @param relativeTsUpperBound - Upper bound (inclusive) for relative timestamp in nanoseconds
   * @param categoryName - Optional category filter
   * @param subCategoryName - Optional sub-category filter
   * @param fileName - Optional file name filter (supports LIKE pattern matching)
   * @returns SQL statement and parameters
   */
  static buildQueryRecordsUpToTimeByCategory(
    stepId: number,
    relativeTsUpperBound: number,
    categoryName?: string,
    subCategoryName?: string,
    fileName?: string
  ): QueryResult {
    let sql = `
      SELECT
        raw.fileId AS fileId,
        file_dict.value AS file,
        event_dict.value AS eventType,
        raw.addr AS addr,
        raw.callchainId AS callchainId,
        raw.heapSize AS heapSize,
        raw.relativeTs AS relativeTs,
        comp_name_dict.value AS componentName,
        raw.componentCategory AS componentCategory,
        category_dict.value AS categoryName,
        sub_category_dict.value AS subCategoryName
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS event_dict
        ON raw.eventTypeId = event_dict.dictId AND event_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS comp_name_dict
        ON raw.componentNameId = comp_name_dict.dictId AND comp_name_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      WHERE raw.step_id = ? AND raw.relativeTs <= ?
    `;
    const params: SqlParam[] = [stepId, relativeTsUpperBound];

    if (categoryName) {
      sql += ' AND category_dict.value = ?';
      params.push(categoryName);
    }

    if (subCategoryName) {
      sql += ' AND sub_category_dict.value = ?';
      params.push(subCategoryName);
    }

    if (fileName) {
      sql += ' AND file_dict.value LIKE ?';
      params.push(`%${fileName}`);
    }

    sql += ' ORDER BY raw.relativeTs';

    return { sql, params };
  }

  /**
   * Build SQL query for records up to specific timestamp with process/thread filters
   * Used for process view mode
   *
   * @param stepId - Step id
   * @param relativeTsUpperBound - Upper bound (inclusive) for relative timestamp in nanoseconds
   * @param processName - Optional process name filter
   * @param threadName - Optional thread name filter
   * @param fileName - Optional file name filter (supports LIKE pattern matching)
   * @returns SQL statement and parameters
   */
  static buildQueryRecordsUpToTimeByProcess(
    stepId: number,
    relativeTsUpperBound: number,
    processName?: string,
    threadName?: string,
    fileName?: string
  ): QueryResult {
    let sql = `
      SELECT
        raw.pid AS pid,
        proc_dict.value AS process,
        raw.tid AS tid,
        thread_dict.value AS thread,
        raw.fileId AS fileId,
        file_dict.value AS file,
        event_dict.value AS eventType,
        raw.addr AS addr,
        raw.callchainId AS callchainId,
        raw.heapSize AS heapSize,
        raw.relativeTs AS relativeTs
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS proc_dict
        ON raw.processId = proc_dict.dictId AND proc_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS thread_dict
        ON raw.threadId = thread_dict.dictId AND thread_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS event_dict
        ON raw.eventTypeId = event_dict.dictId AND event_dict.step_id = raw.step_id

      WHERE raw.step_id = ? AND raw.relativeTs <= ?
    `;
    const params: SqlParam[] = [stepId, relativeTsUpperBound];

    if (processName) {
      sql += ' AND proc_dict.value = ?';
      params.push(processName);
    }

    if (threadName) {
      sql += ' AND thread_dict.value = ?';
      params.push(threadName);
    }

    if (fileName) {
      sql += ' AND file_dict.value LIKE ?';
      params.push(`%${fileName}`);
    }

    sql += ' ORDER BY raw.relativeTs';

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

}
