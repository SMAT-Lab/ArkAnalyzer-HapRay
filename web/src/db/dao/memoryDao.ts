/**
 * 内存数据访问对象 (DAO)
 * 定义内存相关的数据库查询方法和 SQL 构建逻辑
 * 
 * 职责：定义 SQL 查询字符串，提供数据访问接口
 */

/**
 * 内存记录查询结果
 */
export interface MemoryRecordByComponent {
  componentName: string | null;
  relativeTs: number;
  totalHeapSize: number;
}

/**
 * 内存 DAO 类
 * 定义内存相关的数据访问方法
 */
export class MemoryDao {
  /**
   * 构建查询 memory_records 表的 SQL（按 componentName 和 relativeTs 分组统计 heapSize）
   * 
   * @param stepName - 步骤名称（可选，用于过滤特定步骤）
   * @returns SQL 语句和参数
   */
  static buildQueryMemoryRecordsByComponent(stepName?: string): { sql: string; params: any[] } {
    let sql = `
      SELECT 
        componentName,
        relativeTs,
        SUM(heapSize) as totalHeapSize
      FROM memory_records
    `;
    const params: any[] = [];

    if (stepName) {
      sql += ' WHERE step_name = ?';
      params.push(stepName);
    }

    sql += ' GROUP BY componentName, relativeTs ORDER BY relativeTs, componentName';

    return { sql, params };
  }

  /**
   * 整理查询结果数据
   * 
   * @param results - 原始查询结果
   * @returns 整理后的数据
   */
  static formatMemoryRecordsByComponent(results: any[]): MemoryRecordByComponent[] {
    return results.map((row: any) => ({
      componentName: row.componentName ?? null,
      relativeTs: Number(row.relativeTs) || 0,
      totalHeapSize: Number(row.totalHeapSize) || 0,
    }));
  }

  /**
   * 构建查询 memory_records 表所有记录的 SQL
   * 
   * @param stepName - 步骤名称（可选，用于过滤特定步骤）
   * @param limit - 限制返回的记录数（可选）
   * @returns SQL 语句和参数
   */
  static buildQueryMemoryRecords(stepName?: string, limit?: number): { sql: string; params: any[] } {
    let sql = 'SELECT * FROM memory_records';
    const params: any[] = [];

    if (stepName) {
      sql += ' WHERE step_name = ?';
      params.push(stepName);
    }

    sql += ' ORDER BY relativeTs';

    if (limit) {
      sql += ' LIMIT ?';
      params.push(limit);
    }

    return { sql, params };
  }

  /**
   * 构建查询 memory_results 表的 SQL
   * 
   * @param stepName - 步骤名称（可选，用于过滤特定步骤）
   * @returns SQL 语句和参数
   */
  static buildQueryMemoryResults(stepName?: string): { sql: string; params: any[] } {
    let sql = 'SELECT * FROM memory_results';
    const params: any[] = [];

    if (stepName) {
      sql += ' WHERE step_name = ?';
      params.push(stepName);
    }

    sql += ' ORDER BY step_name';

    return { sql, params };
  }
}

