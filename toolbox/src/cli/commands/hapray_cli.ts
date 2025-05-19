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
import { DOMParser } from 'xmldom';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { getComponentCategories } from '../../core/component';
import { PerfAnalyzer, StepItem, Step } from '../../core/perf/perf_analyzer';
import { GlobalConfig } from '../../config/types';
import { initConfig } from '../../config';
import { traceStreamerCmd } from '../../services/external/trace_streamer';
import { copyDirectory, getSceneRoundsFolders } from '../../utils/folder_utils';
import { saveJsonArray } from '../../utils/json_utils';
import { TestSceneInfo } from '../../core/perf/perf_analyzer_base';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
const VERSION = '1.0.0';

const DbtoolsCli = new Command('dbtools')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .option('--disable-dbtools', 'disable dbtools', false)
    .action(async (...args: any[]) => {
        let cliArgs: Partial<GlobalConfig> = { ...args[0] };
        initConfig(cliArgs, (config) => {
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

export interface RoundInfo {
    step_name: string,
    step_id: number,
    round: number,
}

export interface ResultInfo {
    rom_version: string;
    device_sn: string;
}

// 定义整个 steps 数组的结构
export type Steps = Step[];

function getPerfDataPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`, 'perf.data'));
}

function getPerfDbPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`, 'perf.db'));
}

function getHtracePaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'htrace', `step${step.stepIdx.toString()}`, 'trace.htrace'));
}

// async function main(config: GlobalConfig): Promise<void> {
async function main(input: string): Promise<void> {



    if (!fs.existsSync(input)) {
        logger.error(`${input} is not exists.`);
        return;
    }
    logger.info(`Input dir is: ${input}`);
    const roundFolders = getSceneRoundsFolders(input);
    if (roundFolders.length === 0) {
        logger.error(input + '一轮测试信息都没有,无法生成报告！');
        return;
    }
    let output = path.join(input, 'report');
    if (!fs.existsSync(output)) {
        logger.info(`Creating output dir: ${output}`);
        fs.mkdirSync(output, { recursive: true });
    }
    output = path.join(input, 'report', 'hapray_report.html');

    //load result.xml
    let resultXml = path.join(input, 'result', path.basename(input) + '.xml');
    let resultInfo: ResultInfo = { rom_version: '', device_sn: '' };
    if (!fs.existsSync(resultXml)) {
        logger.error('load' + resultXml + ':失败！');
    } else {
        try {
            // 使用 DOMParser 解析 XML字符串
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(fs.readFileSync(resultXml, 'utf-8'), 'text/xml');

            // 获取 testsuites 元素
            const testsuitesElement = xmlDoc.getElementsByTagName('testsuites')[0];

            // 提取starttime 属性
            let devicesAttr = testsuitesElement.getAttribute('devices');

            if (!devicesAttr) {
                logger.error('parse' + resultXml + ':失败！');
            } else {
                const devices = JSON.parse(
                    devicesAttr
                        .replace(/<!\[CDATA\[(.*?)\]\]>/gs, '$1')
                        .replace(/^\[+/, '')
                        .replace(/]+$/, '')
                        .replace(/\\"/g, '"')
                        .replace(/'/g, '"'));
                resultInfo.rom_version = devices.version;
                resultInfo.device_sn = devices.sn;
            }
        } catch (error) {
            logger.error('parse' + resultXml + ':失败！');
        }
    }

    // load testinfo.json
    let rawData = fs.readFileSync(path.join(roundFolders[0], 'testInfo.json'), 'utf8');
    const testInfo: TestInfo = JSON.parse(rawData);

    // load steps.json
    rawData = fs.readFileSync(path.join(roundFolders[0], 'hiperf', 'steps.json'), 'utf8');
    const steps: Steps = JSON.parse(rawData);
    let perfDataPaths = getPerfDataPaths(input, steps);
    let perfDbPaths = getPerfDbPaths(input, steps);
    let htracePaths = getHtracePaths(input, steps);
    let stepsCollect: StepItem[] = [];

    for (let i = 0; i < steps.length; i++) {
        let stepItem: StepItem;
        let result: number[] = [];
        let perfAnalyzer = new PerfAnalyzer('');
        let dbPaths: string[] = [];
        let tracePaths: string[] = [];
        let choose = 0;
        let tracePath = '';
        let dbPath = '';
        if (roundFolders.length >= 3) {
            for (let index = 0; index < roundFolders.length; index++) {
                const roundFolder = roundFolders[index];

                tracePath = path.join(roundFolders[index], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.data');
                dbPath = path.join(roundFolders[index], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.db');
                if (!fs.existsSync(dbPath)) {
                    traceStreamerCmd(tracePath, dbPath);
                }
                dbPaths.push(dbPath);
                tracePaths.push(tracePath);

                const sum = await perfAnalyzer.calcPerfDbTotalInstruction(dbPath);
                result[index] = sum;
                logger.info(roundFolder + '步骤：' + i + '轮次：' + index + '负载总数:' + sum);
            }
            let total = 0;
            let max = Math.max(...result);
            let min = Math.min(...result);
            result.map((v) => (total += v));
            let avg = (total - max - min) / (result.length - 2);


            let skipMax = false;
            let skipMin = false;
            let diffMin = max;

            for (let idx = 0; idx < result.length; idx++) {
                const v = result[idx];
                if (v === max && !skipMax) {
                    skipMax = true;
                    continue;
                }
                if (v === min && !skipMin) {
                    skipMin = true;
                    continue;
                }
                let diff = Math.abs(v - avg);
                if (diff < diffMin) {
                    diffMin = diff;
                    choose = idx;
                }
            }
        } else {
            tracePath = path.join(roundFolders[0], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.data');
            dbPath = path.join(roundFolders[0], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.db');
            if (!fs.existsSync(dbPath)) {
                traceStreamerCmd(tracePath, dbPath);
            }
            dbPaths.push(dbPath);
            tracePaths.push(tracePath);
        }

        logger.info(dbPaths[choose] + ' : setp' + i + ' select round' + choose + ' .');
        //将hiperf和htrace文件复制到最终目录
        const choosePerfDir = path.join(roundFolders[choose], 'hiperf', `step${steps[i].stepIdx.toString()}`);
        const chooseHtraceDir = path.join(roundFolders[choose], 'htrace', `step${steps[i].stepIdx.toString()}`);
        const scenePerfDir = path.join(input, 'hiperf', `step${steps[i].stepIdx.toString()}`);
        const sceneHtraceDir = path.join(input, 'htrace', `step${steps[i].stepIdx.toString()}`);
        await copyDirectory(choosePerfDir, scenePerfDir);
        await copyDirectory(chooseHtraceDir, sceneHtraceDir);
        stepItem = await perfAnalyzer.analyze2(dbPaths[choose], testInfo.app_id, steps[i]);
        let testSceneInfo: TestSceneInfo = { packageName: testInfo.app_id, scene: testInfo.scene, osVersion: resultInfo.rom_version, timestamp: testInfo.timestamp };
        await perfAnalyzer.analyze(dbPaths[choose], testSceneInfo, output, steps[i].stepIdx, choose);
        stepItem.round = choose;
        stepItem.perf_data_path = tracePaths[choose];
        stepsCollect.push(stepItem);
    }

    await saveReport(output, resultInfo, testInfo, perfDataPaths, perfDbPaths, htracePaths, stepsCollect);
}


function replaceAndWriteToNewFile(
    inputPath: string,
    outputPath: string,
    placeholder: string,
    replacement: string
): void {
    try {
        const fileContent = fs.readFileSync(inputPath, 'utf-8');
        const updatedContent = fileContent.replace(placeholder, replacement);

        fs.writeFileSync(outputPath, updatedContent, 'utf-8');
    } catch (error) {
        logger.error('replaceAndWriteToNewFile:', error);
    }
}

async function saveReport(output: string, resultInfo: ResultInfo, testInfo: TestInfo, perfDataPaths: string[], perfDbPaths: string[], htracePaths: string[], steps: StepItem[]): Promise<void> {
    let res = path.join(__dirname, 'res');
    if (!fs.existsSync(res)) {
        res = path.join(__dirname, '../../../res');
    }
    let htmlTemplate = path.join(res, 'report_template.html');

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
    let jsContent = JSON.stringify(jsonObject, null, 0);
    replaceAndWriteToNewFile(htmlTemplate, output, 'JSON_DATA_PLACEHOLDER', jsContent);

    let roundsJsonObject: RoundInfo[] = []
    steps.forEach(step => {
        const roundJsonObject: RoundInfo = {
            step_name: step.step_name,
            step_id: step.step_id,
            round: step.round,
        }
        roundsJsonObject.push(roundJsonObject);
    })
    await saveJsonArray(roundsJsonObject, path.join(output, '../rounds_info.json'));

}

export const HaprayCli = new Command('hapray').version(VERSION).addCommand(DbtoolsCli);
