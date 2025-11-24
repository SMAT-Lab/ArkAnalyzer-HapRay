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
import { Command } from 'commander';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { ElfAnalyzer } from '../../core/elf/elf_analyzer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

interface ElfAnalyzerOptions {
    input: string;
    report_dir: string;
    output: string;
}

export const ElfAnalyzerCli = new Command('elf')
    .requiredOption('-i, --input <string>', 'so file path')
    .requiredOption('-r, --report_dir <string>', 'Directory containing reports to read')
    .requiredOption('-o, --output <string>', 'output file')
    .action(async (options: ElfAnalyzerOptions) => {
        await main(options.input, options.report_dir, options.output);
    });

async function main(input: string, report: string, output: string): Promise<void> {
    if (!fs.existsSync(input)) {
        logger.error(`${input} is not exists.`);
        return;
    }

    if (!fs.existsSync(report)) {
        logger.error(`${report} is not exists.`);
        return;
    }

    if (!fs.existsSync(path.dirname(output))) {
        fs.mkdirSync(path.dirname(output), { recursive: true });
    }

    let symbols = await ElfAnalyzer.getInstance().getInvokeSymbols(input, report, output);
    fs.writeFileSync(output, JSON.stringify(symbols));
}
