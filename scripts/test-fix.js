#!/usr/bin/env node
/**
 * 验证修复是否成功的测试脚本
 */

const fs = require('fs');
const path = require('path');

console.log('\n🔍 验证修复结果\n');
console.log('='.repeat(80));

let allPassed = true;

// 测试1: 检查 requirements.txt 是否存在
console.log('\n[测试1] 检查 optimization_detector/requirements.txt');
const reqFile = path.join(__dirname, '../tools/optimization_detector/requirements.txt');
if (fs.existsSync(reqFile)) {
    const content = fs.readFileSync(reqFile, 'utf-8');
    const hasNumpy = content.includes('numpy>=2.0');
    const hasTensorflow = content.includes('tensorflow>=2.20.0');
    if (hasNumpy && hasTensorflow) {
        console.log('  ✅ requirements.txt 存在且包含必要依赖');
    } else {
        console.log('  ❌ requirements.txt 存在但缺少依赖');
        allPassed = false;
    }
} else {
    console.log('  ❌ requirements.txt 不存在');
    allPassed = false;
}

// 测试2: 检查所有 setup_env.py 是否包含新的错误处理逻辑
console.log('\n[测试2] 检查 setup_env.py 文件的修复');
const setupFiles = [
    'hapray-gui/setup_env.py',
    'tools/optimization_detector/setup_env.py',
    'tools/symbol_recovery/setup_env.py',
    'perf_testing/setup_env.py',
];

setupFiles.forEach(file => {
    const fullPath = path.join(__dirname, '..', file);
    if (fs.existsSync(fullPath)) {
        const content = fs.readFileSync(fullPath, 'utf-8');
        const hasErrorHandling = content.includes('sys.exit(1)') && 
                                 content.includes('❌ ERROR: No dependency file found');
        const hasHelper = content.includes('_has_project_dependencies');
        
        if (hasErrorHandling && hasHelper) {
            console.log(`  ✅ ${file} - 已修复`);
        } else {
            console.log(`  ❌ ${file} - 修复不完整`);
            if (!hasErrorHandling) console.log('     缺少错误处理逻辑');
            if (!hasHelper) console.log('     缺少辅助函数');
            allPassed = false;
        }
    } else {
        console.log(`  ❌ ${file} - 文件不存在`);
        allPassed = false;
    }
});

// 测试3: 检查 verify-build.js 是否存在
console.log('\n[测试3] 检查 verify-build.js');
const verifyScript = path.join(__dirname, 'verify-build.js');
if (fs.existsSync(verifyScript)) {
    const content = fs.readFileSync(verifyScript, 'utf-8');
    const hasOptDetector = content.includes('opt-detector');
    const hasSymbolRecovery = content.includes('symbol-recovery');
    if (hasOptDetector && hasSymbolRecovery) {
        console.log('  ✅ verify-build.js 存在且完整');
    } else {
        console.log('  ❌ verify-build.js 存在但不完整');
        allPassed = false;
    }
} else {
    console.log('  ❌ verify-build.js 不存在');
    allPassed = false;
}

// 测试4: 检查 package.json 是否包含 verify 脚本
console.log('\n[测试4] 检查 package.json');
const packageJson = path.join(__dirname, '../package.json');
if (fs.existsSync(packageJson)) {
    const content = JSON.parse(fs.readFileSync(packageJson, 'utf-8'));
    const hasVerify = content.scripts && content.scripts.verify;
    const releaseIncludesVerify = content.scripts.release && 
                                  content.scripts.release.includes('npm run verify');
    
    if (hasVerify && releaseIncludesVerify) {
        console.log('  ✅ package.json 已正确配置');
        console.log(`     verify: ${content.scripts.verify}`);
        console.log(`     release: ${content.scripts.release}`);
    } else {
        console.log('  ❌ package.json 配置不完整');
        if (!hasVerify) console.log('     缺少 verify 脚本');
        if (!releaseIncludesVerify) console.log('     release 未集成 verify');
        allPassed = false;
    }
} else {
    console.log('  ❌ package.json 不存在');
    allPassed = false;
}

// 最终结果
console.log('\n' + '='.repeat(80));
if (allPassed) {
    console.log('\n✅ 所有测试通过！修复成功！\n');
    console.log('下一步操作:');
    console.log('  1. 清理环境: npm run clean --ws && rm -rf dist/');
    console.log('  2. 测试安装: npm install');
    console.log('  3. 测试构建: npm run build');
    console.log('  4. 验证产物: npm run verify');
    console.log('  5. 提交代码: git add . && git commit -m "fix: resolve P0 build issues"\n');
    process.exit(0);
} else {
    console.log('\n❌ 部分测试失败，请检查上述错误\n');
    process.exit(1);
}

