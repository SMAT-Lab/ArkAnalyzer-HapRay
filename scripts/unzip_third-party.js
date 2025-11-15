const AdmZip = require('adm-zip');
const path = require('path');
const fs = require('fs');
const copyFile = require('./copy_file');

const DIST_TOOLS_DIR = path.join(__dirname, '../dist/tools');
const TRACE_STREAMER_BIN = ['trace_streamer_linux', 'trace_streamer_mac', 'trace_streamer_windows.exe'];

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
    } catch (error) {
        console.log(error);
    }
}

function cleanupTraceStreamerBinary(basePath) {
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

unzipFile('trace_streamer_binary.zip', 'trace_streamer_binary');
unzipFile('xvm.zip', 'xvm');
copyFile('third-party/report.html', 'dist/tools/web/hiperf_report_template.html');
