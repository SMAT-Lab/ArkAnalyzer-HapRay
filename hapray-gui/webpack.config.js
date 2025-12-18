const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');

// 构建拷贝模式数组
const copyPatterns = [];

// Mac 平台时拷贝 run_macos.sh 文件
if (process.platform === 'darwin') {
    copyPatterns.push({
        from: path.resolve(__dirname, '../scripts/run_macos.sh'),
        to: path.resolve(__dirname, '../dist/run_macos.sh'),
        noErrorOnMissing: true,
    });
}

// 构建插件数组
const plugins = [];

// 只在有拷贝模式时才添加 CopyPlugin
if (copyPatterns.length > 0) {
    plugins.push(
        // 拷贝 run_macos.sh 到目标目录
        new CopyPlugin({
            patterns: copyPatterns,
        })
    );
}

// 确保 macOS 下 run_macos.sh 拷贝后仍然是可执行文件
plugins.push({
    apply: (compiler) => {
        compiler.hooks.afterEmit.tap('MakeRunMacosExecutable', () => {
            if (process.platform !== 'darwin') {
                return;
            }
            const dest = path.resolve(__dirname, '../dist/run_macos.sh');
            try {
                if (fs.existsSync(dest)) {
                    fs.chmodSync(dest, 0o755);
                }
            } catch (e) {
                // 这里静默失败即可，不影响构建
            }
        });
    },
});

module.exports = {
    target: 'node',
    mode: 'production',
    entry: './webpack-entry.js', // 虚拟入口文件
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: plugins,
};

