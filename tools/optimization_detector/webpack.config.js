const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const { PreservePermissionsPlugin, PackPlugin } = require('../../scripts/webpack_plugin');
const version = require('./package.json').version;

/**
 * 跳过文件的函数：用于 opt-detector 的打包过滤
 */
function shouldSkipFile(filePath) {
    const skipExtensions = ['.inc', '.h', '.hpp', '.txt', '.md'];
    const skipPatterns = [
        /_internal[\\/]tensorflow[\\/]include/
    ];
    
    const ext = path.extname(filePath).toLowerCase();
    const shouldSkip = skipExtensions.includes(ext) || 
                      skipPatterns.some(pattern => pattern.test(filePath));
    
    return shouldSkip;
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
        // 使用 CopyPlugin 拷贝文件到 dist/tools 目录
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'dist/opt-detector'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector'),
                    noErrorOnMissing: true,
                    filter: (resourcePath) => {
                        // 使用 shouldSkipFile 函数过滤文件
                        return !shouldSkipFile(resourcePath);
                    },
                },
                {
                    from: path.resolve(__dirname, 'README.md'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector/README.md'),
                    noErrorOnMissing: true,
                },
                { from: path.resolve(__dirname, 'plugin.json'), to: path.resolve(__dirname, '../../dist/tools/opt-detector/plugin.json') },
            ],
        }),
        // 保持文件权限插件：在文件拷贝后保持可执行权限
        new PreservePermissionsPlugin({
            mappings: [
                {
                    from: path.resolve(__dirname, 'dist/opt-detector/opt-detector'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector/opt-detector'),
                },
            ],
        }),
        // 使用 PackPlugin 创建 zip 文件
        new PackPlugin({
            zipName: 'opt-detector',
            version: version,
            sourceDir: '../../dist/tools/opt-detector',
            additionalFiles: [
                'README.md'
            ],
            shouldSkipFile: shouldSkipFile // opt-detector 需要跳过某些文件
        }),
    ],
};

