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
import { Command } from 'commander';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

interface HapAnalyzerOptions {
    input: string;
    output: string;
}

export const HapAnalyzerCli = new Command('analyzer')
    .requiredOption('-i, --input <string>', 'Hap file path')
    .option('-o, --output <string>', 'output path', './')
    .action(async (options: HapAnalyzerOptions) => {
        await main(options.input, options.output);
    });

async function main(hapPkgPath: string, output: string): Promise<void> {
    if (!fs.existsSync(hapPkgPath)) {
        logger.error(`${hapPkgPath} is not exists.`);
        return;
    }

    if (!fs.existsSync(output)) {
        fs.mkdirSync(output, { recursive: true });
    }
}
