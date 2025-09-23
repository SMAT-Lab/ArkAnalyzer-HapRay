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

interface FrameworkConfig {
    name: string;
    patterns: string[];
    description: string;
}

interface FrameworkPatternsConfig {
    frameworks: Record<string, FrameworkConfig>;
    systemLibraries: string[];
    fileTypes: Record<string, unknown>; // 添加fileTypes字段但不使用
}

let frameworkConfig: FrameworkPatternsConfig | null = null;

/**
 * 加载框架配置 - 只从JSON文件读取
 */
function loadFrameworkConfig(): FrameworkPatternsConfig {
    if (frameworkConfig) {
        return frameworkConfig;
    }

    // 使用toolbox的方法：先尝试当前目录，再尝试上级目录
    let resDir = path.join(__dirname, 'res');
    if (!fs.existsSync(resDir)) {
        resDir = path.join(__dirname, '../../res');
    }

    const configPath = path.join(resDir, 'framework-patterns.json');

    if (!fs.existsSync(configPath)) {
        throw new Error(`Framework patterns config file not found at: ${configPath}`);
    }

    const configData = fs.readFileSync(configPath, 'utf-8');
    frameworkConfig = JSON.parse(configData);
    return frameworkConfig!;
}

/**
 * 获取技术栈框架SO文件匹配规则
 */
export function getFrameworkPatterns(): Record<string, string[]> {
    const config = loadFrameworkConfig();
    const patterns: Record<string, string[]> = {};

    // 直接从配置中获取所有框架的模式
    for (const [key, framework] of Object.entries(config.frameworks)) {
        patterns[key] = framework.patterns;
    }

    return patterns;
}

/**
 * 获取系统库SO文件模式
 */
export function getSystemSoPatterns(): string[] {
    const config = loadFrameworkConfig();
    return config.systemLibraries;
}

/**
 * 检查SO文件名是否匹配指定的模式
 * @param fileName SO文件名
 * @param pattern 匹配模式（支持正则表达式）
 * @returns 是否匹配
 */
export function matchSoPattern(fileName: string, pattern: string): boolean {
    try {
        // 简单的通配符转正则表达式
        // 将 .* 视为正则表达式中的 .*（匹配任意字符）
        // 将单独的 * 视为通配符（匹配任意字符）
        // 转义其他特殊字符

        let regexPattern = pattern;

        // 先处理 .* 模式（保持不变）
        regexPattern = regexPattern.replace(/\.\*/g, '__DOT_STAR__');

        // 转义其他正则表达式特殊字符
        regexPattern = regexPattern.replace(/[.+^${}()|[\]\\]/g, '\\$&');

        // 处理单独的 * 通配符
        regexPattern = regexPattern.replace(/\*/g, '.*');

        // 恢复 .* 模式
        regexPattern = regexPattern.replace(/__DOT_STAR__/g, '.*');

        const regex = new RegExp(`^${regexPattern}$`, 'i');
        return regex.test(fileName);
    } catch (error) {
        console.warn(`Invalid pattern: ${pattern}`, error);
        return false;
    }
}

/**
 * 检查SO文件是否为系统库
 * @param fileName SO文件名
 * @returns 是否为系统库
 */
export function isSystemSo(fileName: string): boolean {
    const systemPatterns = getSystemSoPatterns();
    return systemPatterns.some((pattern: string) => matchSoPattern(fileName, pattern));
}
