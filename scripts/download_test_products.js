#!/usr/bin/env node

/**
 * 下载测试工程脚本
 * 从 https://gitcode.com/B1A2/HapRayTestProducts.git 下载测试资源
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const TEST_PRODUCTS_REPO = 'https://gitcode.com/B1A2/HapRayTestProducts.git';
const TESTS_DIR = path.join(__dirname, '..', 'tests');

function downloadTestProducts() {
    try {
        console.log('正在下载测试工程资源...');

        // 确保 tests 目录存在
        if (!fs.existsSync(TESTS_DIR)) {
            fs.mkdirSync(TESTS_DIR, { recursive: true });
            console.log(`创建目录: ${TESTS_DIR}`);
        }

        // 检查是否已经存在 .git 目录（表示已经是一个 git 仓库）
        const gitDir = path.join(TESTS_DIR, '.git');
        if (fs.existsSync(gitDir)) {
            console.log('测试资源已存在，正在更新...');
            // 如果已经存在，则拉取最新代码
            execSync('git pull', { cwd: TESTS_DIR, stdio: 'inherit' });
        } else {
            console.log('正在克隆测试工程仓库...');
            // 如果不存在，则克隆仓库
            execSync(`git clone ${TEST_PRODUCTS_REPO} tests`, {
                cwd: path.join(__dirname, '..'),
                stdio: 'inherit'
            });
        }

        console.log('测试工程资源下载完成！');

        // 解压 trace.zip 文件
        extractTraceZip();
    } catch (error) {
        console.error('下载测试工程资源失败:', error.message);
        process.exit(1);
    }
}

/**
 * 解压 trace.zip 文件
 */
function extractTraceZip() {
    const traceZipPath = path.join(TESTS_DIR, 'perf-testing', 'PerfLoad_meituan_0010', 'htrace', 'step1', 'trace.zip');
    const extractDir = path.dirname(traceZipPath);

    try {
        console.log('正在检查 trace.zip 文件...');

        if (!fs.existsSync(traceZipPath)) {
            console.log('trace.zip 文件不存在，跳过解压步骤');
            return;
        }

        console.log(`发现 trace.zip 文件: ${traceZipPath}`);
        console.log(`准备解压到目录: ${extractDir}`);

        // 使用 PowerShell 的 Expand-Archive cmdlet 解压
        const extractCommand = `powershell -command "Expand-Archive -Path '${traceZipPath}' -DestinationPath '${extractDir}' -Force"`;
        console.log('正在解压 trace.zip...');

        execSync(extractCommand, { stdio: 'inherit' });

        // 删除原来的 zip 文件
        console.log('正在删除原来的 trace.zip 文件...');
        fs.unlinkSync(traceZipPath);

        console.log('✓ trace.zip 解压完成并已删除原文件');

    } catch (error) {
        console.error('解压 trace.zip 失败:', error.message);
        // 不终止整个流程，只是警告
        console.log('⚠ 解压失败，但下载过程将继续');
    }
}

if (require.main === module) {
    downloadTestProducts();
}

module.exports = { downloadTestProducts };