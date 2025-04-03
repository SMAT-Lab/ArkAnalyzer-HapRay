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

/**
 * 解析HAP包，从HAP包提取包名，版本，abc文件，so文件
 */
export class Hap {
    file: string;
    bundleName: string;
    versionCode: number;
    versionName: string;
    appName: string;

    private constructor(hapFile: string) {
        logger.info(`parse file ${hapFile}`);
        this.file = hapFile;
        this.bundleName = '';
        this.versionCode = 0;
        this.versionName = '';
        this.appName = '';
    }

    public static async loadFromHap(hapFile: string): Promise<Hap> {
        let parser = new Hap(hapFile);

        let zip = await JSZip.loadAsync(fs.readFileSync(hapFile));
        try {
            let module = JSON.parse(await zip.file('module.json')?.async('string')!);
            parser.bundleName = module.app.bundleName;
            parser.versionCode = module.app.versionCode;
            parser.versionName = module.app.versionName;

            let buf = await zip.file('resources.index')?.async('nodebuffer')!;
            let res = new ResourceIndexParser(buf);
            let label: string = module.app.label;
            if (label.startsWith('$string:')) {
                parser.appName = res.getStringValue(label.substring('$string:'.length));
            }
        } catch (error) {
            logger.error(`HapParser HAP ${hapFile} not found 'pack.info'.`);
        }

        return parser;
    }

    public async readAbc(): Promise<Map<string, Buffer>> {
        let decrypt = new Map<string, Buffer>();
        let abcMap = new Map<string, Buffer>();
        let zip = await JSZip.loadAsync(fs.readFileSync(this.file));

        let metadata = (await zip.file('encrypt/metadata.info')?.async('string')) || '';
        if (metadata.length > 0) {
            let decryptPath = path.join(path.dirname(this.file), 'decrypt');
            if (fs.existsSync(decryptPath)) {
                let basename = path.basename(this.file);
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
                    let key = (await entry.async('nodebuffer')!).subarray(0, 44).toString('base64');
                    if (decrypt.has(key)) {
                        abcMap.set(entry.name, decrypt.get(key)!);
                    }
                }
            }
        }
        return abcMap;
    }

    public async extract(output: string): Promise<void> {
        output = path.join(output, 'unzip', path.basename(this.file));
        fs.mkdirSync(output, { recursive: true });
        let zip = await JSZip.loadAsync(fs.readFileSync(this.file));
        for (const entry of Object.values(zip.files)) {
            try {
                const dest = path.join(output, entry.name);
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
