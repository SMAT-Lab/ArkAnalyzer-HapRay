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

// 导入具体的格式化器实现
import { JsonFormatter } from './json-report';
import { HtmlFormatter } from './html-report';
import { ExcelFormatter } from './excel-report';
import type { BaseFormatter } from './base-formatter';

/**
 * 支持的输出格式
 */
export enum OutputFormat {
    JSON = 'json',
    HTML = 'html',
    EXCEL = 'excel'
}

/**
 * 格式化选项
 */
export interface FormatOptions {
    /** 输出格式 */
    format: OutputFormat;
    /** 输出文件路径 */
    outputPath: string;
    /** 是否美化输出 */
    pretty?: boolean;
    /** 是否包含详细信息 */
    includeDetails?: boolean;
    /** 自定义模板路径（仅HTML格式） */
    templatePath?: string;
}

/**
 * 格式化结果
 */
export interface FormatResult {
    /** 输出文件路径 */
    filePath: string;
    /** 文件大小（字节） */
    fileSize: number;
    /** 格式化耗时（毫秒） */
    duration: number;
    /** 是否成功 */
    success: boolean;
    /** 错误信息（如果失败） */
    error?: string;
}

// 导出 BaseFormatter（从单独的文件导入以避免循环依赖）
export { BaseFormatter } from './base-formatter';

/**
 * 格式化器工厂
 */
export class FormatterFactory {
    /**
     * 创建格式化器
     * @param options 格式化选项
     * @returns 格式化器实例
     */
    static create(options: FormatOptions): BaseFormatter {
        switch (options.format) {
            case OutputFormat.JSON:
                return new JsonFormatter(options);
            case OutputFormat.HTML:
                return new HtmlFormatter(options);
            case OutputFormat.EXCEL:
                return new ExcelFormatter(options);
            default:
                throw new Error(`Unsupported output format: ${options.format}`);
        }
    }

    /**
     * 获取支持的格式列表
     */
    static getSupportedFormats(): Array<OutputFormat> {
        return Object.values(OutputFormat);
    }

    /**
     * 验证格式是否支持
     */
    static isFormatSupported(format: string): boolean {
        return Object.values(OutputFormat).includes(format as OutputFormat);
    }
}

// 重新导出格式化器实现
export { JsonFormatter, HtmlFormatter, ExcelFormatter };
