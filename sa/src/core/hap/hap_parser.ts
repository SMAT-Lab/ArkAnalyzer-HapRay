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

import * as JSZip from 'jszip';
import path from 'path';
import fs from 'fs';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { ResourceIndexParser } from './resource_index_parser';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export interface TechStackDetection {
    /** 文件夹路径 */
    folder: string;
    /** 文件名 */
    file: string;
    /** 文件大小（字节） */
    size: number;
    /** 技术栈类型 */
    techStack: string;
    /** 文件类型 */
    fileType?: string;
    /** 置信度 */
    confidence?: number;
    /** 元数据（只包含自定义字段） */
    metadata: Record<string, unknown>;
}

/**
 * 解析HAP包，从HAP包提取包名，版本，abc文件，so文件
 */
export class Hap {
    hapPath: string;
    bundleName: string;
    versionCode: number;
    versionName: string;
    appName: string;
    techStackDetections: Array<TechStackDetection>;

    private constructor(hapPath: string) {
        logger.info(`parse file ${hapPath}`);
        this.hapPath = hapPath;
        this.bundleName = '';
        this.versionCode = 0;
        this.versionName = '';
        this.appName = '';
        this.techStackDetections = [];
    }

    public static async loadFromHap(hapPath: string): Promise<Hap> {
        let parser = new Hap(hapPath);

        let zip = await JSZip.loadAsync(fs.readFileSync(hapPath));
        try {
            let module = JSON.parse(await zip.file('module.json')?.async('string')!) as {
                app: { bundleName: string; versionCode: number; versionName: string; label: string };
            };
            parser.bundleName = module.app.bundleName;
            parser.versionCode = module.app.versionCode;
            parser.versionName = module.app.versionName;

            let buf = await zip.file('resources.index')?.async('nodebuffer')!;
            let res = new ResourceIndexParser(buf);
            let label: string = module.app.label;
            if (label.startsWith('$string:')) {
                parser.appName = res.getStringValue(label.substring('$string:'.length));
            }
        } catch {
            logger.error(`HapParser HAP ${hapPath} not found 'pack.info'.`);
        }

        return parser;
    }

    public async readAbc(): Promise<Map<string, Buffer>> {
        let decrypt = new Map<string, Buffer>();
        let abcMap = new Map<string, Buffer>();
        let zip = await JSZip.loadAsync(fs.readFileSync(this.hapPath));

        let metadata = (await zip.file('encrypt/metadata.info')?.async('string')) ?? '';
        if (metadata.length > 0) {
            let decryptPath = path.join(path.dirname(this.hapPath), 'decrypt');
            if (fs.existsSync(decryptPath)) {
                let basename = path.basename(this.hapPath);
                for (const abc of fs.readdirSync(decryptPath)) {
                    if (abc.indexOf(basename) !== -1) {
                        let abcBuf: Buffer = fs.readFileSync(path.join(decryptPath, abc));
                        decrypt.set(abcBuf.subarray(0, 44).toString('base64'), abcBuf);
                    }
                }
            }
        }

        for (const entry of Object.values(zip.files)) {
            if (entry.name.endsWith('.abc')) {
                if (metadata.lastIndexOf(entry.name) === -1) {
                    abcMap.set(entry.name, await entry.async('nodebuffer'));
                } else {
                    let key = (await entry.async('nodebuffer')).subarray(0, 44).toString('base64');
                    if (decrypt.has(key)) {
                        abcMap.set(entry.name, decrypt.get(key)!);
                    }
                }
            }
        }
        return abcMap;
    }

    public async extract(output: string): Promise<void> {
        output = path.join(output, 'unzip', path.basename(this.hapPath));
        fs.mkdirSync(output, { recursive: true });
        let zip = await JSZip.loadAsync(fs.readFileSync(this.hapPath));
        for (const entry of Object.values(zip.files)) {
            try {
                const dest = path.join(output, entry.name.replace(/\//g, path.sep));
                if (entry.dir) {
                    fs.mkdirSync(dest, { recursive: true });
                } else {
                    if (!fs.existsSync(path.dirname(dest))) {
                        fs.mkdirSync(path.dirname(dest), { recursive: true });
                    }
                    let content = await entry.async('nodebuffer');
                    fs.writeFileSync(dest, content);
                }
            } catch (error) {
                logger.warn(`extract: ${error}`);
            }
        }
    }
}
