/**
 * Tauri 打包完成后，对 bundle 内 Resources/tools 做硬链接去重
 * 因 Tauri 拷贝 resources 时不会保留硬链接，需在拷贝后对 bundle 内文件做合并
 */
import path from "path";
import fs from "fs";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const BUNDLE_BASE = path.resolve(__dirname, "../src-tauri/target/release/bundle");
const DEBUG_BUNDLE_BASE = path.resolve(__dirname, "../src-tauri/target/debug/bundle");
const mergeScript = path.resolve(__dirname, "../../scripts/merge_duplicates.js");

function findToolsDirs(baseDir) {
  const toolsDirs = [];
  if (!fs.existsSync(baseDir)) return toolsDirs;

  function walk(dir) {
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name === "Resources") {
            const toolsPath = path.join(fullPath, "tools");
            if (fs.existsSync(toolsPath) && fs.statSync(toolsPath).isDirectory()) {
              toolsDirs.push(toolsPath);
            }
          }
          walk(fullPath);
        }
      }
    } catch {
      // ignore
    }
  }
  walk(baseDir);
  return toolsDirs;
}

function main() {
  const bundleBase = fs.existsSync(BUNDLE_BASE) ? BUNDLE_BASE : DEBUG_BUNDLE_BASE;
  if (!fs.existsSync(bundleBase)) {
    console.warn("Bundle 目录不存在，跳过 merge");
    return;
  }

  const toolsDirs = findToolsDirs(bundleBase);
  if (toolsDirs.length === 0) {
    console.log("未找到 Resources/tools，跳过 merge");
    return;
  }

  for (const toolsDir of toolsDirs) {
    console.log(`\n正在对 bundle 内 tools 做硬链接合并: ${toolsDir}`);
    try {
      execSync(`node "${mergeScript}" "${toolsDir}"`, {
        stdio: "inherit",
      });
    } catch (e) {
      console.error(`merge 失败: ${toolsDir}`, e.message);
    }
  }
}

main();
