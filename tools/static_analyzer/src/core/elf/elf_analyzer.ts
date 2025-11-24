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

import * as path from 'path';
import * as fs from 'fs';
import * as readline from 'readline';
import { Logger, LOG_MODULE_TYPE } from 'arkanalyzer';
import type { ELF } from './elfy';
import { parseELF } from './elfy';
import { getAllFiles } from '../../utils/file_utils';
import initSqlJs from 'sql.js';
import { demangle } from './demangle';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

export interface InvokeSymbol {
    symbol: string;
    invoke: boolean;
}

export interface ElfInfo {
    exports: Array<string>;
    imports: Array<string>;
    dependencies: Array<string>;
}

export class ElfAnalyzer {
    private static instance: ElfAnalyzer | undefined;

    private constructor() {}

    public static getInstance(): ElfAnalyzer {
        return (this.instance ??= new ElfAnalyzer());
    }

    /**
     * 获取SO文件的完整信息（符号和依赖）
     */
    public async getElfInfo(filePath: string): Promise<ElfInfo> {
        const file = path.basename(filePath);
        const elfBuffer = fs.readFileSync(filePath);
        let elf: ELF;

        try {
            elf = parseELF(elfBuffer);
        } catch (error) {
            logger.error(`Failed to parse ELF file ${file}: ${(error as Error).message}`);
            return { exports: [], imports: [], dependencies: [] };
        }

        // 提取符号
        const exportedSymbols: Array<string> = [];
        const importedSymbols: Array<string> = [];

        // Extract exported symbols from .dynsym
        if (elf.body.symbols) {
            for (const sym of elf.body.symbols) {
                if (sym.section === 'SHN_UNDEF') {
                    importedSymbols.push((await demangle(sym.name)) || sym.name);
                } else {
                    exportedSymbols.push((await demangle(sym.name)) || sym.name);
                }
            }
        }

        // Extract exported symbols from .symtab
        if (elf.body.symtabSymbols) {
            for (const sym of elf.body.symtabSymbols) {
                if (sym.section === 'SHN_UNDEF') {
                    importedSymbols.push((await demangle(sym.name)) || sym.name);
                } else {
                    exportedSymbols.push((await demangle(sym.name)) || sym.name);
                }
            }
        }

        // 提取依赖库
        const dependencies = this.extractDependencies(elf);

        return {
            exports: [...new Set(exportedSymbols)], // 去重
            imports: [...new Set(importedSymbols)], // 去重
            dependencies
        };
    }

    /**
     * 提取SO文件的依赖库列表
     */
    private extractDependencies(elf: ELF): Array<string> {
        const dependencies: Array<string> = [];

        // 查找 .dynamic section
        const dynamicSection = elf.body.sections.find(s => s.type === 'dynamic');
        if (!dynamicSection || !dynamicSection.data) {
            return dependencies;
        }

        try {
            const is64 = elf.class === '64';
            const entrySize = is64 ? 16 : 8; // 64位: 16字节, 32位: 8字节
            const data = dynamicSection.data;

            // 查找 .dynstr section (字符串表)
            const dynstrSection = elf.body.sections.find(s => s.name === '.dynstr');
            if (!dynstrSection || !dynstrSection.data) {
                return dependencies;
            }

            // 解析 dynamic entries
            for (let offset = 0; offset < data.length; offset += entrySize) {
                if (offset + entrySize > data.length) break;

                let tag: number;
                let value: number | bigint;

                if (is64) {
                    // 64位: tag (8 bytes) + value (8 bytes)
                    tag = Number(data.readBigInt64LE(offset));
                    value = data.readBigInt64LE(offset + 8);
                } else {
                    // 32位: tag (4 bytes) + value (4 bytes)
                    tag = data.readInt32LE(offset);
                    value = data.readInt32LE(offset + 4);
                }

                // DT_NEEDED = 1 (表示依赖的库)
                if (tag === 1) {
                    const strOffset = Number(value);
                    const libName = this.readStringFromBuffer(dynstrSection.data, strOffset);
                    if (libName) {
                        dependencies.push(libName);
                    }
                } else if (tag === 0) {
                    // DT_NULL = 0 (表示结束)
                    break;
                }
            }
        } catch (error) {
            logger.warn(`Failed to extract dependencies: ${(error as Error).message}`);
        }

        return dependencies;
    }

    /**
     * 从Buffer中读取以null结尾的字符串
     */
    private readStringFromBuffer(buffer: Buffer, offset: number): string {
        let end = offset;
        while (end < buffer.length && buffer[end] !== 0) {
            end++;
        }
        return buffer.slice(offset, end).toString('utf8');
    }

    public async getSymbols(filePath: string): Promise<{ exports: Array<string>; imports: Array<string> }> {
        let file = path.basename(filePath);
        const elfBuffer = fs.readFileSync(filePath);
        let elf: ELF;

        try {
            elf = parseELF(elfBuffer);
        } catch (error) {
            logger.error(`Failed to parse ELF file ${file}: ${(error as Error).message}`);
            return { exports: [], imports: [] };
        }

        // Initialize export and import lists
        const exportedSymbols: Array<string> = [];
        const importedSymbols: Array<string> = [];

        // Extract exported symbols from .dynsym
        if (elf.body.symbols) {
            for (const sym of elf.body.symbols) {
                if (sym.section === 'SHN_UNDEF') {
                    importedSymbols.push((await demangle(sym.name)) || sym.name);
                } else {
                    exportedSymbols.push((await demangle(sym.name)) || sym.name);
                }
            }
        }

        // Extract exported symbols from .symtab
        if (elf.body.symtabSymbols) {
            for (const sym of elf.body.symtabSymbols) {
                if (sym.section === 'SHN_UNDEF') {
                    importedSymbols.push((await demangle(sym.name)) || sym.name);
                } else {
                    exportedSymbols.push((await demangle(sym.name)) || sym.name);
                }
            }
        }

        return { exports: exportedSymbols, imports: importedSymbols };
    }

    public async getInvokeSymbols(
        filePath: string,
        perfPath: string,
        cache_file: string
    ): Promise<Array<InvokeSymbol>> {
        let result: Array<InvokeSymbol> = [];

        let perfFiles = getAllFiles(perfPath, { exts: ['.db'] }).filter((value) => {
            let hiperf = path.dirname(path.dirname(value));
            let scene = path.dirname(hiperf);
            return path.basename(hiperf) === 'hiperf' && !path.basename(scene).match(/.*_round\d$/);
        });
        // get all invoked symbols
        let invokeSymbols = new Set<string>();
        let SQL = await initSqlJs();
        for (const dbFile of perfFiles) {
            const db = new SQL.Database(fs.readFileSync(dbFile));
            const results = db.exec(`SELECT symbol FROM perf_files where path like '%${path.basename(filePath)}%'`);
            if (results.length === 0) {
                continue;
            }

            results[0].values.map((row) => {
                invokeSymbols.add(row[0] as string);
            });
        }

        logger.info(`${filePath} parse symbols from perf ${Array.from(invokeSymbols.values()).join('\n')}`);
        let exports: Array<string> = [];
        // read from cache
        if (fs.existsSync(cache_file)) {
            let data = JSON.parse(fs.readFileSync(cache_file, { encoding: 'utf-8' })) as Array<{ symbol: string }>;
            for (const item of data) {
                exports.push(item.symbol);
            }
        } else {
            exports = (await this.getSymbols(filePath)).exports;
        }
        for (const symbol of exports) {
            result.push({ symbol: symbol, invoke: invokeSymbols.has(symbol) });
        }

        return result;
    }

    public async strings(filePath: string, pattern?: string | RegExp): Promise<Array<string>> {
        return new Promise((resolve, reject) => {
            if (!fs.existsSync(filePath)) {
                reject(new Error(`File is not exists: ${filePath}`));
                return;
            }

            const lines: Array<string> = [];
            let regex = new RegExp(pattern ?? /.*$/);
            let currentString = '';

            const stream = fs.createReadStream(filePath);
            const rl = readline.createInterface({
                input: stream,
                crlfDelay: Infinity,
            });

            rl.on('line', (line) => {
                // 处理每一行的字节数据
                for (let i = 0; i < line.length; i++) {
                    const charCode = line.charCodeAt(i);
                    if (charCode >= 32 && charCode <= 126) {
                        currentString += line[i];
                    } else {
                        if (currentString.length >= 4 && regex.test(currentString)) {
                            lines.push(currentString);
                        }
                        currentString = '';
                    }
                }
            });

            rl.on('close', () => {
                // 处理最后一个字符串
                if (currentString.length >= 4 && regex.test(currentString)) {
                    lines.push(currentString);
                }
                resolve(lines);
            });

            rl.on('error', reject);
            stream.on('error', reject);
        });
    }
}
