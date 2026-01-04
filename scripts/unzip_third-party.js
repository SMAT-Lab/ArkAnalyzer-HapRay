const AdmZip = require('adm-zip');
const path = require('path');
const fs = require('fs');
const copyFile = require('./copy_file');

const DIST_TOOLS_DIR = path.join(__dirname, '../dist/tools');
const TRACE_STREAMER_BIN = ['trace_streamer_linux', 'trace_streamer_mac', 'trace_streamer_windows.exe'];
const HILOGTOOL_BIN = ['hilogtool', 'hilogtool.exe'];

function ensureDistToolsDir() {
    if (!fs.existsSync(DIST_TOOLS_DIR)) {
        fs.mkdirSync(DIST_TOOLS_DIR, { recursive: true });
    }
}

function unzipFile(zipFile, output) {
    try {
        ensureDistToolsDir();
        const zipPath = path.join(__dirname, '../third-party', zipFile);
        const extractPath = path.join(DIST_TOOLS_DIR, output);
        if (fs.existsSync(extractPath)) {
            return;
        }

        const zip = new AdmZip(zipPath);
        zip.extractAllTo(DIST_TOOLS_DIR, true);

        if (output === 'trace_streamer_binary') {
            cleanupTraceStreamerBinary(extractPath);
        }
        if (output === 'hilogtool') {
            cleanupHilogtool(extractPath);
        }
    } catch (error) {
        console.log(error);
    }
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
}

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

    // 删除不需要的平台文件
    HILOGTOOL_BIN.forEach(fileName => {
        if (fileName !== keepFile) {
            const targetPath = path.join(basePath, fileName);
            if (fs.existsSync(targetPath)) {
                fs.rmSync(targetPath, { recursive: true, force: true });
                console.log(`Removed unnecessary hilogtool file: ${fileName}`);
            }
        }
    });

    // 为 Unix 系统文件添加可执行权限
    if (process.platform !== 'win32') {
        const toolPath = path.join(basePath, keepFile);
        if (fs.existsSync(toolPath)) {
            try {
                const stats = fs.statSync(toolPath);
                const newMode = stats.mode | 0o111;
                fs.chmodSync(toolPath, newMode);
                console.log(`Added executable permission to: ${keepFile} (mode: ${newMode.toString(8)})`);
            } catch (err) {
                console.warn(`Failed to set executable permission for ${keepFile}:`, err.message);
            }
        }
    }
}

unzipFile('trace_streamer_binary.zip', 'trace_streamer_binary');
unzipFile('xvm.zip', 'xvm');
unzipFile('hilogtool.zip', 'hilogtool');
copyFile('third-party/report.html', 'dist/tools/web/hiperf_report_template.html');
