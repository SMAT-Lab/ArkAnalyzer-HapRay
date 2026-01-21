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
import type { Step } from '../../core/perf/perf_analyzer';
import type { GlobalConfig } from '../../config/types';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

// ===================== 共同类型定义 =====================
export type Steps = Array<Step>;

/**
 * 标准 testInfo.json 文件结构
 */
export interface StandardTestInfo {
    app_id: string;
    app_name: string;
    app_version: string;
    scene: string;
    timestamp: number;
    device?: {
        version: string;
        sn: string;
    };
}

/**
 * 测试报告信息
 */
export interface TestReportInfo {
    app_id: string;
    app_name: string;
    app_version: string;
    scene: string;
    timestamp: number;
    rom_version: string;
    device_sn: string;
}

/**
 * 步骤路径信息
 *
 * 注意：memory 数据从 htracePath 对应的 trace.htrace 中获取
 */
export interface StepPaths {
    stepDir: string;
    perfDataPath: string;
    dbPath: string;
    htracePath: string;
}

/**
 * 分析服务基类
 * 提取 PerfAnalysisService 和 MemoryAnalysisService 的共同逻辑
 */
export abstract class AnalysisServiceBase {
    constructor() {}

    // ===================== 数据加载函数 =====================
    /**
     * 加载步骤信息
     */
    async loadSteps(basePath: string): Promise<Steps> {
        // 统一规则：只在 basePath/report/steps.json 中查找步骤定义
        const stepsJsonPath = path.join(basePath, 'report', 'steps.json');
        return await this.loadJsonFile<Steps>(stepsJsonPath);
    }

    /**
     * 加载测试报告信息
     */
    async loadTestReportInfo(input: string, scene: string, config: GlobalConfig): Promise<TestReportInfo> {
        if (config.compatibility) {
            return this.loadCompatibilityTestReportInfo(input, scene);
        } else {
            return await this.loadStandardTestReportInfo(input);
        }
    }

    /**
     * 加载标准模式的测试报告信息
     */
    async loadStandardTestReportInfo(input: string): Promise<TestReportInfo> {
        const testInfoPath = path.join(input, 'testInfo.json');
        const testInfo = await this.loadJsonFile<StandardTestInfo>(testInfoPath);
        return {
            app_id: testInfo.app_id,
            app_name: testInfo.app_name,
            app_version: testInfo.app_version,
            scene: testInfo.scene,
            timestamp: testInfo.timestamp,
            rom_version: testInfo.device?.version ?? '',
            device_sn: testInfo.device?.sn ?? '',
        };
    }

    /**
     * 加载兼容性模式的测试报告信息
     */
    protected loadCompatibilityTestReportInfo(input: string, scene: string): TestReportInfo {
        return {
            app_id: 'unknown',
            app_name: 'unknown',
            app_version: 'unknown',
            scene: scene,
            timestamp: Date.now(),
            rom_version: 'unknown',
            device_sn: 'unknown',
        };
    }

    // ===================== 工具函数区 =====================
    // ---- JSON/文件操作 ----
    /**
     * 加载 JSON 文件
     */
    async loadJsonFile<T>(filePath: string): Promise<T> {
        const rawData = await fs.promises.readFile(filePath, 'utf8');
        return JSON.parse(rawData) as T;
    }

    // ---- 路径构建工具 ----
    /**
     * 构建步骤相关的路径信息
     *
     * 注意：memory 数据从 trace.htrace 中获取
     */
    buildStepPaths(basePath: string, stepIdx: number): StepPaths {
        const stepDir = path.join(basePath, 'hiperf', `step${stepIdx}`);
        const htraceStepDir = path.join(basePath, 'htrace', `step${stepIdx}`);
        return {
            stepDir,
            perfDataPath: path.join(stepDir, 'perf.data'),
            dbPath: path.join(stepDir, 'perf.db'),
            htracePath: path.join(htraceStepDir, 'trace.htrace'),
        };
    }

    // ---- 并发控制工具 ----
    /**
     * 并发执行任务，支持批次控制
     */
    async executeConcurrentTasks<T, R>(
        items: Array<T>,
        taskFn: (item: T, index: number) => Promise<R>,
        maxConcurrency = 4
    ): Promise<Array<R>> {
        const results = new Array<R>(items.length);

        for (let i = 0; i < items.length; i += maxConcurrency) {
            const batch = items.slice(i, i + maxConcurrency);
            const batchPromises = batch.map(async (item, batchIndex) => {
                const actualIndex = i + batchIndex;
                const result = await taskFn(item, actualIndex);
                return { index: actualIndex, result };
            });

            const batchResults = await Promise.all(batchPromises);
            batchResults.forEach(({ index, result }) => {
                results[index] = result;
            });

            logger.debug(`完成批次 ${Math.floor(i / maxConcurrency) + 1}/${Math.ceil(items.length / maxConcurrency)}`);
        }

        return results;
    }
}

