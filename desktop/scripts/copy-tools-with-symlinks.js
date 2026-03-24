#!/usr/bin/env node
/**
 * 将 dist/tools 复制到目标目录，保留软连接。
 * Tauri 的 bundle.resources 使用 fs::copy 会解析软连接，导致 opt-detector 等 PyInstaller
 * 产物的符号链接丢失。此脚本在 tauri build 后覆盖 tools，恢复软连接。
 */
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DIST_TOOLS = path.resolve(__dirname, "../../dist/tools");

function copyDirWithSymlinks(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isSymbolicLink()) {
      const target = fs.readlinkSync(srcPath);
      try {
        fs.symlinkSync(target, destPath);
      } catch (err) {
        // Windows 未开开发者模式/无管理员权限时 symlink 常失败，回退为复制真实文件以免打包中断
        if (process.platform === "win32") {
          fs.copyFileSync(fs.realpathSync(srcPath), destPath);
        } else {
          throw err;
        }
      }
    } else if (entry.isDirectory()) {
      copyDirWithSymlinks(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function main() {
  if (!fs.existsSync(DIST_TOOLS)) {
    console.warn("copy-tools-with-symlinks: dist/tools 不存在，跳过");
    return;
  }

  const bundleBase = path.resolve(__dirname, "../src-tauri/target/release/bundle");
  const releaseTools = path.resolve(__dirname, "../src-tauri/target/release/tools");

  const targets = [releaseTools];
  if (fs.existsSync(bundleBase)) {
    const macosDir = path.join(bundleBase, "macos");
    const tauriConf = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../src-tauri/tauri.conf.json"), "utf-8"));
    const appName = `${tauriConf.productName || "ArkAnalyzer-HapRay"}.app`;
    const appTools = path.join(macosDir, appName, "Contents", "Resources", "tools");
    if (fs.existsSync(appTools)) {
      targets.push(appTools);
    }
  }

  for (const dest of targets) {
    if (fs.existsSync(dest)) {
      fs.rmSync(dest, { recursive: true });
    }
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    copyDirWithSymlinks(DIST_TOOLS, dest);
    console.log(`  ✓ 已保留软连接复制 tools -> ${path.relative(process.cwd(), dest)}`);
  }
}

main();
