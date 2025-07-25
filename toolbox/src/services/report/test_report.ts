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
import type { Step } from '../../core/perf/perf_analyzer';
import { PerfAnalyzer } from '../../core/perf/perf_analyzer';
import { getConfig } from '../../config';
import { traceStreamerCmd } from '../../services/external/trace_streamer';
import { checkPerfFiles, copyDirectory, copyFile, getSceneRoundsFolders } from '../../utils/folder_utils';
import { saveJsonArray } from '../../utils/json_utils';
import type { Round, TestSceneInfo as PerfTestSceneInfo, TestStepGroup } from '../../core/perf/perf_analyzer_base';
import type { GlobalConfig } from '../../config/types';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

// ===================== 类型定义 =====================
export interface TestReportInfo {
    app_id: string;
    app_name: string;
    app_version: string;
    scene: string;
    timestamp: number;
    rom_version: string;
    device_sn: string;
}

export interface SummaryInfo {
    rom_version: string;
    app_version: string;
    scene: string;
    step_name: string;
    step_id: number;
    count: number;
    round: number;
}

export interface RoundInfo {
    step_id: number;
    round: number;
    count: number;
}

export type Steps = Array<Step>;

// ===================== 主流程入口 =====================
/**
 * 入口主函数
 */
export async function main(input: string): Promise<void> {
    const config = getConfig();
    const scene = path.basename(input);
    if (config.ut === true) {
        input = path.join(__dirname, '..', '..', '..', 'test', 'resources', 'ResourceUsage_PerformanceDynamic_jingdong_0010');
    }
    logger.info(`输入目录: ${input}`);

    if (config.choose && !config.ut) {
        await handleChooseRound(input, scene, config);
    } else {
        await handleGeneratePerfReport(input, scene, config);
    }
}

// ===================== 模式处理函数 =====================
/**
 * 处理选择轮次（choose round）
 */
async function handleChooseRound(input: string, scene: string, config: GlobalConfig): Promise<void> {
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

    const steps = await loadSteps(roundFolders[0]);
    const roundInfos = await processRoundSelection(roundFolders, steps, input);
    const testReportInfo = await loadTestReportInfo(input, scene, config);

    await generateSummaryInfoJson(input, testReportInfo, steps, roundInfos);
}

/**
 * 处理生成报告（Generate PerfReport）
 */
async function handleGeneratePerfReport(input: string, scene: string, config: GlobalConfig): Promise<void> {
    const steps = await loadSteps(input);

    if (!(await checkPerfFiles(input, steps.length))) {
        logger.error('hiperf 数据不全，需要先执行数据收集步骤！');
        return;
    }

    const testReportInfo = await loadTestReportInfo(input, scene, config);
    await generatePerfJson(input, testReportInfo, steps);
}

// ===================== 数据加载函数 =====================
/**
 * 加载步骤信息
 */
async function loadSteps(basePath: string): Promise<Steps> {
    const stepsJsonPath = path.join(basePath, 'hiperf', 'steps.json');
    return await loadJsonFile<Steps>(stepsJsonPath);
}

/**
 * 加载测试报告信息
 */
async function loadTestReportInfo(input: string, scene: string, config: GlobalConfig): Promise<TestReportInfo> {
    if (config.compatibility) {
        return loadCompatibilityTestReportInfo(input, scene);
    } else {
        return await loadStandardTestReportInfo(input);
    }
}

/**
 * 加载标准模式的测试报告信息
 */
async function loadStandardTestReportInfo(input: string): Promise<TestReportInfo> {
    const testInfoPath = path.join(input, 'testInfo.json');
    const testInfo = await loadJsonFile<{
        app_id: string;
        app_name: string;
        app_version: string;
        scene: string;
        timestamp: number;
        device?: {
            version: string;
            sn: string;
        };
    }>(testInfoPath);
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
export async function loadJsonFile<T>(filePath: string): Promise<T> {
    const rawData = await fs.promises.readFile(filePath, 'utf8');
    return JSON.parse(rawData) as T;
}

// ---- 轮次处理相关 ----
/**
 * 处理轮次选择逻辑
 */
export async function processRoundSelection(
    roundFolders: Array<string>,
    steps: Steps,
    inputPath: string
): Promise<Array<RoundInfo>> {
    let roundInfos: Array<RoundInfo> = [];

    await copyStandardFiles(roundFolders[0], inputPath);

    for (const step of steps) {
        const roundResults = await calculateRoundResults(roundFolders, step);
        const selectedRound = selectOptimalRound(roundResults);
        const roundInfo: RoundInfo = {
            step_id: step.stepIdx,
            round: selectedRound,
            count: roundResults[selectedRound],
        };
        roundInfos.push(roundInfo);
        await copySelectedRoundData(roundFolders[selectedRound], inputPath, step);
    }
    return roundInfos;
}

/**
 * 复制标准模式的文件
 */
async function copyStandardFiles(sourceRound: string, inputPath: string): Promise<void> {
    const testInfoPath = path.join(sourceRound, 'testInfo.json');
    await copyFile(testInfoPath, path.join(inputPath, 'testInfo.json'));

    const stepsJsonPath = path.join(sourceRound, 'hiperf', 'steps.json');
    await copyFile(stepsJsonPath, path.join(inputPath, 'hiperf', 'steps.json'));
}

/**
 * 计算每轮的结果
 */
export async function calculateRoundResults(roundFolders: Array<string>, step: Step): Promise<Array<number>> {
    const results: Array<number> = [];
    const perfAnalyzer = new PerfAnalyzer('');

    for (let index = 0; index < roundFolders.length; index++) {
        const stepDir = path.join(roundFolders[index], 'hiperf', `step${step.stepIdx}`);
        let perfDataPath: string;
        let dbPath: string;
        //格式
        perfDataPath = path.join(stepDir, 'perf.data');
        dbPath = path.join(stepDir, 'perf.db');

        if (!fs.existsSync(dbPath)) {
            await traceStreamerCmd(perfDataPath, dbPath);
        }

        const sum = await perfAnalyzer.calcPerfDbTotalInstruction(dbPath);
        results[index] = sum;
        logger.info(`${roundFolders[index]} 步骤：${step.stepIdx} 轮次：${index} 负载总数: ${sum}`);
    }

    return results;
}

/**
 * 选择最佳轮次
 */
export function selectOptimalRound(results: Array<number>): number {
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
export async function copySelectedRoundData(sourceRound: string, destPath: string, step: Step): Promise<void> {
    const stepIdx = step.stepIdx;
    const srcPerfDir = path.join(sourceRound, 'hiperf', `step${stepIdx}`);
    const srcHtraceDir = path.join(sourceRound, 'htrace', `step${stepIdx}`);
    const srcResultDir = path.join(sourceRound, 'result');

    const destPerfDir = path.join(destPath, 'hiperf', `step${stepIdx}`);
    const destHtraceDir = path.join(destPath, 'htrace', `step${stepIdx}`);
    const destResultDir = path.join(destPath, 'result');

    await Promise.all([
        copyDirectory(srcPerfDir, destPerfDir),
        copyDirectory(srcHtraceDir, destHtraceDir),
        copyDirectory(srcResultDir, destResultDir),
    ]);
}

// ---- 性能分析/报告生成 ----
/**
 * 生成 summary_info.json
 */
export async function generateSummaryInfoJson(
    input: string,
    testInfo: TestReportInfo,
    steps: Steps,
    roundInfos: Array<RoundInfo>
): Promise<void> {
    const outputDir = path.join(input, 'report');
    let summaryJsonObject: Array<SummaryInfo> = [];

    steps.forEach((step) => {
        const roundInfo = roundInfos.find((round) => round.step_id === step.stepIdx);
        if (!roundInfo) {
            logger.warn(`未找到步骤 ${step.stepIdx} 的轮次信息`);
            return;
        }

        const summaryObject: SummaryInfo = {
            rom_version: testInfo.rom_version,
            app_version: testInfo.app_version,
            scene: testInfo.scene,
            step_name: step.description,
            step_id: step.stepIdx,
            count: roundInfo.count,
            round: roundInfo.round,
        };
        summaryJsonObject.push(summaryObject);
    });

    await saveJsonArray(summaryJsonObject, path.join(outputDir, 'summary_info.json'));
}

/**
 * 生成性能分析报告
 */
export async function generatePerfJson(inputPath: string, testInfo: TestReportInfo, steps: Steps): Promise<void> {
    const outputDir = path.join(inputPath, 'report');
    const perfDataPaths = getPerfDataPaths(inputPath, steps);
    const perfDbPaths = await getPerfDbPaths(inputPath, steps);
    const htracePaths = getHtracePaths(inputPath, steps);

    const perfAnalyzer = new PerfAnalyzer('');
    const testSceneInfo: PerfTestSceneInfo = {
        packageName: testInfo.app_id,
        appName: testInfo.app_name,
        scene: testInfo.scene,
        osVersion: testInfo.rom_version,
        timestamp: testInfo.timestamp,
        appVersion: testInfo.app_version,
        rounds: [],
        chooseRound: 0,
    };

    let round: Round = { steps: [] };
    for (let i = 0; i < steps.length; i++) {
        let group: TestStepGroup = {
            reportRoot: inputPath,
            groupId: steps[i].stepIdx,
            groupName: steps[i].description,
            dbfile: perfDbPaths[i],
            perfFile: perfDataPaths[i],
            traceFile: htracePaths[i],
        };
        round.steps.push(group);
    }

    testSceneInfo.rounds.push(round);
    await perfAnalyzer.analyze(testSceneInfo, outputDir);
    await perfAnalyzer.saveHiperfJson(testSceneInfo, path.join(outputDir, '../', 'hiperf', 'hiperf_info.json'));
}

/**
 * 获取 perf.data 路径数组（根据兼容性配置选择格式）
 */
export function getPerfDataPaths(inputPath: string, steps: Steps): Array<string> {
    return steps.map((step) => {
        const stepDir = path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`);
        // 格式：perf.data
        const oldFile = path.join(stepDir, 'perf.data');
        if (fs.existsSync(oldFile)) {
            return oldFile;
        }

        // 如果都找不到，返回默认路径
        logger.warn(`未找到步骤 ${step.stepIdx} 的 perf.data 文件`);
        return oldFile;
    });
}

/**
 * 获取 perf.db 路径数组（根据兼容性配置选择格式）
 */
export async function getPerfDbPaths(inputPath: string, steps: Steps): Promise<Array<string>> {
    const results: Array<string> = [];

    for (const step of steps) {
        const stepDir = path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`);
        // 格式：perf.db
        const oldFile = path.join(stepDir, 'perf.db');

        if (fs.existsSync(oldFile)) {
            results.push(oldFile);
            continue;
        }

        if (!fs.existsSync(oldFile)) {
            await traceStreamerCmd(path.join(path.dirname(oldFile), 'perf.data'), oldFile);
        }

        results.push(oldFile);
    }

    return results;
}

/**
 * 获取 trace.htrace 路径数组（根据兼容性配置选择格式）
 */
export function getHtracePaths(inputPath: string, steps: Steps): Array<string> {
    return steps.map((step) => {
        const stepDir = path.join(inputPath, 'htrace', `step${step.stepIdx.toString()}`);
        // 格式：trace.htrace
        const oldFile = path.join(stepDir, 'trace.htrace');
        if (fs.existsSync(oldFile)) {
            return oldFile;
        }

        // 如果都找不到，返回默认路径
        logger.warn(`未找到步骤 ${step.stepIdx} 的 trace.htrace 文件`);
        return oldFile;
    });
}

// ---- 兼容性模式支持 ----
/**
 * 加载兼容性模式的测试报告信息
 */
export function loadCompatibilityTestReportInfo(reportRoot: string, scene: string): TestReportInfo {
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
