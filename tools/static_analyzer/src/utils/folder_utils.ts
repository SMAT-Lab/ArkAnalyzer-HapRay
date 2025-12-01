/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { LOG_MODULE_TYPE, Logger } from 'arkanalyzer';
import * as fs from 'fs';
import * as path from 'path';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export function getFirstLevelFolders(dirPath: string): Array<string> {
    try {
        // 读取指定目录下的所有文件和文件夹
        const items = fs.readdirSync(dirPath);
        const folders: Array<string> = [];

        for (const item of items) {
            // 拼接完整路径
            const itemPath = path.join(dirPath, item);
            // 检查该路径是否为目录
            const stat = fs.statSync(itemPath);
            if (stat.isDirectory() && item !== 'report') {
                logger.info('Round path: ' + itemPath);
                folders.push(itemPath);
            }
        }

        return folders;
    } catch (error) {
        logger.error('Access directory :' + dirPath, error);
        return [];
    }
}

export function getSceneRoundsFolders(sceneDir: string): Array<string> {
    let sceneRoundsFolders: Array<string> = [];
    if (fs.existsSync(sceneDir) && checkPerfData(sceneDir)) {
        sceneRoundsFolders.push(sceneDir);
    } else {
        for (let index = 0; index < 5; index++) {
            const sceneRoundFolder = sceneDir + '_round' + index;
            if (fs.existsSync(sceneRoundFolder) && checkPerfData(sceneRoundFolder)) {
                sceneRoundsFolders.push(sceneRoundFolder);
            }
        }
    }
    return sceneRoundsFolders;
}

export function checkPerfData(dir: string): boolean {
    let hasPerfData = true;
    const hiperfDir = path.join(dir, 'hiperf');
    const stepDirs = getFirstLevelFolders(hiperfDir);
    if (stepDirs.length !== 0) {
        stepDirs.forEach((stepDir) => {
            const perfDataPath = path.join(stepDir, 'perf.data');
            if (!fs.existsSync(perfDataPath)) {
                hasPerfData = false;
            }
        });
    } else {
        hasPerfData = false;
    }
    return hasPerfData;
}

/**
 * 递归创建目录
 */
async function ensureDirectoryExists(dirPath: string): Promise<void> {
    if (fs.existsSync(dirPath)) {return;}

    await ensureDirectoryExists(path.dirname(dirPath));
    await fs.promises.mkdir(dirPath);
}

/**
 * 目录复制选项
 */
interface CopyOptions {
    overwrite?: boolean; // 是否覆盖已有文件，默认为 true
    preserveTimestamps?: boolean; // 是否保留文件时间戳，默认为 true
    filter?: (src: string, stats: fs.Stats) => boolean | Promise<boolean>; // 文件过滤函数
}

/**
 * 递归复制目录
 */
export async function copyDirectory(sourceDir: string, targetDir: string, options: CopyOptions = {}): Promise<void> {
    const { overwrite = true, preserveTimestamps = true, filter = () => true } = options;

    if (sourceDir === targetDir) {
        return;
    }

    if (!fs.existsSync(sourceDir)) {
        logger.error(`源目录不存在: ${sourceDir}`);
        return;
    }

    await ensureDirectoryExists(targetDir);

    // 兼容旧版 Node.js：先读取文件名列表，再逐个获取文件信息
    const fileNames = await fs.promises.readdir(sourceDir);

    for (const fileName of fileNames) {
        const sourcePath = path.join(sourceDir, fileName);
        const targetPath = path.join(targetDir, fileName);

        const stats = await fs.promises.stat(sourcePath);
        const shouldCopy = await filter(sourcePath, stats);
        if (!shouldCopy) {continue;}

        if (stats.isDirectory()) {
            await copyDirectory(sourcePath, targetPath, options);
        } else {
            await copyFile(sourcePath, targetPath, { overwrite, preserveTimestamps });
        }
    }
}

/**
 * 复制单个文件
 */
export async function copyFile(
    sourcePath: string,
    targetPath: string,
    options: { overwrite?: boolean; preserveTimestamps?: boolean } = {}
): Promise<void> {
    if (sourcePath === targetPath) {
        return;
    }

    const { overwrite = true, preserveTimestamps = true } = options;

    const targetExists = fs.existsSync(targetPath);

    if (targetExists && !overwrite) {
        logger.info(`跳过已有文件: ${targetPath}`);
        return;
    }

    await ensureDirectoryExists(path.dirname(targetPath));

    await fs.promises.copyFile(sourcePath, targetPath);
    logger.info(`复制文件: ${sourcePath} -> ${targetPath}`);

    if (preserveTimestamps) {
        const stat = await fs.promises.stat(sourcePath);
        await fs.promises.utimes(targetPath, stat.atime, stat.mtime);
    }
}

export async function checkPerfFiles(dirPath: string, summaryCount: number): Promise<boolean> {
    let hiperfDataCount = 0;
    const hiperfDir = path.join(dirPath, 'hiperf');
    const hiperfStepDirs = getFirstLevelFolders(hiperfDir);
    hiperfStepDirs.forEach((hiperfStepDir) => {
        const perfDataPath = path.join(hiperfStepDir, 'perf.data');
        if (fs.existsSync(perfDataPath)) {
            hiperfDataCount++;
        }
    });
    return hiperfDataCount === summaryCount;
}
