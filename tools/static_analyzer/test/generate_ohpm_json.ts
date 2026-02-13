import fs from 'fs';
import path from 'path';
import axios from 'axios';
import * as tar from 'tar';
import { Ohpm } from '../src/config/types';
import Logger, { LOG_MODULE_TYPE, LOG_LEVEL } from '../src/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
Logger.configure('arkanalyzer-toolbox.log', LOG_LEVEL.ERROR, LOG_LEVEL.INFO, true);

// 扩展 Ohpm 接口，添加 fileName 属性
interface OhpmWithFileName extends Ohpm {
    fileName?: string;
}

const TEMP = '.ohpm';

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

async function parseTarball(tarballUrl: string, files: Set<string>, pkgName: string): Promise<string> {
    let tarballName = tarballUrl.split('/').reverse()[0];
    let response = await axios.get(tarballUrl, { responseType: 'arraybuffer' });
    if (response.status !== 200) {
        return '';
    }
    // 将 pkgName 添加到文件名中，替换 / 为 - 以避免路径问题
    const safePkgName = pkgName.replace(/\//g, '-');
    const fileName = `${safePkgName}-${tarballName}`;
    fs.writeFileSync(path.join(TEMP, fileName), response.data);
    tar.list({
        file: path.join(TEMP, fileName),
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
    return fileName;
}

async function getPkgInfo(pkgName: string): Promise<OhpmWithFileName | undefined> {
    const url = 'https://ohpm.openharmony.cn/ohpm';
    // 对 scoped package 进行 URL 编码：@scope/package -> @scope%2Fpackage
    const encodedPkgName = pkgName.replace(/\//g, '%2F');
    let response;
    try {
        response = await axios.get(`${url}/${encodedPkgName}`);
        if (response.status !== 200) {
            logger.error(`get ohpm ${pkgName} fail: HTTP ${response.status}`);
            return undefined;
        }
    } catch (error: any) {
        if (error.response) {
            logger.error(`get ohpm ${pkgName} fail: HTTP ${error.response.status} - ${error.response.statusText}`);
        } else if (error.request) {
            logger.error(`get ohpm ${pkgName} fail: Network error - ${error.message}`);
        } else {
            logger.error(`get ohpm ${pkgName} fail: ${error.message}`);
        }
        return undefined;
    }

    // 检查必要的数据字段
    if (!response.data || !response.data['dist-tags'] || !response.data['dist-tags'].latest) {
        logger.error(`get ohpm ${pkgName} fail: Missing dist-tags.latest`);
        return undefined;
    }

    const latestVersion = response.data['dist-tags'].latest;
    if (!response.data.versions || !response.data.versions[latestVersion]) {
        logger.error(`get ohpm ${pkgName} fail: Missing version ${latestVersion}`);
        return undefined;
    }

    const latestVersionData = response.data.versions[latestVersion];
    if (!latestVersionData.dist || !latestVersionData.dist.tarball) {
        logger.error(`get ohpm ${pkgName} fail: Missing dist.tarball for version ${latestVersion}`);
        return undefined;
    }

    let pkg: OhpmWithFileName = {
        name: pkgName,
        version: latestVersion,
        versions: Object.keys(response.data.versions),
        files: [],
    };
    pkg.main = latestVersionData.main;
    pkg.module = latestVersionData.module;
    pkg.types = latestVersionData.types;
    let files: Set<string> = new Set();

    // 只下载最新版本
    try {
        let fileName = await parseTarball(latestVersionData.dist.tarball, files, pkgName);
        pkg.fileName = fileName;
    } catch (error: any) {
        logger.error(`parse tarball for ${pkgName}@${latestVersion} fail: ${error.message}`);
        // 即使解析失败，也返回包信息（files 可能为空）
    }

    files.delete('BuildProfile');
    files.delete('hvigorfile');
    pkg.files = Array.from(files);

    return pkg;
}

async function main() {
    let pkgs: OhpmWithFileName[] = [];
    let pageNum = 1;
    let pkgNames: string[] = [];
    fs.mkdirSync(TEMP, { recursive: true });
    do {
        pkgNames = await listOhpmPage(pageNum++);
        for (const pkgName of pkgNames) {
            try {
                let pkg = await getPkgInfo(pkgName);
                if (pkg) {
                    pkgs.push(pkg);
                    logger.info(`Successfully processed ${pkgName}@${pkg.version}`);
                }
            } catch (error: any) {
                logger.error(`get ohpm ${pkgName} fail: ${error.message || error}`);
            }
        }
    } while (pkgNames.length > 0);
    // fs.rmdirSync(TEMP, { recursive: true });
    fs.writeFileSync('ohpm.json', JSON.stringify(pkgs.sort((a, b) => a.name.localeCompare(b.name))));
}

(async function () {
    await main();
})();
