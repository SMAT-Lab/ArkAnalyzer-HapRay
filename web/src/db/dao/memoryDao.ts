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

  /**
   * Build SQL query for memory meminfo data
   * 查询内存meminfo数据
   *
   * @param stepId - Step id
   * @returns SQL statement and parameters
   */
  static buildQueryMemoryMeminfo(stepId: number): QueryResult {
    const sql = `
      SELECT timestamp, timestamp_epoch, data
      FROM memory_meminfo
      WHERE step_id = ?
      ORDER BY timestamp_epoch
    `;
    const params: SqlParam[] = [stepId];
    return { sql, params };
  }

  /**
   * Build SQL query for meminfo data of all steps (for summary page)
   * 查询所有步骤的一级内存数据（用于汇总展示）
   *
   * @returns SQL statement and parameters
   */
  static buildQueryMemoryMeminfoAll(): QueryResult {
    const sql = `
      SELECT step_id, timestamp, timestamp_epoch, data
      FROM memory_meminfo
      ORDER BY step_id, timestamp_epoch
    `;
    const params: SqlParam[] = [];
    return { sql, params };
  }

  /**
   * Build SQL query for net native memory timeline aggregated by step and time bucket (for summary page)
   * 按步骤和时间桶聚合 native 内存净变化（申请为正、释放为负），用于汇总展示。
   * 前端对每个步骤按时间顺序累加即可得到净内存曲线、峰值与结束未释放内存。
   *
   * @returns SQL statement and parameters
   */
  static buildQueryNetMemoryTimelineAll(): QueryResult {
    const sql = `
      SELECT
        step_id,
        (relativeTs / 10000000) as timePoint10ms,
        SUM(heapSize) as netSize,
        COUNT(*) as eventCount
      FROM memory_records
      GROUP BY step_id, timePoint10ms
      ORDER BY step_id, timePoint10ms
    `;
    const params: SqlParam[] = [];
    return { sql, params };
  }

  /**
   * Build SQL query for overview level timeline of all steps (for summary page)
   * 查询所有步骤的总览时间线数据（按步骤、时间桶、大类/进程聚合），用于汇总展示。
   *
   * @param groupBy - Group by field: 'category' or 'process'
   * @returns SQL statement and parameters
   */
  static buildQueryOverviewTimelineAll(groupBy: 'category' | 'process' = 'category'): QueryResult {
    const isProcessGroup = groupBy === 'process';
    const groupFieldId = isProcessGroup ? 'processId' : 'categoryNameId';
    const groupDictAlias = isProcessGroup ? 'proc_dict' : 'category_dict';

    const sql = `
      SELECT
        raw.step_id as step_id,
        (raw.relativeTs / 10000000) as timePoint10ms,
        ${groupDictAlias}.value as groupName,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS ${groupDictAlias}
        ON raw.${groupFieldId} = ${groupDictAlias}.dictId AND ${groupDictAlias}.step_id = raw.step_id
      GROUP BY raw.step_id, timePoint10ms, ${groupDictAlias}.value
      ORDER BY raw.step_id, timePoint10ms, ${groupDictAlias}.value
    `;
    const params: SqlParam[] = [];
    return { sql, params };
  }

  /**
   * Build SQL query for category level records of all steps (for summary page)
   * 查询所有步骤中指定大类的数据（按步骤、时间桶、小类聚合）
   *
   * @param categoryName - Category name
   * @returns SQL statement and parameters
   */
  static buildQueryCategoryRecordsAll(categoryName: string): QueryResult {
    const sql = `
      SELECT
        raw.step_id as step_id,
        (raw.relativeTs / 10000000) as timePoint10ms,
        sub_category_dict.value as subCategoryName,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      WHERE category_dict.value = ?
      GROUP BY raw.step_id, timePoint10ms, sub_category_dict.value
      ORDER BY raw.step_id, timePoint10ms, sub_category_dict.value
    `;
    const params: SqlParam[] = [categoryName];
    return { sql, params };
  }

  /**
   * Build SQL query for subcategory level records of all steps (for summary page)
   * 查询所有步骤中指定小类的数据（按步骤、时间桶、文件聚合）
   *
   * @param categoryName - Category name
   * @param subCategoryName - Subcategory name
   * @returns SQL statement and parameters
   */
  static buildQuerySubCategoryRecordsAll(categoryName: string, subCategoryName: string): QueryResult {
    const sql = `
      SELECT
        raw.step_id as step_id,
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
      WHERE category_dict.value = ? AND sub_category_dict.value = ?
      GROUP BY raw.step_id, timePoint10ms, file_dict.value
      ORDER BY raw.step_id, timePoint10ms, file_dict.value
    `;
    const params: SqlParam[] = [categoryName, subCategoryName];
    return { sql, params };
  }

  /**
   * Build SQL query for file level event type records of all steps, category mode (for summary page)
   * 查询所有步骤中指定文件的事件类型数据（分类模式）
   *
   * @param categoryName - Category name
   * @param subCategoryName - Subcategory name
   * @param fileName - File name
   * @returns SQL statement and parameters
   */
  static buildQueryFileEventTypeRecordsAll(
    categoryName: string,
    subCategoryName: string,
    fileName: string
  ): QueryResult {
    const sql = `
      SELECT
        raw.step_id as step_id,
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
      WHERE category_dict.value = ? AND sub_category_dict.value = ? AND file_dict.value LIKE ?
      GROUP BY raw.step_id, timePoint10ms, event_dict.value, sub_event_dict.value
      ORDER BY raw.step_id, timePoint10ms, event_dict.value, sub_event_dict.value
    `;
    const params: SqlParam[] = [categoryName, subCategoryName, `%${fileName}`];
    return { sql, params };
  }

  /**
   * Build SQL query for process level records of all steps (for summary page)
   * 查询所有步骤中指定进程的数据（按步骤、时间桶、线程聚合）
   *
   * @param processName - Process name
   * @returns SQL statement and parameters
   */
  static buildQueryProcessRecordsAll(processName: string): QueryResult {
    const sql = `
      SELECT
        raw.step_id as step_id,
        (raw.relativeTs / 10000000) as timePoint10ms,
        thread_dict.value as thread,
        SUM(raw.heapSize) as netSize
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS proc_dict
        ON raw.processId = proc_dict.dictId AND proc_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS thread_dict
        ON raw.threadId = thread_dict.dictId AND thread_dict.step_id = raw.step_id
      WHERE proc_dict.value = ?
      GROUP BY raw.step_id, timePoint10ms, thread_dict.value
      ORDER BY raw.step_id, timePoint10ms, thread_dict.value
    `;
    const params: SqlParam[] = [processName];
    return { sql, params };
  }

  /**
   * Build SQL query for thread level records of all steps (for summary page)
   * 查询所有步骤中指定线程的数据（按步骤、时间桶、文件聚合）
   *
   * @param processName - Process name
   * @param threadName - Thread name
   * @returns SQL statement and parameters
   */
  static buildQueryThreadRecordsAll(processName: string, threadName: string): QueryResult {
    const sql = `
      SELECT
        raw.step_id as step_id,
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
      WHERE proc_dict.value = ? AND thread_dict.value = ?
      GROUP BY raw.step_id, timePoint10ms, file_dict.value
      ORDER BY raw.step_id, timePoint10ms, file_dict.value
    `;
    const params: SqlParam[] = [processName, threadName];
    return { sql, params };
  }

  /**
   * Build SQL query for file level event type records of all steps, process mode (for summary page)
   * 查询所有步骤中指定文件的事件类型数据（进程模式）
   *
   * @param processName - Process name
   * @param threadName - Thread name
   * @param fileName - File name
   * @returns SQL statement and parameters
   */
  static buildQueryFileEventTypeRecordsForProcessAll(
    processName: string,
    threadName: string,
    fileName: string
  ): QueryResult {
    const sql = `
      SELECT
        raw.step_id as step_id,
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
      WHERE proc_dict.value = ? AND thread_dict.value = ? AND file_dict.value LIKE ?
      GROUP BY raw.step_id, timePoint10ms, event_dict.value, sub_event_dict.value
      ORDER BY raw.step_id, timePoint10ms, event_dict.value, sub_event_dict.value
    `;
    const params: SqlParam[] = [processName, threadName, `%${fileName}`];
    return { sql, params };
  }

  /**
   * Build SQL query for native memory distribution by category across all steps (for summary pie chart)
   * 汇总模式：按大类统计所有步骤的 Native 净内存分布（净内存 = 申请 - 释放）。
   * 传入时间边界时仅统计截至该累计时间点的记录。
   *
   * @param selectedStepId - Optional selected step id (records of previous steps are fully included)
   * @param innerRelativeTs - Optional upper bound (inclusive) of relative timestamp within the selected step (nanoseconds)
   * @returns SQL statement and parameters
   */
  static buildQueryCategoryDistributionAll(
    selectedStepId?: number,
    innerRelativeTs?: number
  ): QueryResult {
    let sql = `
      SELECT
        category_dict.value AS categoryName,
        SUM(raw.heapSize) AS netSize,
        COUNT(*) AS eventCount
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
    `;
    const params: SqlParam[] = [];

    if (selectedStepId != null && innerRelativeTs != null) {
      sql += ' WHERE (raw.step_id < ? OR (raw.step_id = ? AND raw.relativeTs <= ?))';
      params.push(selectedStepId, selectedStepId, innerRelativeTs);
    }

    sql += ' GROUP BY category_dict.value ORDER BY netSize DESC';
    return { sql, params };
  }

  /**
   * Build SQL query for native memory distribution by subcategory (.so files) within a category
   * across all steps (for summary pie chart drill-down)
   * 汇总模式：按小类（.so / 库文件）统计指定大类下所有步骤的 Native 净内存分布。
   * 传入时间边界时仅统计截至该累计时间点的记录。
   *
   * @param categoryName - Category name
   * @param selectedStepId - Optional selected step id (records of previous steps are fully included)
   * @param innerRelativeTs - Optional upper bound (inclusive) of relative timestamp within the selected step (nanoseconds)
   * @returns SQL statement and parameters
   */
  static buildQuerySubCategoryDistributionAll(
    categoryName: string,
    selectedStepId?: number,
    innerRelativeTs?: number
  ): QueryResult {
    let sql = `
      SELECT
        sub_category_dict.value AS subCategoryName,
        SUM(raw.heapSize) AS netSize,
        COUNT(*) AS eventCount
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      WHERE category_dict.value = ?
    `;
    const params: SqlParam[] = [categoryName];

    if (selectedStepId != null && innerRelativeTs != null) {
      sql += ' AND (raw.step_id < ? OR (raw.step_id = ? AND raw.relativeTs <= ?))';
      params.push(selectedStepId, selectedStepId, innerRelativeTs);
    }

    sql += ' GROUP BY sub_category_dict.value ORDER BY netSize DESC';
    return { sql, params };
  }

  /**
   * Build SQL query for records up to a cumulative time point across all steps, with category filters
   * (for summary page flame graph)
   * 汇总模式：查询截至跨步骤累计时间点的所有记录（分类模式）。
   * 累计时间点由 (selectedStepId, innerRelativeTs) 表示：
   * - step_id < selectedStepId 的步骤取全部记录
   * - step_id = selectedStepId 的步骤取 relativeTs <= innerRelativeTs 的记录
   *
   * @param selectedStepId - 选中时间点所属步骤 ID
   * @param innerRelativeTs - 选中时间点在该步骤内的相对时间上界（纳秒，含）
   * @param categoryName - Optional category name filter
   * @param subCategoryName - Optional subcategory name filter
   * @param fileName - Optional file name filter (supports LIKE pattern matching)
   * @returns Matching records ordered by step_id, relativeTs
   */
  static buildQueryRecordsUpToByCategoryAll(
    selectedStepId: number,
    innerRelativeTs: number,
    categoryName?: string,
    subCategoryName?: string,
    fileName?: string
  ): QueryResult {
    let sql = `
      SELECT
        raw.step_id AS step_id,
        raw.pid AS pid,
        raw.tid AS tid,
        raw.fileId AS fileId,
        file_dict.value AS file,
        event_dict.value AS eventType,
        raw.addr AS addr,
        raw.callchainId AS callchainId,
        raw.heapSize AS heapSize,
        raw.relativeTs AS relativeTs,
        category_dict.value AS categoryName,
        sub_category_dict.value AS subCategoryName
      FROM memory_records AS raw
      LEFT JOIN memory_data_dicts AS file_dict
        ON raw.fileId = file_dict.dictId AND file_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS event_dict
        ON raw.eventTypeId = event_dict.dictId AND event_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS category_dict
        ON raw.categoryNameId = category_dict.dictId AND category_dict.step_id = raw.step_id
      LEFT JOIN memory_data_dicts AS sub_category_dict
        ON raw.subCategoryNameId = sub_category_dict.dictId AND sub_category_dict.step_id = raw.step_id
      WHERE (raw.step_id < ? OR (raw.step_id = ? AND raw.relativeTs <= ?))
    `;
    const params: SqlParam[] = [selectedStepId, selectedStepId, innerRelativeTs];

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

    sql += ' ORDER BY raw.step_id, raw.relativeTs';

    return { sql, params };
  }

  /**
   * Build SQL query for records up to a cumulative time point across all steps, with process filters
   * (for summary page flame graph)
   * 汇总模式：查询截至跨步骤累计时间点的所有记录（进程模式）
   *
   * @param selectedStepId - 选中时间点所属步骤 ID
   * @param innerRelativeTs - 选中时间点在该步骤内的相对时间上界（纳秒，含）
   * @param processName - Optional process name filter
   * @param threadName - Optional thread name filter
   * @param fileName - Optional file name filter (supports LIKE pattern matching)
   * @returns Matching records ordered by step_id, relativeTs
   */
  static buildQueryRecordsUpToByProcessAll(
    selectedStepId: number,
    innerRelativeTs: number,
    processName?: string,
    threadName?: string,
    fileName?: string
  ): QueryResult {
    let sql = `
      SELECT
        raw.step_id AS step_id,
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
      WHERE (raw.step_id < ? OR (raw.step_id = ? AND raw.relativeTs <= ?))
    `;
    const params: SqlParam[] = [selectedStepId, selectedStepId, innerRelativeTs];

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

    sql += ' ORDER BY raw.step_id, raw.relativeTs';

    return { sql, params };
  }

}
