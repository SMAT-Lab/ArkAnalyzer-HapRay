import fs from 'fs';
import path from 'path';
import axios from 'axios';
import * as tar from 'tar';
import { Pkg } from '../src/deps/package_manager';
import Logger, { LOG_MODULE_TYPE, LOG_LEVEL } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
Logger.configure('arkanalyzer-toolbox.log', LOG_LEVEL.ERROR, LOG_LEVEL.INFO);

const TEMP = '.tmp';

/**
 * https://ohpm.openharmony.cn/ohpmweb/registry/oh-package/openapi/v1/search?condition=&pageNum=1&pageSize=50&sortedType=latest&isHomePage=false
 */
async function listOhpmPage(pageNum: number, username?: string, password?: string): Promise<string[]> {
    const url = `https://ohpm.openharmony.cn/ohpmweb/registry/oh-package/openapi/v1/search?condition=&pageNum=${pageNum}&pageSize=50&sortedType=latest&isHomePage=false`;
    const proxy = {
        host: 'proxy.huawei.com',
        port: 8080,
        auth: {
            username: username,
            password: password,
        },
    };
    let config = {};
    if (username && password) {
        config = { proxy: proxy };
    }

    const response = await axios.get(url, config);
    let pkgs: string[] = [];
    if (response.status === 200) {
        response.data.body.rows.forEach((data: { name: string }) => {
            pkgs.push(data.name);
        });
    }
    return pkgs;
}

async function parseTarball(tarballUrl: string, files: Set<string>): Promise<void> {
    let tarballName = tarballUrl.split('/').reverse()[0];
    let response = await axios.get(tarballUrl, { responseType: 'arraybuffer' });
    if (response.status !== 200) {
        return undefined;
    }
    fs.writeFileSync(path.join(TEMP, tarballName), response.data);
    tar.list({
        file: path.join(TEMP, tarballName),
        sync: true,
        onReadEntry: (entry) => {
            logger.info(`${entry.path}`);
            let matches = entry.path.match(/^package\/([\w\+\-\.\#\/]*)\.d\.(js|ts|ets|mjs|cjs)$/);
            if (matches) {
                files.add(matches[1]);
                return;
            }
            matches = entry.path.match(/^package\/([\w\+\-\.\#\/]*)\.(js|ts|ets|mjs|cjs)$/);
            if (matches) {
                files.add(matches[1]);
            }
        },
    });
}

async function getPkgInfo(pkgName: string): Promise<Pkg | undefined> {
    const url = 'https://ohpm.openharmony.cn/ohpm';
    let response = await axios.get(`${url}/${pkgName}`);
    if (response.status !== 200) {
        return undefined;
    }

    let pkg: Pkg = {
        name: pkgName,
        version: response.data['dist-tags'].latest,
        versions: Object.keys(response.data.versions),
        files: [],
    };
    pkg.main = response.data.versions[pkg.version].main;
    pkg.module = response.data.versions[pkg.version].module;
    pkg.types = response.data.versions[pkg.version].types;
    let files: Set<string> = new Set();

    for (const pkgVersion of Object.values<any>(response.data.versions)) {
        await parseTarball(pkgVersion.dist.tarball, files);
    }

    files.delete('BuildProfile');
    files.delete('hvigorfile');
    pkg.files = Array.from(files);

    return pkg;
}

async function main() {
    let pkgs: Pkg[] = [];
    let pageNum = 1;
    let pkgNames: string[] = [];
    fs.mkdirSync(TEMP, { recursive: true });
    do {
        pkgNames = await listOhpmPage(pageNum++);
        for (const pkgName of pkgNames) {
            let pkg = await getPkgInfo(pkgName);
            if (pkg) {
                pkgs.push(pkg);
            } else {
                logger.error(`get ohpm ${pkgName} fail.`);
            }
        }
    } while (pkgNames.length > 0);
    // fs.rmdirSync(TEMP, { recursive: true });
    fs.writeFileSync('ohpm.json', JSON.stringify(pkgs.sort((a, b) => a.name.localeCompare(b.name))));
}

(async function () {
    await main();
})();
