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
import type { GlobalConfig } from '../../config/types';
import { initConfig, updateKindConfig } from '../../config';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { MemoryAnalysisService } from '../../services/analysis/memory_analysis';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

interface MemoryAnalyzerOptions {
    input: string;
    output: string;
    disableDbtools: boolean;
    kindConfig?: string;
    compatibility: boolean;
    ut: boolean;
}

/**
 * 内存分析命令行接口
 * 独立的内存分析命令，不依赖负载分析
 */
export const MemoryCli = new Command('memory')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .option('--disable-dbtools', 'disable dbtools', false)
    .option('-k, --kind-config <string>', 'custom kind configuration in JSON format')
    .option('--compatibility', 'start compatibility mode', false)
    .option('--ut', 'ut mode', false)
    .action(async (options: MemoryAnalyzerOptions) => {
        let cliArgs: Partial<GlobalConfig> = { ...options };
        initConfig(cliArgs, (config) => {
            config.inDbtools = !options.disableDbtools;
            if (options.kindConfig) {
                updateKindConfig(config, options.kindConfig);
            }
            config.compatibility = options.compatibility;
            config.ut = options.ut;
        });

        logger.info('Starting Native Memory analysis...');

        const memoryAnalysisService = new MemoryAnalysisService();
        try {
            await memoryAnalysisService.analyzeMemory(options.input);
            logger.info('Native Memory analysis completed successfully');
        } catch (error) {
            logger.error(`Native Memory analysis failed: ${error}`);
            process.exit(1);
        }
    });

