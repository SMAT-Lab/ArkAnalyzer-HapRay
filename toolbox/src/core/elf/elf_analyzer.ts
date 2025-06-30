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

export class ElfAnalyzer {
    private static instance: ElfAnalyzer | undefined;

    private constructor() {}

    public static getInstance(): ElfAnalyzer {
        return (this.instance ??= new ElfAnalyzer());
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
}
