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

import fs from 'fs';
import path from 'path';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { getTechStackConfigLoader } from '../config/techstack_config_loader';
import type { BinaryMagicEntry } from '../core/techstack/types';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

// From insight/utils/file-utils.ts
/**
 * 检查文件是否存在
 * @param filePath 文件路径
 * @returns 文件是否存在
 */
export function fileExists(filePath: string): boolean {
    try {
        return fs.existsSync(filePath);
    } catch {
        return false;
    }
}

/**
 * 确保目录存在
 * @param dirPath 目录路径
 */
export function ensureDirectoryExists(dirPath: string): void {
    if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
    }
}

export function getAllFiles(
    srcPath: string,
    filter: {
        exts?: Array<string>;
        names?: Array<string>;
        ignore?: Array<string>;
    },
    filenameArr: Array<string> = [],
    visited: Set<string> = new Set<string>()
): Array<string> {
    // 如果源目录不存在，直接结束程序
    if (!fs.existsSync(srcPath)) {
        logger.error('Input directory is not exist, please check!');
        return filenameArr;
    }

    // 获取src的绝对路径
    const realSrc = fs.realpathSync(srcPath);
    if (visited.has(realSrc)) {
        return filenameArr;
    }
    visited.add(realSrc);

    // 遍历src，判断文件类型
    fs.readdirSync(realSrc).forEach((filename) => {
        if (filter.ignore?.includes(filename)) {
            return;
        }
        // 拼接文件的绝对路径
        const realFile = path.resolve(realSrc, filename);

        // 如果是目录，递归提取
        try {
            if (fs.statSync(realFile).isDirectory()) {
                getAllFiles(realFile, filter, filenameArr, visited);
            } else {
                // 如果是文件，则判断其扩展名是否在给定的扩展名数组中
                if (filter.exts?.includes(path.extname(filename)) || filter.names?.includes(filename)) {
                    filenameArr.push(realFile);
                }
            }
        } catch (error) {
            logger.error(`getAllFiles fs.statSync error ${error}`);
        }
    });
    return filenameArr;
}



let cachedBinaryMagicNumbers: Array<BinaryMagicEntry> | null = null;

/**
 * 获取二进制魔数配置：从配置文件读取一次并缓存；配置缺失时返回空数组
 */
function getBinaryMagicNumbers(): Array<BinaryMagicEntry> {
    if (cachedBinaryMagicNumbers) {
        return cachedBinaryMagicNumbers;
    }
    try {
        const cfg = getTechStackConfigLoader().getConfig();
        if (Array.isArray(cfg.binaryMagicNumbers)) {
            cachedBinaryMagicNumbers = cfg.binaryMagicNumbers;
        } else {
            logger.warn('binaryMagicNumbers 未配置，二进制魔数检测将被跳过');
            cachedBinaryMagicNumbers = [];
        }
    } catch (error) {
        logger.error(`读取技术栈配置失败，将不使用魔数检测: ${error}`);
        cachedBinaryMagicNumbers = [];
    }
    return cachedBinaryMagicNumbers;
}

/**
 * 检测文件是否为二进制文件（仅基于文件内容）
 * @param content 文件内容
 * @returns true表示二进制文件，false表示文本文件
 */
export function isBinaryFile(content?: Buffer): boolean {
    // 只通过文件内容判断是否为二进制文件
    if (content && content.length > 0) {
        // 1. 检查二进制魔数
        for (const magic of getBinaryMagicNumbers()) {
            if (checkMagicNumber(content, magic.bytes, magic.offset)) {
                return true;
            }
        }

        // 2. 检查内容是否包含大量非文本字符
        if (containsNonTextCharacters(content)) {
            return true;
        }

        // 3. 内容看起来像文本
        return false;
    }

    // 4. 如果没有文件内容，无法判断，默认认为是文本文件
    return false;
}



/**
 * 检查魔数
 */
function checkMagicNumber(content: Buffer, magicBytes: Array<number>, offset: number): boolean {
    if (content.length < offset + magicBytes.length) {
        return false;
    }

    for (let i = 0; i < magicBytes.length; i++) {
        if (content[offset + i] !== magicBytes[i]) {
            return false;
        }
    }

    return true;
}

/**
 * 检查内容是否包含大量非文本字符
 * 采样前8KB内容进行检测
 */
function containsNonTextCharacters(content: Buffer): boolean {
    const sampleSize = Math.min(content.length, 8192); // 检查前8KB
    let nonTextCount = 0;
    let nullCount = 0;

    for (let i = 0; i < sampleSize; i++) {
        const byte = content[i];

        // NULL字节通常表示二进制文件
        if (byte === 0) {
            nullCount++;
            if (nullCount > 1) {
                return true; // 多个NULL字节，很可能是二进制文件
            }
        }

        // 检查是否为非文本字符
        // 文本字符范围：
        // - 0x09 (Tab)
        // - 0x0A (LF)
        // - 0x0D (CR)
        // - 0x20-0x7E (可打印ASCII)
        // - 0x80-0xFF (扩展ASCII/UTF-8)
        if (byte < 0x20 && byte !== 0x09 && byte !== 0x0A && byte !== 0x0D) {
            nonTextCount++;
        }
    }

    // 如果超过30%的字符是非文本字符，认为是二进制文件
    const nonTextRatio = nonTextCount / sampleSize;
    return nonTextRatio > 0.3;
}

/**
 * 获取文件类型的可读字符串（仅基于文件内容）
 * @param content 文件内容
 * @returns "Binary" 或 "Text"
 */
export function getFileTypeString(content?: Buffer): string {
    return isBinaryFile(content) ? 'Binary' : 'Text';
}