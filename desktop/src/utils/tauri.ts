/**
 * Tauri 环境检测与 API 封装
 */

import { invoke } from "@tauri-apps/api/core"

const TAURI_GLOBAL = "__TAURI__"

export function isTauriEnv(): boolean {
  return !!(window as unknown as Record<string, unknown>)[TAURI_GLOBAL]
}

export async function openPath(path: string): Promise<void> {
  if (!isTauriEnv()) return
  try {
    await invoke("open_path_command", { path })
  } catch {
    // 打开失败时静默处理
  }
}
