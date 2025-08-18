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

import { Command } from 'commander';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { Report } from 'bjc';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

interface BjcOptions {
    input: string;
    output: string;
    projectPath: string;
}

export const BjcCli = new Command('bjc')
    .requiredOption('-i, --input <string>', 'Hap file path')
    .option('-o, --output <string>', 'output path', './')
    .option('--project-path <string>', 'project path directory', '')
    .action(async (options: BjcOptions) => {
        logger.info(`generate coverage report ${options.input} ${options.output}`);
        let report = new Report(options.input, options.projectPath);
        report.generateReport();
        report.writeReport(options.output);
    });
