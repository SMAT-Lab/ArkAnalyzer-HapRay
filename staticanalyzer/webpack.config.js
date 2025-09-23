const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const version = require('./package.json').version;

class PackPlugin {
    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            let dist = path.resolve(__dirname, '../perf_testing/hapray-staticanalyzer');
            if (!fs.existsSync(dist)) {
                return;
            }

            const outputName = path.resolve(__dirname, `hapray-staticanalyzer_v${version}.zip`);
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
        path: path.resolve(__dirname, '../perf_testing/hapray-staticanalyzer'),
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                { from: 'res', to: 'res' },
                { from: 'README.md', to: 'README.md' },
                { from: 'package.json', to: 'package.json' },
            ],
        }),
        new PackPlugin(),
    ],
};
