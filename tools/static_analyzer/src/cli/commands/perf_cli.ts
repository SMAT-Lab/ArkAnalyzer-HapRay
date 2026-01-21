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
import fs from 'fs';
import path from 'path';
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
    packageName?: string;
}

export const PerfCli = new Command('perf')
    .requiredOption('-i, --input <string>', 'scene test report path or sqlite db file path (perf.db or trace.db)')
    .option('--choose', 'choose one from rounds', false)
    .option('--disable-dbtools', 'disable dbtools', false)
    .option('-s, --soDir <string>', '--So_dir soDir', '')
    .option('-k, --kind-config <string>', 'custom kind configuration in JSON format')
    .option('--compatibility', 'start compatibility mode', false)
    .option('--ut', 'ut mode', false)
    .option('--time-ranges <ranges...>', 'optional time range filters in format "startTime-endTime" (nanoseconds), supports multiple ranges')
    .option('--package-name <string>', 'application package name (required for single db file analysis)')
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

        // 检查 input 是否是 .db 文件
        const isDbFile = options.input.toLowerCase().endsWith('.db');
        
        if (isDbFile) {
            // 单步分析模式：直接使用 db 文件
            if (!fs.existsSync(options.input)) {
                logger.error(`DB file not found: ${options.input}`);
                return;
            }
            
            // 从 db 文件路径推断场景目录和步骤索引
            const dbFilePath = path.resolve(options.input);
            const dbDir = path.dirname(dbFilePath);
            const dbFileName = path.basename(dbFilePath).toLowerCase();
            
            // 检查路径格式：hiperf/step<idx>/perf.db 或 htrace/step<idx>/trace.db
            const stepMatch = dbDir.match(/step(\d+)$/);
            if (!stepMatch) {
                logger.error('Invalid db file path format. Expected: .../hiperf/step<idx>/perf.db or .../htrace/step<idx>/trace.db');
                return;
            }
            
            const stepIdx = parseInt(stepMatch[1], 10);
            
            // 场景目录通常是 db 目录的上两级（scene/hiperf/step<idx>/perf.db 或 scene/htrace/step<idx>/trace.db）
            const sceneDir = path.dirname(path.dirname(dbDir));
            
            // 检查是否是 perf.db 还是 trace.db
            const isPerfDb = dbFileName === 'perf.db';
            
            logger.info(`单步分析模式: DB文件=${dbFilePath}, 场景目录=${sceneDir}, 步骤索引=${stepIdx}, 类型=${isPerfDb ? 'perf' : 'trace'}`);
            
            // 使用场景目录和 db 文件进行单步分析
            await perfAnalysisService.generatePerfReportFromDbFile(dbFilePath, sceneDir, stepIdx, options.packageName, timeRanges);
        } else if (options.choose) {
            await perfAnalysisService.chooseRound(options.input);
        } else {
            await perfAnalysisService.generatePerfReport(options.input, timeRanges);
        }
    });
