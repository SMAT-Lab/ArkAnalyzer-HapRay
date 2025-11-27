#!/usr/bin/env node
/**
 * 部署统一的setup_env.py到所有Python模块
 */

const fs = require('fs');
const path = require('path');

const SOURCE = path.join(__dirname, 'universal_setup_env.py');
const TARGETS = [
    'hapray-gui/setup_env.py',
    'tools/optimization_detector/setup_env.py',
    'tools/symbol_recovery/setup_env.py',
    'perf_testing/setup_env.py',
];

console.log('🚀 部署统一的setup_env.py\n');

if (!fs.existsSync(SOURCE)) {
    console.error(`❌ 源文件不存在: ${SOURCE}`);
    process.exit(1);
}

const content = fs.readFileSync(SOURCE, 'utf-8');

TARGETS.forEach(target => {
    const targetPath = path.join(__dirname, '..', target);
    
    // 备份原文件
    if (fs.existsSync(targetPath)) {
        const backupPath = targetPath + '.backup';
        fs.copyFileSync(targetPath, backupPath);
        console.log(`📦 备份: ${target} → ${target}.backup`);
    }
    
    // 写入新文件
    fs.writeFileSync(targetPath, content, 'utf-8');
    console.log(`✅ 部署: ${target}`);
});

console.log('\n✅ 部署完成！\n');
console.log('测试步骤:');
console.log('  1. 删除所有.venv: rm -rf */.venv */*/.venv');
console.log('  2. 运行安装: npm install');
console.log('  3. 验证依赖: node scripts/diagnose-install.js');
console.log('  4. 构建测试: npm run build\n');

