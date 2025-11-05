import type { Database } from 'sql.js'
import { MemoryDao } from '../dao/memoryDao'

export async function queryMemoryRecordsByComponent(db: Database, stepName?: string) {
  const { sql, params } = MemoryDao.buildQueryMemoryRecordsByComponent(stepName)
  const stmt = db.prepare(sql)
  if (params && params.length) {
    stmt.bind(params)
  }
  const rows: any[] = []
  while (stmt.step()) {
    rows.push(stmt.getAsObject({}))
  }
  stmt.free()
  return MemoryDao.formatMemoryRecordsByComponent(rows)
}

export async function queryMemoryResults(db: Database, stepName?: string) {
  const { sql, params } = MemoryDao.buildQueryMemoryResults(stepName)
  const stmt = db.prepare(sql)
  if (params && params.length) {
    stmt.bind(params)
  }
  const rows: any[] = []
  while (stmt.step()) {
    rows.push(stmt.getAsObject({}))
  }
  stmt.free()
  return rows
}

export async function queryMemoryRecords(db: Database, stepName?: string, limit?: number) {
  const { sql, params } = MemoryDao.buildQueryMemoryRecords(stepName, limit)
  const stmt = db.prepare(sql)
  if (params && params.length) {
    stmt.bind(params)
  }
  const rows: any[] = []
  while (stmt.step()) {
    rows.push(stmt.getAsObject({}))
  }
  stmt.free()
  return rows
}
