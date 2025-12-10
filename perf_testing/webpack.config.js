const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const { PreservePermissionsPlugin } = require('../scripts/webpack_plugin');

module.exports = {
    target: 'node',
    mode: 'production',
    entry: './webpack-entry.js', // 虚拟入口文件
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        // 使用 CopyPlugin 拷贝文件到根目录的 dist
        // 将 dist/perf_testing 目录下的内容拷贝到 ../dist/tools/perf_testing
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'dist/perf-testing'),
                    to: path.resolve(__dirname, '../dist/tools/perf-testing'),
                    noErrorOnMissing: true,
                    globOptions: {
                        followSymbolicLinks: false,
                    },
                },
                { 
                    from: path.resolve(__dirname, 'plugin.json'), 
                    to: path.resolve(__dirname, '../dist/tools/perf-testing/plugin.json') 
                },
            ],
        }),
        new PreservePermissionsPlugin({
            mappings: [
                {
                    from: path.resolve(__dirname, 'dist/perf-testing'),
                    to: path.resolve(__dirname, '../dist/tools/perf-testing'),
                },
            ],
        }),
    ],
};

