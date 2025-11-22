const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const { PreservePermissionsPlugin, PackPlugin } = require('../../scripts/webpack_plugin');
const version = require('./package.json').version;

module.exports = {
    target: 'node',
    mode: 'production',
    entry: './webpack-entry.js', // 虚拟入口文件
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        // 使用 CopyPlugin 拷贝文件到 dist/tools 目录
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'dist/symbol-recovery'),
                    to: path.resolve(__dirname, '../../dist/tools/symbol-recovery'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'README.md'),
                    to: path.resolve(__dirname, '../../dist/tools/symbol-recovery/README.md'),
                    noErrorOnMissing: true,
                },
                { from: path.resolve(__dirname, 'plugin.json'), to: path.resolve(__dirname, '../../dist/tools/symbol-recovery/plugin.json') },
            ],
        }),
        // 保持文件权限插件：在文件拷贝后保持可执行权限
        new PreservePermissionsPlugin({
            mappings: [
                {
                    from: path.resolve(__dirname, 'dist/symbol-recovery/symbol-recovery'),
                    to: path.resolve(__dirname, '../../dist/tools/symbol-recovery/symbol-recovery'),
                },
            ],
        }),
        // 使用 PackPlugin 创建 zip 文件
        new PackPlugin({
            zipName: 'symbol-recovery',
            version: version,
            sourceDir: 'dist/symbol-recovery',
            additionalFiles: [
                '../../dist/tools/trace_streamer_binary',
                'README.md'
            ],
            mergeAdditionalDirectories: true // symbol-recovery 需要合并目录内容到 zip 根目录
        }),
    ],
};

