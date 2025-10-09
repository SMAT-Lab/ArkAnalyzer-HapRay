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

/**
 * 框架类型配置
 */
export interface FrameworkTypeConfig {
    name: string;
    description: string;
}

/**
 * 文件类型配置
 */
export interface FileTypeConfig {
    name: string;
    description: string;
    category: string;
}

/**
 * 合并后的配置文件结构
 */
export interface MergedConfig {
    frameworks: Record<string, FrameworkTypeConfig & { patterns: Array<string> }>;
    systemLibraries: Array<string>;
    fileTypes: Record<string, FileTypeConfig>;
}

let mergedConfig: MergedConfig | null = null;

/**
 * 加载合并后的配置
 */
function loadMergedConfig(): MergedConfig {
    if (mergedConfig) {
        return mergedConfig;
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
    mergedConfig = JSON.parse(configData);
    return mergedConfig!;
}

/**
 * 获取所有框架类型
 */
export function getFrameworkTypes(): Array<string> {
    const config = loadMergedConfig();
    return Object.keys(config.frameworks);
}

/**
 * 获取所有文件类型
 */
export function getFileTypes(): Array<string> {
    const config = loadMergedConfig();
    return Object.keys(config.fileTypes);
}

/**
 * 检查文件类型是否存在（仅保留被使用的方法）
 */
export function isValidFileType(type: string): boolean {
    const config = loadMergedConfig();
    return type in config.fileTypes;
}

/**
 * 动态创建框架类型枚举对象
 */
export function createFrameworkTypeEnum(): Record<string, string> {
    const types = getFrameworkTypes();
    const enumObj: Record<string, string> = {};
    
    types.forEach(type => {
        enumObj[type] = type;
    });
    
    return enumObj;
}

/**
 * 动态创建文件类型枚举对象
 */
export function createFileTypeEnum(): Record<string, string> {
    const types = getFileTypes();
    const enumObj: Record<string, string> = {};
    
    types.forEach(type => {
        enumObj[type] = type;
    });
    
    return enumObj;
}
