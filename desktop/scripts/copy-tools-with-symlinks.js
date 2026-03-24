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

function computeStableSymlinkTarget(srcPath, srcRoot, destPath, rawTarget) {
  // 相对链接在 PyInstaller onedir 内通常是正确语义，必须原样保留
  if (!path.isAbsolute(rawTarget)) {
    return rawTarget;
  }

  const relFromSrcRoot = path.relative(srcRoot, rawTarget);
  // 绝对目标仍在 tools 树内时，重写为目标目录可用的相对路径，避免携带构建机绝对路径
  if (!relFromSrcRoot.startsWith("..") && !path.isAbsolute(relFromSrcRoot)) {
    const srcAbsTarget = path.resolve(srcRoot, relFromSrcRoot);
    const destAbsTarget = path.resolve(destPath, "..", path.relative(srcPath, srcAbsTarget));
    return path.relative(path.dirname(destPath), destAbsTarget);
  }

  // tools 之外的绝对目标保持原样（例如系统库）
  return rawTarget;
}

function copyDirWithSymlinks(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isSymbolicLink()) {
      const rawTarget = fs.readlinkSync(srcPath);
      const target = computeStableSymlinkTarget(srcPath, DIST_TOOLS, destPath, rawTarget);
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

function validateSymlinks(rootDir) {
  const stack = [rootDir];
  const broken = [];
  while (stack.length > 0) {
    const cur = stack.pop();
    for (const entry of fs.readdirSync(cur, { withFileTypes: true })) {
      const full = path.join(cur, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
        continue;
      }
      if (!entry.isSymbolicLink()) continue;
      const target = fs.readlinkSync(full);
      const resolved = path.isAbsolute(target)
        ? target
        : path.resolve(path.dirname(full), target);
      if (!fs.existsSync(resolved)) {
        broken.push(`${path.relative(process.cwd(), full)} -> ${target}`);
      }
    }
  }
  if (broken.length > 0) {
    throw new Error(`检测到 ${broken.length} 个坏软连接:\n${broken.join("\n")}`);
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
    validateSymlinks(dest);
    console.log(`  ✓ 已保留软连接复制 tools -> ${path.relative(process.cwd(), dest)}`);
  }
}

main();
