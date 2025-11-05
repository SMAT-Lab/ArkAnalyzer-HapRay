/**
 * SQLite Worker API - 统一入口
 * 提供便捷的 API 来操作数据库，整合了 Client、Dao 层
 */

import { DbClient } from '../db/client/dbClient';
import type { MemoryRecordByComponent } from '../db/dao/memoryDao';

/**
 * 数据库 API 类
 * 整合了数据库客户端和数据访问对象
 */
export class DbApi {
  private client: DbClient;

  constructor() {
    this.client = new DbClient();
  }

  /**
   * 初始化 Worker
   * @param dbDataBase64 - base64 编码的 gzip 压缩的数据库文件（可选，从 window.dbData 读取）
   * @param wasmBase64 - WASM 文件的 base64 编码（可选，从 window.__sqlWasmBase64 读取）
   */
  async init(dbDataBase64?: string, wasmBase64?: string): Promise<void> {
    await this.client.init(dbDataBase64, wasmBase64);
  }

  /**
   * 执行 SQL 语句（不返回结果）
   * @param sql - SQL 语句
   * @param params - 参数数组（可选）
   */
  async exec(sql: string, params?: any[]): Promise<void> {
    await this.client.exec(sql, params);
  }

  /**
   * 查询 SQL 语句（返回结果）
   * @param sql - SQL 查询语句
   * @param params - 参数数组（可选）
   * @returns 查询结果数组
   */
  async query(sql: string, params?: any[]): Promise<any[]> {
    return await this.client.query(sql, params);
  }

  /**
   * 查询 memory_records 表，按 componentName 和 relativeTs 分组统计 heapSize
   * 新流程：直接向 Worker 发送内置业务消息，由 Worker 调用 Dao 并执行 SQLite
   */
  async queryMemoryRecordsByComponent(stepName?: string): Promise<MemoryRecordByComponent[]> {
    return await this.client.request<MemoryRecordByComponent[]>('memory.queryByComponent', { stepName });
  }

  /**
   * 查询 memory_records 表的所有记录（可选过滤）
   * 
   * @param stepName - 步骤名称（可选，用于过滤特定步骤）
   * @param limit - 限制返回的记录数（可选）
   * @returns 查询结果数组
   */
  async queryMemoryRecords(stepName?: string, limit?: number): Promise<any[]> {
    return await this.client.request<any[]>('memory.queryRecords', { stepName, limit });
  }

  /**
   * 查询 memory_results 表的汇总信息
   * 
   * @param stepName - 步骤名称（可选，用于过滤特定步骤）
   * @returns 查询结果数组
   */
  async queryMemoryResults(stepName?: string): Promise<any[]> {
    return await this.client.request<any[]>('memory.queryResults', { stepName });
  }

  /**
   * 关闭数据库和 Worker
   */
  async close(): Promise<void> {
    await this.client.close();
  }
}

// 导出单例实例
let dbApiInstance: DbApi | null = null;

/**
 * 获取 DbApi 实例（单例模式）
 */
export function getDbApi(): DbApi {
  if (!dbApiInstance) {
    dbApiInstance = new DbApi();
  }
  return dbApiInstance;
}

/**
 * 初始化数据库（便捷函数）
 * @param dbDataBase64 - base64 编码的 gzip 压缩的数据库文件（可选）
 * @param wasmBase64 - WASM 文件的 base64 编码（可选）
 */
export async function initDb(dbDataBase64?: string, wasmBase64?: string): Promise<DbApi> {
  const api = getDbApi();
  await api.init(dbDataBase64, wasmBase64);
  return api;
}

