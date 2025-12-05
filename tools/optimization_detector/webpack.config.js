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
    
    // 不要跳过 jaraco/text 目录下的 .txt 文件（setuptools 需要）
    const isJaracoTextFile = /jaraco[\\/]text[\\/].*\.txt$/i.test(filePath) || 
                              /setuptools[\\/]_vendor[\\/]jaraco[\\/]text[\\/].*\.txt$/i.test(filePath);
    if (isJaracoTextFile) {
        return false;
    }

    const isTensorFlowFile = /_internal[\\/]tensorflow[\\/]/i.test(filePath);
    if (isTensorFlowFile) {
        return false; // 不跳过 TensorFlow 文件
    }
    
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
                    // 保持符号链接，不解析为实际文件
                    globOptions: {
                        followSymbolicLinks: false,
                    },
                    // filter: (resourcePath) => {
                    //     // 使用 shouldSkipFile 函数过滤文件
                    //     return !shouldSkipFile(resourcePath);
                    // },
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
        // 需要处理整个 _internal 目录，特别是 .so 文件和 Python 可执行文件
        new PreservePermissionsPlugin({
            mappings: [
                {
                    from: path.resolve(__dirname, 'dist/opt-detector'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector'),
                },
            ],
        })
    ],
};

