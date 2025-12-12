const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const { PackPlugin } = require('../../scripts/webpack_plugin');
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
        // 拷贝 README.md 和 plugin.json 到目标目录
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'README.md'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector/README.md'),
                    noErrorOnMissing: true,
                },
                { from: path.resolve(__dirname, 'plugin.json'), to: path.resolve(__dirname, '../../dist/tools/opt-detector/plugin.json') },
            ],
        }),
        // 打包插件：创建 zip 文件
        new PackPlugin({
            zipName: 'opt-detector',
            sourceDir: '../dist/tools/opt-detector',
            version: version,
        }),
    ],
};

