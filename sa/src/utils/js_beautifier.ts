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

import * as esprima from 'esprima';
import * as escodegen from 'escodegen';
import { Logger, LOG_MODULE_TYPE } from 'arkanalyzer';
import { TechStackConfigLoader } from '../config/techstack_config_loader';
import type { JavaScriptDetectionConfig } from '../core/techstack/types';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * JS 文件识别和格式化工具
 */
export class JsBeautifier {
    private static config: JavaScriptDetectionConfig | null = null;

    /**
     * 获取 JavaScript 检测配置
     */
    private static getConfig(): JavaScriptDetectionConfig {
        if (!this.config) {
            const techStackConfig = TechStackConfigLoader.getInstance().getConfig();
            if (techStackConfig.javascriptDetection) {
                this.config = techStackConfig.javascriptDetection;
            } else {
                // 使用默认配置
                logger.warn('未找到 JavaScript 检测配置，使用默认配置');
                this.config = this.getDefaultConfig();
            }
        }
        return this.config;
    }

    /**
     * 获取默认配置
     */
    private static getDefaultConfig(): JavaScriptDetectionConfig {
        return {
            extensions: ['js', 'mjs', 'cjs'],
            contentPatterns: [
                '\\bfunction\\s+\\w+\\s*\\(',
                '\\bconst\\s+\\w+\\s*=',
                '\\blet\\s+\\w+\\s*=',
                '\\bvar\\s+\\w+\\s*=',
                '\\bclass\\s+\\w+',
                '\\bimport\\s+.*\\s+from\\s+[\'"]',
                '\\bexport\\s+(default\\s+)?\\w+',
                '\\bmodule\\.exports\\s*=',
                '\\brequire\\s*\\([\'"]',
                '=>\\s*\\{',
            ],
            minificationThresholds: {
                avgLineLength: 200,
                maxLineLength: 500,
                whitespaceRatio: 0.05,
                maxLines: 10,
            },
            minContentLength: 10,
        };
    }
    /**
     * 检测文件内容是否为 JavaScript 代码
     * @param content 文件内容（Buffer 或字符串）
     * @param fileName 文件名（可选，用于辅助判断）
     * @returns true 表示是 JS 文件，false 表示不是
     */
    public static isJavaScriptContent(content: Buffer | string, fileName?: string): boolean {
        try {
            const config = this.getConfig();

            // 1. 先检查文件扩展名（快速路径）
            if (fileName) {
                const ext = fileName.toLowerCase().split('.').pop();
                if (ext && config.extensions.includes(ext)) {
                    return true;
                }
            }

            // 2. 转换为字符串
            const code: string = content instanceof Buffer ? content.toString('utf-8') : content as string;

            // 3. 检查是否为空或过短
            if (!code || code.trim().length < config.minContentLength) {
                return false;
            }

            // 4. 检查常见的 JS 代码模式（从配置加载）
            for (const patternStr of config.contentPatterns) {
                const pattern = new RegExp(patternStr);
                if (pattern.test(code)) {
                    return true;
                }
            }

            // 5. 尝试解析为 JavaScript（最终验证）
            // 只检查前 8KB 内容以提高性能
            const sampleCode = code.substring(0, 8192);
            try {
                esprima.parseScript(sampleCode, { tolerant: true });
                return true;
            } catch {
                // 如果 parseScript 失败，尝试 parseModule
                try {
                    esprima.parseModule(sampleCode, { tolerant: true });
                    return true;
                } catch {
                    return false;
                }
            }
        } catch (error) {
            logger.warn(`Failed to detect JavaScript content: ${error}`);
            return false;
        }
    }

    /**
     * 检测 JS 代码是否被压缩（minified）
     * @param code JS 代码字符串
     * @returns true 表示代码被压缩，false 表示未压缩
     */
    public static isMinified(code: string): boolean {
        if (!code || code.trim().length === 0) {
            return false;
        }

        const config = this.getConfig();
        const thresholds = config.minificationThresholds;

        const lines = code.split('\n');
        const totalLines = lines.length;

        // 1. 检查行数：如果只有很少的行但代码很长，可能是压缩的
        if (totalLines < thresholds.maxLines && code.length > 1000) {
            return true;
        }

        // 2. 计算平均行长度
        const avgLineLength = code.length / totalLines;
        if (avgLineLength > thresholds.avgLineLength) {
            return true;
        }

        // 3. 检查是否有很长的单行
        const hasVeryLongLine = lines.some(line => line.length > thresholds.maxLineLength);
        if (hasVeryLongLine) {
            return true;
        }

        // 4. 检查空白字符比例
        const whitespaceCount = (code.match(/\s/g) || []).length;
        const whitespaceRatio = whitespaceCount / code.length;
        if (whitespaceRatio < thresholds.whitespaceRatio) {
            return true;
        }

        return false;
    }

    /**
     * 格式化 JavaScript 代码
     * @param code JS 代码字符串
     * @param options 格式化选项
     * @returns 格式化后的代码
     */
    public static beautify(code: string, options?: {
        indent?: string;
        lineEnd?: string;
    }): string {
        try {
            const indentStyle = options?.indent ?? '  '; // 默认 2 空格缩进
            const lineEnd = options?.lineEnd ?? '\n';

            // 1. 解析代码为 AST
            let ast;
            try {
                ast = esprima.parseScript(code, { tolerant: true, loc: true, range: true });
            } catch {
                // 如果 parseScript 失败，尝试 parseModule
                ast = esprima.parseModule(code, { tolerant: true, loc: true, range: true });
            }

            // 2. 使用 escodegen 生成格式化的代码
            const formattedCode = escodegen.generate(ast, {
                format: {
                    indent: {
                        style: indentStyle,
                    },
                    newline: lineEnd,
                    space: ' ',
                    json: false,
                    renumber: false,
                    hexadecimal: false,
                    quotes: 'single',
                    escapeless: false,
                    compact: false,
                    parentheses: true,
                    semicolons: true,
                },
                comment: true,
            });

            return formattedCode;
        } catch (error) {
            logger.error(`Failed to beautify JavaScript code: ${error}`);
            throw new Error(`JavaScript beautification failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    /**
     * 格式化 JS 文件内容（自动检测是否需要格式化）
     * @param content 文件内容（Buffer 或字符串）
     * @param fileName 文件名（可选）
     * @param forceBeautify 是否强制格式化（默认：false，只格式化压缩的代码）
     * @returns 格式化后的代码字符串，如果不需要格式化则返回 null
     */
    public static beautifyFile(
        content: Buffer | string,
        fileName?: string,
        forceBeautify: boolean = false
    ): string | null {
        try {
            // 1. 检查是否为 JS 文件
            if (!this.isJavaScriptContent(content, fileName)) {
                return null;
            }

            // 2. 转换为字符串
            const code: string = content instanceof Buffer ? content.toString('utf-8') : content as string;

            // 3. 检查是否需要格式化
            if (!forceBeautify && !this.isMinified(code)) {
                logger.info(`File ${fileName ?? 'unknown'} is not minified, skipping beautification`);
                return null;
            }

            // 4. 格式化代码
            logger.info(`Beautifying ${fileName ?? 'unknown'}...`);
            const beautified = this.beautify(code);
            return beautified;
        } catch (error) {
            logger.warn(`Failed to beautify file ${fileName ?? 'unknown'}: ${error}`);
            return null;
        }
    }
}

