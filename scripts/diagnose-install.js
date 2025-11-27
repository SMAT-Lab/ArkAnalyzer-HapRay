#!/usr/bin/env node
/**
 * 诊断npm install的postinstall执行情况
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('\n🔍 诊断 npm install 的 postinstall 执行\n');
console.log('='.repeat(80));

const workspaces = [
    'web',
    'tools/static_analyzer',
    'hapray-gui',
    'tools/optimization_detector',
    'tools/symbol_recovery',
    'perf_testing',
];

console.log('\n[1] 检查各workspace的package.json配置\n');

workspaces.forEach(ws => {
    const pkgPath = path.join(__dirname, '..', ws, 'package.json');
    if (!fs.existsSync(pkgPath)) {
        console.log(`❌ ${ws}: package.json不存在`);
        return;
    }
    
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
    const hasPostinstall = pkg.scripts && pkg.scripts.postinstall;
    const hasSetup = pkg.scripts && pkg.scripts.setup;
    
    console.log(`${hasPostinstall ? '✓' : '✗'} ${ws}:`);
    if (hasPostinstall) {
        console.log(`   postinstall: ${pkg.scripts.postinstall}`);
    }
    if (hasSetup) {
        console.log(`   setup: ${pkg.scripts.setup}`);
    }
    if (!hasPostinstall && !hasSetup) {
        console.log(`   (无postinstall脚本)`);
    }
});

console.log('\n[2] 检查Python模块的.venv是否存在\n');

const pythonWorkspaces = [
    'hapray-gui',
    'tools/optimization_detector',
    'tools/symbol_recovery',
    'perf_testing',
];

pythonWorkspaces.forEach(ws => {
    const venvPath = path.join(__dirname, '..', ws, '.venv');
    const exists = fs.existsSync(venvPath);
    console.log(`${exists ? '✓' : '✗'} ${ws}/.venv ${exists ? '存在' : '不存在'}`);
});

console.log('\n[3] 检查Python依赖文件是否存在\n');

const dependencyFiles = [
    { ws: 'hapray-gui', file: 'requirements.txt' },
    { ws: 'tools/optimization_detector', file: 'requirements.txt' },
    { ws: 'tools/optimization_detector', file: 'pyproject.toml' },
    { ws: 'tools/symbol_recovery', file: 'requirements.txt' },
    { ws: 'tools/symbol_recovery', file: 'pyproject.toml' },
    { ws: 'perf_testing', file: 'requirements.txt' },
];

dependencyFiles.forEach(({ws, file}) => {
    const filePath = path.join(__dirname, '..', ws, file);
    const exists = fs.existsSync(filePath);
    console.log(`${exists ? '✓' : '✗'} ${ws}/${file} ${exists ? '存在' : '不存在'}`);
});

console.log('\n[4] 检查关键Python包是否已安装\n');

pythonWorkspaces.forEach(ws => {
    const venvPython = process.platform === 'win32' 
        ? path.join(__dirname, '..', ws, '.venv', 'Scripts', 'python.exe')
        : path.join(__dirname, '..', ws, '.venv', 'bin', 'python');
    
    if (!fs.existsSync(venvPython)) {
        console.log(`⚠ ${ws}: Python不存在于.venv中`);
        return;
    }
    
    // 检查关键包
    const packagesToCheck = {
        'hapray-gui': ['PySide6', 'pyinstaller'],
        'tools/optimization_detector': ['numpy', 'pandas', 'pyinstaller'],
        'tools/symbol_recovery': ['elftools', 'pandas', 'pyinstaller'],  // pyelftools包名，elftools导入名
        'perf_testing': ['numpy', 'pandas', 'pyinstaller'],
    };
    
    const packages = packagesToCheck[ws] || [];
    console.log(`\n  ${ws}:`);
    
    packages.forEach(pkg => {
        try {
            // pyinstaller是CLI工具，需要特殊检查
            if (pkg === 'pyinstaller') {
                const pyinstallerExe = process.platform === 'win32'
                    ? path.join(__dirname, '..', ws, '.venv', 'Scripts', 'pyinstaller.exe')
                    : path.join(__dirname, '..', ws, '.venv', 'bin', 'pyinstaller');
                if (fs.existsSync(pyinstallerExe)) {
                    console.log(`    ✓ ${pkg} 已安装`);
                } else {
                    console.log(`    ✗ ${pkg} 未安装`);
                }
                return;
            }

            // 其他包通过import检查
            const cmd = `"${venvPython}" -c "import ${pkg.replace('-', '_')}; print('OK')"`;
            execSync(cmd, { stdio: 'pipe' });
            console.log(`    ✓ ${pkg} 已安装`);
        } catch (error) {
            console.log(`    ✗ ${pkg} 未安装`);
        }
    });
});

console.log('\n[5] 检查npm install日志\n');

const npmLogDir = process.platform === 'win32' 
    ? path.join(process.env.APPDATA || '', 'npm-cache', '_logs')
    : path.join(process.env.HOME || '', '.npm', '_logs');

console.log(`日志目录: ${npmLogDir}`);

if (fs.existsSync(npmLogDir)) {
    const logFiles = fs.readdirSync(npmLogDir)
        .filter(f => f.endsWith('-debug.log') || f.endsWith('-debug-0.log'))
        .sort((a, b) => {
            const statA = fs.statSync(path.join(npmLogDir, a));
            const statB = fs.statSync(path.join(npmLogDir, b));
            return statB.mtime - statA.mtime;
        });
    
    if (logFiles.length > 0) {
        const latestLog = path.join(npmLogDir, logFiles[0]);
        console.log(`\n最新日志文件: ${logFiles[0]}`);
        console.log(`使用此命令查看: cat "${latestLog}" | grep -i "postinstall\\|setup\\|error"`);
    } else {
        console.log('未找到npm日志文件');
    }
} else {
    console.log('日志目录不存在');
}

console.log('\n' + '='.repeat(80));
console.log('\n💡 诊断建议:\n');

console.log('1. 如果.venv存在但包未安装:');
console.log('   → postinstall跳过了安装(因为.venv已存在)');
console.log('   → 解决方案: 删除.venv后重新npm install\n');

console.log('2. 如果requirements.txt不存在:');
console.log('   → setup_env.py会静默跳过安装');
console.log('   → 解决方案: 创建requirements.txt文件\n');

console.log('3. 如果postinstall报错但npm install成功:');
console.log('   → npm workspaces允许部分失败');
console.log('   → 解决方案: 修复setup_env.py让错误终止安装\n');

console.log('4. 测试postinstall是否正常:');
console.log('   → 删除所有.venv: rm -rf */.venv */*/.venv');
console.log('   → 重新安装: npm install');
console.log('   → 观察输出查找错误\n');

