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
import { Command } from 'commander';
import { DOMParser } from '@xmldom/xmldom';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { getComponentCategories } from '../../core/component';
import { PerfAnalyzer, Step } from '../../core/perf/perf_analyzer';
import { GlobalConfig } from '../../config/types';
import { getConfig, initConfig } from '../../config';
import { traceStreamerCmd } from '../../services/external/trace_streamer';
import { checkPerfAndHtraceFiles, copyDirectory, copyFile, getSceneRoundsFolders } from '../../utils/folder_utils';
import { saveJsonArray } from '../../utils/json_utils';
import { TestSceneInfo } from '../../core/perf/perf_analyzer_base';
import { StepJsonData } from '../../core/perf/perf_data_transformer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
const VERSION = '1.0.0';

const DbtoolsCli = new Command('dbtools')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .option('--choose', 'choose one from rounds', false)
    .option('--disable-dbtools', 'disable dbtools', false)
    .option('-s, --soDir <string>', '--So_dir soDir', '')
    .action(async (...args: any[]) => {
        let cliArgs: Partial<GlobalConfig> = { ...args[0] };
        initConfig(cliArgs, (config) => {
            config.choose = args[0].choose;
            config.inDbtools = !args[0].disableDbtools;
        });

        await main(args[0].input);
    });

// 定义 testinfo.json 数据的结构
export interface TestInfo {
    app_id: string;
    app_name: string;
    app_version: string;
    scene: string;
    timestamp: number;
}

export interface ResultInfo {
    rom_version: string;
    device_sn: string;
}

// 定义整个 steps 数组的结构
export type Steps = Step[];

// 主函数逻辑
async function main(input: string): Promise<void> {
    const config = getConfig();
    
    if (config.choose) {
        logger.info(`输入目录: ${input}`);
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

        const stepsJsonPath = path.join(roundFolders[0], 'hiperf', 'steps.json');
        const steps: Steps = await loadJsonFile(stepsJsonPath);
        await processRoundSelection(roundFolders, steps, input);
    } else {
        logger.info(`输入目录: ${input}`);        
        const resultXmlPath = path.join(input, 'result', path.basename(input) + '.xml');
        const resultInfo = fs.existsSync(resultXmlPath) 
            ? parseResultXml(resultXmlPath) 
            : { rom_version: '', device_sn: '' };

        const testInfoPath = path.join(input, 'testInfo.json');
        const testInfo: TestInfo = await loadJsonFile(testInfoPath);
        
        const stepsJsonPath = path.join(input, 'hiperf', 'steps.json');
        const steps: Steps = await loadJsonFile(stepsJsonPath);
        
        if (!(await checkPerfAndHtraceFiles(input, steps.length))) {
            logger.error('hiperf 或 htrace 数据不全，需要先执行数据收集步骤！');
            return;
        }

        await generatePerfJson(input, testInfo, resultInfo, steps);
    }
}

// 加载 JSON 文件
async function loadJsonFile<T>(filePath: string): Promise<T> {
    const rawData = await fs.promises.readFile(filePath, 'utf8');
    return JSON.parse(rawData);
}

// 处理轮次选择逻辑
async function processRoundSelection(roundFolders: string[], steps: Steps, inputPath: string): Promise<void> {
    const testInfoPath = path.join(roundFolders[0], 'testInfo.json');
    await copyFile(testInfoPath, path.join(inputPath, 'testInfo.json'));

    const stepsJsonPath = path.join(roundFolders[0], 'hiperf', 'steps.json');
    await copyFile(stepsJsonPath, path.join(inputPath, 'hiperf', 'steps.json'));

    for (let i = 0; i < steps.length; i++) {
        const roundResults = await calculateRoundResults(roundFolders, steps[i]);
        const selectedRound = selectOptimalRound(roundResults);
        await copySelectedRoundData(roundFolders[selectedRound], inputPath, steps[i]);
    }
}

// 计算每轮的结果
async function calculateRoundResults(roundFolders: string[], step: Step): Promise<number[]> {
    const results: number[] = [];
    const perfAnalyzer = new PerfAnalyzer('');

    for (let index = 0; index < roundFolders.length; index++) {
        const perfDataPath = path.join(roundFolders[index], 'hiperf', `step${step.stepIdx}`, 'perf.data');
        const dbPath = path.join(roundFolders[index], 'hiperf', `step${step.stepIdx}`, 'perf.db');
        
        if (!fs.existsSync(dbPath)) {
            traceStreamerCmd(perfDataPath, dbPath);
        }

        const sum = await perfAnalyzer.calcPerfDbTotalInstruction(dbPath);
        results[index] = sum;
        logger.info(`${roundFolders[index]} 步骤：${step.stepIdx} 轮次：${index} 负载总数: ${sum}`);
    }
    return results;
}

// 选择最佳轮次
function selectOptimalRound(results: number[]): number {
    if (results.length < 3) return 0;

    const max = Math.max(...results);
    const min = Math.min(...results);
    const total = results.reduce((sum, val) => sum + val, 0);
    const avg = (total - max - min) / (results.length - 2);

    let optimalIndex = 0;
    let minDiff = Number.MAX_SAFE_INTEGER;

    results.forEach((value, index) => {
        if (value === max || value === min) return;
        
        const diff = Math.abs(value - avg);
        if (diff < minDiff) {
            minDiff = diff;
            optimalIndex = index;
        }
    });

    return optimalIndex;
}

// 复制选中的轮次数据
async function copySelectedRoundData(sourceRound: string, destPath: string, step: Step): Promise<void> {
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
        copyDirectory(srcResultDir, destResultDir)
    ]);
}

// 解析结果 XML 文件
function parseResultXml(xmlPath: string): ResultInfo {
    const result: ResultInfo = { rom_version: '', device_sn: '' };
    
    try {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(fs.readFileSync(xmlPath, 'utf-8'), 'text/xml');
        const testsuitesElement = xmlDoc.getElementsByTagName('testsuites')[0];
        const devicesAttr = testsuitesElement.getAttribute('devices');

        if (devicesAttr) {
            const devices = JSON.parse(
                devicesAttr
                    .replace(/<!\[CDATA\[(.*?)\]\]>/gs, '$1')
                    .replace(/^\[+|]+$/g, '')
                    .replace(/\\"/g, '"')
                    .replace(/'/g, '"')
            );
            result.rom_version = devices.version;
            result.device_sn = devices.sn;
        }
    } catch (error) {
        logger.error(`解析 ${xmlPath} 失败: ${error}`);
    }
    return result;
}

// 生成perfjson
async function generatePerfJson(inputPath: string, testInfo: TestInfo, resultInfo: ResultInfo, steps: Steps): Promise<void> {
    const outputDir = path.join(inputPath, 'report');
    const perfDataPaths = getPerfDataPaths(inputPath, steps);
    const perfDbPaths = getPerfDbPaths(inputPath, steps);
    const htracePaths = getHtracePaths(inputPath, steps);
    const stepsCollect: StepJsonData[] = [];

    for (let i = 0; i < steps.length; i++) {
        const perfAnalyzer = new PerfAnalyzer('');
        const stepData = await perfAnalyzer.analyze2(perfDbPaths[i], testInfo.app_id, steps[i]);
        
        const testSceneInfo: TestSceneInfo = {
            packageName: testInfo.app_id,
            scene: testInfo.scene,
            osVersion: resultInfo.rom_version,
            timestamp: testInfo.timestamp
        };
        
        await perfAnalyzer.analyze(perfDbPaths[i], testSceneInfo, outputDir, steps[i].stepIdx);
        
        stepData.round = 0;
        stepData.perf_data_path = perfDbPaths[i];
        stepsCollect.push(stepData);
    }

    await saveHiperfJson(outputDir, resultInfo, testInfo, perfDataPaths, perfDbPaths, htracePaths, stepsCollect);
}

function getPerfDataPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`, 'perf.data'));
}

function getPerfDbPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`, 'perf.db'));
}

function getHtracePaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'htrace', `step${step.stepIdx.toString()}`, 'trace.htrace'));
}

async function saveHiperfJson(output: string, resultInfo: ResultInfo, testInfo: TestInfo, perfDataPaths: string[], perfDbPaths: string[], htracePaths: string[], steps: StepJsonData[]): Promise<void> {
    output = path.join(output, '../', 'hiperf');
    const jsonObject = {
        rom_version: resultInfo.rom_version,
        app_id: testInfo.app_id,
        app_name: testInfo.app_name,
        app_version: testInfo.app_version,
        scene: testInfo.scene,
        timestamp: testInfo.timestamp,
        perfDataPath: perfDataPaths,
        perfDbPath: perfDbPaths,
        htracePath: htracePaths,
        categories: getComponentCategories()
            .filter((category) => category.id >= 0)
            .map((category) => category.name),
        steps: steps,
    };
    await saveJsonArray([jsonObject], path.join(output, 'hiperf_info.json'));
}

export const HaprayCli = new Command('hapray').version(VERSION).addCommand(DbtoolsCli);
