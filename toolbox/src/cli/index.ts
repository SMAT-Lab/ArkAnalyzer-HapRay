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

import { Command, program } from 'commander';
import Logger, { LOG_LEVEL, LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { HapAnalyzerCli } from './commands/hap_analyzer_cli';
import { DbtoolsCli } from './commands/hapray_cli';
import { ElfAnalyzerCli } from './commands/elf_analyzer_cli';

Logger.configure('arkanalyzer-hapray.log', LOG_LEVEL.ERROR, LOG_LEVEL.INFO, true);
const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
const VERSION = '1.1.0';

const HaprayCli = new Command('hapray').version(VERSION);
HaprayCli.addCommand(HapAnalyzerCli);
HaprayCli.addCommand(DbtoolsCli);
HaprayCli.addCommand(ElfAnalyzerCli);

try {
    program
        .name('arkanalyzer-hapray')
        .description('CLI to arkanalyzer hapray')
        .version(VERSION)
        .addCommand(HaprayCli)
        .parse();
} catch (error) {
    logger.error('error', error);
}
