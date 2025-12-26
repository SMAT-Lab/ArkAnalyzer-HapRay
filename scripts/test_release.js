#!/usr/bin/env node

/**
 * 测试发布包脚本
 * 接收一个 HapRay 的 zip 包，解压后执行端到端测试
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');
const AdmZip = require('adm-zip');

// 读取命令行入参：node test_release.js <zip_file>
let ZIP_FILE = process.argv[2];

/**
 * 获取平台名称
 */
function getPlatformName() {
    const platform = os.platform();
    const platformMap = {
        'darwin': 'darwin',
        'win32': 'win32',
        'linux': 'linux'
    };
    return platformMap[platform] || platform;
}

/**
 * 获取架构名称
 */
function getArchName() {
    const arch = os.arch();
    const archMap = {
        'x64': 'x64',
        'arm64': 'arm64',
        'ia32': 'ia32',
        'arm': 'arm'
    };
    return archMap[arch] || arch;
}

/**
 * 查找默认的 zip 文件
 * 格式: ArkAnalyzer-HapRay-{platform}-{arch}-{version}.zip
 */
function findDefaultZipFile() {
    try {
        // 读取 package.json 获取版本号
        const packageJsonPath = path.join(__dirname, '../package.json');
        if (!fs.existsSync(packageJsonPath)) {
            return null;
        }
        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        const version = packageJson.version;

        // 构建文件名
        const platform = getPlatformName();
        const arch = getArchName();
        const fileName = `ArkAnalyzer-HapRay-${platform}-${arch}-${version}.zip`;

        console.log(`🔍 正在查找默认 zip 文件: ${fileName}`);

        // 在多个位置查找
        const searchPaths = [
            path.join(__dirname, '..', fileName),           // 项目根目录
            path.join(__dirname, '..', '..', fileName),     // 项目父目录
            path.join(process.cwd(), fileName),            // 当前工作目录
            path.join(os.homedir(), fileName),            // 用户主目录
        ];

        for (const searchPath of searchPaths) {
            if (fs.existsSync(searchPath)) {
                const stat = fs.statSync(searchPath);
                if (stat.isFile()) {
                    console.log(`✓ 找到文件: ${searchPath}\n`);
                    return searchPath;
                }
            }
        }

        console.log(`ℹ️  未找到默认文件，已搜索以下位置:`);
        searchPaths.forEach(p => console.log(`   - ${p}`));
        console.log('');
        return null;
    } catch (error) {
        console.warn(`⚠️  查找默认 zip 文件时出错: ${error.message}\n`);
        return null;
    }
}

// 如果未提供 zip 文件，尝试查找默认文件
let zipPath;
if (!ZIP_FILE) {
    console.log('ℹ️  未提供 zip 文件路径，尝试查找默认文件...\n');
    zipPath = findDefaultZipFile();
    
    if (!zipPath) {
        console.error('❌ 错误: 未提供 zip 文件路径且未找到默认文件');
        console.error('   用法: node test_release.js <zip_file>');
        console.error('   或确保存在文件: ArkAnalyzer-HapRay-{platform}-{arch}-{version}.zip');
        process.exit(1);
    }
} else {
    // 验证 zip 文件是否存在
    zipPath = path.resolve(ZIP_FILE);
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
            console.log('   使用 tar 命令解压 (Windows)');
            if (!fs.existsSync(extractPath)) {
                fs.mkdirSync(extractPath, { recursive: true });
            }
            execSync(`tar -xf "${zipPath}" -C "${extractPath}"`, {
                stdio: 'inherit',
            });
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

        // 如果是 macOS，执行 run_macos.sh 移除隔离属性
        if (process.platform === 'darwin') {
            const runMacosScript = path.join(extractedDir, 'run_macos.sh');
            if (fs.existsSync(runMacosScript)) {
                console.log(`🍎 检测到 macOS 平台，执行 run_macos.sh 移除隔离属性...`);
                try {
                    execSync(`bash "${runMacosScript}"`, {
                        stdio: 'inherit',
                        cwd: extractedDir
                    });
                    console.log(`✓ macOS 隔离属性移除完成\n`);
                } catch (error) {
                    console.warn(`⚠️  执行 run_macos.sh 失败: ${error.message}`);
                    console.warn(`   继续执行后续测试...\n`);
                }
            } else {
                console.log(`ℹ️  未找到 run_macos.sh，跳过隔离属性移除\n`);
            }
        }

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
