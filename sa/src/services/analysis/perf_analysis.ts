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
import { DOMParser } from '@xmldom/xmldom';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import type { Step, TimeRange } from '../../core/perf/perf_analyzer';
import { PerfAnalyzer } from '../../core/perf/perf_analyzer';
import { getConfig } from '../../config';
import { traceStreamerCmd } from '../external/trace_streamer';
import { checkPerfFiles, copyDirectory, copyFile, getSceneRoundsFolders } from '../../utils/folder_utils';

import type {
    Round,
    TestSceneInfo as PerfTestSceneInfo,
    TestStepGroup,
    TestReportInfo,
    RoundInfo,
} from '../../core/perf/perf_analyzer_base';
import type { GlobalConfig } from '../../config/types';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

// ===================== 类型定义 =====================
export type Steps = Array<Step>;

// ===================== 内部类型定义 =====================
/**
 * 标准 testInfo.json 文件结构
 */
interface StandardTestInfo {
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
 * 步骤路径信息
 */
interface StepPaths {
    stepDir: string;
    perfDataPath: string;
    dbPath: string;
    htracePath: string;
}

export class PerfAnalysisService {
    constructor() {}

    /**
     * 处理选择轮次（choose round）
     */
    async chooseRound(input: string): Promise<void> {
        const roundFolders = getSceneRoundsFolders(input);
        if (roundFolders.length === 0) {
            logger.error(`${input} 没有可用的测试轮次数据，无法生成报告！`);
            return;
        }

        const output = path.join(input, 'report');
        if (!fs.existsSync(output)) {
            logger.info(`创建输出目录: ${output}`);
            fs.mkdirSync(output, { recursive: true });
        }

        const steps = await this.loadSteps(roundFolders[0]);
        await this.processRoundSelection(roundFolders, steps, input);
        logger.info('轮次选择完成，summary_info.json 将在生成报告时创建');
    }

    /**
     * 处理生成报告（Generate PerfReport）
     */
    async generatePerfReport(input: string, timeRanges?: Array<TimeRange>): Promise<void> {
        const config = getConfig();
        const scene = path.basename(input);
        const steps = await this.loadSteps(input);

        if (!(await checkPerfFiles(input, steps.length))) {
            logger.error('hiperf 数据不全，需要先执行数据收集步骤！');
            return;
        }

        const testReportInfo = await this.loadTestReportInfo(input, scene, config);
        await this.generatePerfJson(input, testReportInfo, steps, timeRanges);
    }

    // ===================== 数据加载函数 =====================
    /**
     * 加载步骤信息
     */
    async loadSteps(basePath: string): Promise<Steps> {
        const stepsJsonPath = path.join(basePath, 'hiperf', 'steps.json');
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
    
    // ===================== 工具函数区 =====================
    // ---- JSON/文件操作 ----
    /** 加载 JSON 文件 */
    async loadJsonFile<T>(filePath: string): Promise<T> {
        const rawData = await fs.promises.readFile(filePath, 'utf8');
        return JSON.parse(rawData) as T;
    }
    
    // ---- 路径构建工具 ----
    /**
     * 构建步骤相关的路径信息
     */
    buildStepPaths(basePath: string, stepIdx: number): StepPaths {
        const stepDir = path.join(basePath, 'hiperf', `step${stepIdx}`);
        return {
            stepDir,
            perfDataPath: path.join(stepDir, 'perf.data'),
            dbPath: path.join(stepDir, 'perf.db'),
            htracePath: path.join(basePath, 'htrace', `step${stepIdx}`, 'trace.htrace'),
        };
    }
    
    // ---- TestSceneInfo 构建工具 ----
    /**
     * 从 TestReportInfo 构建 PerfTestSceneInfo
     */
    buildTestSceneInfo(testInfo: TestReportInfo): PerfTestSceneInfo {
        return {
            packageName: testInfo.app_id,
            appName: testInfo.app_name,
            scene: testInfo.scene,
            osVersion: testInfo.rom_version,
            timestamp: testInfo.timestamp,
            appVersion: testInfo.app_version,
            rounds: [],
            chooseRound: 0,
        };
    }
    
    /**
     * 从标准 testInfo.json 构建 PerfTestSceneInfo
     */
    buildTestSceneInfoFromStandardTestInfo(testInfo: StandardTestInfo): PerfTestSceneInfo {
        return {
            packageName: testInfo.app_id,
            appName: testInfo.app_name,
            scene: testInfo.scene,
            osVersion: testInfo.device?.version ?? '',
            timestamp: testInfo.timestamp,
            appVersion: testInfo.app_version,
            rounds: [],
            chooseRound: 0,
        };
    }
    
    // ---- TestStepGroup 构建工具 ----
    /**
     * 构建 TestStepGroup
     */
    buildTestStepGroup(
        reportRoot: string,
        step: Step,
        stepPaths: StepPaths
    ): TestStepGroup {
        return {
            reportRoot,
            groupId: step.stepIdx,
            groupName: step.description,
            dbfile: stepPaths.dbPath,
            perfFile: stepPaths.perfDataPath,
            traceFile: stepPaths.htracePath,
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
    
    // ---- 轮次处理相关 ----
    /**
     * 处理轮次选择逻辑
     */
    async processRoundSelection(
        roundFolders: Array<string>,
        steps: Steps,
        inputPath: string
    ): Promise<Array<RoundInfo>> {
        let roundInfos: Array<RoundInfo> = [];
    
        await this.copyStandardFiles(roundFolders[0], inputPath);
    
        for (const step of steps) {
            const roundResults = await this.calculateRoundResults(roundFolders, step);
            const selectedRound = this.selectOptimalRound(roundResults);
            const roundInfo: RoundInfo = {
                step_id: step.stepIdx,
                round: selectedRound,
                count: roundResults[selectedRound],
            };
            roundInfos.push(roundInfo);
            await this.copySelectedRoundData(roundFolders[selectedRound], inputPath, step);
        }
        return roundInfos;
    }
    
    /**
     * 复制标准模式的文件
     */
    async copyStandardFiles(sourceRound: string, inputPath: string): Promise<void> {
        const testInfoPath = path.join(sourceRound, 'testInfo.json');
        await copyFile(testInfoPath, path.join(inputPath, 'testInfo.json'));
    
        const stepsJsonPath = path.join(sourceRound, 'hiperf', 'steps.json');
        await copyFile(stepsJsonPath, path.join(inputPath, 'hiperf', 'steps.json'));
    }
    
    /**
     * 计算每轮的结果 - 使用并发执行提高效率
     */
    async calculateRoundResults(roundFolders: Array<string>, step: Step): Promise<Array<number>> {
        logger.info(`开始并发分析 ${roundFolders.length} 个轮次，步骤：${step.stepIdx}，并发数：5`);
    
        // 使用并发工具函数处理所有轮次
        const results = await this.executeConcurrentTasks(
            roundFolders,
            async (roundFolder: string, index: number): Promise<number> => {
                try {
                    const stepPaths = this.buildStepPaths(roundFolder, step.stepIdx);
    
                    // 确保数据库文件存在
                    if (!fs.existsSync(stepPaths.dbPath)) {
                        await traceStreamerCmd(stepPaths.perfDataPath, stepPaths.dbPath);
                    }
    
                    // 为每个轮次创建独立的分析器实例，避免并发冲突
                    const perfAnalyzer = new PerfAnalyzer('');
                    const sum = await this.calculateRoundResultWithFullAnalysis(roundFolder, step, perfAnalyzer);
    
                    logger.info(`${roundFolder} 步骤：${step.stepIdx} 轮次：${index} 负载总数: ${sum}`);
                    return sum;
                } catch (error) {
                    logger.error(`轮次 ${index} (${roundFolder}) 分析失败: ${error}`);
                    return 0;
                }
            },
            5
        );
    
        logger.info(`完成所有轮次分析，共 ${roundFolders.length} 个轮次`);
        return results;
    }
    
    /**
     * 使用完整分析方式计算单轮结果的汇总值
     */
    async calculateRoundResultWithFullAnalysis(
        roundFolder: string,
        step: Step,
        perfAnalyzer: PerfAnalyzer
    ): Promise<number> {
        try {
            // 加载该轮次的测试信息
            const testInfoPath = path.join(roundFolder, 'testInfo.json');
            const testInfo = await this.loadJsonFile<StandardTestInfo>(testInfoPath);
    
            // 构建测试场景信息
            const testSceneInfo = this.buildTestSceneInfoFromStandardTestInfo(testInfo);
    
            // 构建单个步骤的轮次信息
            const stepPaths = this.buildStepPaths(roundFolder, step.stepIdx);
            const testStepGroup = this.buildTestStepGroup(roundFolder, step, stepPaths);
    
            const round: Round = { steps: [testStepGroup] };
            testSceneInfo.rounds.push(round);
    
            const perfSum = await perfAnalyzer.analyzeOnly(testSceneInfo);
    
            // 从分析结果中提取该步骤的汇总值
            const stepSum = perfSum.steps.find(s => s.stepIdx === step.stepIdx);
            if (stepSum?.total && stepSum.total.length > 1) {
                // total[0] 是周期数 (cycles)，total[1] 是指令数 (instructions)
                // 如果第一个值（cycles）等于0，则获取第二个值（instructions）
                return stepSum.total[0] === 0 ? stepSum.total[1] : stepSum.total[0];
            }
    
            // 如果没有找到具体步骤的数据，计算所有步骤的总和
            const totalValue = perfSum.steps.reduce((sum, s) => {
                if (s.total.length > 1) {
                    // 如果第一个值（cycles）等于0，则使用第二个值（instructions）
                    return sum + (s.total[0] === 0 ? s.total[1] : s.total[0]);
                }
                return sum;
            }, 0);
            return totalValue;
    
        } catch (error) {
            logger.warn(`完整分析失败: ${error}`);
            return 0;
        }
    }
    
    /**
     * 选择最佳轮次
     */
    selectOptimalRound(results: Array<number>): number {
        if (results.length < 3) {
            return 0;
        }
    
        const max = Math.max(...results);
        const min = Math.min(...results);
        const total = results.reduce((sum, val) => sum + val, 0);
        const avg = (total - max - min) / (results.length - 2);
    
        let optimalIndex = 0;
        let minDiff = Number.MAX_SAFE_INTEGER;
    
        results.forEach((value, index) => {
            if (value === max || value === min) {
                return;
            }
    
            const diff = Math.abs(value - avg);
            if (diff < minDiff) {
                minDiff = diff;
                optimalIndex = index;
            }
        });
    
        return optimalIndex;
    }
    
    /**
     * 复制选中的轮次数据
     */
    async copySelectedRoundData(sourceRound: string, destPath: string, step: Step): Promise<void> {
        const stepIdx = step.stepIdx;
        const srcStepPaths = this.buildStepPaths(sourceRound, stepIdx);
        const destStepPaths = this.buildStepPaths(destPath, stepIdx);

        const srcResultDir = path.join(sourceRound, 'result');
        const destResultDir = path.join(destPath, 'result');

        // 构建ui目录路径
        const srcUiStepDir = path.join(sourceRound, 'ui', `step${stepIdx}`);
        const destUiStepDir = path.join(destPath, 'ui', `step${stepIdx}`);

        await Promise.all([
            copyDirectory(srcStepPaths.stepDir, destStepPaths.stepDir),
            copyDirectory(path.dirname(srcStepPaths.htracePath), path.dirname(destStepPaths.htracePath)),
            copyDirectory(srcResultDir, destResultDir),
            copyDirectory(srcUiStepDir, destUiStepDir)
        ]);
    }
    
    // ---- 负载分析/报告生成 ----
    
    /**
     * 生成负载分析报告
     */
    async generatePerfJson(inputPath: string, testInfo: TestReportInfo, steps: Steps, timeRanges?: Array<TimeRange>): Promise<void> {
        const outputDir = path.join(inputPath, 'report');
        const perfDataPaths = this.getPerfDataPaths(inputPath, steps);
        const perfDbPaths = await this.getPerfDbPaths(inputPath, steps);
        const htracePaths = this.getHtracePaths(inputPath, steps);
    
        const perfAnalyzer = new PerfAnalyzer('');
        const testSceneInfo = this.buildTestSceneInfo(testInfo);
    
        let round: Round = { steps: [] };
        for (let i = 0; i < steps.length; i++) {
            const stepPaths: StepPaths = {
                stepDir: '', // 不需要用到
                perfDataPath: perfDataPaths[i],
                dbPath: perfDbPaths[i],
                htracePath: htracePaths[i],
            };
            const group = this.buildTestStepGroup(inputPath, steps[i], stepPaths);
            round.steps.push(group);
        }
    
        testSceneInfo.rounds.push(round);
    
        // 如果有时间范围过滤，使用第一个时间范围（支持多个时间范围的功能可以后续扩展）
        const timeRange = timeRanges && timeRanges.length > 0 ? timeRanges[0] : undefined;
        if (timeRange) {
            logger.info(`Using time range filter: ${timeRange.startTime} - ${timeRange.endTime} nanoseconds`);
        }
    
        await perfAnalyzer.analyze(testSceneInfo, outputDir, timeRange);
        await perfAnalyzer.saveHiperfJson(testSceneInfo, path.join(outputDir, '../', 'hiperf', 'hiperf_info.json'));
        await perfAnalyzer.generateSummaryInfoJson(inputPath, testInfo, steps);
    }
    
    /**
     * 获取 perf.data 路径数组
     */
    getPerfDataPaths(inputPath: string, steps: Steps): Array<string> {
        return steps.map((step) => {
            const stepPaths = this.buildStepPaths(inputPath, step.stepIdx);
            if (fs.existsSync(stepPaths.perfDataPath)) {
                return stepPaths.perfDataPath;
            }
    
            // 如果都找不到，返回默认路径
            logger.warn(`未找到步骤 ${step.stepIdx} 的 perf.data 文件`);
            return stepPaths.perfDataPath;
        });
    }
    
    /**
     * 获取 perf.db 路径数组
     */
    async getPerfDbPaths(inputPath: string, steps: Steps): Promise<Array<string>> {
        const results: Array<string> = [];
    
        for (const step of steps) {
            const stepPaths = this.buildStepPaths(inputPath, step.stepIdx);
    
            if (fs.existsSync(stepPaths.dbPath)) {
                results.push(stepPaths.dbPath);
                continue;
            }
    
            if (!fs.existsSync(stepPaths.dbPath)) {
                await traceStreamerCmd(stepPaths.perfDataPath, stepPaths.dbPath);
            }
    
            results.push(stepPaths.dbPath);
        }
    
        return results;
    }
    
    /**
     * 获取 trace.htrace 路径数组
     */
    getHtracePaths(inputPath: string, steps: Steps): Array<string> {
        return steps.map((step) => {
            const stepPaths = this.buildStepPaths(inputPath, step.stepIdx);
            if (fs.existsSync(stepPaths.htracePath)) {
                return stepPaths.htracePath;
            }
    
            // 如果都找不到，返回默认路径
            logger.warn(`未找到步骤 ${step.stepIdx} 的 trace.htrace 文件`);
            return stepPaths.htracePath;
        });
    }
    
    // ---- 兼容性模式支持 ----
    /**
     * 加载兼容性模式的测试报告信息
     */
    loadCompatibilityTestReportInfo(reportRoot: string, scene: string): TestReportInfo {
        logger.info('加载兼容性模式测试报告信息');
    
        let info: TestReportInfo = {
            app_id: '',
            app_name: '',
            app_version: '',
            scene: scene,
            timestamp: 0,
            rom_version: '',
            device_sn: '',
        };
    
        // 解析结果XML文件
        let resultXml = path.join(reportRoot, 'result', `${scene}.xml`);
        if (!fs.existsSync(resultXml)) {
            logger.error(`loadTestReportInfo not found file ${resultXml}`);
        } else {
            try {
                const parser = new DOMParser();
                const xmlDoc = parser.parseFromString(fs.readFileSync(resultXml, 'utf-8'), 'text/xml');
                const testsuitesElement = xmlDoc.getElementsByTagName('testsuites')[0];
    
                let devicesAttr = testsuitesElement.getAttribute('devices');
                const starttimeStr = testsuitesElement.getAttribute('starttime');
    
                if (!starttimeStr || !devicesAttr) {
                    logger.error(`loadTestReportInfo parse file ${resultXml} error.`);
                } else {
                    const devices = JSON.parse(
                        devicesAttr
                            .replace(/<!\[CDATA\[(.*?)\]\]>/gs, '$1')
                            .replace(/^\[+/, '')
                            .replace(/]+$/, '')
                            .replace(/\\"/g, '"')
                    ) as { version: string; sn: string };
    
                    const starttime = new Date(starttimeStr);
                    info.rom_version = devices.version;
                    info.timestamp = starttime.getTime();
                    info.device_sn = devices.sn;
                }
            } catch (error) {
                logger.error(`${resultXml} 解析失败: ${error}`);
            }
        }
    
        // 解析设备信息文件
        let deviceInfoFile = path.join(reportRoot, 'env/device_info.json');
        try {
            if (fs.existsSync(deviceInfoFile)) {
                let deviceInfo = JSON.parse(fs.readFileSync(deviceInfoFile, 'utf-8')) as { PackageName: string, App_Version: string };
                info.app_id = deviceInfo.PackageName;
                info.app_version = deviceInfo.App_Version;
            }
            logger.info(`loadTestReportInfo ${reportRoot} done`);
        } catch (error) {
            logger.error(`${deviceInfoFile} 解析失败: ${error}`);
        }
    
        return info;
    }
}


