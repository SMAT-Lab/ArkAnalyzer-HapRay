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

// 主要类和接口
export { HapStaticAnalyzer } from './hap-static-analyzer';

// 分析器
export { SoAnalyzer } from './analyzers/so-analyzer';
export { ResourceAnalyzer } from './analyzers/resource-analyzer';

// 类型定义
export * from './types';

// 错误类
export * from './errors';


// 格式化器
export * from './formatters';

import { HapStaticAnalyzer } from './hap-static-analyzer';

/**
 * 快速分析HAP包的便捷函数
 * @param hapFilePath HAP包文件路径
 * @param verbose 是否详细输出
 * @returns 分析结果
 */
export async function analyzeHap(
    hapFilePath: string,
    verbose = false
) {
    const analyzer = new HapStaticAnalyzer(verbose);
    return await analyzer.analyzeHap(hapFilePath);
}
