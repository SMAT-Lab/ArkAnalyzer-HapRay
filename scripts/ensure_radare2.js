#!/usr/bin/env node
/**
 * 在 prebuild 之前尽量安装 / 放置 radare2，便于 bundle_radare2 打入 dist/tools/bin/r2/。
 *
 * Windows：无 Chocolatey 时从 GitHub Releases 拉取官方 w64 / w64-arm64 zip 到 third-party/.cache/（与 bundle_radare2 探测路径一致）。
 * 任意失败仅警告，不阻塞构建（exit 0）。
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');
const http = require('http');
const { execFileSync } = require('child_process');
const { isRadare2Bundleable, getPortableRadare2CacheRoot } = require('./bundle_radare2');

const GITHUB_LATEST = 'https://api.github.com/repos/radareorg/radare2/releases/latest';

/** 下载到文件：Windows 上 curl 优先带 --ssl-no-revoke（缓解 Schannel 吊销检查失败）；再 Node https；仍失败则用 curl -k。 */
async function downloadUrlToFile(url, destPath) {
  const winTls = process.platform === 'win32' ? ['--ssl-no-revoke'] : [];
  try {
    execFileSync('curl', ['-fL', '--retry', '2', ...winTls, '-o', destPath, url], { stdio: 'inherit', windowsHide: true });
    return;
  } catch {
    /* 继续 */
  }
  try {
    const buf = await httpsGetBuffer(url);
    fs.writeFileSync(destPath, buf);
    return;
  } catch (e) {
    const msg = String(e && e.message ? e.message : e);
    const certish = /certificate|CERT|UNABLE_TO_VERIFY|SELF_SIGNED|ssl|verify/i.test(msg);
    if (!certish) throw e;
  }
  console.warn('[ensure_radare2] TLS verify failed; retrying download with curl -k (insecure)');
  execFileSync('curl', ['-fL', '-k', '--retry', '2', '-o', destPath, url], { stdio: 'inherit', windowsHide: true });
}

function tryExec(cmd, args, label) {
  try {
    execFileSync(cmd, args, { stdio: 'inherit', windowsHide: true });
    return true;
  } catch (e) {
    console.warn(`[ensure_radare2] ${label} failed: ${e.message}`);
    return false;
  }
}

/** 跟随重定向拉取 URL 为 Buffer */
function httpsGetBuffer(url, redirectsLeft = 8) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const lib = u.protocol === 'https:' ? https : http;
    const req = lib.request(
      u,
      {
        method: 'GET',
        headers: { 'User-Agent': 'ArkAnalyzer-HapRay-ensure-radare2', Accept: 'application/octet-stream,*/*' },
      },
      (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && redirectsLeft > 0) {
          const next = new URL(res.headers.location, url).href;
          res.resume();
          httpsGetBuffer(next, redirectsLeft - 1).then(resolve).catch(reject);
          return;
        }
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          return;
        }
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => resolve(Buffer.concat(chunks)));
      }
    );
    req.on('error', reject);
    req.end();
  });
}

function findChocoExe() {
  const candidates = [
    'choco',
    path.join(process.env.ProgramData || '', 'chocolatey', 'bin', 'choco.exe'),
    path.join(process.env.SystemDrive || 'C:', 'ProgramData', 'chocolatey', 'bin', 'choco.exe'),
  ];
  for (const c of candidates) {
    try {
      execFileSync(c, ['--version'], { stdio: 'pipe', windowsHide: true });
      return c;
    } catch {
      /* try next */
    }
  }
  return null;
}

function pickWindowsZipAsset(assets) {
  const isArm = process.arch === 'arm64';
  for (const a of assets) {
    const n = a.name;
    if (!n || !n.endsWith('.zip')) continue;
    if (isArm) {
      if (/^radare2-.+-w64-arm64\.zip$/.test(n)) return a;
    } else if (/^radare2-.+-w64\.zip$/.test(n) && !n.includes('arm64')) {
      return a;
    }
  }
  return null;
}

function extractZipWindows(zipPath, destDir) {
  try {
    execFileSync('tar', ['-xf', zipPath, '-C', destDir], { stdio: 'inherit', windowsHide: true });
    return;
  } catch {
    console.log('[ensure_radare2] tar -xf failed, trying PowerShell Expand-Archive...');
  }
  const z = zipPath.replace(/'/g, "''");
  const d = destDir.replace(/'/g, "''");
  execFileSync('powershell.exe', [
    '-NoProfile',
    '-NonInteractive',
    '-Command',
    `Expand-Archive -LiteralPath '${z}' -DestinationPath '${d}' -Force`,
  ], { stdio: 'inherit', windowsHide: true });
}

async function ensurePortableRadare2Windows() {
  const cacheRoot = getPortableRadare2CacheRoot();
  if (!cacheRoot) return;

  const stampPath = path.join(cacheRoot, '.installed_tag');
  let release;
  const metaTmp = path.join(os.tmpdir(), `hapray-r2-release-${Date.now()}.json`);
  try {
    await downloadUrlToFile(GITHUB_LATEST, metaTmp);
    release = JSON.parse(fs.readFileSync(metaTmp, 'utf8'));
  } catch (e) {
    console.warn(`[ensure_radare2] GitHub API fetch failed: ${e.message}`);
    return;
  } finally {
    try {
      fs.unlinkSync(metaTmp);
    } catch {
      /* ignore */
    }
  }

  const tag = release.tag_name;
  if (!tag || !Array.isArray(release.assets)) {
    console.warn('[ensure_radare2] unexpected GitHub release JSON');
    return;
  }

  const asset = pickWindowsZipAsset(release.assets);
  if (!asset || !asset.browser_download_url) {
    console.warn('[ensure_radare2] no radare2 Windows zip asset in latest release');
    return;
  }

  if (fs.existsSync(stampPath) && fs.readFileSync(stampPath, 'utf8').trim() === tag && isRadare2Bundleable()) {
    console.log(`[ensure_radare2] portable radare2 ${tag} already present, skip download`);
    return;
  }

  console.log(`[ensure_radare2] downloading ${asset.name} (${tag}) ...`);
  fs.rmSync(cacheRoot, { recursive: true, force: true });
  fs.mkdirSync(cacheRoot, { recursive: true });

  const zipPath = path.join(cacheRoot, '._download.zip');
  try {
    await downloadUrlToFile(asset.browser_download_url, zipPath);
  } catch (e) {
    console.warn(`[ensure_radare2] download failed: ${e.message}`);
    fs.rmSync(cacheRoot, { recursive: true, force: true });
    return;
  }

  try {
    extractZipWindows(zipPath, cacheRoot);
  } catch (e) {
    console.warn(`[ensure_radare2] extract failed: ${e.message}`);
    try {
      fs.unlinkSync(zipPath);
    } catch {
      /* ignore */
    }
    fs.rmSync(cacheRoot, { recursive: true, force: true });
    return;
  }

  try {
    fs.unlinkSync(zipPath);
  } catch {
    /* ignore */
  }

  fs.writeFileSync(stampPath, `${tag}\n`, 'utf8');
  console.log(`[ensure_radare2] portable radare2 installed under ${cacheRoot}`);
}

async function main() {
  if (isRadare2Bundleable()) {
    console.log('[ensure_radare2] radare2 already OK for bundling, skip install');
    process.exit(0);
    return;
  }

  console.log('[ensure_radare2] radare2 not bundle-ready; attempting install...');

  const p = process.platform;
  if (p === 'win32') {
    const choco = findChocoExe();
    if (choco) {
      tryExec(choco, ['install', 'radare2', '-y', '--no-progress'], 'Chocolatey radare2');
    } else {
      console.log('[ensure_radare2] Chocolatey not found, will try portable zip from GitHub');
    }

    if (!isRadare2Bundleable()) {
      await ensurePortableRadare2Windows();
    }

    if (!isRadare2Bundleable()) {
      console.warn(
        '[ensure_radare2] radare2 still not bundle-ready after Chocolatey/portable steps; symbol recovery may fall back to capstone'
      );
    }
  } else if (p === 'darwin') {
    try {
      execFileSync('brew', ['--version'], { stdio: 'pipe', windowsHide: true });
      tryExec('brew', ['install', 'radare2'], 'Homebrew radare2');
    } catch {
      console.warn('[ensure_radare2] Homebrew not found; install manually: brew install radare2');
    }
  } else if (p === 'linux') {
    const ok = tryExec(
      'sh',
      [
        '-c',
        'command -v apt-get >/dev/null 2>&1 && sudo -n apt-get update -qq && sudo -n apt-get install -y -qq radare2',
      ],
      'apt radare2'
    );
    if (!ok) {
      console.warn(
        '[ensure_radare2] apt non-interactive install skipped or failed; try: sudo apt-get install -y radare2'
      );
    }
  } else {
    console.warn(`[ensure_radare2] unsupported platform ${p}, skip install`);
  }

  process.exit(0);
}

main().catch((e) => {
  console.warn('[ensure_radare2] unexpected error:', e.message);
  process.exit(0);
});
