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
