const AdmZip = require('adm-zip');
const path = require('path');
const fs = require('fs');
const copyFile = require('./copy_file');

const DIST_TOOLS_DIR = path.join(__dirname, '../dist/tools');
/** 预构建解压的 hdc / hilogtool / trace_streamer_binary 放在 dist/tools/bin 下 */
const DIST_TOOLS_BIN_DIR = path.join(DIST_TOOLS_DIR, 'bin');
const PERF_TESTING_RESOURCE_DIR = path.join(__dirname, '../perf_testing/resource');
const TRACE_STREAMER_BIN = ['trace_streamer_linux', 'trace_streamer_mac', 'trace_streamer_windows.exe'];

function traceStreamerMarkerPath() {
    const m = {
        win32: 'trace_streamer_windows.exe',
        darwin: 'trace_streamer_mac',
        linux: 'trace_streamer_linux'
    };
    return path.join(DIST_TOOLS_BIN_DIR, m[process.platform]);
}

/** 将 dist/tools/bin/<subdir>/ 下文件提升到 dist/tools/bin/（避免 hdc/hdc、hilogtool/hilogtool 与父目录同名时 rename 冲突：先整体移走再展开） */
function flattenToolDirToParent(binDir, dirName) {
    const sub = path.join(binDir, dirName);
    if (!fs.existsSync(sub) || !fs.statSync(sub).isDirectory()) {
        return;
    }
    const staging = path.join(binDir, `.flatten_tmp_${dirName}_${process.pid}`);
    fs.renameSync(sub, staging);
    const names = fs.readdirSync(staging);
    names.forEach((name) => {
        const from = path.join(staging, name);
        const to = path.join(binDir, name);
        if (fs.existsSync(to)) {
            fs.rmSync(to, { recursive: true, force: true });
        }
        fs.renameSync(from, to);
    });
    fs.rmdirSync(staging);
}

function ensureDistToolsDir() {
    if (!fs.existsSync(DIST_TOOLS_DIR)) {
        fs.mkdirSync(DIST_TOOLS_DIR, { recursive: true });
    }
}

function ensureDistToolsBinDir() {
    ensureDistToolsDir();
    if (!fs.existsSync(DIST_TOOLS_BIN_DIR)) {
        fs.mkdirSync(DIST_TOOLS_BIN_DIR, { recursive: true });
    }
}

function ensurePerfTestingResourceDir() {
    if (!fs.existsSync(PERF_TESTING_RESOURCE_DIR)) {
        fs.mkdirSync(PERF_TESTING_RESOURCE_DIR, { recursive: true });
    }
}

function unzipFile(zipFile, output) {
    try {
        ensureDistToolsBinDir();
        const zipPath = path.join(__dirname, '../third-party', zipFile);
        const extractPath = path.join(DIST_TOOLS_BIN_DIR, output);

        if (output === 'trace_streamer_binary') {
            if (fs.existsSync(traceStreamerMarkerPath())) {
                return;
            }
            if (fs.existsSync(extractPath)) {
                fs.rmSync(extractPath, { recursive: true, force: true });
            }
        } else if (output === 'hilogtool') {
            const marker = path.join(
                DIST_TOOLS_BIN_DIR,
                process.platform === 'win32' ? 'hilogtool.exe' : 'hilogtool'
            );
            if (fs.existsSync(marker)) {
                return;
            }
            if (fs.existsSync(extractPath)) {
                fs.rmSync(extractPath, { recursive: true, force: true });
            }
        } else if (fs.existsSync(extractPath)) {
            return;
        }

        const zip = new AdmZip(zipPath);
        zip.extractAllTo(DIST_TOOLS_BIN_DIR, true);

        if (output === 'trace_streamer_binary') {
            cleanupTraceStreamerBinary(extractPath);
        }
        if (output === 'hilogtool') {
            cleanupHilogtool(extractPath);
        }
    } catch (error) {
        console.error(`Error extracting ${zipFile}:`, error.message);
    }
}


/** hdc-bundles.zip 内平台目录名 -> 当前 Node 进程对应目录 */
function resolveHdcBundlePlatformDir() {
    if (process.platform === 'win32') {
        return 'windows-x64';
    }
    if (process.platform === 'linux') {
        if (process.arch === 'arm64') {
            return null;
        }
        return 'linux-x64';
    }
    if (process.platform === 'darwin') {
        if (process.arch === 'arm64') {
            return 'darwin-arm64';
        }
        return 'darwin-x64';
    }
    return null;
}

/**
 * 解压 third-party/hdc-bundles.zip，整理后二进制与 libusb 位于 dist/tools/bin/（与 hdc 同目录）。
 */
function unzipHdcBundle() {
    const zipFile = 'hdc-bundles.zip';
    const output = 'hdc';
    try {
        ensureDistToolsBinDir();
        const zipPath = path.join(__dirname, '../third-party', zipFile);
        const extractPath = path.join(DIST_TOOLS_BIN_DIR, output);
        const hdcFileName = process.platform === 'win32' ? 'hdc.exe' : 'hdc';
        const hdcFlat = path.join(DIST_TOOLS_BIN_DIR, hdcFileName);
        if (fs.existsSync(hdcFlat) && fs.statSync(hdcFlat).isFile()) {
            return;
        }
        if (fs.existsSync(extractPath)) {
            fs.rmSync(extractPath, { recursive: true, force: true });
        }
        if (!fs.existsSync(zipPath)) {
            console.warn(`[prebuild] 跳过 hdc：未找到 ${zipPath}`);
            return;
        }

        const zip = new AdmZip(zipPath);
        zip.extractAllTo(DIST_TOOLS_BIN_DIR, true);
        cleanupHdcBundle(extractPath);
    } catch (error) {
        console.error(`Error extracting ${zipFile}:`, error.message);
    }
}

function cleanupHdcBundle(basePath) {
    const keepDir = resolveHdcBundlePlatformDir();
    const platformDirs = ['darwin-arm64', 'darwin-x64', 'linux-x64', 'windows-x64'];

    if (!keepDir) {
        console.warn(
            `[prebuild] hdc 压缩包不包含当前平台 (${process.platform}/${process.arch})，已删除 dist/tools/bin/hdc 目录`
        );
        if (fs.existsSync(basePath)) {
            fs.rmSync(basePath, { recursive: true, force: true });
        }
        return;
    }

    const srcDir = path.join(basePath, keepDir);
    if (!fs.existsSync(srcDir)) {
        console.warn(`[prebuild] hdc 压缩包中缺少目录 ${keepDir}，跳过整理`);
        return;
    }

    platformDirs.forEach((dir) => {
        if (dir === keepDir) {
            return;
        }
        const p = path.join(basePath, dir);
        if (fs.existsSync(p)) {
            fs.rmSync(p, { recursive: true, force: true });
        }
    });

    const names = fs.readdirSync(srcDir);
    names.forEach((name) => {
        const from = path.join(srcDir, name);
        const to = path.join(basePath, name);
        if (fs.existsSync(to)) {
            fs.rmSync(to, { recursive: true, force: true });
        }
        fs.renameSync(from, to);
    });
    fs.rmdirSync(srcDir);

    const readmePath = path.join(basePath, 'README.md');
    if (fs.existsSync(readmePath)) {
        fs.rmSync(readmePath, { force: true });
    }

    const hdcName = process.platform === 'win32' ? 'hdc.exe' : 'hdc';
    const hdcPath = path.join(basePath, hdcName);
    if (fs.existsSync(hdcPath) && process.platform !== 'win32') {
        try {
            const stats = fs.statSync(hdcPath);
            fs.chmodSync(hdcPath, stats.mode | 0o111);
            console.log(`[prebuild] hdc 已解压至 ${basePath}，已设置可执行权限`);
        } catch (err) {
            console.warn(`[prebuild] 无法为 hdc 设置可执行权限:`, err.message);
        }
    } else if (fs.existsSync(hdcPath)) {
        console.log(`[prebuild] hdc 已解压至 ${basePath}`);
    }

    flattenToolDirToParent(DIST_TOOLS_BIN_DIR, 'hdc');
    console.log(`[prebuild] hdc 已置于 ${DIST_TOOLS_BIN_DIR}`);
}

function cleanupTraceStreamerBinary(basePath) {
    // 首先为 trace_streamer_mac 和 trace_streamer_linux 添加可执行权限
    // 在删除文件之前设置权限，确保即使文件被保留也能正确设置权限
    const executableFiles = ['trace_streamer_mac', 'trace_streamer_linux'];
    executableFiles.forEach(fileName => {
        const filePath = path.join(basePath, fileName);
        if (fs.existsSync(filePath)) {
            try {
                const stats = fs.statSync(filePath);
                // 添加可执行权限：所有者、组、其他用户都有执行权限
                const newMode = stats.mode | 0o111; // 0o111 = 0b001001001 (rwxrwxrwx 中的 x)
                fs.chmodSync(filePath, newMode);
                console.log(`Added executable permission to: ${fileName} (mode: ${newMode.toString(8)})`);
            } catch (err) {
                console.warn(`Failed to set executable permission for ${fileName}:`, err.message);
            }
        }
    });

    const platformKeepMap = {
        win32: 'trace_streamer_windows.exe',
        darwin: 'trace_streamer_mac',
        linux: 'trace_streamer_linux'
    };
    const keepFile = platformKeepMap[process.platform];
    if (!keepFile) {
        return;
    }

    TRACE_STREAMER_BIN.forEach(fileName => {
        if (fileName !== keepFile) {
            const targetPath = path.join(basePath, fileName);
            if (fs.existsSync(targetPath)) {
                fs.rmSync(targetPath, { recursive: true, force: true });
            }
        }
    });

    if (process.platform !== 'darwin') {
        const libPath = path.join(basePath, 'lib');
        if (fs.existsSync(libPath)) {
            fs.rmSync(libPath, { recursive: true, force: true });
        }
    }

    flattenToolDirToParent(DIST_TOOLS_BIN_DIR, 'trace_streamer_binary');
}

// 注意：cleanupHilogtool函数已废弃，因为现在hilogtool通过copyHilogtool函数处理，
// 只复制当前平台的二进制文件，不需要清理其他平台的文件
function cleanupHilogtool(basePath) {
    // 根据操作系统保留对应的 hilogtool 可执行文件
    const platformKeepMap = {
        win32: 'hilogtool.exe',
        darwin: 'hilogtool',  // macOS
        linux: 'hilogtool'
    };
    const keepFile = platformKeepMap[process.platform];
    if (!keepFile) {
        return;
    }

    // 新的目录结构：hilogtool.zip 解压后包含 linux/、mac/、windows/ 子目录
    const platformDirMap = {
        win32: 'windows',
        darwin: 'mac',
        linux: 'linux'
    };
    const keepPlatformDir = platformDirMap[process.platform];

    // 删除不需要的平台目录
    const platforms = ['linux', 'mac', 'windows'];
    platforms.forEach(platformDir => {
        if (platformDir !== keepPlatformDir) {
            const targetPath = path.join(basePath, platformDir);
            if (fs.existsSync(targetPath)) {
                fs.rmSync(targetPath, { recursive: true, force: true });
                console.log(`Removed unnecessary hilogtool platform directory: ${platformDir}`);
            }
        }
    });

    // 将保留的平台文件移动到上级目录
    const keepDir = path.join(basePath, keepPlatformDir);
    const keepFilePath = path.join(keepDir, keepFile);
    const finalPath = path.join(basePath, keepFile);

    if (fs.existsSync(keepFilePath)) {
        fs.renameSync(keepFilePath, finalPath);
        console.log(`Moved hilogtool: ${keepFilePath} -> ${finalPath}`);
    }

    // 删除空的平台目录
    if (fs.existsSync(keepDir)) {
        const remainingItems = fs.readdirSync(keepDir);
        if (remainingItems.length === 0) {
            fs.rmdirSync(keepDir);
        }
    }

    // 为 Unix 系统文件添加可执行权限
    if (process.platform !== 'win32') {
        if (fs.existsSync(finalPath)) {
            try {
                const stats = fs.statSync(finalPath);
                const newMode = stats.mode | 0o111;
                fs.chmodSync(finalPath, newMode);
                console.log(`Added executable permission to: ${keepFile} (mode: ${newMode.toString(8)})`);
            } catch (err) {
                console.warn(`Failed to set executable permission for ${keepFile}:`, err.message);
            }
        }
    }

    flattenToolDirToParent(DIST_TOOLS_BIN_DIR, 'hilogtool');
}

unzipFile('trace_streamer_binary.zip', 'trace_streamer_binary');
unzipFile('hilogtool.zip', 'hilogtool');
unzipHdcBundle();

// xvm 和 web 放到 perf_testing/resource，供 PyInstaller 打包（避免 dist 被清理导致资源丢失）
function unzipToPerfTestingResource(zipFile, subfolder) {
    try {
        ensurePerfTestingResourceDir();
        const zipPath = path.join(__dirname, '../third-party', zipFile);
        const extractPath = path.join(PERF_TESTING_RESOURCE_DIR, subfolder);
        if (fs.existsSync(extractPath)) {
            return;
        }
        const zip = new AdmZip(zipPath);
        zip.extractAllTo(PERF_TESTING_RESOURCE_DIR, true);
    } catch (error) {
        console.error(`Error extracting ${zipFile} to perf_testing/resource:`, error.message);
    }
}
unzipToPerfTestingResource('xvm.zip', 'xvm');
copyFile('third-party/report.html', 'perf_testing/resource/web/hiperf_report_template.html');
