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
        // 将 dist/hapray 目录下的内容拷贝到 ../dist
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'dist/hapray/ArkAnalyzer-HapRay'),
                    to: path.resolve(__dirname, '../dist'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'dist/hapray/ArkAnalyzer-HapRay-GUI'),
                    to: path.resolve(__dirname, '../dist'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'dist/hapray/ArkAnalyzer-HapRay.exe'),
                    to: path.resolve(__dirname, '../dist'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'dist/hapray/ArkAnalyzer-HapRay-GUI.exe'),
                    to: path.resolve(__dirname, '../dist'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'dist/hapray/_internal'),
                    to: path.resolve(__dirname, '../dist/_internal'),
                    noErrorOnMissing: true,
                },
            ],
        }),
        // 保持文件权限插件：在文件拷贝后保持可执行权限
        new PreservePermissionsPlugin({
            mappings: [
                {
                    from: path.resolve(__dirname, 'dist/hapray/ArkAnalyzer-HapRay'),
                    to: path.resolve(__dirname, '../dist/ArkAnalyzer-HapRay'),
                },
                {
                    from: path.resolve(__dirname, 'dist/hapray/ArkAnalyzer-HapRay-GUI'),
                    to: path.resolve(__dirname, '../dist/ArkAnalyzer-HapRay-GUI'),
                },
            ],
        }),
    ],
};

