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
import { FileType, MagicNumber } from '../types';
import { isValidFileType } from './types-config';

interface MagicNumbersConfig {
    magicNumbers: Array<{
        type: string;
        signature: number[];
        offset: number;
        description: string;
    }>;
    fileExtensions: Record<string, string>;
    mimeTypes: Record<string, string>;
}

let magicConfig: MagicNumbersConfig | null = null;

/**
 * 加载魔术字配置 - 只从JSON文件读取
 */
function loadMagicConfig(): MagicNumbersConfig {
    if (magicConfig) {
        return magicConfig;
    }

    // 使用toolbox的方法：先尝试当前目录，再尝试上级目录
    let resDir = path.join(__dirname, 'res');
    if (!fs.existsSync(resDir)) {
        resDir = path.join(__dirname, '../../res');
    }

    const configPath = path.join(resDir, 'magic-numbers.json');

    if (!fs.existsSync(configPath)) {
        throw new Error(`Magic numbers config file not found at: ${configPath}`);
    }

    const configData = fs.readFileSync(configPath, 'utf-8');
    magicConfig = JSON.parse(configData);
    return magicConfig!;
}

/**
 * 获取文件魔术字配置
 */
export function getMagicNumbers(): MagicNumber[] {
    const config = loadMagicConfig();
    return config.magicNumbers
        .filter(item => isValidFileType(item.type))
        .map(item => ({
            type: item.type as FileType,
            signature: item.signature,
            offset: item.offset,
            description: item.description
        }));
}

/**
 * 根据文件内容检测文件类型
 * @param buffer 文件内容缓冲区
 * @returns 检测到的文件类型
 */
export function detectFileTypeByMagic(buffer: Buffer): FileType {
    const magicNumbers = getMagicNumbers();

    for (const magic of magicNumbers) {
        const offset = magic.offset || 0;

        // 检查缓冲区是否足够大
        if (buffer.length < offset + magic.signature.length) {
            continue;
        }

        // 检查魔术字是否匹配
        let matches = true;
        for (let i = 0; i < magic.signature.length; i++) {
            if (buffer[offset + i] !== magic.signature[i]) {
                matches = false;
                break;
            }
        }

        if (matches) {
            return magic.type;
        }
    }

    return FileType.Unknown;
}

/**
 * 根据文件扩展名检测文件类型
 * @param fileName 文件名
 * @returns 检测到的文件类型
 */
export function detectFileTypeByExtension(fileName: string): FileType {
    const config = loadMagicConfig();
    const ext = fileName.toLowerCase().split('.').pop();

    if (ext && config.fileExtensions[ext]) {
        const fileType = config.fileExtensions[ext];
        if (isValidFileType(fileType)) {
            return fileType as FileType;
        }
    }

    return FileType.Unknown;
}

/**
 * 获取文件的MIME类型
 * @param fileName 文件名
 * @returns MIME类型
 */
export function getMimeType(fileName: string): string {
    const config = loadMagicConfig();
    const ext = path.extname(fileName).toLowerCase();

    return config.mimeTypes[ext] || 'application/octet-stream';
}

/**
 * 检测文件是否为文本文件
 * @param buffer 文件内容缓冲区
 * @returns 是否为文本文件
 */
export function isTextFile(buffer: Buffer): boolean {
    // 检查前1024字节是否包含非文本字符
    const sampleSize = Math.min(buffer.length, 1024);
    let nonTextChars = 0;
    
    for (let i = 0; i < sampleSize; i++) {
        const byte = buffer[i];
        
        // 允许的文本字符：可打印ASCII字符、换行符、制表符等
        if ((byte >= 32 && byte <= 126) || // 可打印ASCII
            byte === 9 ||  // Tab
            byte === 10 || // LF
            byte === 13 || // CR
            byte >= 128) { // UTF-8多字节字符
            continue;
        }
        
        nonTextChars++;
    }
    
    // 如果非文本字符比例小于5%，认为是文本文件
    return (nonTextChars / sampleSize) < 0.05;
}
