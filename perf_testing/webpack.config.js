const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
    target: 'node',
    mode: 'production',
    entry: './webpack-entry.js', // 虚拟入口文件
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        // 拷贝 plugin.json 到目标目录
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'plugin.json'),
                    to: path.resolve(__dirname, '../dist/tools/perf-testing/plugin.json')
                },
            ],
        }),
    ],
};

