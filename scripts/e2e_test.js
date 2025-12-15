#!/usr/bin/env node

/**
 * ArkAnalyzer-HapRay 端到端测试脚本
 * 测试构建产物完整性和各个模块的基本功能
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const DIST_DIR = path.join(__dirname, '..', 'dist');
const TOOLS_DIR = path.join(DIST_DIR, 'tools');

// 测试资源目录（优先使用外部测试资源）
const TEST_PRODUCTS_DIR = path.join(__dirname, '..', 'tests');
const USE_EXTERNAL_RESOURCES = true;

// 输出目录
const OUTPUT_DIR = path.join(TEST_PRODUCTS_DIR, 'output');

// 需要检查的工具目录列表
const REQUIRED_TOOLS = [
    'opt-detector',
    'perf-testing',  // 对应 perf_testing
    'sa-cmd',        // 对应 static_analyzer
    'symbol-recovery',
    'trace_streamer_binary',
    'web',
    'xvm'
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
        const result = execSync(command, {
            stdio: options.silent ? 'pipe' : 'inherit',
            env: { ...process.env, ...options.env },
            ...options
        });
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
        path.join(TEST_PRODUCTS_DIR, 'resource', 'opt-detector', 'meituan.hap'),
        path.join('opt-detector', 'meituan.hap')
    );

    if (!fs.existsSync(testFile)) {
        console.log('⚠ 跳过 opt 模块实际测试：meituan.hap文件不存在');
        return { success: false, error: 'meituan.hap文件不存在' };
    }

    console.log('使用meituan.hap进行opt模块测试');

    try {
        const outputFile = path.join(OUTPUT_DIR, 'temp_opt_test.xlsx');
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
        console.error(`✗ opt 模块测试失败: ${error.message}`);
        return { success: false, error: error.message };
    }
}

/**
 * 测试静态分析模块的基本功能
 */
function testStaticModule() {
    const testFile = path.join(TEST_PRODUCTS_DIR, 'opt-detector', 'meituan.hap');

    if (!fs.existsSync(testFile)) {
        console.log('⚠ 跳过 static 模块实际测试：meituan.hap文件不存在');
        return { success: false, error: 'meituan.hap文件不存在' };
    }

    const outputDir = path.join(OUTPUT_DIR, 'static_test_output', 'meituan');

    try {
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        runCommand(`${EXECUTABLE} static -i "${testFile}" -o "${outputDir}"`, 'static 模块实际功能测试', { silent: false });

        const files = fs.readdirSync(outputDir);
        if (files.length >= 3) {
            console.log(`✓ static 模块实际功能测试成功 (生成${files.length}个文件)`);
            console.log(`输出文件保存在: ${outputDir}`);
            return { success: true };
        } else {
            console.log(`✗ static 模块输出文件不足 (需要>=3个，实际${files.length}个)`);
            return { success: false, error: `输出文件不足: ${files.length} < 3` };
        }
    } catch (error) {
        console.error(`✗ static 模块实际功能测试失败:`, error.message);
        return { success: false, error: error.message };
    }
}

/**
 * 获取reports目录下最大数字的文件夹
 */
function getLatestReportFolder(reportsDir) {
    if (!fs.existsSync(reportsDir)) return null;

    const folders = fs.readdirSync(reportsDir).filter(f => {
        const fullPath = path.join(reportsDir, f);
        return fs.statSync(fullPath).isDirectory() && /^\d+$/.test(f);
    });

    if (folders.length === 0) return null;

    const maxFolder = folders.sort((a, b) => parseInt(b) - parseInt(a))[0];
    return path.join(reportsDir, maxFolder);
}

/**
 * 移动perf命令生成的reports目录到tests/output目录下
 */
function moveReportsDirectory() {
    const reportsDir = path.join(__dirname, '..', 'reports');
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

/**
 * 测试perf命令
 */
function testPerfModule() {
    console.log('开始测试perf命令功能');

    try {
        const distTestCaseDir = path.join(DIST_DIR, 'tools', 'perf-testing', '_internal', 'hapray', 'testcases', 'com.sankuai.hmeituan');
        const distTestCaseFile = path.join(distTestCaseDir, 'PerfLoad_meituan_0010.json');
        const sourceTestCaseDir = path.join(__dirname, '..', 'perf_testing', 'hapray', 'testcases', 'com.sankuai.hmeituan');
        const sourceTestCaseFile = path.join(sourceTestCaseDir, 'PerfLoad_meituan_0010.json');
        const testCaseFile = fs.existsSync(distTestCaseFile) ? distTestCaseFile : sourceTestCaseFile;

        if (!fs.existsSync(testCaseFile)) {
            return { success: false, error: 'meituan_0010测试用例不存在' };
        }

        console.log(`发现meituan_0010测试用例，尝试执行perf命令...`);
        runCommand(`${EXECUTABLE} perf --run_testcases "PerfLoad_meituan_0010" --round 1`, 'perf 命令实际测试', { silent: false });
        console.log('✓ perf 命令执行成功');

        const reportsDir = moveReportsDirectory();
        if (reportsDir) {
            const latestFolder = getLatestReportFolder(reportsDir);
            if (latestFolder && fs.existsSync(path.join(latestFolder, 'hapray_report.html'))) {
                console.log('✓ perf 命令校验成功: hapray_report.html 存在');
                return { success: true };
            } else {
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

            // 校验 cache/llm_analysis_cache.json 中的对象数
            const cacheFile = path.join(__dirname, '..', 'cache', 'llm_analysis_cache.json');
            if (fs.existsSync(cacheFile)) {
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

/**
 * 主测试函数
 */
async function runE2ETests() {
    console.log('🚀 开始 ArkAnalyzer-HapRay 端到端测试\n');

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

        if (failedModules.length === 0) {
            console.log('\n🎉 所有模块测试通过！');
            process.exit(0);
        } else {
            console.log('\n⚠️  部分模块测试失败');
            process.exit(1);
        }

    } catch (error) {
        console.error('\n❌ 端到端测试失败:', error.message);
        console.error('请检查构建过程和配置。');
        process.exit(1);
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    runE2ETests();
}

module.exports = { runE2ETests, checkDirectoryExists, checkFileExists, runCommand, testModule };