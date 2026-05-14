#!/usr/bin/env node
/**
 * 将当前系统已安装的 radare2 + 反编译插件（r2dec/r2ghidra）打包到 dist/tools/bin/r2/。
 *
 * 在 CI/CD 中由 prebuild 调用（在 build.yml 中安装 radare2 + r2dec 之后执行）。
 * 若 r2 未安装则跳过（不阻塞构建）。
 *
 * 输出目录结构：
 *   dist/tools/bin/r2/
 *     r2 / r2.bat        (wrapper/launcher)
 *     r2_real(.exe)      (真实 r2 入口，与 r2pipe 兼容)
 *     radare2(.exe)      (r2pipe 查找名)
 *     *.dll              (Windows：与 radare2.exe 同目录的依赖)
 *     plugins/           (反编译插件)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');

const DIST_TOOLS_BIN = path.resolve(__dirname, '../dist/tools/bin');
const BUNDLE_DIR = path.join(DIST_TOOLS_BIN, 'r2');

/** 便携版缓存根（与 ensure_radare2.js 约定一致，位于 third-party/.cache） */
function getPortableRadare2CacheRoot() {
  if (process.platform !== 'win32') return null;
  const suffix = process.arch === 'arm64' ? 'w64-arm64' : 'w64';
  return path.resolve(__dirname, '../third-party/.cache', `radare2-${suffix}`);
}

/** 遍历 ensure_radare2 下载解压的便携版目录 */
function findPortableWindowsRadare2Bin() {
  const root = getPortableRadare2CacheRoot();
  if (!root || !fs.existsSync(root)) return null;

  function walk(d, depth) {
    if (depth > 10) return null;
    let dirents;
    try {
      dirents = fs.readdirSync(d, { withFileTypes: true });
    } catch {
      return null;
    }
    const hasExe = ['radare2.exe', 'r2.exe'].some((n) => fs.existsSync(path.join(d, n)));
    if (hasExe) {
      try {
        const sibs = fs.readdirSync(d);
        if (sibs.some((f) => f.toLowerCase().endsWith('.dll'))) return d;
      } catch {
        /* continue */
      }
    }
    for (const e of dirents) {
      if (!e.isDirectory()) continue;
      const found = walk(path.join(d, e.name), depth + 1);
      if (found) return found;
    }
    return null;
  }
  return walk(root, 0);
}

function pathSegments() {
  const raw = process.env.PATH || process.env.Path || '';
  return raw.split(path.delimiter).filter(Boolean);
}

/** Unix：在 PATH 中查找第一个存在的可执行文件名 */
function findOnPathUnix(names) {
  for (const dir of pathSegments()) {
    for (const name of names) {
      const full = path.join(dir, name);
      try {
        if (fs.existsSync(full) && fs.statSync(full).isFile()) {
          return full;
        }
      } catch {
        /* skip */
      }
    }
  }
  return null;
}

/** Windows：Chocolatey 将完整发行版放在 ProgramData\\chocolatey\\lib\\radare2\\...\\bin */
function findChocolateyRadare2Bin() {
  const programData = process.env.ProgramData;
  if (!programData) return null;
  const root = path.join(programData, 'chocolatey', 'lib', 'radare2');
  if (!fs.existsSync(root)) return null;

  function walk(d, depth) {
    if (depth > 10) return null;
    let dirents;
    try {
      dirents = fs.readdirSync(d, { withFileTypes: true });
    } catch {
      return null;
    }
    const binDir = path.join(d, 'bin');
    const main = path.join(binDir, 'radare2.exe');
    if (fs.existsSync(main)) {
      try {
        const files = fs.readdirSync(binDir);
        if (files.some((f) => f.toLowerCase().endsWith('.dll'))) {
          return binDir;
        }
      } catch {
        /* skip */
      }
    }
    for (const e of dirents) {
      if (!e.isDirectory()) continue;
      const found = walk(path.join(d, e.name), depth + 1);
      if (found) return found;
    }
    return null;
  }
  return walk(root, 0);
}

/**
 * Windows：返回「含 radare2.exe 与若干 .dll」的目录；勿仅用 chocolatey\\bin 下的 shim 目录。
 */
function findWindowsRadare2BinDir() {
  const portable = findPortableWindowsRadare2Bin();
  if (portable) return portable;

  const chocoBin = findChocolateyRadare2Bin();
  if (chocoBin) return chocoBin;

  for (const name of ['radare2.exe', 'r2.exe']) {
    for (const dir of pathSegments()) {
      const full = path.join(dir, name);
      try {
        if (!fs.existsSync(full) || !fs.statSync(full).isFile()) continue;
        const d = path.dirname(full);
        const sibs = fs.readdirSync(d);
        if (sibs.some((f) => f.toLowerCase().endsWith('.dll'))) {
          return d;
        }
      } catch {
        /* skip */
      }
    }
  }
  return null;
}

/** 非 Windows：沿用 PATH 查找 r2 / radare2 */
function findUnixR2Exe() {
  return findOnPathUnix(['r2', 'radare2']);
}

function r2Query(r2Exe, args) {
  try {
    return execFileSync(r2Exe, args, { encoding: 'utf-8', windowsHide: true }).trim();
  } catch {
    return null;
  }
}

function copyDirFilesFlat(srcDir, dstDir) {
  let n = 0;
  let dirents;
  try {
    dirents = fs.readdirSync(srcDir, { withFileTypes: true });
  } catch {
    return 0;
  }
  for (const e of dirents) {
    if (!e.isFile()) continue;
    const src = path.join(srcDir, e.name);
    const dst = path.join(dstDir, e.name);
    try {
      fs.copyFileSync(src, dst);
      if (process.platform !== 'win32') fs.chmodSync(dst, 0o755);
      n++;
    } catch (err) {
      console.warn(`[bundle_radare2] WARNING: skip copy ${e.name}: ${err.message}`);
    }
  }
  return n;
}

function bundleRadare2() {
  const isWin = process.platform === 'win32';

  let r2Path;
  let winBinDir;

  if (isWin) {
    winBinDir = findWindowsRadare2BinDir();
    if (!winBinDir) {
      console.warn('[bundle_radare2] WARNING: radare2 bin dir not found on PATH / Chocolatey, skipping bundling');
      return false;
    }
    r2Path = path.join(winBinDir, 'radare2.exe');
    if (!fs.existsSync(r2Path)) {
      r2Path = path.join(winBinDir, 'r2.exe');
    }
    if (!fs.existsSync(r2Path)) {
      console.warn('[bundle_radare2] WARNING: no radare2.exe/r2.exe in resolved bin dir, skipping');
      return false;
    }
    console.log(`[bundle_radare2] Found Windows radare2 bin dir: ${winBinDir}`);
    console.log(`[bundle_radare2] Entry binary: ${r2Path}`);
  } else {
    r2Path = findUnixR2Exe();
    if (!r2Path) {
      console.warn('[bundle_radare2] WARNING: r2 not found in PATH, skipping bundling');
      return false;
    }
    console.log(`[bundle_radare2] Found r2 at: ${r2Path}`);
  }

  const pluginsDir = path.join(BUNDLE_DIR, 'plugins');
  fs.mkdirSync(pluginsDir, { recursive: true });

  // Windows：勿对 radare2.exe 执行 -v/-H（与 .github/workflows/build.yml 一致）。
  // 在 Git Bash / 无 TTY 的 runner 上 r2 可能调 stty 等导致长时间挂起；execFileSync 亦无超时。
  let r2Version = null;
  let pluginDir = null;
  let libDir = null;
  if (isWin && winBinDir) {
    const guessLib = path.resolve(winBinDir, '..', 'lib');
    const guessPlugins = path.join(guessLib, 'plugins');
    if (fs.existsSync(guessPlugins)) pluginDir = guessPlugins;
    if (fs.existsSync(guessLib)) libDir = guessLib;
  } else {
    r2Version = r2Query(r2Path, ['-v'])?.split(/\r?\n/)[0] ?? null;
    pluginDir = r2Query(r2Path, ['-H', 'R2_PLUGINS']);
    libDir = r2Query(r2Path, ['-H', 'R2_LIBDIR']);
  }

  console.log(`[bundle_radare2] Version: ${r2Version || '(unknown)'}`);
  console.log(`[bundle_radare2] R2_PLUGINS: ${pluginDir || '(unknown)'}`);
  console.log(`[bundle_radare2] R2_LIBDIR:   ${libDir || '(unknown)'}`);

  const r2BinName = isWin ? 'r2.exe' : 'r2';
  const r2Real = path.join(BUNDLE_DIR, isWin ? 'r2_real.exe' : 'r2_real');
  const r2Radare2 = path.join(BUNDLE_DIR, isWin ? 'radare2.exe' : 'radare2');

  try {
    if (isWin) {
      const copied = copyDirFilesFlat(winBinDir, BUNDLE_DIR);
      console.log(`[bundle_radare2] Copied ${copied} file(s) from ${winBinDir} -> ${BUNDLE_DIR}`);
    } else {
      fs.copyFileSync(r2Path, r2Real);
      fs.chmodSync(r2Real, 0o755);
      console.log(`[bundle_radare2] Copied r2 binary: ${r2Path} -> ${r2Real}`);
      fs.copyFileSync(r2Path, r2Radare2);
      fs.chmodSync(r2Radare2, 0o755);
      console.log(`[bundle_radare2] Copied r2 binary as radare2 for r2pipe compat: ${r2Radare2}`);
    }

    if (isWin) {
      const entry = path.join(BUNDLE_DIR, path.basename(r2Path));
      if (fs.existsSync(entry)) {
        fs.copyFileSync(entry, r2Real);
        fs.copyFileSync(entry, r2Radare2);
        console.log(`[bundle_radare2] r2_real.exe / radare2.exe aligned with ${path.basename(r2Path)}`);
      }
    }
  } catch (e) {
    console.warn(`[bundle_radare2] WARNING: failed to copy r2 binary: ${e.message}`);
    return false;
  }

  const searchDirs = [pluginDir, libDir].filter(Boolean);

  const homeDir = os.homedir();
  const xdgDataHome = process.env.XDG_DATA_HOME || path.join(homeDir, '.local', 'share');
  searchDirs.push(path.join(xdgDataHome, 'radare2', 'plugins'));
  searchDirs.push(path.join(homeDir, '.local', 'share', 'radare2', 'plugins'));
  searchDirs.push(path.join(homeDir, '.brew', 'Cellar', 'radare2'));
  if (isWin && winBinDir) {
    searchDirs.push(path.join(winBinDir, '..', 'lib', 'plugins'));
    searchDirs.push(path.join(winBinDir, 'plugins'));
  }

  let pluginCount = 0;
  const seenPlugins = new Set();

  for (const dir of searchDirs) {
    if (!dir || !fs.existsSync(dir)) continue;
    try {
      const items = fs.readdirSync(dir);
      for (const item of items) {
        const lower = item.toLowerCase();
        const isPlugin =
          lower.includes('r2dec') || lower.includes('r2ghidra') || lower.includes('pdg') || lower.includes('pdd');
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
    } catch {
      /* skip unreadable dirs */
    }
  }

  if (pluginCount === 0) {
    console.warn('[bundle_radare2] WARNING: no decompiler plugins found (r2dec/r2ghidra)');
  } else {
    console.log(`[bundle_radare2] Bundled ${pluginCount} plugin(s)`);
  }

  if (isWin) {
    const wrapperBat = path.join(BUNDLE_DIR, 'r2.bat');
    fs.writeFileSync(
      wrapperBat,
      `@echo off
"%~dp0r2_real.exe" %*
`
    );
    console.log('[bundle_radare2] Created r2.bat wrapper for Windows');
  } else {
    const wrapper = `#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
export R2PIPE_R2_BIN="${DIR}/r2_real"
exec "${DIR}/r2_real" "$@"
`;
    const wrapperPath = path.join(BUNDLE_DIR, r2BinName);
    fs.writeFileSync(wrapperPath, wrapper);
    fs.chmodSync(wrapperPath, 0o755);

    const topLink = path.join(DIST_TOOLS_BIN, r2BinName);
    try {
      if (!fs.existsSync(topLink)) {
        fs.symlinkSync(path.join('r2', r2BinName), topLink);
        console.log(`[bundle_radare2] Created symlink: ${topLink} -> r2/${r2BinName}`);
      }
    } catch {
      /* symlink may fail on some systems */
    }

    console.log('[bundle_radare2] Created r2 wrapper script');
  }

  console.log('[bundle_radare2] Done');
  return true;
}

/** 当前环境是否满足 bundle_radare2 的探测规则（与即将执行的打包逻辑一致） */
function isRadare2Bundleable() {
  if (process.platform === 'win32') {
    const winBinDir = findWindowsRadare2BinDir();
    if (!winBinDir) return false;
    const p1 = path.join(winBinDir, 'radare2.exe');
    const p2 = path.join(winBinDir, 'r2.exe');
    return fs.existsSync(p1) || fs.existsSync(p2);
  }
  return findUnixR2Exe() !== null;
}

module.exports = { bundleRadare2, isRadare2Bundleable, getPortableRadare2CacheRoot };

if (require.main === module) {
  bundleRadare2();
  process.exit(0);
}
