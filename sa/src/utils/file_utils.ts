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

/**
 * 常见的文本文件扩展名
 */
const TEXT_EXTENSIONS = new Set([
    // 代码文件
    '.js', '.ts', '.jsx', '.tsx', '.ets', '.json', '.xml', '.html', '.htm', '.css', '.scss', '.sass', '.less',
    '.java', '.kt', '.kts', '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.m', '.mm', '.swift',
    '.py', '.rb', '.php', '.go', '.rs', '.dart', '.lua', '.pl', '.sh', '.bash', '.zsh', '.fish',
    '.sql', '.graphql', '.proto', '.thrift',

    // 配置文件
    '.yaml', '.yml', '.toml', '.ini', '.conf', '.config', '.properties', '.env',
    '.gradle', '.maven', '.pom', '.npmrc', '.yarnrc', '.babelrc', '.eslintrc', '.prettierrc',

    // 文档文件
    '.txt', '.md', '.markdown', '.rst', '.adoc', '.tex', '.rtf',

    // 其他文本格式
    '.csv', '.tsv', '.log', '.diff', '.patch', '.gitignore', '.gitattributes',
    '.editorconfig', '.dockerignore', '.npmignore',

    // 脚本和批处理
    '.bat', '.cmd', '.ps1', '.vbs', '.applescript'
]);

/**
 * 常见的二进制文件扩展名
 */
const BINARY_EXTENSIONS = new Set([
    // 可执行文件和库
    '.exe', '.dll', '.so', '.dylib', '.a', '.lib', '.o', '.obj', '.elf',

    // 压缩包
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.jar', '.war', '.ear', '.hap', '.hsp', '.app',

    // 图片
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff', '.tif', '.psd', '.ai',

    // 音频
    '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.ape',

    // 视频
    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg',

    // 字体
    '.ttf', '.otf', '.woff', '.woff2', '.eot',

    // 数据库
    '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb',

    // 编译产物
    '.class', '.pyc', '.pyo', '.pyd', '.wasm', '.abc',

    // 文档（二进制格式）
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',

    // 其他二进制格式
    '.bin', '.dat', '.pak', '.dex', '.apk', '.ipa', '.dmg', '.iso', '.img'
]);

/**
 * 二进制文件魔数（文件头特征）
 */
const BINARY_MAGIC_NUMBERS: Array<{ bytes: Array<number>; offset: number }> = [
    // ELF (Linux可执行文件/库)
    { bytes: [0x7F, 0x45, 0x4C, 0x46], offset: 0 },

    // PE (Windows可执行文件)
    { bytes: [0x4D, 0x5A], offset: 0 },

    // Mach-O (macOS可执行文件) - 32位
    { bytes: [0xFE, 0xED, 0xFA, 0xCE], offset: 0 },
    { bytes: [0xCE, 0xFA, 0xED, 0xFE], offset: 0 },

    // Mach-O (macOS可执行文件) - 64位
    { bytes: [0xFE, 0xED, 0xFA, 0xCF], offset: 0 },
    { bytes: [0xCF, 0xFA, 0xED, 0xFE], offset: 0 },

    // ZIP/JAR/APK/HAP
    { bytes: [0x50, 0x4B, 0x03, 0x04], offset: 0 },
    { bytes: [0x50, 0x4B, 0x05, 0x06], offset: 0 },

    // PNG
    { bytes: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A], offset: 0 },

    // JPEG
    { bytes: [0xFF, 0xD8, 0xFF], offset: 0 },

    // GIF
    { bytes: [0x47, 0x49, 0x46, 0x38], offset: 0 },

    // PDF
    { bytes: [0x25, 0x50, 0x44, 0x46], offset: 0 },

    // Class文件
    { bytes: [0xCA, 0xFE, 0xBA, 0xBE], offset: 0 },

    // DEX文件
    { bytes: [0x64, 0x65, 0x78, 0x0A], offset: 0 }
];

/**
 * 检测文件是否为二进制文件
 * @param fileName 文件名
 * @param content 文件内容（可选）
 * @returns true表示二进制文件，false表示文本文件
 */
export function isBinaryFile(fileName: string, content?: Buffer): boolean {
    // 1. 首先根据扩展名判断
    const ext = getFileExtension(fileName);

    if (BINARY_EXTENSIONS.has(ext)) {
        return true;
    }

    if (TEXT_EXTENSIONS.has(ext)) {
        return false;
    }

    // 2. 如果有文件内容，检查魔数
    if (content && content.length > 0) {
        // 检查二进制魔数
        for (const magic of BINARY_MAGIC_NUMBERS) {
            if (checkMagicNumber(content, magic.bytes, magic.offset)) {
                return true;
            }
        }

        // 3. 检查内容是否包含大量非文本字符
        if (containsNonTextCharacters(content)) {
            return true;
        }
    }

    // 4. 默认情况：未知扩展名且无内容或内容看起来像文本，则认为是文本文件
    return false;
}

/**
 * 获取文件扩展名（小写，包含点）
 */
function getFileExtension(fileName: string): string {
    const lastDot = fileName.lastIndexOf('.');
    if (lastDot === -1 || lastDot === fileName.length - 1) {
        return '';
    }
    return fileName.substring(lastDot).toLowerCase();
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
 * 获取文件类型的可读字符串
 * @param fileName 文件名
 * @param content 文件内容（可选）
 * @returns "Binary" 或 "Text"
 */
export function getFileTypeString(fileName: string, content?: Buffer): string {
    return isBinaryFile(fileName, content) ? 'Binary' : 'Text';
}