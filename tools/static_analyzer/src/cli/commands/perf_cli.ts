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
import type { TimeRange } from '../../core/perf/perf_analyzer';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { PerfAnalysisService } from '../../services/analysis/perf_analysis';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * Parse time range strings into TimeRange objects
 */
function parseTimeRanges(timeRangeStrings?: Array<string>): Array<TimeRange> | undefined {
    if (!timeRangeStrings || timeRangeStrings.length === 0) {
        return undefined;
    }

    const timeRanges: Array<TimeRange> = [];
    for (const timeRangeStr of timeRangeStrings) {
        try {
            if (!timeRangeStr.includes('-')) {
                logger.error(`Invalid time range format: ${timeRangeStr}. Expected format: "startTime-endTime"`);
                continue;
            }

            const [startStr, endStr] = timeRangeStr.split('-', 2);
            const startTime = parseInt(startStr.trim(), 10);
            const endTime = parseInt(endStr.trim(), 10);

            if (isNaN(startTime) || isNaN(endTime)) {
                logger.error(`Invalid time range numbers: ${timeRangeStr}`);
                continue;
            }

            if (startTime >= endTime) {
                logger.error(`Invalid time range: start time (${startTime}) must be less than end time (${endTime})`);
                continue;
            }

            timeRanges.push({ startTime, endTime });
        } catch (error) {
            logger.error(`Failed to parse time range "${timeRangeStr}": ${error}`);
            continue;
        }
    }

    return timeRanges.length > 0 ? timeRanges : undefined;
}

interface HapAnalyzerOptions {
    input: string;
    output: string;
    choose: boolean;
    disableDbtools: boolean;
    kindConfig?: string;
    compatibility: boolean;
    ut: boolean;
    timeRanges?: Array<string>;
    analysisMode?: 'all' | 'perf' | 'memory'; // 分析模式：all(默认)、perf(仅负载)、memory(仅内存)
}

export const PerfCli = new Command('perf')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .option('--choose', 'choose one from rounds', false)
    .option('--disable-dbtools', 'disable dbtools', false)
    .option('-s, --soDir <string>', '--So_dir soDir', '')
    .option('-k, --kind-config <string>', 'custom kind configuration in JSON format')
    .option('--compatibility', 'start compatibility mode', false)
    .option('--ut', 'ut mode', false)
    .option('--time-ranges <ranges...>', 'optional time range filters in format "startTime-endTime" (nanoseconds), supports multiple ranges')
    .action(async (options: HapAnalyzerOptions) => {
        let cliArgs: Partial<GlobalConfig> = { ...options };
        initConfig(cliArgs, (config) => {
            config.choose = options.choose;
            config.inDbtools = !options.disableDbtools;
            if (options.kindConfig) {
                updateKindConfig(config, options.kindConfig);
            }
            config.compatibility = options.compatibility;
            config.ut = options.ut;
        });

        // Parse time ranges
        const timeRanges = parseTimeRanges(options.timeRanges);
        if (timeRanges) {
            logger.info(`Using ${timeRanges.length} time range filter(s):`);
            timeRanges.forEach((tr, i) => {
                logger.info(`  Range ${i + 1}: ${tr.startTime} - ${tr.endTime} nanoseconds`);
            });
        }

        const perfAnalysisService = new PerfAnalysisService();

        if (options.choose) {
            await perfAnalysisService.chooseRound(options.input);
        } else {
            await perfAnalysisService.generatePerfReport(options.input, timeRanges);
        }
    });
