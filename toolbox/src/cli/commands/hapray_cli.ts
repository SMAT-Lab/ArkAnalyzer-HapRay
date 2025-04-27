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
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { getComponentCategories } from '../../core/component';
import { PerfAnalyzer, StepItem, Step } from '../../core/perf/perf_analyzer';
import { GlobalConfig } from '../../config/types';
import { initConfig } from '../../config';
import { traceStreamerCmd } from '../../services/external/trace_streamer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
const VERSION = '1.0.0';

const DbtoolsCli = new Command('dbtools')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .action(async (...args: any[]) => {
        let cliArgs: Partial<GlobalConfig> = { ...args[0] };
        initConfig(cliArgs, (config) => {});

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

// 定义整个 steps 数组的结构
export type Steps = Step[];

function getPerfPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', step.stepIdx.toString(), 'perf.db'));
}

// async function main(config: GlobalConfig): Promise<void> {
async function main(input: string): Promise<void> {
    if (!fs.existsSync(input)) {
        logger.error(`${input} is not exists.`);
        return;
    }
    logger.info(`Input dir is: ${input}`);
    let output = path.join(input, 'report');
    if (!fs.existsSync(output)) {
        logger.info(`Creating output dir: ${output}`);
        fs.mkdirSync(output, { recursive: true });
    }
    output = path.join(input, 'report', 'hapray_report.html');

    // load testinfo.json
    let rawData = fs.readFileSync(path.join(input, 'testInfo.json'), 'utf8');
    const testInfo: TestInfo = JSON.parse(rawData);

    // load steps.json
    rawData = fs.readFileSync(path.join(input, 'hiperf', 'steps.json'), 'utf8');
    const steps: Steps = JSON.parse(rawData);
    let paths = getPerfPaths(input, steps);

    let stepsCollect: StepItem[] = [];
    for (let i = 0; i < steps.length; i++) {
        let tracePath = path.join(input, 'hiperf', steps[i].stepIdx.toString(), 'perf.data');
        let dbPath = path.join(input, 'hiperf', steps[i].stepIdx.toString(), 'perf.db');
        if (!fs.existsSync(dbPath)) {
            traceStreamerCmd(tracePath, dbPath);
        }
        let perfAnalyzer = new PerfAnalyzer('');
        stepsCollect.push(await perfAnalyzer.analyze2(dbPath, testInfo.app_id, steps[i]));
    }

    saveReport(output, testInfo, paths, stepsCollect);
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
        console.error('replaceAndWriteToNewFile:', error);
    }
}

function saveReport(output: string, testInfo: TestInfo, perfPaths: string[], steps: StepItem[]) {
    let res = path.join(__dirname, 'res');
    if (!fs.existsSync(res)) {
        res = path.join(__dirname, '../../../res');
    }
    let htmlTemplate = path.join(res, 'report_template.html');

    const jsonObject = {
        app_id: testInfo.app_id,
        app_name: testInfo.app_name,
        app_version: testInfo.app_version,
        scene: testInfo.scene,
        timestamp: testInfo.timestamp,
        perfPath: perfPaths,
        categories: getComponentCategories()
            .filter((category) => category.id >= 0)
            .map((category) => category.name),
        steps: steps,
    };
    let jsContent = JSON.stringify(jsonObject, null, 0);
    replaceAndWriteToNewFile(htmlTemplate, output, 'JSON_DATA_PLACEHOLDER', jsContent);
    return;
}

export const HaprayCli = new Command('hapray').version(VERSION).addCommand(DbtoolsCli);
