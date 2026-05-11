#!/usr/bin/env node
/**
 * 将当前系统已安装的 radare2 + 反编译插件（r2dec/r2ghidra）打包到 dist/tools/bin/r2/。
 *
 * 在 CI/CD 中由 prebuild 调用（在 build.yml 中安装 radare2 + r2dec 之后执行）。
 * 若 r2 未安装则跳过（不阻塞构建）。
 *
 * 输出目录结构：
 *   dist/tools/bin/r2/
 *     r2               (wrapper/launcher)
 *     r2_real           (真实的 r2 二进制 / r2.exe)
 *     plugins/          (反编译插件 .so/.dylib/.dll)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const DIST_TOOLS_BIN = path.resolve(__dirname, '../dist/tools/bin');
const BUNDLE_DIR = path.join(DIST_TOOLS_BIN, 'r2');

function run(cmd, options = {}) {
  try {
    return execSync(cmd, { encoding: 'utf-8', ...options }).trim();
  } catch {
    return null;
  }
}

function bundleRadare2() {
  // 1. 检查 r2 是否在 PATH 中
  const r2Path = run('command -v r2 2>/dev/null || which r2 2>/dev/null');
  if (!r2Path) {
    console.warn('[bundle_radare2] WARNING: r2 not found in PATH, skipping bundling');
    return false;
  }
  console.log(`[bundle_radare2] Found r2 at: ${r2Path}`);

  // 2. 创建 bundle 目录
  const pluginsDir = path.join(BUNDLE_DIR, 'plugins');
  fs.mkdirSync(pluginsDir, { recursive: true });

  // 3. 获取 r2 版本信息和插件目录
  const r2Version = run('r2 -v 2>/dev/null | head -1');
  const pluginDir = run('r2 -H R2_PLUGINS 2>/dev/null');
  const libDir = run('r2 -H R2_LIBDIR 2>/dev/null');

  console.log(`[bundle_radare2] Version: ${r2Version || '(unknown)'}`);
  console.log(`[bundle_radare2] R2_PLUGINS: ${pluginDir || '(unknown)'}`);
  console.log(`[bundle_radare2] R2_LIBDIR:   ${libDir || '(unknown)'}`);

  // 4. 复制 r2 二进制
  const isWin = process.platform === 'win32';
  const r2BinName = isWin ? 'r2.exe' : 'r2';
  const r2Real = path.join(BUNDLE_DIR, 'r2_real');
  // r2pipe.open() 查找 radare2（非 r2），打包时同时提供 radare2 二进制供 r2pipe 使用
  const r2Radare2 = path.join(BUNDLE_DIR, isWin ? 'radare2.exe' : 'radare2');

  try {
    fs.copyFileSync(r2Path, r2Real);
    if (!isWin) fs.chmodSync(r2Real, 0o755);
    console.log(`[bundle_radare2] Copied r2 binary: ${r2Path} -> ${r2Real}`);
    // 也复制为 radare2 / radare2.exe（r2pipe 查找的名称）
    fs.copyFileSync(r2Path, r2Radare2);
    if (!isWin) fs.chmodSync(r2Radare2, 0o755);
    console.log(`[bundle_radare2] Copied r2 binary as radare2 for r2pipe compat: ${r2Radare2}`);
  } catch (e) {
    console.warn(`[bundle_radare2] WARNING: failed to copy r2 binary: ${e.message}`);
    return false;
  }

  // 5. 复制插件文件（搜索多个可能的位置）
  const searchDirs = [pluginDir, libDir].filter(Boolean);

  // 常见 r2pm 插件安装位置
  const homeDir = os.homedir();
  const xdgDataHome = process.env.XDG_DATA_HOME || path.join(homeDir, '.local', 'share');
  searchDirs.push(path.join(xdgDataHome, 'radare2', 'plugins'));
  searchDirs.push(path.join(homeDir, '.local', 'share', 'radare2', 'plugins'));
  // macOS brew cellars
  searchDirs.push(path.join(homeDir, '.brew', 'Cellar', 'radare2'));

  let pluginCount = 0;
  const seenPlugins = new Set();

  for (const dir of searchDirs) {
    if (!dir || !fs.existsSync(dir)) continue;
    try {
      const items = fs.readdirSync(dir);
      for (const item of items) {
        const lower = item.toLowerCase();
        const isPlugin = lower.includes('r2dec') || lower.includes('r2ghidra')
          || lower.includes('pdg') || lower.includes('pdd');
        if (!isPlugin) continue;
        if (seenPlugins.has(item)) continue;
        seenPlugins.add(item);

        const src = path.join(dir, item);
        if (fs.statSync(src).isDirectory()) continue;

        const dst = path.join(pluginsDir, item);
        try {
          fs.copyFileSync(src, dst);
          if (!isWin) fs.chmodSync(dst, 0o755);
          console.log(`[bundle_radare2] Copied plugin: ${item}`);
          pluginCount++;
        } catch (e) {
          console.warn(`[bundle_radare2] WARNING: failed to copy plugin ${item}: ${e.message}`);
        }
      }
    } catch (e) {
      // skip unreadable dirs
    }
  }

  if (pluginCount === 0) {
    console.warn('[bundle_radare2] WARNING: no decompiler plugins found (r2dec/r2ghidra)');
  } else {
    console.log(`[bundle_radare2] Bundled ${pluginCount} plugin(s)`);
  }

  // 6. 创建 r2 wrapper（插件安装由 Python 代码中的 _ensure_bundled_plugins 处理）
  // wrapper 仅负责让 shutil.which('r2') 能找到 bundle 路径
  if (isWin) {
    // Windows: r2.bat wrapper, r2_real.exe 是真实二进制
    const wrapperBat = path.join(BUNDLE_DIR, 'r2.bat');
    fs.writeFileSync(wrapperBat, `@echo off
"%~dp0r2_real.exe" %*
`);
    console.log('[bundle_radare2] Created r2.bat wrapper for Windows');
  } else {
    // Unix: 创建 shell wrapper
    const wrapper = `#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
export R2PIPE_R2_BIN="${DIR}/r2_real"
exec "${DIR}/r2_real" "$@"
`;
    const wrapperPath = path.join(BUNDLE_DIR, r2BinName);
    fs.writeFileSync(wrapperPath, wrapper);
    fs.chmodSync(wrapperPath, 0o755);

    // 在 dist/tools/bin/ 下创建 r2 symlink 方便 PATH 查找
    const topLink = path.join(DIST_TOOLS_BIN, r2BinName);
    try {
      if (!fs.existsSync(topLink)) {
        fs.symlinkSync(path.join('r2', r2BinName), topLink);
        console.log(`[bundle_radare2] Created symlink: ${topLink} -> r2/${r2BinName}`);
      }
    } catch {
      // symlink may fail on some systems
    }

    console.log('[bundle_radare2] Created r2 wrapper script');
  }

  console.log('[bundle_radare2] Done');
  return true;
}

const result = bundleRadare2();
process.exit(result ? 0 : 0); // 不阻塞构建
