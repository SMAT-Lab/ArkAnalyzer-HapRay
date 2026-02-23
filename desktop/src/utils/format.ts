/**
 * 格式化工具函数
 */

/** 将 YYYYMMDD_HHMMSS 格式时间戳格式化为可读字符串 */
export function formatTimestamp(ts?: string): string {
  if (!ts) return ""
  if (ts.length >= 15) {
    const y = ts.slice(0, 4)
    const m = ts.slice(4, 6)
    const d = ts.slice(6, 8)
    const h = ts.slice(9, 11)
    const min = ts.slice(11, 13)
    const s = ts.slice(13, 15)
    return `${y}-${m}-${d} ${h}:${min}:${s}`
  }
  return ts
}
