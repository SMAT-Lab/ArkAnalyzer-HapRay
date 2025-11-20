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
import { HapAnalysisService } from '../../services/analysis/hap_analysis';
import { LOG_MODULE_TYPE, Logger } from 'arkanalyzer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

interface AnalyzeOptions {
    input: string;
    output: string;
    jobs?: string;
    beautifyJs?: boolean;
}

const VERSION = '1.0.0';

export const HapAnalyzerCli = new Command('hap')
    .version(VERSION)
    .description('HAP 静态分析器 - 分析 HAP/ZIP 文件或目录中的技术栈与资源')
    .requiredOption('-i, --input <path>', '分析输入路径（HAP/ZIP 文件或目录）')
    .option('-o, --output <path>', '输出目录', './output')
    .option('-j, --jobs <number>', '并发分析数量，默认为CPU核心数', 'auto')
    .option('--beautify-js', '美化压缩的 JS 文件并保存到输出目录', false)
    .action(async (options: AnalyzeOptions) => {
        await analyzeHap(options);
    });

async function analyzeHap(options: AnalyzeOptions): Promise<void> {
    const { input, output, jobs, beautifyJs } = options;

    try {
        const analyzer = new HapAnalysisService({ verbose: true, beautifyJs });
        await analyzer.analyzeMultipleHaps(input, output, jobs);
    } catch (error) {
        logger.error('分析失败：', error);
        process.exit(1);
    }
}

