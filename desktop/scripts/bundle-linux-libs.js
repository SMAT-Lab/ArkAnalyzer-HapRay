#!/usr/bin/env node
/**
 * Linux 专用：将可执行文件依赖的 .so 复制到可执行文件旁的 lib/ 目录，
 * 配合 .cargo/config.toml 中的 rpath ($ORIGIN/lib)，使目标机器无需安装 libwebkit2gtk 等。
 * 非 Linux 平台直接退出。
 */
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

if (process.platform !== "linux") {
  process.exit(0);
}

const productName = "ArkAnalyzer-HapRay";
const releaseDir = path.resolve(__dirname, "../src-tauri/target/release");
const binaryPath = path.join(releaseDir, productName);
const libDir = path.join(releaseDir, "lib");

if (!fs.existsSync(binaryPath)) {
  console.warn("[bundle-linux-libs] 未找到可执行文件:", binaryPath);
  process.exit(0);
}

// 解析 ldd 输出： "libfoo.so.0 => /usr/lib/... (0x...)" 或 "libfoo.so.0 (0x...)"
function parseLdd(output) {
  const entries = [];
  for (const line of output.split("\n")) {
    const arrow = line.indexOf("=>");
    if (arrow === -1) {
      const match = line.trim().match(/^(\S+)\s+\(0x[0-9a-f]+\)$/);
      if (match) {
        const name = match[1];
        if (name.startsWith("linux-vdso") || name.startsWith("linux-gate")) continue;
        entries.push({ name, path: null });
      }
      continue;
    }
    const name = line.slice(0, arrow).trim();
    const pathPart = line.slice(arrow + 2).trim();
    const pathMatch = pathPart.match(/^(\S+)/);
    if (pathMatch && fs.existsSync(pathMatch[1])) {
      entries.push({ name, path: pathMatch[1] });
    }
  }
  return entries;
}

try {
  const lddOut = execSync(`ldd "${binaryPath}"`, { encoding: "utf-8", maxBuffer: 4 * 1024 * 1024 });
  const entries = parseLdd(lddOut);
  fs.mkdirSync(libDir, { recursive: true });

  let copied = 0;
  for (const { name, path: srcPath } of entries) {
    if (!srcPath) continue;
    const destPath = path.join(libDir, name);
    if (fs.existsSync(destPath)) continue;
    try {
      fs.copyFileSync(srcPath, destPath);
      copied++;
    } catch (e) {
      console.warn("[bundle-linux-libs] 复制失败:", name, e.message);
    }
  }
  console.log(`[bundle-linux-libs] 已复制 ${copied} 个 .so 到 ${libDir}`);
} catch (e) {
  console.warn("[bundle-linux-libs] ldd 执行失败:", e.message);
  process.exit(0);
}
