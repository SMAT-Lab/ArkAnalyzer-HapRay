#!/usr/bin/env node

/**
 * 测试发布包脚本
 * 接收一个 HapRay 的 zip 包，解压后执行端到端测试
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const AdmZip = require('adm-zip');

// 读取命令行入参：node test_release.js <zip_file>
const ZIP_FILE = process.argv[2];

if (!ZIP_FILE) {
    console.error('❌ 错误: 未提供 zip 文件路径');
    console.error('   用法: node test_release.js <zip_file>');
    process.exit(1);
}

// 验证 zip 文件是否存在
const zipPath = path.resolve(ZIP_FILE);
if (!fs.existsSync(zipPath)) {
    console.error(`❌ 错误: zip 文件不存在: ${zipPath}`);
    process.exit(1);
}

// 验证是否为文件
const zipStat = fs.statSync(zipPath);
if (!zipStat.isFile()) {
    console.error(`❌ 错误: 指定的路径不是文件: ${zipPath}`);
    process.exit(1);
}

// 创建临时解压目录
const tempDir = path.join(__dirname, '../temp_release_test');
const extractDir = path.join(tempDir, path.basename(zipPath, path.extname(zipPath)));

/**
 * 解压 zip 文件（跨平台支持）
 */
function unzipFile(zipPath, extractPath) {
    console.log(`📦 开始解压 zip 文件...`);
    console.log(`   源文件: ${zipPath}`);
    console.log(`   目标目录: ${extractPath}`);

    try {
        // 如果目标目录已存在，先删除
        if (fs.existsSync(extractPath)) {
            console.log(`   清理已存在的目录: ${extractPath}`);
            fs.rmSync(extractPath, { recursive: true, force: true });
        }

        // 确保父目录存在
        const parentDir = path.dirname(extractPath);
        if (!fs.existsSync(parentDir)) {
            fs.mkdirSync(parentDir, { recursive: true });
        }

        // 根据平台选择解压方式
        const platform = process.platform;
        if (platform === 'win32') {
            // Windows 使用 AdmZip（不支持软链接，但至少能解压）
            console.log('   使用 PowerShell Expand-Archive 解压 (Windows)');
            execSync(
                `powershell -NoLogo -NoProfile -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${extractPath}' -Force"`,
                { stdio: 'inherit' }
            );
        } else {
            // macOS/Linux 使用系统 unzip 命令（保留软链接）
            console.log(`   使用系统 unzip 命令解压（${platform} 平台，保留软链接）`);
            execSync(`unzip -q "${zipPath}" -d "${extractPath}"`, {
                stdio: 'inherit',
            });
        }

        console.log(`✓ 解压成功`);
        return extractPath;
    } catch (error) {
        console.error(`✗ 解压失败: ${error.message}`);
        throw error;
    }
}

/**
 * 清理临时目录
 */
function cleanup() {
    try {
        if (fs.existsSync(tempDir)) {
            fs.rmSync(tempDir, { recursive: true, force: true });
            console.log(`🧹 已清理临时目录: ${tempDir}`);
        }
    } catch (error) {
        console.warn(`⚠️  清理临时目录失败: ${error.message}`);
    }
}

/**
 * 执行端到端测试
 */
function runE2ETest(distDir) {
    console.log(`\n🧪 开始执行端到端测试...`);
    console.log(`   测试目录: ${distDir}\n`);

    try {
        const e2eTestScript = path.join(__dirname, 'e2e_test.js');
        execSync(`node "${e2eTestScript}" "${distDir}"`, {
            stdio: 'inherit',
            cwd: __dirname
        });
        console.log(`\n✓ 端到端测试完成`);
    } catch (error) {
        console.error(`\n✗ 端到端测试失败`);
        throw error;
    }
}

/**
 * 主函数
 */
async function main() {
    console.log('🚀 开始测试发布包\n');
    console.log(`📁 Zip 文件: ${zipPath}\n`);

    try {
        // 1. 解压 zip 文件
        const extractedDir = unzipFile(zipPath, extractDir);

        // 验证解压后的目录是否存在
        if (!fs.existsSync(extractedDir)) {
            throw new Error(`解压后的目录不存在: ${extractedDir}`);
        }

        // 验证是否为目录
        const extractStat = fs.statSync(extractedDir);
        if (!extractStat.isDirectory()) {
            throw new Error(`解压后的路径不是目录: ${extractedDir}`);
        }

        console.log(`\n✓ 解压验证通过\n`);

        // 2. 执行端到端测试
        runE2ETest(extractedDir);

        console.log('\n🎉 测试完成！');
        process.exit(0);
    } catch (error) {
        console.error('\n❌ 测试失败:', error.message);
        process.exit(1);
    } finally {
        // 清理临时目录
        cleanup();
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    main();
}

module.exports = { main, unzipFile };
