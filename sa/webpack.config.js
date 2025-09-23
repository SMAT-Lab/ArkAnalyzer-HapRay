const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const version = require('./package.json').version;

class PackPlugin {
    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            let dist = path.resolve(__dirname, '../perf_testing/hapray-sa');
            if (!fs.existsSync(dist)) {
                return;
            }

            const outputName = path.resolve(__dirname, `hapray-sa_v${version}.zip`);
            const outputZipStream = fs.createWriteStream(outputName);
            const archive = archiver('zip');
            archive.pipe(outputZipStream);

            fs.readdirSync(dist).forEach((filename) => {
                const realFile = path.resolve(dist, filename);
                if (fs.statSync(realFile).isDirectory()) {
                    archive.directory(realFile, filename);
                } else {
                    archive.file(realFile, { name: filename });
                }
            });

            archive.finalize();
        });
    }
}

module.exports = {
    target: 'node',
    mode: 'production',
    entry: './src/cli.ts',
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
        ],
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js'],
    },
    output: {
        filename: 'hapray-static.js',
        path: path.resolve(__dirname, '../perf_testing/hapray-sa'),
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                // 复制资源文件
                { from: 'res', to: 'res' },
                // 复制基本文件
                { from: 'README.md', to: 'README.md' },
                { from: 'package.json', to: 'package.json' },
                // 复制必要的node_modules依赖
                {
                    from: '../node_modules/handlebars',
                    to: 'node_modules/handlebars',
                },
                {
                    from: '../node_modules/jszip',
                    to: 'node_modules/jszip',
                },
                {
                    from: '../node_modules/exceljs',
                    to: 'node_modules/exceljs',
                },
                {
                    from: '../node_modules/commander',
                    to: 'node_modules/commander',
                },
                {
                    from: '../node_modules/@types/node',
                    to: 'node_modules/@types/node',
                },
            ],
        }),
        new PackPlugin(),
    ],
};
