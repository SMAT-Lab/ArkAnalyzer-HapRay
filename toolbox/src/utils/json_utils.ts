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

/**
 * 将 JSON 数组写入文件
 * @param data - 要写入的 JSON 数组数据
 * @param filePath - 目标文件路径
 * @param options - 可选配置
 */
export async function saveJsonArray<T>(
    data: Array<T>,
    filePath: string,
    options: {
        indent?: number; // 缩进空格数，默认为 2
        encoding?: BufferEncoding; // 文件编码，默认为 utf-8
        overwrite?: boolean; // 是否覆盖现有文件，默认为 true
    } = {}
): Promise<void> {
    const { indent = 2, encoding = 'utf-8', overwrite = true } = options;

    // 确保目录存在
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }

    // 检查文件是否存在且不允许覆盖
    if (!overwrite && fs.existsSync(filePath)) {
        throw new Error(`文件已存在: ${filePath}`);
    }

    // 转换为 JSON 字符串
    const jsonString = JSON.stringify(data, null, indent);

    // 写入文件
    return new Promise((resolve, reject) => {
        fs.writeFile(filePath, jsonString, { encoding }, (err) => {
            if (err) {
                reject(new Error(`写入文件失败: ${err.message}`));
            } else {
                resolve();
            }
        });
    });
}

/**
 * 同步版本：将 JSON 数组写入文件
 */
export function saveJsonArraySync<T>(
    data: Array<T>,
    filePath: string,
    options: {
        indent?: number;
        encoding?: BufferEncoding;
        overwrite?: boolean;
    } = {}
): void {
    const { indent = 2, encoding = 'utf-8', overwrite = true } = options;

    // 确保目录存在
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }

    // 检查文件是否存在且不允许覆盖
    if (!overwrite && fs.existsSync(filePath)) {
        throw new Error(`文件已存在: ${filePath}`);
    }

    // 转换为 JSON 字符串并写入
    const jsonString = JSON.stringify(data, null, indent);
    fs.writeFileSync(filePath, jsonString, { encoding });
}
