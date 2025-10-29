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
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { NativeMemoryAnalyzer } from '../../core/memory/native_memory_analyzer';
import { getConfig } from '../../config';
import { AnalysisServiceBase, type Steps, type TestReportInfo } from './analysis_service_base';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * 内存分析服务
 * 独立的内存分析服务，不依赖负载分析
 * 参考 PerfAnalysisService 的结构
 */
export class MemoryAnalysisService extends AnalysisServiceBase {
    constructor() {
        super();
    }

    /**
     * 执行内存分析
     * 主入口方法，用于独立的内存分析
     */
    async analyzeMemory(input: string): Promise<void> {
        const config = getConfig();
        const scene = path.basename(input);
        const steps = await this.loadSteps(input);
        const testReportInfo = await this.loadTestReportInfo(input, scene, config);
        const memoryDbPaths = await this.getMemoryDbPaths(input, steps);

        if (memoryDbPaths.length === 0) {
            logger.warn('未找到任何内存数据文件，无法进行内存分析');
            return;
        }

        const outputDir = path.join(input, 'report');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        await this.generateMemoryJson(testReportInfo, memoryDbPaths, outputDir, steps);
    }

    /**
     * 生成内存分析报告
     * 只生成内存数据，不分析负载数据
     */
    async generateMemoryJson(
        testInfo: TestReportInfo,
        memoryDbPaths: Array<string>,
        outputDir: string,
        steps: Steps
    ): Promise<void> {
        const { stepMemoryDataMap } = await this.analyzeNativeMemory(testInfo, memoryDbPaths, outputDir, steps);

        if (stepMemoryDataMap.size > 0) {
            const nativeMemoryJson: Record<string, unknown> = {};
            for (const [stepIdx, memoryData] of stepMemoryDataMap.entries()) {
                nativeMemoryJson[`step${stepIdx}`] = memoryData;
            }
            const nativeMemoryJsonPath = path.join(outputDir, 'native_memory.json');
            fs.writeFileSync(nativeMemoryJsonPath, JSON.stringify(nativeMemoryJson, null, 2), 'utf-8');
            logger.info(`Saved Native Memory data: ${stepMemoryDataMap.size} steps`);
        } else {
            logger.warn('未生成任何内存分析数据');
        }
    }

    /**
     * 分析Native Memory数据
     * 为每个步骤生成平铺的Native Memory数据（类似perf数据格式）和完整的分析结果
     */
    private async analyzeNativeMemory(
        _testInfo: TestReportInfo,
        memoryDbPaths: Array<string>,
        _outputDir: string,
        steps: Steps
    ): Promise<{ stepMemoryDataMap: Map<number, { stats: { peakMemorySize: number; peakMemoryDuration: number; averageMemorySize: number }; records: Array<unknown> }> }> {
        const stepMemoryDataMap = new Map<number, { stats: { peakMemorySize: number; peakMemoryDuration: number; averageMemorySize: number }; records: Array<unknown> }>();

        logger.info(`Analyzing Native Memory data for ${memoryDbPaths.length} step(s)`);

        for (let i = 0; i < memoryDbPaths.length; i++) {
            const memoryDbPath = memoryDbPaths[i];

            if (!memoryDbPath || !fs.existsSync(memoryDbPath)) {
                logger.info(`No memory data found for step ${i + 1}, skipping`);
                continue;
            }

            const stepIdx = steps[i].stepIdx;

            try {
                logger.info(`Analyzing Native Memory for step ${stepIdx}: ${memoryDbPath}`);

                const analyzer = new NativeMemoryAnalyzer(memoryDbPath);
                const records = await analyzer.analyze(stepIdx);
                const stats = analyzer.calculateMemoryStats();

                // Store flattened records with statistics
                stepMemoryDataMap.set(stepIdx, {
                    stats: {
                        peakMemorySize: stats.peak_memory_size,
                        peakMemoryDuration: stats.peak_memory_duration,
                        averageMemorySize: stats.average_memory_size,
                    },
                    records: records,
                });

                logger.info(`Native Memory analysis for step ${stepIdx} completed, ${records.length} records`);
            } catch (error) {
                logger.error(`Failed to analyze Native Memory for step ${stepIdx}: ${error}`);
            }
        }

        return { stepMemoryDataMap };
    }
}

