const fs = require('fs');
const path = require('path');

const REQUIRED_FILES = [
    { path: 'dist/ArkAnalyzer-HapRay.exe', critical: true, desc: 'CLI入口' },
    { path: 'dist/ArkAnalyzer-HapRay-GUI.exe', critical: true, desc: 'GUI入口' },
    { path: 'dist/_internal', critical: true, desc: 'Python运行时' },
    { path: 'dist/tools/sa-cmd/hapray-sa-cmd.js', critical: true, desc: '静态分析' },
    { path: 'dist/tools/opt-detector/opt-detector.exe', critical: true, desc: '优化检测器' },
    { path: 'dist/tools/symbol-recovery/symbol-recovery.exe', critical: true, desc: '符号恢复' },
    { path: 'dist/tools/perf-testing/perf-testing.exe', critical: true, desc: '性能测试' },
    { path: 'dist/tools/web/report_template.html', critical: false, desc: 'Web模板' },
    { path: 'dist/tools/xvm', critical: false, desc: 'XVM工具' },
    { path: 'dist/tools/trace_streamer_binary', critical: false, desc: 'Trace Streamer' },
];

function checkFile(filePath) {
    const fullPath = path.resolve(__dirname, '..', filePath);
    if (!fs.existsSync(fullPath)) {
        return { exists: false, size: 'N/A' };
    }
    
    const stats = fs.statSync(fullPath);
    if (stats.isDirectory()) {
        return { exists: true, size: 'DIR' };
    }
    
    const sizeMB = (stats.size / 1024 / 1024).toFixed(2);
    return { exists: true, size: `${sizeMB} MB` };
}

function main() {
    console.log('\n🔍 Build Verification\n');
    console.log('='.repeat(80));
    
    let criticalMissing = [];
    let warnings = [];
    
    REQUIRED_FILES.forEach(file => {
        const result = checkFile(file.path);
        const status = result.exists ? '✓' : (file.critical ? '✗' : '⚠');
        const typeLabel = file.critical ? '[CRITICAL]' : '[OPTIONAL]';
        
        console.log(
            `${status} ${typeLabel.padEnd(12)} ${file.desc.padEnd(15)} ` +
            `${file.path} (${result.size})`
        );
        
        if (!result.exists) {
            if (file.critical) {
                criticalMissing.push(file);
            } else {
                warnings.push(file);
            }
        }
    });
    
    console.log('='.repeat(80));
    
    if (criticalMissing.length > 0) {
        console.error('\n❌ BUILD VERIFICATION FAILED!\n');
        console.error('Missing critical files:');
        criticalMissing.forEach(f => {
            console.error(`   - ${f.path} (${f.desc})`);
        });
        console.error('\nBuild cannot proceed with missing critical files.');
        console.error('Please check the build logs for errors.\n');
        process.exit(1);
    }
    
    if (warnings.length > 0) {
        console.warn('\n⚠️  Build completed with warnings:\n');
        console.warn('Missing optional files (non-critical):');
        warnings.forEach(f => {
            console.warn(`   - ${f.path} (${f.desc})`);
        });
        console.warn('');
    }
    
    console.log('\n✅ Build verification PASSED!\n');
}

try {
    main();
} catch (error) {
    console.error('\n❌ Verification script error:', error.message);
    console.error(error.stack);
    process.exit(1);
}

