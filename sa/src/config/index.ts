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

import { LOG_MODULE_TYPE, Logger } from 'arkanalyzer';
import { loadConfig } from './loader';
import type { ComponentConfig, GlobalConfig } from './types';
const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

let _config: GlobalConfig | null = null;

export function initConfig(cliArgs: Partial<GlobalConfig>, afterLoad: (cfg: GlobalConfig) => void): void {
    _config = loadConfig(cliArgs);
    afterLoad(_config);
    _config = Object.freeze(_config);
}

export function getConfig(): GlobalConfig {
    return (_config ??= Object.freeze(loadConfig({})));
}

export function updateKindConfig(config: GlobalConfig, kindsJson: string): void {
    try {
        const kinds = JSON.parse(kindsJson) as Array<ComponentConfig>;
        config.perf.kinds.push(...kinds);
    } catch (error) {
        logger.error(`Invalid kind configuration: ${(error as Error).message} ${kindsJson}`);
    }
}



// 主要类和接口
export { HapAnalysisService } from '../services/analysis/hap_analysis';

// 类型定义
export * from './types';
export * from '../types/zip-types';

// 错误类
export * from '../errors';

// 工具函数
export * from '../utils/file_utils';
export * from '../utils/zip-adapter';

// 格式化器
export * from '../services/report';

import { HapAnalysisService } from '../services/analysis/hap_analysis';

/**
 * 快速分析HAP包的便捷函数
 * @param hapFilePath HAP包文件路径
 * @param verbose 是否详细输出
 * @returns 分析结果
 */
export async function analyzeHap(
    hapFilePath: string,
    verbose = false
): Promise<unknown> {
    const analyzer = new HapAnalysisService({ verbose });
    return await analyzer.analyzeHap(hapFilePath);
}
