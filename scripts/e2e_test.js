#!/usr/bin/env node

/**
 * ArkAnalyzer-HapRay 端到端测试脚本
 * 测试构建产物完整性和各个模块的基本功能
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');
const ExcelJS = require('exceljs');
const ROOT_DIR = path.resolve(__dirname, '..');

// dist 目录：
// - 读取命令行入参：node e2e_test.js <dist_dir>
// - 如果未提供参数，默认使用当前工作目录下的 dist 目录
const DIST_DIR = path.resolve(process.argv[2]);
console.log(`DIST_DIR: ${DIST_DIR}`);

// 验证 DIST_DIR 是否存在
if (!fs.existsSync(DIST_DIR)) {
    console.error(`❌ 错误: dist 目录不存在: ${DIST_DIR}`);
    console.error('   用法: node e2e_test.js <dist_dir>');
    process.exit(1);
}

// 验证 DIST_DIR 是否为目录
const distStat = fs.statSync(DIST_DIR);
if (!distStat.isDirectory()) {
    console.error(`❌ 错误: 指定的路径不是目录: ${DIST_DIR}`);
    process.exit(1);
}

const TOOLS_DIR = path.join(DIST_DIR, 'tools');

// 测试资源目录（优先使用外部测试资源），位于打包根目录下
const TEST_PRODUCTS_DIR = path.join(DIST_DIR, 'tests');
const USE_EXTERNAL_RESOURCES = true;

// 输出目录
const OUTPUT_DIR = path.join(TEST_PRODUCTS_DIR, 'output');

// 基准结果目录
const ORIGIN_RESULT_DIR = path.join(TEST_PRODUCTS_DIR, 'origin-result');

// 需要检查的工具目录列表（web/xvm 已打包进 perf-testing，不再单独存在）
const REQUIRED_TOOLS = [
    'opt-detector',
    'perf-testing',  // 对应 perf_testing（含 web、xvm 资源）
    'sa-cmd',        // 对应 static_analyzer
    'symbol-recovery',
    'bin'
];

// 获取平台相关的可执行文件名
function getExecutableName() {
    const platform = process.platform;
    if (platform === 'win32') {
        return 'ArkAnalyzer-HapRay.exe';
    } else if (platform === 'darwin') {
        return 'ArkAnalyzer-HapRay';
    } else {
        // Linux 和其他 Unix-like 系统
        return 'ArkAnalyzer-HapRay';
    }
}

// 获取平台相关的可执行文件路径（用于命令调用）
function getExecutablePath() {
    const exeName = getExecutableName();
    const exePath = path.join(DIST_DIR, exeName);
    const platform = process.platform;

    if (platform === 'win32') {
        return `"${exePath}"`;
    } else {
        // Unix-like 系统需要确保可执行权限
        try {
            fs.accessSync(exePath, fs.constants.F_OK);
            // 尝试添加可执行权限
            fs.chmodSync(exePath, 0o755);
        } catch (error) {
            console.warn(`警告: 无法设置可执行权限: ${error.message}`);
        }
        return exePath;
    }
}

const EXECUTABLE = getExecutablePath();

const IS_MAC = process.platform === 'darwin';

function getMacOptMappedOutputFile(outputFilePath) {
    // tools/optimization_detector/cli.py:
    // ~/ArkAnalyzer-HapRay/optimization_detector/reports/<basename>
    const root = path.join(os.homedir(), 'ArkAnalyzer-HapRay', 'optimization_detector', 'reports');
    return path.join(root, path.basename(outputFilePath));
}

function getMacOptCacheDir() {
    // tools/optimization_detector/optimization_detector/file_info.py:
    // ~/ArkAnalyzer-HapRay/optimization_detector/files_results_cache
    return path.join(os.homedir(), 'ArkAnalyzer-HapRay', 'optimization_detector', 'files_results_cache');
}

function getMacStaticMappedOutputDir(outputDirPath) {
    // static 命令在 macOS 上经历两层映射：
    // 1) perf_testing/hapray/actions/static_action.py 先映射到 ~/ArkAnalyzer-HapRay/static-output/<basename>
    // 2) static_analyzer/src/utils/logger.ts 再映射到 ~/ArkAnalyzer-HapRay/static_analyzer/hap/<basename>
    // 最终产物以第二层为准。
    const root = path.join(os.homedir(), 'ArkAnalyzer-HapRay', 'static_analyzer', 'hap');
    return path.join(root, path.basename(outputDirPath));
}

function getMacPerfReportsRoot() {
    // perf_testing/hapray/core/common/path_utils.py: ~/ArkAnalyzer-HapRay/reports
    return path.join(os.homedir(), 'ArkAnalyzer-HapRay', 'reports');
}

function getMacSymbolRecoveryCacheFile() {
    // tools/symbol_recovery/core/utils/config.py:
    // ~/ArkAnalyzer-HapRay/symbol_recovery/cache/cache/llm_analysis_cache.json
    return path.join(
        os.homedir(),
        'ArkAnalyzer-HapRay',
        'symbol_recovery',
        'cache',
        'cache',
        'llm_analysis_cache.json'
    );
}

function getMacSymbolRecoveryOutputDir(desiredOutputDirPath) {
    // tools/symbol_recovery/main.py:
    // Config.get_output_dir() 在 darwin 下会固定落到 ~/ArkAnalyzer-HapRay/symbol_recovery/<out.name>
    const root = path.join(os.homedir(), 'ArkAnalyzer-HapRay', 'symbol_recovery');
    return path.join(root, path.basename(desiredOutputDirPath));
}

function getOptXlsxFileActual() {
    const desired = path.join(OUTPUT_DIR, 'temp_opt_test.xlsx');
    return IS_MAC ? getMacOptMappedOutputFile(desired) : desired;
}

function getStaticXlsxDirActual() {
    const desiredBaseDir = path.join(OUTPUT_DIR, 'static_test_output', 'test_suite-default-unsigned');
    const mappedBaseDir = getMacStaticMappedOutputDir(desiredBaseDir);
    if (!IS_MAC) return path.join(desiredBaseDir, 'test_suite-default-unsigned');
    return mappedBaseDir;
}

function collectFilesByExt(dirPath, ext, depth = 3) {
    const results = [];
    if (depth < 0 || !fs.existsSync(dirPath)) return results;

    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
        const p = path.join(dirPath, entry.name);
        if (entry.isDirectory()) {
            results.push(...collectFilesByExt(p, ext, depth - 1));
        } else if (entry.isFile() && entry.name.endsWith(ext)) {
            results.push(p);
        }
    }
    return results;
}

/**
 * 获取测试文件路径，优先使用外部测试资源
 */
function getTestFilePath(fallbackPath, externalSubPath = null) {
    if (USE_EXTERNAL_RESOURCES && externalSubPath) {
        const externalPath = path.join(TEST_PRODUCTS_DIR, externalSubPath);
        if (fs.existsSync(externalPath)) {
            console.log(`使用外部测试资源: ${externalPath}`);
            return externalPath;
        }
    }
    return fallbackPath;
}

/**
 * 检查目录是否存在
 */
function checkDirectoryExists(dirPath, description) {
    console.log(`检查 ${description}...`);
    if (!fs.existsSync(dirPath)) {
        throw new Error(`${description} 不存在: ${dirPath}`);
    }
    console.log(`✓ ${description} 存在`);
}

/**
 * 检查文件是否存在
 */
function checkFileExists(filePath, description) {
    console.log(`检查 ${description}...`);
    if (!fs.existsSync(filePath)) {
        throw new Error(`${description} 不存在: ${filePath}`);
    }
    console.log(`✓ ${description} 存在`);
}

/**
 * 执行命令并检查退出码
 */
function runCommand(command, description, options = {}) {
    console.log(`执行 ${description}...`);
    try {
        const execOptions = {
            stdio: options.silent ? 'pipe' : 'inherit',
            env: { ...process.env, ...options.env },
            cwd: DIST_DIR,
            ...options
        };
        // 不需要传递给 execSync 的自定义字段
        delete execOptions.silent;

        const result = execSync(command, execOptions);
        console.log(`✓ ${description} 成功`);
        return result;
    } catch (error) {
        console.error(`✗ ${description} 失败:`, error.message);
        throw error;
    }
}

/**
 * 测试单个模块的基本功能
 */
function testModule(command, moduleName, testFunc) {
    try {
        if (command !== 'update') {
            runCommand(`${EXECUTABLE} ${command} --help`, `${moduleName} 模块帮助`, { silent: true });
            console.log(`✓ ${moduleName} 模块加载正常`);
        }
        return testFunc ? testFunc() : { success: true };
    } catch (error) {
        console.error(`✗ ${moduleName} 模块测试失败:`, error.message);
        return { success: false, error: error.message };
    }
}

/**
 * 测试优化检测模块的基本功能
 */
function testOptModule() {
    const testFile = getTestFilePath(
        path.join(TEST_PRODUCTS_DIR, 'resource', 'opt-detector', 'test_suite-default-unsigned.hsp'),
        path.join('opt-detector', 'test_suite-default-unsigned.hsp')
    );

    if (!fs.existsSync(testFile)) {
        console.log('⚠ 跳过 opt 模块实际测试：test_suite-default-unsigned.hsp文件不存在');
        return { success: false, error: 'test_suite-default-unsigned.hsp文件不存在' };
    }

    console.log('使用test_suite-default-unsigned.hsp进行opt模块测试');

    try {
        // macOS 下 opt 会读取用户目录缓存，清理后可避免命中历史失败结果。
        if (IS_MAC) {
            const macOptCacheDir = getMacOptCacheDir();
            if (fs.existsSync(macOptCacheDir)) {
                fs.rmSync(macOptCacheDir, { recursive: true, force: true });
                console.log(`已清理 opt 缓存目录: ${macOptCacheDir}`);
            }
        }

        const outputFile = getOptXlsxFileActual();
        const command = `${EXECUTABLE} opt -i "${testFile}" -o "${outputFile}" -f excel --verbose`;

        console.log('执行opt命令进行完整分析...');
        runCommand(command, 'opt 模块功能测试', { silent: false });

        if (fs.existsSync(outputFile)) {
            console.log('✓ opt 模块实际功能测试成功');
            console.log(`输出文件保存在: ${outputFile}`);
            return { success: true };
        } else {
            console.log('✗ opt 命令执行完成但未生成预期输出文件');
            return { success: false, error: '未生成输出文件' };
        }
    } catch (error) {
        const msg = String(error && error.message ? error.message : error);
        console.error(`✗ opt 模块测试失败: ${msg}`);
        return { success: false, error: msg };
    }
}

/**
 * 测试静态分析模块的基本功能
 */
function testStaticModule() {
    const testFile = path.join(TEST_PRODUCTS_DIR, 'opt-detector', 'test_suite-default-unsigned.hsp');

    if (!fs.existsSync(testFile)) {
        console.log('⚠ 跳过 static 模块实际测试：test_suite-default-unsigned.hsp文件不存在');
        return { success: false, error: 'test_suite-default-unsigned.hsp文件不存在' };
    }

    const outputDir = path.join(OUTPUT_DIR, 'static_test_output', 'test_suite-default-unsigned');
    const outputDirActual = IS_MAC ? getMacStaticMappedOutputDir(outputDir) : outputDir;

    try {
        if (IS_MAC && !fs.existsSync(outputDirActual)) {
            fs.mkdirSync(outputDirActual, { recursive: true });
        } else if (!IS_MAC && !fs.existsSync(outputDirActual)) {
            fs.mkdirSync(outputDirActual, { recursive: true });
        }

        runCommand(`${EXECUTABLE} static -i "${testFile}" -o "${outputDirActual}"`, 'static 模块实际功能测试', { silent: false });

        // macOS 下输出层级不稳定，Windows/Linux 保持原有目录结构判断逻辑。
        let files = [];
        if (IS_MAC) {
            files = collectFilesByExt(outputDirActual, '', 6);
        } else {
            const nestedDir = path.join(outputDirActual, 'test_suite-default-unsigned');
            const scanDir = fs.existsSync(nestedDir) ? nestedDir : outputDirActual;
            files = fs.readdirSync(scanDir).map((name) => path.join(scanDir, name));
        }
        if (files.length >= 3) {
            console.log(`✓ static 模块实际功能测试成功 (生成${files.length}个文件)`);
            console.log(`输出文件保存在: ${outputDirActual}`);
            return { success: true };
        } else {
            console.log(`✗ static 模块输出文件不足 (需要>=3个，实际${files.length}个)`);
            console.log(`输出文件: ${files.map((f) => path.relative(outputDirActual, f)).join(', ')}`);
            return { success: false, error: `输出文件不足: ${files.length} < 3` };
        }
    } catch (error) {
        console.error(`✗ static 模块实际功能测试失败:`, error.message);
        return { success: false, error: error.message };
    }
}

/**
 * 获取reports目录下最新的时间戳文件夹
 */
function getLatestReportFolder(reportsDir) {
    if (!fs.existsSync(reportsDir)) return null;

    const folders = fs.readdirSync(reportsDir).filter(f => {
        const fullPath = path.join(reportsDir, f);
        return fs.statSync(fullPath).isDirectory() && /^\d+$/.test(f);
    });

    if (folders.length === 0) return null;

    const maxFolder = folders.sort((a, b) => parseInt(b) - parseInt(a))[0];
    return path.join(reportsDir, maxFolder, 'PerfLoad_meituan_0010');
}

function getLatestNumericFolder(reportsDir) {
    if (!fs.existsSync(reportsDir)) return null;
    const folders = fs.readdirSync(reportsDir).filter(f => {
        const fullPath = path.join(reportsDir, f);
        return fs.statSync(fullPath).isDirectory() && /^\d+$/.test(f);
    });
    if (folders.length === 0) return null;
    return folders.sort((a, b) => parseInt(b) - parseInt(a))[0];
}

/**
 * 移动perf命令生成的reports目录到tests/output目录下
 */
function moveReportsDirectory() {
    const reportsDir = path.join(DIST_DIR, 'reports');
    const targetDir = path.join(OUTPUT_DIR, 'reports');

    try {
        if (fs.existsSync(reportsDir)) {
            console.log('正在移动perf测试结果...');

            if (fs.existsSync(targetDir)) {
                fs.rmSync(targetDir, { recursive: true, force: true });
            }

            fs.renameSync(reportsDir, targetDir);
            console.log(`✓ perf测试结果已移动到: ${targetDir}`);
            return targetDir;
        } else {
            console.log('⚠ reports目录不存在，跳过移动操作');
            return null;
        }
    } catch (error) {
        console.error('移动reports目录失败:', error.message);
        return null;
    }
}

function hasPerfMeituanTestcase() {
    const candidates = [
        // onedir
        path.join(DIST_DIR, 'tools', 'perf-testing', '_internal', 'hapray', 'testcases', 'com.sankuai.hmeituan', 'PerfLoad_meituan_0010.json'),
        // 开发源码目录（用于本地回退校验）
        path.join(ROOT_DIR, 'perf_testing', 'hapray', 'testcases', 'com.sankuai.hmeituan', 'PerfLoad_meituan_0010.json')
    ];
    return candidates.some((p) => fs.existsSync(p));
}

/**
 * 测试perf命令
 */
function testPerfModule() {
    console.log('开始测试perf命令功能');

    try {
        // onefile 下测试用例在运行时解包到临时目录，磁盘上通常看不到 _internal。
        // 因此仅做“可见路径存在”提示，不作为硬失败条件，避免误报。
        if (!hasPerfMeituanTestcase()) {
            console.warn('⚠ 未在可见目录找到 PerfLoad_meituan_0010.json（onefile 场景可忽略），继续执行 perf 命令...');
        }

        console.log(`发现meituan_0010测试用例，尝试执行perf命令...`);

        if (IS_MAC) {
            // macOS：perf 会强制写入用户目录 ~/ArkAnalyzer-HapRay/reports
            const reportsRoot = getMacPerfReportsRoot();
            if (!fs.existsSync(reportsRoot)) {
                fs.mkdirSync(reportsRoot, { recursive: true });
            }

            const beforeTimestamp = getLatestNumericFolder(reportsRoot);

            runCommand(
                `${EXECUTABLE} perf --run_testcases "PerfLoad_meituan_0010" --round 1`,
                'perf 命令实际测试',
                { silent: false }
            );
            console.log('✓ perf 命令执行成功');

            const afterTimestamp = getLatestNumericFolder(reportsRoot);
            const latestFolder = afterTimestamp ? path.join(reportsRoot, afterTimestamp, 'PerfLoad_meituan_0010') : null;
            if (latestFolder && fs.existsSync(path.join(latestFolder, 'report', 'hapray_report.html'))) {
                console.log('✓ perf 命令校验成功: hapray_report.html 存在');
                return { success: true };
            }

            console.log(`⚠ 查找路径: ${latestFolder ? path.join(latestFolder, 'report', 'hapray_report.html') : '未找到文件夹'}`);
            if (beforeTimestamp === afterTimestamp) {
                return { success: false, error: 'perf 未产生新的 reports 输出（时间戳未变化）' };
            }
            return { success: false, error: 'hapray_report.html 不存在' };
        }

        // 非 macOS：reports 会写入 dist/reports（保留原逻辑）
        const oldReportsDir = path.join(DIST_DIR, 'reports');
        if (fs.existsSync(oldReportsDir)) {
            fs.rmSync(oldReportsDir, { recursive: true, force: true });
        }

        runCommand(`${EXECUTABLE} perf --run_testcases "PerfLoad_meituan_0010" --round 1`, 'perf 命令实际测试', { silent: false });
        console.log('✓ perf 命令执行成功');

        // 检查是否生成了新的reports目录
        if (!fs.existsSync(oldReportsDir)) {
            console.log('⚠ perf命令执行完成但未生成reports目录（可能是设备连接失败）');
            return { success: false, error: 'perf命令未生成reports目录' };
        }

        const reportsDir = moveReportsDirectory();
        if (reportsDir) {
            const latestFolder = getLatestReportFolder(reportsDir);
            if (latestFolder && fs.existsSync(path.join(latestFolder, 'report', 'hapray_report.html'))) {
                console.log('✓ perf 命令校验成功: hapray_report.html 存在');
                return { success: true };
            } else {
                console.log(`⚠ 查找路径: ${latestFolder ? path.join(latestFolder, 'report', 'hapray_report.html') : '未找到文件夹'}`);
                return { success: false, error: 'hapray_report.html 不存在' };
            }
        } else {
            return { success: false, error: 'reports目录不存在' };
        }
    } catch (error) {
        console.error(`✗ perf 命令测试失败:`, error.message);
        return { success: false, error: error.message };
    }
}

/**
 * 测试update命令
 */
function testUpdateModule() {
    console.log('开始测试update命令功能');

    try {
        const reportDir = getTestFilePath(null, path.join('perf-testing', 'PerfLoad_meituan_0010'));

        if (!fs.existsSync(reportDir)) {
            return { success: false, error: '测试报告目录不存在' };
        }

        console.log('发现测试报告目录，尝试执行update命令...');
        const updateCommand = `${EXECUTABLE} update -r "${reportDir}" --mode 0`;
        runCommand(updateCommand, 'update 命令功能测试', { silent: false });
        console.log('✓ update 命令执行成功');

        const reportFile = path.join(reportDir, 'report', 'hapray_report.html');
        if (fs.existsSync(reportFile)) {
            console.log('✓ update 命令校验成功: hapray_report.html 存在');
            return { success: true };
        } else {
            return { success: false, error: 'hapray_report.html 不存在' };
        }
    } catch (error) {
        console.error(`✗ update 命令测试失败:`, error.message);
        return { success: false, error: error.message };
    }
}

/**
 * 测试符号恢复模块的基本功能
 */
function testSymbolRecoveryModule() {
    console.log('开始测试symbol-recovery模块功能');

    try {
        const htmlFile = path.join(TEST_PRODUCTS_DIR, 'symbol-recovery', 'hiperf_report.html');
        const perfDataFile = path.join(TEST_PRODUCTS_DIR, 'symbol-recovery', 'perf.data');
        const soDir = path.join(TEST_PRODUCTS_DIR, 'symbol-recovery');

        console.log(`使用外部测试资源:`);
        console.log(`  - HTML报告: ${htmlFile}`);
        console.log(`  - perf数据: ${perfDataFile}`);
        console.log(`  - SO目录: ${soDir}`);

        const hasHtmlFile = fs.existsSync(htmlFile);
        const hasPerfData = fs.existsSync(perfDataFile);
        const hasSoDir = fs.existsSync(soDir);

        if (!hasHtmlFile || !hasPerfData || !hasSoDir) {
            console.log('⚠ 测试文件不完整，跳过symbol-recovery实际功能测试');
            return { success: false, error: '测试文件不完整' };
        }

        console.log('发现完整的测试资源，尝试执行symbol-recovery命令...');
        const outputDir = path.join(OUTPUT_DIR, 'temp_symbol_recovery_output');

        try {
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }

            const command = `${EXECUTABLE} symbol-recovery --perf-data "${perfDataFile}" --html-input "${htmlFile}" --so-dir "${soDir}" --output "${outputDir}" --top-n 5`;
            console.log('使用perf.data + HTML + SO完整模式测试');

            runCommand(command, 'symbol-recovery 功能测试', { silent: false });

            console.log('✓ symbol-recovery 命令执行成功');
            console.log(`输出结果保存在: ${outputDir}`);

            const actualOutputDir = IS_MAC ? getMacSymbolRecoveryOutputDir(outputDir) : outputDir;
            const expectedExcel = path.join(actualOutputDir, 'event_count_top5_analysis.xlsx');
            const expectedHtml = path.join(actualOutputDir, 'event_count_top5_report.html');

            // 校验 cache/llm_analysis_cache.json 中的对象数（按多路径查找）
            const cacheCandidates = [
                path.join(DIST_DIR, 'ArkAnalyzer-HapRay.app', 'Contents', 'Resources', 'tools', 'symbol-recovery', 'cache', 'llm_analysis_cache.json'),
                path.join(DIST_DIR, 'tools', 'symbol-recovery', 'cache', 'llm_analysis_cache.json'),
                path.join(DIST_DIR, 'cache', 'llm_analysis_cache.json'),
                ...(IS_MAC ? [getMacSymbolRecoveryCacheFile()] : [])
            ];
            const cacheFile = cacheCandidates.find((p) => fs.existsSync(p));
            if (cacheFile) {
                const cacheData = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
                const objectCount = Object.keys(cacheData).length;
                if (objectCount === 3) {
                    console.log(`✓ symbol-recovery 校验成功: cache中有${objectCount}个对象`);
                    return { success: true };
                } else {
                    console.log(`✗ symbol-recovery 校验失败: cache中有${objectCount}个对象，期望3个`);
                    return { success: false, error: `cache对象数不匹配: ${objectCount} != 3` };
                }
            } else {
                console.log('✗ symbol-recovery 校验失败: cache文件不存在');
                console.log(`  已尝试路径: ${cacheCandidates.join(', ')}`);
                return { success: false, error: 'cache文件不存在' };
            }

        } catch (error) {
            console.error(`✗ symbol-recovery 功能测试失败: ${error.message}`);
            return { success: false, error: error.message };
        }

    } catch (error) {
        console.error(`✗ symbol-recovery 模块测试失败:`, error.message);
        return { success: false, error: error.message };
    }
}

/** ExcelJS 单元格转为可对比字符串（优先用显示文本，贴近旧 xlsx 的 sheet_to_json） */
function excelCellToString(cell) {
    if (!cell) return '';
    if (cell.text !== undefined && cell.text !== null && String(cell.text) !== '') {
        return String(cell.text);
    }
    const v = cell.value;
    if (v === null || v === undefined) return '';
    if (typeof v === 'object' && v !== null) {
        if (v.richText && Array.isArray(v.richText)) {
            return v.richText.map((r) => r.text || '').join('');
        }
        if (v.text !== undefined) return String(v.text);
        if (v.result !== undefined) return String(v.result);
        if (v.hyperlink !== undefined && v.text !== undefined) return String(v.text);
        if (v.formula !== undefined && v.result !== undefined) return String(v.result);
    }
    if (v instanceof Date) return v.toISOString();
    return String(v);
}

/** 将工作表转为二维数组（行主序，空单元格为 ''），对齐原 sheet_to_json({ header: 1, defval: '' }) */
function worksheetToRows(worksheet) {
    const rows = [];
    worksheet.eachRow({ includeEmpty: true }, (row) => {
        const arr = [];
        const n = row.cellCount;
        for (let c = 1; c <= n; c++) {
            arr.push(excelCellToString(row.getCell(c)));
        }
        rows.push(arr);
    });
    return rows;
}

async function readWorkbookSheetRows(filePath) {
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile(filePath);
    const names = wb.worksheets.map((ws) => ws.name);
    const sheets = {};
    for (const ws of wb.worksheets) {
        sheets[ws.name] = worksheetToRows(ws);
    }
    return { names, sheets };
}

/**
 * 对比两个xlsx文件内容是否相同（排除时间戳等动态字段）
 */
async function compareXlsxFiles(file1, file2, showDetails = false, skipRules = {}) {
    const wb1 = await readWorkbookSheetRows(file1);
    const wb2 = await readWorkbookSheetRows(file2);

    if (showDetails) {
        console.log(`  文件1: ${path.basename(file1)}`);
        console.log(`  文件2: ${path.basename(file2)}`);
        console.log(`  Sheet数量: ${wb1.names.length} vs ${wb2.names.length}`);
    }

    if (wb1.names.length !== wb2.names.length) {
        if (showDetails) console.log(`  ✗ Sheet数量不同`);
        return false;
    }

    for (let i = 0; i < wb1.names.length; i++) {
        const sheetName = wb1.names[i];
        if (showDetails) console.log(`  检查Sheet: ${sheetName}`);

        const sheet1 = wb1.sheets[sheetName];
        const sheet2 = wb2.sheets[wb2.names[i]];

        if (showDetails) console.log(`    行数: ${sheet1.length} vs ${sheet2.length}`);

        if (sheet1.length !== sheet2.length) {
            if (showDetails) console.log(`    ✗ 行数不同`);
            return false;
        }

        const sheetSkip = skipRules[sheetName] || {};

        for (let row = 0; row < sheet1.length; row++) {
            // 跳过指定的行（行号从0开始）
            if (sheetSkip.rows && sheetSkip.rows.includes(row)) continue;

            const row1 = sheet1[row];
            const row2 = sheet2[row];

            if (row1.length !== row2.length) {
                if (showDetails) console.log(`    ✗ 第${row + 1}行列数不同: ${row1.length} vs ${row2.length}`);
                return false;
            }

            for (let col = 0; col < row1.length; col++) {
                // 跳过指定的列（列号从0开始）
                if (sheetSkip.cols && sheetSkip.cols.includes(col)) continue;

                const val1 = String(row1[col] || '');
                const val2 = String(row2[col] || '');

                // 跳过时间戳格式（支持 - 和 / 分隔符）
                if (/\d{4}[-\/]\d{2}[-\/]\d{2}[T ]\d{2}:\d{2}:\d{2}/.test(val1) && /\d{4}[-\/]\d{2}[-\/]\d{2}[T ]\d{2}:\d{2}:\d{2}/.test(val2)) {
                    continue;
                }

                // 跳过hash值（32位或64位十六进制字符串）
                if (/^[a-f0-9]{32,64}$/i.test(val1) && /^[a-f0-9]{32,64}$/i.test(val2)) {
                    continue;
                }

                if (val1 !== val2) {
                    if (showDetails) {
                        console.log(`    ✗ 第${row + 1}行第${col + 1}列不同:`);
                        console.log(`      期望: "${val2.substring(0, 100)}${val2.length > 100 ? '...' : ''}"`);
                        console.log(`      实际: "${val1.substring(0, 100)}${val1.length > 100 ? '...' : ''}"`);
                    }
                    return false;
                }
            }
        }
    }

    return true;
}

/**
 * 获取static命令生成的最新xlsx文件
 */
function getStaticXlsxFile() {
    const staticDir = getStaticXlsxDirActual();
    if (!fs.existsSync(staticDir)) return null;

    if (IS_MAC) {
        // macOS 下 static 输出层级不稳定：可能直接产出，也可能在子目录中产出
        const candidates = collectFilesByExt(staticDir, '.xlsx', 4);
        if (candidates.length === 0) return null;
        candidates.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
        return candidates[0];
    }

    const files = fs.readdirSync(staticDir)
        .filter(f => f.endsWith('.xlsx'))
        .map(f => ({ name: f, path: path.join(staticDir, f), time: fs.statSync(path.join(staticDir, f)).mtime }))
        .sort((a, b) => b.time - a.time);
    return files.length > 0 ? files[0].path : null;
}

/**
 * 获取update命令生成的最新xlsx文件
 */
function getUpdateXlsxFile() {
    const reportDir = path.join(TEST_PRODUCTS_DIR, 'perf-testing', 'PerfLoad_meituan_0010', 'report');
    if (!fs.existsSync(reportDir)) return null;
    const files = fs.readdirSync(reportDir)
        .filter(f => f.startsWith('ecol_load_perf') && f.endsWith('.xlsx') && !f.endsWith('_techstack.xlsx'))
        .map(f => ({ name: f, path: path.join(reportDir, f), time: fs.statSync(path.join(reportDir, f)).mtime }))
        .sort((a, b) => b.time - a.time);
    return files.length > 0 ? files[0].path : null;
}

/**
 * 校验关键产物内容
 */
async function verifyArtifactsHash(results) {
    console.log('🔍 开始校验关键产物内容...\n');

    const artifacts = {
        opt: {
            actual: getOptXlsxFileActual(),
            expected: path.join(ORIGIN_RESULT_DIR, 'opt.xlsx')
        },
        update: {
            actual: getUpdateXlsxFile(),
            expected: path.join(ORIGIN_RESULT_DIR, 'update.xlsx')
        },
        static: {
            actual: getStaticXlsxFile(),
            expected: path.join(ORIGIN_RESULT_DIR, 'static.xlsx')
        }
    };

    let allMatch = true;

    for (const [key, files] of Object.entries(artifacts)) {
        if (!results[key] || !results[key].success) {
            console.log(`⊘ 跳过 ${key}: 测试未通过`);
            continue;
        }

        if (!files.actual || !fs.existsSync(files.actual)) {
            console.log(`⊘ 跳过 ${key}: 实际文件不存在`);
            continue;
        }

        if (!fs.existsSync(files.expected)) {
            console.log(`⊘ 跳过 ${key}: 基准文件不存在`);
            continue;
        }

        // 定义跳过规则
        let skipRules = {};
        if (key === 'update') {
            skipRules = {
                'ecol_load_hiperf_detail': { cols: [1, 4, 9] },  // 第10列（索引9）
                'ecol_load_step': { cols: [2, 4, 8] }      // 第3,5,9列（索引2,4,8）
            };
        } else if (key === 'static') {
            skipRules = {
                '分析摘要': { rows: [0, 1, 6, 7] },           // 第1,7,8行（索引0,6,7）
                '技术栈信息': { cols: [6, 7, 12, 13] }                // 第7列（索引6）
            };
        } else if (key === 'opt') {
            skipRules = {
                'optimization': { cols: [1, 13, 19, 24] }                       // 第2列（索引1）
            };
        }

        if (await compareXlsxFiles(files.actual, files.expected, true, skipRules)) {
            console.log(`✓ ${key}: 内容匹配`);
        } else {
            console.log(`✗ ${key}: 内容不匹配`);
            allMatch = false;
        }
    }

    if (!allMatch) {
        console.log('\n⚠️  检测到产物内容变化');
        return { success: false };
    }

    return { success: true };
}

/**
 * 主测试函数
 */
async function runE2ETests() {
    console.log('🚀 开始 ArkAnalyzer-HapRay 端到端测试\n');

    // 先下载/更新测试资源
    try {
        runCommand(`node ${path.join(__dirname, 'download_test_products.js')} "${DIST_DIR}"`, '下载测试资源', { silent: false });
    } catch (downloadError) {
        // macOS/CI 环境可能因网络限制无法拉取测试资源；若本地 dist/tests 已存在则继续执行。
        console.warn(`⚠ 下载测试资源失败：${downloadError.message}`);
        const optHsp = path.join(TEST_PRODUCTS_DIR, 'opt-detector', 'test_suite-default-unsigned.hsp');
        const symbolHtml = path.join(TEST_PRODUCTS_DIR, 'symbol-recovery', 'hiperf_report.html');
        if (!fs.existsSync(optHsp) || !fs.existsSync(symbolHtml) || !hasPerfMeituanTestcase()) {
            throw downloadError;
        }
        console.warn('⚠ 跳过下载：检测到 dist/tests 资源已存在，继续执行后续测试。');
    }

    // 配置 LLM 环境变量用于符号恢复模块测试
    console.log('🤖 配置 LLM 环境变量...');
    process.env.LLM_API_KEY = 'sk-14ccee5142d04e7fbbcda3418b715390';
    process.env.LLM_BASE_URL = 'https://api.deepseek.com/v1';
    process.env.LLM_MODEL = 'deepseek-chat';

    console.log('✓ LLM 环境变量配置完成：');
    console.log(`  - 模型名称: ${process.env.LLM_MODEL}`);
    console.log(`  - API 密钥: ${process.env.LLM_API_KEY ? '已设置' : '未设置'}`);
    console.log(`  - Base URL: ${process.env.LLM_BASE_URL}`);
    console.log('');

    const results = {};

    try {
        // 0. 确保输出目录存在
        if (!fs.existsSync(OUTPUT_DIR)) {
            fs.mkdirSync(OUTPUT_DIR, { recursive: true });
            console.log(`创建输出目录: ${OUTPUT_DIR}`);
        }

        // 1. 检查构建产物
        console.log('📦 检查构建产物...');

        checkDirectoryExists(DIST_DIR, 'dist 目录');
        checkFileExists(path.join(DIST_DIR, getExecutableName()), '主可执行文件');

        // 检查 tools 目录
        checkDirectoryExists(TOOLS_DIR, 'tools 目录');

        // 检查所有必需的工具目录
        for (const tool of REQUIRED_TOOLS) {
            checkDirectoryExists(path.join(TOOLS_DIR, tool), `${tool} 工具目录`);
        }

        console.log('✓ 所有必需的工具目录都存在\n');

        // 2. 测试主程序帮助信息
        console.log('🔧 测试主程序功能...');
        runCommand(`${EXECUTABLE} --help`, '主程序帮助信息', { silent: true });
        console.log('✓ 主程序运行正常\n');

        // 3. 并行测试各个模块
        console.log('🧪 并行测试各个模块...\n');

        const tests = [
            { key: 'opt', command: 'opt', name: '优化检测 (opt-detector)', func: testOptModule },
            { key: 'static', command: 'static', name: '静态分析 (sa-cmd)', func: testStaticModule },
            { key: 'perf', command: 'perf', name: '性能测试 (perf)', func: testPerfModule },
            { key: 'update', command: 'update', name: '报告更新 (update)', func: testUpdateModule },
            { key: 'symbol-recovery', command: 'symbol-recovery', name: '符号恢复 (symbol-recovery)', func: testSymbolRecoveryModule }
        ];

        await Promise.all(tests.map(async (test) => {
            console.log(`=== 测试 ${test.key} 模块 ===`);
            results[test.key] = await Promise.resolve(testModule(test.command, test.name, test.func));
            console.log('');
        }));

        // 4. 统计结果
        console.log('=' .repeat(60));
        console.log('📊 测试结果统计\n');

        const successModules = [];
        const failedModules = [];

        for (const [module, result] of Object.entries(results)) {
            if (result && result.success) {
                successModules.push(module);
                console.log(`✓ ${module}: 成功`);
            } else {
                failedModules.push(module);
                console.log(`✗ ${module}: 失败 - ${result ? result.error : '未知错误'}`);
            }
        }

        console.log('\n' + '=' .repeat(60));
        console.log(`成功: ${successModules.length}/${Object.keys(results).length}`);
        console.log(`失败: ${failedModules.length}/${Object.keys(results).length}`);

        // 5. 校验关键产物hash
        console.log('\n' + '=' .repeat(60));
        const hashVerification = await verifyArtifactsHash(results);

        if (failedModules.length === 0 && hashVerification.success) {
            console.log('🎉 所有模块测试通过，产物hash校验通过！');
            process.exit(0);
        } else {
            if (failedModules.length > 0) {
                console.log('⚠️  部分模块测试失败');
            }
            if (!hashVerification.success) {
                console.log('⚠️  产物hash校验失败');
            }
            process.exit(1);
        }

    } catch (error) {
        console.error('\n❌ 端到端测试失败:', error.message);
        console.error('请检查构建过程和配置。');
        process.exit(1);
    } finally {
        // 清理缓存目录
        const cacheDir = path.join(DIST_DIR, 'files_results_cache');
        if (fs.existsSync(cacheDir)) {
            fs.rmSync(cacheDir, { recursive: true, force: true });
            console.log('\n🧹 已清理缓存目录: files_results_cache');
        }
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    runE2ETests();
}

module.exports = { runE2ETests, checkDirectoryExists, checkFileExists, runCommand, testModule };