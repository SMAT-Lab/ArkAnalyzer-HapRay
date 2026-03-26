/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import { Command } from 'commander';
import { HapAnalysisService } from '../../services/analysis/hap_analysis';
import Logger, { LOG_MODULE_TYPE } from '../../utils/logger';
import { buildToolResult, emitToolResult } from '../../utils/machine_output';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

const DEFAULT_RESULT_BASENAME = 'hapray-tool-result.json';

interface AnalyzeOptions {
    input: string;
    output: string;
    jobs?: number;
    beautifyJs?: boolean;
    machineJson?: boolean;
    resultFile?: string;
}

const VERSION = '1.0.0';

export const HapAnalyzerCli = new Command('hap')
    .version(VERSION)
    .description('HAP 静态分析器 - 分析 HAP/ZIP 文件或目录中的技术栈与资源')
    .requiredOption('-i, --input <path>', '分析输入路径（HAP/ZIP 文件或目录）')
    .option('-o, --output <path>', '输出目录', './output')
    .option('-j, --jobs <number>', '并发分析数量，默认为CPU核心数', undefined)
    .option('--beautify-js', '美化压缩的 JS 文件并保存到输出目录', false)
    .option(
        '--result-file <path>',
        `tool-result JSON 写入路径（默认: <output>/${DEFAULT_RESULT_BASENAME}）`
    )
    .option(
        '--machine-json',
        '无法写入结果文件时，在 stdout 输出一行 JSON（兜底）；日志走 stderr',
        false
    )
    .action(async (options: AnalyzeOptions) => {
        await analyzeHap(options);
    });

async function writeToolResultToFile(filePath: string, payload: ReturnType<typeof buildToolResult>): Promise<void> {
    const abs = path.resolve(filePath);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, JSON.stringify(payload, null, 2), 'utf8');
}

async function analyzeHap(options: AnalyzeOptions): Promise<void> {
    const { input, output, jobs, beautifyJs, machineJson, resultFile } = options;

    const mappedOutput = Logger.mapOutputPath('hap', output);
    const defaultResultPath = path.join(mappedOutput, DEFAULT_RESULT_BASENAME);
    const targetResultPath = resultFile ? path.resolve(resultFile) : defaultResultPath;

    try {
        const analyzer = new HapAnalysisService({ verbose: true, beautifyJs });
        await analyzer.analyzeMultipleHaps(input, mappedOutput, jobs);
        const payload = buildToolResult(
            'static_analyzer',
            true,
            0,
            { output_dir: mappedOutput, input, hapray_tool_result_path: targetResultPath },
            null,
            VERSION,
            'hap'
        );
        try {
            await writeToolResultToFile(targetResultPath, payload);
        } catch (writeErr) {
            logger.error('写入 tool-result 失败：', writeErr);
            if (machineJson) {
                Logger.reconfigureForMachineJson();
                emitToolResult({
                    ...payload,
                    outputs: { ...payload.outputs, hapray_tool_result_sink: 'stdout' },
                });
            }
        }
    } catch (error) {
        logger.error('分析失败：', error);
        const payload = buildToolResult(
            'static_analyzer',
            false,
            1,
            {
                input,
                output: mappedOutput,
                hapray_tool_result_path: targetResultPath,
            },
            error instanceof Error ? error.message : String(error),
            VERSION,
            'hap'
        );
        try {
            await writeToolResultToFile(targetResultPath, payload);
        } catch {
            if (machineJson) {
                Logger.reconfigureForMachineJson();
                emitToolResult(payload);
            }
        }
        process.exit(1);
    }
}
