const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const { PackPlugin } = require('../../scripts/webpack_plugin');
const version = require('./package.json').version;

// 构建拷贝模式数组
const copyPatterns = [
    {
        from: path.resolve(__dirname, 'README.md'),
        to: path.resolve(__dirname, '../../dist/tools/opt-detector/README.md'),
        noErrorOnMissing: true,
    },
    { 
        from: path.resolve(__dirname, 'plugin.json'), 
        to: path.resolve(__dirname, '../../dist/tools/opt-detector/plugin.json') 
    },
];

// Mac 平台时拷贝 run_macos.sh 文件
if (process.platform === 'darwin') {
    copyPatterns.push({
        from: path.resolve(__dirname, '../../scripts/run_macos.sh'),
        to: path.resolve(__dirname, '../../dist/tools/opt-detector/run_macos.sh'),
        noErrorOnMissing: true,
    });
}

module.exports = {
    target: 'node',
    mode: 'production',
    entry: './webpack-entry.js', // 虚拟入口文件
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        // 拷贝 README.md 和 plugin.json 到目标目录
        new CopyPlugin({
            patterns: copyPatterns,
        }),
        // 确保 macOS 下 run_macos.sh 拷贝后仍然是可执行文件
        {
            apply: (compiler) => {
                compiler.hooks.afterEmit.tap('MakeRunMacosExecutable', () => {
                    if (process.platform !== 'darwin') {
                        return;
                    }
                    const dest = path.resolve(__dirname, '../../dist/tools/opt-detector/run_macos.sh');
                    try {
                        fs.chmodSync(dest, 0o755);
                    } catch (e) {
                        // 这里静默失败即可，不影响构建
                    }
                });
            },
        },
        // 打包插件：创建 zip 文件
        new PackPlugin({
            zipName: 'opt-detector',
            sourceDir: '../dist/tools/opt-detector',
            version: version,
        }),
    ],
};

